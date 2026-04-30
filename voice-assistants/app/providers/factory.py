from __future__ import annotations

from app.providers.base import BaseProvider
from app.providers.openai_provider import OpenAIProvider
from app.providers.claude_provider import ClaudeProvider
from app.providers.n8n_provider import N8NProvider

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
