# AI Coding Conventions & Best Practices

All code written in this project must adhere to the architectural boundaries and coding principles below.

---

## 🐍 1. Backend (FastAPI, SQLModel, Alembic) - STRICTLY ENFORCED

The backend follows a **Feature-Grouped Architecture** (e.g., `auth`, `users`, `posts` under `back-end/app/`). You must strictly enforce layer isolation:

1. **Feature Module Structure**:
   - `router.py`: API route definitions. Endpoints must NOT contain database queries or complex business logic. They should only validate requests (via Pydantic schemas), call services, and return responses.
   - `service.py`: Business logic belongs strictly in this file. Services process inputs, orchestrate repositories/database operations, and raise appropriate HTTP exceptions.
   - `models.py`: SQLModel database models representing tables.
   - `schemas.py`: Pydantic models for request and response validation.
   - `dependencies.py`: Feature-specific helper dependencies.

2. **Dependency Injection**:
   - Always inject database sessions (`Session`), app configuration (`Settings`), and authentication states (`current_user`) using FastAPI's `Depends`.
   - Example:
     ```python
     from typing import Annotated
     from fastapi import Depends
     from sqlmodel import Session
     from app.core.database import get_session

     def my_service_function(session: Annotated[Session, Depends(get_session)]):
         ...
     ```

3. **Repository Pattern**:
   - Database operations (CRUD, queries, complex filtering) should be separated into a repository layer or data access functions (e.g., in a `repository.py` or helper functions in the module) to isolate SQLModel/SQLAlchemy query logic from high-level business logic.
   - Do not query the database directly inside routers.

4. **Exception Handling & Bypass Rule**:
   - **CRITICAL**: If you encounter an exceptional case or complex pattern that cannot adhere to the DI/Repository/Service boundaries, **you must stop and report it immediately to the user** for review and assessment. Bypassing these rules is NOT allowed without explicit user consent.

5. **Naming Conventions**:
   - Use `snake_case` for Python filenames, directories, functions, and variables.
   - Use `PascalCase` for SQLModel database models, schemas, and classes.

---

## ⚛️ 2. Frontend (Next.js, TypeScript, React) - RECOMMENDED ONLY

The frontend rules serve as guidelines and recommendations rather than strict constraints:

1. **Conventions**:
   - Use React and TypeScript conventions.
   - Use `PascalCase` for component files and components (e.g., `UserProfile.tsx`).
   - Use `camelCase` for functions, hooks, and variables.
   - Route files and layouts belong inside `src/app/` using the Next.js App Router structure.

2. **Structure Recommendations**:
   - Focus on reusable components and clean modular styling.
   - Share hooks and utilities when appropriate.
   - Keep page files focused on layout and composition; delegate UI state logic to hooks or state managers.
