"""Custom exceptions for document processing."""


class DocumentProcessingError(Exception):
    """Base exception for document processing errors."""

    pass


class UnsupportedFileTypeError(DocumentProcessingError):
    """Raised when an unsupported file type is encountered."""

    pass
