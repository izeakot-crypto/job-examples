#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""n8n adapter — calls an n8n workflow via webhook/API."""
from __future__ import annotations

from typing import Any

import httpx

from ..models import Completion, Message, ProviderConfig
from .base import BaseProvider


class N8NProvider(BaseProvider):

    async def create_session(self, config: ProviderConfig, parameters: dict) -> dict[str, Any]:
        if not config.url:
            raise ValueError("n8n provider requires 'url' (webhook endpoint)")
        return {
            "url": config.url,
            "api_key": config.api_key,
            "system_prompt": config.system_prompt,
            "parameters": parameters,
        }

    async def send_message(self, provider_data: dict[str, Any], messages: list[Message]) -> Completion:
        url = provider_data["url"]
        params = provider_data.get("parameters", {})
        timeout = params.get("timeout", 120)

        headers: dict[str, str] = {"Content-Type": "application/json"}
        if provider_data.get("api_key"):
            headers["Authorization"] = f"Bearer {provider_data['api_key']}"
        headers.update(params.get("headers", {}))

        payload: dict[str, Any] = {
            "messages": [{"role": m.role, "content": m.content} for m in messages],
        }
        if provider_data.get("system_prompt"):
            payload["system_prompt"] = provider_data["system_prompt"]
        payload.update({k: v for k, v in params.items() if k not in ("headers", "timeout", "response_path")})

        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        text = self._extract_text(data, params.get("response_path", "output"))
        return Completion(
            text=text,
            tokens_send=data.get("tokens_send", 0),
            tokens_received=data.get("tokens_received", 0),
        )

    async def close_session(self, provider_data: dict[str, Any]) -> None:
        pass

    @staticmethod
    def _extract_text(data: Any, path: str) -> str:
        current = data
        for key in path.split("."):
            if isinstance(current, dict):
                current = current.get(key, "")
            elif isinstance(current, list) and current:
                current = current[0].get(key, "") if isinstance(current[0], dict) else ""
            else:
                return str(current)
        return str(current)
