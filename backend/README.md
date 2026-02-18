# Enterprise RAG Platform - Backend

Enterprise-grade Retrieval-Augmented Generation platform backend with multi-agent orchestration.

## Features

- FastAPI-based REST API
- Multi-agent system (Planner, Retriever, Validator)
- Document ingestion (PDF/DOCX)
- FAISS vector store for embeddings
- Structured logging with structlog
- Type-safe configuration with pydantic-settings

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Create a `.env` file (see `.env.example`):
```bash
cp .env.example .env
```

3. Run the application:
```bash
python -m src.main
```

Or with uvicorn directly:
```bash
uvicorn src.main:app --reload
```

## Project Structure

```
backend/
├── src/
│   ├── api/
│   │   └── routes/        # API endpoints
│   ├── agents/            # Multi-agent system
│   ├── core/              # Configuration and logging
│   ├── db/                # Vector store and metadata
│   ├── models/            # Embedding and generator models
│   ├── services/          # Business logic services
│   └── main.py            # Application entry point
└── tests/                 # Test suite
```

## API Endpoints

- `GET /api/health` - Health check
- `POST /api/chat` - Chat query (TODO)
- `GET /api/chat/stream` - Streaming chat (TODO)
- `POST /api/ingest` - Document ingestion (TODO)
- `GET /api/ingest/status/{document_id}` - Ingestion status (TODO)

## Development

Run tests:
```bash
pytest
```
