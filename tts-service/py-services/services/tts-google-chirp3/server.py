#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TTS Google Chirp3-HD — FastAPI HTTP-сервер для синтезу мовлення.

Ендпоінти:
  POST /api/tts-google-chirp3/open      — відкрити сесію (прогрів gRPC)
  POST /api/tts-google-chirp3/generate  — згенерувати аудіо (WAV)
  POST /api/tts-google-chirp3/close     — закрити сесію
  GET  /api/tts-google-chirp3/status    — статус сервера
  GET  /api/tts-google-chirp3/health    — health check (без авторизації)
"""
import os
import time
import asyncio

import httpx
from fastapi import Depends
from fastapi.responses import Response, JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from shared.base_service import create_app, run_service
from shared.auth import require_auth
from shared.logger import get_logger
from shared.statusline import set_statusline

from . import tts_engine

# --- Конфігурація з .env (префікс TGC_) ---
SERVICE_NAME = "tts-google-chirp3"
PORT = int(os.environ.get("TGC_PORT", 8589))
API_KEY = os.environ.get("TGC_API_KEY", "")

# Google credentials
_CREDENTIALS_PATH = os.environ.get("TGC_GOOGLE_CREDENTIALS", "")
if _CREDENTIALS_PATH and os.path.exists(_CREDENTIALS_PATH):
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = _CREDENTIALS_PATH

# Discord алерти (WARNING+ → Discord) — як в translation-checker
_DISCORD_ALERTS_WEBHOOK = os.environ.get("DISCORD_WEBHOOK", "")

# Біллінг (fire-and-forget POST після кожної генерації)
BILLING_URL = os.environ.get("TGC_BILLING_URL", "")

logger = get_logger(SERVICE_NAME, discord_webhook=_DISCORD_ALERTS_WEBHOOK)

# --- Сесії ---
sessions: dict = {}
request_counter = 0


# --- Pydantic-моделі для Swagger UI ---
class OpenRequest(BaseModel):
    """Запит на відкриття сесії."""
    session_id: str = Field(..., description="Ідентифікатор сесії від LIRA")
    comp_schema: str = Field(..., description="Змінна для біллінгу")


class OpenResponse(BaseModel):
    """Відповідь на відкриття сесії."""
    model_config = ConfigDict(json_schema_extra={"example": {
        "status": "ready", "session_id": "call-12345", "comp_schema": "billing_1",
        "session_key": "call-12345_billing_1", "startup_ms": 3200,
        "voices": ["Leda", "Puck", "Kore", "Aoede", "Charon", "Fenrir"], "timeout_sec": 300,
    }})
    status: str = Field(description="Статус")
    session_id: str = Field(description="ID сесії")
    comp_schema: str = Field(description="Біллінг-змінна")
    session_key: str = Field(description="Ключ сесії (session_id_comp_schema)")
    startup_ms: int = Field(description="Час відкриття сесії (мс)")
    voices: list[str] = Field(description="Доступні голоси")
    timeout_sec: int = Field(description="Таймаут неактивної сесії (с)")


class GenerateRequest(BaseModel):
    """Запит на генерацію аудіо."""
    session_id: str = Field(..., description="Ідентифікатор сесії")
    comp_schema: str = Field(..., description="Змінна для біллінгу")
    text: str = Field(..., description="Текст для синтезу", min_length=1)
    voice: str = Field(default="Leda", description="Голос (Leda, Puck, Kore, Aoede, Charon, Fenrir)")
    locale: str = Field(default="uk_UA", description="Мова: uk_UA, ru_RU, en_US, pl_PL, es_ES, tr_TR")


class CloseRequest(BaseModel):
    """Запит на закриття сесії."""
    session_id: str = Field(..., description="Ідентифікатор сесії")
    comp_schema: str = Field(..., description="Змінна для біллінгу")


class CloseResponse(BaseModel):
    """Відповідь на закриття сесії."""
    model_config = ConfigDict(json_schema_extra={"example": {
        "status": "closed", "session_id": "call-12345", "comp_schema": "billing_1",
    }})
    status: str = Field(description="Статус")
    session_id: str = Field(description="ID сесії")
    comp_schema: str = Field(description="Біллінг-змінна")


class HealthResponse(BaseModel):
    """Відповідь health check."""
    model_config = ConfigDict(json_schema_extra={"example": {
        "status": "ok", "service": "tts-google-chirp3", "version": "1.0.0",
        "grpc_ready": True, "grpc_clients": 5, "active_sessions": 2,
    }})
    status: str = Field(description="Статус сервісу")
    service: str = Field(description="Назва сервісу")
    version: str = Field(description="Версія")
    grpc_ready: bool = Field(description="gRPC прогрітий (true після першого /open)")
    grpc_clients: int = Field(description="Кількість активних gRPC каналів (0–5)")
    active_sessions: int = Field(description="Кількість відкритих TTS-сесій")


class SessionDetail(BaseModel):
    """Деталі активної сесії."""
    model_config = ConfigDict(json_schema_extra={"example": {
        "session_id": "call-12345", "comp_schema": "billing_1",
        "age_sec": 120, "idle_sec": 15, "request_count": 8,
        "total_chars": 1250, "timeout_in": 285,
    }})
    session_id: str = Field(description="ID сесії")
    comp_schema: str = Field(description="Біллінг-змінна")
    age_sec: int = Field(description="Вік сесії (секунди)")
    idle_sec: int = Field(description="Час без активності (секунди)")
    request_count: int = Field(description="Кількість запитів /generate")
    total_chars: int = Field(description="Загальна кількість символів")
    timeout_in: int = Field(description="Секунд до автозакриття")


class CacheStats(BaseModel):
    """Статистика кешу."""
    model_config = ConfigDict(json_schema_extra={"example": {
        "cached_files": 42, "total_size_mb": 15.3,
        "cache_hits": 128, "cache_misses": 42, "hit_rate": "75.3%", "ttl_hours": 24,
    }})
    cached_files: int = Field(description="Кількість файлів у кеші")
    total_size_mb: float = Field(description="Розмір кешу (МБ)")
    cache_hits: int = Field(description="Кількість cache hit")
    cache_misses: int = Field(description="Кількість cache miss")
    hit_rate: str = Field(description="Відсоток cache hit")
    ttl_hours: int = Field(description="TTL кешу (години)")


class ServerConfig(BaseModel):
    """Конфігурація сервера."""
    model_config = ConfigDict(json_schema_extra={"example": {
        "max_concurrent": 100, "grpc_clients": 5, "session_timeout_sec": 300,
        "silence_between_chunks_ms": 150, "audio_format": "WAV 8kHz 16bit mono",
    }})
    max_concurrent: int = Field(description="Макс. паралельних запитів")
    grpc_clients: int = Field(description="Кількість gRPC каналів")
    session_timeout_sec: int = Field(description="Таймаут неактивної сесії (с)")
    silence_between_chunks_ms: int = Field(description="Тиша між частинами (мс)")
    audio_format: str = Field(description="Формат аудіо")


class StatusResponse(BaseModel):
    """Відповідь статусу сервера."""
    model_config = ConfigDict(json_schema_extra={"example": {
        "status": "running", "total_requests": 156, "active_sessions": 1,
        "sessions": {"call-12345_billing_1": {
            "session_id": "call-12345", "comp_schema": "billing_1",
            "age_sec": 120, "idle_sec": 15, "request_count": 8,
            "total_chars": 1250, "timeout_in": 285,
        }},
        "voices": ["Leda", "Puck", "Kore", "Aoede", "Charon", "Fenrir"],
        "locales": ["en_US", "es_ES", "pl_PL", "ru_RU", "tr_TR", "uk_UA"],
        "cache": {"cached_files": 42, "total_size_mb": 15.3, "cache_hits": 128, "cache_misses": 42, "hit_rate": "75.3%", "ttl_hours": 24},
        "config": {"max_concurrent": 100, "grpc_clients": 5, "session_timeout_sec": 300, "silence_between_chunks_ms": 150, "audio_format": "WAV 8kHz 16bit mono"},
    }})
    status: str = Field(description="Статус")
    total_requests: int = Field(description="Загальна кількість запитів з моменту запуску")
    active_sessions: int = Field(description="Кількість відкритих сесій")
    sessions: dict[str, SessionDetail] = Field(default={}, description="Активні сесії (ключ = session_key)")
    voices: list[str] = Field(description="Доступні голоси")
    locales: list[str] = Field(description="Підтримувані locale")
    cache: CacheStats = Field(description="Статистика кешу")
    config: ServerConfig = Field(description="Конфігурація сервера")


class ErrorResponse(BaseModel):
    """Відповідь з помилкою (400, 404, 500)."""
    model_config = ConfigDict(json_schema_extra={"example": {
        "error": "Unsupported locale: 'fr_FR'. Supported: en_US, es_ES, pl_PL, ru_RU, tr_TR, uk_UA",
    }})
    error: str = Field(description="Опис помилки")


class AuthErrorResponse(BaseModel):
    """Помилка авторизації (401)."""
    model_config = ConfigDict(json_schema_extra={"example": {"detail": "Invalid API key"}})
    detail: str = Field(description="Опис помилки авторизації")


class ValidationErrorDetail(BaseModel):
    """Деталь помилки валідації."""
    type: str = Field(description="Тип помилки")
    loc: list = Field(description="Шлях до поля")
    msg: str = Field(description="Повідомлення")
    input: dict = Field(default={}, description="Отримані дані")


class ValidationErrorResponse(BaseModel):
    """Помилка валідації полів (422)."""
    model_config = ConfigDict(json_schema_extra={"example": {
        "detail": [{"type": "missing", "loc": ["body", "session_id"], "msg": "Field required", "input": {"comp_schema": "billing_1"}}],
    }})
    detail: list[ValidationErrorDetail] = Field(description="Список помилок валідації")


# --- Загальні responses для Swagger/ReDoc ---
RESP_401 = {
    "model": AuthErrorResponse,
    "description": (
        "**Помилка авторизації**\n\n"
        "| Ситуація | Відповідь | Як виправити |\n"
        "|----------|-----------|-------------|\n"
        "| Відсутній заголовок `Authorization` | `Not authenticated` | Додайте заголовок `Authorization: Bearer <ваш_ключ>` |\n"
        "| Ключ без префіксу `Bearer` | `Not authenticated` | Формат: `Bearer <ключ>`, а не просто ключ |\n"
        "| Порожній Bearer токен | `Not authenticated` | Вкажіть ключ після `Bearer ` |\n"
        "| Невірний API ключ | `Invalid API key` | Перевірте значення TGC_API_KEY у .env на сервері |\n"
    ),
    "content": {
        "application/json": {
            "examples": {
                "no_header": {
                    "summary": "Немає заголовка Authorization",
                    "value": {"detail": "Not authenticated"},
                },
                "invalid_key": {
                    "summary": "Невірний API ключ",
                    "value": {"detail": "Invalid API key"},
                },
            }
        }
    },
}

RESP_422 = {
    "model": ValidationErrorResponse,
    "description": (
        "**Помилка валідації запиту**\n\n"
        "| Ситуація | Поле `type` | Як виправити |\n"
        "|----------|------------|-------------|\n"
        "| Пропущене обов'язкове поле | `missing` | Додайте поле, вказане в `loc` (наприклад `session_id`) |\n"
        "| Невірний тип даних | `string_type` | Передайте значення як рядок |\n"
        "| Порожній текст (min_length=1) | `string_too_short` | Передайте непорожній `text` |\n"
        "| Невалідний JSON | `json_invalid` | Перевірте синтаксис JSON у тілі запиту |\n"
        "| Невірний Content-Type | `model_attributes_type` | Використовуйте `Content-Type: application/json` |\n"
    ),
    "content": {
        "application/json": {
            "examples": {
                "missing_field": {
                    "summary": "Пропущене поле session_id",
                    "value": {"detail": [{"type": "missing", "loc": ["body", "session_id"], "msg": "Field required", "input": {"comp_schema": "billing_1"}}]},
                },
                "malformed_json": {
                    "summary": "Невалідний JSON",
                    "value": {"detail": [{"type": "json_invalid", "loc": ["body", 37], "msg": "JSON decode error", "input": {}, "ctx": {"error": "Expecting value"}}]},
                },
                "wrong_content_type": {
                    "summary": "Невірний Content-Type (text/plain замість application/json)",
                    "value": {"detail": [{"type": "model_attributes_type", "loc": ["body"], "msg": "Input should be a valid dictionary or object to extract fields from", "input": "raw string"}]},
                },
            }
        }
    },
}


# --- FastAPI app ---
app = create_app(
    service_name=SERVICE_NAME,
    title="TTS Google Chirp3-HD API",
    description="Синтез мовлення через Google Chirp3-HD з паралельною генерацією та кешуванням",
    version="1.0.0",
    include_health=False,
)


# --- Healthcheck при старті ---
def _verify_google_credentials():
    """Тестовий запит до Google TTS API — перевірка credentials."""
    from google.cloud import texttospeech
    client = texttospeech.TextToSpeechClient()
    client.synthesize_speech(
        input=texttospeech.SynthesisInput(text="ok"),
        voice=texttospeech.VoiceSelectionParams(
            language_code="uk-UA", name="uk-UA-Chirp3-HD-Leda",
        ),
        audio_config=texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.LINEAR16,
            sample_rate_hertz=8000,
        ),
    )
    client.transport.close()


# --- Startup / Shutdown ---
@app.on_event("startup")
async def startup():
    set_statusline(SERVICE_NAME, port=PORT, status="Running")

    # --- Перевірка конфігурації ---
    if not API_KEY:
        logger.warning("TGC_API_KEY не встановлено — авторизація вимкнена!")

    creds_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")
    if not creds_path:
        logger.error("GOOGLE_APPLICATION_CREDENTIALS не встановлено — TTS не працюватиме!")
    elif not os.path.exists(creds_path):
        logger.error(f"Google credentials файл не знайдено: {creds_path}")
    else:
        # Тестовий запит до Google TTS API
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(tts_engine.executor, _verify_google_credentials)
            logger.info("Google TTS API credentials — OK")
        except Exception as e:
            logger.error(f"Google TTS API credentials — ПОМИЛКА: {type(e).__name__}: {str(e)[:200]}")

    logger.info(f"Порт: {PORT}")
    logger.info(f"Голоси: {', '.join(tts_engine.VOICE_NAMES)}")
    logger.info(f"Locales: {', '.join(sorted(tts_engine.SUPPORTED_LOCALES))}")
    logger.info(f"gRPC каналів: {tts_engine.GRPC_CLIENTS}")
    logger.info(f"Таймаут сесії: {tts_engine.SESSION_TIMEOUT}с")
    logger.info(f"Кеш TTL: {tts_engine.CACHE_TTL // 3600}г")
    existing = tts_engine.cache_stats()
    logger.info(f"Кеш файлів: {existing['cached_files']} ({existing['total_size_mb']} MB)")
    logger.info(f"Біллінг: {'enabled → ' + BILLING_URL if BILLING_URL else 'disabled (TGC_BILLING_URL not set)'}")
    asyncio.create_task(_session_watchdog())


@app.on_event("shutdown")
async def shutdown():
    tts_engine.shutdown_global_clients()


# --- Біллінг (fire-and-forget) ---
async def _send_billing(comp_schema: str, text: str):
    """Fire-and-forget: логування в біллінг. Не блокує відповідь TTS."""
    if not BILLING_URL:
        return
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                BILLING_URL,
                json={
                    "comp_schema": comp_schema,
                    "text": text,
                },
            )
            if resp.status_code == 200:
                logger.debug(f"Billing OK: {comp_schema} | {len(text)} chars")
            else:
                logger.error(f"Billing FAILED (HTTP {resp.status_code}) comp_schema={comp_schema}: {resp.text[:500]}")
    except Exception as e:
        logger.error(f"Billing FAILED (network) comp_schema={comp_schema}: {type(e).__name__}: {str(e)[:200]}")


# --- Background watchdog ---
async def _session_watchdog():
    """Закриває неактивні сесії + чистить кеш."""
    cache_check_counter = 0
    while True:
        await asyncio.sleep(30)
        now = time.time()
        expired = [
            sid for sid, s in sessions.items()
            if now - s["last_activity"] > tts_engine.SESSION_TIMEOUT
        ]
        for sid in expired:
            logger.info(f"Сесія {sid} — таймаут {tts_engine.SESSION_TIMEOUT}с без активності")
            _cleanup_session(sid)
        cache_check_counter += 30
        if cache_check_counter >= 1800:
            cache_check_counter = 0
            removed = tts_engine.cache_cleanup()
            if removed > 0:
                logger.info(f"Кеш: видалено {removed} файлів (TTL {tts_engine.CACHE_TTL // 3600}г)")


def _cleanup_session(session_key: str):
    if session_key in sessions:
        s = sessions.pop(session_key)
        logger.info(
            f"Сесія {session_key} закрита "
            f"(запитів: {s['request_count']}, тривалість: {int(time.time() - s['created'])}с)"
        )
        if not sessions:
            tts_engine.shutdown_global_clients()


# --- Health check (розширений) ---
@app.get(
    f"/api/{SERVICE_NAME}/health",
    response_model=HealthResponse,
    responses={
        200: {
            "description": (
                "**Сервіс працює**\n\n"
                "Авторизація не потрібна. Повертає статус сервісу, готовність gRPC та кількість активних сесій.\n\n"
                "| Поле | Опис |\n"
                "|------|------|\n"
                "| `status` | Завжди `ok` якщо сервіс працює |\n"
                "| `grpc_ready` | `true` — gRPC прогрітий, `false` — ще не було жодного /open |\n"
                "| `grpc_clients` | Кількість активних gRPC каналів (0–5) |\n"
                "| `active_sessions` | Кількість відкритих TTS-сесій |\n"
            ),
        },
    },
)
async def health():
    """Health check — перевірка доступності сервісу (без авторизації)."""
    return HealthResponse(
        status="ok",
        service=SERVICE_NAME,
        version="1.0.0",
        grpc_ready=tts_engine.grpc_ready,
        grpc_clients=len(tts_engine.warm_clients),
        active_sessions=len(sessions),
    )


# --- POST /open ---
@app.post(
    f"/api/{SERVICE_NAME}/open",
    response_model=OpenResponse,
    responses={
        200: {
            "description": (
                "**Сесія успішно відкрита**\n\n"
                "При першому виклику прогріває gRPC-канали (~3-5 сек). Наступні виклики — миттєві.\n\n"
                "| Поле | Опис |\n"
                "|------|------|\n"
                "| `session_key` | Унікальний ключ: `{session_id}_{comp_schema}` — використовується внутрішньо |\n"
                "| `startup_ms` | Час відкриття (перший раз ~3000мс, далі ~0мс) |\n"
                "| `timeout_sec` | Час неактивності до автозакриття сесії (300с = 5 хв) |\n"
            ),
        },
        401: RESP_401,
        422: RESP_422,
        500: {
            "model": ErrorResponse,
            "description": (
                "**Помилка прогріву gRPC**\n\n"
                "| Ситуація | Причина | Як виправити |\n"
                "|----------|---------|-------------|\n"
                "| `ServiceUnavailable` | Немає доступу до Google Cloud API | Перевірте мережу сервера та доступ до `texttospeech.googleapis.com` |\n"
                "| `DefaultCredentialsError` | Не знайдено Google credentials | Перевірте `TGC_GOOGLE_CREDENTIALS` у .env та наявність файлу |\n"
                "| `PermissionDenied` | Сервісний акаунт не має прав | Увімкніть Cloud Text-to-Speech API у Google Cloud Console |\n"
                "| `Timeout` | gRPC канали не відповідають | Спробуйте повторити запит через 10-30 секунд |\n"
            ),
            "content": {"application/json": {"example": {"error": "gRPC warmup failed: DefaultCredentialsError: Could not automatically determine credentials"}}},
        },
    },
    dependencies=[Depends(require_auth(API_KEY))],
)
async def open_session(body: OpenRequest):
    """Відкрити TTS-сесію. Прогріває gRPC при першому виклику."""
    t0 = time.time()
    session_key = f"{body.session_id}_{body.comp_schema}"

    logger.info(f"POST /open — session_id: {body.session_id}, comp_schema: {body.comp_schema}")

    if not tts_engine.grpc_ready:
        logger.info("gRPC не прогрітий — запускаю прогрів...")
        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(tts_engine.executor, tts_engine.warmup_global_clients)
        except Exception as e:
            logger.error(f"gRPC warmup failed: {e}")
            return JSONResponse(
                status_code=500,
                content={"error": f"gRPC warmup failed: {type(e).__name__}: {str(e)[:200]}"},
            )
    else:
        logger.info(f"gRPC: {len(tts_engine.warm_clients)} каналів (вже прогріті)")

    sessions[session_key] = {
        "created": time.time(),
        "last_activity": time.time(),
        "session_id": body.session_id,
        "comp_schema": body.comp_schema,
        "request_count": 0,
        "total_gen_ms": 0,
        "total_chars": 0,
    }

    startup_ms = int((time.time() - t0) * 1000)
    logger.info(f"Сесія {session_key} готова за {startup_ms}мс")

    return OpenResponse(
        status="ready",
        session_id=body.session_id,
        comp_schema=body.comp_schema,
        session_key=session_key,
        startup_ms=startup_ms,
        voices=tts_engine.VOICE_NAMES,
        timeout_sec=tts_engine.SESSION_TIMEOUT,
    )


# --- POST /generate ---
@app.post(
    f"/api/{SERVICE_NAME}/generate",
    responses={
        200: {
            "description": (
                "**Аудіо успішно згенеровано**\n\n"
                "Повертає binary WAV (8kHz, 16bit, mono). Метадані у заголовках відповіді:\n\n"
                "| Заголовок | Опис | Приклад |\n"
                "|-----------|------|--------|\n"
                "| `X-TTS-Total-Ms` | Загальний час обробки (мс) | `450` |\n"
                "| `X-TTS-Gen-Ms` | Час генерації Google API (мс) | `380` |\n"
                "| `X-TTS-Parts` | Кількість частин (речень) | `3` |\n"
                "| `X-TTS-Audio-Sec` | Тривалість аудіо (сек) | `2.45` |\n"
                "| `X-TTS-Cache` | `HIT` — з кешу, `MISS` — нова генерація | `MISS` |\n"
                "| `X-TTS-Voice` | Голос | `Leda` |\n"
                "| `X-TTS-Locale` | Locale | `uk_UA` |\n"
            ),
        },
        400: {
            "model": ErrorResponse,
            "description": (
                "**Невірні параметри запиту**\n\n"
                "| Ситуація | Приклад відповіді | Причина | Як виправити |\n"
                "|----------|-------------------|---------|-------------|\n"
                "| Непідтримувана locale | `Unsupported locale: 'fr_FR'` | Locale відсутня у списку підтримуваних | Використовуйте: `uk_UA`, `ru_RU`, `en_US`, `pl_PL`, `es_ES`, `tr_TR` |\n"
                "| Невірний регістр locale | `Unsupported locale: 'UK_ua'` | Locale чутлива до регістру | Використовуйте точний формат: `uk_UA` (не `UK_ua`) |\n"
                "| Порожня locale | `Unsupported locale: ''` | Передано порожній рядок | Вкажіть locale або не передавайте поле (default: `uk_UA`) |\n"
                "| Сесія не існує | `Invalid session...` | Не було виклику POST /open | Спершу відкрийте сесію: `POST /open` з тими ж `session_id` + `comp_schema` |\n"
                "| Сесія протухла | `Invalid session...` | Пройшло >5 хвилин без активності | Відкрийте нову сесію: `POST /open` |\n\n"
                "**Примітка:** формат `uk-UA` (з дефісом) автоматично нормалізується в `uk_UA` і працює коректно.\n"
            ),
            "content": {
                "application/json": {
                    "examples": {
                        "bad_locale": {
                            "summary": "Непідтримувана locale",
                            "value": {"error": "Unsupported locale: 'fr_FR'. Supported: en_US, es_ES, pl_PL, ru_RU, tr_TR, uk_UA"},
                        },
                        "no_session": {
                            "summary": "Сесія не існує або протухла",
                            "value": {"error": "Invalid session. session_id='call-123', comp_schema='billing_1'. Call POST /open first."},
                        },
                    }
                }
            },
        },
        401: RESP_401,
        422: RESP_422,
        500: {
            "model": ErrorResponse,
            "description": (
                "**Помилка Google TTS API**\n\n"
                "| Ситуація | Причина | Як виправити |\n"
                "|----------|---------|-------------|\n"
                "| `ResourceExhausted` | Вичерпано квоту Google Cloud TTS | Перевірте ліміти в Google Cloud Console > Quotas |\n"
                "| `InvalidArgument` | Google не може синтезувати текст | Перевірте текст — пробіли, спец. символи, занадто короткий |\n"
                "| `ServiceUnavailable` | Google API тимчасово недоступний | Повторіть запит через 5-10 секунд |\n"
                "| `DeadlineExceeded` | Таймаут генерації | Скоротіть текст або повторіть запит |\n"
            ),
            "content": {
                "application/json": {
                    "examples": {
                        "quota": {
                            "summary": "Вичерпано квоту",
                            "value": {"error": "TTS generation failed: ResourceExhausted: Quota exceeded for quota metric 'characters' of service 'texttospeech.googleapis.com'"},
                        },
                        "bad_text": {
                            "summary": "Невалідний текст для синтезу",
                            "value": {"error": "TTS generation failed: InvalidArgument: Request contains an invalid argument"},
                        },
                    }
                }
            },
        },
    },
    dependencies=[Depends(require_auth(API_KEY))],
)
async def generate(body: GenerateRequest):
    """Згенерувати аудіо (WAV 8kHz 16bit mono). Повертає бінарний WAV з метаданими в заголовках."""
    global request_counter
    t_received = time.time()
    request_counter += 1

    locale = tts_engine.normalize_locale(body.locale)

    if locale not in tts_engine.SUPPORTED_LOCALES:
        return JSONResponse(
            status_code=400,
            content={"error": f"Unsupported locale: '{body.locale}'. Supported: {', '.join(sorted(tts_engine.SUPPORTED_LOCALES))}"},
        )

    session_key = f"{body.session_id}_{body.comp_schema}"
    if not body.session_id or session_key not in sessions:
        return JSONResponse(
            status_code=400,
            content={"error": f"Invalid session. session_id='{body.session_id}', comp_schema='{body.comp_schema}'. Call POST /open first."},
        )

    google_locale = tts_engine.to_google_locale(locale)
    session = sessions[session_key]
    session["last_activity"] = time.time()
    session["request_count"] += 1
    voice_name = tts_engine.get_voice_name(body.voice, locale)

    logger.info(
        f"POST /generate — session: {body.session_id} | "
        f"locale: {locale} | voice: {body.voice} ({voice_name}) | "
        f"text: \"{body.text[:80]}\" ({len(body.text)} сим)"
    )

    # --- Кеш ---
    ckey = tts_engine.cache_key(body.text, body.voice, locale)
    cached_wav = tts_engine.cache_get(ckey)

    if cached_wav is not None:
        tts_engine.cache_hits += 1
        total_ms = (time.time() - t_received) * 1000
        total_audio_sec = (len(cached_wav) - 44) / (8000 * 2)
        session["total_chars"] += len(body.text)
        asyncio.create_task(_send_billing(body.comp_schema, body.text))
        logger.info(f"CACHE HIT: {ckey[:12]}... | {total_ms:.1f}мс | {len(cached_wav):,} bytes")
        return Response(
            content=cached_wav,
            media_type="audio/wav",
            headers={
                "X-TTS-Session": session_key,
                "X-TTS-Comp-Schema": body.comp_schema,
                "X-TTS-Total-Ms": str(int(total_ms)),
                "X-TTS-Gen-Ms": "0",
                "X-TTS-Parts": "0",
                "X-TTS-Audio-Sec": str(round(total_audio_sec, 2)),
                "X-TTS-Text-Len": str(len(body.text)),
                "X-TTS-Voice": body.voice,
                "X-TTS-Locale": locale,
                "X-TTS-Cache": "HIT",
            },
        )

    # --- CACHE MISS ---
    tts_engine.cache_misses += 1

    parts = tts_engine.split_sentences(body.text)
    total_parts = len(parts)
    logger.info(f"CACHE MISS — генерація {total_parts} частин...")

    loop = asyncio.get_event_loop()
    futures = []
    for i, part_text in enumerate(parts):
        future = loop.run_in_executor(
            tts_engine.executor,
            tts_engine.generate_tts_part, part_text, voice_name, google_locale, i,
        )
        futures.append(future)

    t_gen = time.time()
    try:
        results = await asyncio.gather(*futures)
    except Exception as e:
        logger.error(f"Google TTS API error: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": f"TTS generation failed: {type(e).__name__}: {str(e)[:200]}"},
        )
    gen_ms = (time.time() - t_gen) * 1000

    silence = b'\x00\x00' * int(8000 * tts_engine.SILENCE_MS / 1000)
    all_pcm = b''
    total_audio_sec = 0.0

    for i, (pcm, part_gen_time, part_chars, audio_sec) in enumerate(results):
        if i < total_parts - 1:
            pcm = pcm + silence
        all_pcm += pcm
        total_audio_sec += audio_sec

    wav_data = tts_engine.wrap_pcm_to_wav(all_pcm)
    tts_engine.cache_put(ckey, wav_data)

    total_ms = (time.time() - t_received) * 1000
    session["total_gen_ms"] += int(gen_ms)
    session["total_chars"] += len(body.text)
    asyncio.create_task(_send_billing(body.comp_schema, body.text))

    logger.info(
        f"РЕЗУЛЬТАТ: {len(body.text)} сим | {total_parts} частин | "
        f"gen: {gen_ms:.0f}мс | total: {total_ms:.0f}мс | "
        f"audio: {total_audio_sec:.2f}с | {len(wav_data):,} bytes | CACHED"
    )

    return Response(
        content=wav_data,
        media_type="audio/wav",
        headers={
            "X-TTS-Session": session_key,
            "X-TTS-Comp-Schema": body.comp_schema,
            "X-TTS-Total-Ms": str(int(total_ms)),
            "X-TTS-Gen-Ms": str(int(gen_ms)),
            "X-TTS-Parts": str(total_parts),
            "X-TTS-Audio-Sec": str(round(total_audio_sec, 2)),
            "X-TTS-Text-Len": str(len(body.text)),
            "X-TTS-Voice": body.voice,
            "X-TTS-Locale": locale,
            "X-TTS-Cache": "MISS",
        },
    )


# --- POST /close ---
@app.post(
    f"/api/{SERVICE_NAME}/close",
    response_model=CloseResponse,
    responses={
        200: {
            "description": (
                "**Сесія успішно закрита**\n\n"
                "gRPC канали автоматично закриваються коли остання сесія закривається.\n"
                "Повторний виклик /close для тієї ж сесії поверне 404.\n"
            ),
        },
        401: RESP_401,
        404: {
            "model": ErrorResponse,
            "description": (
                "**Сесія не знайдена**\n\n"
                "| Ситуація | Причина | Як виправити |\n"
                "|----------|---------|-------------|\n"
                "| Сесія вже закрита | Повторний виклик /close | Ігноруйте — сесія вже закрита, це не помилка |\n"
                "| Сесія не існувала | Не було виклику /open з такими параметрами | Перевірте `session_id` та `comp_schema` |\n"
                "| Сесія протухла (таймаут) | Минуло >5 хвилин без активності | Сесія автоматично закрита сервером — нічого робити не потрібно |\n"
            ),
            "content": {"application/json": {"example": {"error": "Session not found: session_id='call-123', comp_schema='billing_1'"}}},
        },
        422: RESP_422,
    },
    dependencies=[Depends(require_auth(API_KEY))],
)
async def close_session(body: CloseRequest):
    """Закрити TTS-сесію."""
    session_key = f"{body.session_id}_{body.comp_schema}"

    if session_key in sessions:
        s = sessions[session_key]
        logger.info(
            f"POST /close — {session_key} | "
            f"тривалість: {int(time.time() - s['created'])}с | "
            f"запитів: {s['request_count']} | символів: {s['total_chars']}"
        )
        _cleanup_session(session_key)
        return CloseResponse(
            status="closed",
            session_id=body.session_id,
            comp_schema=body.comp_schema,
        )
    else:
        return JSONResponse(
            status_code=404,
            content={"error": f"Session not found: session_id='{body.session_id}', comp_schema='{body.comp_schema}'"},
        )


# --- GET /status ---
@app.get(
    f"/api/{SERVICE_NAME}/status",
    response_model=StatusResponse,
    responses={
        200: {
            "description": (
                "**Статус сервера**\n\n"
                "Повертає повну інформацію про стан сервісу:\n\n"
                "| Поле | Опис |\n"
                "|------|------|\n"
                "| `status` | Завжди `running` |\n"
                "| `total_requests` | Загальна кількість запитів /generate з моменту запуску |\n"
                "| `active_sessions` | Кількість відкритих сесій |\n"
                "| `sessions` | Деталі по кожній сесії (вік, idle, запити, символи, таймаут) |\n"
                "| `cache` | Статистика кешу: файли, розмір, hit/miss ratio |\n"
                "| `voices` | Список доступних голосів |\n"
                "| `locales` | Список підтримуваних локалей |\n"
                "| `config` | Поточна конфігурація: max_concurrent, grpc_clients, timeout |\n"
            ),
        },
        401: RESP_401,
        422: RESP_422,
    },
    dependencies=[Depends(require_auth(API_KEY))],
)
async def status():
    """Статус сервера — сесії, кеш, конфігурація (потребує авторизації)."""
    now = time.time()
    active = {}
    for sid, s in sessions.items():
        active[sid] = SessionDetail(
            session_id=s["session_id"],
            comp_schema=s["comp_schema"],
            age_sec=int(now - s["created"]),
            idle_sec=int(now - s["last_activity"]),
            request_count=s["request_count"],
            total_chars=s["total_chars"],
            timeout_in=max(0, tts_engine.SESSION_TIMEOUT - int(now - s["last_activity"])),
        )

    cs = tts_engine.cache_stats()

    return StatusResponse(
        status="running",
        total_requests=request_counter,
        active_sessions=len(sessions),
        sessions=active,
        voices=tts_engine.VOICE_NAMES,
        locales=sorted(tts_engine.SUPPORTED_LOCALES),
        cache=CacheStats(**cs),
        config=ServerConfig(
            max_concurrent=tts_engine.MAX_CONCURRENT,
            grpc_clients=tts_engine.GRPC_CLIENTS,
            session_timeout_sec=tts_engine.SESSION_TIMEOUT,
            silence_between_chunks_ms=tts_engine.SILENCE_MS,
            audio_format="WAV 8kHz 16bit mono",
        ),
    )


# --- Запуск ---
if __name__ == '__main__':
    run_service(app, port=PORT, service_name=SERVICE_NAME)
