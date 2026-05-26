# AI Agent SDLC Workflow Rules

This document establishes the mandatory Software Development Life Cycle (SDLC) workflow that **all AI coding agents** (including Antigravity, Claude, Codex, Gemini, Copilot, etc.) must follow when working on this project.

---

## 🚫 1. No Immediate Code Execution
- **RULE**: Never start making code modifications or running modifying commands immediately upon receiving a request.
- **REASON**: Early coding without planning leads to architectural drift, compilation failures, and regression bugs.

---

## 📝 2. Mandatory Planning & Brainstorming
Before writing code, you must create or update an **Implementation Plan** (either in the planning artifact or as a planning section in chat):
1. **Brainstorming**: Analyze the requirement, identifying potential technical hurdles, dependencies, and architectural impacts.
2. **Multiple Approaches**: Define and present **at least two (2) distinct approaches** to solve the problem.
3. **Trade-off Analysis**: For each approach, detail:
   - **Pros**: Benefits, performance improvements, simplicity.
   - **Cons**: Over-engineering risks, boilerplate code, performance costs.
   - **Trade-offs**: Explain why one is preferred over the other for this specific project.

---

## ❓ 3. User Alignment Questions
- **RULE**: Within your proposed plan, you **must ask the user at least three (3) specific, open-ended questions** to clarify requirements, design preferences, or edge cases.
- **EXECUTION**: Wait for the user's explicit response and approval of the plan before executing any changes.

---

## 🧪 4. Code Correctness & Verification
Before outputting code or declaring a task complete, you must verify the implementation:
1. **Compilation**: Code must compile and build without errors.
2. **Backend Verification**: Run `uv run pytest` in the `back-end/` directory. All tests must pass.
3. **Frontend Verification**: Run `npm run lint` and `npm run build` in the `front-end/` directory. Zero linter warnings/errors and successful builds are expected.
4. **Action on Failure**: If verification fails, you must analyze the errors, fix them, and re-run verification. You are **not allowed** to finish the task with outstanding warnings or failures.
