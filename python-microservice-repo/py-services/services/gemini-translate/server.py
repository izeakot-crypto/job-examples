#!/usr/bin/env python3
"""
Gemini Translate — пакетний сервіс перекладу JSON через Google Gemini API.

Endpoints:
  POST /api/gemini-translate/translate  — перекласти масив рядків
  GET  /api/gemini-translate/health     — health check (без авторизації)

Сервіс приймає JSON-масив об'єктів {"original": "...", "translation": ""}
(той самий формат що використовує CLI-скрипт translate_json_final.py)
і повертає масив із заповненими полями "translation".

Підтримувані коди мов: en, uk, ru, de, fr, es, it, pl, pt, tr, ar, zh, ja, ko, ka, kk, ro
"""
import asyncio
import os

from fastapi import Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from shared.auth import require_auth
from shared.base_service import create_app, run_service
from shared.logger import get_logger
from shared.statusline import set_statusline

from .translator import LANGUAGE_CODES, translate_batch

# ---------------------------------------------------------------------------
# Конфігурація
# ---------------------------------------------------------------------------

SERVICE_NAME = "gemini-translate"
PORT = int(os.environ.get("GT_PORT", 8594))
API_KEY = os.environ.get("GT_API_KEY", "")
DISCORD_WEBHOOK = os.environ.get("GT_DISCORD_WEBHOOK", "")

GEMINI_API_KEY = os.environ.get("GT_GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GT_GEMINI_MODEL", "gemini-2.5-pro")
BATCH_SIZE = int(os.environ.get("GT_BATCH_SIZE", 200))
MAX_RETRIES = int(os.environ.get("GT_MAX_RETRIES", 8))
SLEEP_BETWEEN_BATCHES = int(os.environ.get("GT_SLEEP_BETWEEN_BATCHES", 30))
SLEEP_BETWEEN_RETRIES = int(os.environ.get("GT_SLEEP_BETWEEN_RETRIES", 10))

logger = get_logger(SERVICE_NAME, discord_webhook=DISCORD_WEBHOOK)

# ---------------------------------------------------------------------------
# Pydantic-моделі для Swagger/ReDoc
# ---------------------------------------------------------------------------


class TranslationItem(BaseModel):
    """Один елемент перекладу — відповідає формату CLI-скрипту."""

    model_config = ConfigDict(json_schema_extra={
        "example": {"original": "Ошибка выхода из PCP", "translation": ""},
    })

    original: str = Field(description="Оригінальний рядок для перекладу")
    translation: str = Field(default="", description="Результат перекладу (заповнює сервіс)")


class TranslateRequest(BaseModel):
    """Тіло запиту для /translate."""

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "lang": "de",
            "items": [
                {"original": "Ошибка выхода из PCP", "translation": ""},
                {"original": "Входящий звонок", "translation": ""},
            ],
        },
    })

    lang: str = Field(
        description=(
            "Код цільової мови. Підтримувані: "
            + ", ".join(sorted(LANGUAGE_CODES.keys()))
        )
    )
    items: list[TranslationItem] = Field(
        description=(
            "Масив елементів перекладу. "
            "Елементи з непорожнім полем `translation` пропускаються — "
            "повертаються без змін (resume-режим)."
        )
    )


class ValidationFailure(BaseModel):
    """Деталі елемента, що не пройшов валідацію після всіх спроб."""

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "index": 2,
            "original": "Error %s occurred",
            "translation": "Fehler aufgetreten",
            "error": "Format symbols mismatch — expected: {'%s': 1}, got: {}",
        },
    })

    index: int = Field(description="Індекс елемента у вхідному масиві `items`")
    original: str = Field(description="Оригінальний рядок")
    translation: str = Field(description="Отриманий переклад (може бути некоректним)")
    error: str = Field(description="Опис помилки валідації")


class TranslateResponse(BaseModel):
    """Відповідь /translate."""

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "items": [
                {"original": "Ошибка выхода из PCP", "translation": "PCP-Abmeldefehler"},
                {"original": "Входящий звонок", "translation": "Eingehender Anruf"},
            ],
            "total": 2,
            "translated": 2,
            "skipped": 0,
            "validation_failures": [],
        },
    })

    items: list[TranslationItem] = Field(
        description="Вхідний масив із заповненими полями `translation`"
    )
    total: int = Field(description="Загальна кількість елементів у запиті")
    translated: int = Field(description="Кількість елементів, відправлених у Gemini")
    skipped: int = Field(
        description="Кількість пропущених елементів (поле `translation` вже було заповнене)"
    )
    validation_failures: list[ValidationFailure] = Field(
        description=(
            "Елементи, що не пройшли валідацію після всіх спроб. "
            "HTTP-статус залишається 200 — переклад повертається навіть при часткових помилках."
        )
    )


class HealthResponse(BaseModel):
    """Відповідь health check."""

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "status": "ok",
            "service": "gemini-translate",
            "version": "1.0.0",
            "gemini_model": "gemini-2.5-pro",
            "gemini_key_set": True,
        },
    })

    status: str = Field(description="Статус сервісу — `ok` якщо запущений")
    service: str = Field(description="Назва сервісу")
    version: str = Field(description="Версія сервісу")
    gemini_model: str = Field(description="Модель Gemini (змінна GT_GEMINI_MODEL)")
    gemini_key_set: bool = Field(
        description="Чи встановлено GT_GEMINI_API_KEY. `false` → /translate поверне 503"
    )


class ErrorResponse(BaseModel):
    """Відповідь з помилкою (400, 503)."""

    model_config = ConfigDict(json_schema_extra={"example": {
        "detail": "Unknown language code 'xx'. Supported: ['ar', 'de', 'en', ...]",
    }})
    detail: str = Field(description="Опис помилки")


class AuthErrorResponse(BaseModel):
    """Помилка авторизації (401)."""

    model_config = ConfigDict(json_schema_extra={"example": {"detail": "Invalid API key"}})
    detail: str = Field(description="Опис помилки авторизації")


class ValidationErrorDetail(BaseModel):
    """Деталь помилки валідації Pydantic."""
    type: str = Field(description="Тип помилки")
    loc: list = Field(description="Шлях до поля")
    msg: str = Field(description="Повідомлення")
    input: dict = Field(default={}, description="Отримані дані")


class ValidationErrorResponse(BaseModel):
    """Помилка валідації полів запиту (422)."""

    model_config = ConfigDict(json_schema_extra={"example": {
        "detail": [{"type": "missing", "loc": ["body", "lang"], "msg": "Field required", "input": {}}],
    }})
    detail: list[ValidationErrorDetail] = Field(description="Список помилок валідації")


# ---------------------------------------------------------------------------
# Загальні responses для Swagger/ReDoc
# ---------------------------------------------------------------------------

RESP_401 = {
    "model": AuthErrorResponse,
    "description": (
        "**Помилка авторизації**\n\n"
        "| Ситуація | Відповідь | Як виправити |\n"
        "|----------|-----------|-------------|\n"
        "| Відсутній заголовок `Authorization` | `Not authenticated` | Додайте заголовок `Authorization: Bearer <GT_API_KEY>` |\n"
        "| Ключ без префіксу `Bearer` | `Not authenticated` | Формат: `Bearer <ключ>`, а не просто ключ |\n"
        "| Порожній Bearer токен | `Not authenticated` | Вкажіть ключ після `Bearer ` |\n"
        "| Невірний API ключ | `Invalid API key` | Перевірте значення GT_API_KEY у .env на сервері |\n"
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
        "**Помилка валідації запиту (Pydantic)**\n\n"
        "| Ситуація | Поле `type` | Як виправити |\n"
        "|----------|------------|-------------|\n"
        "| Пропущене обов'язкове поле `lang` | `missing` | Додайте поле `lang` з кодом мови |\n"
        "| Пропущене обов'язкове поле `items` | `missing` | Додайте поле `items` — масив об'єктів |\n"
        "| Пропущене поле `original` в елементі | `missing` | Кожен елемент масиву повинен мати поле `original` |\n"
        "| Невірний тип `items` (не масив) | `list_type` | Передайте `items` як JSON-масив `[...]` |\n"
        "| Невалідний JSON | `json_invalid` | Перевірте синтаксис JSON у тілі запиту |\n"
        "| Невірний Content-Type | `model_attributes_type` | Використовуйте `Content-Type: application/json` |\n"
    ),
    "content": {
        "application/json": {
            "examples": {
                "missing_lang": {
                    "summary": "Пропущене поле lang",
                    "value": {"detail": [{"type": "missing", "loc": ["body", "lang"], "msg": "Field required", "input": {"items": []}}]},
                },
                "missing_original": {
                    "summary": "Пропущене поле original в елементі",
                    "value": {"detail": [{"type": "missing", "loc": ["body", "items", 0, "original"], "msg": "Field required", "input": {"translation": ""}}]},
                },
                "malformed_json": {
                    "summary": "Невалідний JSON",
                    "value": {"detail": [{"type": "json_invalid", "loc": ["body", 10], "msg": "JSON decode error", "input": {}}]},
                },
            }
        }
    },
}

RESP_400 = {
    "model": ErrorResponse,
    "description": (
        "**Помилка запиту**\n\n"
        "| Ситуація | Приклад `detail` | Як виправити |\n"
        "|----------|-----------------|-------------|\n"
        "| Невідомий код мови | `Unknown language code 'xx'. Supported: ['ar', 'de', ...]` | Використовуйте один із підтримуваних кодів: `ar, de, en, es, fr, it, ja, ka, kk, ko, pl, pt, ro, ru, tr, uk, zh` |\n"
        "| Порожній масив `items` | `items list is empty` | Передайте хоча б один елемент у масиві `items` |\n"
    ),
    "content": {
        "application/json": {
            "examples": {
                "unknown_lang": {
                    "summary": "Невідомий код мови",
                    "value": {"detail": "Unknown language code 'xx'. Supported: ['ar', 'de', 'en', 'es', 'fr', 'it', 'ja', 'ka', 'kk', 'ko', 'pl', 'pt', 'ro', 'ru', 'tr', 'uk', 'zh']"},
                },
                "empty_items": {
                    "summary": "Порожній масив items",
                    "value": {"detail": "items list is empty"},
                },
            }
        }
    },
}

RESP_503 = {
    "model": ErrorResponse,
    "description": (
        "**Сервіс недоступний**\n\n"
        "| Ситуація | Причина | Як виправити |\n"
        "|----------|---------|-------------|\n"
        "| `GT_GEMINI_API_KEY` не встановлено | Ключ Gemini API відсутній у `.env` на сервері | Додайте `GT_GEMINI_API_KEY=AIza...` в `/opt/py-services/.env` та перезапустіть контейнер |\n"
    ),
    "content": {
        "application/json": {
            "examples": {
                "no_api_key": {
                    "summary": "Gemini API ключ не налаштований",
                    "value": {"detail": "Gemini API key is not configured"},
                },
            }
        }
    },
}

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = create_app(
    service_name=SERVICE_NAME,
    title="Gemini Translate API",
    description=(
        "Пакетний сервіс перекладу рядків інтерфейсу через Google Gemini API.\n\n"
        "Приймає JSON-масив у форматі `[{\"original\": \"...\", \"translation\": \"\"}]` "
        "(той самий формат що використовує CLI-скрипт `translate_json_final.py`) "
        "і повертає масив із заповненими перекладами.\n\n"
        "**Особливості:**\n"
        "- Батчева обробка (до 200 рядків за один запит до Gemini)\n"
        "- Автоматична валідація: формат-символи (`%s`, `%d`), лапки, переноси рядків, фігурні дужки\n"
        "- Retry до 8 разів із зворотним зв'язком про помилки валідації\n"
        "- Resume-режим: елементи з непорожнім `translation` пропускаються\n"
        "- Discord-алерти при помилках (якщо налаштовано `GT_DISCORD_WEBHOOK`)"
    ),
    version="1.0.0",
    include_health=False,
)


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------

@app.on_event("startup")
async def startup():
    set_statusline(SERVICE_NAME, port=PORT, status="Running")
    if not API_KEY:
        logger.warning("GT_API_KEY не встановлено — авторизація вимкнена!")
    if not GEMINI_API_KEY:
        logger.warning("GT_GEMINI_API_KEY не встановлено — /translate повертатиме 503!")
    logger.info(f"Порт: {PORT} | Модель: {GEMINI_MODEL} | Розмір батчу: {BATCH_SIZE} | Макс. спроб: {MAX_RETRIES}")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get(
    f"/api/{SERVICE_NAME}/health",
    response_model=HealthResponse,
    summary="Health check",
    tags=["System"],
    responses={
        200: {
            "description": (
                "**Сервіс запущений**\n\n"
                "| Поле | Опис |\n"
                "|------|------|\n"
                "| `status` | Завжди `ok` якщо сервіс відповідає |\n"
                "| `gemini_key_set` | `true` — сервіс готовий до перекладу. `false` — GT_GEMINI_API_KEY не встановлено, /translate поверне 503 |\n"
                "| `gemini_model` | Поточна модель Gemini (змінна GT_GEMINI_MODEL) |\n"
            ),
        },
    },
)
async def health() -> HealthResponse:
    """Повертає статус сервісу. Авторизація не потрібна."""
    return HealthResponse(
        status="ok",
        service=SERVICE_NAME,
        version="1.0.0",
        gemini_model=GEMINI_MODEL,
        gemini_key_set=bool(GEMINI_API_KEY),
    )


@app.post(
    f"/api/{SERVICE_NAME}/translate",
    response_model=TranslateResponse,
    dependencies=[Depends(require_auth(API_KEY))],
    summary="Перекласти масив рядків",
    tags=["Translation"],
    responses={
        200: {
            "description": (
                "**Переклад виконано**\n\n"
                "Відповідь завжди 200, навіть якщо деякі рядки не пройшли валідацію. "
                "Перевіряйте поле `validation_failures` — воно містить елементи, "
                "що не пройшли валідацію після всіх спроб.\n\n"
                "**Поля відповіді:**\n\n"
                "| Поле | Опис |\n"
                "|------|------|\n"
                "| `items` | Вхідний масив із заповненими полями `translation` |\n"
                "| `total` | Загальна кількість елементів у запиті |\n"
                "| `translated` | Кількість елементів, відправлених у Gemini |\n"
                "| `skipped` | Елементи з уже заповненим `translation` — не відправлялись у Gemini |\n"
                "| `validation_failures` | Елементи з помилками валідації (переклад повернуто, але може бути некоректним) |\n\n"
                "**Типи помилок валідації в `validation_failures[].error`:**\n\n"
                "| Тип | Опис |\n"
                "|-----|------|\n"
                "| `Format symbols mismatch` | Кількість `%s`, `%d`, `%1$s` тощо не збігається з оригіналом |\n"
                "| `Newline count mismatch` | Кількість `\\n` не збігається |\n"
                "| `Spacing mismatch` | Початкові/кінцеві пробіли не збережено |\n"
                "| `Braces content mismatch` | Вміст `{змінних}` або `{{плейсхолдерів}}` змінено |\n"
                "| `Quotes mismatch` | Кількість лапок `'`, `\"`, `«`, `»` не збігається |\n"
            ),
        },
        400: RESP_400,
        401: RESP_401,
        422: RESP_422,
        503: RESP_503,
    },
)
async def translate(body: TranslateRequest) -> TranslateResponse:
    """Перекласти масив рядків на цільову мову через Google Gemini.

    - Елементи з непорожнім полем **translation** повертаються без змін (resume-режим).
    - Рядки відправляються батчами по GT_BATCH_SIZE (за замовчуванням 200).
    - При помилках валідації сервіс повторює запит до GT_MAX_RETRIES разів,
      передаючи Gemini деталі помилок для самовиправлення.
    - Елементи що не пройшли валідацію після всіх спроб повертаються
      у полі **validation_failures** — HTTP-статус залишається 200.
    """
    if not GEMINI_API_KEY:
        logger.error("GT_GEMINI_API_KEY не встановлено — неможливо обробити запит на переклад")
        raise HTTPException(status_code=503, detail="Gemini API key is not configured")

    lang_code = body.lang.lower()
    if lang_code not in LANGUAGE_CODES:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown language code '{body.lang}'. Supported: {sorted(LANGUAGE_CODES.keys())}",
        )

    if not body.items:
        raise HTTPException(status_code=400, detail="items list is empty")

    target_lang = LANGUAGE_CODES[lang_code]
    items = [item.model_copy() for item in body.items]

    pending_indices = [i for i, item in enumerate(items) if not item.translation]
    skipped = len(items) - len(pending_indices)

    logger.info(
        f"Translate request: lang={lang_code} total={len(items)} "
        f"pending={len(pending_indices)} skipped={skipped}"
    )

    all_validation_failures: list[ValidationFailure] = []

    batch_count = (len(pending_indices) + BATCH_SIZE - 1) // BATCH_SIZE
    for batch_num in range(batch_count):
        batch_slice = pending_indices[batch_num * BATCH_SIZE: (batch_num + 1) * BATCH_SIZE]
        batch_strings = [items[i].original for i in batch_slice]

        logger.info(f"Batch {batch_num + 1}/{batch_count}: {len(batch_strings)} strings → Gemini")

        translations, failures = translate_batch(
            strings=batch_strings,
            target_lang=target_lang,
            api_key=GEMINI_API_KEY,
            model=GEMINI_MODEL,
            max_retries=MAX_RETRIES,
            sleep_between_retries=SLEEP_BETWEEN_RETRIES,
        )

        for local_idx, global_idx in enumerate(batch_slice):
            if local_idx < len(translations):
                items[global_idx].translation = translations[local_idx]

        for failure in failures:
            global_idx = batch_slice[failure["id"]]
            all_validation_failures.append(
                ValidationFailure(
                    index=global_idx,
                    original=failure["original"],
                    translation=failure["translation"],
                    error=failure["error"],
                )
            )

        if failures:
            logger.warning(
                f"Batch {batch_num + 1}/{batch_count}: "
                f"{len(failures)} validation failures після {MAX_RETRIES} спроб"
            )

        if batch_num < batch_count - 1 and SLEEP_BETWEEN_BATCHES > 0:
            await asyncio.sleep(SLEEP_BETWEEN_BATCHES)

    logger.info(
        f"Translation done: lang={lang_code} translated={len(pending_indices)} "
        f"failures={len(all_validation_failures)}"
    )

    return TranslateResponse(
        items=items,
        total=len(items),
        translated=len(pending_indices),
        skipped=skipped,
        validation_failures=all_validation_failures,
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    run_service(app, port=PORT, service_name=SERVICE_NAME)
