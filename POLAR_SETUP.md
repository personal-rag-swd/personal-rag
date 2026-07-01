# Polar.sh Billing — Setup Checklist

Tracks what's already implemented (code-complete, tested) vs. what still needs
to happen on the Polar.sh side before the billing feature is fully live. See
`back-end/app/billing/` for the implementation.

**Scope**: billing is metered on **AI (LLM token) usage only** — chat and
report generation. Document ingestion is not billed and has no gating.

## Status

Code is merged and working **without** any Polar credentials configured:
- `/api/v1/billing/checkout` and `/api/v1/billing/portal` return `503` until
  `POLAR_API_KEY` + `POLAR_PRODUCT_ID` are set (`_require_billing_configured`
  in `app/billing/router.py`).
- The background usage-emission task (`app/billing/tasks.py`) no-ops (logs
  once, returns) when `POLAR_API_KEY` is empty — it never loops or errors.
- `/api/v1/billing/usage` and free-tier LLM-token quota gating (chat, report
  generation) work fully today against local Mongo, independent of Polar.
- 24 backend tests cover the billing module against real Mongo with a fake
  Polar client (`tests/billing/`); 116/116 total backend tests pass.

What's **not yet possible** without the values below: real checkout,
customer portal, and usage actually landing in Polar's meter/dashboard.

`POLAR_API_KEY`, `POLAR_ORGANIZATION_ID`, and `POLAR_WEBHOOK_SECRET` are
already in `.env` (root) — verified:
- `POLAR_API_KEY`: live `GET /v1/products/` → `200` (org has 0 products so
  far, expected — step 3 below not done yet).
- `POLAR_WEBHOOK_SECRET`: signs/verifies correctly end-to-end through
  `verify_webhook_signature`.

> **Local dev note**: `Settings` (`app/core/config.py`) loads `env_file=".env"`
> relative to the **process working directory**. Running
> `uv run fastapi dev app/main.py` from `back-end/` will *not* pick up the
> root `.env` — only `docker compose up` (which reads the root `.env` into
> each container) does today. If you want to run the backend standalone with
> `uv run` and have it pick up the root `.env`, either copy/symlink it to
> `back-end/.env`, or run `fastapi dev` with the working directory at the
> repo root. Pre-existing behavior, not something this billing work changed.

## What I need from you (Polar sandbox)

### 1. Create a sandbox organization — ✅ done
### 2. Create an Organization Access Token — ✅ done, added to `.env`, verified with a live `GET /v1/products/` call
### Note your Organization ID — ✅ done, added to `.env`

### 3. Create one Meter

Dashboard → **Meters** → New meter:

| Meter | Event name to filter on | Aggregation |
|---|---|---|
| LLM token usage | `llm_usage` | sum of `metadata.quantity` |

This event name is hardcoded as `_METER_EVENT_NAME` in
`app/billing/service.py` and is what `emit_pending_usage_events_to_polar`
sends for every batch of token-usage events.

→ give me the meter id as `POLAR_LLM_TOKENS_METER_ID`

### 4. Create a Product with a metered price

Dashboard → **Products** → New product (e.g. "Aviary Pro"). Add one price
component attached to the meter above (price-per-unit, e.g. per 1K tokens).
This is the single paid plan for the MVP — the free tier (fixed token
allowance per calendar month) is enforced entirely by our own
`UsageAllowance` gating, not by a Polar product.

→ give me the product id as `POLAR_PRODUCT_ID`

### 5. Register a webhook endpoint — ✅ done, added to `.env`

Already registered against `POST /api/v1/billing/webhooks/polar` behind a
tunnel, secret verified end-to-end (see Status above).

### 6. Success URL (optional, has a sensible default)
Where Polar redirects after a successful checkout. Defaults to
`http://localhost:5173/settings/billing?checkout=success` — override via
`POLAR_SUCCESS_URL` if your dev/staging frontend URL differs.

## Where these values go

Add to your `.env` (see `.env.example`, section `Billing (Polar.sh)`):

```
POLAR_API_KEY=
POLAR_WEBHOOK_SECRET=
POLAR_ENVIRONMENT=sandbox
POLAR_ORGANIZATION_ID=
POLAR_PRODUCT_ID=
POLAR_LLM_TOKENS_METER_ID=
POLAR_SUCCESS_URL=http://localhost:5173/settings/billing?checkout=success
```

`POLAR_LLM_TOKENS_METER_ID` / `POLAR_ORGANIZATION_ID` aren't read by any code
path today (the meter/event name is a hardcoded string that must match what
you configure on the meter in step 3) — listed here so everything's in one
place if we later add server-side validation.

## How to verify once configured

1. `uv run fastapi dev app/main.py` with the env vars set.
2. Log in on the frontend, go to `/settings/billing`, click **Upgrade for
   unlimited usage** → should redirect to a real Polar sandbox checkout page
   (not a 503).
3. Complete checkout with Polar's test card flow.
4. Confirm the webhook fired: check `BillingCustomer.subscription_status` in
   Mongo (`billing_customers` collection) flips to `active`.
5. Chat / generate a report a few times, then check Polar's sandbox
   dashboard → Meters — the value should increase within
   `POLAR_USAGE_EMIT_INTERVAL_SECONDS` (default 60s) of usage happening.
6. Click **Manage billing** on `/settings/billing` → should redirect to
   Polar's hosted customer portal.

## Open items once sandbox is live

- Confirm the meter event name / metadata shape match exactly (Polar meter
  filters are exact-match on event name).
- Decide production cutover values (separate org, product, meter, webhook
  endpoint on the production domain) — same checklist, repeated with
  `POLAR_ENVIRONMENT=production`.
