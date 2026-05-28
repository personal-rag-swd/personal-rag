# Personal RAG

Personal RAG is a two-part application with a FastAPI backend and a Vite + React frontend. The backend provides authentication, user management, notebooks, and file services (presigned URLs and upload callbacks). The frontend provides the application UI.

## Repository Structure

```text
.
├── back-end/          # FastAPI, SQLModel, Alembic, pytest
│   ├── app/           # API application code (auth, users, file)
│   ├── alembic/       # Database migration environment and versions
│   └── pyproject.toml # Python dependencies and pytest config
├── front-end/         # Vite, React, TypeScript, Tailwind CSS
│   ├── src/           # Application source code
│   ├── src/features/  # Feature modules (auth, files actions and state)
│   └── package.json   # Frontend scripts and dependencies
├── docker-compose.yml # Full local dev stack (Postgres, MinIO, backend, frontend)
└── AGENTS.md          # Contributor guide
```

## Prerequisites

- Docker and Docker Compose

## Quick Start (Full Stack via Docker Compose)

```bash
docker compose up --build
```

Service URLs:

- Frontend: `http://localhost:5173`
- Backend API: `http://localhost:8000`
- `GET /ping` for a health check
- `GET /docs` for Scalar API documentation
- MinIO API: `http://localhost:9000`
- MinIO Console: `http://localhost:9001` (username/password: `minioadmin` / `minioadmin`)

The stack includes:

- Postgres with pgvector
- MinIO + `mc` bootstrap (bucket + webhook event configuration)
- FastAPI backend in dev mode
- Vite frontend dev server

## Optional Host-Run Setup

If you prefer running backend/frontend directly on your host, keep Postgres/MinIO in Compose:

```bash
cp .env.example .env
docker compose up -d postgres minio minio-mc

cd back-end
ln -sf ../.env .env
uv sync
uv run alembic upgrade head
uv run fastapi dev app/main.py

cd front-end
npm install
npm run dev
```

## Development Commands

Backend commands should be run from `back-end/`:

- `uv run pytest`: run backend tests.
- `uv run alembic revision --autogenerate -m "message"`: generate a migration from model changes.
- `uv run alembic upgrade head`: apply migrations.

Frontend commands should be run from `front-end/`:

- `npm run lint`: run ESLint.
- `npm run build`: create a production build.
- `npm run dev`: run Vite dev server.
- `npm run preview`: preview the production build.

## Configuration

Backend configuration is loaded from `back-end/.env` when running the backend directly on the host. Start from the project root `.env.example` and never commit real credentials, tokens, API keys, or database passwords.

Key local storage settings for MinIO/S3-compatible integration:

- `S3_ENDPOINT_URL` (local default: `http://localhost:9000`)
- `S3_BUCKET`
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`

## Contributing

See [AGENTS.md](./AGENTS.md) for repository conventions, testing expectations, commit guidance, and security notes.
