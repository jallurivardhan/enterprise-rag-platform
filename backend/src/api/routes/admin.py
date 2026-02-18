"""Admin API endpoints for role-based access control."""

from fastapi import APIRouter, Depends, HTTPException, Query

from src.services.auth import require_admin
from src.services.user_store import user_store
from src.db.metadata import MetadataStore
from src.db.vector_store import FAISSVectorStore
from src.api.routes.ingest import get_metadata_store, get_vector_store
from src.core.config import settings
from src.services.analytics_store import analytics_store
from src.services.feedback_store import feedback_store

router = APIRouter(tags=["Admin"])


@router.get("/users")
async def list_all_users(admin: dict = Depends(require_admin)):
    """List all users (admin only)."""
    users = [
        {k: v for k, v in u.items() if k != "password_hash"}
        for u in user_store.users
    ]
    return {"users": users, "total": len(users)}


@router.get("/documents")
async def list_all_documents(
    admin: dict = Depends(require_admin),
    metadata_store: MetadataStore = Depends(get_metadata_store),
):
    """List ALL documents from all users (admin only)."""
    # Get all documents without user filtering
    all_docs = metadata_store.list_documents(user_id=None)
    # Convert to dict format
    docs = [
        {
            "id": doc.id,
            "filename": doc.filename,
            "file_type": doc.file_type,
            "chunks_count": doc.chunks_count,
            "permission": doc.permission if hasattr(doc, "permission") and doc.permission else "public",
            "owner_id": doc.owner_id if hasattr(doc, "owner_id") else None,
            "created_at": doc.created_at,
        }
        for doc in all_docs
    ]
    return {"documents": docs, "total": len(docs)}


@router.delete("/documents/{document_id}")
async def admin_delete_document(
    document_id: str,
    admin: dict = Depends(require_admin),
    metadata_store: MetadataStore = Depends(get_metadata_store),
    vector_store: FAISSVectorStore = Depends(get_vector_store),
):
    """Delete any document (admin only)."""
    # Delete from vector store
    chunks_deleted = vector_store.delete_document(document_id)
    vector_store.save(settings.VECTOR_DB_PATH)
    
    # Delete from metadata store
    success = metadata_store.delete_document(document_id)
    if not success:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"status": "deleted", "document_id": document_id, "chunks_deleted": chunks_deleted}


@router.get("/analytics")
async def get_global_analytics(
    admin: dict = Depends(require_admin),
    metadata_store: MetadataStore = Depends(get_metadata_store),
):
    """Get global analytics (admin only)."""
    return {
        "usage": analytics_store.get_stats(),
        "feedback": feedback_store.get_stats(),
        "total_users": len(user_store.users),
        "total_documents": len(metadata_store._documents),
    }


@router.patch("/users/{user_id}/role")
async def update_user_role(
    user_id: str,
    role: str = Query(..., description="New role: 'admin' or 'user'"),
    admin: dict = Depends(require_admin),
):
    """Change user role (admin only)."""
    if role not in ["admin", "user"]:
        raise HTTPException(status_code=400, detail="Role must be 'admin' or 'user'")

    user = user_store.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Update role
    for i, u in enumerate(user_store.users):
        if u["id"] == user_id:
            user_store.users[i]["role"] = role
            user_store._save()
            break

    return {"status": "success", "user_id": user_id, "role": role}
