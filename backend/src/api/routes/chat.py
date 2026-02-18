"""Chat API endpoints for RAG queries."""

import json
import time
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from src.services.auth import get_current_user, check_rate_limit
from pydantic import BaseModel, Field, field_validator
from sse_starlette.sse import EventSourceResponse

from src.agents.planner import PlannerAgent
from src.agents.retriever import RetrieverAgent
from src.agents.validator import ValidatorAgent
from src.core.logging import get_logger
from src.db import FAISSVectorStore
from src.models.embeddings import EmbeddingModel
from src.models.generator import Generator
from src.services.rag_pipeline import RAGPipeline
from src.agentic_rag import AgenticRAGPipeline, AgenticResponse, ReasoningStep
from src.query_classifier import query_classifier, QueryClassification

# Import dependencies from ingest routes
from src.api.routes.ingest import get_vector_store

logger = get_logger(__name__)

router = APIRouter(tags=["Chat"])

# Test endpoint to verify router is working
@router.get("/test")
async def chat_test():
    """Test endpoint to verify chat router is loaded."""
    return {"status": "chat router is working", "endpoint": "/api/chat"}

# Global RAG pipeline instance (singleton)
_rag_pipeline: Optional[RAGPipeline] = None


def get_rag_pipeline() -> RAGPipeline:
    """Dependency to get RAG pipeline instance."""
    global _rag_pipeline
    if _rag_pipeline is None:
        vector_store = get_vector_store()
        embedding_model = EmbeddingModel()
        
        # Initialize all agents
        planner = PlannerAgent()
        retriever = RetrieverAgent(vector_store, embedding_model)
        validator = ValidatorAgent()
        generator = Generator()
        
        _rag_pipeline = RAGPipeline(planner, retriever, validator, generator)
        logger.info("RAG pipeline initialized for chat")
    
    return _rag_pipeline


_agentic_pipeline: Optional[AgenticRAGPipeline] = None


def get_agentic_pipeline() -> AgenticRAGPipeline:
    """Dependency to get Agentic RAG pipeline instance."""
    global _agentic_pipeline
    if _agentic_pipeline is None:
        from src.api.routes.ingest import get_vector_store
        from src.models.embeddings import EmbeddingModel
        from src.agents.retriever import RetrieverAgent
        from src.models.generator import Generator

        vector_store = get_vector_store()
        embedding_model = EmbeddingModel()
        retriever = RetrieverAgent(vector_store, embedding_model)
        generator = Generator()
        _agentic_pipeline = AgenticRAGPipeline(retriever, generator)
        logger.info("Agentic RAG pipeline initialized")
    return _agentic_pipeline


# Request/Response Models
class ChatRequest(BaseModel):
    """Chat request model."""

    query: str = Field(..., min_length=1, max_length=2000, description="User's query")
    conversation_id: Optional[str] = Field(None, description="Conversation ID for tracking")
    mode: Optional[str] = Field("normal", description="RAG mode: normal, agentic, or auto")

    @field_validator("query")
    @classmethod
    def sanitize_query(cls, v: str) -> str:
        return v.strip()

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, v: str) -> str:
        if v not in ["normal", "agentic", "auto"]:
            return "normal"
        return v


class SourceInfo(BaseModel):
    """Source information model."""

    content: str = Field(..., description="Chunk content")
    filename: str = Field(..., description="Source filename")
    page_number: Optional[int] = Field(None, description="Page number (for PDFs)")
    chunk_index: int = Field(..., description="Chunk index in document")
    score: float = Field(..., description="Relevance score")


class ResponseMetadata(BaseModel):
    """Response metadata model."""

    planning_time_ms: float = Field(..., description="Planning time in milliseconds")
    retrieval_time_ms: float = Field(..., description="Retrieval time in milliseconds")
    generation_time_ms: float = Field(..., description="Generation time in milliseconds")
    validation_time_ms: float = Field(..., description="Validation time in milliseconds")
    total_time_ms: float = Field(..., description="Total processing time in milliseconds")
    model_used: Optional[str] = Field(None, description="Model used for generation")


class TrustScore(BaseModel):
    """Trust score information for AI responses."""

    grounding_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="How well answer is grounded in sources (0-1)",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Overall confidence score (0-1)",
    )
    is_grounded: bool = Field(..., description="Whether answer is well-supported by sources")
    is_valid: bool = Field(..., description="Whether answer passes all quality checks")
    hallucination_risk: str = Field(..., description="Hallucination risk level: low, medium, high")
    issues: list[str] = Field(
        default_factory=list,
        description="List of validation issues found",
    )
    check_results: dict[str, bool] = Field(
        default_factory=dict,
        description="Individual check results",
    )


class CostInfo(BaseModel):
    """Cost information for the API request."""

    input_tokens: int = Field(0, description="Number of input tokens used")
    output_tokens: int = Field(0, description="Number of output tokens used")
    total_tokens: int = Field(0, description="Total tokens used")
    estimated_cost_usd: float = Field(0.0, description="Estimated cost in USD")
    model: str = Field("gpt-4o-mini", description="Model used for generation")


class ReasoningStepResponse(BaseModel):
    """Reasoning step for agentic responses."""

    step_number: int = Field(..., description="Step number in reasoning chain")
    action: str = Field(
        ...,
        description="Action taken: analyze, retrieve, synthesize, verify, complete",
    )
    thought: str = Field(..., description="Agent's reasoning")
    result: Optional[str] = Field(None, description="Outcome of this step")
    sub_query: Optional[str] = Field(None, description="Sub-query if retrieving")
    chunks_found: Optional[int] = Field(None, description="Chunks found if retrieving")


class QueryClassificationResponse(BaseModel):
    """Query classification result."""

    complexity: str = Field(..., description="simple or complex")
    confidence: float = Field(..., description="Classification confidence")
    recommended_mode: str = Field(..., description="normal or agentic")
    reasoning: str = Field(..., description="Why this classification")


class ChatResponse(BaseModel):
    """Chat response model."""

    answer: str = Field(..., description="Generated answer")
    sources: list[dict] = Field(..., description="List of source chunks")
    conversation_id: Optional[str] = Field(None, description="Conversation ID")
    trust: Optional[TrustScore] = Field(
        None,
        description="Trust and grounding information",
    )
    cost: Optional[CostInfo] = Field(
        None,
        description="Token usage and cost information",
    )
    mode_used: str = Field("normal", description="RAG mode that was used")
    reasoning_steps: Optional[list[ReasoningStepResponse]] = Field(
        None, description="Agentic reasoning steps"
    )
    classification: Optional[QueryClassificationResponse] = Field(
        None, description="Query classification for auto mode"
    )
    sub_queries: Optional[list[str]] = Field(
        None, description="Sub-queries used in agentic mode"
    )


class FeedbackRequest(BaseModel):
    """Feedback request model."""

    query: str = Field(..., description="User's query")
    answer: str = Field(..., description="AI's answer")
    rating: str = Field(..., description="Rating: 'up' or 'down'")
    conversation_id: Optional[str] = Field(None, description="Conversation ID")


@router.post("/", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    current_user: dict = Depends(check_rate_limit),
    rag_pipeline: RAGPipeline = Depends(get_rag_pipeline),
) -> ChatResponse:
    """Process a chat query using the RAG pipeline (rate limited). Supports normal, agentic, and auto modes."""
    from src.services.conversation_memory import conversation_memory

    logger.info(
        "CHAT_ENDPOINT_CALLED",
        endpoint="/api/chat",
        query=request.query[:50],
        mode=request.mode,
    )
    request_id = str(uuid.uuid4())[:8]

    try:
        # Create or use existing conversation
        conv_id = request.conversation_id
        if not conv_id:
            conv_id = conversation_memory.create_conversation()

        # Determine which mode to use
        mode = request.mode or "normal"
        classification = None

        # Auto mode: classify the query
        if mode == "auto":
            classification_result = await query_classifier.classify(request.query)
            mode = classification_result.recommended_mode
            classification = QueryClassificationResponse(
                complexity=classification_result.complexity,
                confidence=classification_result.confidence,
                recommended_mode=classification_result.recommended_mode,
                reasoning=classification_result.reasoning,
            )
            logger.info(
                "Auto mode classification",
                complexity=classification_result.complexity,
                recommended=mode,
            )

        # Execute based on mode
        if mode == "agentic":
            # Use Agentic RAG
            agentic_pipeline = get_agentic_pipeline()
            response = await agentic_pipeline.run(request.query, conversation_id=conv_id)

            # Format response
            sources = response.sources
            reasoning_steps = [
                ReasoningStepResponse(
                    step_number=step.step_number,
                    action=step.action,
                    thought=step.thought,
                    result=step.result,
                    sub_query=step.sub_query,
                    chunks_found=step.chunks_found,
                )
                for step in response.reasoning_steps
            ]

            # Build trust score from agentic response
            avg_score = sum(s.get("score", 0) for s in sources) / max(len(sources), 1)
            trust_score = TrustScore(
                grounding_score=avg_score,
                confidence=avg_score,
                is_grounded=avg_score > 0.5,
                is_valid=len(sources) > 0,
                hallucination_risk=(
                    "low"
                    if avg_score > 0.7
                    else "medium"
                    if avg_score > 0.4
                    else "high"
                ),
                issues=[] if avg_score > 0.5 else ["Weak grounding in sources"],
                check_results={
                    "length": True,
                    "relevance": avg_score > 0.3,
                    "grounding": avg_score > 0.5,
                    "citation": True,
                    "hallucination": avg_score > 0.4,
                },
            )

            # Build cost info (estimate based on agentic iterations)
            estimated_tokens = response.iterations * 2000 + 1500
            cost_info = CostInfo(
                input_tokens=int(estimated_tokens * 0.7),
                output_tokens=int(estimated_tokens * 0.3),
                total_tokens=estimated_tokens,
                estimated_cost_usd=round((estimated_tokens / 1_000_000) * 0.30, 6),
                model="gpt-4o-mini",
            )

            # Store in conversation memory
            conversation_memory.add_message(conv_id, "user", request.query)
            conversation_memory.add_message(conv_id, "assistant", response.answer, sources)

            return ChatResponse(
                answer=response.answer,
                sources=sources,
                conversation_id=conv_id,
                trust=trust_score,
                cost=cost_info,
                mode_used="agentic",
                reasoning_steps=reasoning_steps,
                classification=classification,
                sub_queries=response.sub_queries_used,
            )

        else:
            # Use Normal RAG (normal mode)
            response = await rag_pipeline.run(
                request.query, conversation_id=conv_id, max_retries=2
            )

            # Format sources
            sources = []
            for source in response.sources:
                sources.append(
                    {
                        "content": source.get("content", "")[:500],
                        "filename": source.get("filename", "Unknown"),
                        "page_number": source.get("page_number"),
                        "chunk_index": source.get("chunk_index", 0),
                        "score": source.get("score", 0.0),
                    }
                )

            # Store in conversation memory
            conversation_memory.add_message(conv_id, "user", request.query)
            conversation_memory.add_message(
                conv_id, "assistant", response.answer, sources
            )

            # Build metadata
            metadata = response.metadata if isinstance(response.metadata, dict) else {}

            # Build trust score
            trust_score = None
            if response.validation:
                validation = response.validation
                confidence = validation.get("confidence", 0.5)
                is_grounded = validation.get("is_grounded", False)
                hallucination_check = validation.get("check_results", {}).get(
                    "hallucination", True
                )

                if (
                    confidence >= 0.8
                    and is_grounded
                    and hallucination_check
                ):
                    hallucination_risk = "low"
                elif confidence >= 0.5 and (
                    is_grounded or hallucination_check
                ):
                    hallucination_risk = "medium"
                else:
                    hallucination_risk = "high"

                trust_score = TrustScore(
                    grounding_score=confidence,
                    confidence=confidence,
                    is_grounded=is_grounded,
                    is_valid=validation.get("is_valid", False),
                    hallucination_risk=hallucination_risk,
                    issues=validation.get("issues", []),
                    check_results=validation.get("check_results", {}),
                )

            # Build cost info
            cost_info = None
            if metadata:
                tokens_used = metadata.get("tokens_used", 0)
                model_name = metadata.get("model", "gpt-4o-mini")
                input_tokens = int(tokens_used * 0.7)
                output_tokens = int(tokens_used * 0.3)
                input_cost = (input_tokens / 1_000_000) * 0.15
                output_cost = (output_tokens / 1_000_000) * 0.60
                total_cost = input_cost + output_cost

                cost_info = CostInfo(
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    total_tokens=tokens_used,
                    estimated_cost_usd=round(total_cost, 6),
                    model=model_name or "gpt-4o-mini",
                )

            # Log for analytics
            from src.services.analytics_store import analytics_store

            analytics_store.log_query(
                query=request.query,
                response_time_ms=metadata.get("total_time_ms", 0),
                sources_count=len(sources),
                conversation_id=conv_id,
            )

            return ChatResponse(
                answer=response.answer,
                sources=sources,
                conversation_id=conv_id,
                trust=trust_score,
                cost=cost_info,
                mode_used="normal",
                reasoning_steps=None,
                classification=classification,
                sub_queries=None,
            )

    except Exception as e:
        logger.error("chat_error", request_id=request_id, error=str(e))
        raise HTTPException(
            status_code=500, detail=f"Chat processing failed: {str(e)}"
        )


@router.get("/history/{conversation_id}")
async def get_history(conversation_id: str):
    """Get conversation history for a given conversation ID."""
    from src.services.conversation_memory import conversation_memory
    
    history = conversation_memory.get_history(conversation_id)
    if not history:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    return {
        "conversation_id": conversation_id,
        "messages": history
    }


@router.get("/hybrid-status")
async def get_hybrid_status():
    """Check if hybrid search is enabled."""
    from src.services.bm25_search import bm25_search
    from src.services.hybrid_retriever import hybrid_retriever
    
    return {
        "bm25_indexed": len(bm25_search.documents) > 0,
        "documents_indexed": len(bm25_search.documents),
        "hybrid_enabled": hybrid_retriever is not None and hybrid_retriever.indexed if hybrid_retriever else False
    }


@router.get("/analytics")
async def get_analytics():
    """Get usage analytics."""
    from src.services.analytics_store import analytics_store
    from src.services.feedback_store import feedback_store
    
    stats = analytics_store.get_stats()
    feedback_stats = feedback_store.get_stats()
    
    return {
        "usage": stats,
        "feedback": feedback_stats,
        "popular_topics": analytics_store.get_popular_queries(10),
        "recent_queries": analytics_store.get_recent_queries(10),
        "hourly_distribution": analytics_store.get_hourly_distribution()
    }


@router.post("/feedback")
async def submit_feedback(request: FeedbackRequest):
    """Submit feedback for a response."""
    from src.services.feedback_store import feedback_store
    
    if request.rating not in ["up", "down"]:
        raise HTTPException(status_code=400, detail="Rating must be 'up' or 'down'")
    
    entry = feedback_store.add_feedback(
        query=request.query,
        answer=request.answer,
        rating=request.rating,
        conversation_id=request.conversation_id
    )
    return {"status": "success", "feedback_id": entry["id"]}


@router.get("/feedback/stats")
async def get_feedback_stats():
    """Get feedback statistics."""
    from src.services.feedback_store import feedback_store
    return feedback_store.get_stats()


@router.get("/rate-limit")
async def get_rate_limit_status(current_user: dict = Depends(get_current_user)):
    """Get current rate limit status for user."""
    from src.services.rate_limiter import rate_limiter
    return rate_limiter.check_rate_limit(current_user["id"])


@router.post("/stream")
async def chat_stream(
    request: ChatRequest,
    current_user: dict = Depends(get_current_user),
    rag_pipeline: RAGPipeline = Depends(get_rag_pipeline),
) -> EventSourceResponse:
    """
    Stream chat responses using Server-Sent Events (SSE).

    Args:
        request: Chat request with query and optional conversation_id
        rag_pipeline: RAG pipeline dependency

    Returns:
        EventSourceResponse: SSE stream of events
    """
    request_id = str(uuid.uuid4())
    request_start = time.time()
    query_preview = request.query[:100] + ("..." if len(request.query) > 100 else "")

    logger.info(
        "Chat stream request received",
        request_id=request_id,
        query_preview=query_preview,
        conversation_id=request.conversation_id,
    )

    async def event_generator():
        """Generate SSE events from RAG pipeline stream."""
        try:
            async for event in rag_pipeline.run_stream(request.query):
                # Convert StreamEvent to SSE format
                event_data = {}

                if event.type == "token" and event.content:
                    event_data = {"content": event.content}
                elif event.type == "sources" and event.sources:
                    event_data = {"sources": event.sources}
                elif event.type == "metadata" and event.metadata:
                    event_data = event.metadata
                elif event.type == "error" and event.error:
                    event_data = {"message": event.error}
                elif event.type == "done":
                    elapsed = time.time() - request_start
                    event_data = {
                        "status": "complete",
                        "total_time_ms": round(elapsed * 1000, 2),
                    }

                # Yield the main event
                yield {
                    "event": event.type,
                    "data": json.dumps(event_data, ensure_ascii=False),
                }

                # After yielding sources, calculate and yield trust data
                if event.type == "sources" and event.sources:
                    # Calculate trust score from sources
                    source_count = len(event.sources) if event.sources else 0
                    avg_score = sum(s.get("score", 0) for s in event.sources) / max(source_count, 1)

                    trust_data = {
                        "grounding_score": avg_score,
                        "confidence": avg_score,
                        "is_grounded": avg_score > 0.5,
                        "is_valid": source_count > 0,
                        "hallucination_risk": "low"
                        if avg_score > 0.7
                        else "medium"
                        if avg_score > 0.4
                        else "high",
                        "issues": [] if avg_score > 0.5 else ["Weak grounding in sources"],
                        "check_results": {
                            "length": True,
                            "relevance": avg_score > 0.3,
                            "grounding": avg_score > 0.5,
                            "citation": True,
                            "hallucination": avg_score > 0.4,
                        },
                    }

                    yield {
                        "event": "trust",
                        "data": json.dumps(trust_data, ensure_ascii=False),
                    }

            logger.info(
                "Chat stream completed",
                request_id=request_id,
                query_preview=query_preview,
                duration_ms=round((time.time() - request_start) * 1000, 2),
            )

        except Exception as e:
            elapsed = time.time() - request_start
            logger.error(
                "Chat stream failed",
                request_id=request_id,
                query_preview=query_preview,
                error=str(e),
                error_type=type(e).__name__,
                duration_ms=round(elapsed * 1000, 2),
            )
            yield {
                "event": "error",
                "data": json.dumps({"message": str(e)}, ensure_ascii=False),
            }
            yield {
                "event": "done",
                "data": json.dumps({"status": "error"}, ensure_ascii=False),
            }

    return EventSourceResponse(event_generator())
