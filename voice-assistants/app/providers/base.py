from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.models import Completion, Message, ProviderConfig


class BaseProvider(ABC):
    """Abstract interface that every provider adapter must implement."""

    @abstractmethod
    async def create_session(
        self,
        config: ProviderConfig,
        parameters: dict,
    ) -> dict[str, Any]:
        """Initialise a provider-side session. Returns provider-specific data to store."""
        ...

    @abstractmethod
    async def send_message(
        self,
        provider_data: dict[str, Any],
        messages: list[Message],
    ) -> Completion:
        """Send messages and return a unified Completion."""
        ...

    @abstractmethod
    async def close_session(
        self,
        provider_data: dict[str, Any],
    ) -> None:
        """Clean up provider-side resources (threads, etc.)."""
        ...
