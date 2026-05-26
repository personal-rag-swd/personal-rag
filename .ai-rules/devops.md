# AI DevOps Rules & Conventions

To maintain a clean and trace-friendly repository history, all Git operations (branching, commits, and pull requests) must comply with these guidelines.

---

## 🌿 1. Branch Naming Convention

Branches must follow the pattern:
```text
<type>/<short-description>
```
* **Case**: Always use **kebab-case** or **snake-case** (lowercase letters only).
* **Types**:
  - `feat` or `feature`: New features (e.g., `feat/add-login-api`).
  - `fix` or `bugfix`: Bug fixes (e.g., `fix/token-expiration`).
  - `refactor`: Refactoring without functional changes (e.g., `refactor/clean-network-client`).
  - `chore`: Maintenance tasks (e.g., `chore/upgrade-dependencies`).
  - `docs`: Documentation changes (e.g., `docs/update-architecture-doc`).

---

## 💬 2. Commit Message Convention (Conventional Commits)

Commit messages must follow the standard Conventional Commits format:
```text
<type>(<scope>): <short summary>

[optional body]
```
* **Title constraints**: The first line must be **72 characters or less**.
* **Scope**: Specify the target module (e.g., `auth`, `users`, `posts`, `core`, `router`).

### Allowed Types:
* `feat`: New feature.
* `fix`: Bug fix.
* `docs`: Documentation changes.
* `style`: Code style changes (formatting, spacing) without logic changes.
* `refactor`: Reorganizing code without adding features or fixing bugs.
* `test`: Adding or modifying tests.
* `chore`: Build system, CI/CD, or dependency updates.

---

## 🔀 3. Pull Request (PR) Policy

* **Target Branch**: Open PRs targeting `develop` or the current release branch. Avoid PRing directly into `main` unless it is a hotfix.
* **PR Title Format**: `[Type][Scope] Short description` (e.g., `[Feature][Auth] Add JWT validation`).
* **PR Checklist**:
  - [ ] Code has been successfully formatted and statically analyzed.
  - [ ] All unit/integration tests pass.
  - [ ] Documentation has been updated if structural changes were introduced.
