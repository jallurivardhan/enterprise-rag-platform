"""Multi-agent RAG pipeline orchestration."""

import time
from typing import Any, AsyncGenerator, Literal, Optional

from pydantic import BaseModel, Field

from src.agents.planner import Plan, PlannerAgent, RouteType
from src.agents.retriever import RetrieverAgent
from src.agents.validator import ValidationResult, ValidatorAgent
from src.core.logging import get_logger
from src.models.generator import Generator

logger = get_logger(__name__)


class StreamEvent(BaseModel):
    """Event for streaming RAG responses."""

    type: Literal["token", "sources", "metadata", "error", "done"] = Field(
        ..., description="Event type"
    )
    content: Optional[str] = Field(None, description="Token content (for token events)")
    sources: Optional[list[dict]] = Field(None, description="Source chunks (for sources events)")
    metadata: Optional[dict] = Field(None, description="Metadata (for metadata events)")
    error: Optional[str] = Field(None, description="Error message (for error events)")


class RAGResponse(BaseModel):
    """Complete RAG pipeline response."""

    answer: str = Field(..., description="Generated answer")
    sources: list[dict] = Field(..., description="Source chunks with scores")
    plan: dict = Field(..., description="Serialized Plan")
    validation: dict = Field(..., description="Serialized ValidationResult")
    metadata: dict = Field(..., description="Timing, tokens, and other metadata")


class RAGPipeline:
    """
    Main RAG orchestration pipeline.
    
    Coordinates Planner, Retriever, Validator, and Generator agents
    into a complete query processing flow with retry logic and streaming support.
    """

    def __init__(
        self,
        planner: PlannerAgent,
        retriever: RetrieverAgent,
        validator: ValidatorAgent,
        generator: Generator,
    ) -> None:
        """
        Initialize the RAG pipeline.

        Args:
            planner: Planner agent instance
            retriever: Retriever agent instance
            validator: Validator agent instance
            generator: Generator instance
        """
        self.planner = planner
        self.retriever = retriever
        self.validator = validator
        self.generator = generator
        logger.info("RAG pipeline initialized with dependency injection")

    async def run(self, query: str, conversation_id: Optional[str] = None, max_retries: int = 2) -> RAGResponse:
        """
        Run the complete RAG pipeline.

        Args:
            query: User's query
            conversation_id: Optional conversation ID for context-aware responses
            max_retries: Maximum number of retry attempts if validation fails

        Returns:
            RAGResponse: Complete response with answer, sources, plan, validation, and metadata
        """
        pipeline_start = time.time()
        request_id = f"req_{int(time.time() * 1000)}"

        # Get conversation history context
        enhanced_query = query
        if conversation_id:
            from src.services.conversation_memory import conversation_memory
            history_context = conversation_memory.get_context_string(conversation_id)
            if history_context:
                enhanced_query = f"Previous conversation:\n{history_context}\n\nCurrent question: {query}"
                logger.info("Using conversation context", request_id=request_id, conversation_id=conversation_id)

        logger.info("RAG pipeline started", request_id=request_id, query=query[:100])

        # Initialize response components
        source_chunks = []
        answer = ""
        validation_result: Optional[ValidationResult] = None
        generation_result = None
        timing = {
            "planning_time_ms": 0.0,
            "retrieval_time_ms": 0.0,
            "generation_time_ms": 0.0,
            "validation_time_ms": 0.0,
            "total_time_ms": 0.0,
        }

        # Initialize plan with default (for outer exception handler safety)
        plan = Plan(
            route=RouteType.RAG_ONLY,
            reasoning="Direct RAG retrieval",
            retrieval_query=query,
            num_chunks=5,
            confidence=0.9
        )

        try:
            # BYPASS: Skip planner, always do RAG
            planning_start = time.time()
            plan = Plan(
                route=RouteType.RAG_ONLY,
                reasoning="Direct RAG retrieval",
                retrieval_query=enhanced_query,  # Use enhanced query with conversation context
                num_chunks=5,
                confidence=0.9
            )
            timing["planning_time_ms"] = (time.time() - planning_start) * 1000

            logger.info(
                "Planning bypassed - using direct RAG",
                request_id=request_id,
                route=plan.route.value,
                num_chunks=plan.num_chunks,
                confidence=plan.confidence,
                duration_ms=round(timing["planning_time_ms"], 2),
            )

            # Step 2: Handle special routes
            if plan.route == RouteType.REFUSE:
                answer = "I cannot answer this query as it appears to be out of scope or inappropriate."
                validation_result = ValidationResult(
                    is_valid=True,
                    confidence=0.9,
                    issues=[],
                    is_grounded=False,
                    check_results={},
                )
                timing["total_time_ms"] = (time.time() - pipeline_start) * 1000
                return self._build_response(
                    answer=answer,
                    sources=[],
                    plan=plan,
                    validation=validation_result,
                    timing=timing,
                    generation_result=None,
                )

            if plan.route == RouteType.CLARIFY:
                answer = f"Could you please clarify your question? {plan.reasoning}"
                validation_result = ValidationResult(
                    is_valid=True,
                    confidence=0.7,
                    issues=[],
                    is_grounded=False,
                    check_results={},
                )
                timing["total_time_ms"] = (time.time() - pipeline_start) * 1000
                return self._build_response(
                    answer=answer,
                    sources=[],
                    plan=plan,
                    validation=validation_result,
                    timing=timing,
                    generation_result=None,
                )

            # Step 3: Retrieval (with retry logic)
            retrieval_start = time.time()
            retry_count = 0
            use_rerank = plan.route == RouteType.RAG_WITH_RERANK

            while retry_count <= max_retries:
                try:
                    # Try hybrid retrieval if available
                    from src.services.hybrid_retriever import hybrid_retriever
                    from src.services.bm25_search import bm25_search
                    
                    if hybrid_retriever and hybrid_retriever.indexed and len(bm25_search.documents) > 0:
                        # Use hybrid retrieval
                        retrieval_result = await hybrid_retriever.retrieve(
                            plan.retrieval_query,
                            k=plan.num_chunks + (retry_count * 2),
                            min_score=0.1 - (retry_count * 0.02),
                        )
                    elif use_rerank or retry_count > 0:
                        # Use reranking (either from plan or retry)
                        retrieval_result = await self.retriever.retrieve_with_rerank(
                            plan.retrieval_query,
                            k=plan.num_chunks + (retry_count * 2),  # Increase chunks on retry
                            initial_k=(plan.num_chunks + (retry_count * 2)) * 3,
                        )
                    else:
                        retrieval_result = await self.retriever.retrieve(
                            plan.retrieval_query,
                            k=plan.num_chunks + (retry_count * 2),
                            min_score=0.3 - (retry_count * 0.05),  # Lower threshold on retry
                        )

                    source_chunks = retrieval_result.chunks
                    timing["retrieval_time_ms"] = (time.time() - retrieval_start) * 1000

                    logger.info(
                        "Retrieval completed",
                        request_id=request_id,
                        chunks_retrieved=len(source_chunks),
                        retry_count=retry_count,
                        duration_ms=round(timing["retrieval_time_ms"], 2),
                    )

                    if not source_chunks:
                        if retry_count < max_retries:
                            retry_count += 1
                            logger.warning(
                                "No chunks retrieved, retrying",
                                request_id=request_id,
                                retry_count=retry_count,
                            )
                            continue
                        else:
                            answer = "I couldn't find relevant information to answer your question. Please try rephrasing or check if the documents contain the information you're looking for."
                            validation_result = ValidationResult(
                                is_valid=False,
                                confidence=0.3,
                                issues=["No relevant chunks retrieved"],
                                is_grounded=False,
                                check_results={},
                            )
                            timing["total_time_ms"] = (time.time() - pipeline_start) * 1000
                            return self._build_response(
                                answer=answer,
                                sources=[],
                                plan=plan,
                                validation=validation_result,
                                timing=timing,
                                generation_result=None,
                            )

                    break  # Success, exit retry loop

                except Exception as e:
                    logger.error(
                        "Retrieval failed",
                        request_id=request_id,
                        error=str(e),
                        retry_count=retry_count,
                    )
                    if retry_count < max_retries:
                        retry_count += 1
                        continue
                    else:
                        # Return error response
                        answer = f"An error occurred while retrieving information: {str(e)}"
                        validation_result = ValidationResult(
                            is_valid=False,
                            confidence=0.0,
                            issues=[f"Retrieval error: {str(e)}"],
                            is_grounded=False,
                            check_results={},
                        )
                        timing["total_time_ms"] = (time.time() - pipeline_start) * 1000
                        return self._build_response(
                            answer=answer,
                            sources=[],
                            plan=plan,
                            validation=validation_result,
                            timing=timing,
                            generation_result=None,
                        )

            # Step 4: Generation
            generation_start = time.time()
            try:
                generation_result = await self.generator.generate_from_chunks(
                    query, source_chunks
                )
                answer = generation_result.content
                timing["generation_time_ms"] = (time.time() - generation_start) * 1000

                logger.info(
                    "Generation completed",
                    request_id=request_id,
                    answer_length=len(answer),
                    tokens_used=generation_result.tokens_used,
                    duration_ms=round(timing["generation_time_ms"], 2),
                )
            except Exception as e:
                logger.error("Generation failed", request_id=request_id, error=str(e))
                answer = f"An error occurred while generating the response: {str(e)}"
                generation_result = None
                timing["generation_time_ms"] = (time.time() - generation_start) * 1000

            # Step 5: Validation
            validation_start = time.time()
            try:
                validation_result = await self.validator.validate(query, answer, source_chunks)
                timing["validation_time_ms"] = (time.time() - validation_start) * 1000

                logger.info(
                    "Validation completed",
                    request_id=request_id,
                    is_valid=validation_result.is_valid,
                    confidence=validation_result.confidence,
                    is_grounded=validation_result.is_grounded,
                    duration_ms=round(timing["validation_time_ms"], 2),
                )

                # Retry logic: If validation fails and retries remaining
                if (
                    not validation_result.is_valid
                    and retry_count < max_retries
                    and source_chunks
                ):
                    retry_count += 1
                    logger.warning(
                        "Validation failed, retrying with adjusted strategy",
                        request_id=request_id,
                        retry_count=retry_count,
                        issues=validation_result.issues,
                    )

                    # Adjust strategy based on validation issues
                    if not validation_result.is_grounded:
                        # Try reranking if not already using it
                        use_rerank = True
                        plan.num_chunks = min(20, plan.num_chunks + 3)

                    # Retry from retrieval step
                    retrieval_start = time.time()
                    if use_rerank:
                        retrieval_result = await self.retriever.retrieve_with_rerank(
                            plan.retrieval_query,
                            k=plan.num_chunks,
                            initial_k=plan.num_chunks * 3,
                        )
                    else:
                        retrieval_result = await self.retriever.retrieve(
                            plan.retrieval_query, k=plan.num_chunks, min_score=0.2
                        )

                    source_chunks = retrieval_result.chunks
                    timing["retrieval_time_ms"] += (time.time() - retrieval_start) * 1000

                    # Regenerate
                    generation_start = time.time()
                    generation_result = await self.generator.generate_from_chunks(
                        query, source_chunks
                    )
                    answer = generation_result.content
                    timing["generation_time_ms"] += (time.time() - generation_start) * 1000

                    # Re-validate
                    validation_start = time.time()
                    validation_result = await self.validator.validate(
                        query, answer, source_chunks
                    )
                    timing["validation_time_ms"] += (time.time() - validation_start) * 1000

            except Exception as e:
                logger.error("Validation failed", request_id=request_id, error=str(e))
                validation_result = ValidationResult(
                    is_valid=False,
                    confidence=0.5,
                    issues=[f"Validation error: {str(e)}"],
                    is_grounded=False,
                    check_results={},
                )
                timing["validation_time_ms"] = (time.time() - validation_start) * 1000

            # Format sources
            sources = [
                {
                    "document_id": chunk.metadata.document_id,
                    "filename": chunk.metadata.source_file,
                    "chunk_index": chunk.metadata.chunk_index,
                    "page_number": chunk.metadata.page_number,
                    "score": chunk.score,
                    "rank": chunk.rank,
                    "content": chunk.content,  # Include content for API responses
                }
                for chunk in source_chunks
            ]

            timing["total_time_ms"] = (time.time() - pipeline_start) * 1000

            logger.info(
                "RAG pipeline completed",
                request_id=request_id,
                answer_length=len(answer),
                sources_count=len(sources),
                is_valid=validation_result.is_valid if validation_result else False,
                total_duration_ms=round(timing["total_time_ms"], 2),
            )

            return self._build_response(
                answer=answer,
                sources=sources,
                plan=plan,
                validation=validation_result or ValidationResult(
                    is_valid=False, confidence=0.0, issues=[], is_grounded=False, check_results={}
                ),
                timing=timing,
                generation_result=generation_result,
            )

        except Exception as e:
            logger.error("RAG pipeline failed", request_id=request_id, error=str(e))
            timing["total_time_ms"] = (time.time() - pipeline_start) * 1000

            # Return error response (plan is always defined now)
            return self._build_response(
                answer=f"An unexpected error occurred: {str(e)}",
                sources=[],
                plan=plan,
                validation=ValidationResult(
                    is_valid=False,
                    confidence=0.0,
                    issues=[f"Pipeline error: {str(e)}"],
                    is_grounded=False,
                    check_results={},
                ),
                timing=timing,
                generation_result=None,
            )

    async def run_stream(self, query: str) -> AsyncGenerator[StreamEvent, None]:
        """
        Run the RAG pipeline with streaming output.

        Args:
            query: User's query

        Yields:
            StreamEvent: Streaming events (token, sources, metadata, error, done)
        """
        request_id = f"req_{int(time.time() * 1000)}"
        logger.info("RAG pipeline streaming started", request_id=request_id, query=query[:100])

        try:
            # Step 1: Planning
            yield StreamEvent(
                type="metadata",
                metadata={"step": "planning", "status": "in_progress"},
            )

            try:
                plan = await self.planner.plan(query)
                yield StreamEvent(
                    type="metadata",
                    metadata={
                        "step": "planning",
                        "status": "completed",
                        "route": plan.route.value,
                        "num_chunks": plan.num_chunks,
                    },
                )
            except Exception as e:
                logger.error("Planning failed in stream", request_id=request_id, error=str(e))
                yield StreamEvent(
                    type="error",
                    error=f"Planning failed: {str(e)}",
                )
                yield StreamEvent(type="done")
                return

            # Handle special routes
            if plan.route == RouteType.REFUSE:
                yield StreamEvent(
                    type="token",
                    content="I cannot answer this query as it appears to be out of scope or inappropriate.",
                )
                yield StreamEvent(type="sources", sources=[])
                yield StreamEvent(type="done")
                return

            if plan.route == RouteType.CLARIFY:
                yield StreamEvent(
                    type="token",
                    content=f"Could you please clarify your question? {plan.reasoning}",
                )
                yield StreamEvent(type="sources", sources=[])
                yield StreamEvent(type="done")
                return

            # Step 2: Retrieval
            yield StreamEvent(
                type="metadata",
                metadata={"step": "retrieval", "status": "in_progress"},
            )

            try:
                if plan.route == RouteType.RAG_WITH_RERANK:
                    retrieval_result = await self.retriever.retrieve_with_rerank(
                        plan.retrieval_query, k=plan.num_chunks, initial_k=plan.num_chunks * 3
                    )
                else:
                    retrieval_result = await self.retriever.retrieve(
                        plan.retrieval_query, k=plan.num_chunks, min_score=0.3
                    )

                source_chunks = retrieval_result.chunks

                yield StreamEvent(
                    type="metadata",
                    metadata={
                        "step": "retrieval",
                        "status": "completed",
                        "chunks_retrieved": len(source_chunks),
                    },
                )
            except Exception as e:
                logger.error("Retrieval failed in stream", request_id=request_id, error=str(e))
                yield StreamEvent(
                    type="error",
                    error=f"Retrieval failed: {str(e)}",
                )
                yield StreamEvent(type="done")
                return

            # Step 3: Generation (streaming)
            yield StreamEvent(
                type="metadata",
                metadata={"step": "generation", "status": "in_progress"},
            )

            try:
                # Format context for streaming
                context = self.generator.format_context(source_chunks)

                # Stream generation
                async for token in self.generator.generate_stream(
                    query, context
                ):
                    yield StreamEvent(type="token", content=token)

                yield StreamEvent(
                    type="metadata",
                    metadata={"step": "generation", "status": "completed"},
                )
            except Exception as e:
                logger.error("Generation failed in stream", request_id=request_id, error=str(e))
                yield StreamEvent(
                    type="error",
                    error=f"Generation failed: {str(e)}",
                )
                yield StreamEvent(type="done")
                return

            # Step 4: Format and yield sources
            sources = [
                {
                    "document_id": chunk.metadata.document_id,
                    "filename": chunk.metadata.source_file,
                    "chunk_index": chunk.metadata.chunk_index,
                    "page_number": chunk.metadata.page_number,
                    "score": chunk.score,
                    "rank": chunk.rank,
                    "content": chunk.content,  # Include content for API responses
                }
                for chunk in source_chunks
            ]

            yield StreamEvent(type="sources", sources=sources)

            # Final metadata
            yield StreamEvent(
                type="metadata",
                metadata={
                    "step": "complete",
                    "status": "completed",
                    "sources_count": len(sources),
                },
            )

            yield StreamEvent(type="done")

        except Exception as e:
            logger.error("Streaming pipeline failed", request_id=request_id, error=str(e))
            yield StreamEvent(
                type="error",
                error=f"Pipeline error: {str(e)}",
            )
            yield StreamEvent(type="done")

    def _build_response(
        self,
        answer: str,
        sources: list[dict],
        plan: Plan,
        validation: ValidationResult,
        timing: dict,
        generation_result: Optional[Any],
    ) -> RAGResponse:
        """
        Build RAGResponse from components.

        Args:
            answer: Generated answer
            sources: Source chunks
            plan: Plan object
            validation: Validation result
            timing: Timing dictionary
            generation_result: Generation result (optional)

        Returns:
            RAGResponse: Complete response
        """
        metadata = {
            "timing": timing,
            "tokens_used": generation_result.tokens_used if generation_result else 0,
            "model": generation_result.model if generation_result else None,
        }

        return RAGResponse(
            answer=answer,
            sources=sources,
            plan=plan.model_dump(),
            validation=validation.model_dump(),
            metadata=metadata,
        )
