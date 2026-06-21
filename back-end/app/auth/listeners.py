"""Listeners reacting to authentication domain events."""

from __future__ import annotations

from app.auth import service as auth_service
from app.auth.domain_events import RegistrationRequested
from app.core.event_bus import DomainEventBus, domain_event_bus


async def send_registration_email(event: RegistrationRequested) -> None:
    """Deliver the registration OTP email.

    Registered ``critical`` so a delivery failure propagates back through
    ``emit`` to the registration handler, which surfaces it as a 502 — preserving
    the pre-migration contract that no pending registration is stored when the
    email cannot be sent. Routing it through the bus means additional reactions
    (welcome flows, audit, analytics) can attach without editing the handler, and
    delivery can later be moved off the request path by spawning it instead.

    ``send_registration_otp`` is looked up on the module at call time so the test
    suite's monkeypatch of it remains effective.
    """
    auth_service.send_registration_otp(event.email, event.otp, event.settings)


def register_auth_event_listeners(bus: DomainEventBus = domain_event_bus) -> None:
    """Wire the auth listeners onto ``bus`` (idempotent)."""
    bus.subscribe(RegistrationRequested, send_registration_email, critical=True)
