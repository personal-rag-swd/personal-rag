# Implementation Plan: Admin Dashboard

## Overview

Add an admin dashboard to Aviary covering four capability areas:

1. **Overview metrics** — stat cards + usage chart: total/active users, notebooks, documents by status, LLM tokens consumed over time.
2. **User management** — paginated, searchable user table; change role, activate/deactivate; view a user's subscription tier and token usage.
3. **Ingestion monitoring** — recent/failed `NotebookDocument` feed so admins can spot stuck or failed RAG indexing.
4. **Billing overview** — subscription breakdown across users from `BillingCustomer` records.

**Non-goals (for now):** audit logging, an admin-creation flow (admins are promoted by setting `role: "admin"` directly, e.g. in Mongo or via another admin once user management ships), impersonation, and content moderation of notebook data.

### What already exists

- RBAC primitives: `User.role` is a plain string (`"user"` / `"admin"`) — `back-end/app/users/models.py`. `require_role("admin")` in `back-end/app/users/dependencies.py` checks the `role` claim baked into the JWT by `create_access_token` (`app/core/security.py`).
- Exactly one admin endpoint today: `GET /api/v1/users/` in `back-end/app/users/router.py`.
- Frontend: `useAuth().user` already carries `role: string` (`front-end/src/features/auth/store/auth-store.ts`). No role-based routing exists yet.
- All needed UI primitives exist in `front-end/src/components/ui/` (`table`, `pagination`, `card`, `chart` — a shadcn Recharts wrapper, recharts ^3.8 is installed — `badge`, `dialog`, `alert-dialog`, `dropdown-menu`, `tabs`, `select`, `skeleton`). `@tanstack/react-table` is **not yet installed** — add it and build tables with the shadcn data-table pattern (TanStack Table headless core rendered through `table.tsx`).

### Known caveat: JWT role claim

`require_role` trusts the JWT's `role` claim and does not re-read the DB, so a demoted admin keeps access until their access token expires. Acceptable for read endpoints given the short access-token TTL; for the **mutating** endpoint (`PATCH /admin/users/{id}`), add a live check: depend on `get_current_user` and raise `ForbiddenError` if `current_user.role != "admin"`.

---

## Phase 1 — Backend: new `app/admin/` module

Create `back-end/app/admin/` with `__init__.py`, `router.py`, `schemas.py`, `service.py`, following the existing feature-module pattern (see `app/billing/` and `app/users/` for reference). No new Beanie `Document` models are needed, so **no `init_beanie` changes**.

### Conventions that must be respected (from CLAUDE.md)

- Dict-based Mongo queries only (`{"field": value}`), never `Eq(Model.field, ...)`.
- Id lookups use `{"_id": value}`.
- Keep the router thin; aggregation logic lives in `service.py`.

### Endpoints (all under `/api/v1/admin`, all guarded by `Depends(require_role("admin"))`)

| Endpoint | Purpose |
|---|---|
| `GET /admin/stats` | Overview counts |
| `GET /admin/usage/daily?days=30` | Token usage timeseries |
| `GET /admin/users?page=&page_size=&search=` | Paginated user list |
| `PATCH /admin/users/{user_id}` | Update role / is_active |
| `GET /admin/users/{user_id}/usage` | Per-user usage drill-down |
| `GET /admin/documents?status=&page=&page_size=` | Ingestion monitoring feed |
| `GET /admin/billing/summary` | Subscription breakdown |

Details:

- **`GET /admin/stats`** → `AdminStatsResponse`:
  - `total_users`, `active_users` (`is_active: true`) via `User.count()` / `count_documents`.
  - `total_notebooks` via `Notebook.count()`.
  - `documents_by_status`: `$group` on `NotebookDocument.status` (`pending/uploaded/processing/indexed/failed`).
  - `reports_by_status`: `$group` on `NotebookReport.status`.
  - `tokens_this_month`: `$match` `created_at >= start of current calendar month` + `$sum: "$quantity"` on `UsageEventLog` (collection `billing_usage_event_logs`, model in `app/billing/models.py`).
  - `active_subscriptions`: `count_documents` on `BillingCustomer` with `subscription_status in ["active", "trialing"]`.
- **`GET /admin/usage/daily?days=30`** → list of `{date, tokens}`: aggregation on `UsageEventLog` — `$match` on `created_at >= now - days`, `$group` by `$dateTrunc: {date: "$created_at", unit: "day"}`, `$sum: "$quantity"`, `$sort` ascending. Clamp `days` to 1–365.
- **`GET /admin/users`** → paginated `AdminUserListResponse {items, total, page, page_size}`:
  - Filter: case-insensitive regex on `email` when `search` given (`{"email": {"$regex": re.escape(search), "$options": "i"}}`).
  - Sort `created_at` desc; `skip/limit` pagination (`page_size` clamped, default 20, max 100).
  - Enrich each row with subscription info + current-period token usage: **batch** lookups — one `BillingCustomer.find({"user_id": {"$in": [...]}})` and one `UsageAllowance` query for the page's user ids, then merge in Python. No N+1 queries.
  - Row schema `AdminUserRead`: `id, email, role, is_active, created_at, subscription_status, product_id, tokens_used_this_period`.
- **`PATCH /admin/users/{user_id}`** with body `AdminUserUpdate {role: str | None, is_active: bool | None}`:
  - Depend on `get_current_user` (live DB check) *and* verify `current_user.role == "admin"`.
  - 404 (`UserNotFoundError`) if no user with that id (`User.find_one({"_id": user_id})`).
  - **Self-protection**: 403 if `user_id == current_user.id` and the change demotes from admin or deactivates — an admin cannot lock themselves out.
  - Validate `role` against `{"user", "admin"}` (422 otherwise).
  - Update `updated_at`; return `AdminUserRead`.
- **`GET /admin/users/{user_id}/usage`** — reuse the existing `get_usage_summary(user_id, settings)` from `app/billing/service/queries.py` (already returns `UsageSummaryResponse` combining period/session/weekly usage + allowances + tier). 404 for unknown user.
- **`GET /admin/documents`** → paginated recent `NotebookDocument`s: `id, filename, content_type, size, status, error_message, notebook_id, user_id, created_at, updated_at`; optional `status` filter; sorted `created_at` desc. Do **not** include `content` or chunk embeddings in the response.
- **`GET /admin/billing/summary`** → `$group` `BillingCustomer` by `subscription_status` and by `product_id`; return `{by_status: {...}, by_product: {...}, total_customers}`.

### Registration (both places, per CLAUDE.md)

- `back-end/app/main.py`: `app.include_router(admin_router, prefix=API_V1_PREFIX)` alongside the existing five routers.
- `back-end/tests/conftest.py` `make_test_app()`: mirror the same `include_router` line.

## Phase 2 — Backend: tests (`back-end/tests/test_admin.py`)

Follow `tests/test_users.py` patterns: `pytestmark = pytest.mark.anyio`, class-grouped tests, helpers from `tests.conftest` (`make_user` / `create_user(role="admin")`, `auth_headers(user, settings)`, `create_notebook`). Because `auth_headers` bakes the user's role into the JWT, `create_user(role="admin")` is sufficient for the guard.

Cover per endpoint:
- **Auth matrix**: admin → 200, non-admin → 403, no token → 401.
- **`/admin/stats`**: seed users/notebooks/documents with mixed statuses + a few `UsageEventLog` docs; assert exact counts and token sum.
- **`/admin/usage/daily`**: seed `UsageEventLog`s across distinct days (construct `created_at` explicitly); assert grouping and sums.
- **`/admin/users`**: pagination math (`total`, page boundaries), email search, enrichment fields present when a `BillingCustomer` exists.
- **`PATCH /admin/users/{id}`**: role change persists; deactivate persists; self-demotion → 403; self-deactivate → 403; unknown id → 404; bad role → 422.
- **`/admin/documents`**: status filter (`failed` only), sort order, no `content` field leaked.
- **`/admin/billing/summary`**: seed `BillingCustomer`s across statuses; assert grouping.

Notes: tests hit real MongoDB (`personal-rag-test`) — no LLM stubbing needed here (no LLM calls in this feature). Seeding `UsageEventLog`/`BillingCustomer` directly via `.insert()` does **not** touch Polar; do not call billing service provisioning functions in these tests.

## Phase 3 — Frontend: routing, guard, layout

In `front-end/src/routes.tsx`:

- Add an `AdminRoute` guard mirroring `ProtectedRoute`, additionally redirecting non-admins:

  ```tsx
  function AdminRoute({ children }: { children: React.ReactNode }) {
    const { user, isAuthenticated, isLoading } = useAuth()
    if (isLoading) return <FullPageSpinner />
    if (!isAuthenticated) return <Navigate to="/login" replace />
    if (user?.role !== "admin") return <Navigate to="/dashboard" replace />
    return <>{children}</>
  }
  ```

- Add an `AdminLayout` cloned from the existing `DashboardLayout` shell (`SidebarProvider` → `AppSidebar variant="inset"` → `SidebarInset` → `SiteHeader` + content), rendering a lazy-loaded `AdminPage`.
- Route: `<Route path="/admin" element={<AdminRoute><AdminLayout /></AdminRoute>} />`.

In `front-end/src/features/dashboard/components/app-sidebar.tsx`: add an "Admin" nav item (e.g. `Shield` icon from lucide-react, url `/admin`) rendered only when `useAuth().user?.role === "admin"`.

## Phase 4 — Frontend: `features/admin/`

Create `front-end/src/features/admin/{api.ts, types.ts, components/}` following the conventions in `features/notebooks/api.ts` (snake_case `XApiPayload` types + `mapX()` mappers to camelCase domain types, `apiFetch` from `lib/api-client.ts`, array query keys).

**Tables use TanStack Table + shadcn**: `npm install @tanstack/react-table`, then add a reusable `front-end/src/components/ui/data-table.tsx` following the shadcn data-table pattern — `useReactTable` with column defs (`ColumnDef<T>[]`), rendered through the existing `table.tsx` primitives via `flexRender`, with sorting and column visibility handled client-side. Pagination and search stay **server-side** (manual): set `manualPagination: true`, `pageCount` from the API's `total`, and drive `pagination`/search state from the query hooks — do not fetch all rows client-side.

**`api.ts` hooks** (query keys namespaced under `["admin", ...]`):
- `useAdminStatsQuery` → `GET /api/v1/admin/stats`
- `useAdminDailyUsageQuery(days)` → `GET /api/v1/admin/usage/daily`
- `useAdminUsersQuery({ page, pageSize, search })` → `GET /api/v1/admin/users` (use `placeholderData: keepPreviousData` for smooth pagination)
- `useUpdateUserMutation` → `PATCH /api/v1/admin/users/{id}`; `onSuccess` invalidates `["admin", "users"]` and `["admin", "stats"]`
- `useAdminUserUsageQuery(userId)` → `GET /api/v1/admin/users/{id}/usage` (enabled only when a user is selected)
- `useAdminDocumentsQuery({ status, page })` → `GET /api/v1/admin/documents`
- `useAdminBillingSummaryQuery` → `GET /api/v1/admin/billing/summary`

**`components/admin-page.tsx`** — page with `tabs.tsx` (Overview / Users / Ingestion / Billing):

- **Overview tab** (`admin-overview.tsx`): grid of stat `card.tsx`s (users, active users, notebooks, indexed vs failed documents, tokens this month, active subscriptions) + a Recharts area/bar chart of daily token usage via `components/ui/chart.tsx` (`ChartContainer` + `ChartTooltip`).
- **Users tab** (`admin-users-table.tsx`): TanStack Table via the shared `data-table.tsx` with `ColumnDef<AdminUser>[]`; search `input.tsx` (debounced, server-side) + server-side pagination (`manualPagination`); `badge.tsx` for role, active state, and subscription tier; a row-actions column rendering `dropdown-menu.tsx` (Promote/Demote, Activate/Deactivate — each behind an `alert-dialog.tsx` confirmation; disable the destructive actions on the current admin's own row); a "View usage" action opening a `dialog.tsx` fed by `useAdminUserUsageQuery`.
- **Ingestion tab** (`admin-documents-table.tsx`): TanStack Table via `data-table.tsx` with a status filter (`select.tsx`, server-side), status `badge.tsx` (color by status; `failed` destructive), truncated `error_message` with tooltip, filename/notebook/user columns, server-side pagination.
- **Billing tab** (`admin-billing-summary.tsx`): cards or a simple bar chart of customers by `subscription_status` and by product/tier.

Loading states via `skeleton.tsx`; mutation feedback via `sonner` toasts (existing pattern).

**`types.ts`**: `AdminStats`, `DailyUsagePoint`, `AdminUser`, `AdminUserPage`, `AdminDocument`, `BillingSummary` (camelCase).

Optional hardening: narrow the `role` field on the auth store's `User` interface from `string` to `"user" | "admin"`.

## Suggested implementation order

1. Backend `app/admin/` service + schemas + router; register in `main.py` and `tests/conftest.py`.
2. Backend tests (`tests/test_admin.py`) green.
3. Frontend `AdminRoute` + `AdminLayout` + `/admin` route + sidebar nav item; install `@tanstack/react-table` and add `components/ui/data-table.tsx`.
4. Overview tab (stats + chart).
5. Users tab (data table, search, pagination, mutations).
6. Ingestion tab.
7. Billing tab; polish (skeletons, empty states via `empty.tsx`).

## Verification

**Backend** (from `back-end/`, requires local MongoDB on 27017 and MinIO on 9000 with `minioadmin`/`minioadmin`):
- `uv run pytest tests/test_admin.py` — new suite.
- `uv run pytest --ignore=tests/billing` — full suite; `tests/billing` is excluded because it calls the live Polar sandbox and fails on a clean tree.
- `uv run ruff check && uv run ruff format --check`
- `npx pyright --pythonpath .venv/bin/python`

**Frontend** (from `front-end/`, no test runner):
- `npm run lint`
- `npm run typecheck`

**Manual end-to-end**:
1. Start the stack (`uv run fastapi dev app/main.py` + `npm run dev`, or `docker compose up --build`).
2. Promote a user: set `role: "admin"` on their `users` document in Mongo, then log in fresh (the role claim is baked into the JWT at login).
3. Visit `/admin`: verify all four tabs render with real data; change another user's role and confirm it persists; verify the self-demotion guard.
4. As a non-admin: confirm `/admin` redirects to `/dashboard` and direct API calls to `/api/v1/admin/*` return 403.
