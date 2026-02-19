# Enterprise RAG Platform

<div align="center">

**An enterprise-grade AI document intelligence system built with FastAPI and Next.js**

[![Live Demo](https://img.shields.io/badge/Live_Demo-Visit_App-blue?style=for-the-badge)](https://enterprise-rag-platform-eosin.vercel.app/login)
[![API](https://img.shields.io/badge/API-Render-green?style=for-the-badge)](https://dashboard.render.com/web/srv-d6amcv8boq4c73dg4tjg)

</div>

---

## Application Screenshots

### Homepage
![Homepage](./assets/homepage.png)

### Normal RAG Mode
![Normal RAG](./assets/normal-rag.png)

### Agentic RAG Mode
![Agentic RAG](./assets/agentic-rag.png)

### Comparison Mode
![Comparison](./assets/comparison.png)

### Analytics Dashboard
![Analytics](./assets/analytics.png)

---

## Overview

Enterprise RAG Platform is a production-grade document intelligence system that allows users to upload documents and ask questions in natural language. It uses advanced Retrieval-Augmented Generation (RAG) techniques, including multi-step Agentic reasoning, to generate accurate and explainable answers grounded in source documents.

### Live Demo

| Service | URL |
|---------|-----|
| **Frontend** | [https://enterprise-rag-platform-gamma.vercel.app](https://enterprise-rag-platform-eosin.vercel.app/login) |
| **Backend API** | [https://enterprise-rag-platform.onrender.com](https://dashboard.render.com/web/srv-d6amcv8boq4c73dg4tjg) |

---

## Project Goals

This platform simulates how modern organizations use AI to search, analyze, and reason over internal documents securely. The goal was to build a **production-style AI system** — not just a demo.

---

## Features

### Document Management
- **Multi-format Support**: Upload PDF, DOCX, and TXT files
- **Smart Chunking**: Automatic document splitting for optimal retrieval
- **Permission Control**: Set documents as public or private
- **Easy Management**: View, delete, and organize your documents

### AI-Powered Chat with Multiple RAG Modes

| Mode | Description | Best For |
|------|-------------|----------|
| **Normal RAG** | Single-step retrieval and response generation | Simple, direct queries |
| **Agentic RAG** | Multi-step reasoning with query decomposition, multiple retrieval passes, and self-verification | Complex, analytical questions |
| **Auto Mode** | AI automatically selects the appropriate strategy | When unsure which mode to use |

### Security and Authentication
- **JWT Authentication**: Secure user login and registration
- **bcrypt Password Hashing**: Industry-standard security
- **Role-Based Access Control**: Admin and user roles
- **Document-Level Permissions**: Public and private documents
- **Rate Limiting**: 20 requests per minute per user

### Trust and Grounding Layer

Every response includes:
- Confidence score (0-100%)
- Grounding validation
- Hallucination risk detection
- Source citations
- Token usage and estimated cost

### Analytics Dashboard
- Total queries tracking
- Average response time
- User satisfaction rate
- Popular topics analysis
- Feedback statistics
- Recent activity monitoring

### User Experience
- **Streaming Responses**: Real-time word-by-word generation
- **Voice Input**: Speak your questions
- **Dark/Light Mode**: Customizable UI theme
- **Export to PDF**: Save conversations
- **Keyboard Shortcuts**: Power user features
- **Conversation Memory**: Context-aware follow-ups

---

## Tech Stack

### Frontend
| Technology | Purpose |
|------------|---------|
| Next.js 14 | React framework with App Router |
| TypeScript | Type-safe development |
| Tailwind CSS | Utility-first styling |
| shadcn/ui | UI component library |
| Server-Sent Events | Real-time streaming |

### Backend
| Technology | Purpose |
|------------|---------|
| FastAPI | High-performance Python API |
| OpenAI GPT-4o-mini | Language model for chat |
| OpenAI text-embedding-3-small | Vector embeddings |
| In-memory Vector Store | Cosine similarity search |
| BM25 | Keyword search for hybrid retrieval |
| JWT + bcrypt | Authentication |

### Deployment
| Service | Platform |
|---------|----------|
| Frontend | Vercel |
| Backend | Render |
| Monitoring | UptimeRobot |

---

## Technical Architecture

```
Frontend --> FastAPI Backend --> RAG Pipeline --> Vector Store --> LLM
```

### Backend Multi-Agent Structure
- **Planner Agent**: Analyzes query complexity
- **Retriever Agent**: Fetches relevant documents
- **Generator Agent**: Creates responses
- **Validator Agent**: Checks grounding and hallucination risk

Agentic RAG introduces multi-hop reasoning and self-verification before generating the final response.

---

## Challenges Faced and Solutions

### 1. CORS Configuration Issues
**Problem**: Frontend couldn't communicate with backend due to CORS restrictions.

**Solution**: Configured FastAPI CORS middleware to allow all origins during development, then restricted to specific Vercel domains for production.

### 2. Render Memory Limits (512MB)
**Problem**: PyTorch + sentence-transformers exceeded Render's free tier 512MB RAM limit.

**Solution**: 
- Replaced local sentence-transformers with OpenAI text-embedding-3-small API
- Replaced FAISS with lightweight in-memory vector store using cosine similarity
- Removed heavy dependencies (~500MB saved)

### 3. Hardcoded Localhost URLs
**Problem**: Frontend had localhost:8000 hardcoded in 16+ locations across 8 files, causing production failures.

**Solution**: Global find-and-replace to use environment variables and production URLs.

### 4. Vercel Build Cache
**Problem**: Vercel kept serving old cached builds even after code updates.

**Solution**: Deleted project and redeployed fresh with "Use existing Build Cache" unchecked.

### 5. Environment Variables at Build Time
**Problem**: Next.js NEXT_PUBLIC_ variables are embedded at build time, not runtime.

**Solution**: Required full redeployment (without cache) after changing environment variables.

### 6. Render Cold Starts
**Problem**: Render free tier spins down after 15 minutes of inactivity, causing 30-60 second cold starts.

**Solution**: Set up UptimeRobot to ping /api/health endpoint every 5 minutes to keep the service awake.

### 7. TypeScript Strict Mode Errors
**Problem**: Vercel deployment failed due to TypeScript errors that didn't appear locally.

**Solution**: Fixed type definitions for SpeechRecognition API, toast components, and header types.

---

## Getting Started

### Prerequisites
- Node.js 18+
- Python 3.10+
- OpenAI API Key

### Local Development

#### 1. Clone the repository
```bash
git clone https://github.com/jallurivardhan/enterprise-rag-platform.git
cd enterprise-rag-platform
```

#### 2. Backend Setup
```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create .env file
echo "OPENAI_API_KEY=your-openai-api-key" > .env
echo "JWT_SECRET=your-secret-key" >> .env

# Run the server
uvicorn src.main:app --reload --port 8000
```

#### 3. Frontend Setup
```bash
cd frontend

# Install dependencies
npm install

# Create .env.local file
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local

# Run the development server
npm run dev
```

#### 4. Open the app
Visit [http://localhost:3000](http://localhost:3000)

---

## Docker Deployment

```bash
# Clone the repository
git clone https://github.com/jallurivardhan/enterprise-rag-platform.git
cd enterprise-rag-platform

# Create .env file with your API keys
echo "OPENAI_API_KEY=your-openai-api-key" > .env
echo "JWT_SECRET=your-secret-key" >> .env

# Run with Docker Compose
docker-compose up --build
```

---

## Usage

### 1. Create an Account
- Click "Sign Up" on the login page
- Enter your username and password

### 2. Upload Documents
- Click "Upload Document" in the sidebar
- Select PDF, DOCX, or TXT files (max 10MB)
- Set permission to public or private

### 3. Ask Questions
- Type your question in the chat input
- Select RAG mode (Normal/Agentic/Auto)
- Press Enter or click Send

### 4. Review Responses
- View AI-generated answers with source citations
- Check trust indicators for confidence levels
- Expand sources to see relevant document chunks
- Provide feedback with thumbs up/down

---

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| Ctrl + Enter | Send message |
| Ctrl + K | Focus input |
| Ctrl + L | Clear chat |
| Ctrl + E | Export to PDF |
| Ctrl + M | Toggle RAG mode |
| Ctrl + D | Toggle dark mode |
| Ctrl + / | Show shortcuts |
| Esc | Close modal |

---

## API Endpoints

### Authentication
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /api/auth/register | Register new user |
| POST | /api/auth/login | Login user |
| GET | /api/auth/me | Get current user |

### Documents
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /api/ingest/upload | Upload document |
| GET | /api/ingest/documents | List documents |
| DELETE | /api/ingest/documents/{id} | Delete document |
| PATCH | /api/ingest/documents/{id}/permission | Update permission |

### Chat
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /api/chat | Send chat query |
| GET | /api/chat/stream | Stream chat response |
| POST | /api/chat/feedback | Submit feedback |

### Admin
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /api/admin/users | List all users |
| GET | /api/admin/documents | List all documents |
| PATCH | /api/admin/users/{id}/role | Update user role |

### Health
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /api/health | Health check |

---

## Project Structure

```
enterprise-rag-platform/
├── backend/
│   ├── src/
│   │   ├── agents/          # RAG agents (retriever, planner)
│   │   ├── api/             # API routes
│   │   │   └── routes/      # Endpoint handlers
│   │   ├── core/            # Config, logging
│   │   ├── db/              # Vector store, metadata
│   │   ├── models/          # Embedding models
│   │   └── services/        # Business logic
│   ├── requirements.txt
│   └── Dockerfile
│
├── frontend/
│   ├── src/
│   │   ├── app/             # Next.js pages
│   │   ├── components/      # React components
│   │   ├── hooks/           # Custom hooks
│   │   ├── lib/             # Utilities, API client
│   │   └── types/           # TypeScript types
│   ├── package.json
│   └── Dockerfile
│
├── assets/                  # Screenshots for README
└── docker-compose.yml
```

---

## Engineering Highlights

- Implemented Agentic RAG with query decomposition and self-verification
- Built hybrid retrieval combining vector search and BM25
- Designed modular multi-agent backend architecture
- Integrated real-time streaming with Server-Sent Events
- Implemented enterprise-style authentication and RBAC
- Built analytics and observability features
- Added cost and token tracking per query
- Deployed full-stack production application
- Optimized for free-tier hosting (Vercel + Render)

---

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (git checkout -b feature/AmazingFeature)
3. Commit your changes (git commit -m 'Add some AmazingFeature')
4. Push to the branch (git push origin feature/AmazingFeature)
5. Open a Pull Request

---

## Author

**Vardhan Jalluri**

GitHub: [@jallurivardhan](https://github.com/jallurivardhan)

---

## Acknowledgements

- [OpenAI](https://openai.com) for GPT-4 and embeddings API
- [Vercel](https://vercel.com) for frontend hosting
- [Render](https://render.com) for backend hosting
- [shadcn/ui](https://ui.shadcn.com) for beautiful UI components
- [LangChain](https://langchain.com) for RAG framework
- [UptimeRobot](https://uptimerobot.com) for monitoring

---

<div align="center">


Developed by Vardhan Jalluri

</div>