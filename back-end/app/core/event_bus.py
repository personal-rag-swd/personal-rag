"""In-process domain event dispatcher (the control-plane event bus).

Business actions ``emit`` typed :class:`DomainEvent`s and independent listeners
react to them. This is deliberately distinct from
``app.notebooks.events.NotebookEventBus``, which is the *transport* that fans
serialized envelopes out to browser SSE connections — that fan-out is wired in
here as one listener among potentially several (audit, metrics, follow-up work).

Dispatch is in-process and best-effort:

* :meth:`DomainEventBus.emit` awaits each matching listener in registration
  order, so database writes stay ordered and errors are observable to the
  emitter.
* A listener that raises is logged and skipped so it cannot break sibling
  listeners or the emitter — unless it was registered ``critical=True``, in
  which case the exception propagates (used where the side effect is part of the
  request's contract, e.g. the registration email).
* Dispatch walks the event's MRO, so a listener registered on a base event class
  (``DocumentEvent``) receives every subclass (``DocumentIndexed`` …) while a
  listener registered on a concrete subclass only sees that one transition.

Durability is explicitly out of scope: events are lost on process crash, exactly
like the SSE bus and FastAPI background tasks. Anything that must survive a
restart relies on the persisted document/report status lifecycle and the
``fail_stale_*`` / ``_recover_pending_*`` recovery passes — not on this bus.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

logger = logging.getLogger(__name__)


class DomainEvent:
    """Marker base class for every event dispatched on :class:`DomainEventBus`."""


EventT = TypeVar("EventT", bound=DomainEvent)
Listener = Callable[[Any], Awaitable[None]]


class DomainEventBus:
    """Process-wide async dispatcher mapping domain event types to listeners."""

    def __init__(self) -> None:
        self._listeners: dict[type[DomainEvent], list[tuple[Listener, bool]]] = (
            defaultdict(list)
        )

    def subscribe(
        self,
        event_type: type[EventT],
        listener: Callable[[EventT], Awaitable[None]],
        *,
        critical: bool = False,
    ) -> None:
        """Register ``listener`` for ``event_type`` and its subclasses.

        Idempotent: registering the same listener for the same type twice is a
        no-op, so wiring functions can run on every app (and test) startup
        without accumulating duplicate subscriptions.

        Registering the same callable with a *different* ``critical`` flag (on
        this or any other event type) is rejected, since :meth:`emit` dedups a
        callable across the event MRO and would otherwise silently honor only
        one of the conflicting flags.
        """
        for bucket in self._listeners.values():
            for existing, existing_critical in bucket:
                if existing is listener and existing_critical != critical:
                    name = getattr(listener, "__qualname__", listener)
                    msg = (
                        f"{name} is already registered with critical="
                        f"{existing_critical}; cannot re-register with "
                        f"critical={critical}"
                    )
                    raise ValueError(msg)
        bucket = self._listeners[event_type]
        if any(existing is listener for existing, _ in bucket):
            return
        bucket.append((listener, critical))

    async def emit(self, event: DomainEvent) -> None:
        """Dispatch ``event`` to every listener of its type or a base type.

        Listeners run sequentially in registration order. A listener that raises
        is logged and skipped, except a ``critical`` listener whose exception
        propagates to the caller.
        """
        called: set[Listener] = set()
        for klass in type(event).__mro__:
            for listener, critical in self._listeners.get(klass, ()):
                # MRO is walked most-derived first, so a listener registered on
                # several related event classes runs once, under its most-derived
                # registration. Register a given callable on a single event type.
                if listener in called:
                    continue
                called.add(listener)
                await self._invoke(listener, critical, event)

    async def _invoke(
        self, listener: Listener, critical: bool, event: DomainEvent
    ) -> None:
        try:
            await listener(event)
        except Exception:
            logger.exception(
                "Domain event listener %r failed handling %s",
                getattr(listener, "__qualname__", listener),
                type(event).__name__,
            )
            if critical:
                raise


domain_event_bus = DomainEventBus()
