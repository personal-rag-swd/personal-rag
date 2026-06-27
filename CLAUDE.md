# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Personal RAG ("Aviary") is a notebook-based RAG application: users create notebooks, upload documents, and chat with an LLM agent grounded in those documents (with retrieval citations) plus generate structured reports. It is a FastAPI backend + Vite/React 19 frontend.

> The project recently migrated from PostgreSQL/pgvector + Alembic to **MongoDB + Beanie**. Some prose in `README.md` still references Postgres/pgvector/alembic — those parts are stale. `AGENTS.md` and this file reflect the current state.

## Commands

Backend (run from `back-end/`):
- `uv sync` — install deps
- `uv run fastapi dev app/main.py` — run dev API server (port 8000)
- `uv run pytest` — run all tests; single test: `uv run pytest tests/test_notebooks.py::test_name`
- `uv run ruff check` / `uv run ruff format` — lint / format (ruff config in `pyproject.toml`, line length 88, very strict ruleset)

Frontend (run from `front-end/`):
- `npm install`, `npm run dev` (port 5173)
- `npm run build` (= `tsc -b && vite build`), `npm run typecheck`, `npm run lint`, `npm run format`

Full stack: `cp .env.example .env && docker compose up --build`. CI (`.github/workflows/ci.yml`) runs backend `uv run pytest` and frontend `npm run lint` + `npm run build` on PRs to `master`.

## MongoDB / Beanie conventions (critical)

These are non-obvious and cause silent failures if violated:
- **Always use dict-based queries** (`{"field": value}`), never `Eq(Model.field, value)` — Pydantic v2's metaclass blocks class-level field access on Beanie `Document`s.
- For id lookups use `{"_id": value}`, **not** `{"id": value}` — Beanie maps Python `id` → Mongo `_id`.
- Document models all use `id: UUID = Field(default_factory=uuid4)`. UUIDs are stored as BSON `Binary`; when building `$vectorSearch` filters on UUID fields, wrap with `Binary.from_uuid(...)` (see `rag/search_service.py`).
- Atlas `$vectorSearch` uses server-side embeddings: pass `query` (raw text) on the `content` path, not a precomputed `queryVector`. Index name is `notebook_chunks_vector_index`.
- Tests use `mongomock-motor`; `conftest.py` patches `list_collection_names` to drop the `authorizedCollections` kwarg for compatibility.
- All Document models register in `app/main.py` `lifespan()` via `init_beanie(document_models=[...])` — new models must be added there.

## Backend architecture

Feature-oriented modules under `back-end/app/`, each with `models.py` / `schemas.py` / `service.py` / `router.py`. Keep route handlers thin; business logic lives in services. Routers are mounted under `/api/v1` in `main.py`.

- `auth/` — OTP email-verification registration (`PendingRegistration`), JWT access + rotating refresh tokens (`RefreshToken`). Email via Resend.
- `users/` — `User` model + RBAC. `users/dependencies.py` provides `get_current_user` (reads `Authorization: Bearer` header **or** `access_token` cookie) and `require_role(role)`.
- `file/` — S3/MinIO presigned-URL upload flow (`POST /file/presigned-url`). Clients upload directly to object storage.
- `notebooks/` — the core. Contains the RAG pipeline, chat agent, reports, and real-time events.

### Document ingestion pipeline (`notebooks/rag/`, `notebooks/consumer.py`)

1. Client gets a presigned URL and uploads to MinIO/S3; a `NotebookDocument` row is created with `status="pending"`.
2. MinIO emits an `ObjectCreated` event → RabbitMQ. `consumer.py` (`run_notebook_document_consumer`, started in `lifespan` when `RABBITMQ_CONSUMER_ENABLED=true`) consumes it and calls `ingest_document_by_id`.
3. Ingestion (`ingestion_service.py`): claim doc (`status="processing"`) → fetch bytes from S3 (or `document.content` for in-app notes) → `chunk_document` (`document_chunker.py`) → store `NotebookDocumentChunk` rows → `wait_for_atlas_vector_index` (polls Atlas index until ACTIVE + queryable) → `status="indexed"`.
4. Document **status lifecycle**: `pending → uploaded → processing → indexing → indexed` (or `failed`). Stale docs are timed out by `fail_stale_*` helpers.
5. **Fallback without RabbitMQ**: `process_unprocessed_notebook_documents()` polls Mongo for `pending`/`uploaded` docs — used when `RABBITMQ_CONSUMER_ENABLED=false` (the default).

### Chat & retrieval

- `agent/chat_agent.py` — a `pydantic-ai` `Agent` with a single `search_notebook_context` tool that calls `rag/search_service.py:search_notebook_chunks` (Atlas `$vectorSearch`, optionally rewriting the query first via `rewrite_query_text` when `ENABLE_QUERY_REWRITE`).
- `POST /notebooks/{id}/chat` streams via the **AG-UI adapter** (`AGUIAdapter.dispatch_request`). Chat history persists as `NotebookMessage` docs; `keep_recent` trims to the last ~15 non-system messages per turn.
- LLM access goes through `core/llm_provider.py` (`resolve_chat_provider`). Only the `openrouter` provider is wired up; forced tool-choice is disabled for broad model compatibility. `chat_provider_is_configured()` gates LLM features behind a friendly 503.

### Reports & real-time updates

- `agent/report_agents.py` + `service.py:run_report_generation` generate structured `NotebookReport`s as background `asyncio` tasks. On startup, `_recover_pending_reports()` re-queues reports stuck in `pending`/`generating`.
- `events.py` — an in-process `event_bus` (per-`user_id` asyncio queues). Ingestion/report state changes call `publish_document_event` / `publish_report_event`; clients subscribe over SSE at `GET /notebooks/events`.

## Frontend architecture

`front-end/src/` is feature-organized:
- `features/<name>/` (`auth`, `notebooks`, `files`, `dashboard`) each hold `api.ts`, `types.ts`, `store/` (Zustand), and `components/`.
- `components/ui/` — shadcn-style primitives (kebab-case filenames). `components/assistant-ui/` — chat UI built on `@assistant-ui/react` + `@assistant-ui/react-ag-ui`, which connects to the backend's AG-UI chat stream.
- `lib/api-client.ts` — axios instances with `baseURL = VITE_API_URL`, `withCredentials: true` (cookie-based auth). Server state via `@tanstack/react-query` (`lib/query-client.ts`).
- Routing in `routes.tsx`; React Router 7. Tailwind CSS v4.
- No frontend test runner — validate UI changes with `npm run lint` and `npm run typecheck`.
- `front-end-old/` is legacy Next.js; do not touch unless explicitly asked.

## Conventions

- Python: 4-space indent, full type hints, snake_case, imports at top of file (inline imports OK in tests). Feature modules follow `models/schemas/service/router`.
- Frontend: PascalCase components, camelCase functions/vars, kebab-case reusable UI filenames.
- Config: backend settings in `core/config.py` (pydantic-settings, loaded from `.env`). Never commit secrets. Production compose (`docker-compose.prod.yml`) requires `MONGODB_URL`, `MINIO_*`, `JWT_SECRET_KEY`, `CORS_ORIGINS`, `S3_PUBLIC_ENDPOINT_URL`, `VITE_API_URL`.
