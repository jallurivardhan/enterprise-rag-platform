"""Agentic RAG pipeline with multi-step reasoning."""

import time
import json
from typing import Optional, List
from pydantic import BaseModel, Field
from openai import AsyncOpenAI
from src.core.config import settings
from src.core.logging import get_logger
from src.agents.retriever import RetrieverAgent, RetrievedChunk
from src.models.generator import Generator

logger = get_logger(__name__)


class ReasoningStep(BaseModel):
    """A single reasoning step in the agentic process."""

    step_number: int
    action: str  # "analyze", "decompose", "retrieve", "synthesize", "verify", "complete"
    thought: str  # What the agent is thinking
    result: Optional[str] = None  # Outcome of this step
    sub_query: Optional[str] = None  # If retrieving, what query
    chunks_found: Optional[int] = None  # Number of chunks retrieved


class AgenticResponse(BaseModel):
    """Response from the agentic RAG pipeline."""

    answer: str
    sources: List[dict]
    reasoning_steps: List[ReasoningStep]
    total_reasoning_time_ms: float
    sub_queries_used: List[str]
    iterations: int
    metadata: dict


class AgenticRAGPipeline:
    def __init__(self, retriever: RetrieverAgent, generator: Generator):
        self.retriever = retriever
        self.generator = generator
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.logger = get_logger(__name__)
        self.max_iterations = 4  # Prevent infinite loops

    async def run(self, query: str, conversation_id: Optional[str] = None) -> AgenticResponse:
        """Run the agentic RAG pipeline with multi-step reasoning."""
        start_time = time.time()
        reasoning_steps = []
        all_chunks = []
        sub_queries = []

        # Step 1: Analyze query complexity and decompose if needed
        step = ReasoningStep(
            step_number=1,
            action="analyze",
            thought="Analyzing query to determine if it needs decomposition...",
        )

        decomposition = await self._decompose_query(query)
        step.result = f"Identified {len(decomposition)} sub-questions"
        reasoning_steps.append(step)

        # Step 2: Retrieve for each sub-query
        for i, sub_query in enumerate(decomposition):
            sub_queries.append(sub_query)
            step = ReasoningStep(
                step_number=len(reasoning_steps) + 1,
                action="retrieve",
                thought=f"Retrieving information for: {sub_query}",
                sub_query=sub_query,
            )

            try:
                result = await self.retriever.retrieve(sub_query, k=3, min_score=0.3)
                chunks = result.chunks
                all_chunks.extend(chunks)
                step.result = f"Found {len(chunks)} relevant chunks"
                step.chunks_found = len(chunks)
            except Exception as e:
                step.result = f"Retrieval failed: {str(e)}"
                step.chunks_found = 0

            reasoning_steps.append(step)

        # Remove duplicate chunks based on content
        unique_chunks = self._deduplicate_chunks(all_chunks)

        # Step 3: Synthesize answer
        step = ReasoningStep(
            step_number=len(reasoning_steps) + 1,
            action="synthesize",
            thought=f"Synthesizing answer from {len(unique_chunks)} unique chunks...",
        )

        answer = await self._generate_answer(query, unique_chunks, sub_queries)
        step.result = "Answer generated"
        reasoning_steps.append(step)

        # Step 4: Verify completeness
        step = ReasoningStep(
            step_number=len(reasoning_steps) + 1,
            action="verify",
            thought="Verifying if answer addresses all aspects of the query...",
        )

        is_complete, missing_aspects = await self._verify_completeness(
            query, answer, sub_queries
        )

        if is_complete:
            step.result = "Answer verified as complete"
        else:
            step.result = f"Answer incomplete. Missing: {', '.join(missing_aspects)}"

            # Try one more retrieval for missing aspects
            if missing_aspects and len(reasoning_steps) < self.max_iterations * 3:
                reasoning_steps.append(step)
                for aspect in missing_aspects[:2]:  # Limit to 2 additional retrievals
                    step = ReasoningStep(
                        step_number=len(reasoning_steps) + 1,
                        action="retrieve",
                        thought=f"Retrieving additional info for: {aspect}",
                        sub_query=aspect,
                    )
                    sub_queries.append(aspect)

                    try:
                        result = await self.retriever.retrieve(aspect, k=2, min_score=0.25)
                        new_chunks = result.chunks
                        unique_chunks.extend(new_chunks)
                        step.result = f"Found {len(new_chunks)} additional chunks"
                        step.chunks_found = len(new_chunks)
                    except Exception:
                        step.result = "No additional chunks found"
                        step.chunks_found = 0

                    reasoning_steps.append(step)

                # Regenerate answer with additional context
                step = ReasoningStep(
                    step_number=len(reasoning_steps) + 1,
                    action="synthesize",
                    thought="Regenerating answer with additional context...",
                )
                answer = await self._generate_answer(query, unique_chunks, sub_queries)
                step.result = "Enhanced answer generated"

        reasoning_steps.append(step)

        # Final step: Complete
        step = ReasoningStep(
            step_number=len(reasoning_steps) + 1,
            action="complete",
            thought="Agentic reasoning complete",
            result=f"Final answer ready with {len(unique_chunks)} sources",
        )
        reasoning_steps.append(step)

        # Format sources
        sources = [
            {
                "document_id": chunk.metadata.document_id,
                "filename": chunk.metadata.source_file,
                "chunk_index": chunk.metadata.chunk_index,
                "page_number": chunk.metadata.page_number,
                "score": chunk.score,
                "content": chunk.content[:500],
            }
            for chunk in unique_chunks
        ]

        total_time = (time.time() - start_time) * 1000

        return AgenticResponse(
            answer=answer,
            sources=sources,
            reasoning_steps=reasoning_steps,
            total_reasoning_time_ms=total_time,
            sub_queries_used=sub_queries,
            iterations=len([s for s in reasoning_steps if s.action == "retrieve"]),
            metadata={
                "total_chunks": len(unique_chunks),
                "reasoning_steps_count": len(reasoning_steps),
            },
        )

    async def _decompose_query(self, query: str) -> List[str]:
        """Decompose a complex query into sub-queries."""
        prompt = f"""Analyze this query and break it down into simpler sub-questions if needed.
If the query is already simple, return just the original query.
Return ONLY a JSON array of strings, nothing else.

Query: {query}

Rules:
- Maximum 4 sub-questions
- Each sub-question should be self-contained
- If query is simple (single topic, single ask), return ["{query}"]

Response (JSON array only):"""

        try:
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=300,
            )
            content = response.choices[0].message.content.strip()
            # Parse JSON array
            sub_queries = json.loads(content)
            if isinstance(sub_queries, list) and len(sub_queries) > 0:
                return sub_queries[:4]  # Limit to 4
        except Exception as e:
            self.logger.error(f"Query decomposition failed: {e}")

        return [query]  # Fallback to original query

    async def _generate_answer(
        self,
        query: str,
        chunks: List[RetrievedChunk],
        sub_queries: List[str],
    ) -> str:
        """Generate answer from chunks with awareness of sub-queries."""
        context = "\n\n".join(
            [
                f"[Source {i+1}: {chunk.metadata.source_file}]\n{chunk.content}"
                for i, chunk in enumerate(chunks[:10])  # Limit context
            ]
        )

        sub_queries_text = "\n".join([f"- {sq}" for sq in sub_queries])

        prompt = f"""Answer the user's question based on the provided context.
Make sure to address all aspects of the question.

Original Question: {query}

Sub-questions to address:
{sub_queries_text}

Context:
{context}

Instructions:
- Answer comprehensively, addressing each sub-question
- Cite sources using [Source N] format
- If information is missing, acknowledge it
- Be concise but complete

Answer:"""

        try:
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=1500,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            self.logger.error(f"Answer generation failed: {e}")
            return f"I encountered an error generating the answer: {str(e)}"

    async def _verify_completeness(
        self, query: str, answer: str, sub_queries: List[str]
    ) -> tuple[bool, List[str]]:
        """Verify if the answer addresses all aspects of the query."""
        prompt = f"""Check if the answer adequately addresses the original query and all sub-questions.

Original Query: {query}

Sub-questions that should be addressed:
{json.dumps(sub_queries)}

Answer provided:
{answer}

Respond with ONLY a JSON object:
{{"is_complete": true/false, "missing_aspects": ["aspect1", "aspect2"] or []}}

If complete, missing_aspects should be empty array.
If incomplete, list what's missing (max 2 items)."""

        try:
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=200,
            )
            content = response.choices[0].message.content.strip()
            result = json.loads(content)
            return result.get("is_complete", True), result.get("missing_aspects", [])
        except Exception as e:
            self.logger.error(f"Completeness verification failed: {e}")
            return True, []  # Assume complete on error

    def _deduplicate_chunks(self, chunks: List[RetrievedChunk]) -> List[RetrievedChunk]:
        """Remove duplicate chunks based on content similarity."""
        seen_content = set()
        unique = []
        for chunk in chunks:
            # Use first 100 chars as signature
            signature = chunk.content[:100].lower().strip()
            if signature not in seen_content:
                seen_content.add(signature)
                unique.append(chunk)
        return unique
