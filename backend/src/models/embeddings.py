"""Embedding model for generating vector representations."""

import hashlib
import time
from collections import OrderedDict
from typing import Optional

import numpy as np
from sentence_transformers import SentenceTransformer

from src.core.config import settings
from src.core.logging import get_logger

logger = get_logger(__name__)


class EmbeddingModel:
    """
    Model for generating embeddings using sentence transformers.
    
    Implements singleton pattern to avoid reloading the model multiple times.
    Includes in-memory caching and L2 normalization for cosine similarity.
    """

    _instance: Optional["EmbeddingModel"] = None
    _model_cache: dict[str, SentenceTransformer] = {}

    def __new__(cls, model_name: str = "all-mpnet-base-v2") -> "EmbeddingModel":
        """
        Create or return existing singleton instance.

        Args:
            model_name: Name of the model to use

        Returns:
            EmbeddingModel: Singleton instance
        """
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, model_name: str = "all-mpnet-base-v2") -> None:
        """
        Initialize the embedding model (lazy loading).

        Args:
            model_name: Name of the model to use (defaults to "all-mpnet-base-v2")
        """
        self.model_name = model_name
        self._model: Optional[SentenceTransformer] = None
        self._dimension: Optional[int] = None
        self._cache: OrderedDict[str, list[float]] = OrderedDict()
        self._max_cache_size = 10000
        logger.debug("EmbeddingModel initialized", model=model_name)

    def _load_model(self) -> None:
        """
        Lazy load the sentence transformer model.

        Raises:
            RuntimeError: If model loading fails
        """
        if self._model is not None:
            return

        # Check if model is already loaded in cache
        if self.model_name in self._model_cache:
            logger.info("Using cached model instance", model=self.model_name)
            self._model = self._model_cache[self.model_name]
            self._dimension = self._model.get_sentence_embedding_dimension()
            return

        start_time = time.time()
        try:
            logger.info("Loading embedding model", model=self.model_name)
            self._model = SentenceTransformer(self.model_name)
            self._dimension = self._model.get_sentence_embedding_dimension()
            
            # Cache the model instance
            self._model_cache[self.model_name] = self._model
            
            elapsed = time.time() - start_time
            logger.info(
                "Embedding model loaded",
                model=self.model_name,
                dimension=self._dimension,
                duration_ms=round(elapsed * 1000, 2),
            )
        except Exception as e:
            logger.error("Failed to load embedding model", model=self.model_name, error=str(e))
            raise RuntimeError(f"Failed to load embedding model '{self.model_name}': {e}") from e

    def _get_cache_key(self, text: str) -> str:
        """
        Generate a cache key for the given text.

        Args:
            text: Text to generate cache key for

        Returns:
            str: SHA256 hash of the text
        """
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def _normalize_embedding(self, embedding: np.ndarray) -> np.ndarray:
        """
        Normalize embedding vector using L2 normalization for cosine similarity.

        Args:
            embedding: Embedding vector to normalize

        Returns:
            np.ndarray: Normalized embedding vector
        """
        norm = np.linalg.norm(embedding)
        if norm == 0:
            return embedding
        return embedding / norm

    def _normalize_embeddings(self, embeddings: np.ndarray) -> np.ndarray:
        """
        Normalize multiple embedding vectors using L2 normalization.

        Args:
            embeddings: Array of embedding vectors to normalize

        Returns:
            np.ndarray: Normalized embedding vectors
        """
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        norms[norms == 0] = 1  # Avoid division by zero
        return embeddings / norms

    def encode(self, text: str) -> list[float]:
        """
        Encode a single text into an embedding vector.

        Args:
            text: Text to encode

        Returns:
            list[float]: Normalized embedding vector as a list

        Raises:
            RuntimeError: If encoding fails
        """
        if not text or not text.strip():
            logger.warning("Empty text provided for encoding")
            # Return zero vector of appropriate dimension
            self._load_model()
            return [0.0] * self._dimension

        # Check cache
        cache_key = self._get_cache_key(text)
        if cache_key in self._cache:
            logger.debug("Cache hit for text encoding", cache_key=cache_key[:8])
            return self._cache[cache_key]

        # Load model if needed
        self._load_model()

        start_time = time.time()
        try:
            # Encode text
            embedding = self._model.encode(
                text,
                convert_to_numpy=True,
                normalize_embeddings=False,  # We'll normalize ourselves
            )

            # Normalize for cosine similarity
            embedding = self._normalize_embedding(embedding)

            # Convert to list
            result = embedding.tolist()

            # Cache the result
            self._add_to_cache(cache_key, result)

            elapsed = time.time() - start_time
            logger.debug(
                "Text encoded",
                text_length=len(text),
                duration_ms=round(elapsed * 1000, 3),
            )

            return result

        except Exception as e:
            logger.error("Failed to encode text", error=str(e), text_length=len(text))
            raise RuntimeError(f"Failed to encode text: {e}") from e

    def encode_batch(
        self, texts: list[str], batch_size: int = 32, show_progress: bool = True
    ) -> list[list[float]]:
        """
        Encode multiple texts into embedding vectors.

        Args:
            texts: List of texts to encode
            batch_size: Batch size for encoding
            show_progress: Whether to show progress bar

        Returns:
            list[list[float]]: List of normalized embedding vectors

        Raises:
            RuntimeError: If encoding fails
        """
        if not texts:
            logger.warning("Empty text list provided for batch encoding")
            return []

        # Filter out empty texts
        valid_texts = [text for text in texts if text and text.strip()]
        if not valid_texts:
            logger.warning("No valid texts in batch")
            self._load_model()
            return [[0.0] * self._dimension] * len(texts)

        # Load model if needed
        self._load_model()

        start_time = time.time()
        try:
            # Check cache for each text
            cache_keys = [self._get_cache_key(text) for text in valid_texts]
            cached_results = {}
            texts_to_encode = []
            indices_to_encode = []

            for idx, (text, cache_key) in enumerate(zip(valid_texts, cache_keys)):
                if cache_key in self._cache:
                    cached_results[idx] = self._cache[cache_key]
                else:
                    texts_to_encode.append(text)
                    indices_to_encode.append(idx)

            # Encode texts not in cache
            if texts_to_encode:
                logger.debug(
                    "Encoding batch",
                    total=len(valid_texts),
                    cached=len(cached_results),
                    to_encode=len(texts_to_encode),
                    batch_size=batch_size,
                )

                embeddings = self._model.encode(
                    texts_to_encode,
                    batch_size=batch_size,
                    show_progress_bar=show_progress,
                    convert_to_numpy=True,
                    normalize_embeddings=False,  # We'll normalize ourselves
                )

                # Normalize embeddings
                embeddings = self._normalize_embeddings(embeddings)

                # Store results and cache them
                for i, embedding in enumerate(embeddings):
                    idx = indices_to_encode[i]
                    text = texts_to_encode[i]
                    cache_key = cache_keys[valid_texts.index(text)]
                    result = embedding.tolist()
                    cached_results[idx] = result
                    self._add_to_cache(cache_key, result)

            # Reconstruct results in original order (including empty texts)
            results = []
            valid_idx = 0
            for text in texts:
                if text and text.strip():
                    results.append(cached_results[valid_idx])
                    valid_idx += 1
                else:
                    # Empty text gets zero vector
                    results.append([0.0] * self._dimension)

            elapsed = time.time() - start_time
            logger.info(
                "Batch encoded",
                total=len(texts),
                cached=len(cached_results) - len(texts_to_encode),
                encoded=len(texts_to_encode),
                duration_ms=round(elapsed * 1000, 2),
            )

            return results

        except Exception as e:
            logger.error(
                "Failed to encode batch",
                error=str(e),
                batch_size=len(texts),
            )
            raise RuntimeError(f"Failed to encode batch: {e}") from e

    def _add_to_cache(self, cache_key: str, embedding: list[float]) -> None:
        """
        Add embedding to cache with size limit management.

        Args:
            cache_key: Cache key for the embedding
            embedding: Embedding vector to cache
        """
        # Remove oldest entries if cache is full
        if len(self._cache) >= self._max_cache_size:
            # Remove oldest entry (FIFO)
            self._cache.popitem(last=False)
            logger.debug("Cache entry evicted", cache_size=len(self._cache))

        # Add new entry (moves to end)
        self._cache[cache_key] = embedding
        logger.debug("Cache entry added", cache_key=cache_key[:8], cache_size=len(self._cache))

    def get_embedding_dimension(self) -> int:
        """
        Get the dimension of the embedding vectors.

        Returns:
            int: Embedding dimension

        Raises:
            RuntimeError: If model is not loaded
        """
        self._load_model()
        if self._dimension is None:
            raise RuntimeError("Model dimension not available")
        return self._dimension

    def clear_cache(self) -> None:
        """
        Clear the embedding cache.
        """
        cache_size = len(self._cache)
        self._cache.clear()
        logger.info("Embedding cache cleared", entries_removed=cache_size)

    def get_cache_stats(self) -> dict[str, int]:
        """
        Get cache statistics.

        Returns:
            dict: Cache statistics with size and max_size
        """
        return {
            "cache_size": len(self._cache),
            "max_cache_size": self._max_cache_size,
        }
