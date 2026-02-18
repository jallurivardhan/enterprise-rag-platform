"""Document ingestion API endpoints."""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile

from src.services.auth import get_current_user
from pydantic import BaseModel, Field


class PermissionUpdate(BaseModel):
    """Permission update request model."""
    permission: str

from src.core.config import settings
from src.core.logging import get_logger
from src.db import DocumentMetadata, FAISSVectorStore, MetadataStore
from src.models.embeddings import EmbeddingModel
from src.services.document_processor import DocumentProcessor
from src.services.exceptions import DocumentProcessingError, UnsupportedFileTypeError

logger = get_logger(__name__)

router = APIRouter(prefix="/ingest", tags=["Ingestion"])

# Global service instances (singleton pattern)
_vector_store: Optional[FAISSVectorStore] = None
_metadata_store: Optional[MetadataStore] = None
_document_processor: Optional[DocumentProcessor] = None


def get_vector_store() -> FAISSVectorStore:
    """Dependency to get vector store instance."""
    global _vector_store
    if _vector_store is None:
        embedding_model = EmbeddingModel()
        dimension = embedding_model.get_embedding_dimension()
        _vector_store = FAISSVectorStore(
            dimension=dimension,
            index_path=settings.VECTOR_DB_PATH,
        )
    return _vector_store


def get_metadata_store() -> MetadataStore:
    """Dependency to get metadata store instance."""
    global _metadata_store
    if _metadata_store is None:
        _metadata_store = MetadataStore(storage_path="./data/metadata.json")
    return _metadata_store


def get_document_processor() -> DocumentProcessor:
    """Dependency to get document processor instance."""
    global _document_processor
    if _document_processor is None:
        _document_processor = DocumentProcessor()
    return _document_processor


# Request/Response Models
class UploadResponse(BaseModel):
    """Response model for document upload."""

    document_id: str = Field(..., description="Unique document identifier")
    filename: str = Field(..., description="Original filename")
    chunks_created: int = Field(..., description="Number of chunks created")
    status: str = Field(default="success", description="Processing status")


class DocumentListItem(BaseModel):
    """Document list item model."""

    id: str = Field(..., description="Document ID")
    filename: str = Field(..., description="Filename")
    file_type: str = Field(..., description="File type")
    chunks_count: int = Field(..., description="Number of chunks")
    permission: str = Field(default="public", description="Document permission: 'public' or 'private'")
    created_at: str = Field(..., description="Creation timestamp")


class DocumentListResponse(BaseModel):
    """Response model for document list."""

    documents: list[DocumentListItem] = Field(..., description="List of documents")
    total: int = Field(..., description="Total number of documents")
    limit: int = Field(..., description="Limit used")
    offset: int = Field(..., description="Offset used")


class DeleteResponse(BaseModel):
    """Response model for document deletion."""

    success: bool = Field(..., description="Whether deletion was successful")
    chunks_deleted: int = Field(..., description="Number of chunks deleted")


class ChunkListItem(BaseModel):
    """Chunk list item model."""

    chunk_index: int = Field(..., description="Chunk index in document")
    content_preview: str = Field(..., description="First 200 characters of content")
    token_count: int = Field(..., description="Number of tokens")
    page_number: Optional[int] = Field(None, description="Page number (for PDFs)")


class ChunkListResponse(BaseModel):
    """Response model for chunk list."""

    chunks: list[ChunkListItem] = Field(..., description="List of chunks")
    total: int = Field(..., description="Total number of chunks")
    limit: int = Field(..., description="Limit used")
    offset: int = Field(..., description="Offset used")


@router.post("/upload", response_model=UploadResponse, status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    permission: str = Form(default="public"),
    current_user: dict = Depends(get_current_user),
    vector_store: FAISSVectorStore = Depends(get_vector_store),
    metadata_store: MetadataStore = Depends(get_metadata_store),
    processor: DocumentProcessor = Depends(get_document_processor),
) -> UploadResponse:
    """
    Upload and process a document.

    Args:
        file: The document file to upload
        vector_store: Vector store dependency
        metadata_store: Metadata store dependency
        processor: Document processor dependency

    Returns:
        UploadResponse: Response with document_id, filename, chunks_created, and status

    Raises:
        HTTPException: If file validation or processing fails
    """
    request_id = str(uuid.uuid4())
    logger.info(
        "Document upload request received",
        request_id=request_id,
        filename=file.filename,
        content_type=file.content_type,
    )

    try:
        # Validate filename
        if not file.filename:
            raise HTTPException(status_code=400, detail="Filename is required")

        # Validate file type
        file_ext = file.filename.split(".")[-1].lower() if "." in file.filename else ""
        allowed_extensions = ["pdf", "docx", "txt"]
        if file_ext not in allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type: {file_ext}. Allowed types: {', '.join(allowed_extensions)}",
            )

        # Read file content
        file_content = await file.read()
        file_size = len(file_content)

        # Validate file size (max 10MB)
        max_size = 10 * 1024 * 1024  # 10MB
        if file_size > max_size:
            raise HTTPException(
                status_code=413,
                detail=f"File size ({file_size} bytes) exceeds maximum allowed size ({max_size} bytes)",
            )

        # Reset file pointer for processing
        await file.seek(0)

        # Process document
        logger.info("Processing document", request_id=request_id, filename=file.filename, file_size=file_size)
        
        # Handle .txt files separately (DocumentProcessor doesn't support them)
        if file_ext == "txt":
            # Read text content
            text_content = (await file.read()).decode("utf-8")
            await file.seek(0)
            
            # Create a ProcessingResult manually for text files
            from src.services.document_processor import ProcessingResult
            
            document_id = str(uuid.uuid4())
            base_metadata = {
                "document_id": document_id,
                "source_file": file.filename,
            }
            
            # Clean and chunk the text
            cleaned_text = processor.clean_text(text_content)
            chunks = processor.chunk_text(cleaned_text, base_metadata, page_number=None)
            
            processing_result = ProcessingResult(
                document_id=document_id,
                filename=file.filename,
                chunks=chunks,
                total_chunks=len(chunks),
                status="success",
            )
        else:
            # Use DocumentProcessor for PDF and DOCX
            processing_result = await processor.process_file(file)

        # Store chunks in vector store
        logger.info(
            "Storing chunks in vector store",
            request_id=request_id,
            document_id=processing_result.document_id,
            chunks_count=len(processing_result.chunks),
        )
        vector_store.add_documents(processing_result.chunks)

        # Save vector store
        vector_store.save(settings.VECTOR_DB_PATH)

        # Validate permission
        if permission not in ["public", "private"]:
            raise HTTPException(status_code=400, detail="Permission must be 'public' or 'private'")

        # Create document metadata
        doc_metadata = DocumentMetadata(
            id=processing_result.document_id,
            filename=processing_result.filename,
            file_size=file_size,
            file_type=file_ext,
            chunks_count=len(processing_result.chunks),
            permission=permission,
            owner_id=current_user["id"],
        )

        # Store metadata
        metadata_store.add_document(doc_metadata)

        # Index for BM25 hybrid search
        try:
            from src.services.bm25_search import bm25_search
            from src.services.hybrid_retriever import hybrid_retriever, HybridRetriever
            from src.agents.retriever import RetrieverAgent
            from src.models.embeddings import EmbeddingModel
            
            # Rebuild BM25 index with all chunks from all documents
            all_docs = metadata_store.list_documents()
            all_chunks_for_index = []
            
            for doc in all_docs:
                # Get chunks for this document from vector store
                doc_chunks = vector_store.get_chunks_by_document_id(doc.id)
                for chunk in doc_chunks:
                    all_chunks_for_index.append({
                        'content': chunk.content,
                        'metadata': chunk.metadata.model_dump() if hasattr(chunk.metadata, 'model_dump') else chunk.metadata
                    })
            
            if all_chunks_for_index:
                bm25_search.index_documents(all_chunks_for_index)
                
                # Initialize hybrid retriever if not already done
                if hybrid_retriever is None:
                    embedding_model = EmbeddingModel()
                    retriever_agent = RetrieverAgent(vector_store, embedding_model)
                    import src.services.hybrid_retriever as hr_module
                    hr_module.hybrid_retriever = HybridRetriever(retriever_agent, vector_weight=0.7)
                    hr_module.hybrid_retriever.index_for_bm25(all_chunks_for_index)
                else:
                    # Update existing hybrid retriever index
                    hybrid_retriever.index_for_bm25(all_chunks_for_index)
                
                logger.info(
                    "BM25 index updated",
                    request_id=request_id,
                    chunks_indexed=len(all_chunks_for_index),
                )
        except Exception as e:
            logger.warning(
                "BM25 indexing failed (non-critical)",
                request_id=request_id,
                error=str(e),
            )

        logger.info(
            "Document uploaded successfully",
            request_id=request_id,
            document_id=processing_result.document_id,
            chunks_created=len(processing_result.chunks),
        )

        return UploadResponse(
            document_id=processing_result.document_id,
            filename=processing_result.filename,
            chunks_created=len(processing_result.chunks),
            status="success",
        )

    except HTTPException:
        raise
    except UnsupportedFileTypeError as e:
        logger.error("Unsupported file type", request_id=request_id, error=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except DocumentProcessingError as e:
        logger.error("Document processing failed", request_id=request_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Document processing failed: {str(e)}")
    except Exception as e:
        logger.error(
            "Unexpected error during document upload",
            request_id=request_id,
            error=str(e),
            error_type=type(e).__name__,
        )
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/documents", response_model=DocumentListResponse)
async def list_documents(
    limit: int = Query(default=50, ge=1, le=100, description="Maximum number of documents to return"),
    offset: int = Query(default=0, ge=0, description="Number of documents to skip"),
    current_user: dict = Depends(get_current_user),
    metadata_store: MetadataStore = Depends(get_metadata_store),
) -> DocumentListResponse:
    """
    List all ingested documents with pagination.
    
    Admin users see ALL documents.
    Regular users see only their own documents + public documents.

    Args:
        limit: Maximum number of documents to return
        offset: Number of documents to skip
        current_user: Current authenticated user
        metadata_store: Metadata store dependency

    Returns:
        DocumentListResponse: List of documents with pagination info
    """
    request_id = str(uuid.uuid4())
    logger.info("Listing documents", request_id=request_id, limit=limit, offset=offset, user_id=current_user["id"], user_role=current_user.get("role"))

    try:
        # Admin sees ALL documents
        if current_user.get("role") == "admin":
            all_documents = metadata_store.list_documents(user_id=None)
        else:
            # Regular user sees only their docs + public docs
            all_documents = metadata_store.list_documents(user_id=current_user["id"])

        # Apply pagination
        total = len(all_documents)
        paginated_documents = all_documents[offset : offset + limit]

        # Convert to response model - ensure permission field exists
        document_items = []
        for doc in paginated_documents:
            # Ensure permission field exists (for backward compatibility with old documents)
            doc_permission = doc.permission if hasattr(doc, 'permission') and doc.permission else "public"
            document_items.append(
                DocumentListItem(
                    id=doc.id,
                    filename=doc.filename,
                    file_type=doc.file_type,
                    chunks_count=doc.chunks_count,
                    permission=doc_permission,
                    created_at=doc.created_at,
                )
            )

        logger.info(
            "Documents listed",
            request_id=request_id,
            total=total,
            returned=len(document_items),
            user_role=current_user.get("role"),
        )

        return DocumentListResponse(
            documents=document_items,
            total=total,
            limit=limit,
            offset=offset,
        )

    except Exception as e:
        logger.error("Failed to list documents", request_id=request_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to list documents: {str(e)}")


@router.get("/documents/{document_id}", response_model=DocumentMetadata)
async def get_document(
    document_id: str,
    metadata_store: MetadataStore = Depends(get_metadata_store),
) -> DocumentMetadata:
    """
    Get a single document by ID.

    Args:
        document_id: Document ID to retrieve
        metadata_store: Metadata store dependency

    Returns:
        DocumentMetadata: Full document metadata

    Raises:
        HTTPException: If document not found
    """
    request_id = str(uuid.uuid4())
    logger.info("Getting document", request_id=request_id, document_id=document_id)

    try:
        doc = metadata_store.get_document(document_id)
        if doc is None:
            logger.warning("Document not found", request_id=request_id, document_id=document_id)
            raise HTTPException(status_code=404, detail=f"Document with ID '{document_id}' not found")

        logger.info("Document retrieved", request_id=request_id, document_id=document_id)
        return doc

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get document", request_id=request_id, document_id=document_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get document: {str(e)}")


@router.delete("/documents/{document_id}", response_model=DeleteResponse)
async def delete_document(
    document_id: str,
    vector_store: FAISSVectorStore = Depends(get_vector_store),
    metadata_store: MetadataStore = Depends(get_metadata_store),
) -> DeleteResponse:
    """
    Delete a document and all its chunks.

    Args:
        document_id: Document ID to delete
        vector_store: Vector store dependency
        metadata_store: Metadata store dependency

    Returns:
        DeleteResponse: Deletion result with chunks_deleted count

    Raises:
        HTTPException: If document not found
    """
    request_id = str(uuid.uuid4())
    logger.info("Deleting document", request_id=request_id, document_id=document_id)

    try:
        # Check if document exists
        doc = metadata_store.get_document(document_id)
        if doc is None:
            logger.warning("Document not found for deletion", request_id=request_id, document_id=document_id)
            raise HTTPException(status_code=404, detail=f"Document with ID '{document_id}' not found")

        # Delete from vector store (returns number of chunks deleted)
        chunks_deleted = vector_store.delete_document(document_id)

        # Save vector store after deletion
        vector_store.save(settings.VECTOR_DB_PATH)

        # Delete from metadata store
        metadata_store.delete_document(document_id)

        logger.info(
            "Document deleted successfully",
            request_id=request_id,
            document_id=document_id,
            chunks_deleted=chunks_deleted,
        )

        return DeleteResponse(success=True, chunks_deleted=chunks_deleted)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to delete document",
            request_id=request_id,
            document_id=document_id,
            error=str(e),
        )
        raise HTTPException(status_code=500, detail=f"Failed to delete document: {str(e)}")


@router.patch("/documents/{document_id}/permission")
async def update_permission(
    document_id: str,
    body: PermissionUpdate,
    current_user: dict = Depends(get_current_user),
    metadata_store: MetadataStore = Depends(get_metadata_store),
):
    """Update document permission (public/private)."""
    permission = body.permission
    request_id = str(uuid.uuid4())
    logger.info(
        "Updating document permission",
        request_id=request_id,
        document_id=document_id,
        permission=permission,
        user_id=current_user["id"],
    )

    # Validate permission
    if permission not in ["public", "private"]:
        raise HTTPException(status_code=400, detail="Permission must be 'public' or 'private'")

    # Get document and verify ownership
    doc = metadata_store.get_document(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Only owner can change permission
    if doc.owner_id != current_user["id"]:
        logger.warning(
            "Unauthorized permission update attempt",
            request_id=request_id,
            document_id=document_id,
            user_id=current_user["id"],
            owner_id=doc.owner_id,
        )
        raise HTTPException(status_code=403, detail="You can only change your own documents")

    # Update permission
    updated_doc = metadata_store.update_document(document_id, {"permission": permission})
    if not updated_doc:
        raise HTTPException(status_code=500, detail="Failed to update document permission")

    logger.info(
        "Document permission updated",
        request_id=request_id,
        document_id=document_id,
        permission=permission,
    )

    return {"status": "success", "document_id": document_id, "permission": permission}


@router.get("/documents/{document_id}/chunks", response_model=ChunkListResponse)
async def list_document_chunks(
    document_id: str,
    limit: int = Query(default=50, ge=1, le=100, description="Maximum number of chunks to return"),
    offset: int = Query(default=0, ge=0, description="Number of chunks to skip"),
    vector_store: FAISSVectorStore = Depends(get_vector_store),
    metadata_store: MetadataStore = Depends(get_metadata_store),
) -> ChunkListResponse:
    """
    List all chunks for a document with pagination.

    Args:
        document_id: Document ID
        limit: Maximum number of chunks to return
        offset: Number of chunks to skip
        vector_store: Vector store dependency
        metadata_store: Metadata store dependency

    Returns:
        ChunkListResponse: List of chunks with pagination info

    Raises:
        HTTPException: If document not found
    """
    request_id = str(uuid.uuid4())
    logger.info("Listing document chunks", request_id=request_id, document_id=document_id, limit=limit, offset=offset)

    try:
        # Check if document exists
        doc = metadata_store.get_document(document_id)
        if doc is None:
            logger.warning("Document not found", request_id=request_id, document_id=document_id)
            raise HTTPException(status_code=404, detail=f"Document with ID '{document_id}' not found")

        # Get all chunks for this document from vector store
        all_chunks = vector_store.get_chunks_by_document_id(document_id)

        # Apply pagination
        total = len(all_chunks)
        paginated_chunks = all_chunks[offset : offset + limit]

        # Convert to response model
        chunk_items = [
            ChunkListItem(
                chunk_index=chunk.metadata.chunk_index,
                content_preview=chunk.content[:200] + ("..." if len(chunk.content) > 200 else ""),
                token_count=chunk.metadata.token_count,
                page_number=chunk.metadata.page_number,
            )
            for chunk in paginated_chunks
        ]

        logger.info(
            "Document chunks listed",
            request_id=request_id,
            document_id=document_id,
            total=total,
            returned=len(chunk_items),
        )

        return ChunkListResponse(
            chunks=chunk_items,
            total=total,
            limit=limit,
            offset=offset,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to list document chunks",
            request_id=request_id,
            document_id=document_id,
            error=str(e),
        )
        raise HTTPException(status_code=500, detail=f"Failed to list document chunks: {str(e)}")


@router.get("/hybrid-status")
async def get_hybrid_status():
    """Check if hybrid search is enabled."""
    from src.services.bm25_search import bm25_search
    return {
        "bm25_indexed": len(bm25_search.documents) > 0,
        "documents_indexed": len(bm25_search.documents),
        "hybrid_enabled": True
    }
