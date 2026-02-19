"""OpenAI Embeddings Service - Lightweight alternative to sentence-transformers."""

from langchain_openai import OpenAIEmbeddings
from src.core.config import settings

# Use OpenAI embeddings instead of local models
embeddings = OpenAIEmbeddings(
    openai_api_key=settings.OPENAI_API_KEY,
    model="text-embedding-3-small"  # Cheapest and fastest
)

def get_embeddings():
    """Return the embeddings instance."""
    return embeddings