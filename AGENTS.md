# Repository Guidelines

## Project Structure & Module Organization

This repository contains a FastAPI backend and a Vite React frontend.

- `back-end/app/`: FastAPI application code.
  - `auth/`: Routers, schemas, models, and services for authentication, signup/login, and token rotation.
  - `users/`: Users schema and CRUD routes.
  - `file/`: File upload router, ingestion helper, metadata schemas, and services integrated with MinIO/S3.
  - `notebooks/`: Core notebook features, prompting, workflows, schemas, and models.
    - `routes/`: Sub-routers split by behavior: `chat.py`, `crud.py`, `documents.py`, `events.py`, and `reports.py`.
    - `agent/`: AI Agent logic, workflow orchestration, and prompt execution.
    - `memory/`: Memory context providers for chat.
    - `tools/`: Extensible agent tools.
    - `prompt/`: System instruction sets.
    - `consumer.py`: RabbitMQ queue/worker consumer for processing document ingestion/chunking/indexing.
    - `report_service.py`: Background PDF report compiler and task tracking/recovery.
  - `core/`: Global settings (`config.py`), database engines (`database.py`), S3 storage adapters (`s3.py`), token verification and security helpers (`security.py`), and Logfire telemetry (`telemetry.py`).
  - `utils/`: Common helpers.
  - `main.py`: Main app entry point setting up logging, lifespan (background consumers/report recovery), routing, and Scalar documentation.
- `back-end/tests/`: pytest coverage suite. Main files include:
  - `test_auth_rotation.py`, `test_user_rbac.py`: Credentials and role-based access.
  - `test_file.py`: S3 presigned URLs, metadata, and files CRUD.
  - `test_notebooks.py`, `test_notebook_chat.py`, `test_notebook_prompt.py`, `test_notebook_search_and_chunking.py`, `test_notebooks_reports_background.py`: Notebook management, chat providers, prompts, chunking, and background PDF compiler tasks.
  - `test_rabbitmq_consumer.py`: Message consumer broker logic.
  - `test_chat_provider_factory.py`, `test_embedding_adapters.py`: LLM provider/adapter integration.
- `back-end/alembic/`: Database migration environment and generated version scripts.
- `front-end/src/`: React 19 Vite application code:
  - `components/`: Core components, including `ui/` (shadcn-based layout components), `assistant-ui/` (chat interface components), and custom `branding/` branding.
  - `features/`: Modular frontend features: `auth/`, `dashboard/`, `files/`, and `notebooks/`.
  - `hooks/`: Reusable custom React hooks.
  - `lib/`: Shared utility libraries (e.g. `cn` helper for tailwind merge).
  - `App.tsx` and `routes.tsx`: Main routing and layout declaration.
  - `index.css`: Styling baseline and Tailwind CSS v4 directives.
- `front-end/public/` and `front-end/src/assets/`: Static client-side assets.

## Build, Test, and Development Commands

Run backend commands from `back-end/`:

- `uv sync`: install Python dependencies from `pyproject.toml` and `uv.lock`.
- `uv run fastapi dev app/main.py`: start the local API server in development mode.
- `./scripts/run_tests_postgres.sh`: spin up the pgvector test database container and execute backend test suite.
- `uv run pytest`: run backend tests (when DATABASE_URL is already pointing at a test DB).
- `uv run ruff check`: lint backend code.
- `uv run ruff format`: format backend code.
- `uv run alembic upgrade head`: apply database migrations.
- `uv run alembic revision --autogenerate -m "add feature"`: create a database migration.

Run frontend commands from `front-end/`:

- `npm install`: install Node dependencies.
- `npm run dev`: start the Vite dev server.
- `npm run build`: compile and build production assets.
- `npm run lint`: run ESLint checks.
- `npm run format`: format TS/TSX files with Prettier.
- `npm run typecheck`: run TypeScript compiler checks without building.

## Coding Style & Naming Conventions

Use feature-oriented backend modules: `models.py`, `schemas.py`, `service.py`, and `router.py`. Keep route handlers thin and business logic in services. Python uses 4-space indentation, type hints, and snake_case names.
Keep imports at the top of Python files; avoid inline imports in application code. Inline imports are acceptable in test files when needed for test isolation or fixtures.

Frontend code uses TypeScript, React 19, Tailwind CSS (v4 via Vite plugin), and shadcn-style components. Use PascalCase components, camelCase functions and variables, and kebab-case reusable UI filenames.

## Testing Guidelines

Backend tests use pytest and are discovered under `back-end/tests/` as `test_*.py`. Add focused tests for changed behavior, especially auth, permissions, models, and background task runners or message consumers. The frontend has linting and type checks but no dedicated test runner; run `npm run lint` and `npm run typecheck` for UI changes.

## Commit & Pull Request Guidelines

Recent commits use short imperative summaries, such as `Add API v1 prefix`. Keep the first line specific and under about 72 characters.

Pull requests should include a concise description, test results, linked issues when applicable, and screenshots for visible UI changes. Note migrations, new environment variables, and setup steps.

## Security & Configuration Tips

Start backend configuration from the root `.env.example`. Never commit secrets, database URLs, JWT keys, email tokens, or object storage credentials. Keep caches and build outputs out of version control.

Production compose requires these variables (see `docker-compose.prod.yml`):

- `POSTGRES_USER`, `POSTGRES_PASSWORD`
- `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD`
- `MINIO_BROWSER_REDIRECT_URL`, `MINIO_SERVER_URL`
- `JWT_SECRET_KEY`
- `CORS_ORIGINS`
- `S3_PUBLIC_ENDPOINT_URL`
- `VITE_API_URL`
