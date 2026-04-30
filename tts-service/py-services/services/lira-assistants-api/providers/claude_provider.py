#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Anthropic Messages API adapter."""
from __future__ import annotations

from typing import Any

from anthropic import AsyncAnthropic

from ..models import Completion, Message, ProviderConfig
from .base import BaseProvider


class ClaudeProvider(BaseProvider):

    async def create_session(self, config: ProviderConfig, parameters: dict) -> dict[str, Any]:
        return {
            "api_key": config.api_key,
            "url": config.url,
            "model": config.model or "claude-sonnet-4-20250514",
            "system_prompt": config.system_prompt,
            "temperature": config.temperature,
            "max_tokens": config.max_tokens,
            "parameters": parameters,
        }

    async def send_message(self, provider_data: dict[str, Any], messages: list[Message]) -> Completion:
        client = self._make_client(provider_data)
        api_messages = [{"role": m.role, "content": m.content} for m in messages]
        params: dict[str, Any] = {
            "model": provider_data["model"],
            "messages": api_messages,
            "temperature": provider_data["temperature"],
            "max_tokens": provider_data["max_tokens"],
        }
        if provider_data.get("system_prompt"):
            params["system"] = provider_data["system_prompt"]
        params.update(provider_data.get("parameters", {}))
        resp = await client.messages.create(**params)
        text = ""
        if resp.content:
            text = resp.content[0].text
        return Completion(
            text=text,
            tokens_send=resp.usage.input_tokens,
            tokens_received=resp.usage.output_tokens,
        )

    async def close_session(self, provider_data: dict[str, Any]) -> None:
        pass

    def _make_client(self, data: dict[str, Any]) -> AsyncAnthropic:
        kwargs: dict[str, Any] = {"api_key": data["api_key"]}
        if data.get("url"):
            kwargs["base_url"] = data["url"]
        return AsyncAnthropic(**kwargs)
