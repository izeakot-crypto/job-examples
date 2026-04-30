from __future__ import annotations

import json
import logging

import httpx

from .config import settings
from .schemas import Plan, Sheet, Template, Transcript

logger = logging.getLogger(__name__)

BOT_BASE = "/api/bot/quality-assurance"
TRANSCRIPT_BASE = "/api/v1/record-transcript"


class OkiTokiClient:
    """HTTP-клиент для API Оки-Токи."""

    def __init__(self, comp_id: int | None = None) -> None:
        self._base_url = settings.qc_oki_toki_base_url.rstrip("/")
        self._token = settings.qc_oki_toki_api_token
        self._comp_id = comp_id if comp_id is not None else settings.qc_oki_toki_comp_id
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=30.0,
        )

    # --- helpers ---

    def _base_params(self) -> dict:
        return {"api_token": self._token, "comp_id": self._comp_id}

    async def _get(self, path: str, extra_params: dict | None = None) -> dict | list:
        params = self._base_params()
        if extra_params:
            params.update(extra_params)
        resp = await self._client.get(path, params=params)
        resp.raise_for_status()
        return resp.json()

    async def _post(self, path: str, extra_params: dict | None = None, data: dict | None = None) -> dict | list:
        params = self._base_params()
        if extra_params:
            params.update(extra_params)
        resp = await self._client.post(path, params=params, data=data)
        resp.raise_for_status()
        return resp.json()

    # --- эндпоинты ---

    async def get_plan(self, plan_id: int) -> Plan:
        """Получить настройки плана проверки."""
        data = await self._get(f"{BOT_BASE}/plan", {"plan_id": plan_id})
        return Plan.model_validate(data)

    async def get_template(self, template_id: int) -> Template:
        """Получить шаблон оценочного листа."""
        data = await self._get(f"{BOT_BASE}/template", {"template_id": template_id})
        return Template.model_validate(data)

    async def get_unchecked_sessions(self, plan_id: int) -> list[int]:
        """Получить список session_id непроверенных звонков."""
        data = await self._get(f"{BOT_BASE}/list_session_id_for_check", {"id": plan_id})
        return data

    async def get_call_sheet(self, plan_id: int, session_id: int) -> Sheet:
        """Получить пустую анкету для звонка."""
        data = await self._get(
            f"{BOT_BASE}/call/get",
            {"plan_id": plan_id, "session_id": session_id},
        )
        return Sheet.model_validate(data)

    async def save_call_sheet(self, session_id: int, sheet: Sheet) -> dict:
        """Сохранить заполненную анкету."""
        sheet_json = sheet.model_dump_json()
        return await self._post(
            f"{BOT_BASE}/call/set",
            extra_params={"session_id": session_id},
            data={"sheet_json": sheet_json},
        )

    async def skip_call_sheet(self, plan_id: int, session_id: int, comment: str) -> dict:
        """Пропустить анкету (без оценки)."""
        return await self._post(
            f"{BOT_BASE}/call/skip",
            extra_params={
                "plan_id": plan_id,
                "session_id": session_id,
                "comment": comment,
            },
        )

    async def request_transcription(self, comp_id: int, session_id: int) -> bool:
        """Запросить создание двусторонней транскрибации у Вадима.

        Возвращает True если запрос принят, False если нет аудио.
        TODO: заменить заглушку на реальный эндпоинт Вадима.
        """
        # TODO: POST /api/bot/record-transcript/create
        # {"comp_id": comp_id, "session_id": session_id, "type": "dual"}
        # Ответ: {"status": "accepted"} -> True
        #         {"status": "already_exists"} -> True
        #         {"status": "error", "message": "Recording not found"} -> False
        logger.warning(
            "request_transcription: заглушка (comp_id=%d, session_id=%d). "
            "Эндпоинт Вадима ещё не готов — пропускаем.",
            comp_id, session_id,
        )
        return False  # Пока нет эндпоинта — ведём себя как раньше (skip)

    async def get_plans_by_session(self, comp_id: int, session_id: int) -> list[int]:
        """Проверить, входит ли звонок в планы с ботом.

        Возвращает список plan_id или пустой список.
        """
        data = await self._get(
            f"{BOT_BASE}/plans-by-session",
            {"comp_id": comp_id, "session_id": session_id},
        )
        return [item["plan_id"] for item in data]

    async def get_transcript(self, session_id: int) -> Transcript:
        """Получить транскрипт звонка."""
        params = {"api_token": self._token, "session_id": session_id}
        resp = await self._client.get(f"{TRANSCRIPT_BASE}/get", params=params)
        resp.raise_for_status()
        return Transcript.model_validate(resp.json())

    async def get_ready_plans(self) -> list[dict]:
        """Получить список планов, готовых к проверке (План Б).

        Возвращает список {"comp_id": int, "plan_id": int}.
        Без comp_id — возвращает по всем компаниям.
        """
        params = {"api_token": self._token}
        resp = await self._client.get(f"{BOT_BASE}/plans-ready", params=params)
        resp.raise_for_status()
        return resp.json()

    # --- lifecycle ---

    async def close(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> OkiTokiClient:
        return self

    async def __aexit__(self, *exc) -> None:
        await self.close()
