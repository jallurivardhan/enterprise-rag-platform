"""Retriever agent for fetching relevant context."""

import time
from typing import Optional, List

from pydantic import BaseModel, Field

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
    chunks: List[RetrievedChunk] = Field(..., description="List of retrieved chunks")
    query: str = Field(..., description="Original query")
    retrieval_time_ms: float = Field(..., description="Retrieval time in milliseconds")
    total_candidates: int = Field(..., description="Total number of candidates before filtering")


class RetrieverAgent:
    """Agent responsible for retrieving relevant documents from the vector store."""

    def __init__(
        self, vector_store: FAISSVectorStore, embedding_model: Optional[EmbeddingModel] = None
    ) -> None:
        """
        Initialize the retriever agent.

        Args:
            vector_store: Vector store instance for retrieval
            embedding_model: Optional embedding model (kept for compatibility)
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
            RetrievalResult: Retrieval result with chunks
        """
        start_time = time.time()
        logger.info("Retrieving documents", query=query[:100], k=k, min_score=min_score)

        # Search vector store
        search_results = self.vector_store.search(query, k=k * 2)
        total_candidates = len(search_results)

        # Convert and filter by min_score
        retrieved_chunks = []
        for search_result in search_results:
            if search_result.score >= min_score:
                retrieved_chunk = RetrievedChunk(
                    content=search_result.chunk.content,
                    metadata=search_result.chunk.metadata,
                    score=search_result.score,
                    rank=len(retrieved_chunks) + 1,
                )
                retrieved_chunks.append(retrieved_chunk)

            if len(retrieved_chunks) >= k:
                break

        # Deduplicate
        retrieved_chunks = self._deduplicate(retrieved_chunks)[:k]

        # Update ranks
        for i, chunk in enumerate(retrieved_chunks, start=1):
            chunk.rank = i

        elapsed_ms = (time.time() - start_time) * 1000

        logger.info(
            "Documents retrieved",
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
        """Retrieve chunks with simple reranking."""
        start_time = time.time()
        
        # Get initial candidates
        search_results = self.vector_store.search(query, k=initial_k)
        total_candidates = len(search_results)

        # Convert to RetrievedChunk
        initial_chunks = [
            RetrievedChunk(
                content=sr.chunk.content,
                metadata=sr.chunk.metadata,
                score=sr.score,
                rank=sr.rank,
            )
            for sr in search_results
        ]

        # Deduplicate and rerank
        initial_chunks = self._deduplicate(initial_chunks)
        reranked_chunks = self._simple_rerank(query, initial_chunks, k)

        # Update ranks
        for i, chunk in enumerate(reranked_chunks, start=1):
            chunk.rank = i

        elapsed_ms = (time.time() - start_time) * 1000

        return RetrievalResult(
            chunks=reranked_chunks,
            query=query,
            retrieval_time_ms=round(elapsed_ms, 2),
            total_candidates=total_candidates,
        )

    def _simple_rerank(self, query: str, chunks: List[RetrievedChunk], k: int) -> List[RetrievedChunk]:
        """Rerank chunks using keyword overlap and embedding scores."""
        if not chunks:
            return []

        query_lower = query.lower()
        stop_words = {"the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with", "by", "from", "is", "are", "was", "were", "be", "been", "being", "have", "has", "had", "do", "does", "did", "will", "would", "should", "could", "may", "might", "can", "what", "which", "who", "whom", "whose", "where", "when", "why", "how"}
        query_words = set(word for word in query_lower.split() if word not in stop_words and len(word) > 2)

        scored_chunks = []
        for chunk in chunks:
            content_lower = chunk.content.lower()
            content_words = set(word for word in content_lower.split() if word not in stop_words and len(word) > 2)

            if query_words and content_words:
                intersection = len(query_words & content_words)
                union = len(query_words | content_words)
                keyword_score = intersection / union if union > 0 else 0.0
            else:
                keyword_score = 0.0

            combined_score = (chunk.score * 0.7) + (keyword_score * 0.3)
            scored_chunks.append((combined_score, chunk))

        scored_chunks.sort(key=lambda x: x[0], reverse=True)

        reranked = []
        for combined_score, chunk in scored_chunks[:k]:
            chunk.score = combined_score
            reranked.append(chunk)

        return reranked

    def _deduplicate(self, chunks: List[RetrievedChunk], similarity_threshold: float = 0.9) -> List[RetrievedChunk]:
        """Remove near-duplicate chunks."""
        if not chunks:
            return []

        deduplicated = []
        seen_contents = set()

        for chunk in chunks:
            normalized = " ".join(chunk.content.lower().split())
            
            is_duplicate = False
            for seen in seen_contents:
                chunk_words = set(normalized.split())
                seen_words = set(seen.split())
                if chunk_words and seen_words:
                    intersection = len(chunk_words & seen_words)
                    union = len(chunk_words | seen_words)
                    similarity = intersection / union if union > 0 else 0.0
                    if similarity >= similarity_threshold:
                        is_duplicate = True
                        break

            if not is_duplicate:
                deduplicated.append(chunk)
                seen_contents.add(normalized)

        return deduplicated