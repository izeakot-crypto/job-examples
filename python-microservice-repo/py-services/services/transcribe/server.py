#!/usr/bin/env python3
"""
Transcribe — мікросервіс транскрипції аудіо через Whisper API.

Схема роботи:
  1. Клієнт надсилає POST /api/transcribe/add-task з посиланням на аудіофайл,
     мовою та callback_url для отримання результату.
  2. Сервіс одразу повертає унікальний id задачі.
  3. Фоново: завантажує аудіо → відправляє на Whisper API → POST callback_url з результатом.
  4. Якщо webhook не спрацював — 4 спроби (одразу, 5с, 30с, 120с), потім Discord алерт.

Ендпоінти:
  POST /api/transcribe/add-task  — додати задачу (Bearer auth)
  GET  /api/transcribe/health    — health check (без auth)
"""
import os

from fastapi import Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from shared.base_service import create_app, run_service
from shared.auth import require_auth
from shared.logger import get_logger
from shared.discord import DiscordNotifier

from .whisper_client import WhisperClient
from .queue import TranscribeQueue

SERVICE_NAME    = "transcribe"
PORT            = int(os.environ.get("TR_PORT", 8593))
API_KEY         = os.environ.get("TR_API_KEY", "")
WHISPER_URL     = os.environ.get("TR_WHISPER_URL", "")
WHISPER_MODEL   = os.environ.get("TR_WHISPER_MODEL", "istupakov/parakeet-tdt-0.6b-v3-onnx")
DISCORD_WEBHOOK = os.environ.get("TR_DISCORD_WEBHOOK", "")

logger = get_logger(SERVICE_NAME, discord_webhook=DISCORD_WEBHOOK)

discord_notifier = DiscordNotifier(
    webhook_url=DISCORD_WEBHOOK,
    service_name=SERVICE_NAME,
) if DISCORD_WEBHOOK else None

whisper = WhisperClient(url=WHISPER_URL, model=WHISPER_MODEL)
queue   = TranscribeQueue(whisper=whisper, discord_notifier=discord_notifier)


# ---------------------------------------------------------------------------
# Pydantic моделі — Request
# ---------------------------------------------------------------------------

class AddTaskRequest(BaseModel):
    """Запит на додавання задачі транскрипції."""
    model_config = ConfigDict(json_schema_extra={"example": {
        "source_url":   "https://storage.example.com/calls/call-12345.mp3",
        "locale":       "uk",
        "callback_url": "https://your-service.example.com/transcribe/callback",
    }})

    source_url: str = Field(
        description=(
            "URL аудіофайлу для завантаження. "
            "Підтримувані формати: MP3, WAV, OGG, M4A, FLAC та інші що підтримує Whisper. "
            "Файл має бути публічно доступний або доступний з IP сервера. "
            "Таймаут завантаження: 30 секунд."
        )
    )
    locale: str = Field(
        default="",
        description=(
            "Мова розпізнавання. Формат: ISO 639-1 або BCP-47. "
            "Приклади: `uk`, `ru`, `en`, `pl`, `de`, `tr`, `hi`, `uk_UA`, `en-US`. "
            "Якщо порожньо — Whisper визначає мову автоматично."
        )
    )
    callback_url: str = Field(
        description=(
            "URL для POST-запиту з результатом транскрипції (webhook). "
            "Повинен бути доступний з IP сервера та повертати HTTP 2xx. "
            "Таймаут очікування відповіді: 15 секунд. "
            "При невдачі — 4 спроби: одразу, через 5с, 30с, 120с."
        )
    )


# ---------------------------------------------------------------------------
# Pydantic моделі — Response
# ---------------------------------------------------------------------------

class AddTaskResponse(BaseModel):
    """Відповідь після успішного додавання задачі."""
    model_config = ConfigDict(json_schema_extra={"example": {
        "id": "YOUR_AZURE_KEY",
    }})

    id: str = Field(
        description=(
            "Унікальний MD5 ID задачі. "
            "Цей самий `id` буде присутній у payload webhook-а на `callback_url`."
        )
    )


class HealthResponse(BaseModel):
    """Стан сервісу."""
    model_config = ConfigDict(json_schema_extra={"example": {
        "status":             "ok",
        "service":            "transcribe",
        "version":            "1.0.0",
        "environment":        "prod",
        "whisper_url":        "http://whisper-server:9000",
        "worker_concurrency": 3,
    }})

    status:             str = Field(description="Статус сервісу. Завжди `ok` якщо сервіс запущений.")
    service:            str = Field(description="Назва сервісу.")
    version:            str = Field(description="Версія сервісу.")
    environment:        str = Field(description="Середовище: `prod` або `test`.")
    whisper_url:        str = Field(description=(
        "URL Whisper API (з env `TR_WHISPER_URL`). "
        "Якщо `(не задано)` — транскрипція не буде працювати, задачі зависнуть у черзі."
    ))
    worker_concurrency: int = Field(description=(
        "Кількість паралельних asyncio воркерів (env `TR_WORKER_CONCURRENCY`, за замовчуванням 3)."
    ))


class TranscribeItem(BaseModel):
    """Один розпізнаний фрагмент розмови."""
    model_config = ConfigDict(json_schema_extra={"example": {
        "channel":    1,
        "start_time": 1.23,
        "end_time":   3.45,
        "text":       "Доброго дня, чим можу допомогти?",
    }})

    channel:    int   = Field(description="`1` = перший канал (оператор), `2` = другий (клієнт).")
    start_time: float = Field(description="Час початку фрази у секундах від початку запису.")
    end_time:   float = Field(description="Час кінця фрази у секундах.")
    text:       str   = Field(description="Розпізнаний текст фрагменту.")


class CallbackPayload(BaseModel):
    """Payload що сервіс надсилає POST-запитом на `callback_url` після транскрипції.

    > **Це не вхідний параметр API** — це опис того що надійде на ВАШ сервер.
    """
    model_config = ConfigDict(json_schema_extra={"example": {
        "done":      True,
        "id":        "YOUR_AZURE_KEY",
        "createdAt": "2024-01-15 10:30:00",
        "items": [
            {"channel": 1, "start_time": 1.23, "end_time": 3.45, "text": "Доброго дня, чим можу допомогти?"},
            {"channel": 2, "start_time": 2.80, "end_time": 5.10, "text": "Привіт, хотів уточнити замовлення."},
            {"channel": 1, "start_time": 5.50, "end_time": 7.20, "text": "Звісно, назвіть номер замовлення."},
        ],
    }})

    done:      bool                 = Field(description="Завжди `true` — транскрипція завершена успішно.")
    id:        str                  = Field(description="ID задачі — той самий що повернув `/add-task`.")
    createdAt: str                  = Field(description="Час завершення транскрипції (UTC, `YYYY-MM-DD HH:MM:SS`).")
    items:     list[TranscribeItem] = Field(description=(
        "Список розпізнаних фраз, відсортованих за `start_time`. "
        "Порожній список `[]` якщо у записі не виявлено мовлення."
    ))


# ---------------------------------------------------------------------------
# Стандартні моделі помилок
# ---------------------------------------------------------------------------

class ErrorResponse(BaseModel):
    """Відповідь з помилкою (400)."""
    model_config = ConfigDict(json_schema_extra={"example": {"detail": "source_url is required"}})
    detail: str = Field(description="Опис помилки.")


class AuthErrorResponse(BaseModel):
    """Помилка авторизації (401)."""
    model_config = ConfigDict(json_schema_extra={"example": {"detail": "Invalid API key"}})
    detail: str = Field(description="Опис помилки авторизації.")


class ValidationErrorDetail(BaseModel):
    """Деталь помилки валідації."""
    type:  str  = Field(description="Тип помилки.")
    loc:   list = Field(description="Шлях до поля з помилкою.")
    msg:   str  = Field(description="Повідомлення про помилку.")
    input: dict = Field(default={}, description="Отримані дані.")


class ValidationErrorResponse(BaseModel):
    """Помилка валідації полів (422)."""
    model_config = ConfigDict(json_schema_extra={"example": {
        "detail": [{"type": "missing", "loc": ["body", "source_url"], "msg": "Field required", "input": {"callback_url": "http://example.com/cb"}}],
    }})
    detail: list[ValidationErrorDetail] = Field(description="Список помилок валідації.")


# ---------------------------------------------------------------------------
# Описи помилок для ReDoc
# ---------------------------------------------------------------------------

RESP_401 = {
    "model": AuthErrorResponse,
    "description": (
        "**Помилка авторизації**\n\n"
        "| Причина | Відповідь сервера | Як виправити |\n"
        "|---------|-------------------|-------------|\n"
        "| Заголовок `Authorization` відсутній | `Not authenticated` | Додайте заголовок `Authorization: Bearer <ваш_ключ>` |\n"
        "| Ключ передано без префіксу `Bearer` | `Not authenticated` | Формат: `Bearer <ключ>`, а не просто ключ |\n"
        "| Порожній Bearer токен | `Not authenticated` | Вкажіть ключ після `Bearer ` |\n"
        "| Невірний API ключ | `Invalid API key` | Перевірте значення `TR_API_KEY` у `.env` на сервері |\n"
        "| `TR_API_KEY` порожній у `.env` | `Invalid API key` | Задайте `TR_API_KEY` у `.env` та перезапустіть контейнер |\n"
    ),
    "content": {
        "application/json": {
            "examples": {
                "no_header": {
                    "summary": "Відсутній заголовок Authorization",
                    "value":   {"detail": "Not authenticated"},
                },
                "invalid_key": {
                    "summary": "Невірний API ключ",
                    "value":   {"detail": "Invalid API key"},
                },
            }
        }
    },
}

RESP_400 = {
    "model": ErrorResponse,
    "description": (
        "**Невалідний запит — бізнес-валідація**\n\n"
        "Поля присутні в JSON але мають порожнє значення `\"\"`.\n\n"
        "| Причина | Відповідь | Як виправити |\n"
        "|---------|-----------|-------------|\n"
        "| `source_url` є але порожній | `source_url is required` | Передайте непорожній URL аудіофайлу |\n"
        "| `callback_url` є але порожній | `callback_url is required` | Передайте непорожній URL вашого webhook-а |\n"
        "\n"
        "> **Відмінність від 422:** 400 = поле є але порожнє. 422 = поле відсутнє взагалі або невірний тип."
    ),
    "content": {
        "application/json": {
            "examples": {
                "empty_source_url": {
                    "summary": "source_url є але порожній рядок",
                    "value":   {"detail": "source_url is required"},
                },
                "empty_callback_url": {
                    "summary": "callback_url є але порожній рядок",
                    "value":   {"detail": "callback_url is required"},
                },
            }
        }
    },
}

RESP_422 = {
    "model": ValidationErrorResponse,
    "description": (
        "**Помилка структурної валідації запиту**\n\n"
        "| Причина | `type` | `loc` | Як виправити |\n"
        "|---------|--------|-------|-------------|\n"
        "| Поле `source_url` відсутнє | `missing` | `[body, source_url]` | Додайте `source_url` в тіло |\n"
        "| Поле `callback_url` відсутнє | `missing` | `[body, callback_url]` | Додайте `callback_url` в тіло |\n"
        "| Поле передане не як рядок | `string_type` | `[body, <поле>]` | Передайте значення як рядок, не число чи `null` |\n"
        "| Невалідний JSON у тілі | `json_invalid` | `[body, <позиція>]` | Перевірте синтаксис JSON |\n"
        "| Відсутній `Content-Type: application/json` | `model_attributes_type` | `[body]` | Додайте заголовок `Content-Type: application/json` |\n"
        "\n"
        "> **Як читати `loc`:** другий елемент — назва поля з помилкою."
    ),
    "content": {
        "application/json": {
            "examples": {
                "missing_source_url": {
                    "summary": "Відсутнє поле source_url",
                    "value": {"detail": [{"type": "missing", "loc": ["body", "source_url"], "msg": "Field required", "input": {"callback_url": "http://example.com/cb"}}]},
                },
                "missing_callback_url": {
                    "summary": "Відсутнє поле callback_url",
                    "value": {"detail": [{"type": "missing", "loc": ["body", "callback_url"], "msg": "Field required", "input": {"source_url": "http://example.com/audio.mp3"}}]},
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


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = create_app(
    service_name=SERVICE_NAME,
    title="Transcribe API",
    description=(
        "Сервіс транскрипції аудіозаписів телефонних дзвінків через Whisper API.\n\n"
        "## Схема роботи\n\n"
        "1. Надішліть `POST /api/transcribe/add-task` з посиланням на аудіо та `callback_url`\n"
        "2. Сервіс **одразу** повертає `id` — не чекаючи завершення обробки\n"
        "3. Фоново: завантажує аудіо → Whisper → POST на `callback_url` з результатом\n\n"
        "## Черга та паралельність\n\n"
        "Задачі зберігаються в Redis черзі (`transcribe:queue`). "
        "Кількість паралельних воркерів: `TR_WORKER_CONCURRENCY` (за замовчуванням `3`). "
        "Задачі не губляться при перезапуску сервісу.\n\n"
        "## Змінні середовища\n\n"
        "| Змінна | Опис | За замовчуванням |\n"
        "|--------|------|------------------|\n"
        "| `TR_API_KEY` | Bearer токен для авторизації | *(обов'язково)* |\n"
        "| `TR_WHISPER_URL` | URL Whisper API сервера | *(обов'язково)* |\n"
        "| `TR_WHISPER_MODEL` | Назва моделі Whisper | `istupakov/parakeet-tdt-0.6b-v3-onnx` |\n"
        "| `TR_REDIS_URL` | URL Redis для черги | `redis://localhost:6379/0` |\n"
        "| `TR_WORKER_CONCURRENCY` | Кількість паралельних воркерів | `3` |\n"
        "| `TR_DISCORD_WEBHOOK` | Webhook для алертів у Discord `Transcribe_errors` | *(опціонально)* |\n"
        "| `TR_PORT` | Порт сервісу | `8593` |\n"
    ),
    version="1.0.0",
    include_health=False,
)


@app.on_event("startup")
async def startup():
    if not WHISPER_URL:
        logger.warning("TR_WHISPER_URL не задано — транскрипція не працюватиме!")
    await queue.start()


@app.on_event("shutdown")
async def shutdown():
    await queue.stop()


# ---------------------------------------------------------------------------
# Ендпоінти
# ---------------------------------------------------------------------------

@app.get(
    f"/api/{SERVICE_NAME}/health",
    response_model=HealthResponse,
    summary="Health check",
    tags=["System"],
    responses={
        200: {"description": "Сервіс працює нормально.", "model": HealthResponse},
    },
)
async def health():
    """Перевірка стану сервісу. Авторизація не потрібна.

    ### На що звертати увагу

    | Поле | Що означає | Проблема |
    |------|------------|---------|
    | `whisper_url: "(не задано)"` | `TR_WHISPER_URL` не заданий | Всі задачі будуть скасовуватись з помилкою ConnectError |
    | `worker_concurrency: 0` | `TR_WORKER_CONCURRENCY=0` | Задачі кладуться в чергу але ніхто не обробляє |
    | `environment: test` | Це TEST контейнер | URL `/test/transcribe/...` замість `/api/transcribe/...` |
    """
    return HealthResponse(
        status="ok",
        service=SERVICE_NAME,
        version="1.0.0",
        environment=os.environ.get("CONTAINER_ROLE", "prod"),
        whisper_url=WHISPER_URL or "(не задано)",
        worker_concurrency=int(os.environ.get("TR_WORKER_CONCURRENCY", 3)),
    )


@app.post(
    f"/api/{SERVICE_NAME}/add-task",
    response_model=AddTaskResponse,
    dependencies=[Depends(require_auth(API_KEY))],
    summary="Додати задачу транскрипції",
    tags=["Transcribe"],
    responses={
        200: {
            "description": "Задача прийнята в чергу. Результат надійде на `callback_url` після обробки.",
            "model": AddTaskResponse,
        },
        400: RESP_400,
        401: RESP_401,
        422: RESP_422,
    },
)
async def add_task(body: AddTaskRequest):
    """Додає аудіофайл у чергу транскрипції та повертає `id` задачі.

    Обробка відбувається **асинхронно** — сервіс відповідає одразу, не чекаючи Whisper.
    Результат надходить POST-запитом на `callback_url`.

    ### Підтримувані формати аудіо

    MP3, WAV, OGG, M4A, FLAC, WebM та інші формати що підтримує Whisper.
    Стерео (2 канали) та моно (1 канал) записи.

    ### Підтримувані мови (`locale`)

    | Код | Мова |
    |-----|------|
    | `uk` або `uk_UA` | Українська |
    | `ru` або `ru_RU` | Російська |
    | `en` або `en_US` | Англійська |
    | `pl` або `pl_PL` | Польська |
    | `de` або `de_DE` | Німецька |
    | `tr` або `tr_TR` | Турецька |
    | `hi` | Гінді |
    | *(порожньо)* | Автовизначення Whisper |

    ### Формат callback payload

    ```json
    {
        "done": true,
        "id": "YOUR_AZURE_KEY",
        "createdAt": "2024-01-15 10:30:00",
        "items": [
            {"channel": 1, "start_time": 1.23, "end_time": 3.45, "text": "Доброго дня"},
            {"channel": 2, "start_time": 2.80, "end_time": 5.10, "text": "Привіт"}
        ]
    }
    ```

    ### Поля `items`

    | Поле | Тип | Опис |
    |------|-----|------|
    | `channel` | int | `1` = перший канал (оператор), `2` = другий (клієнт) |
    | `start_time` | float | Початок фрази (секунди від початку запису) |
    | `end_time` | float | Кінець фрази (секунди) |
    | `text` | string | Розпізнаний текст фрагменту |

    ### Retry логіка webhook

    | Спроба | Затримка | Тригер повтору |
    |--------|----------|----------------|
    | 1 | одразу | — |
    | 2 | через 5с | HTTP 5xx або недоступність |
    | 3 | через 30с | HTTP 5xx або недоступність |
    | 4 | через 120с | HTTP 5xx або недоступність |

    HTTP 4xx від `callback_url` — вважається успішною доставкою, retry не робиться.
    Після 4 невдалих спроб — Discord алерт в `Transcribe_errors`.

    ### Всі помилки фонової обробки (логи + Discord)

    **Завантаження аудіо:**

    | Помилка | Причина | Дія |
    |---------|---------|-----|
    | HTTP 404 на `source_url` | Файл не існує | Задача скасовується |
    | HTTP 4xx на `source_url` | Немає доступу до файлу | Задача скасовується |
    | HTTP 5xx на `source_url` | Файловий сервер впав | Задача скасовується |
    | Таймаут 30с при завантаженні | Повільний сервер або великий файл | Задача скасовується |
    | DNS / ConnectError | URL недоступний з IP сервера | Задача скасовується |

    **Whisper API:**

    | Помилка | Причина | Дія |
    |---------|---------|-----|
    | ConnectError (10с) | Whisper не запущений або `TR_WHISPER_URL` невірний | Задача скасовується |
    | Таймаут 800с | Файл занадто великий або Whisper перевантажений | Задача скасовується |
    | HTTP 4xx від Whisper | Невірний формат аудіо | Задача скасовується |
    | HTTP 5xx від Whisper | Внутрішня помилка Whisper | Задача скасовується |
    | Невалідний JSON від Whisper | Помилка на стороні Whisper | Задача скасовується |
    | `TR_WHISPER_URL` порожній | Не задано в `.env` | Всі задачі скасовуються |

    **Webhook:**

    | Помилка | Причина | Дія |
    |---------|---------|-----|
    | ConnectError | `callback_url` недоступний | 4 retry, потім Discord алерт |
    | Таймаут 15с | `callback_url` відповідає повільно | 4 retry, потім Discord алерт |
    | HTTP 5xx | Ваш сервер впав | 4 retry, потім Discord алерт |
    | HTTP 4xx | Ваш сервер відхилив | Вважається успішним, без retry |
    """
    if not body.source_url:
        raise HTTPException(status_code=400, detail="source_url is required")
    if not body.callback_url:
        raise HTTPException(status_code=400, detail="callback_url is required")

    task_id = queue.enqueue(
        source_url=body.source_url,
        locale=body.locale,
        callback_url=body.callback_url,
    )

    logger.info(f"Нова задача: id={task_id}, locale={body.locale or 'auto'}, url={body.source_url}")

    return AddTaskResponse(id=task_id)


if __name__ == "__main__":
    run_service(app, port=PORT, service_name=SERVICE_NAME)

