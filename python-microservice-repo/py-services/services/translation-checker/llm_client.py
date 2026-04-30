#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LLMClient — универсальный клиент для работы с LLM-провайдерами.

Поддерживаемые провайдеры:
  - ollama    : Ollama API (/api/generate)
  - openai    : OpenAI-совместимый API (/v1/chat/completions)
  - gemini    : Google Gemini через OpenAI-совместимый прокси

Провайдер выбирается через переменную LLM_PROVIDER (по умолчанию "ollama").
"""
import json
import re
import time

import requests

from shared.logger import get_logger

logger = get_logger("translation-checker.llm")

# ---------------------------------------------------------------------------
# Провайдеры
# ---------------------------------------------------------------------------
PROVIDER_OLLAMA = "ollama"
PROVIDER_OPENAI = "openai"
PROVIDER_GEMINI = "gemini"

KNOWN_PROVIDERS = {PROVIDER_OLLAMA, PROVIDER_OPENAI, PROVIDER_GEMINI}

# Базовые URL по умолчанию для провайдеров (можно переопределить через LLM_BASE_URL)
DEFAULT_BASE_URLS = {
    PROVIDER_OLLAMA: "http://localhost:11434",
    PROVIDER_OPENAI: "https://api.openai.com",
    PROVIDER_GEMINI: "https://generativelanguage.googleapis.com/v1beta/openai",
}

DEFAULT_MODELS = {
    PROVIDER_OLLAMA: "llama3",
    PROVIDER_OPENAI: "gpt-4o-mini",
    PROVIDER_GEMINI: "gemini-2.5-flash",
}


class LLMClient:
    """Универсальный клиент для LLM-провайдеров с retry-логикой."""

    def __init__(
        self,
        provider: str = PROVIDER_OLLAMA,
        base_url: str = "",
        model: str = "",
        api_key: str = "",
        timeout: int = 300,
        temperature: float = 0.1,
        max_tokens: int = 4096,
        max_retries: int = 5,
    ):
        self.provider = provider.lower().strip()
        if self.provider not in KNOWN_PROVIDERS:
            raise ValueError(
                f"Неизвестный провайдер '{self.provider}'. "
                f"Доступные: {', '.join(sorted(KNOWN_PROVIDERS))}"
            )

        self.base_url = (base_url or DEFAULT_BASE_URLS.get(self.provider, "")).rstrip("/")
        self.model = model or DEFAULT_MODELS.get(self.provider, "")
        self.api_key = api_key
        self.timeout = timeout
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.max_retries = max_retries

        # Заголовки
        self.headers = {"Content-Type": "application/json"}
        if api_key:
            self.headers["Authorization"] = f"Bearer {api_key}"

        logger.info(
            f"LLMClient инициализирован: provider={self.provider}, "
            f"model={self.model}, base_url={self.base_url}"
        )

    # ------------------------------------------------------------------
    # Проверка соединения
    # ------------------------------------------------------------------
    def check_connection(self) -> bool:
        """Проверка доступности LLM-провайдера."""
        try:
            if self.provider == PROVIDER_OLLAMA:
                return self._check_ollama()
            else:
                return self._check_openai_compat()
        except Exception as e:
            logger.warning(f"Ошибка проверки соединения ({self.provider}): {e}")
            return False

    def _check_ollama(self) -> bool:
        """Проверка Ollama через /api/tags."""
        url = f"{self.base_url}/api/tags"
        logger.info(f"Проверка соединения: {url}")
        resp = requests.get(url, headers=self.headers, timeout=30)
        resp.raise_for_status()
        models = [m["name"] for m in resp.json().get("models", [])]
        logger.info(f"Ollama доступна. Модели: {', '.join(models[:5])}")
        if self.model not in models and f"{self.model}:latest" not in models:
            base_names = [m.split(":")[0] for m in models]
            if self.model.split(":")[0] not in base_names:
                logger.warning(f"Модель '{self.model}' не найдена!")
                return False
        return True

    def _check_openai_compat(self) -> bool:
        """Проверка OpenAI-совместимого API через /v1/models или тестовый запрос."""
        # Gemini и некоторые провайдеры не поддерживают /v1/models,
        # поэтому делаем лёгкий тестовый запрос
        url = f"{self.base_url}/v1/models" if self.provider == PROVIDER_OPENAI else None

        if url:
            try:
                logger.info(f"Проверка соединения: {url}")
                resp = requests.get(url, headers=self.headers, timeout=30)
                resp.raise_for_status()
                data = resp.json()
                models = [m.get("id", "") for m in data.get("data", [])]
                logger.info(f"{self.provider} доступен. Модели: {', '.join(models[:5])}")
                return True
            except Exception:
                pass

        # Fallback: маленький тестовый запрос
        try:
            logger.info(f"Проверка {self.provider} тестовым запросом...")
            self.generate("Ответь одним словом: привет")
            logger.info(f"{self.provider} доступен и отвечает.")
            return True
        except Exception as e:
            logger.warning(f"{self.provider} недоступен: {e}")
            return False

    # ------------------------------------------------------------------
    # Генерация
    # ------------------------------------------------------------------
    def generate(self, prompt: str) -> str:
        """Отправка запроса к LLM с retry-логикой."""
        prompt_preview = prompt[:80].replace("\n", " ")

        for attempt in range(self.max_retries):
            t_start = time.time()
            try:
                if self.provider == PROVIDER_OLLAMA:
                    resp_text = self._generate_ollama(prompt)
                else:
                    resp_text = self._generate_openai_compat(prompt)

                elapsed = time.time() - t_start
                logger.info(
                    f"OK {elapsed:.1f}с | {self.provider}/{self.model} | "
                    f"ответ: {len(resp_text)} символов | {prompt_preview}..."
                )
                return resp_text

            except requests.exceptions.ConnectionError:
                elapsed = time.time() - t_start
                wait = 10 * (attempt + 1)
                logger.warning(
                    f"ConnectionError через {elapsed:.1f}с "
                    f"(попытка {attempt + 1}/{self.max_retries}), жду {wait}с"
                )
                time.sleep(wait)

            except requests.exceptions.Timeout:
                elapsed = time.time() - t_start
                wait = 15 * (attempt + 1)
                logger.warning(
                    f"Timeout через {elapsed:.1f}с "
                    f"(попытка {attempt + 1}/{self.max_retries}), жду {wait}с"
                )
                time.sleep(wait)

            except requests.exceptions.HTTPError as exc:
                elapsed = time.time() - t_start
                response = exc.response if exc.response is not None else None
                status = response.status_code if response else 0
                body = (response.text[:200] if response and response.text else "пусто")
                if status == 429:
                    wait = 30 * (attempt + 1)
                    logger.warning(
                        f"HTTP 429 Rate Limit "
                        f"(попытка {attempt + 1}/{self.max_retries}), жду {wait}с"
                    )
                    time.sleep(wait)
                elif status >= 500:
                    wait = 15 * (attempt + 1)
                    logger.warning(
                        f"HTTP {status} "
                        f"(попытка {attempt + 1}/{self.max_retries}), жду {wait}с | {body}"
                    )
                    time.sleep(wait)
                else:
                    logger.error(f"HTTP {status} — не retriable | {body}")
                    raise

        logger.error(f"Все {self.max_retries} попыток исчерпаны!")
        raise RuntimeError(f"Все {self.max_retries} попыток исчерпаны")

    def _generate_ollama(self, prompt: str) -> str:
        """Запрос через Ollama API (/api/generate)."""
        response = requests.post(
            f"{self.base_url}/api/generate",
            headers=self.headers,
            json={
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": self.temperature,
                    "num_predict": self.max_tokens,
                },
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json().get("response", "")

    def _generate_openai_compat(self, prompt: str) -> str:
        """Запрос через OpenAI-совместимый API (/v1/chat/completions)."""
        # Определяем URL для chat completions
        url = f"{self.base_url}/chat/completions"
        if "/v1" not in self.base_url:
            url = f"{self.base_url}/v1/chat/completions"

        response = requests.post(
            url,
            headers=self.headers,
            json={
                "model": self.model,
                "messages": [
                    {"role": "user", "content": prompt}
                ],
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        data = response.json()

        # Стандартный формат OpenAI
        choices = data.get("choices", [])
        if choices:
            return choices[0].get("message", {}).get("content", "")

        # Fallback для нестандартных ответов
        logger.warning(f"Нестандартный формат ответа: {json.dumps(data)[:200]}")
        return ""


# ---------------------------------------------------------------------------
# Утилита для парсинга JSON из ответов LLM (не зависит от провайдера)
# ---------------------------------------------------------------------------
def parse_llm_json(raw: str) -> list:
    """Извлечение JSON-массива из ответа LLM."""
    try:
        result = json.loads(raw)
        if isinstance(result, list):
            return result
    except json.JSONDecodeError:
        pass

    match = re.search(r"```json?\s*([\s\S]*?)```", raw)
    if match:
        try:
            result = json.loads(match.group(1))
            if isinstance(result, list):
                return result
        except json.JSONDecodeError:
            pass

    match = re.search(r"\[[\s\S]*\]", raw)
    if match:
        try:
            result = json.loads(match.group(0))
            if isinstance(result, list):
                return result
        except json.JSONDecodeError:
            pass

    if (
        raw.strip() == "[]"
        or "ошибок нет" in raw.lower()
        or "нет ошибок" in raw.lower()
        or "проблем нет" in raw.lower()
    ):
        return []

    logger.warning(f"Не удалось распарсить ответ LLM: {raw[:150]}...")
    return []


# ---------------------------------------------------------------------------
# Обратная совместимость
# ---------------------------------------------------------------------------
# Алиас для плавной миграции — старый код с `from .ollama_client import OllamaClient`
# продолжит работать после обновления импортов
OllamaClient = LLMClient
