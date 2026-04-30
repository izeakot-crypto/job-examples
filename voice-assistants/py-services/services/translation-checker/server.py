#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Translation Checker — FastAPI HTTP-сервер для проверки качества переводов.

Эндпоинты:
  POST /api/translation-checker/check       — анализ переводов (JSON body)
  POST /api/translation-checker/check-file  — анализ переводов (загрузка файла JSON/CSV)
  GET  /api/translation-checker/health      — health check (без авторизации)

Режим: fire-and-forget — мгновенный ответ, анализ в фоне.
"""
import os
import sys
import csv
import io
import json
import time
from concurrent.futures import ThreadPoolExecutor

from typing import Optional

from fastapi import Request, Depends, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field


# --- Pydantic-модели для Swagger UI ---
class TranslationItem(BaseModel):
    """Элемент перевода для проверки."""
    model_config = {"json_schema_extra": {
        "examples": [{"Оригинал": "Сохранить", "EN": "Save", "UA": "Зберегти", "PL": "Zapisz"}]
    }}

    original: str = Field(alias="Оригинал", description="Оригинальный текст (русский)")
    EN: Optional[str] = Field(None, description="Английский перевод")
    UA: Optional[str] = Field(None, description="Украинский перевод")
    PL: Optional[str] = Field(None, description="Польский перевод")
    DE: Optional[str] = Field(None, description="Немецкий перевод")
    ES: Optional[str] = Field(None, description="Испанский перевод")
    PT: Optional[str] = Field(None, description="Португальский перевод")


class CheckRequest(BaseModel):
    """Запрос на проверку переводов."""
    items: list[dict] = Field(
        description="Список элементов для проверки. Каждый элемент — словарь с полем 'Оригинал' и переводами (EN, UA, PL и т.д.)",
        json_schema_extra={"examples": [[
            {"Оригинал": "Сохранить", "EN": "Save", "UA": "Зберегти"},
            {"Оригинал": "Удалить", "EN": "Delete", "UA": "Видалити"}
        ]]}
    )


class CheckResponse(BaseModel):
    """Ответ на запрос проверки."""
    status: str = Field(description="Статус: accepted", examples=["accepted"])
    message: str = Field(description="Сообщение о принятии", examples=["Принято 2 элементов для анализа"])
    total_items: int = Field(description="Количество принятых элементов", examples=[2])

from shared.base_service import create_app, run_service
from shared.auth import require_auth
from shared.logger import get_logger
from shared.statusline import set_statusline

from .llm_client import LLMClient
from .analyzer import TranslationAnalyzer
from .notifier import TelegramNotifier, DiscordNotifier

# --- Конфигурация из .env ---
SERVICE_NAME = "translation-checker"
PORT = int(os.environ.get("TC_PORT", 8585))
API_KEY = os.environ.get("TC_API_KEY", "")

# LLM Provider (ollama / openai / gemini)
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "ollama")
LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "") or os.environ.get("OLLAMA_URL", "")
LLM_MODEL = os.environ.get("LLM_MODEL", "") or os.environ.get("OLLAMA_MODEL", "")
LLM_API_KEY = os.environ.get("LLM_API_KEY", "") or os.environ.get("OLLAMA_API_KEY", "")
LLM_TIMEOUT = int(os.environ.get("LLM_TIMEOUT", os.environ.get("OLLAMA_TIMEOUT", 300)))
LLM_TEMPERATURE = float(os.environ.get("LLM_TEMPERATURE", os.environ.get("OLLAMA_TEMPERATURE", 0.1)))
LLM_MAX_TOKENS = int(os.environ.get("LLM_MAX_TOKENS", os.environ.get("OLLAMA_MAX_TOKENS", 4096)))
LLM_MAX_RETRIES = int(os.environ.get("LLM_MAX_RETRIES", os.environ.get("OLLAMA_MAX_RETRIES", 5)))

# Telegram
TG_BOT_TOKEN = os.environ.get("TC_TG_BOT_TOKEN", "")
TG_CHAT_ID = os.environ.get("TC_TG_CHAT_ID", "")

# Discord
DISCORD_WEBHOOK = os.environ.get("TC_DISCORD_WEBHOOK", "")

# Analysis
CHECK_ORIGINAL = os.environ.get("CHECK_ORIGINAL", "true").lower() == "true"
CHECK_TRANSLATIONS = os.environ.get("CHECK_TRANSLATIONS", "true").lower() == "true"
MAX_LENGTH_RATIO = float(os.environ.get("MAX_LENGTH_RATIO", 3.0))
MIN_LENGTH_RATIO = float(os.environ.get("MIN_LENGTH_RATIO", 0.2))

# Retry
ANALYSIS_MAX_RETRIES = 3
ANALYSIS_RETRY_DELAY = 10

# --- Инициализация ---
DISCORD_ALERTS_WEBHOOK = os.environ.get("DISCORD_WEBHOOK", "")
logger = get_logger(SERVICE_NAME, discord_webhook=DISCORD_ALERTS_WEBHOOK)
executor = ThreadPoolExecutor(max_workers=4)

# Глобальные объекты
analyzer = None
notifiers = []
llm_client = None


def init_services():
    """Инициализация всех сервисов из .env переменных."""
    global analyzer, notifiers, llm_client

    if not API_KEY:
        logger.error("API_KEY не задан! Установите переменную окружения API_KEY.")
        sys.exit(1)

    if not LLM_BASE_URL:
        logger.error("LLM_BASE_URL (или OLLAMA_URL) не задан!")
        sys.exit(1)

    # LLM Client
    llm_client = LLMClient(
        provider=LLM_PROVIDER,
        base_url=LLM_BASE_URL,
        model=LLM_MODEL,
        api_key=LLM_API_KEY,
        timeout=LLM_TIMEOUT,
        temperature=LLM_TEMPERATURE,
        max_tokens=LLM_MAX_TOKENS,
        max_retries=LLM_MAX_RETRIES,
    )

    if not llm_client.check_connection():
        logger.warning(f"LLM ({LLM_PROVIDER}) пока недоступен — анализ будет пробовать при каждом запросе")

    # Анализатор
    analysis_config = {
        "check_original": CHECK_ORIGINAL,
        "check_translations": CHECK_TRANSLATIONS,
        "max_length_ratio": MAX_LENGTH_RATIO,
        "min_length_ratio": MIN_LENGTH_RATIO,
    }
    analyzer = TranslationAnalyzer(llm_client, analysis_config)

    # Нотификаторы
    notifiers.clear()

    if TG_BOT_TOKEN and TG_CHAT_ID:
        notifiers.append(TelegramNotifier(TG_BOT_TOKEN, int(TG_CHAT_ID)))
        logger.info(f"Telegram нотификация: чат {TG_CHAT_ID}")

    if DISCORD_WEBHOOK:
        notifiers.append(DiscordNotifier(DISCORD_WEBHOOK))
        logger.info("Discord нотификация включена")


def analyze_with_retry(analyzer_instance, item, max_retries=ANALYSIS_MAX_RETRIES):
    """Анализ с retry при ошибках API."""
    for attempt in range(max_retries):
        try:
            return analyzer_instance.analyze(item)
        except Exception as e:
            if attempt < max_retries - 1:
                delay = ANALYSIS_RETRY_DELAY * (attempt + 1)
                logger.warning(f"Ошибка анализа (попытка {attempt + 1}/{max_retries}): {e}. Повтор через {delay}с")
                time.sleep(delay)
            else:
                logger.error(f"Анализ не удался после {max_retries} попыток: {e}")
                return None


def process_items_background(items: list):
    """Фоновый анализ элементов — fire and forget."""
    if analyzer is None:
        logger.warning("[ФОНОВЫЙ АНАЛИЗ] Анализатор не инициализирован — пропуск")
        return

    logger.info(f"[ФОНОВЫЙ АНАЛИЗ] Начало обработки {len(items)} элементов")
    total_problems = 0

    for i, item in enumerate(items):
        original = item.get('Оригинал', '')
        if not original:
            logger.info(f"Элемент {i+1}: нет поля 'Оригинал' — пропускаем")
            continue

        logger.info(f"Анализ [{i+1}/{len(items)}]: {original[:60]}...")

        try:
            result = analyze_with_retry(analyzer, item)

            if result and result.get('problems'):
                problem_count = len(result['problems'])
                total_problems += problem_count
                logger.info(f"  -> Найдено {problem_count} проблем")

                for notifier in notifiers:
                    try:
                        notifier.send_alert(result)
                    except Exception as e:
                        logger.error(f"Ошибка отправки алерта ({notifier.__class__.__name__}): {e}")
            else:
                logger.info(f"  -> OK")

        except Exception as e:
            logger.error(f"Ошибка обработки элемента {i+1}: {e}")

    logger.info(f"[ФОНОВЫЙ АНАЛИЗ] Завершено. Элементов: {len(items)}, проблем: {total_problems}")


def parse_csv_to_items(content: str) -> list:
    """Парсинг CSV в список словарей для анализа."""
    reader = csv.DictReader(io.StringIO(content))
    items = []
    for row in reader:
        item = {k.strip(): v.strip() for k, v in row.items() if k and v}
        if item:
            items.append(item)
    return items


# --- FastAPI приложение ---
app = create_app(
    service_name=SERVICE_NAME,
    title="Translation Checker API",
    description="Проверка качества переводов",
    version="2.0.0",
    include_health=False,
)


@app.on_event("startup")
async def startup():
    init_services()
    set_statusline(SERVICE_NAME, port=PORT, status="Running")
    logger.info(f"Режим: fire-and-forget")
    logger.info(f"Порт: {PORT}")
    logger.info(f"Алерты: {', '.join(n.__class__.__name__ for n in notifiers)}")


@app.get(f"/api/{SERVICE_NAME}/health")
async def health():
    """Health check — без авторизации."""
    llm_ok = False
    if llm_client:
        try:
            llm_ok = llm_client.check_connection()
        except Exception:
            pass

    return {
        "status": "ok",
        "service": SERVICE_NAME,
        "version": "2.1.0",
        "environment": os.environ.get("CONTAINER_ROLE", "prod"),
        "mode": "fire-and-forget",
        "llm_provider": LLM_PROVIDER,
        "llm_model": LLM_MODEL,
        "llm_available": llm_ok,
        "notifiers": [n.__class__.__name__ for n in notifiers],
    }


@app.post(f"/api/{SERVICE_NAME}/check", response_model=CheckResponse, dependencies=[Depends(require_auth(API_KEY))])
async def check_translations(body: CheckRequest):
    """Приём переводов в формате JSON — анализ в фоне.

    Отправьте список элементов с оригинальным текстом и переводами.
    Анализ выполняется в фоне (fire-and-forget).
    """

    items = body.items

    if not items:
        return CheckResponse(
            status="accepted",
            message="No items to process",
            total_items=0
        )

    logger.info(f"POST /check — принято {len(items)} элементов, запуск фонового анализа")
    executor.submit(process_items_background, items)

    return CheckResponse(
        status="accepted",
        message=f"Принято {len(items)} элементов для анализа",
        total_items=len(items)
    )


@app.post(f"/api/{SERVICE_NAME}/check-file", response_model=CheckResponse, dependencies=[Depends(require_auth(API_KEY))])
async def check_translations_file(file: UploadFile = File(description="JSON или CSV файл с переводами")):
    """Загрузка файла с переводами (JSON или CSV) — анализ в фоне.

    Поддерживаемые форматы:
    - **JSON**: `{"items": [{"Оригинал": "текст", "EN": "text", ...}]}`
    - **CSV**: с заголовками `Оригинал,EN,UA,...`
    """

    try:
        content = await file.read()
        text = content.decode('utf-8')
    except UnicodeDecodeError:
        try:
            text = content.decode('cp1251')
        except Exception:
            raise HTTPException(status_code=400, detail="Cannot decode file. Use UTF-8 or CP1251 encoding")

    filename = (file.filename or '').lower()

    if filename.endswith('.csv'):
        try:
            items = parse_csv_to_items(text)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"CSV parse error: {e}")
    elif filename.endswith('.json'):
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                items = data.get('items', [data])
            elif isinstance(data, list):
                items = data
            else:
                raise ValueError("Expected JSON object or array")
        except json.JSONDecodeError as e:
            raise HTTPException(status_code=400, detail=f"JSON parse error: {e}")
    else:
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                items = data.get('items', [data])
            elif isinstance(data, list):
                items = data
            else:
                raise ValueError()
        except (json.JSONDecodeError, ValueError):
            try:
                items = parse_csv_to_items(text)
            except Exception:
                raise HTTPException(
                    status_code=400,
                    detail="Cannot parse file. Supported formats: JSON, CSV."
                )

    if not items:
        return CheckResponse(
            status="accepted",
            message="File parsed but no items found",
            total_items=0
        )

    logger.info(f"POST /check-file — файл '{file.filename}', {len(items)} элементов, запуск фонового анализа")
    executor.submit(process_items_background, items)

    return CheckResponse(
        status="accepted",
        message=f"Файл '{file.filename}' принят. {len(items)} элементов для анализа",
        total_items=len(items)
    )


if __name__ == '__main__':
    run_service(app, port=PORT, service_name=SERVICE_NAME)
