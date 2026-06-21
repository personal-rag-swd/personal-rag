"""Domain events emitted during the authentication / registration flow."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID

from app.core.event_bus import DomainEvent

if TYPE_CHECKING:
    from app.core.config import Settings


@dataclass(frozen=True, eq=False)
class RegistrationRequested(DomainEvent):
    """A user requested registration; a verification OTP must be delivered."""

    email: str
    otp: str
    settings: Settings


@dataclass(frozen=True, eq=False)
class RegistrationVerified(DomainEvent):
    """A pending registration was confirmed and the user account created."""

    user_id: UUID
    email: str
