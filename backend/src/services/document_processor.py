"""Document processing service for chunking and embedding."""

import re
import time
import unicodedata
from io import BytesIO
from pathlib import Path
from typing import Optional
from uuid import uuid4

import tiktoken
from docx import Document
from fastapi import UploadFile
from pypdf import PdfReader
from pydantic import BaseModel, Field

from src.core.config import settings
from src.core.logging import get_logger
from src.services.exceptions import DocumentProcessingError, UnsupportedFileTypeError

logger = get_logger(__name__)


class ChunkMetadata(BaseModel):
    """Metadata for a document chunk."""

    document_id: str = Field(..., description="Unique document identifier (UUID)")
    source_file: str = Field(..., description="Original filename")
    chunk_index: int = Field(..., description="Index of this chunk in the document")
    page_number: Optional[int] = Field(None, description="Page number for PDFs, None for others")
    total_chunks: int = Field(..., description="Total number of chunks in the document")
    char_start: int = Field(..., description="Character start position in original text")
    char_end: int = Field(..., description="Character end position in original text")
    token_count: int = Field(..., description="Number of tokens in this chunk")


class DocumentChunk(BaseModel):
    """A processed document chunk with content and metadata."""

    id: str = Field(default_factory=lambda: str(uuid4()), description="Unique chunk identifier")
    content: str = Field(..., description="Chunk text content")
    metadata: ChunkMetadata = Field(..., description="Chunk metadata")
    embedding: Optional[list[float]] = Field(None, description="Optional embedding vector")


class ProcessingResult(BaseModel):
    """Result of document processing."""

    document_id: str = Field(..., description="Unique document identifier")
    filename: str = Field(..., description="Original filename")
    chunks: list[DocumentChunk] = Field(..., description="List of processed chunks")
    total_chunks: int = Field(..., description="Total number of chunks created")
    status: str = Field(default="success", description="Processing status")


class DocumentProcessor:
    """Service for processing documents (PDF/DOCX) into chunks with token-based chunking."""

    def __init__(
        self,
        chunk_size_tokens: Optional[int] = None,
        chunk_overlap_tokens: Optional[int] = None,
    ) -> None:
        """
        Initialize the document processor.

        Args:
            chunk_size_tokens: Maximum tokens per chunk (defaults to CHUNK_SIZE from settings)
            chunk_overlap_tokens: Token overlap between chunks (defaults to CHUNK_OVERLAP from settings)
        """
        self.chunk_size_tokens = chunk_size_tokens or settings.CHUNK_SIZE
        self.chunk_overlap_tokens = chunk_overlap_tokens or settings.CHUNK_OVERLAP
        
        # Initialize tiktoken encoder
        try:
            self.encoder = tiktoken.get_encoding("cl100k_base")
            logger.info(
                "Document processor initialized",
                chunk_size_tokens=self.chunk_size_tokens,
                chunk_overlap_tokens=self.chunk_overlap_tokens,
            )
        except Exception as e:
            logger.error("Failed to initialize tiktoken encoder", error=str(e))
            raise DocumentProcessingError(f"Failed to initialize tokenizer: {e}")

    def count_tokens(self, text: str) -> int:
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
            logger.error("Failed to count tokens", error=str(e))
            raise DocumentProcessingError(f"Token counting failed: {e}")

    def clean_text(self, text: str) -> str:
        """
        Clean and normalize text.

        Args:
            text: Raw text to clean

        Returns:
            str: Cleaned text
        """
        start_time = time.time()
        
        # Normalize unicode characters
        text = unicodedata.normalize("NFKC", text)
        
        # Remove special control characters but keep newlines and tabs
        text = re.sub(r"[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F]", "", text)
        
        # Normalize whitespace: replace multiple spaces/tabs with single space
        text = re.sub(r"[ \t]+", " ", text)
        
        # Normalize newlines: replace multiple newlines with double newline (paragraph break)
        text = re.sub(r"\n{3,}", "\n\n", text)
        
        # Remove leading/trailing whitespace from each line
        lines = [line.strip() for line in text.split("\n")]
        text = "\n".join(lines)
        
        # Remove excessive blank lines (more than 2 consecutive)
        text = re.sub(r"\n\n\n+", "\n\n", text)
        
        # Strip overall leading/trailing whitespace
        text = text.strip()
        
        elapsed = time.time() - start_time
        logger.debug("Text cleaned", duration_ms=round(elapsed * 1000, 2), original_length=len(text))
        
        return text

    def extract_text_from_pdf(self, file_path: Path) -> list[tuple[int, str]]:
        """
        Extract text from PDF file with page numbers.

        Args:
            file_path: Path to PDF file

        Returns:
            list: List of tuples (page_number, text) for each page

        Raises:
            DocumentProcessingError: If PDF extraction fails
        """
        start_time = time.time()
        
        try:
            reader = PdfReader(file_path)
            pages = []
            
            for page_num, page in enumerate(reader.pages, start=1):
                try:
                    text = page.extract_text()
                    if text.strip():  # Only include non-empty pages
                        pages.append((page_num, text))
                except Exception as e:
                    logger.warning(
                        "Failed to extract text from page",
                        page=page_num,
                        error=str(e),
                    )
            
            elapsed = time.time() - start_time
            logger.info(
                "PDF text extracted",
                filename=file_path.name,
                pages=len(pages),
                duration_ms=round(elapsed * 1000, 2),
            )
            
            return pages
            
        except Exception as e:
            logger.error("PDF extraction failed", filename=file_path.name, error=str(e))
            raise DocumentProcessingError(f"Failed to extract text from PDF: {e}")

    def extract_text_from_docx(self, file_path: Path) -> str:
        """
        Extract text from DOCX file.

        Args:
            file_path: Path to DOCX file

        Returns:
            str: Extracted text

        Raises:
            DocumentProcessingError: If DOCX extraction fails
        """
        start_time = time.time()
        
        try:
            doc = Document(file_path)
            paragraphs = [para.text for para in doc.paragraphs if para.text.strip()]
            text = "\n\n".join(paragraphs)
            
            elapsed = time.time() - start_time
            logger.info(
                "DOCX text extracted",
                filename=file_path.name,
                paragraphs=len(paragraphs),
                duration_ms=round(elapsed * 1000, 2),
            )
            
            return text
            
        except Exception as e:
            logger.error("DOCX extraction failed", filename=file_path.name, error=str(e))
            raise DocumentProcessingError(f"Failed to extract text from DOCX: {e}")

    def chunk_text(
        self, text: str, metadata: dict, page_number: Optional[int] = None
    ) -> list[DocumentChunk]:
        """
        Split text into chunks based on token count, preserving boundaries.

        Args:
            text: Text to chunk
            metadata: Base metadata dictionary
            page_number: Optional page number for PDFs

        Returns:
            list: List of DocumentChunk objects
        """
        start_time = time.time()
        
        if not text.strip():
            logger.warning("Empty text provided for chunking")
            return []
        
        # Encode entire text to tokens
        tokens = self.encoder.encode(text)
        total_tokens = len(tokens)
        
        chunks = []
        chunk_index = 0
        current_char_pos = 0  # Track position in original text
        
        i = 0
        while i < total_tokens:
            # Calculate chunk boundaries
            chunk_end = min(i + self.chunk_size_tokens, total_tokens)
            
            # Extract token slice
            chunk_tokens = tokens[i:chunk_end]
            
            # Decode tokens back to text
            chunk_text = self.encoder.decode(chunk_tokens)
            
            # Try to preserve sentence boundaries
            if chunk_end < total_tokens:
                # Look ahead to find a good break point (sentence end)
                lookahead = min(50, total_tokens - chunk_end)  # Look ahead up to 50 tokens
                for j in range(chunk_end, min(chunk_end + lookahead, total_tokens)):
                    candidate_tokens = tokens[i:j]
                    candidate_text = self.encoder.decode(candidate_tokens)
                    
                    # Check if we hit a sentence boundary
                    if re.search(r"[.!?]\s+", candidate_text[-100:]):  # Check last 100 chars
                        chunk_end = j
                        chunk_tokens = tokens[i:chunk_end]
                        chunk_text = self.encoder.decode(chunk_tokens)
                        break
            
            # Never split mid-word - if we're in the middle of a word, extend to word boundary
            if chunk_end < total_tokens:
                # Check if we're mid-word by looking at the decoded text
                if chunk_text and not re.match(r".*\s$", chunk_text) and chunk_text[-1].isalnum():
                    # Try to extend to next space or punctuation
                    for j in range(chunk_end, min(chunk_end + 20, total_tokens)):
                        extended_tokens = tokens[i:j]
                        extended_text = self.encoder.decode(extended_tokens)
                        if re.search(r"[\s.!?,;:]", extended_text[-10:]):  # Found boundary
                            chunk_end = j
                            chunk_tokens = tokens[i:chunk_end]
                            chunk_text = self.encoder.decode(chunk_tokens)
                            break
            
            # Find actual character positions in original text
            # Use the decoded chunk text to find its position in the original text
            char_start = current_char_pos
            
            # Try to find the chunk text in the original text starting from current position
            # This handles cases where token encoding/decoding might slightly alter the text
            chunk_text_stripped = chunk_text.strip()
            if chunk_text_stripped:
                # Search for the chunk text in the original text
                search_start = max(0, current_char_pos - 50)  # Allow some lookback
                search_text = text[search_start:]
                
                # Try exact match first
                pos = search_text.find(chunk_text_stripped)
                if pos == -1:
                    # Try finding a substring match (in case of minor differences)
                    # Use first 50 chars of chunk as anchor
                    anchor = chunk_text_stripped[:min(50, len(chunk_text_stripped))]
                    pos = search_text.find(anchor)
                    if pos != -1:
                        char_start = search_start + pos
                    else:
                        # Fallback: use approximate position based on token ratio
                        token_ratio = i / total_tokens if total_tokens > 0 else 0
                        char_start = int(len(text) * token_ratio)
                else:
                    char_start = search_start + pos
                
                # Calculate end position
                char_end = char_start + len(chunk_text_stripped)
                current_char_pos = char_end
            else:
                # Empty chunk - use approximate position
                token_ratio = chunk_end / total_tokens if total_tokens > 0 else 0
                char_start = int(len(text) * token_ratio)
                char_end = char_start
                current_char_pos = char_end
            
            # Ensure positions are within bounds
            char_start = max(0, min(char_start, len(text)))
            char_end = max(char_start, min(char_end, len(text)))
            
            # Create chunk metadata
            chunk_metadata = ChunkMetadata(
                document_id=metadata["document_id"],
                source_file=metadata["source_file"],
                chunk_index=chunk_index,
                page_number=page_number,
                total_chunks=0,  # Will be updated after all chunks are created
                char_start=char_start,
                char_end=char_end,
                token_count=len(chunk_tokens),
            )
            
            # Create chunk
            chunk = DocumentChunk(
                content=chunk_text_stripped,
                metadata=chunk_metadata,
            )
            
            chunks.append(chunk)
            chunk_index += 1
            
            # Move to next chunk with overlap
            if chunk_end >= total_tokens:
                break
            i = max(i + 1, chunk_end - self.chunk_overlap_tokens)
        
        # Update total_chunks in all metadata
        for chunk in chunks:
            chunk.metadata.total_chunks = len(chunks)
        
        elapsed = time.time() - start_time
        logger.info(
            "Text chunked",
            document_id=metadata["document_id"],
            total_chunks=len(chunks),
            total_tokens=total_tokens,
            duration_ms=round(elapsed * 1000, 2),
        )
        
        return chunks

    async def process_file(self, file: UploadFile) -> ProcessingResult:
        """
        Process an uploaded file into chunks.

        Args:
            file: FastAPI UploadFile object

        Returns:
            ProcessingResult: Processing result with chunks

        Raises:
            UnsupportedFileTypeError: If file type is not supported
            DocumentProcessingError: If processing fails
        """
        process_start = time.time()
        document_id = str(uuid4())
        filename = file.filename or "unknown"
        
        logger.info(
            "Processing file",
            filename=filename,
            document_id=document_id,
            content_type=file.content_type,
        )
        
        # Validate file type
        file_ext = filename.split(".")[-1].lower() if "." in filename else ""
        if file_ext not in ["pdf", "docx"]:
            raise UnsupportedFileTypeError(
                f"Unsupported file type: {file_ext}. Only PDF and DOCX are supported."
            )
        
        try:
            # Read file content
            file_content = await file.read()
            
            # Create temporary file for processing
            import tempfile
            with tempfile.NamedTemporaryFile(delete=False, suffix=f".{file_ext}") as tmp_file:
                tmp_path = Path(tmp_file.name)
                tmp_file.write(file_content)
            
            try:
                all_chunks = []
                
                if file_ext == "pdf":
                    # Extract text with page numbers
                    pages = self.extract_text_from_pdf(tmp_path)
                    
                    for page_num, page_text in pages:
                        # Clean text
                        cleaned_text = self.clean_text(page_text)
                        
                        if not cleaned_text.strip():
                            continue
                        
                        # Chunk text for this page
                        base_metadata = {
                            "document_id": document_id,
                            "source_file": filename,
                        }
                        page_chunks = self.chunk_text(cleaned_text, base_metadata, page_number=page_num)
                        all_chunks.extend(page_chunks)
                
                elif file_ext == "docx":
                    # Extract text
                    text = self.extract_text_from_docx(tmp_path)
                    
                    # Clean text
                    cleaned_text = self.clean_text(text)
                    
                    if not cleaned_text.strip():
                        raise DocumentProcessingError("No text content found in document")
                    
                    # Chunk text
                    base_metadata = {
                        "document_id": document_id,
                        "source_file": filename,
                    }
                    all_chunks = self.chunk_text(cleaned_text, base_metadata, page_number=None)
                
                # Re-index chunks to ensure sequential chunk_index
                for idx, chunk in enumerate(all_chunks):
                    chunk.metadata.chunk_index = idx
                    chunk.metadata.total_chunks = len(all_chunks)
                
                elapsed = time.time() - process_start
                logger.info(
                    "File processing completed",
                    filename=filename,
                    document_id=document_id,
                    total_chunks=len(all_chunks),
                    duration_ms=round(elapsed * 1000, 2),
                )
                
                return ProcessingResult(
                    document_id=document_id,
                    filename=filename,
                    chunks=all_chunks,
                    total_chunks=len(all_chunks),
                    status="success",
                )
                
            finally:
                # Clean up temporary file
                try:
                    tmp_path.unlink()
                except Exception as e:
                    logger.warning("Failed to delete temporary file", path=str(tmp_path), error=str(e))
                    
        except UnsupportedFileTypeError:
            raise
        except DocumentProcessingError:
            raise
        except Exception as e:
            logger.error(
                "File processing failed",
                filename=filename,
                document_id=document_id,
                error=str(e),
                error_type=type(e).__name__,
            )
            raise DocumentProcessingError(f"Failed to process file: {e}") from e
