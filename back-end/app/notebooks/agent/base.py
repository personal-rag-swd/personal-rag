from __future__ import annotations

from typing import Protocol, runtime_checkable
from pydantic_ai.models import Model


@runtime_checkable
class ChatModelProvider(Protocol):
    def build_model(self) -> Model:
        """Build and return a configured chat model instance."""
