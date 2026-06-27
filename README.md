# Personal RAG Studio (Aviary)

Personal RAG Studio is a high-performance, asynchronous Retrieval-Augmented Generation (RAG) application. It features a robust **FastAPI backend** powered by **Pydantic AI** & **Beanie ODM (MongoDB)** and a modern **React 19 frontend** built with Vite, Tailwind CSS, and `shadcn/ui` components.

The application allows users to build context-rich study/research notebooks, ingest multiple document formats, chat with their sources using semantic search, and dynamically generate educational artifacts like interactive quizzes, flashcards, mind maps, and detailed reports.

---

## 🏗️ Architecture Flow

The system employs a client-direct S3 upload pattern coupled with an asynchronous, event-driven ingestion pipeline to keep the API server responsive.

```mermaid
graph TD
    %% Styling
    classDef frontend fill:#3b82f6,stroke:#1d4ed8,color:#fff
    classDef storage fill:#10b981,stroke:#047857,color:#fff
    classDef backend fill:#f59e0b,stroke:#b45309,color:#fff
    classDef mq fill:#8b5cf6,stroke:#6d28d9,color:#fff
    classDef db fill:#ec4899,stroke:#be185d,color:#fff

    %% Components
    FE[React 19 Frontend]:::frontend
    S3[MinIO / S3 Storage]:::storage
    RMQ[RabbitMQ Broker]:::mq
    BE[FastAPI Backend]:::backend
    MDB[MongoDB & Beanie]:::db
    PAI[Pydantic AI / LLM]:::backend

    %% Direct upload flow
    FE -->|1. Request Presigned URL| BE
    BE -->|2. Return Presigned URL| FE
    FE -->|3. Direct PUT Upload| S3

    %% Event Ingestion Loop
    S3 -->|4. ObjectCreated Event| RMQ
    RMQ -->|5. Deliver Notification| BE
    BE -->|6. Fetch & Parse File| S3
    BE -->|7. Chunk & Save Chunks| MDB
    BE -->|8. Wait for Atlas Vector Index| MDB

    %% RAG Search & Generation Flow
    FE -->|9. Submit Chat / Generate Report| BE
    BE -->|10. Rewrite Query| PAI
    BE -->|11. Atlas Vector Search| MDB
    BE -->|12. Generate Structured Output| PAI
    PAI -->|13. Return Answer / Report| BE
    BE -->|14. Respond SSE / JSON| FE
```

### 1. Direct-to-S3 Upload Flow
* The frontend requests a presigned upload URL from the backend (`POST /api/v1/file/presigned-url`).
* The frontend uploads the file directly to **MinIO / S3** using a `PUT` request with XMLHttpRequests to support upload progress tracking.
* On successful upload, the document is registered in **MongoDB** as `uploaded`.

### 2. Asynchronous Ingestion Loop
* MinIO triggers a bucket event on `ObjectCreated` and pushes it to **RabbitMQ** via an AMQP notification exchange.
* A robust, robust FastAPI lifespan background consumer (`aio-pika`) processes messages from the queue.
* The consumer claims the document (status → `processing`), reads it from MinIO, extracts text using specialized parsers, chunks the content using LangChain splitters, and persists the chunks in MongoDB.
* In Atlas environments, the worker waits (status → `indexing`) until the MongoDB Atlas Vector Search index is fully built and searchable before marking the document as `indexed`.
* *Fallback*: If RabbitMQ is disabled, a scheduler falls back to polling MongoDB for `pending`/`uploaded` files and processing them in the background.

### 3. Retrieval & Generation Flow (Pydantic AI Agents)
* **Query Optimization**: User search queries are rewritten by a dedicated LLM search agent (`query_rewrite_agent`) to strip conversational filler and extract core keywords.
* **Atlas Vector Search**: MongoDB Atlas handles semantic vector searches (`$vectorSearch`) using server-side embedding models (Atlas-managed embeddings).
* **Structured Generation**: Study agents generate structured responses (e.g. Quizzes, Flashcards, Mind Maps) mapped directly to Pydantic models (`output_type`), validating and sanitizing the content before returning it to the user.

---

## 🌟 Core Features

* 📁 **Multi-Format Support**: Extraction and chunking for `.pdf` (using `PyMuPDF`/`pymupdf4llm` to preserve markdown formatting), `.docx` (with paragraph and table cell parsing), `.txt`, and `.md`.
* 💬 **Context-Aware Studio Chat**: A RAG-driven chat interface where the agent dynamically calls tools to search the notebook's sources and formulate answers with citations.
* 📝 **Notebook Notes**: Inline rich-text editor for user notes, which are automatically chunked and indexed into the vector database just like uploaded documents.
* 📊 **RAG Artifact Generators**:
  * **Interactive Quizzes**: Custom count and difficulty settings. Auto-sanitized questions ensure 4 multiple-choice options with valid correct indices and detailed explanations.
  * **Flashcards**: Interactive study cards with front/back content.
  * **Interactive Mind Maps**: Interactive node-based mapping (custom ReactFlow visualization).
  * **Custom Reports**: Instantly generates Briefing Documents, Study Guides, Blog Posts, or Custom Reports using detail levels and instruction overlays.
* 📡 **SSE Real-time Synchronization**: A Server-Sent Events (`GET /notebooks/events`) stream broadcasts live document ingestion progress (`processing` ➔ `indexing` ➔ `indexed`) and report generation updates to the client.

---

## 📁 Repository Structure

```text
.
├── back-end/               # FastAPI Backend Service
│   ├── app/                # Application modules
│   │   ├── auth/           # User authentication, registration, & OTP delivery
│   │   ├── users/          # User profiles & RBAC models
│   │   ├── file/           # Direct upload presigned URLs & status callback routers
│   │   ├── notebooks/      # Core RAG features
│   │   │   ├── agent/      # Pydantic AI Chat & Report Agents definitions
│   │   │   ├── memory/     # Chat history tracking & AGUI converters
│   │   │   ├── prompt/     # System templates & prompt engineering
│   │   │   ├── rag/        # Document chunking, ingestion worker, & Atlas Vector Search
│   │   │   └── tools/      # Context search agent tools
│   │   ├── core/           # Config settings, Database/Beanie init, S3 client, & telemetry
│   │   └── utils/          # Shared helper modules
│   ├── tests/              # Pytest coverage suites
│   ├── pyproject.toml      # Dependency & linting configuration (uv environment)
│   └── uv.lock             # Lockfile for backend dependencies
├── front-end/              # Vite + React 19 Frontend Web App
│   ├── src/                # Frontend codebase
│   │   ├── components/     # Reusable UI & Layouts
│   │   │   └── ui/         # Shadcn/ui elements
│   │   ├── features/       # Feature-specific logic (auth, dashboard, files, notebooks)
│   │   ├── hooks/          # React hooks
│   │   ├── lib/            # Axios API client, queryClient, & utility functions
│   │   ├── routes.tsx      # Application routing definitions
│   │   └── App.tsx         # Main entry point and providers layout
│   ├── public/             # Static public assets
│   ├── package.json        # Frontend commands & npm packages
│   └── vite.config.ts      # Vite dev configurations & proxy targets
├── docker-compose.yml      # Local dev stack (MongoDB, RabbitMQ, MinIO, Backend, Frontend)
├── docker-compose.prod.yml # Production-ready Compose orchestration
├── DOKPLOY_DEPLOYMENT.md   # Deployment steps for Dokploy environments
└── AGENTS.md               # Code contribution, style guidelines, & conventions
```

---

## 🛠️ Tech Stack

### Backend
* **FastAPI**: Modern, fast web framework for building APIs.
* **Beanie ODM**: MongoDB Object Document Mapper built on `motor` and `Pydantic v2`.
* **Pydantic AI**: Model-agnostic LLM application framework from the creators of Pydantic.
* **aio-pika**: Asynchronous RabbitMQ client for consuming MinIO events.
* **PyMuPDF & PyMuPDF4LLM**: Page-by-page text & layout markdown extraction.
* **python-docx**: DOCX parsing.
* **Logfire / OpenTelemetry**: Comprehensive telemetry and system observability.

### Frontend
* **React 19**: Modern components and state hook workflows.
* **Vite**: Rapid asset bundle packaging and hot reloading.
* **Tailwind CSS**: Utility-first styling.
* **TanStack Query**: Asynchronous server state fetching, caching, and synchronization.
* **Lucide React**: Vector iconography.
* **Shadcn/ui**: Modern design system foundations.

---

## ⚙️ Configuration (`.env.example` Reference)

The application uses a centralized `.env` configuration file in the project root. Copy `.env.example` to `.env` and fill in your details:

```ini
# Database configuration (MongoDB)
DATABASE_URL=mongodb://localhost:27017/personal-rag

# Authentication & Security
JWT_SECRET_KEY=change-me-to-a-32-byte-dev-secret
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=30
OTP_EXPIRE_MINUTES=10
OTP_MAX_ATTEMPTS=5

# LLM Providers (Pydantic AI)
CHAT_PROVIDER=gemini
CHAT_API_KEY=your-gemini-api-key
CHAT_MODEL=gemini-2.5-flash-lite

# Embedding Settings (MongoDB Atlas Vector Search)
EMBEDDING_PROVIDER=gemini
EMBEDDING_API_KEY=your-gemini-api-key
EMBEDDING_MODEL=gemini-embedding-2
EMBEDDING_DIMENSION=1536

# Object Storage (MinIO)
S3_BUCKET=personal-rag-bucket
S3_REGION=us-east-1
S3_ENDPOINT_URL=http://localhost:9000
S3_PUBLIC_ENDPOINT_URL=http://localhost:9000
AWS_ACCESS_KEY_ID=minioadmin
AWS_SECRET_ACCESS_KEY=minioadmin

# RabbitMQ / Message Broker Eventing
RABBITMQ_CONSUMER_ENABLED=true
RABBITMQ_URL=amqp://guest:guest@localhost:5672/
RABBITMQ_QUEUE_NAME=notebook-document-ingestion
```

---

## 🚀 Getting Started

### Prerequisites
* **Docker & Docker Compose** installed.
* **Node.js** (v18+) & **npm** (if running frontend on host).
* **Python 3.11+** & **uv** (if running backend on host).

### Run with Docker Compose (Recommended)

1. Clone the repository and navigate to the project root.
2. Copy the template env file:
   ```bash
   cp .env.example .env
   ```
3. Boot up the full stack:
   ```bash
   docker compose up --build
   ```
4. Access the applications:
   * **Frontend Application**: `http://localhost:5173`
   * **Backend API Docs (Scalar)**: `http://localhost:8000/docs`
   * **MinIO Console**: `http://localhost:9001` (Credentials: `minioadmin` / `minioadmin`)

### Run Manually (Hybrid Mode)

If you prefer to run services locally on your host for rapid coding cycles:

1. Spin up only the infrastructure dependencies:
   ```bash
   docker compose up -d mongodb minio rabbitmq minio-mc
   ```
2. **Start Backend**:
   ```bash
   cd back-end
   ln -sf ../.env .env
   uv sync
   uv run fastapi dev app/main.py
   ```
3. **Start Frontend**:
   ```bash
   cd front-end
   npm install
   npm run dev
   ```

---

## 🧪 Development Commands

Run quality and test checks before committing code:

### Backend Checks
From the `back-end/` folder:
* **Run Tests**: `uv run pytest` (uses `mongomock-motor` for virtual database mocks)
* **Linting Check**: `uv run ruff check`
* **Auto-format Code**: `uv run ruff format`

### Frontend Checks
From the `front-end/` folder:
* **Linting Check**: `npm run lint`
* **Prettier formatting**: `npm run format`
* **Static Typecheck**: `npm run typecheck`
* **Production Build Verification**: `npm run build`
