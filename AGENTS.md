# Repository Guidelines

## Project Structure & Module Organization

This repository contains a FastAPI backend and a Vite React frontend.

- `back-end/app/`: API code grouped by feature (`auth`, `users`, `file`, `notebooks`) plus `core/`.
- `back-end/tests/`: pytest coverage for auth, RBAC, files, reports, notebooks, and chat.
- `back-end/alembic/`: (deleted) — migrated from PostgreSQL to MongoDB.
- `front-end/src/`: React code. Shared UI is in `components/ui/`, feature API/types in `features/`, and app wiring in `App.tsx` and `routes.tsx`.
- `front-end/public/` and `front-end/src/assets/`: static assets.
- `front-end-old/`: legacy Next.js code; avoid changing it unless the task explicitly targets it.

## Build, Test, and Development Commands

Run backend commands from `back-end/`:

- `uv sync`: install Python dependencies from `pyproject.toml` and `uv.lock`.
- `uv run fastapi dev app/main.py`: start the local API server.
- `uv run pytest`: run backend tests.
- `uv run ruff check`: lint backend code.
- `uv run ruff format`: format backend code.
- `uv run alembic upgrade head`: *(no longer available — project uses MongoDB)*.

Run frontend commands from `front-end/`:

- `npm install`: install Node dependencies.
- `npm run dev`: start the Vite dev server.
- `npm run build`: type-check and build production assets.
- `npm run lint`: run ESLint.
- `npm run format`: format TS/TSX files with Prettier.
- `npm run typecheck`: run TypeScript checks without building.

## Coding Style & Naming Conventions

Use feature-oriented backend modules: `models.py`, `schemas.py`, `service.py`, and `router.py`. Keep route handlers thin and business logic in services. Python uses 4-space indentation, type hints, and snake_case names.
Keep imports at the top of Python files; avoid inline imports in application code. Inline imports are acceptable in test files when needed for test isolation or fixtures.

Frontend code uses TypeScript, React 19, Tailwind CSS, and shadcn-style components. Use PascalCase components, camelCase functions and variables, and kebab-case reusable UI filenames.

## Testing Guidelines

Backend tests use pytest and are discovered under `back-end/tests/` as `test_*.py`. Add focused tests for changed behavior, especially auth, permissions, models, and callbacks. The frontend has linting and type checks but no dedicated test runner; run `npm run lint` and `npm run typecheck` for UI changes.

## Commit & Pull Request Guidelines

Recent commits use short imperative summaries, such as `Add API v1 prefix`. Keep the first line specific and under about 72 characters.

Pull requests should include a concise description, test results, linked issues when applicable, and screenshots for visible UI changes. Note migrations, new environment variables, and setup steps.

## Security & Configuration Tips

Start backend configuration from `back-end/.env.example`. Never commit secrets, database URLs, JWT keys, email tokens, or object storage credentials. Keep caches and build outputs out of version control.

Production compose requires these variables (see `docker-compose.prod.yml`):

- `MONGODB_URL`
- `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD`
- `MINIO_BROWSER_REDIRECT_URL`, `MINIO_SERVER_URL`
- `JWT_SECRET_KEY`
- `CORS_ORIGINS`
- `S3_PUBLIC_ENDPOINT_URL`
- `VITE_API_URL`

### MongoDB & Beanie Notes

The project uses **MongoDB** with **Beanie 2.1.0** as the ODM. Key patterns:
- Always use **dict-based queries** (`{"field": value}`), never `Eq(Model.field, value)` — Pydantic v2 metaclass blocks class-level field access.
- For `id` lookups, use `{"_id": value}`, NOT `{"id": value}` — Beanie maps Python `id` to MongoDB `_id`.
- Atlas `$vectorSearch` uses `queryText` (server-side embeddings), not `queryVector`.
- Tests use `mongomock-motor` — patch `list_collection_names` to drop `authorizedCollections` kwarg for compatibility.
