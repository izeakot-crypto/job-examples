#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""In-memory session manager for assistant sessions."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from .models import Completion, CreateRequest, Message, ProviderConfig
from .providers.base import BaseProvider
from .providers.factory import get_provider


@dataclass
class SessionData:
    assistant_session_id: str
    session_id: str
    comp_id: int
    contact_id: int
    provider_name: str
    config: ProviderConfig
    parameters: dict
    provider_data: dict[str, Any] = field(default_factory=dict)
    history: list[Message] = field(default_factory=list)


class SessionManager:
    def __init__(self) -> None:
        self._sessions: dict[str, SessionData] = {}

    def _get_session(self, comp_id: int, assistant_session_id: str) -> SessionData:
        session = self._sessions.get(assistant_session_id)
        if session is None:
            raise KeyError(f"Session '{assistant_session_id}' not found")
        if session.comp_id != comp_id:
            raise PermissionError("comp_id mismatch")
        return session

    def _get_provider(self, session: SessionData) -> BaseProvider:
        return get_provider(session.provider_name)

    @property
    def active_count(self) -> int:
        return len(self._sessions)

    async def create(self, req: CreateRequest) -> str:
        provider = get_provider(req.provider)
        assistant_session_id = str(uuid.uuid4())
        provider_data = await provider.create_session(req.config, req.parameters)
        session = SessionData(
            assistant_session_id=assistant_session_id,
            session_id=req.session_id,
            comp_id=req.comp_id,
            contact_id=req.contact_id,
            provider_name=req.provider.value,
            config=req.config,
            parameters=req.parameters,
            provider_data=provider_data,
        )
        self._sessions[assistant_session_id] = session
        return assistant_session_id

    async def resume(self, comp_id: int, assistant_session_id: str) -> str:
        session = self._get_session(comp_id, assistant_session_id)
        return session.assistant_session_id

    async def message(self, comp_id: int, assistant_session_id: str, messages: list[Message]) -> Completion:
        session = self._get_session(comp_id, assistant_session_id)
        provider = self._get_provider(session)
        session.history.extend(messages)
        completion = await provider.send_message(session.provider_data, session.history)
        session.history.append(Message(role="assistant", content=completion.text))
        return completion

    async def close(self, comp_id: int, assistant_session_id: str) -> None:
        session = self._get_session(comp_id, assistant_session_id)
        provider = self._get_provider(session)
        await provider.close_session(session.provider_data)
        del self._sessions[assistant_session_id]
