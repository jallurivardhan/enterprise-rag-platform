"""FastAPI application entry point."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes import admin, auth, chat, health, ingest
from src.core.config import settings
from src.core.logging import setup_logging, get_logger

# Setup logging
setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan context manager for startup and shutdown events."""
    # Startup
    logger.info("Starting up application", host=settings.API_HOST, port=settings.API_PORT)
    yield
    # Shutdown
    logger.info("Shutting down application")


# Create FastAPI app
app = FastAPI(
    title="Enterprise RAG Platform",
    description="Enterprise-grade Retrieval-Augmented Generation platform with multi-agent orchestration",
    version="1.0.0",
    lifespan=lifespan,
)

# Configure CORS - Allow all Vercel preview URLs
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for now to fix the issue
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router, prefix="/api", tags=["health"])
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(chat.router, prefix="/api/chat", tags=["Chat"])
app.include_router(ingest.router, prefix="/api")  # Router already has /ingest prefix
app.include_router(admin.router, prefix="/api/admin", tags=["Admin"])

# Log registered routes for debugging
logger.info("Routers registered", 
            health_routes=len(health.router.routes),
            chat_routes=len(chat.router.routes),
            ingest_routes=len(ingest.router.routes))
for route in chat.router.routes:
    logger.info("Chat route registered", path=route.path, methods=getattr(route, 'methods', []))


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint."""
    return {"message": "Enterprise RAG Platform API"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.API_RELOAD,
    )