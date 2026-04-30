from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from copy import deepcopy

import httpx
from openai import AsyncOpenAI

from .config import settings
from .prompts import build_system_prompt, build_evaluation_prompt
from .token_tracker import TokenTracker
from .schemas import LLMResult, Sheet

logger = logging.getLogger(__name__)


class EvaluationResult:
    """Результат оценки: заполненная анкета + метаданные LLM."""

    def __init__(
        self,
        sheet: Sheet,
        llm_result: LLMResult,
        llm_response_raw: str,
        llm_prompt: str,
        processing_time_ms: int,
    ) -> None:
        self.sheet = sheet
        self.llm_result = llm_result
        self.llm_response_raw = llm_response_raw
        self.llm_prompt = llm_prompt
        self.processing_time_ms = processing_time_ms


class Evaluator:
    """Отправляет транскрипт + вопросы в LLM и возвращает заполненную анкету.

    Поддерживает провайдеры:
    - gemini: через OpenAI-совместимый API Google
    - ollama: через нативный Ollama API (прокси к Claude)
    """

    def __init__(self) -> None:
        self._provider = settings.llm_provider
        self._model = settings.llm_model
        self._temperature = settings.llm_temperature
        self._max_retries = settings.llm_max_retries
        self.tracker = TokenTracker()

        if self._provider == "ollama":
            self._base_url = settings.llm_base_url.rstrip("/")
            self._api_key = settings.llm_api_key
            self._http = httpx.AsyncClient(timeout=120.0)
        else:
            # gemini и любой OpenAI-совместимый провайдер
            self._openai = AsyncOpenAI(
                api_key=settings.llm_api_key,
                base_url=settings.llm_base_url,
            )

    async def evaluate(self, sheet: Sheet, transcript_text: str) -> EvaluationResult:
        """Оценивает звонок и возвращает результат с метаданными."""
        system_prompt = build_system_prompt(sheet)
        user_prompt = build_evaluation_prompt(sheet, transcript_text)
        full_prompt = f"[SYSTEM]\n{system_prompt}\n\n[USER]\n{user_prompt}"

        for attempt in range(1, self._max_retries + 1):
            try:
                start = time.monotonic()

                if self._provider == "ollama":
                    raw = await self._call_ollama(system_prompt, user_prompt)
                else:
                    raw = await self._call_openai(system_prompt, user_prompt)

                elapsed_ms = int((time.monotonic() - start) * 1000)

                llm_result = self._parse_response(raw)
                filled_sheet = self._apply_result(sheet, llm_result)

                logger.debug(
                    "LLM ответ для анкеты: general_comment=%s",
                    llm_result.general_comment,
                )

                return EvaluationResult(
                    sheet=filled_sheet,
                    llm_result=llm_result,
                    llm_response_raw=raw,
                    llm_prompt=full_prompt,
                    processing_time_ms=elapsed_ms,
                )

            except Exception:
                logger.exception("LLM attempt %d/%d failed", attempt, self._max_retries)
                if attempt == self._max_retries:
                    raise
                await asyncio.sleep(2 * attempt)  # 2с, 4с, 6с...

    async def _call_openai(self, system_prompt: str, user_prompt: str) -> str:
        """Вызов через OpenAI-совместимый API (Gemini и др.)."""
        response = await self._openai.chat.completions.create(
            model=self._model,
            temperature=self._temperature,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        if response.usage:
            self.tracker.record(
                self._model,
                response.usage.prompt_tokens,
                response.usage.completion_tokens,
            )
        return response.choices[0].message.content

    async def _call_ollama(self, system_prompt: str, user_prompt: str) -> str:
        """Вызов через нативный Ollama API."""
        resp = await self._http.post(
            f"{self._base_url}/chat",
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self._model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "stream": False,
                "options": {"temperature": self._temperature},
            },
        )
        resp.raise_for_status()
        data = resp.json()

        content = data["message"]["content"]

        # Ollama-прокси возвращает фиктивный prompt_eval_count (всегда 3).
        # Оцениваем input-токены по длине промпта (~4 символа = 1 токен).
        raw_input = data.get("prompt_eval_count", 0)
        output_tokens = data.get("eval_count", 0)
        if raw_input <= 10:
            prompt_len = len(system_prompt) + len(user_prompt)
            input_tokens = prompt_len // 4
        else:
            input_tokens = raw_input

        if input_tokens or output_tokens:
            self.tracker.record(self._model, input_tokens, output_tokens)

        return content

    @staticmethod
    def _extract_json(raw: str) -> str:
        """Извлекает JSON из ответа, убирая markdown-обёртку ```json...```."""
        match = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw)
        if match:
            return match.group(1).strip()
        return raw.strip()

    def _parse_response(self, raw: str) -> LLMResult:
        """Парсит JSON-ответ LLM в структурированный результат."""
        clean = self._extract_json(raw)
        if not clean:
            raise ValueError(f"LLM вернула пустой ответ: {raw[:200]}")
        try:
            data = json.loads(clean)
        except json.JSONDecodeError as e:
            logger.error("Невалидный JSON от LLM: %s\nОтвет: %s", e, raw[:500])
            raise

        # Поддержка старого формата (массив напрямую) и нового (объект с answers)
        if isinstance(data, list):
            answers = []
            for item in data:
                answers.append({
                    "category_id": item["category_id"],
                    "question_id": item["question_id"],
                    "answer": "yes" if item.get("rating", 0) == 1 else "no",
                    "comment": item.get("comment"),
                    "transcript_fragment": item.get("transcript_fragment"),
                })
            return LLMResult(answers=answers)

        return LLMResult.model_validate(data)

    def _apply_result(self, sheet: Sheet, result: LLMResult) -> Sheet:
        """Проставляет rating и general_comment в копию анкеты."""
        filled = deepcopy(sheet)

        answer_map = {
            (a.category_id, a.question_id): a
            for a in result.answers
        }

        for category in filled.value:
            for question in category.value:
                key = (category.id, question.id)
                if key in answer_map:
                    answer = answer_map[key]
                    question.rating = 1 if answer.answer == "yes" else 0

        filled.comment_other = result.general_comment
        filled.is_complete = True
        return filled

    async def close(self) -> None:
        if self._provider == "ollama":
            await self._http.aclose()
