"""Retriever agent for fetching relevant context."""

import time
from typing import Optional

from pydantic import BaseModel, Field

from src.agents.planner import Plan
from src.core.logging import get_logger
from src.db.vector_store import FAISSVectorStore, SearchResult
from src.models.embeddings import EmbeddingModel
from src.services.document_processor import ChunkMetadata

logger = get_logger(__name__)


class RetrievedChunk(BaseModel):
    """A retrieved chunk with content, metadata, score, and rank."""

    content: str = Field(..., description="Chunk text content")
    metadata: ChunkMetadata = Field(..., description="Chunk metadata")
    score: float = Field(..., description="Similarity score (0-1, higher is better)")
    rank: int = Field(..., description="1-based ranking")


class RetrievalResult(BaseModel):
    """Result of a retrieval operation."""

    chunks: list[RetrievedChunk] = Field(..., description="List of retrieved chunks")
    query: str = Field(..., description="Original query")
    retrieval_time_ms: float = Field(..., description="Retrieval time in milliseconds")
    total_candidates: int = Field(..., description="Total number of candidates before filtering")


class RetrieverAgent:
    """
    Agent responsible for retrieving relevant documents from the vector store.
    
    Supports basic retrieval and reranking for improved relevance.
    """

    def __init__(
        self, vector_store: FAISSVectorStore, embedding_model: Optional[EmbeddingModel] = None
    ) -> None:
        """
        Initialize the retriever agent.

        Args:
            vector_store: Vector store instance for retrieval
            embedding_model: Optional embedding model (for reranking, currently not used)
        """
        self.vector_store = vector_store
        self.embedding_model = embedding_model
        logger.info("Retriever agent initialized")

    async def retrieve(
        self, query: str, k: int = 5, min_score: float = 0.3
    ) -> RetrievalResult:
        """
        Retrieve relevant chunks for a query.

        Args:
            query: The user's query
            k: Number of results to return
            min_score: Minimum similarity score threshold (0-1)

        Returns:
            RetrievalResult: Retrieval result with chunks, timing, and metadata
        """
        start_time = time.time()
        logger.info("Retrieving documents", query=query[:100], k=k, min_score=min_score)

        # Search vector store (handles encoding internally)
        search_results = self.vector_store.search(query, k=k * 2)  # Get more candidates for filtering
        total_candidates = len(search_results)

        # Convert to RetrievedChunk and filter by min_score
        retrieved_chunks = []
        filtered_count = 0

        for search_result in search_results:
            if search_result.score >= min_score:
                retrieved_chunk = RetrievedChunk(
                    content=search_result.chunk.content,
                    metadata=search_result.chunk.metadata,
                    score=search_result.score,
                    rank=len(retrieved_chunks) + 1,
                )
                retrieved_chunks.append(retrieved_chunk)
            else:
                filtered_count += 1

            # Stop if we have enough results
            if len(retrieved_chunks) >= k:
                break

        # Deduplicate results
        retrieved_chunks = self._deduplicate(retrieved_chunks)

        # Limit to k results
        retrieved_chunks = retrieved_chunks[:k]

        # Update ranks
        for i, chunk in enumerate(retrieved_chunks, start=1):
            chunk.rank = i

        elapsed_ms = (time.time() - start_time) * 1000

        if filtered_count > 0:
            logger.info(
                "Chunks filtered by score threshold",
                filtered=filtered_count,
                min_score=min_score,
            )

        logger.info(
            "Documents retrieved",
            query=query[:100],
            returned=len(retrieved_chunks),
            total_candidates=total_candidates,
            duration_ms=round(elapsed_ms, 2),
        )

        return RetrievalResult(
            chunks=retrieved_chunks,
            query=query,
            retrieval_time_ms=round(elapsed_ms, 2),
            total_candidates=total_candidates,
        )

    async def retrieve_with_rerank(
        self, query: str, k: int = 5, initial_k: int = 20
    ) -> RetrievalResult:
        """
        Retrieve chunks with reranking for improved relevance.

        Args:
            query: The user's query
            k: Number of final results to return
            initial_k: Number of candidates to retrieve before reranking

        Returns:
            RetrievalResult: Retrieval result with reranked chunks
        """
        start_time = time.time()
        logger.info(
            "Retrieving with reranking",
            query=query[:100],
            k=k,
            initial_k=initial_k,
        )

        # Retrieve initial candidates
        initial_results = self.vector_store.search(query, k=initial_k)
        total_candidates = len(initial_results)

        # Convert to RetrievedChunk
        initial_chunks = []
        for search_result in initial_results:
            retrieved_chunk = RetrievedChunk(
                content=search_result.chunk.content,
                metadata=search_result.chunk.metadata,
                score=search_result.score,
                rank=search_result.rank,
            )
            initial_chunks.append(retrieved_chunk)

        # Deduplicate before reranking
        initial_chunks = self._deduplicate(initial_chunks)

        # Rerank chunks
        reranked_chunks = self._simple_rerank(query, initial_chunks, k)

        # Update ranks
        for i, chunk in enumerate(reranked_chunks, start=1):
            chunk.rank = i

        elapsed_ms = (time.time() - start_time) * 1000

        logger.info(
            "Documents retrieved with reranking",
            query=query[:100],
            initial_candidates=total_candidates,
            returned=len(reranked_chunks),
            duration_ms=round(elapsed_ms, 2),
        )

        return RetrievalResult(
            chunks=reranked_chunks,
            query=query,
            retrieval_time_ms=round(elapsed_ms, 2),
            total_candidates=total_candidates,
        )

    def _simple_rerank(
        self, query: str, chunks: list[RetrievedChunk], k: int
    ) -> list[RetrievedChunk]:
        """
        Rerank chunks using keyword overlap and embedding scores.

        Args:
            query: The user's query
            chunks: List of chunks to rerank
            k: Number of top results to return

        Returns:
            list[RetrievedChunk]: Reranked chunks
        """
        if not chunks:
            return []

        # Extract query keywords (lowercase, remove stop words)
        query_lower = query.lower()
        stop_words = {
            "the",
            "a",
            "an",
            "and",
            "or",
            "but",
            "in",
            "on",
            "at",
            "to",
            "for",
            "of",
            "with",
            "by",
            "from",
            "is",
            "are",
            "was",
            "were",
            "be",
            "been",
            "being",
            "have",
            "has",
            "had",
            "do",
            "does",
            "did",
            "will",
            "would",
            "should",
            "could",
            "may",
            "might",
            "can",
            "what",
            "which",
            "who",
            "whom",
            "whose",
            "where",
            "when",
            "why",
            "how",
        }

        query_words = set(
            word
            for word in query_lower.split()
            if word not in stop_words and len(word) > 2
        )

        # Calculate combined scores for each chunk
        scored_chunks = []
        for chunk in chunks:
            # Get content words
            content_lower = chunk.content.lower()
            content_words = set(
                word
                for word in content_lower.split()
                if word not in stop_words and len(word) > 2
            )

            # Calculate keyword overlap score (Jaccard similarity)
            if query_words and content_words:
                intersection = len(query_words & content_words)
                union = len(query_words | content_words)
                keyword_score = intersection / union if union > 0 else 0.0
            else:
                keyword_score = 0.0

            # Combine embedding score (70%) with keyword score (30%)
            combined_score = (chunk.score * 0.7) + (keyword_score * 0.3)

            scored_chunks.append((combined_score, chunk))

        # Sort by combined score (descending)
        scored_chunks.sort(key=lambda x: x[0], reverse=True)

        # Return top k chunks with updated scores
        reranked = []
        for combined_score, chunk in scored_chunks[:k]:
            chunk.score = combined_score
            reranked.append(chunk)

        logger.debug(
            "Chunks reranked",
            query=query[:50],
            input_count=len(chunks),
            output_count=len(reranked),
        )

        return reranked

    def _deduplicate(
        self, chunks: list[RetrievedChunk], similarity_threshold: float = 0.9
    ) -> list[RetrievedChunk]:
        """
        Remove near-duplicate chunks, keeping the one with higher score.

        Args:
            chunks: List of chunks to deduplicate
            similarity_threshold: Similarity threshold for considering chunks duplicates (0-1)

        Returns:
            list[RetrievedChunk]: Deduplicated chunks
        """
        if not chunks:
            return []

        # Simple deduplication based on content similarity
        # For more sophisticated deduplication, we could use embeddings
        deduplicated = []
        seen_contents = set()

        for chunk in chunks:
            # Normalize content for comparison (lowercase, remove extra whitespace)
            normalized_content = " ".join(chunk.content.lower().split())

            # Check if we've seen similar content
            is_duplicate = False
            for seen_content in seen_contents:
                # Calculate simple similarity (word overlap)
                chunk_words = set(normalized_content.split())
                seen_words = set(seen_content.split())

                if chunk_words and seen_words:
                    intersection = len(chunk_words & seen_words)
                    union = len(chunk_words | seen_words)
                    similarity = intersection / union if union > 0 else 0.0

                    if similarity >= similarity_threshold:
                        # Check if current chunk has higher score
                        # Find the chunk with this content in deduplicated list
                        for existing_chunk in deduplicated:
                            existing_normalized = " ".join(
                                existing_chunk.content.lower().split()
                            )
                            if existing_normalized == seen_content:
                                if chunk.score > existing_chunk.score:
                                    # Replace with higher-scoring chunk
                                    deduplicated.remove(existing_chunk)
                                    deduplicated.append(chunk)
                                    seen_contents.remove(seen_content)
                                    seen_contents.add(normalized_content)
                                is_duplicate = True
                                break
                        if is_duplicate:
                            break

            if not is_duplicate:
                deduplicated.append(chunk)
                seen_contents.add(normalized_content)

        removed_count = len(chunks) - len(deduplicated)
        if removed_count > 0:
            logger.debug(
                "Chunks deduplicated",
                original_count=len(chunks),
                deduplicated_count=len(deduplicated),
                removed=removed_count,
            )

        return deduplicated

