from __future__ import annotations

from typing import Any

from app.billing.polar_client import PolarAPIError


class FakePolarClient:
    """In-memory stand-in for ``PolarClient`` used across billing tests.

    Every outbound Polar call in ``billing/service.py`` goes through a
    ``PolarClient``-shaped object, so tests never hit the real sandbox API.
    """

    def __init__(self, *, fail_ingest: bool = False) -> None:
        self.fail_ingest = fail_ingest
        self.created_customers: list[dict[str, Any]] = []
        self.checkout_calls: list[dict[str, Any]] = []
        self.customer_session_calls: list[dict[str, Any]] = []
        self.ingested_events: list[dict[str, Any]] = []
        self._next_customer_id = 1

    async def create_customer(self, *, email: str, external_id: str) -> dict[str, Any]:
        customer_id = f"cus_{self._next_customer_id}"
        self._next_customer_id += 1
        self.created_customers.append({"email": email, "external_id": external_id})
        return {"id": customer_id}

    async def create_checkout_session(
        self, *, product_id: str, customer_external_id: str, success_url: str
    ) -> dict[str, Any]:
        self.checkout_calls.append(
            {
                "product_id": product_id,
                "customer_external_id": customer_external_id,
                "success_url": success_url,
            }
        )
        return {"url": "https://sandbox.polar.sh/checkout/fake"}

    async def create_customer_session(self, *, customer_id: str) -> dict[str, Any]:
        self.customer_session_calls.append({"customer_id": customer_id})
        return {"customer_portal_url": "https://sandbox.polar.sh/portal/fake"}

    async def ingest_events(self, events: list[dict[str, Any]]) -> dict[str, Any]:
        if self.fail_ingest:
            raise PolarAPIError("simulated Polar outage")
        self.ingested_events.extend(events)
        return {"inserted": len(events)}
