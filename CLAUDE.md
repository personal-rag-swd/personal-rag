# Claude Developer Rules & Commands

This file defines the commands and guidelines for working on the `personal-rag` project (FastAPI + Next.js).

---

## 🛠 Commands

Run commands from the relevant directory.

### 🐍 Backend Commands (under `back-end/`)
* **Get/Sync dependencies**: `uv sync`
* **Run local API (dev mode)**: `uv run fastapi dev app/main.py`
* **Run tests**: `uv run pytest`
* **Apply database migrations**: `uv run alembic upgrade head`
* **Generate a new migration**: `uv run alembic revision --autogenerate -m "message"`

### ⚛️ Frontend Commands (under `front-end/`)
* **Install dependencies**: `npm install`
* **Run Next.js dev server**: `npm run dev`
* **Build production application**: `npm run build`
* **Serve production build**: `npm run start`
* **Run ESLint checker**: `npm run lint`

---

## 📌 Development Workflow & Architectural Rules

You must follow the modular rules defined in the `.ai-rules/` directory:

1. **SDLC Planning & Questions**: You MUST plan first before making code edits. Compare at least 2 solutions with trade-offs and ask at least 3 clarifying questions.
   * Details in: [.ai-rules/sdlc_workflow.md](file:///.ai-rules/sdlc_workflow.md)
2. **Coding Standards**:
   * **Backend**: Strictly enforce dependency injection via FastAPI `Depends`, repository pattern, and business logic kept strictly in `service.py`. Report exceptions immediately for review.
   * **Frontend**: Recommended practices for React, TypeScript, and Next.js App Router.
   * Details in: [.ai-rules/coding_conventions.md](file:///.ai-rules/coding_conventions.md)
3. **DevOps & Branch/Commit Naming**: Use standard branch prefixes (`feature/`, `bugfix/`, `hotfix/`, etc.) and Conventional Commits format under 72 chars.
   * Details in: [.ai-rules/devops.md](file:///.ai-rules/devops.md)
