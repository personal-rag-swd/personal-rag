# Personal RAG

Personal RAG is a two-part application with a FastAPI backend and a Vite + React frontend. The backend provides authentication, user management, notebooks, and file services (presigned URLs plus RabbitMQ-driven notebook ingestion). The frontend delivers the application UI and client-side workflows.

## What This App Includes

- FastAPI API with feature-oriented modules (`auth`, `users`, `file`, `notebooks`)
- File upload flow with presigned URLs, MinIO object notifications, and in-app ingestion
- React 19 frontend with Tailwind CSS and shadcn/ui components
- Local dev stack with MongoDB, RabbitMQ, and MinIO

## How The App Is Organized

- Backend API lives under `back-end/app/` and exposes routes under `/api/v1`
- Scalar API docs are available at `GET /docs`
- Frontend lives under `front-end/` and talks to the API via `VITE_API_URL`
- Object storage uses MinIO locally; `ObjectCreated` events are forwarded to RabbitMQ and consumed inside the FastAPI app

## Repository Structure

```text
.
├── back-end/               # FastAPI, Beanie ODM (MongoDB), pytest
│   ├── app/                # API application code
│   │   ├── auth/           # Authentication flows
│   │   ├── users/          # User management
│   │   ├── file/           # File upload endpoints
│   │   ├── notebooks/      # Notebook endpoints
│   │   ├── core/           # Settings, DB, security
│   │   ├── middleware/     # Request middleware
│   │   └── utils/          # Shared helpers
│   ├── tests/              # Pytest suites
│   └── pyproject.toml      # Python dependencies and pytest config
├── front-end/              # Vite, React, TypeScript, Tailwind CSS
│   ├── src/                # Application source code
│   │   ├── components/     # Shared UI
│   │   │   └── ui/         # shadcn/ui components
│   │   ├── features/       # Feature API/types/state
│   │   ├── hooks/          # Shared hooks
│   │   ├── lib/            # Client utilities
│   │   ├── assets/         # Bundled assets
│   │   ├── routes.tsx      # App routes
│   │   └── App.tsx         # App shell
│   ├── public/             # Static assets
│   └── package.json        # Frontend scripts and dependencies
├── docker-compose.yml      # Full local dev stack (MongoDB, MinIO, RabbitMQ, backend, frontend)
├── docker-compose.prod.yml # Production compose stack
├── DOKPLOY_DEPLOYMENT.md   # Dokploy deployment notes
└── AGENTS.md               # Contributor guide
```

## Prerequisites

- Docker and Docker Compose for full-stack local dev
- Node.js and npm for frontend-only development
- `uv` for backend development (Python dependency manager)

## Local Development

The easiest way to run locally is Docker Compose. It brings up MongoDB, MinIO, RabbitMQ,
the FastAPI backend, and the Vite dev server in one command.

If you want to run the backend and frontend on your host machine instead, keep
MongoDB, RabbitMQ, and MinIO in Compose and start the services manually.

### Option A: Full Stack via Docker Compose (Recommended)

First-time setup:

```bash
cp .env.example .env
```

```bash
docker compose up --build
```

Service URLs:

- Frontend: `http://localhost:5173`
- Backend API: `http://localhost:8000`
- `GET /ping` for a health check
- `GET /docs` for Scalar API documentation
- API base path: `/api/v1`
- MinIO API: `http://localhost:9000`
- MinIO Console: `http://localhost:9001` (username/password: `minioadmin` / `minioadmin`)

The stack includes:

- MongoDB
- MinIO + RabbitMQ + `mc` bootstrap (bucket + AMQP event configuration)
- FastAPI backend in dev mode
- Vite frontend dev server

### Option B: Host-Run Backend + Frontend

If you prefer running the backend and frontend directly on your host, keep MongoDB/RabbitMQ/MinIO in Compose:

```bash
cp .env.example .env
docker compose up -d mongodb minio rabbitmq minio-mc

cd back-end
ln -sf ../.env .env
uv sync
uv run fastapi dev app/main.py

cd front-end
npm install
npm run dev
```

Once running, the frontend is at `http://localhost:5173` and the API is at
`http://localhost:8000`.

## Development Commands

Backend commands should be run from `back-end/`:

- `uv run pytest`: run backend tests.
- `uv run ruff check`: lint backend code.
- `uv run ruff format`: format backend code.
- (MongoDB models use Beanie ODM and automatically initialize collections on startup)

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

Production compose requirements (must be set when using `docker-compose.prod.yml`):

- `DATABASE_URL`
- `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD`
- `MINIO_BROWSER_REDIRECT_URL`, `MINIO_SERVER_URL`
- `JWT_SECRET_KEY`
- `CORS_ORIGINS`
- `S3_PUBLIC_ENDPOINT_URL`
- `VITE_API_URL`

Optional provider settings:

- `CHAT_PROVIDER` (defaults to `openrouter`)
- `OPENROUTER_API_KEY` or `GEMINI_API_KEY`
- `GEMINI_MODEL` (defaults to `gemini-2.5-flash`)

## Contributing

See [AGENTS.md](./AGENTS.md) for repository conventions, testing expectations, commit guidance, and security notes.
