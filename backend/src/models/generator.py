"""LLM generator for RAG responses."""

import asyncio
import time
from typing import AsyncGenerator, Optional

import tiktoken
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from src.agents.retriever import RetrievedChunk
from src.core.config import settings
from src.core.logging import get_logger

logger = get_logger(__name__)

# Default system prompt template
DEFAULT_SYSTEM_PROMPT = """You are a helpful AI assistant that answers questions based on the provided context.

RULES:
1. ONLY use information from the provided context to answer
2. If the context doesn't contain enough information to fully answer, say so clearly
3. Cite your sources by referencing [Source 1], [Source 2], etc.
4. Be concise but thorough
5. If you're unsure, express uncertainty rather than making up information

CONTEXT:
{context}"""


class GenerationResult(BaseModel):
    """Result of text generation."""

    content: str = Field(..., description="Generated text content")
    model: str = Field(..., description="Model used for generation")
    tokens_used: int = Field(..., description="Total tokens used (prompt + response)")
    generation_time_ms: float = Field(..., description="Generation time in milliseconds")


class Generator:
    """
    Generator for creating RAG responses using OpenAI LLMs.
    
    Supports both standard generation and streaming, with token management
    and error handling.
    """

    # Token limits for different models (approximate, includes prompt + response)
    MODEL_TOKEN_LIMITS = {
        "gpt-3.5-turbo": 4096,
        "gpt-4": 8192,
        "gpt-4-turbo-preview": 128000,
        "gpt-4-turbo": 128000,
        "gpt-4o-mini": 128000,  # Same as gpt-4-turbo
    }

    def __init__(
        self, model_name: str = "gpt-4o-mini", api_key: Optional[str] = None
    ) -> None:
        """
        Initialize the generator.

        Args:
            model_name: OpenAI model to use (gpt-3.5-turbo, gpt-4, etc.)
            api_key: Optional OpenAI API key (defaults to settings.OPENAI_API_KEY)
        """
        self.model_name = model_name
        self.api_key = api_key or settings.OPENAI_API_KEY
        self.llm: Optional[ChatOpenAI] = None
        self.max_tokens = self.MODEL_TOKEN_LIMITS.get(model_name, 4096)
        self.reserved_tokens = 1000  # Reserve tokens for response

        # Initialize tiktoken encoder
        try:
            self.encoder = tiktoken.encoding_for_model(model_name)
        except KeyError:
            # Fallback to cl100k_base for unknown models
            self.encoder = tiktoken.get_encoding("cl100k_base")
            logger.warning("Using cl100k_base encoding for model", model=model_name)

        if not self.api_key:
            logger.warning("OpenAI API key not set, generator will return error messages")
        else:
            try:
                self.llm = ChatOpenAI(
                    model=model_name,
                    temperature=0.7,
                    api_key=self.api_key,
                )
                logger.info("Generator initialized", model=model_name)
            except Exception as e:
                logger.error("Failed to initialize LLM", model=model_name, error=str(e))
                self.llm = None

    def format_context(self, chunks: list[RetrievedChunk]) -> str:
        """
        Format retrieved chunks as context for the LLM.

        Args:
            chunks: List of RetrievedChunk objects

        Returns:
            str: Formatted context string
        """
        if not chunks:
            return "No context available."

        formatted_parts = []
        for i, chunk in enumerate(chunks, start=1):
            # Build source attribution
            source_info = f"from {chunk.metadata.source_file}"
            if chunk.metadata.page_number is not None:
                source_info += f", page {chunk.metadata.page_number}"

            # Format chunk
            formatted = f"[Source {i}] ({source_info})\n{chunk.content}\n"
            formatted_parts.append(formatted)

        return "\n".join(formatted_parts)

    def _count_tokens(self, text: str) -> int:
        """
        Count tokens in text using tiktoken.

        Args:
            text: Text to count tokens for

        Returns:
            int: Number of tokens
        """
        try:
            return len(self.encoder.encode(text))
        except Exception as e:
            logger.warning("Failed to count tokens, using approximation", error=str(e))
            # Fallback: approximate 1 token = 4 characters
            return len(text) // 4

    def _truncate_context(
        self, chunks: list[RetrievedChunk], max_context_tokens: int
    ) -> list[RetrievedChunk]:
        """
        Truncate context by removing oldest/lowest-scored chunks if exceeding token limit.

        Args:
            chunks: List of chunks to truncate
            max_context_tokens: Maximum tokens allowed for context

        Returns:
            list[RetrievedChunk]: Truncated list of chunks
        """
        if not chunks:
            return chunks

        # Calculate tokens for each chunk
        chunk_tokens = []
        total_tokens = 0

        for chunk in chunks:
            # Count tokens in formatted chunk
            formatted = f"[Source X] (from {chunk.metadata.source_file})\n{chunk.content}\n"
            tokens = self._count_tokens(formatted)
            chunk_tokens.append((chunk, tokens))
            total_tokens += tokens

        # If within limit, return as is
        if total_tokens <= max_context_tokens:
            return chunks

        # Sort by score (descending) to keep highest-scored chunks
        chunk_tokens.sort(key=lambda x: x[0].score, reverse=True)

        # Select chunks until we hit the limit
        selected_chunks = []
        current_tokens = 0

        for chunk, tokens in chunk_tokens:
            if current_tokens + tokens <= max_context_tokens:
                selected_chunks.append(chunk)
                current_tokens += tokens
            else:
                break

        # If we still have space, try to add more chunks (lower priority)
        remaining_chunks = [c for c, _ in chunk_tokens if c not in selected_chunks]
        for chunk in remaining_chunks:
            formatted = f"[Source X] (from {chunk.metadata.source_file})\n{chunk.content}\n"
            tokens = self._count_tokens(formatted)
            if current_tokens + tokens <= max_context_tokens:
                selected_chunks.append(chunk)
                current_tokens += tokens

        # Maintain original order (by rank) for selected chunks
        selected_chunks.sort(key=lambda x: x.rank)

        removed_count = len(chunks) - len(selected_chunks)
        if removed_count > 0:
            logger.info(
                "Context truncated",
                original_chunks=len(chunks),
                final_chunks=len(selected_chunks),
                removed=removed_count,
                original_tokens=total_tokens,
                final_tokens=current_tokens,
            )

        return selected_chunks

    async def _call_llm_with_retry(
        self, messages: list[dict], max_retries: int = 3
    ) -> str:
        """
        Call LLM with retry logic.

        Args:
            messages: List of message dicts for the LLM
            max_retries: Maximum number of retry attempts

        Returns:
            str: Generated response content

        Raises:
            ValueError: If API key is not set or all retries failed
        """
        if not self.llm:
            raise ValueError(
                "OpenAI API key is not set. Please set OPENAI_API_KEY environment variable."
            )

        last_error = None
        for attempt in range(max_retries):
            try:
                response = await self.llm.ainvoke(messages)
                return response.content
            except Exception as e:
                last_error = e
                wait_time = 2 ** attempt  # Exponential backoff
                logger.warning(
                    "LLM call failed, retrying",
                    attempt=attempt + 1,
                    max_retries=max_retries,
                    error=str(e),
                    wait_time=wait_time,
                )
                if attempt < max_retries - 1:
                    await asyncio.sleep(wait_time)

        logger.error("LLM call failed after all retries", error=str(last_error))
        raise ValueError(f"Failed to generate response after {max_retries} attempts: {last_error}") from last_error

    async def generate(
        self,
        query: str,
        context: str,
        system_prompt: Optional[str] = None,
    ) -> GenerationResult:
        """
        Generate a response based on query and context.

        Args:
            query: User's query
            context: Formatted context string
            system_prompt: Optional custom system prompt (uses default if None)

        Returns:
            GenerationResult: Generation result with content and metadata

        Raises:
            ValueError: If API key is not set or generation fails
        """
        start_time = time.time()

        if not self.llm:
            error_msg = "OpenAI API key is not set. Please set OPENAI_API_KEY environment variable."
            logger.error("Generation failed", error=error_msg)
            return GenerationResult(
                content=error_msg,
                model=self.model_name,
                tokens_used=0,
                generation_time_ms=0.0,
            )

        # Use default system prompt if not provided
        if system_prompt is None:
            system_prompt = DEFAULT_SYSTEM_PROMPT.format(context=context)

        # Build messages
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": query},
        ]

        # Count tokens
        prompt_tokens = sum(self._count_tokens(msg["content"]) for msg in messages)

        logger.info(
            "Generating response",
            model=self.model_name,
            query=query[:100],
            prompt_tokens=prompt_tokens,
        )

        try:
            # Call LLM with retry
            content = await self._call_llm_with_retry(messages)

            # Count response tokens
            response_tokens = self._count_tokens(content)
            total_tokens = prompt_tokens + response_tokens

            elapsed_ms = (time.time() - start_time) * 1000

            logger.info(
                "Response generated",
                model=self.model_name,
                response_length=len(content),
                tokens_used=total_tokens,
                duration_ms=round(elapsed_ms, 2),
            )

            return GenerationResult(
                content=content,
                model=self.model_name,
                tokens_used=total_tokens,
                generation_time_ms=round(elapsed_ms, 2),
            )

        except Exception as e:
            elapsed_ms = (time.time() - start_time) * 1000
            error_msg = f"Failed to generate response: {str(e)}"
            logger.error("Generation failed", error=str(e), duration_ms=round(elapsed_ms, 2))
            return GenerationResult(
                content=error_msg,
                model=self.model_name,
                tokens_used=0,
                generation_time_ms=round(elapsed_ms, 2),
            )

    async def generate_stream(
        self,
        query: str,
        context: str,
        system_prompt: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """
        Generate a streaming response.

        Args:
            query: User's query
            context: Formatted context string
            system_prompt: Optional custom system prompt (uses default if None)

        Yields:
            str: Tokens/chunks as they arrive

        Raises:
            ValueError: If API key is not set
        """
        if not self.llm:
            error_msg = "OpenAI API key is not set. Please set OPENAI_API_KEY environment variable."
            logger.error("Streaming generation failed", error=error_msg)
            yield error_msg
            return

        # Use default system prompt if not provided
        if system_prompt is None:
            system_prompt = DEFAULT_SYSTEM_PROMPT.format(context=context)

        # Build messages
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": query},
        ]

        logger.info("Starting streaming generation", model=self.model_name, query=query[:100])

        try:
            # Create streaming LLM
            streaming_llm = ChatOpenAI(
                model=self.model_name,
                temperature=0.7,
                api_key=self.api_key,
                streaming=True,
            )

            # Stream response
            async for chunk in streaming_llm.astream(messages):
                # LangChain ChatOpenAI returns AIMessageChunk objects
                if hasattr(chunk, "content"):
                    content = chunk.content
                    if content:
                        yield content
                elif isinstance(chunk, str):
                    yield chunk

            logger.info("Streaming generation completed", model=self.model_name)

        except Exception as e:
            error_msg = f"Streaming failed: {str(e)}"
            logger.error("Streaming generation failed", error=str(e))
            yield error_msg

    # Convenience method that accepts chunks directly
    async def generate_from_chunks(
        self,
        query: str,
        chunks: list[RetrievedChunk],
        system_prompt: Optional[str] = None,
    ) -> GenerationResult:
        """
        Generate response from RetrievedChunk list with automatic token management.

        Args:
            query: User's query
            chunks: List of RetrievedChunk objects
            system_prompt: Optional custom system prompt

        Returns:
            GenerationResult: Generation result with content and metadata
        """
        # Calculate available tokens for context
        # Reserve tokens for: system prompt, query, response
        query_tokens = self._count_tokens(query)
        system_prompt_tokens = self._count_tokens(
            system_prompt or DEFAULT_SYSTEM_PROMPT.format(context="")
        )
        reserved = system_prompt_tokens + query_tokens + self.reserved_tokens
        max_context_tokens = self.max_tokens - reserved

        # Truncate context if needed
        truncated_chunks = self._truncate_context(chunks, max_context_tokens)

        # Format context
        context = self.format_context(truncated_chunks)

        # Generate response
        return await self.generate(query, context, system_prompt)


# Backward compatibility alias
ResponseGenerator = Generator
