"""Listeners reacting to authentication domain events."""

from __future__ import annotations

from app.auth import service as auth_service
from app.auth.domain_events import RegistrationRequested
from app.core.event_bus import DomainEventBus, domain_event_bus


async def send_registration_email(event: RegistrationRequested) -> None:
    try:
        auth_service.send_registration_otp(event.email, event.otp, event.settings)
    except Exception as e:
        import logging
        logger = logging.getLogger("app.auth")
        logger.warning(
            "Could not send registration email via Resend (RESEND_API_KEY may be missing). "
            "Local dev bypass OTP for %s is: %s",
            event.email,
            event.otp,
        )
        # In non-production, do not fail registration due to missing Resend API key
        import os
        if os.getenv("RESEND_API_KEY"):
            raise e


def register_auth_event_listeners(bus: DomainEventBus = domain_event_bus) -> None:
    """Wire the auth listeners onto ``bus`` (idempotent)."""
    bus.subscribe(RegistrationRequested, send_registration_email, critical=True)
