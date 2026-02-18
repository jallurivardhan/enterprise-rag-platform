"""FAISS vector store implementation."""

import json
import threading
import time
from pathlib import Path
from typing import Optional

import faiss
import numpy as np
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
    FAISS-based vector store for embeddings with thread-safe operations.
    
    Uses IndexFlatIP (Inner Product) for cosine similarity with normalized vectors.
    """

    def __init__(self, dimension: int = 768, index_path: Optional[str] = None) -> None:
        """
        Initialize the FAISS vector store.

        Args:
            dimension: Dimension of embedding vectors (default: 768 for all-mpnet-base-v2)
            index_path: Optional path to load existing index from disk
        """
        self.dimension = dimension
        self.index: Optional[faiss.Index] = None
        self.chunks: dict[str, DocumentChunk] = {}  # chunk_id -> DocumentChunk mapping
        self.chunk_ids: list[str] = []  # Ordered list of chunk IDs (matches FAISS index order)
        self._lock = threading.Lock()  # Thread safety lock
        self.embedding_model = EmbeddingModel()

        # Initialize or load index
        if index_path and Path(f"{index_path}.index").exists():
            logger.info("Loading existing index", path=index_path)
            self.load(index_path)
        else:
            self._initialize_index(clear_chunks=True)
            if index_path:
                logger.info("Index path provided but file doesn't exist, creating new index", path=index_path)

        logger.info(
            "FAISSVectorStore initialized",
            dimension=self.dimension,
            total_chunks=self.total_chunks,
        )

    def _initialize_index(self, clear_chunks: bool = False) -> None:
        """
        Initialize a new FAISS index.
        
        Args:
            clear_chunks: If True, clear chunks and chunk_ids. Default False.
        """
        # Use IndexFlatIP for inner product (cosine similarity with normalized vectors)
        self.index = faiss.IndexFlatIP(self.dimension)
        if clear_chunks:
            self.chunks = {}
            self.chunk_ids = []
        logger.debug("FAISS index initialized", dimension=self.dimension, index_type="IndexFlatIP", clear_chunks=clear_chunks)

    @property
    def total_chunks(self) -> int:
        """
        Get the total number of chunks in the index.

        Returns:
            int: Number of chunks
        """
        if self.index is None:
            return 0
        return self.index.ntotal

    def add_documents(self, chunks: list[DocumentChunk]) -> None:
        """
        Add document chunks to the vector store.

        Args:
            chunks: List of DocumentChunk objects to add

        Raises:
            ValueError: If chunks list is empty or invalid
        """
        if not chunks:
            logger.warning("Empty chunks list provided")
            return

        start_time = time.time()

        with self._lock:  # Thread-safe write operation
            try:
                # Ensure index is initialized
                if self.index is None:
                    self._initialize_index()

                # Check for duplicates
                new_chunks = []
                duplicate_count = 0
                for chunk in chunks:
                    if chunk.id in self.chunks:
                        duplicate_count += 1
                        logger.debug("Skipping duplicate chunk", chunk_id=chunk.id)
                        continue
                    new_chunks.append(chunk)

                if duplicate_count > 0:
                    logger.warning("Skipped duplicate chunks", count=duplicate_count)

                if not new_chunks:
                    logger.warning("No new chunks to add after filtering duplicates")
                    return

                # Generate embeddings for chunks that don't have them
                chunks_to_embed = [chunk for chunk in new_chunks if chunk.embedding is None]
                if chunks_to_embed:
                    logger.debug("Generating embeddings", count=len(chunks_to_embed))
                    texts = [chunk.content for chunk in chunks_to_embed]
                    embeddings = self.embedding_model.encode_batch(texts, show_progress=False)

                    # Assign embeddings to chunks
                    for chunk, embedding in zip(chunks_to_embed, embeddings):
                        chunk.embedding = embedding

                # Prepare vectors for FAISS (must be float32)
                vectors = np.array(
                    [chunk.embedding for chunk in new_chunks],
                    dtype=np.float32,
                )

                # Validate vector dimensions
                if vectors.shape[1] != self.dimension:
                    raise ValueError(
                        f"Vector dimension mismatch: expected {self.dimension}, got {vectors.shape[1]}"
                    )

                # Add vectors to FAISS index
                self.index.add(vectors)

                # Store chunks in metadata dict and maintain order
                for chunk in new_chunks:
                    self.chunks[chunk.id] = chunk
                    self.chunk_ids.append(chunk.id)

                elapsed = time.time() - start_time
                logger.info(
                    "Documents added to vector store",
                    chunks_added=len(new_chunks),
                    duplicates_skipped=duplicate_count,
                    total_chunks=self.total_chunks,
                    duration_ms=round(elapsed * 1000, 2),
                )

            except Exception as e:
                logger.error(
                    "Failed to add documents",
                    error=str(e),
                    error_type=type(e).__name__,
                    chunks_count=len(chunks),
                )
                raise

    def search(self, query: str, k: int = 5) -> list[SearchResult]:
        """
        Search for similar chunks using a text query.

        Args:
            query: Text query to search for
            k: Number of results to return

        Returns:
            list[SearchResult]: List of search results with chunks, scores, and ranks

        Raises:
            ValueError: If query is empty or index is empty
        """
        if not query or not query.strip():
            logger.warning("Empty query provided")
            return []

        if self.index is None or self.total_chunks == 0:
            logger.warning("Index is empty, returning no results")
            return []

        start_time = time.time()

        try:
            # Encode query
            query_embedding = self.embedding_model.encode(query)
            query_vector = np.array([query_embedding], dtype=np.float32)

            # Validate query vector dimension
            if query_vector.shape[1] != self.dimension:
                raise ValueError(
                    f"Query vector dimension mismatch: expected {self.dimension}, got {query_vector.shape[1]}"
                )

            # Search FAISS index (returns inner product scores)
            # Since vectors are normalized, inner product = cosine similarity
            k = min(k, self.total_chunks)  # Don't request more than available
            scores, indices = self.index.search(query_vector, k)

            # Build results
            results = []
            for rank, (score, idx) in enumerate(zip(scores[0], indices[0]), start=1):
                # FAISS returns -1 for invalid indices when k > available vectors
                if idx == -1 or idx >= len(self.chunk_ids):
                    continue

                # Get chunk by index (FAISS indices correspond to order in chunk_ids list)
                chunk_id = self.chunk_ids[idx]
                chunk = self.chunks.get(chunk_id)

                if chunk is None:
                    logger.warning("Chunk not found for index", chunk_id=chunk_id, index=idx)
                    continue

                # Normalize score to 0-1 range (inner product of normalized vectors is -1 to 1)
                # For cosine similarity, we want 0-1 range
                normalized_score = (score + 1) / 2

                result = SearchResult(
                    chunk=chunk,
                    score=float(normalized_score),
                    rank=rank,
                )
                results.append(result)

            elapsed = time.time() - start_time
            logger.info(
                "Search completed",
                query_length=len(query),
                k_requested=k,
                results_returned=len(results),
                duration_ms=round(elapsed * 1000, 3),
            )

            return results

        except Exception as e:
            logger.error(
                "Search failed",
                error=str(e),
                error_type=type(e).__name__,
                query_length=len(query),
            )
            raise

    def get_chunks_by_document_id(self, document_id: str) -> list[DocumentChunk]:
        """
        Get all chunks for a specific document.

        Args:
            document_id: Document ID to get chunks for

        Returns:
            list[DocumentChunk]: List of chunks belonging to the document
        """
        chunks = []
        for chunk in self.chunks.values():
            if chunk.metadata.document_id == document_id:
                chunks.append(chunk)
        # Sort by chunk_index
        chunks.sort(key=lambda c: c.metadata.chunk_index)
        return chunks

    def delete_document(self, document_id: str) -> int:
        """
        Delete all chunks belonging to a document.

        Since FAISS doesn't support deletion, this rebuilds the index.

        Args:
            document_id: Document ID to delete

        Returns:
            int: Number of chunks deleted

        Raises:
            ValueError: If document_id is empty
        """
        if not document_id:
            raise ValueError("Document ID cannot be empty")

        start_time = time.time()

        with self._lock:  # Thread-safe write operation
            try:
                # Find chunks belonging to this document
                chunks_to_delete = [
                    chunk_id
                    for chunk_id, chunk in self.chunks.items()
                    if chunk.metadata.document_id == document_id
                ]

                if not chunks_to_delete:
                    logger.info("No chunks found for document", document_id=document_id)
                    return 0

                # Remove chunks from metadata and ordered list
                for chunk_id in chunks_to_delete:
                    del self.chunks[chunk_id]
                    if chunk_id in self.chunk_ids:
                        self.chunk_ids.remove(chunk_id)

                # Rebuild index with remaining chunks (in order)
                remaining_chunks = [self.chunks[chunk_id] for chunk_id in self.chunk_ids]
                if remaining_chunks:
                    # Prepare vectors
                    vectors = np.array(
                        [chunk.embedding for chunk in remaining_chunks],
                        dtype=np.float32,
                    )

                    # Reinitialize index
                    self._initialize_index()
                    self.index.add(vectors)
                else:
                    # No chunks left, just reinitialize empty index
                    self._initialize_index()

                elapsed = time.time() - start_time
                logger.info(
                    "Document deleted",
                    document_id=document_id,
                    chunks_deleted=len(chunks_to_delete),
                    remaining_chunks=self.total_chunks,
                    duration_ms=round(elapsed * 1000, 2),
                )

                return len(chunks_to_delete)

            except Exception as e:
                logger.error(
                    "Failed to delete document",
                    document_id=document_id,
                    error=str(e),
                    error_type=type(e).__name__,
                )
                raise

    def save(self, path: str) -> None:
        """
        Save the FAISS index and metadata to disk.

        Args:
            path: Path to save the index (without extension)

        Raises:
            IOError: If save operation fails
        """
        if self.index is None or self.total_chunks == 0:
            logger.warning("No index to save or index is empty")
            return

        start_time = time.time()

        try:
            index_path = Path(f"{path}.index")
            metadata_path = Path(f"{path}.metadata.json")

            # Create parent directory if it doesn't exist
            index_path.parent.mkdir(parents=True, exist_ok=True)

            # Save FAISS index
            faiss.write_index(self.index, str(index_path))
            logger.debug("FAISS index saved", path=str(index_path))

            # Save metadata (chunks) - preserve order
            metadata_data = {
                "chunks": {chunk_id: self.chunks[chunk_id].model_dump() for chunk_id in self.chunk_ids},
                "chunk_ids": self.chunk_ids,  # Save order explicitly
                "dimension": self.dimension,
                "total_chunks": self.total_chunks,
            }

            with open(metadata_path, "w", encoding="utf-8") as f:
                json.dump(metadata_data, f, indent=2, ensure_ascii=False)

            elapsed = time.time() - start_time
            logger.info(
                "Vector store saved",
                path=path,
                total_chunks=self.total_chunks,
                duration_ms=round(elapsed * 1000, 2),
            )

        except Exception as e:
            logger.error(
                "Failed to save vector store",
                path=path,
                error=str(e),
                error_type=type(e).__name__,
            )
            raise IOError(f"Failed to save vector store to {path}: {e}") from e

    def load(self, path: str) -> None:
        """
        Load the FAISS index and metadata from disk.

        Args:
            path: Path to load the index from (without extension)

        Raises:
            FileNotFoundError: If index files don't exist
            IOError: If load operation fails
        """
        start_time = time.time()

        try:
            index_path = Path(f"{path}.index")
            metadata_path = Path(f"{path}.metadata.json")

            # Check if files exist
            if not index_path.exists():
                raise FileNotFoundError(f"Index file not found: {index_path}")

            if not metadata_path.exists():
                raise FileNotFoundError(f"Metadata file not found: {metadata_path}")

            # Load FAISS index
            self.index = faiss.read_index(str(index_path))
            self.dimension = self.index.d
            logger.debug("FAISS index loaded", path=str(index_path), dimension=self.dimension)

            # Load metadata
            with open(metadata_path, "r", encoding="utf-8") as f:
                metadata_data = json.load(f)

            # Restore chunks and maintain order
            self.chunks = {}
            # Try to restore order from chunk_ids list, fallback to dict order
            chunk_ids_ordered = metadata_data.get("chunk_ids")
            if chunk_ids_ordered:
                self.chunk_ids = chunk_ids_ordered
                for chunk_id in chunk_ids_ordered:
                    if chunk_id in metadata_data.get("chunks", {}):
                        chunk_data = metadata_data["chunks"][chunk_id]
                        chunk = DocumentChunk(**chunk_data)
                        self.chunks[chunk_id] = chunk
            else:
                # Fallback: restore in dict order (for backward compatibility)
                self.chunk_ids = []
                for chunk_id, chunk_data in metadata_data.get("chunks", {}).items():
                    chunk = DocumentChunk(**chunk_data)
                    self.chunks[chunk_id] = chunk
                    self.chunk_ids.append(chunk_id)

            # Validate dimension
            if metadata_data.get("dimension") != self.dimension:
                logger.warning(
                    "Dimension mismatch",
                    stored=metadata_data.get("dimension"),
                    index=self.dimension,
                )

            elapsed = time.time() - start_time
            logger.info(
                "Vector store loaded",
                path=path,
                total_chunks=self.total_chunks,
                dimension=self.dimension,
                duration_ms=round(elapsed * 1000, 2),
            )

        except FileNotFoundError:
            raise
        except Exception as e:
            logger.error(
                "Failed to load vector store",
                path=path,
                error=str(e),
                error_type=type(e).__name__,
            )
            raise IOError(f"Failed to load vector store from {path}: {e}") from e
