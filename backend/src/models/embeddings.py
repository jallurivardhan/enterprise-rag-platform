"""OpenAI Embedding model for generating vector representations."""

import hashlib
import time
from collections import OrderedDict
from typing import Optional, List

from langchain_openai import OpenAIEmbeddings

from src.core.config import settings
from src.core.logging import get_logger

logger = get_logger(__name__)


class EmbeddingModel:
    """
    Model for generating embeddings using OpenAI API.
    
    Implements singleton pattern to avoid recreating the client.
    Includes in-memory caching for efficiency.
    """

    _instance: Optional["EmbeddingModel"] = None

    def __new__(cls, model_name: str = "text-embedding-3-small") -> "EmbeddingModel":
        """Create or return existing singleton instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, model_name: str = "text-embedding-3-small") -> None:
        """Initialize the embedding model."""
        if hasattr(self, '_initialized') and self._initialized:
            return
            
        self.model_name = model_name
        self._dimension = 1536  # text-embedding-3-small dimension
        self._cache: OrderedDict[str, List[float]] = OrderedDict()
        self._max_cache_size = 10000
        
        # Initialize OpenAI embeddings
        self._embeddings = OpenAIEmbeddings(
            openai_api_key=settings.OPENAI_API_KEY,
            model=model_name,
        )
        
        self._initialized = True
        logger.info("EmbeddingModel initialized with OpenAI", model=model_name)

    def _get_cache_key(self, text: str) -> str:
        """Generate a cache key for the given text."""
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def encode(self, text: str) -> List[float]:
        """
        Encode a single text into an embedding vector.

        Args:
            text: Text to encode

        Returns:
            List[float]: Embedding vector
        """
        if not text or not text.strip():
            logger.warning("Empty text provided for encoding")
            return [0.0] * self._dimension

        # Check cache
        cache_key = self._get_cache_key(text)
        if cache_key in self._cache:
            logger.debug("Cache hit for text encoding")
            return self._cache[cache_key]

        start_time = time.time()
        try:
            # Use OpenAI to encode
            embedding = self._embeddings.embed_query(text)
            
            # Cache the result
            self._add_to_cache(cache_key, embedding)

            elapsed = time.time() - start_time
            logger.debug(
                "Text encoded",
                text_length=len(text),
                duration_ms=round(elapsed * 1000, 3),
            )

            return embedding

        except Exception as e:
            logger.error("Failed to encode text", error=str(e))
            raise RuntimeError(f"Failed to encode text: {e}") from e

    def encode_batch(
        self, texts: List[str], batch_size: int = 32, show_progress: bool = True
    ) -> List[List[float]]:
        """
        Encode multiple texts into embedding vectors.

        Args:
            texts: List of texts to encode
            batch_size: Batch size (not used with OpenAI, but kept for compatibility)
            show_progress: Whether to show progress (not used)

        Returns:
            List[List[float]]: List of embedding vectors
        """
        if not texts:
            return []

        # Filter out empty texts and track indices
        results = []
        texts_to_encode = []
        text_indices = []
        
        for i, text in enumerate(texts):
            if text and text.strip():
                cache_key = self._get_cache_key(text)
                if cache_key in self._cache:
                    results.append((i, self._cache[cache_key]))
                else:
                    texts_to_encode.append(text)
                    text_indices.append(i)
            else:
                results.append((i, [0.0] * self._dimension))

        start_time = time.time()
        
        if texts_to_encode:
            try:
                # Batch encode with OpenAI
                embeddings = self._embeddings.embed_documents(texts_to_encode)
                
                # Cache and store results
                for idx, (text, embedding) in enumerate(zip(texts_to_encode, embeddings)):
                    cache_key = self._get_cache_key(text)
                    self._add_to_cache(cache_key, embedding)
                    results.append((text_indices[idx], embedding))
                    
            except Exception as e:
                logger.error("Failed to encode batch", error=str(e))
                raise RuntimeError(f"Failed to encode batch: {e}") from e

        # Sort by original index and extract embeddings
        results.sort(key=lambda x: x[0])
        final_results = [emb for _, emb in results]

        elapsed = time.time() - start_time
        logger.info(
            "Batch encoded",
            total=len(texts),
            encoded=len(texts_to_encode),
            duration_ms=round(elapsed * 1000, 2),
        )

        return final_results

    def _add_to_cache(self, cache_key: str, embedding: List[float]) -> None:
        """Add embedding to cache with size limit management."""
        if len(self._cache) >= self._max_cache_size:
            self._cache.popitem(last=False)
        self._cache[cache_key] = embedding

    def get_embedding_dimension(self) -> int:
        """Get the dimension of the embedding vectors."""
        return self._dimension

    def clear_cache(self) -> None:
        """Clear the embedding cache."""
        cache_size = len(self._cache)
        self._cache.clear()
        logger.info("Embedding cache cleared", entries_removed=cache_size)

    def get_cache_stats(self) -> dict:
        """Get cache statistics."""
        return {
            "cache_size": len(self._cache),
            "max_cache_size": self._max_cache_size,
        }