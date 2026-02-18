# Enterprise RAG Platform

Enterprise RAG Platform is a full-stack document Q&A application. Users can upload documents (PDF/TXT), ask questions, and get answers that are grounded in the uploaded content with source references.

It is built to look and behave like a production system: authentication, permissions, role-based access, rate limiting, streaming responses, feedback, analytics, and an "Agentic RAG" mode for complex questions.

---

## Table of Contents

- [What This App Does](#what-this-app-does)
- [Key Features](#key-features)
- [Tech Stack](#tech-stack)
- [Architecture](#architecture)
- [How Agentic RAG Works](#how-agentic-rag-works)
- [API Overview](#api-overview)
- [Local Setup](#local-setup)
- [Docker Setup](#docker-setup)
- [Deployment](#deployment)
- [Keyboard Shortcuts](#keyboard-shortcuts)
- [Challenges & Solutions](#challenges--solutions)
- [Skills Demonstrated](#skills-demonstrated)
- [Author](#author)

---

## What This App Does

1. You upload documents once (PDF or text)
2. The system breaks them into smaller searchable chunks
3. When you ask a question, it searches your documents for the best matching parts
4. It sends only the relevant parts to the AI model (OpenAI)
5. It returns an answer with sources and a confidence/trust indicator

**The Problem It Solves:**
- People have many documents (reports, manuals, research papers)
- Finding specific information means reading through everything manually
- Takes hours to search and compile answers from multiple documents

**My Solution:**
- Upload documents once, ask unlimited questions
- AI instantly searches through all documents
- Provides accurate answers with source citations
- Shows confidence level so users know how reliable the answer is

---

## Key Features

### Document Management
| Feature | Description |
|---------|-------------|
| Upload | Drag and drop PDF and TXT files |
| Auto Processing | Automatic chunking and embedding |
| Permissions | Public (everyone) or Private (only you) |
| Delete | Owner or admin can remove documents |

### Search and Retrieval
| Feature | Description |
|---------|-------------|
| Hybrid Search | Combines semantic (FAISS) + keyword (BM25) search |
| Scoring | 70% semantic + 30% keyword for optimal results |
| Multi-Agent | Planner → Retriever → Generator → Validator pipeline |

### RAG Modes
| Mode | Description | Best For |
|------|-------------|----------|
| Normal RAG | Single retrieval, fast answer | Simple questions |
| Agentic RAG | Multi-step reasoning, self-verification | Complex questions |
| Auto | AI chooses based on complexity | When unsure |

### Trust and Transparency
| Feature | Description |
|---------|-------------|
| Confidence Score | 0-100% reliability indicator |
| Grounding Check | Verifies answer matches sources |
| Hallucination Detection | Flags potentially made-up content |
| Source Citations | Shows exactly which documents were used |

### Security and Access Control
| Feature | Description |
|---------|-------------|
| Authentication | Secure signup/login with bcrypt hashing |
| JWT Tokens | 24-hour expiry for security |
| RBAC | Admin and User roles |
| Rate Limiting | 20 requests/minute per user |

### Cost Tracking
| Feature | Description |
|---------|-------------|
| Token Usage | Shows input/output tokens per query |
| Cost Estimation | USD cost based on GPT-4o-mini pricing |
| Model Info | Displays which AI model was used |

### User Experience
| Feature | Description |
|---------|-------------|
| Streaming | Real-time word-by-word responses |
| Voice Input | Speak instead of type |
| Compare Mode | Normal vs Agentic side-by-side |
| Export PDF | Download conversations |
| Keyboard Shortcuts | Power user productivity |
| Prompt Templates | Pre-built query templates |
| Dark/Light Mode | Theme preference |
| Analytics | Usage metrics dashboard |

---

## Tech Stack

### Backend
| Technology | Purpose |
|------------|---------|
| Python 3.11+ | Programming language |
| FastAPI | Web framework |
| FAISS | Vector database |
| Sentence Transformers | Text embeddings (all-mpnet-base-v2) |
| BM25 | Keyword search |
| OpenAI GPT-4o-mini | Response generation |
| JWT + bcrypt | Authentication |

### Frontend
| Technology | Purpose |
|------------|---------|
| Next.js 14 | React framework |
| TypeScript | Type safety |
| Tailwind CSS | Styling |
| Lucide React | Icons |

### DevOps
| Technology | Purpose |
|------------|---------|
| Docker | Containerization |
| Docker Compose | Multi-container orchestration |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     FRONTEND (Next.js)                       │
│  • Login/Signup  • Document Upload  • Chat UI  • Analytics  │
└─────────────────────────┬───────────────────────────────────┘
                          │ API Calls (JWT Protected)
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                    BACKEND API (FastAPI)                     │
│  • Authentication  • Rate Limiting  • RBAC  • Streaming     │
└─────────────────────────┬───────────────────────────────────┘
                          │
          ┌───────────────┼───────────────┐
          ▼               ▼               ▼
┌─────────────┐   ┌─────────────┐   ┌─────────────┐
│   PLANNER   │   │  RETRIEVER  │   │  GENERATOR  │
│   Agent     │──▶│   Agent     │──▶│   Agent     │
│             │   │             │   │             │
│ Understands │   │ Finds       │   │ Creates     │
│ the query   │   │ relevant    │   │ the answer  │
└─────────────┘   │ chunks      │   └──────┬──────┘
                  └──────┬──────┘          │
                         │                 ▼
                         │        ┌─────────────────┐
                         │        │   VALIDATOR     │
                         │        │   Agent         │
                         │        │                 │
                         │        │ Checks accuracy │
                         │        │ and grounding   │
                         │        └─────────────────┘
                         │
          ┌──────────────┴──────────────┐
          ▼                             ▼
┌─────────────────┐           ┌─────────────────┐
│  FAISS Vector   │           │    OpenAI       │
│    Database     │           │   GPT-4o-mini   │
└─────────────────┘           └─────────────────┘
```

---

## How Agentic RAG Works

### Traditional RAG (Simple)
```
Question → Search Once → Generate Answer
```
Problem: Often misses information for complex questions

### Agentic RAG (Advanced)
```
Question → Analyze → Decompose → Search Multiple Times → Combine → Verify → Answer
```

### Real Example

Question: "Compare the water monitoring and food security projects"

| Step | Action | What Happens |
|------|--------|--------------|
| 1 | Analyze | Detects this is a comparison (complex) |
| 2 | Decompose | Breaks into: "What is water monitoring?" + "What is food security?" |
| 3 | Retrieve | Searches for each sub-question separately |
| 4 | Synthesize | Combines all findings into one answer |
| 5 | Verify | Checks if all aspects are covered |
| 6 | Complete | Returns comprehensive answer with reasoning |

### Performance Comparison

| Query Type | Normal RAG | Agentic RAG |
|------------|------------|-------------|
| Simple questions | Good (50% confidence) | Good (50% confidence) |
| Complex comparisons | Incomplete (50%) | Comprehensive (76%) |
| Multi-part questions | Often misses parts | Covers all aspects |

---

## API Overview

### Authentication
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/signup` | Create account |
| POST | `/api/auth/login` | Login, get JWT token |
| GET | `/api/auth/me` | Current user info |

### Documents
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/ingest/upload` | Upload PDF/TXT |
| GET | `/api/ingest/documents` | List documents |
| DELETE | `/api/ingest/documents/{id}` | Delete document |
| PATCH | `/api/ingest/documents/{id}/permission` | Toggle public/private |

### Chat
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/chat` | Send question (mode: normal/agentic/auto) |
| POST | `/api/chat/stream` | Streaming response (SSE) |
| POST | `/api/chat/feedback` | Thumbs up/down |
| GET | `/api/chat/analytics` | Usage statistics |

### Admin (Admin role only)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/admin/users` | List all users |
| GET | `/api/admin/documents` | List all documents |
| PATCH | `/api/admin/users/{id}/role` | Change user role |

---

## Local Setup

### Prerequisites
- Python 3.11+
- Node.js 18+
- OpenAI API Key

### 1. Clone the Repository
```bash
git clone https://github.com/jallurivardhan/enterprise-rag-platform.git
cd enterprise-rag-platform
```

### 2. Backend Setup (FastAPI)
```bash
cd backend

# Create virtual environment
python -m venv venv

# Activate (Windows)
.\venv\Scripts\activate

# Activate (Mac/Linux)
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create .env file
echo "OPENAI_API_KEY=your_openai_key" > .env
echo "JWT_SECRET=your_secret_key" >> .env

# Run backend
python -m uvicorn src.main:app --reload --port 8000
```

### 3. Frontend Setup (Next.js)
```bash
cd frontend

# Install dependencies
npm install

# Run frontend
npm run dev
```

### 4. Access the Application
| Service | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| API Docs | http://localhost:8000/docs |

---

## Docker Setup

Run everything with one command:

```bash
# Copy environment file
cp .env.example .env

# Add your OpenAI API key to .env
# OPENAI_API_KEY=your-key-here

# Build and run
docker-compose up --build
```

---

## Deployment

### Frontend (Vercel)
1. Push code to GitHub
2. Import frontend folder into Vercel
3. Set environment variable:
   ```
   NEXT_PUBLIC_API_URL=https://your-backend-url.com
   ```
4. Deploy

### Backend (Railway/Render)
1. Connect your GitHub repo
2. Set environment variables:
   ```
   OPENAI_API_KEY=your_key
   JWT_SECRET=your_secret
   ```
3. Deploy
4. Update frontend's `NEXT_PUBLIC_API_URL`

---

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl + Enter` | Send message |
| `Ctrl + K` | Focus input |
| `Ctrl + L` | Clear chat |
| `Ctrl + E` | Export to PDF |
| `Ctrl + M` | Cycle RAG modes |
| `Ctrl + D` | Toggle dark/light mode |
| `Ctrl + /` | Show shortcuts modal |
| `Escape` | Close modal |

---

## Challenges & Solutions

### 1. Authentication & Permissions

| # | Challenge | Error | Solution |
|---|-----------|-------|----------|
| 1 | bcrypt incompatibility | `module 'bcrypt' has no attribute '__about__'` | Used bcrypt directly instead of passlib |
| 2 | CORS blocking requests | `Failed to fetch` | Added CORSMiddleware with allow_origins |
| 3 | 401 on document fetch | Unauthorized error | Added Authorization header to all requests |
| 4 | Permission button not working | No onClick response | Added onClick handler to button |
| 5 | UI not updating | Stale data shown | Fixed API response to include permission field |
| 6 | Admin access issues | Filtering applied to admin | Added role check to bypass filters |

### 2. Trust Layer, Streaming & Agentic RAG

| # | Challenge | Error | Solution |
|---|-----------|-------|----------|
| 7 | Trust data not showing | Data undefined | Added trust fields to API response |
| 8 | Streaming missing trust | No trust in stream mode | Added trust event to SSE stream |
| 9 | Cost showing $0 | Tokens not tracked | Calculated from response metadata |
| 10 | Agentic import errors | ModuleNotFoundError | Created files in correct directory |
| 11 | Light mode invisible text | White on white | Added dark: prefix for dual-mode |
| 12 | Theme blinking | Jarring transition | Added fade overlay effect |
| 13 | Voice input TypeScript | Type not found | Added global type declarations |
| 14 | Compare mode partial | Only one result | Used Promise.all() for parallel calls |
| 15 | Docker health failing | Container unhealthy | Fixed endpoint to /api/health |

### Key Learnings
- Always test with both user roles (Admin/User)
- Configure CORS early in development
- Include all needed data in API responses
- Test both light and dark modes
- Verify Docker configurations match actual routes

---

## Skills Demonstrated

### AI/ML Engineering
- RAG architecture design and implementation
- Vector embeddings and similarity search
- LLM prompt engineering
- Multi-agent system design
- Agentic AI patterns (query decomposition, self-verification)

### Backend Development
- REST API design with FastAPI
- JWT authentication and authorization
- Role-based access control (RBAC)
- Rate limiting algorithms
- Server-Sent Events for streaming

### Frontend Development
- React/Next.js application development
- TypeScript for type safety
- Responsive design with Tailwind CSS
- Real-time updates and streaming UI
- Accessibility features

### DevOps
- Docker containerization
- Docker Compose orchestration
- Environment configuration management
- Health monitoring

### Software Engineering
- Clean code architecture
- Comprehensive error handling
- Debugging and problem-solving
- Technical documentation

---

## Project Structure

```
enterprise-rag-platform/
├── backend/
│   ├── src/
│   │   ├── api/routes/        # auth, ingest, chat, admin, health
│   │   ├── agents/            # planner, retriever, generator, validator
│   │   ├── services/          # rag pipeline, agentic rag, auth, rate limit
│   │   ├── db/                # FAISS + metadata storage
│   │   └── models/            # embeddings + OpenAI integration
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── app/               # pages (chat, login, analytics, admin)
│   │   ├── components/        # UI components
│   │   └── hooks/             # custom React hooks
│   ├── Dockerfile
│   └── package.json
├── docker-compose.yml
├── .env.example
└── README.md
```

---

## Metrics

| Metric | Value |
|--------|-------|
| Total Features | 22+ |
| API Endpoints | 15+ |
| Challenges Overcome | 15 |
| AI Modes | 3 |
| Security Features | 5 |

---

## Future Enhancements

- [ ] PostgreSQL database migration
- [ ] Cloud deployment (Vercel + Railway)
- [ ] SSO/SAML authentication
- [ ] Audit logging
- [ ] Multi-collection document organization
- [ ] Slack/Teams integration

---

## Author

**Vardhan Jalluri**

- GitHub: [jallurivardhan](https://github.com/jallurivardhan)
- LinkedIn: [vardhanjalluri](https://www.linkedin.com/in/vardhanjalluri)

---

*Built with FastAPI, Next.js, FAISS, and OpenAI*
