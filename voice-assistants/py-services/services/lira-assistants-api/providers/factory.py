#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Provider factory — maps provider name to adapter class."""
from __future__ import annotations

from .base import BaseProvider
from .openai_provider import OpenAIProvider
from .claude_provider import ClaudeProvider
from .n8n_provider import N8NProvider

_PROVIDERS: dict[str, type[BaseProvider]] = {
    "openai": OpenAIProvider,
    "claude": ClaudeProvider,
    "n8n": N8NProvider,
}


def get_provider(name: str | object) -> BaseProvider:
    key = name.value if hasattr(name, "value") else str(name)
    cls = _PROVIDERS.get(key)
    if cls is None:
        supported = ", ".join(_PROVIDERS)
        raise ValueError(f"Unknown provider '{key}'. Supported: {supported}")
    return cls()
