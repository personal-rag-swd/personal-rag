"""Central registration of in-process domain event listeners.

Imported by the FastAPI lifespan (and the test fixtures) so the event→listener
wiring lives in exactly one place and is easy to read at a glance. Registration
is idempotent, so calling it more than once is safe.
"""

from __future__ import annotations

from app.auth.listeners import register_auth_event_listeners
from app.core.event_bus import DomainEventBus, domain_event_bus
from app.notebooks.listeners import register_notebook_event_listeners


def register_default_event_listeners(bus: DomainEventBus = domain_event_bus) -> None:
    register_notebook_event_listeners(bus)
    register_auth_event_listeners(bus)
