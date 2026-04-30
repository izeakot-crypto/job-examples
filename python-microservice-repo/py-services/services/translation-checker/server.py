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

from fastapi import Depends, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

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

LLM_PROVIDER   = os.environ.get("LLM_PROVIDER", "ollama")
LLM_BASE_URL   = os.environ.get("LLM_BASE_URL", "") or os.environ.get("OLLAMA_URL", "")
LLM_MODEL      = os.environ.get("LLM_MODEL", "") or os.environ.get("OLLAMA_MODEL", "")
LLM_API_KEY    = os.environ.get("LLM_API_KEY", "") or os.environ.get("OLLAMA_API_KEY", "")
LLM_TIMEOUT    = int(os.environ.get("LLM_TIMEOUT", os.environ.get("OLLAMA_TIMEOUT", 300)))
LLM_TEMPERATURE = float(os.environ.get("LLM_TEMPERATURE", os.environ.get("OLLAMA_TEMPERATURE", 0.1)))
LLM_MAX_TOKENS = int(os.environ.get("LLM_MAX_TOKENS", os.environ.get("OLLAMA_MAX_TOKENS", 4096)))
LLM_MAX_RETRIES = int(os.environ.get("LLM_MAX_RETRIES", os.environ.get("OLLAMA_MAX_RETRIES", 5)))

TG_BOT_TOKEN = os.environ.get("TC_TG_BOT_TOKEN", "")
TG_CHAT_ID   = os.environ.get("TC_TG_CHAT_ID", "")
DISCORD_WEBHOOK = os.environ.get("TC_DISCORD_WEBHOOK", "")

CHECK_ORIGINAL    = os.environ.get("CHECK_ORIGINAL", "true").lower() == "true"
CHECK_TRANSLATIONS = os.environ.get("CHECK_TRANSLATIONS", "true").lower() == "true"
MAX_LENGTH_RATIO  = float(os.environ.get("MAX_LENGTH_RATIO", 3.0))
MIN_LENGTH_RATIO  = float(os.environ.get("MIN_LENGTH_RATIO", 0.2))

ANALYSIS_MAX_RETRIES = 3
ANALYSIS_RETRY_DELAY = 10

DISCORD_ALERTS_WEBHOOK = os.environ.get("DISCORD_WEBHOOK", "")
logger   = get_logger(SERVICE_NAME, discord_webhook=DISCORD_ALERTS_WEBHOOK)
executor = ThreadPoolExecutor(max_workers=4)

analyzer   = None
notifiers  = []
llm_client = None


# ---------------------------------------------------------------------------
# Pydantic-моделі запитів/відповідей
# ---------------------------------------------------------------------------

class CheckRequest(BaseModel):
    """Запит на перевірку перекладів."""
    items: list[dict] = Field(
        description=(
            "Список елементів для перевірки. "
            "Кожен елемент — словник з полем `Оригинал` та перекладами (EN, UA, PL, DE, ES, PT)."
        ),
        json_schema_extra={"examples": [[
            {"Оригинал": "Сохранить", "EN": "Save", "UA": "Зберегти", "PL": "Zapisz"},
            {"Оригинал": "Удалить",   "EN": "Delete", "UA": "Видалити"},
        ]]}
    )


class CheckResponse(BaseModel):
    """Відповідь — задача прийнята."""
    model_config = ConfigDict(json_schema_extra={"example": {
        "status": "accepted",
        "message": "Прийнято 2 елементів для аналізу",
        "total_items": 2,
    }})
    status:      str = Field(description="Завжди `accepted`")
    message:     str = Field(description="Повідомлення з кількістю прийнятих елементів")
    total_items: int = Field(description="Кількість елементів, переданих на аналіз")


class AuthErrorResponse(BaseModel):
    """Помилка авторизації (401)."""
    model_config = ConfigDict(json_schema_extra={"example": {"detail": "Invalid API key"}})
    detail: str = Field(description="Опис помилки авторизації")


class ValidationErrorDetail(BaseModel):
    type:  str
    loc:   list
    msg:   str
    input: dict = {}


class ValidationErrorResponse(BaseModel):
    """Помилка валідації (422)."""
    model_config = ConfigDict(json_schema_extra={"example": {
        "detail": [{"type": "missing", "loc": ["body", "items"], "msg": "Field required", "input": {}}]
    }})
    detail: list[ValidationErrorDetail]


class FileErrorResponse(BaseModel):
    """Помилка обробки файлу (400)."""
    model_config = ConfigDict(json_schema_extra={"example": {
        "detail": "JSON parse error: Expecting value: line 1 column 1 (char 0)"
    }})
    detail: str = Field(description="Опис помилки")


# ---------------------------------------------------------------------------
# Спільні responses для ReDoc
# ---------------------------------------------------------------------------

RESP_401 = {
    "model": AuthErrorResponse,
    "description": (
        "**Помилка авторизації**\n\n"
        "| Ситуація | Відповідь | Як виправити |\n"
        "|----------|-----------|--------------|\n"
        "| Відсутній заголовок `Authorization` | `Not authenticated` | Додайте `Authorization: Bearer <ключ>` |\n"
        "| Ключ без префіксу `Bearer ` | `Not authenticated` | Формат: `Bearer <ключ>`, не просто ключ без слова Bearer |\n"
        "| Порожній токен (`Bearer ` без значення) | `Not authenticated` | Вкажіть ключ після `Bearer ` |\n"
        "| Невірний API ключ | `Invalid API key` | Перевірте значення `TC_API_KEY` у `.env` на сервері |\n"
        "| `TC_API_KEY` не задано у `.env` | Сервіс не запустився | Встановіть `TC_API_KEY` у `.env` та перезапустіть сервіс |\n"
    ),
    "content": {
        "application/json": {
            "examples": {
                "no_header": {
                    "summary": "Відсутній заголовок Authorization",
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

RESP_422_CHECK = {
    "model": ValidationErrorResponse,
    "description": (
        "**Помилка валідації тіла запиту**\n\n"
        "| Ситуація | `type` у відповіді | Як виправити |\n"
        "|----------|--------------------|--------------|\n"
        "| Поле `items` відсутнє | `missing` | Додайте поле `items` в тіло запиту |\n"
        "| `items` не є масивом (наприклад, рядок або об'єкт) | `list_type` | Передайте `items` як JSON-масив `[{...}, ...]` |\n"
        "| Невалідний JSON у тілі (синтаксична помилка) | `json_invalid` | Перевірте синтаксис JSON — дужки, лапки, коми |\n"
        "| Невірний `Content-Type` (не `application/json`) | `model_attributes_type` | Встановіть заголовок `Content-Type: application/json` |\n\n"
        "**Як читати поле `loc`:** масив шляху до проблемного поля. "
        "Наприклад, `[\"body\", \"items\"]` — помилка у полі `items` тіла запиту."
    ),
    "content": {
        "application/json": {
            "examples": {
                "missing_items": {
                    "summary": "Поле items відсутнє",
                    "value": {"detail": [{"type": "missing", "loc": ["body", "items"], "msg": "Field required", "input": {}}]},
                },
                "items_not_list": {
                    "summary": "items не є масивом",
                    "value": {"detail": [{"type": "list_type", "loc": ["body", "items"], "msg": "Input should be a valid list", "input": "not a list"}]},
                },
                "malformed_json": {
                    "summary": "Невалідний JSON",
                    "value": {"detail": [{"type": "json_invalid", "loc": ["body", 0], "msg": "JSON decode error", "input": {}, "ctx": {"error": "Expecting value"}}]},
                },
                "wrong_content_type": {
                    "summary": "Невірний Content-Type",
                    "value": {"detail": [{"type": "model_attributes_type", "loc": ["body"], "msg": "Input should be a valid dictionary or object to extract fields from", "input": "raw string"}]},
                },
            }
        }
    },
}

RESP_422_FILE = {
    "description": (
        "**Файл не передано у запиті**\n\n"
        "| Ситуація | Як виправити |\n"
        "|----------|--------------|\n"
        "| Поле `file` відсутнє в запиті | Надішліть файл як `multipart/form-data` з полем `file` |\n"
        "| Запит надіслано як `application/json` замість `multipart/form-data` | Змініть тип запиту на `multipart/form-data` |\n"
    ),
    "content": {
        "application/json": {
            "example": {"detail": [{"type": "missing", "loc": ["body", "file"], "msg": "Field required", "input": {}}]}
        }
    },
}

RESP_400_FILE = {
    "model": FileErrorResponse,
    "description": (
        "**Помилка читання або парсингу файлу**\n\n"
        "| Ситуація | Повідомлення у `detail` | Як виправити |\n"
        "|----------|--------------------------|--------------|\n"
        "| Файл у некоректному кодуванні (не UTF-8 і не CP1251) | `Cannot decode file. Use UTF-8 or CP1251 encoding` | Збережіть файл у кодуванні UTF-8 або CP1251 |\n"
        "| Синтаксична помилка у JSON-файлі | `JSON parse error: <деталь>` | Перевірте JSON синтаксис файлу — дужки, лапки, коми |\n"
        "| Помилка структури CSV-файлу | `CSV parse error: <деталь>` | Перший рядок має бути заголовками, роздільник — кома |\n"
        "| Файл не є ні JSON ні CSV (нерозпізнаний формат) | `Cannot parse file. Supported formats: JSON, CSV.` | Надішліть файл з розширенням `.json` або `.csv` |\n"
    ),
    "content": {
        "application/json": {
            "examples": {
                "decode_error": {
                    "summary": "Некоректне кодування файлу",
                    "value": {"detail": "Cannot decode file. Use UTF-8 or CP1251 encoding"},
                },
                "json_parse_error": {
                    "summary": "Синтаксична помилка у JSON",
                    "value": {"detail": "JSON parse error: Expecting value: line 1 column 1 (char 0)"},
                },
                "csv_parse_error": {
                    "summary": "Помилка структури CSV",
                    "value": {"detail": "CSV parse error: unexpected end of data"},
                },
                "unknown_format": {
                    "summary": "Нерозпізнаний формат файлу",
                    "value": {"detail": "Cannot parse file. Supported formats: JSON, CSV."},
                },
            }
        }
    },
}


# ---------------------------------------------------------------------------
# Опис сервісу для ReDoc
# ---------------------------------------------------------------------------

_DESCRIPTION = """
Сервіс перевірки якості перекладів через LLM (Ollama / OpenAI / Gemini).

Режим роботи: **fire-and-forget** — сервіс миттєво відповідає `accepted`,
а аналіз виконується у фоновому потоці. При виявленні проблем алерт
надсилається у **Telegram** та/або **Discord**.

---

## Авторизація

Всі ендпоінти (крім `/health`) потребують Bearer-токена:

```
Authorization: Bearer <TC_API_KEY>
```

---

## Змінні оточення (`.env`)

| Змінна | Обов'язкова | За замовч. | Опис |
|--------|:-----------:|-----------|------|
| `TC_API_KEY` | ✅ | — | Bearer-токен авторизації. Без нього сервіс **не запуститься** |
| `TC_PORT` | — | `8585` | Порт сервісу |
| `LLM_PROVIDER` | ✅ | `ollama` | Провайдер LLM: `ollama`, `openai`, `gemini` |
| `LLM_BASE_URL` | ✅ | — | URL до LLM API (напр. `http://ollama:11434`) |
| `LLM_MODEL` | ✅ | — | Назва моделі (напр. `llama3`, `gpt-4o`, `gemini-2.5-flash`) |
| `LLM_API_KEY` | — | — | API ключ для OpenAI або Gemini (для Ollama не потрібен) |
| `LLM_TIMEOUT` | — | `300` | Таймаут запиту до LLM (секунди) |
| `LLM_TEMPERATURE` | — | `0.1` | Температура генерації (0.0–1.0) |
| `LLM_MAX_TOKENS` | — | `4096` | Максимум токенів у відповіді LLM |
| `LLM_MAX_RETRIES` | — | `5` | Кількість retry при помилці LLM |
| `TC_TG_BOT_TOKEN` | — | — | Telegram Bot Token для алертів |
| `TC_TG_CHAT_ID` | — | — | Telegram Chat ID для алертів |
| `TC_DISCORD_WEBHOOK` | — | — | Discord Webhook URL для алертів |
| `CHECK_ORIGINAL` | — | `true` | Перевіряти оригінальний текст через LLM |
| `CHECK_TRANSLATIONS` | — | `true` | Перевіряти переклади через LLM |
| `MAX_LENGTH_RATIO` | — | `3.0` | Макс. відношення довжини перекладу до оригіналу |
| `MIN_LENGTH_RATIO` | — | `0.2` | Мін. відношення довжини перекладу до оригіналу |

---

## Фоновий аналіз — помилки які не повертаються у HTTP-відповіді

Ці помилки виникають **після** того як сервіс вже відповів `accepted`.
Вони фіксуються у логах і надсилаються в Telegram/Discord.

### Помилки LLM

| Ситуація | Що відбувається | Що робити |
|----------|-----------------|-----------|
| LLM недоступний при старті сервісу | WARNING у логах, сервіс продовжує роботу | Перевірте `LLM_BASE_URL` та стан LLM-сервера |
| ConnectionError під час аналізу | Retry: затримка `10с × номер_спроби`, до `LLM_MAX_RETRIES` разів | Перевірте мережу та доступність LLM |
| Timeout під час аналізу (перевищено `LLM_TIMEOUT`) | Retry: затримка `15с × номер_спроби`, до `LLM_MAX_RETRIES` разів | Збільшіть `LLM_TIMEOUT` або зменшіть розмір тексту |
| HTTP 429 Rate Limit від LLM | Retry: затримка `30с × номер_спроби`, до `LLM_MAX_RETRIES` разів | Зменшіть навантаження або збільшіть ліміти у LLM-провайдера |
| HTTP 5xx від LLM | Retry: затримка `15с × номер_спроби`, до `LLM_MAX_RETRIES` разів | Перевірте стан LLM-сервера |
| HTTP 4xx від LLM (крім 429) | **Без retry**, ERROR у логах, елемент пропускається | Перевірте `LLM_MODEL` та `LLM_API_KEY` |
| Всі `LLM_MAX_RETRIES` спроби вичерпано | ERROR у логах, елемент пропускається | Перевірте LLM та перезапустіть задачу |
| LLM повернув невалідний JSON у відповіді | WARNING у логах, елемент вважається без проблем | Спробуйте іншу модель або збільшіть `LLM_MAX_TOKENS` |

### Програмні перевірки (без LLM)

Ці перевірки виконуються завжди, навіть якщо LLM недоступний:

| Тип перевірки | Опис |
|---------------|------|
| Пустий переклад | Поле перекладу є, але порожнє — severity `high` |
| Невідповідність плейсхолдерів (`%s`, `%d`, `{...}`) | Кількість у перекладі не збігається з оригіналом — severity `high` |
| Підозріло довгий переклад | Відношення довжини > `MAX_LENGTH_RATIO` (за замовч. 3.0) — severity `medium` |
| Підозріло короткий переклад | Відношення довжини < `MIN_LENGTH_RATIO` (за замовч. 0.2) — severity `medium` |

### Помилки нотифікаторів

| Ситуація | Що відбувається |
|----------|-----------------|
| Telegram/Discord недоступні | ERROR у логах, аналіз продовжується без переривання |
| Жоден нотифікатор не налаштований | Результати лише в логах сервісу, алертів немає |
| Елемент не має поля `Оригинал` | Елемент пропускається без помилки |

---

## Формат даних

Кожен елемент — об'єкт з полем `Оригинал` та перекладами за кодами мов:

```json
{"Оригинал": "Зберегти", "EN": "Save", "UA": "Зберегти", "PL": "Zapisz", "DE": "Speichern"}
```

Підтримувані коди мов: `EN`, `UA`, `PL`, `DE`, `ES`, `PT`, `FR`, `IT`, `KK`, `RO`, `TR`, `KA`.
"""


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = create_app(
    service_name=SERVICE_NAME,
    title="Translation Checker API",
    description=_DESCRIPTION,
    version="2.1.0",
    include_health=False,
)


# ---------------------------------------------------------------------------
# Ініціалізація
# ---------------------------------------------------------------------------

def init_services():
    global analyzer, notifiers, llm_client

    if not API_KEY:
        logger.error("TC_API_KEY не задан! Установите переменную окружения TC_API_KEY.")
        sys.exit(1)

    if not LLM_BASE_URL:
        logger.error("LLM_BASE_URL (или OLLAMA_URL) не задан!")
        sys.exit(1)

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

    analysis_config = {
        "check_original": CHECK_ORIGINAL,
        "check_translations": CHECK_TRANSLATIONS,
        "max_length_ratio": MAX_LENGTH_RATIO,
        "min_length_ratio": MIN_LENGTH_RATIO,
    }
    analyzer = TranslationAnalyzer(llm_client, analysis_config)

    notifiers.clear()

    if TG_BOT_TOKEN and TG_CHAT_ID:
        notifiers.append(TelegramNotifier(TG_BOT_TOKEN, int(TG_CHAT_ID)))
        logger.info(f"Telegram нотификация: чат {TG_CHAT_ID}")

    if DISCORD_WEBHOOK:
        notifiers.append(DiscordNotifier(DISCORD_WEBHOOK))
        logger.info("Discord нотификация включена")


def analyze_with_retry(analyzer_instance, item, max_retries=ANALYSIS_MAX_RETRIES):
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
    reader = csv.DictReader(io.StringIO(content))
    items = []
    for row in reader:
        item = {k.strip(): v.strip() for k, v in row.items() if k and v}
        if item:
            items.append(item)
    return items


# ---------------------------------------------------------------------------
# Ендпоінти
# ---------------------------------------------------------------------------

@app.on_event("startup")
async def startup():
    init_services()
    set_statusline(SERVICE_NAME, port=PORT, status="Running")
    logger.info(f"Режим: fire-and-forget")
    logger.info(f"Порт: {PORT}")
    logger.info(f"Алерты: {', '.join(n.__class__.__name__ for n in notifiers)}")


@app.get(
    f"/api/{SERVICE_NAME}/health",
    summary="Health check",
    responses={
        200: {
            "description": (
                "**Сервіс працює**\n\n"
                "Авторизація не потрібна. Повертає стан сервісу та доступність LLM.\n\n"
                "| Поле | Значення | Опис |\n"
                "|------|----------|------|\n"
                "| `status` | `ok` | Сервіс запущений і приймає запити |\n"
                "| `llm_available` | `true` / `false` | `true` — LLM відповідає, `false` — недоступний, аналіз не виконуватиметься |\n"
                "| `llm_provider` | `ollama` / `openai` / `gemini` | Поточний провайдер LLM |\n"
                "| `llm_model` | назва моделі | Модель, налаштована у `LLM_MODEL` |\n"
                "| `notifiers` | список | Активні нотифікатори: `TelegramNotifier`, `DiscordNotifier` або порожній список |\n"
                "| `mode` | `fire-and-forget` | Режим роботи — завжди це значення |\n\n"
                "**Якщо `llm_available: false`:** перевірте `LLM_BASE_URL` у `.env` та доступність LLM-сервера з хоста."
            ),
        },
    },
)
async def health():
    """Перевірка доступності сервісу — без авторизації."""
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


@app.post(
    f"/api/{SERVICE_NAME}/check",
    response_model=CheckResponse,
    summary="Перевірити переклади (JSON)",
    responses={
        200: {
            "description": (
                "**Задача прийнята — аналіз виконується у фоні**\n\n"
                "Сервіс одразу повертає відповідь, не чекаючи завершення аналізу.\n"
                "Результати надсилаються у Telegram / Discord при виявленні проблем.\n\n"
                "| Поле | Опис |\n"
                "|------|------|\n"
                "| `status` | Завжди `accepted` |\n"
                "| `message` | Повідомлення з кількістю прийнятих елементів |\n"
                "| `total_items` | Кількість елементів, переданих на аналіз |\n"
            ),
        },
        401: RESP_401,
        422: RESP_422_CHECK,
    },
    dependencies=[Depends(require_auth(API_KEY))],
)
async def check_translations(body: CheckRequest):
    """Прийом перекладів у форматі JSON — аналіз у фоні (fire-and-forget)."""
    items = body.items

    if not items:
        return CheckResponse(status="accepted", message="No items to process", total_items=0)

    logger.info(f"POST /check — принято {len(items)} элементов, запуск фонового анализа")
    executor.submit(process_items_background, items)

    return CheckResponse(
        status="accepted",
        message=f"Прийнято {len(items)} елементів для аналізу",
        total_items=len(items),
    )


@app.post(
    f"/api/{SERVICE_NAME}/check-file",
    response_model=CheckResponse,
    summary="Перевірити переклади (файл JSON або CSV)",
    responses={
        200: {
            "description": (
                "**Файл прийнято — аналіз виконується у фоні**\n\n"
                "Сервіс одразу повертає відповідь після розпарсення файлу.\n"
                "Результати надсилаються у Telegram / Discord при виявленні проблем.\n\n"
                "| Поле | Опис |\n"
                "|------|------|\n"
                "| `status` | Завжди `accepted` |\n"
                "| `message` | Назва файлу та кількість знайдених елементів |\n"
                "| `total_items` | Кількість рядків / елементів знайдених у файлі |\n"
            ),
        },
        400: RESP_400_FILE,
        401: RESP_401,
        422: RESP_422_FILE,
    },
    dependencies=[Depends(require_auth(API_KEY))],
)
async def check_translations_file(file: UploadFile = File(description="JSON або CSV файл з перекладами")):
    """Завантаження файлу з перекладами (JSON або CSV) — аналіз у фоні.

    Підтримувані формати:
    - **JSON**: `{"items": [{...}, ...]}` або масив `[{...}, ...]`
    - **CSV**: перший рядок — заголовки (`Оригинал,EN,UA,...`), роздільник — кома

    Кодування файлу: **UTF-8** або **CP1251**.
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
        return CheckResponse(status="accepted", message="File parsed but no items found", total_items=0)

    logger.info(f"POST /check-file — файл '{file.filename}', {len(items)} элементов, запуск фонового анализа")
    executor.submit(process_items_background, items)

    return CheckResponse(
        status="accepted",
        message=f"Файл '{file.filename}' прийнято. {len(items)} елементів для аналізу",
        total_items=len(items),
    )


if __name__ == '__main__':
    run_service(app, port=PORT, service_name=SERVICE_NAME)
