from __future__ import annotations

from typing import Any

from openai import AsyncOpenAI

from app.models import Completion, Message, ProviderConfig
from app.providers.base import BaseProvider


class OpenAIProvider(BaseProvider):
    """
    Two modes:
    1. Assistants API — when assistant_id is provided (supports RAG / file_search).
    2. Chat Completions — fallback when no assistant_id.
    """

    # ── interface ─────────────────────────────────────────

    async def create_session(
        self,
        config: ProviderConfig,
        parameters: dict,
    ) -> dict[str, Any]:
        client = self._make_client(config)

        data: dict[str, Any] = {
            "api_key": config.api_key,
            "url": config.url,
            "model": config.model or "gpt-4o",
            "system_prompt": config.system_prompt,
            "temperature": config.temperature,
            "max_tokens": config.max_tokens,
            "parameters": parameters,
        }

        if config.assistant_id:
            thread = await client.beta.threads.create()
            data["mode"] = "assistants"
            data["assistant_id"] = config.assistant_id
            data["thread_id"] = thread.id
        else:
            data["mode"] = "chat"

        return data

    async def send_message(
        self,
        provider_data: dict[str, Any],
        messages: list[Message],
    ) -> Completion:
        client = self._make_client_from_data(provider_data)

        if provider_data["mode"] == "assistants":
            return await self._send_assistants(client, provider_data, messages)
        return await self._send_chat(client, provider_data, messages)

    async def close_session(self, provider_data: dict[str, Any]) -> None:
        if provider_data.get("mode") == "assistants" and provider_data.get("thread_id"):
            client = self._make_client_from_data(provider_data)
            try:
                await client.beta.threads.delete(provider_data["thread_id"])
            except Exception:
                pass  # best-effort cleanup

    # ── Chat Completions ─────────────────────────────────

    async def _send_chat(
        self,
        client: AsyncOpenAI,
        data: dict[str, Any],
        messages: list[Message],
    ) -> Completion:
        api_messages: list[dict] = []
        if data.get("system_prompt"):
            api_messages.append({"role": "system", "content": data["system_prompt"]})
        api_messages.extend({"role": m.role, "content": m.content} for m in messages)

        params: dict[str, Any] = {
            "model": data["model"],
            "messages": api_messages,
            "temperature": data["temperature"],
            "max_tokens": data["max_tokens"],
        }
        # merge vendor-specific parameters
        params.update(data.get("parameters", {}))

        resp = await client.chat.completions.create(**params)
        choice = resp.choices[0]
        usage = resp.usage

        return Completion(
            text=choice.message.content or "",
            tokens_send=usage.prompt_tokens if usage else 0,
            tokens_received=usage.completion_tokens if usage else 0,
        )

    # ── Assistants API ───────────────────────────────────

    async def _send_assistants(
        self,
        client: AsyncOpenAI,
        data: dict[str, Any],
        messages: list[Message],
    ) -> Completion:
        thread_id = data["thread_id"]

        # add only the last user message (history lives in the thread)
        last_msg = messages[-1]
        await client.beta.threads.messages.create(
            thread_id=thread_id,
            role=last_msg.role,
            content=last_msg.content,
        )

        run = await client.beta.threads.runs.create_and_poll(
            thread_id=thread_id,
            assistant_id=data["assistant_id"],
        )

        if run.status != "completed":
            raise RuntimeError(f"OpenAI run failed: {run.status} — {run.last_error}")

        result_messages = await client.beta.threads.messages.list(
            thread_id=thread_id, order="desc", limit=1,
        )
        text = ""
        if result_messages.data:
            content_block = result_messages.data[0].content[0]
            if hasattr(content_block, "text"):
                text = content_block.text.value

        usage = run.usage
        return Completion(
            text=text,
            tokens_send=usage.prompt_tokens if usage else 0,
            tokens_received=usage.completion_tokens if usage else 0,
        )

    # ── helpers ───────────────────────────────────────────

    def _make_client(self, config: ProviderConfig) -> AsyncOpenAI:
        kwargs: dict[str, Any] = {"api_key": config.api_key}
        if config.url:
            kwargs["base_url"] = config.url
        return AsyncOpenAI(**kwargs)

    def _make_client_from_data(self, data: dict[str, Any]) -> AsyncOpenAI:
        kwargs: dict[str, Any] = {"api_key": data["api_key"]}
        if data.get("url"):
            kwargs["base_url"] = data["url"]
        return AsyncOpenAI(**kwargs)
