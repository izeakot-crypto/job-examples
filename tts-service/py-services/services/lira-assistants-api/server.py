#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LIRA Assistants API — FastAPI HTTP-сервер для AI-асистентів.

Ендпоінти:
  POST /api/lira-assistants-api/create   — створити нову сесію асистента
  POST /api/lira-assistants-api/resume   — відновити існуючу сесію
  POST /api/lira-assistants-api/message  — відправити повідомлення, отримати відповідь
  POST /api/lira-assistants-api/close    — закрити сесію
  GET  /api/lira-assistants-api/health   — health check (без авторизації)
"""
import os

from fastapi import Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from shared.base_service import create_app, run_service
from shared.auth import require_auth
from shared.logger import get_logger
from shared.statusline import set_statusline

from .models import (
    CreateRequest, CreateResponse,
    ResumeRequest, ResumeResponse,
    MessageRequest, MessageResponse,
    CloseRequest, CloseResponse,
    ErrorResponse,
)
from .session import SessionManager

# --- Конфігурація з .env (префікс LA_) ---
SERVICE_NAME = "lira-assistants-api"
PORT = int(os.environ.get("LA_PORT", 8590))
API_KEY = os.environ.get("LA_API_KEY", "")
_DISCORD_WEBHOOK = os.environ.get("LA_DISCORD_WEBHOOK", "") or os.environ.get("DISCORD_WEBHOOK", "")

logger = get_logger(SERVICE_NAME, discord_webhook=_DISCORD_WEBHOOK)

# --- Session manager ---
sessions = SessionManager()


# --- Моделі для документації помилок ---

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
        "detail": [{"type": "missing", "loc": ["body", "session_id"], "msg": "Field required", "input": {}}],
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
        "| Невірний API ключ | `Invalid API key` | Перевірте значення LA_API_KEY у .env на сервері |\n"
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
        "| Пропущене обов'язкове поле | `missing` | Додайте поле, вказане в `loc` (наприклад `session_id`, `comp_id`) |\n"
        "| Невірний тип даних | `int_parsing` | `comp_id` має бути числом, не рядком |\n"
        "| Невідомий провайдер | `enum` | `provider` має бути: `openai`, `claude` або `n8n` |\n"
        "| Невалідний JSON | `json_invalid` | Перевірте синтаксис JSON у тілі запиту |\n"
        "| Невірний Content-Type | `model_attributes_type` | Використовуйте `Content-Type: application/json` |\n"
        "| `temperature` поза діапазоном | `less_than_equal` | `temperature` має бути від 0 до 2 |\n"
        "| `max_tokens` <= 0 | `greater_than` | `max_tokens` має бути більше 0 |\n"
    ),
    "content": {
        "application/json": {
            "examples": {
                "missing_field": {
                    "summary": "Пропущене поле comp_id",
                    "value": {"detail": [{"type": "missing", "loc": ["body", "comp_id"], "msg": "Field required", "input": {"assistant_session_id": "..."}}]},
                },
                "bad_provider": {
                    "summary": "Невідомий провайдер",
                    "value": {"detail": [{"type": "enum", "loc": ["body", "provider"], "msg": "Input should be 'openai', 'claude' or 'n8n'", "input": "gemini"}]},
                },
                "bad_json": {
                    "summary": "Невалідний JSON",
                    "value": {"detail": [{"type": "json_invalid", "loc": ["body", 0], "msg": "JSON decode error", "input": {}}]},
                },
                "bad_content_type": {
                    "summary": "Невірний Content-Type",
                    "value": {"detail": [{"type": "model_attributes_type", "loc": ["body"], "msg": "Input should be a valid dictionary or object to extract fields from", "input": "raw string"}]},
                },
            }
        }
    },
}

RESP_403 = {
    "model": ErrorResponse,
    "description": (
        "**Невідповідність comp_id**\n\n"
        "| Ситуація | Причина | Як виправити |\n"
        "|----------|---------|-------------|\n"
        "| `comp_id mismatch` | `comp_id` у запиті не збігається з `comp_id`, вказаним при створенні сесії | Передайте той самий `comp_id`, що використовувався при `/create` |\n\n"
        "**Навіщо це?** Захист від доступу до чужих сесій — кожна сесія прив'язана до конкретної компанії.\n"
    ),
    "content": {
        "application/json": {
            "example": {"error": {"reason": "comp_id mismatch"}},
        }
    },
}

RESP_404_SESSION = {
    "model": ErrorResponse,
    "description": (
        "**Сесія не знайдена**\n\n"
        "| Ситуація | Причина | Як виправити |\n"
        "|----------|---------|-------------|\n"
        "| Невірний ID | `assistant_session_id` не існує | Перевірте UUID, отриманий з `/create` |\n"
        "| Сесія вже закрита | Була закрита через `/close` | Створіть нову сесію через `/create` |\n"
        "| Сервер перезапущено | Сесії зберігаються в пам'яті — при рестарті втрачаються | Створіть нову сесію через `/create` |\n"
    ),
    "content": {
        "application/json": {
            "examples": {
                "not_found": {
                    "summary": "Сесія не знайдена",
                    "value": {"error": {"reason": "Session '550e8400-e29b-41d4-a716-446655440000' not found"}},
                },
            }
        }
    },
}


# --- FastAPI app ---
app = create_app(
    service_name=SERVICE_NAME,
    title="LIRA Assistants API",
    description=(
        "Універсальний API для AI-асистентів у системі Oki-Toki (OpenAI, Claude, n8n).\n\n"
        "## Провайдери\n\n"
        "| Провайдер | Режим | Потрібні поля в `config` |\n"
        "|-----------|-------|------------------------|\n"
        "| `openai` | Chat Completions | `api_key`, `model` (default: gpt-4o) |\n"
        "| `openai` + `assistant_id` | Assistants API | `api_key`, `assistant_id` |\n"
        "| `claude` | Messages API | `api_key`, `model` (default: claude-sonnet-4-20250514) |\n"
        "| `n8n` | Webhook HTTP POST | `url` (обов'язково), `api_key` (опціонально) |\n\n"
        "## Порядок роботи\n\n"
        "1. **`/create`** — ініціалізувати сесію з провайдером\n"
        "2. **`/message`** — відправити повідомлення та отримати відповідь (можна викликати багато разів)\n"
        "3. **`/close`** — закрити сесію та звільнити ресурси\n\n"
        "**`/resume`** — відновити сесію після втрати з'єднання (за тим самим `assistant_session_id`)\n\n"
        "## Формат помилок\n\n"
        "Всі помилки бізнес-логіки (400, 403, 404, 500) повертаються у форматі:\n"
        "```json\n"
        '{\"error\": {\"reason\": \"описание ошибки\"}}\n'
        "```\n"
    ),
    version="1.0.0",
)


# --- Startup ---
@app.on_event("startup")
async def startup():
    set_statusline(SERVICE_NAME, port=PORT, status="Running")
    if not API_KEY:
        logger.warning("LA_API_KEY not set — authorization disabled!")
    logger.info(f"Port: {PORT}")


# --- POST /create ---
@app.post(
    f"/api/{SERVICE_NAME}/create",
    response_model=CreateResponse,
    responses={
        200: {
            "description": (
                "**Сесія успішно створена**\n\n"
                "Повертає `assistant_session_id` (UUID) — використовуйте його для всіх подальших запитів.\n\n"
                "| Поле | Опис |\n"
                "|------|------|\n"
                "| `assistant_session_id` | UUID сесії для `/message`, `/resume`, `/close` |\n\n"
                "**Особливості провайдерів:**\n\n"
                "| Провайдер | Що відбувається при створенні |\n"
                "|-----------|------------------------------|\n"
                "| `openai` (Chat) | Зберігає конфіг, сесія готова до повідомлень |\n"
                "| `openai` (Assistants) | Створює Thread в OpenAI API |\n"
                "| `claude` | Зберігає конфіг (stateless) |\n"
                "| `n8n` | Перевіряє наявність URL, зберігає конфіг |\n"
            ),
        },
        400: {
            "model": ErrorResponse,
            "description": (
                "**Невірні параметри запиту**\n\n"
                "| Ситуація | Приклад відповіді | Як виправити |\n"
                "|----------|-------------------|-------------|\n"
                "| n8n без URL | `n8n provider requires 'url'` | Додайте `config.url` з адресою n8n webhook |\n"
                "| Невірний API ключ OpenAI | `AuthenticationError: Incorrect API key` | Перевірте `config.api_key` |\n"
                "| Невірний API ключ Claude | `AuthenticationError` | Перевірте `config.api_key` |\n"
                "| Невідомий assistant_id | `No assistant found` | Перевірте ID в OpenAI Dashboard |\n"
            ),
            "content": {
                "application/json": {
                    "examples": {
                        "n8n_no_url": {
                            "summary": "n8n без URL webhook",
                            "value": {"error": {"reason": "n8n provider requires 'url' (webhook endpoint)"}},
                        },
                        "bad_openai_key": {
                            "summary": "Невірний API ключ OpenAI",
                            "value": {"error": {"reason": "AuthenticationError: Incorrect API key provided: sk-...xxx"}},
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
                "**Внутрішня помилка при створенні сесії**\n\n"
                "| Ситуація | Причина | Як виправити |\n"
                "|----------|---------|-------------|\n"
                "| OpenAI API недоступний | Тимчасовий збій OpenAI | Повторіть запит через 5-10 секунд |\n"
                "| Claude API недоступний | Тимчасовий збій Anthropic | Повторіть запит через 5-10 секунд |\n"
                "| n8n webhook не відповідає | Воркфлоу вимкнений або URL невірний | Перевірте, що воркфлоу активний в n8n |\n"
                "| Rate limit провайдера | Перевищено ліміт запитів | Зачекайте 30-60 секунд та повторіть |\n"
            ),
            "content": {
                "application/json": {
                    "examples": {
                        "openai_down": {
                            "summary": "OpenAI API недоступний",
                            "value": {"error": {"reason": "Connection error: OpenAI API is temporarily unavailable"}},
                        },
                        "rate_limit": {
                            "summary": "Rate limit провайдера",
                            "value": {"error": {"reason": "RateLimitError: You exceeded your current quota"}},
                        },
                    }
                }
            },
        },
    },
    dependencies=[Depends(require_auth(API_KEY))],
)
async def create(body: CreateRequest):
    """Створити нову сесію AI-асистента.

    Ініціалізує з'єднання з обраним провайдером (OpenAI, Claude, n8n)
    та повертає унікальний `assistant_session_id` для подальшої роботи.
    """
    logger.info(
        f"POST /create — provider: {body.provider.value}, "
        f"session_id: {body.session_id}, comp_id: {body.comp_id}"
    )
    try:
        assistant_session_id = await sessions.create(body)
        logger.info(f"Session created: {assistant_session_id}")
        return CreateResponse(assistant_session_id=assistant_session_id)
    except ValueError as e:
        logger.warning(f"Create failed (400): {e}")
        return JSONResponse(status_code=400, content={"error": {"reason": str(e)}})
    except Exception as e:
        logger.error(f"Create failed (500): {e}")
        return JSONResponse(status_code=500, content={"error": {"reason": str(e)}})


# --- POST /resume ---
@app.post(
    f"/api/{SERVICE_NAME}/resume",
    response_model=ResumeResponse,
    responses={
        200: {
            "description": (
                "**Сесія успішно відновлена**\n\n"
                "Повертає `assistant_session_id` — підтверджує, що сесія активна і готова до `/message`.\n\n"
                "| Поле | Опис |\n"
                "|------|------|\n"
                "| `assistant_session_id` | Той самий UUID сесії |\n\n"
                "Історія повідомлень зберігається — наступний `/message` отримає повний контекст розмови.\n"
            ),
        },
        401: RESP_401,
        403: RESP_403,
        404: RESP_404_SESSION,
        422: RESP_422,
        500: {
            "model": ErrorResponse,
            "description": (
                "**Внутрішня помилка сервера**\n\n"
                "Непередбачена помилка. Зверніться до адміністратора.\n"
            ),
            "content": {
                "application/json": {
                    "example": {"error": {"reason": "Internal server error"}},
                }
            },
        },
    },
    dependencies=[Depends(require_auth(API_KEY))],
)
async def resume(body: ResumeRequest):
    """Відновити існуючу сесію AI-асистента.

    Перевіряє, що сесія існує та належить вказаній компанії (comp_id).
    Використовується для reconnect після втрати з'єднання.
    """
    logger.info(f"POST /resume — assistant_session_id: {body.assistant_session_id}")
    try:
        assistant_session_id = await sessions.resume(body.comp_id, body.assistant_session_id)
        return ResumeResponse(assistant_session_id=assistant_session_id)
    except KeyError as e:
        logger.warning(f"Resume failed (404): {e}")
        return JSONResponse(status_code=404, content={"error": {"reason": e.args[0]}})
    except PermissionError as e:
        logger.warning(f"Resume failed (403): {e}")
        return JSONResponse(status_code=403, content={"error": {"reason": str(e)}})
    except Exception as e:
        logger.error(f"Resume failed (500): {e}")
        return JSONResponse(status_code=500, content={"error": {"reason": str(e)}})


# --- POST /message ---
@app.post(
    f"/api/{SERVICE_NAME}/message",
    response_model=MessageResponse,
    responses={
        200: {
            "description": (
                "**Відповідь асистента отримана**\n\n"
                "Повертає `completion` з текстом відповіді та статистикою токенів.\n\n"
                "| Поле | Опис |\n"
                "|------|------|\n"
                "| `completion.text` | Текст відповіді асистента |\n"
                "| `completion.tokens_send` | Кількість токенів у промпті (input) |\n"
                "| `completion.tokens_received` | Кількість токенів у відповіді (output) |\n\n"
                "**Токени за провайдером:**\n\n"
                "| Провайдер | Підрахунок токенів |\n"
                "|-----------|-------------------|\n"
                "| `openai` | Точний — з `usage` відповіді API |\n"
                "| `claude` | Точний — з `usage` відповіді API |\n"
                "| `n8n` | Залежить від воркфлоу — якщо повертає `tokens_send`/`tokens_received` в JSON |\n\n"
                "Історія повідомлень накопичується — кожен `/message` відправляє провайдеру повний контекст розмови.\n"
            ),
        },
        401: RESP_401,
        403: RESP_403,
        404: RESP_404_SESSION,
        422: RESP_422,
        500: {
            "model": ErrorResponse,
            "description": (
                "**Помилка при отриманні відповіді від провайдера**\n\n"
                "| Ситуація | Причина | Як виправити |\n"
                "|----------|---------|-------------|\n"
                "| OpenAI API error | Помилка ChatGPT/Assistants API | Перевірте ліміти та ключ |\n"
                "| Claude API error | Помилка Anthropic API | Перевірте ліміти та ключ |\n"
                "| n8n недоступний | `All connection attempts failed` — webhook URL не відповідає | Перевірте URL та мережу, чи n8n запущений |\n"
                "| n8n HTTP error | Воркфлоу повернув 4xx/5xx помилку | Перевірте логи n8n воркфлоу |\n"
                "| n8n timeout | Webhook не відповів за 120с (або custom timeout) | Оптимізуйте n8n воркфлоу або збільште `parameters.timeout` |\n"
                "| OpenAI Run failed | Assistants API run не завершився | Перевірте конфігурацію Assistant в OpenAI |\n"
                "| Rate limit | Перевищено ліміт запитів | Зачекайте 30-60 секунд |\n"
                "| Context length exceeded | Занадто довга історія повідомлень | Закрийте сесію та створіть нову |\n"
            ),
            "content": {
                "application/json": {
                    "examples": {
                        "openai_error": {
                            "summary": "Помилка OpenAI API",
                            "value": {"error": {"reason": "RateLimitError: Rate limit reached for gpt-4o"}},
                        },
                        "claude_error": {
                            "summary": "Помилка Claude API",
                            "value": {"error": {"reason": "OverloadedError: Anthropic API is temporarily overloaded"}},
                        },
                        "n8n_connection": {
                            "summary": "n8n webhook недоступний",
                            "value": {"error": {"reason": "All connection attempts failed"}},
                        },
                        "n8n_http_error": {
                            "summary": "n8n повернув HTTP помилку",
                            "value": {"error": {"reason": "Server error '500 INTERNAL SERVER ERROR' for url 'https://n8n.example.com/webhook/xxx'"}},
                        },
                        "run_failed": {
                            "summary": "OpenAI Assistants Run не завершився",
                            "value": {"error": {"reason": "OpenAI run failed: failed — Error processing request"}},
                        },
                        "context_length": {
                            "summary": "Перевищено довжину контексту",
                            "value": {"error": {"reason": "BadRequestError: This model's maximum context length is 128000 tokens"}},
                        },
                    }
                }
            },
        },
    },
    dependencies=[Depends(require_auth(API_KEY))],
)
async def message(body: MessageRequest):
    """Відправити повідомлення AI-асистенту та отримати відповідь.

    Повідомлення додаються до історії сесії. Провайдер отримує
    повний контекст розмови (всі попередні повідомлення + нові).
    """
    logger.info(
        f"POST /message — assistant_session_id: {body.assistant_session_id}, "
        f"messages: {len(body.messages)}"
    )
    try:
        completion = await sessions.message(body.comp_id, body.assistant_session_id, body.messages)
        logger.info(
            f"Completion: {len(completion.text)} chars, "
            f"tokens: {completion.tokens_send}+{completion.tokens_received}"
        )
        return MessageResponse(completion=completion)
    except KeyError as e:
        logger.warning(f"Message failed (404): {e}")
        return JSONResponse(status_code=404, content={"error": {"reason": e.args[0]}})
    except PermissionError as e:
        logger.warning(f"Message failed (403): {e}")
        return JSONResponse(status_code=403, content={"error": {"reason": str(e)}})
    except Exception as e:
        logger.error(f"Message failed (500): {e}")
        return JSONResponse(status_code=500, content={"error": {"reason": str(e)}})


# --- POST /close ---
@app.post(
    f"/api/{SERVICE_NAME}/close",
    response_model=CloseResponse,
    responses={
        200: {
            "description": (
                "**Сесія успішно закрита**\n\n"
                "Ресурси провайдера звільнені, сесія видалена з пам'яті.\n\n"
                "| Провайдер | Що відбувається при закритті |\n"
                "|-----------|----------------------------|\n"
                "| `openai` (Chat) | Нічого — stateless |\n"
                "| `openai` (Assistants) | Видаляє Thread в OpenAI API |\n"
                "| `claude` | Нічого — stateless |\n"
                "| `n8n` | Нічого — stateless |\n\n"
                "Повторний виклик `/close` для тієї ж сесії поверне 404.\n"
            ),
        },
        401: RESP_401,
        403: RESP_403,
        404: {
            "model": ErrorResponse,
            "description": (
                "**Сесія не знайдена**\n\n"
                "| Ситуація | Причина | Як виправити |\n"
                "|----------|---------|-------------|\n"
                "| Сесія вже закрита | Повторний виклик `/close` | Ігноруйте — сесія вже закрита, це не помилка |\n"
                "| Невірний ID | `assistant_session_id` не існує | Перевірте UUID |\n"
                "| Сервер перезапущено | Сесії втрачаються при рестарті | Нічого робити не потрібно — ресурси вже звільнені |\n"
            ),
            "content": {
                "application/json": {
                    "examples": {
                        "already_closed": {
                            "summary": "Сесія вже закрита",
                            "value": {"error": {"reason": "Session '550e8400-e29b-41d4-a716-446655440000' not found"}},
                        },
                    }
                }
            },
        },
        422: RESP_422,
        500: {
            "model": ErrorResponse,
            "description": (
                "**Помилка при закритті сесії**\n\n"
                "| Ситуація | Причина | Як виправити |\n"
                "|----------|---------|-------------|\n"
                "| Помилка видалення OpenAI Thread | API OpenAI недоступний | Сесія все одно видалена локально — ігноруйте |\n"
            ),
            "content": {
                "application/json": {
                    "example": {"error": {"reason": "Failed to delete OpenAI thread: Connection timeout"}},
                }
            },
        },
    },
    dependencies=[Depends(require_auth(API_KEY))],
)
async def close(body: CloseRequest):
    """Закрити сесію AI-асистента.

    Звільняє ресурси провайдера (видаляє Thread для OpenAI Assistants)
    та видаляє сесію з пам'яті сервера.
    """
    logger.info(f"POST /close — assistant_session_id: {body.assistant_session_id}")
    try:
        await sessions.close(body.comp_id, body.assistant_session_id)
        logger.info(f"Session closed: {body.assistant_session_id}")
        return CloseResponse(status="closed")
    except KeyError as e:
        logger.warning(f"Close failed (404): {e}")
        return JSONResponse(status_code=404, content={"error": {"reason": e.args[0]}})
    except PermissionError as e:
        logger.warning(f"Close failed (403): {e}")
        return JSONResponse(status_code=403, content={"error": {"reason": str(e)}})
    except Exception as e:
        logger.error(f"Close failed (500): {e}")
        return JSONResponse(status_code=500, content={"error": {"reason": str(e)}})


# --- Run ---
if __name__ == '__main__':
    run_service(app, port=PORT, service_name=SERVICE_NAME)
