"""Metadata management for document chunks and documents."""

import json
import shutil
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field

from src.core.logging import get_logger

logger = get_logger(__name__)


# Keep the old chunk-level DocumentMetadata for backward compatibility
class ChunkDocumentMetadata:
    """Metadata for a document chunk (legacy class)."""

    def __init__(
        self,
        document_id: str | None = None,
        filename: str | None = None,
        file_type: str | None = None,
        chunk_index: int | None = None,
        total_chunks: int | None = None,
        **kwargs: Any,
    ) -> None:
        """
        Initialize document metadata.

        Args:
            document_id: Unique document identifier
            filename: Original filename
            file_type: Type of file (pdf, docx)
            chunk_index: Index of this chunk in the document
            total_chunks: Total number of chunks in the document
            **kwargs: Additional metadata fields
        """
        self.document_id = document_id or str(uuid4())
        self.filename = filename
        self.file_type = file_type
        self.chunk_index = chunk_index
        self.total_chunks = total_chunks
        self.created_at = datetime.utcnow().isoformat()
        self.extra_metadata = kwargs

    def to_dict(self) -> dict[str, Any]:
        """
        Convert metadata to dictionary.

        Returns:
            dict: Metadata as dictionary
        """
        return {
            "document_id": self.document_id,
            "filename": self.filename,
            "file_type": self.file_type,
            "chunk_index": self.chunk_index,
            "total_chunks": self.total_chunks,
            "created_at": self.created_at,
            **self.extra_metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ChunkDocumentMetadata":
        """
        Create metadata from dictionary.

        Args:
            data: Dictionary containing metadata

        Returns:
            ChunkDocumentMetadata: Metadata instance
        """
        extra = {
            k: v
            for k, v in data.items()
            if k not in ["document_id", "filename", "file_type", "chunk_index", "total_chunks", "created_at"]
        }
        return cls(
            document_id=data.get("document_id"),
            filename=data.get("filename"),
            file_type=data.get("file_type"),
            chunk_index=data.get("chunk_index"),
            total_chunks=data.get("total_chunks"),
            **extra,
        )


# New document-level metadata model
class DocumentMetadata(BaseModel):
    """Document-level metadata model."""

    id: str = Field(..., description="Unique document identifier (UUID)")
    filename: str = Field(..., description="Original filename")
    file_size: int = Field(..., description="File size in bytes")
    file_type: str = Field(..., description="File type (pdf, docx)")
    chunks_count: int = Field(default=0, description="Number of chunks in the document")
    permission: str = Field(default="public", description="Document permission: 'public' or 'private'")
    owner_id: Optional[str] = Field(default=None, description="User ID of document owner")
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat(), description="Creation timestamp")
    updated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat(), description="Last update timestamp")


class MetadataStore:
    """
    Thread-safe metadata store for document-level metadata.
    
    Uses JSON file storage with automatic backups and corruption recovery.
    """

    def __init__(self, storage_path: str = "./data/metadata.json") -> None:
        """
        Initialize the metadata store.

        Args:
            storage_path: Path to the JSON metadata file
        """
        self.storage_path = Path(storage_path)
        self._lock = threading.Lock()
        self._documents: dict[str, DocumentMetadata] = {}

        # Create parent directory if it doesn't exist
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

        # Load existing metadata if file exists
        if self.storage_path.exists():
            self._load()
        else:
            logger.info("No existing metadata file found, starting with empty store", path=str(self.storage_path))

        logger.info(
            "MetadataStore initialized",
            path=str(self.storage_path),
            documents_count=len(self._documents),
        )

    def _load(self) -> None:
        """
        Load metadata from disk.

        Raises:
            IOError: If file exists but cannot be read or parsed
        """
        if not self.storage_path.exists():
            logger.debug("Metadata file does not exist, nothing to load", path=str(self.storage_path))
            return

        start_time = time.time()

        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Load documents
            self._documents = {}
            for doc_id, doc_data in data.get("documents", {}).items():
                try:
                    doc = DocumentMetadata(**doc_data)
                    self._documents[doc_id] = doc
                except Exception as e:
                    logger.warning(
                        "Failed to load document metadata",
                        document_id=doc_id,
                        error=str(e),
                    )
                    continue

            elapsed = time.time() - start_time
            logger.info(
                "Metadata loaded from disk",
                path=str(self.storage_path),
                documents_count=len(self._documents),
                duration_ms=round(elapsed * 1000, 2),
            )

        except json.JSONDecodeError as e:
            # Try to restore from backup
            backup_path = Path(f"{self.storage_path}.backup")
            if backup_path.exists():
                logger.warning(
                    "Metadata file corrupted, attempting to restore from backup",
                    path=str(self.storage_path),
                    backup_path=str(backup_path),
                )
                try:
                    shutil.copy2(backup_path, self.storage_path)
                    # Retry loading
                    self._load()
                    return
                except Exception as restore_error:
                    logger.error(
                        "Failed to restore from backup",
                        error=str(restore_error),
                    )
                    raise IOError(f"Metadata file corrupted and backup restore failed: {e}") from e
            else:
                logger.error("Metadata file corrupted and no backup available", path=str(self.storage_path), error=str(e))
                raise IOError(f"Metadata file corrupted and no backup available: {e}") from e

        except Exception as e:
            logger.error("Failed to load metadata", path=str(self.storage_path), error=str(e))
            raise IOError(f"Failed to load metadata from {self.storage_path}: {e}") from e

    def _save(self) -> None:
        """
        Save metadata to disk with backup.

        Raises:
            IOError: If save operation fails
        """
        start_time = time.time()

        try:
            # Create backup if file exists
            if self.storage_path.exists():
                backup_path = Path(f"{self.storage_path}.backup")
                try:
                    shutil.copy2(self.storage_path, backup_path)
                    logger.debug("Backup created", backup_path=str(backup_path))
                except Exception as e:
                    logger.warning("Failed to create backup", error=str(e))
                    # Continue anyway - backup is best effort

            # Prepare data for saving
            data = {
                "documents": {doc_id: doc.model_dump() for doc_id, doc in self._documents.items()},
                "last_updated": datetime.utcnow().isoformat(),
            }

            # Write to temporary file first, then rename (atomic write)
            temp_path = Path(f"{self.storage_path}.tmp")
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            # Atomic rename
            temp_path.replace(self.storage_path)

            elapsed = time.time() - start_time
            logger.debug(
                "Metadata saved to disk",
                path=str(self.storage_path),
                documents_count=len(self._documents),
                duration_ms=round(elapsed * 1000, 2),
            )

        except Exception as e:
            # Try to restore from backup if write failed
            backup_path = Path(f"{self.storage_path}.backup")
            if backup_path.exists() and self.storage_path.exists():
                logger.warning(
                    "Save failed, attempting to restore from backup",
                    error=str(e),
                )
                try:
                    shutil.copy2(backup_path, self.storage_path)
                    logger.info("Restored from backup after failed save")
                except Exception as restore_error:
                    logger.error("Failed to restore from backup", error=str(restore_error))

            logger.error("Failed to save metadata", path=str(self.storage_path), error=str(e))
            raise IOError(f"Failed to save metadata to {self.storage_path}: {e}") from e

    def add_document(self, metadata: DocumentMetadata) -> None:
        """
        Add a new document to the store.

        Args:
            metadata: DocumentMetadata object to add

        Raises:
            ValueError: If document with same ID already exists
        """
        if not metadata.id:
            raise ValueError("Document ID cannot be empty")

        with self._lock:  # Thread-safe write operation
            if metadata.id in self._documents:
                raise ValueError(f"Document with ID '{metadata.id}' already exists")

            # Set timestamps
            now = datetime.utcnow().isoformat()
            metadata.created_at = now
            metadata.updated_at = now

            self._documents[metadata.id] = metadata
            self._save()

            logger.info("Document added to metadata store", document_id=metadata.id, filename=metadata.filename)

    def get_document(self, document_id: str) -> Optional[DocumentMetadata]:
        """
        Get a document by ID.

        Args:
            document_id: Document ID to retrieve

        Returns:
            Optional[DocumentMetadata]: Document metadata if found, None otherwise
        """
        with self._lock:  # Thread-safe read operation
            return self._documents.get(document_id)

    def list_documents(self, user_id: Optional[str] = None) -> list[DocumentMetadata]:
        """
        List all documents in the store, optionally filtered by user.

        Args:
            user_id: Optional user ID to filter documents (returns only user's documents and public documents)

        Returns:
            list[DocumentMetadata]: List of document metadata
        """
        with self._lock:  # Thread-safe read operation
            if user_id:
                # Return user's documents and public documents
                return [
                    doc
                    for doc in self._documents.values()
                    if doc.owner_id == user_id or doc.permission == "public"
                ]
            return list(self._documents.values())

    def delete_document(self, document_id: str) -> bool:
        """
        Delete a document from the store.

        Args:
            document_id: Document ID to delete

        Returns:
            bool: True if document was deleted, False if not found
        """
        with self._lock:  # Thread-safe write operation
            if document_id not in self._documents:
                logger.debug("Document not found for deletion", document_id=document_id)
                return False

            deleted_doc = self._documents.pop(document_id)
            self._save()

            logger.info("Document deleted from metadata store", document_id=document_id, filename=deleted_doc.filename)
            return True

    def update_document(self, document_id: str, updates: dict) -> Optional[DocumentMetadata]:
        """
        Update a document's metadata.

        Args:
            document_id: Document ID to update
            updates: Dictionary of fields to update (excludes id, created_at)

        Returns:
            Optional[DocumentMetadata]: Updated document metadata if found, None otherwise

        Raises:
            ValueError: If trying to update immutable fields
        """
        # Prevent updating immutable fields
        immutable_fields = {"id", "created_at"}
        if any(field in updates for field in immutable_fields):
            raise ValueError(f"Cannot update immutable fields: {immutable_fields}")

        with self._lock:  # Thread-safe write operation
            if document_id not in self._documents:
                logger.debug("Document not found for update", document_id=document_id)
                return None

            doc = self._documents[document_id]

            # Update fields
            for key, value in updates.items():
                if hasattr(doc, key):
                    setattr(doc, key, value)

            # Update timestamp
            doc.updated_at = datetime.utcnow().isoformat()

            self._save()

            logger.info("Document updated in metadata store", document_id=document_id, updated_fields=list(updates.keys()))
            return doc
