# Repository Guidelines

## Project Structure & Module Organization

- `back-end/`: FastAPI service using SQLModel and Alembic. Application code lives in `back-end/app/`.
- `back-end/app/auth`, `users`, and `posts`: feature modules with `router.py`, `service.py`, `schemas.py`, and `models.py`.
- `back-end/app/core`: shared configuration, database, and security helpers.
- `back-end/alembic/versions`: database migrations.
- `back-end/tests`: backend tests.
- `front-end/`: Next.js app. Route files and global styles live under `front-end/src/app/`; static assets are in `front-end/public/`.

## Build, Test, and Development Commands

Run commands from the relevant app directory.

Backend:

- `uv sync`: install Python dependencies.
- `uv run fastapi dev app/main.py`: run the API locally in development mode.
- `uv run pytest`: run backend tests.
- `uv run alembic upgrade head`: apply database migrations.
- `uv run alembic revision --autogenerate -m "message"`: create a migration after model changes.

Frontend:

- `npm install`: install Node dependencies.
- `npm run dev`: start the Next.js development server.
- `npm run build`: build the production app.
- `npm run start`: serve a production build.
- `npm run lint`: run ESLint.

## Coding Style & Naming Conventions

Backend code is grouped by feature. Keep endpoints in `router.py`, business logic in `service.py`, request/response models in `schemas.py`, and database models in `models.py`. Use snake_case for Python files, functions, and variables; use PascalCase for model and schema classes.

Frontend code uses TypeScript and React conventions. Use PascalCase for components, camelCase for variables and functions, and keep route files inside `src/app`. Follow the existing ESLint and Next.js configuration.

## Testing Guidelines

Backend tests use `pytest`; place them under `back-end/tests` and name files `test_*.py`. Prefer focused tests for service behavior, dependencies, and API routes.

There is no frontend test runner configured yet. For frontend changes, at minimum run `npm run lint` and `npm run build`.

## Commit & Pull Request Guidelines

The Git history uses short, imperative-style messages such as `Update the project structure`. Keep commits concise and scoped to one change.

Pull requests should include a summary of what changed, test or lint results, and any database migration notes. Include screenshots for visible frontend changes and link related issues when available.

## Security & Configuration Tips

Use `back-end/.env.example` as the local configuration template. Do not commit real `.env` values, credentials, tokens, or database URLs. For authentication, password, or migration changes, include verification notes in the pull request.
