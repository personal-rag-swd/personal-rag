"""Thin wrapper around the Polar.sh REST API.

Centralizes every outbound Polar HTTP call behind one class so
``billing/service.py`` never talks to ``httpx`` directly. This is the single
mock boundary for tests (see ``tests/billing/``), mirroring how
``core/llm_provider.py`` centralizes LLM access.
"""

from __future__ import annotations

import logging
from typing import Any, Protocol

import httpx

from app.core.config import Settings

logger = logging.getLogger(__name__)


class PolarClientProtocol(Protocol):
    """Structural type satisfied by ``PolarClient`` and test fakes alike."""

    async def create_customer(
        self, *, email: str, external_id: str
    ) -> dict[str, Any]: ...

    async def create_checkout_session(
        self, *, product_id: str, customer_external_id: str, success_url: str
    ) -> dict[str, Any]: ...

    async def create_customer_session(self, *, customer_id: str) -> dict[str, Any]: ...

    async def ingest_events(self, events: list[dict[str, Any]]) -> dict[str, Any]: ...


_SANDBOX_BASE_URL = "https://sandbox-api.polar.sh"
_PRODUCTION_BASE_URL = "https://api.polar.sh"


class PolarAPIError(Exception):
    """Raised when Polar's API returns a non-2xx response."""


class PolarClient:
    def __init__(self, settings: Settings) -> None:
        base_url = (
            _PRODUCTION_BASE_URL
            if settings.polar_environment == "production"
            else _SANDBOX_BASE_URL
        )
        self._settings = settings
        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers={"Authorization": f"Bearer {settings.polar_api_key}"},
            timeout=15.0,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _request(
        self, method: str, path: str, *, json: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        response = await self._client.request(method, path, json=json)
        if response.is_error:
            logger.warning(
                "Polar API error: %s %s -> %s %s",
                method,
                path,
                response.status_code,
                response.text[:500],
            )
            raise PolarAPIError(
                f"Polar API {method} {path} failed: {response.status_code}"
            )
        return response.json()

    async def create_customer(self, *, email: str, external_id: str) -> dict[str, Any]:
        return await self._request(
            "POST",
            "/v1/customers/",
            json={"email": email, "external_id": external_id},
        )

    async def create_checkout_session(
        self,
        *,
        product_id: str,
        customer_external_id: str,
        success_url: str,
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            "/v1/checkouts/",
            json={
                "products": [product_id],
                "customer_external_id": customer_external_id,
                "success_url": success_url,
            },
        )

    async def create_customer_session(self, *, customer_id: str) -> dict[str, Any]:
        return await self._request(
            "POST",
            "/v1/customer-sessions/",
            json={"customer_id": customer_id},
        )

    async def ingest_events(self, events: list[dict[str, Any]]) -> dict[str, Any]:
        return await self._request(
            "POST",
            "/v1/events/ingest",
            json={"events": events},
        )


_client_cache: dict[str, PolarClient] = {}


def get_polar_client(settings: Settings) -> PolarClient:
    """Return a process-wide ``PolarClient`` (lazily constructed).

    Tests should monkeypatch this function (or pass an explicit ``client=``
    argument to the ``billing.service`` functions) to inject a fake client
    instead of hitting Polar's sandbox over the network.
    """
    if "default" not in _client_cache:
        _client_cache["default"] = PolarClient(settings)
    return _client_cache["default"]
