#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Abstract interface that every provider adapter must implement."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from ..models import Completion, Message, ProviderConfig


class BaseProvider(ABC):

    @abstractmethod
    async def create_session(self, config: ProviderConfig, parameters: dict) -> dict[str, Any]:
        ...

    @abstractmethod
    async def send_message(self, provider_data: dict[str, Any], messages: list[Message]) -> Completion:
        ...

    @abstractmethod
    async def close_session(self, provider_data: dict[str, Any]) -> None:
        ...
