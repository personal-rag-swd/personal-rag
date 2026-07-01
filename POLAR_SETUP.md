# Polar.sh Billing — Setup Checklist

Tracks what's already implemented (code-complete, tested) vs. what still needs
to happen on the Polar.sh side before the billing feature is fully live. See
`back-end/app/billing/` for the implementation.

**Scope**: billing covers **AI (LLM token) usage only** — chat and report
generation. Document ingestion is not billed and has no gating. There are two
paid tiers, both **fixed recurring prices** with a hard token cap enforced by
our own code, not usage-based/metered billing:

| Tier | Price | Token cap/month |
|---|---|---|
| Free | $0 | 50,000 |
| Pro | $20/mo | 5,000,000 |
| Max | $100/mo | 35,000,000 |

Every tier is a hard cap — once a user (free, Pro, or Max) exhausts their
allowance, chat/report generation is blocked until the next period or an
upgrade. There is no "unlimited" tier.

## Status

Code is merged and working **without** any Polar credentials configured:
- `/api/v1/billing/checkout` and `/api/v1/billing/portal` return `503` until
  `POLAR_API_KEY` + the relevant tier's product id
  (`POLAR_PRO_PRODUCT_ID`/`POLAR_MAX_PRODUCT_ID`) are set
  (`_require_billing_configured` in `app/billing/router.py`).
- The background usage-emission task (`app/billing/tasks.py`) no-ops (logs
  once, returns) when `POLAR_API_KEY` is empty — it never loops or errors.
- `/api/v1/billing/usage` and free-tier LLM-token quota gating (chat, report
  generation) work fully today against local Mongo, independent of Polar.
- Backend tests cover the billing module against real Mongo with a fake
  Polar client (`tests/billing/`).

The two products (Pro, Max) already exist on the Polar sandbox org — IDs are
in `.env` (root, gitignored) and the gitignored Dokploy handoff doc, not
here. Still needed: the Meter (tracking-only) and re-verifying the webhook
endpoint against the actual production domain (see
`.env.dokploy-billing-handoff.md` for that status).

`POLAR_API_KEY`, `POLAR_ORGANIZATION_ID`, and `POLAR_WEBHOOK_SECRET` are
already in `.env` (root) — verified:
- `POLAR_API_KEY`: live `GET /v1/products/` → `200`.
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
### 3. Create the two Products (fixed recurring price) — ✅ done, IDs in `.env`

Do **not** attach a metered price to these products — they're plain fixed
subscriptions. The token cap per tier (5,000,000 for Pro, 35,000,000 for
Max) is enforced by our own `UsageAllowance` gating once the webhook tells us
which product a customer subscribed to.

### 4. Create one Meter (tracking only — set its price to $0/unit)

Dashboard → **Meters** → New meter:

| Meter | Event name to filter on | Aggregation |
|---|---|---|
| LLM token usage | `llm_usage` | sum of `metadata.quantity` |

This event name is hardcoded as `_METER_EVENT_NAME` in
`app/billing/service.py` and is what `emit_pending_usage_events_to_polar`
sends for every batch of token-usage events. This meter is for
tracking/audit visibility on the Polar dashboard only — it is **not** the
billing mechanism, so if you attach a price component to it, set it to
**$0/unit**. Actual billing is the two fixed-price products above, and quota
enforcement (the hard token cap) is done entirely by our own code.

→ give me the meter id as `POLAR_LLM_TOKENS_METER_ID`

### 5. Register a webhook endpoint — ✅ done, added to `.env`

Registered against `POST /api/v1/billing/webhooks/polar` behind a tunnel,
secret verified end-to-end (see Status above). **Needs re-registering
against the real production backend domain** before going live there — see
`.env.dokploy-billing-handoff.md`.

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
POLAR_PRO_PRODUCT_ID=
POLAR_MAX_PRODUCT_ID=
POLAR_LLM_TOKENS_METER_ID=
POLAR_SUCCESS_URL=http://localhost:5173/settings/billing?checkout=success
```

`POLAR_LLM_TOKENS_METER_ID` / `POLAR_ORGANIZATION_ID` aren't read by any code
path today (the meter/event name is a hardcoded string that must match what
you configure on the meter in step 4) — listed here so everything's in one
place if we later add server-side validation.

## How to verify once configured

1. `uv run fastapi dev app/main.py` with the env vars set.
2. Log in on the frontend, go to `/settings/billing`, click **Upgrade to
   Pro** (or Max) → should redirect to a real Polar sandbox checkout page
   for that product's $20 (or $100) price (not a 503).
3. Complete checkout with Polar's test card flow.
4. Confirm the webhook fired: check `BillingCustomer.subscription_status`
   flips to `active` **and** `product_id` is set to the product you
   subscribed to (Mongo `billing_customers` collection).
5. Confirm `/api/v1/billing/usage` now reports the tier-specific allowance
   (5,000,000 for Pro, 35,000,000 for Max) instead of the free-tier 50,000.
6. Chat / generate a report a few times, then check Polar's sandbox
   dashboard → Meters — the value should increase within
   `POLAR_USAGE_EMIT_INTERVAL_SECONDS` (default 60s) of usage happening
   (tracking only, doesn't affect the bill).
7. Click **Manage billing** on `/settings/billing` → should redirect to
   Polar's hosted customer portal.

## Open items once sandbox is live

- Confirm the meter event name / metadata shape match exactly (Polar meter
  filters are exact-match on event name).
- Decide production cutover values (separate org, product, meter, webhook
  endpoint on the production domain) — same checklist, repeated with
  `POLAR_ENVIRONMENT=production`.
