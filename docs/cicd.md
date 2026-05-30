# CI/CD Setup & Rollout Notes

This document provides a concise overview of the CI/CD workflows and Dependabot configuration implemented on the `chore/setup-cicd` branch.

## 1. Workflows

### PR CI Workflow (`.github/workflows/ci.yml`)
Runs on:
- Pull requests to any branch.
- Pushes to the `master` branch.

Jobs:
- **Backend CI**:
  - Leverages `astral-sh/setup-uv` with caching.
  - Installs the Python toolchain.
  - Runs `uv sync --locked`.
  - Runs `uv run ruff check .` for linting.
  - Runs `uv run pytest` for testing.
- **Frontend CI**:
  - Sets up Node.js 24.
  - Runs `npm ci` (with npm cache).
  - Runs `npm run lint`.
  - Runs `npm run typecheck`.
  - Runs `npm run build`.
- **Docker Smoke Build**:
  - Uses `docker/setup-buildx-action` and `docker/build-push-action`.
  - Runs a dry-run build (`push: false`) for both `back-end/Dockerfile` and `front-end/Dockerfile`.
  - Injects `VITE_API_URL=http://localhost:8000` to the frontend build as a smoke test default.

---

### Docker Publish Workflow (`.github/workflows/docker-publish.yml`)
Runs on:
- Pushes to the `master` branch.
- Manual trigger via `workflow_dispatch`.

Permissions:
- Uses least-privilege permissions (`contents: read`, `packages: write`).

Outputs:
- Builds and pushes backend/frontend images to GitHub Container Registry (GHCR).
- Image tags:
  - Long Git commit SHA (e.g. `ghcr.io/owner/personal-rag-backend:<commit_sha>`).
  - Git ref/branch name (e.g. `ghcr.io/owner/personal-rag-backend:master`).
  - `latest` tag when pushed directly to the `master` branch.

---

## 2. Environment Variables & Secrets Configuration

| Scope | Name | Type | Description |
|---|---|---|---|
| Repository Variables | `VITE_API_URL` | Variable | (Optional) The browser-facing API URL injected during the frontend build. Defaults to `http://localhost:8000` if not set. |
| GitHub Actions | `GITHUB_TOKEN` | Secret (Built-in) | Automatically provided by GitHub Actions runner, used to authenticate with GHCR. |

---

## 3. Dependabot Setup & Limitations

Dependabot is configured to check weekly for:
- GitHub Actions updates (`/` directory).
- Frontend package updates (`/front-end` directory).
- Backend package updates (`/back-end` directory) using the `pip` ecosystem.

> [!WARNING]
> **Dependabot `uv` Limitation**: Dependabot does not currently natively support automatically updating `uv.lock`. When Dependabot issues a PR to update `pyproject.toml`, developers or subsequent automation steps must run `uv lock --update` in `back-end/` to update `uv.lock` and commit the change to the PR before merging.

---

## 4. Rollout Steps

1. **Merge PR**: Merge the `chore/setup-cicd` branch into `master`.
2. **GHCR Permissions**:
   - Ensure the repository has permissions to write to packages. If the first run fails with a permission error, go to the Package Settings in GHCR and link the package to this repository, granting write permissions to the repository actions.
3. **Verify Builds**:
   - Verify the CI workflow runs and passes on the PR.
   - Run a manual dispatch of "Publish Docker Images" to verify publishing to GHCR.
