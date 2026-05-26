# Personal RAG

Personal RAG is a two-part application with a FastAPI backend and a Next.js frontend. The backend currently provides authentication and user routes, database migrations, JWT settings, and Scalar API documentation. The frontend is a Next.js app scaffolded under `front-end/`.

## Repository Structure

```text
.
├── back-end/          # FastAPI, SQLModel, Alembic, pytest
│   ├── app/           # API application code
│   ├── alembic/       # Database migration environment and versions
│   └── pyproject.toml # Python dependencies and pytest config
├── front-end/         # Next.js, React, TypeScript, Tailwind CSS
│   ├── src/app/       # App Router files and global styles
│   └── package.json   # Frontend scripts and dependencies
└── AGENTS.md          # Contributor guide
```

## Prerequisites

- Python 3.14 or newer
- `uv`
- Node.js and npm
- PostgreSQL database

## Backend Setup

```bash
cd back-end
cp .env.example .env
uv sync
uv run alembic upgrade head
uv run fastapi dev app/main.py
```

Update `back-end/.env` with your local database URL and secrets before running the API. The API exposes:

- `GET /ping` for a health check
- `GET /docs` for Scalar API documentation

## Frontend Setup

```bash
cd front-end
npm install
npm run dev
```

The development server starts the Next.js app locally. Use `npm run build` before deployment to verify the production build.

## Development Commands

Backend commands should be run from `back-end/`:

- `uv run pytest`: run backend tests.
- `uv run alembic revision --autogenerate -m "message"`: generate a migration from model changes.
- `uv run alembic upgrade head`: apply migrations.

Frontend commands should be run from `front-end/`:

- `npm run lint`: run ESLint.
- `npm run build`: create a production build.
- `npm run start`: serve a production build.

## Configuration

Backend configuration is loaded from `back-end/.env`. Start from `back-end/.env.example` and never commit real credentials, tokens, API keys, or database passwords.

Key settings include `DATABASE_URL`, `JWT_SECRET_KEY`, token expiration values, and optional Resend email configuration.

## Contributing

See [AGENTS.md](./AGENTS.md) for repository conventions, testing expectations, commit guidance, and security notes.
