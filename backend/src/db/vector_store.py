"""ChromaDB vector store implementation - lightweight alternative to FAISS."""

import json
import time
from pathlib import Path
from typing import Optional, List
import uuid

from pydantic import BaseModel, Field

from src.core.config import settings
from src.core.logging import get_logger
from src.models.embeddings import EmbeddingModel
from src.services.document_processor import DocumentChunk

logger = get_logger(__name__)


class SearchResult(BaseModel):
    """Search result with chunk, score, and rank."""
    chunk: DocumentChunk = Field(..., description="Retrieved document chunk")
    score: float = Field(..., description="Similarity score (0-1, higher is better)")
    rank: int = Field(..., description="1-based ranking of the result")


class FAISSVectorStore:
    """
    In-memory vector store using simple cosine similarity.
    Lightweight alternative that works within 512MB RAM.
    
    Note: Class name kept as FAISSVectorStore for compatibility.
    """

    def __init__(self, dimension: int = 1536, index_path: Optional[str] = None) -> None:
        """
        Initialize the vector store.

        Args:
            dimension: Dimension of embedding vectors (1536 for OpenAI text-embedding-3-small)
            index_path: Optional path to load existing index from disk
        """
        self.dimension = dimension
        self.chunks: dict[str, DocumentChunk] = {}
        self.chunk_ids: List[str] = []
        self.embeddings: dict[str, List[float]] = {}
        self.embedding_model = EmbeddingModel()

        # Load existing index if path provided
        if index_path and Path(f"{index_path}.metadata.json").exists():
            logger.info("Loading existing index", path=index_path)
            self.load(index_path)
        else:
            if index_path:
                logger.info("Index path provided but file doesn't exist, creating new index", path=index_path)

        logger.info(
            "VectorStore initialized",
            dimension=self.dimension,
            total_chunks=self.total_chunks,
        )

    @property
    def total_chunks(self) -> int:
        """Get the total number of chunks in the index."""
        return len(self.chunks)

    def add_documents(self, chunks: List[DocumentChunk]) -> None:
        """
        Add document chunks to the vector store.

        Args:
            chunks: List of DocumentChunk objects to add
        """
        if not chunks:
            logger.warning("Empty chunks list provided")
            return

        start_time = time.time()

        # Filter duplicates
        new_chunks = []
        for chunk in chunks:
            if chunk.id not in self.chunks:
                new_chunks.append(chunk)

        if not new_chunks:
            logger.warning("No new chunks to add after filtering duplicates")
            return

        # Generate embeddings for chunks that don't have them
        chunks_to_embed = [c for c in new_chunks if c.embedding is None]
        if chunks_to_embed:
            texts = [c.content for c in chunks_to_embed]
            embeddings = self.embedding_model.encode_batch(texts, show_progress=False)
            for chunk, embedding in zip(chunks_to_embed, embeddings):
                chunk.embedding = embedding

        # Store chunks and embeddings
        for chunk in new_chunks:
            self.chunks[chunk.id] = chunk
            self.chunk_ids.append(chunk.id)
            self.embeddings[chunk.id] = chunk.embedding

        elapsed = time.time() - start_time
        logger.info(
            "Documents added to vector store",
            chunks_added=len(new_chunks),
            total_chunks=self.total_chunks,
            duration_ms=round(elapsed * 1000, 2),
        )

    def search(self, query: str, k: int = 5) -> List[SearchResult]:
        """
        Search for similar chunks using a text query.

        Args:
            query: Text query to search for
            k: Number of results to return

        Returns:
            List[SearchResult]: List of search results
        """
        if not query or not query.strip():
            return []

        if self.total_chunks == 0:
            logger.warning("Index is empty, returning no results")
            return []

        start_time = time.time()

        # Encode query
        query_embedding = self.embedding_model.encode(query)

        # Calculate cosine similarity with all chunks
        scores = []
        for chunk_id in self.chunk_ids:
            chunk_embedding = self.embeddings.get(chunk_id)
            if chunk_embedding:
                score = self._cosine_similarity(query_embedding, chunk_embedding)
                scores.append((chunk_id, score))

        # Sort by score (descending)
        scores.sort(key=lambda x: x[1], reverse=True)

        # Build results
        results = []
        for rank, (chunk_id, score) in enumerate(scores[:k], start=1):
            chunk = self.chunks.get(chunk_id)
            if chunk:
                # Normalize score to 0-1 range
                normalized_score = (score + 1) / 2
                results.append(SearchResult(
                    chunk=chunk,
                    score=float(normalized_score),
                    rank=rank,
                ))

        elapsed = time.time() - start_time
        logger.info(
            "Search completed",
            query_length=len(query),
            results_returned=len(results),
            duration_ms=round(elapsed * 1000, 3),
        )

        return results

    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        import math
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = math.sqrt(sum(a * a for a in vec1))
        norm2 = math.sqrt(sum(b * b for b in vec2))
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return dot_product / (norm1 * norm2)

    def get_chunks_by_document_id(self, document_id: str) -> List[DocumentChunk]:
        """Get all chunks for a specific document."""
        chunks = [c for c in self.chunks.values() if c.metadata.document_id == document_id]
        chunks.sort(key=lambda c: c.metadata.chunk_index)
        return chunks

    def delete_document(self, document_id: str) -> int:
        """
        Delete all chunks belonging to a document.

        Args:
            document_id: Document ID to delete

        Returns:
            int: Number of chunks deleted
        """
        if not document_id:
            raise ValueError("Document ID cannot be empty")

        chunks_to_delete = [
            cid for cid, chunk in self.chunks.items()
            if chunk.metadata.document_id == document_id
        ]

        if not chunks_to_delete:
            return 0

        for chunk_id in chunks_to_delete:
            del self.chunks[chunk_id]
            del self.embeddings[chunk_id]
            self.chunk_ids.remove(chunk_id)

        logger.info(
            "Document deleted",
            document_id=document_id,
            chunks_deleted=len(chunks_to_delete),
        )

        return len(chunks_to_delete)

    def save(self, path: str) -> None:
        """Save the vector store to disk."""
        if self.total_chunks == 0:
            logger.warning("No chunks to save")
            return

        start_time = time.time()
        metadata_path = Path(f"{path}.metadata.json")
        metadata_path.parent.mkdir(parents=True, exist_ok=True)

        # Save metadata
        data = {
            "chunks": {cid: self.chunks[cid].model_dump() for cid in self.chunk_ids},
            "chunk_ids": self.chunk_ids,
            "embeddings": self.embeddings,
            "dimension": self.dimension,
        }

        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        elapsed = time.time() - start_time
        logger.info(
            "Vector store saved",
            path=path,
            total_chunks=self.total_chunks,
            duration_ms=round(elapsed * 1000, 2),
        )

    def load(self, path: str) -> None:
        """Load the vector store from disk."""
        start_time = time.time()
        metadata_path = Path(f"{path}.metadata.json")

        if not metadata_path.exists():
            raise FileNotFoundError(f"Metadata file not found: {metadata_path}")

        with open(metadata_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.chunk_ids = data.get("chunk_ids", [])
        self.embeddings = data.get("embeddings", {})
        self.dimension = data.get("dimension", 1536)

        self.chunks = {}
        for chunk_id in self.chunk_ids:
            if chunk_id in data.get("chunks", {}):
                chunk_data = data["chunks"][chunk_id]
                self.chunks[chunk_id] = DocumentChunk(**chunk_data)

        elapsed = time.time() - start_time
        logger.info(
            "Vector store loaded",
            path=path,
            total_chunks=self.total_chunks,
            duration_ms=round(elapsed * 1000, 2),
        )