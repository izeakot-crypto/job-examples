# Transcribe Microservice — Developer Guide

## Зміст

- [Огляд](#огляд)
- [Схема роботи](#схема-роботи)
- [Підключення з боку Нюлука](#підключення-з-боку-нюлука)
- [API Reference](#api-reference)
  - [POST /add-task](#post-add-task)
  - [GET /health](#get-health)
- [Формат callback (webhook)](#формат-callback-webhook)
- [Коди помилок](#коди-помилок)
- [Змінні оточення](#змінні-оточення)
- [Архітектура](#архітектура)
- [Retry логіка](#retry-логіка)
- [Discord алерти](#discord-алерти)

---

## Огляд

Мікросервіс транскрипції аудіо. Приймає посилання на аудіофайл, ставить задачу в чергу та повертає результат через webhook.

**Base URL:** `https://py-services.oki-toki.net/api/transcribe`  
**ReDoc документація:** `https://py-services.oki-toki.net/api/transcribe/redoc`  
**Авторизація:** Bearer token у заголовку `Authorization`

### Credentials для підключення

| Параметр | Значення |
|----------|----------|
| **URL** | `https://py-services.oki-toki.net/api/transcribe/add-task` |
| **Bearer токен** | `tr_YOUR_AZURE_KEYYOUR_AZURE_KEY` |

---

## Схема роботи

```
Нюлук                    Наш сервіс                    Whisper (Макс)
  │                           │                               │
  │  POST /add-task            │                               │
  │  + source_url             │                               │
  │  + locale                 │                               │
  │  + callback_url           │                               │
  │ ─────────────────────────>│                               │
  │                           │                               │
  │  {"id": "abc123"}         │                               │
  │ <─────────────────────────│                               │
  │                           │                               │
  │           [фоново]        │                               │
  │                           │── 1. завантажує аудіо ──────> │ (скачує з source_url)
  │                           │                               │
  │                           │── 2. POST /parakeet_asr ─────>│
  │                           │      + аудіофайл              │
  │                           │      + модель                 │
  │                           │      + мова                   │
  │                           │                               │
  │                           │<── сегменти тексту ───────────│
  │                           │                               │
  │<── 3. POST callback_url ──│                               │
  │       + результат         │                               │
```

**Головна особливість:** сервіс одразу повертає `id` задачі і не чекає результату. Результат приходить асинхронно через webhook на `callback_url`.

---

## Підключення з боку Нюлука

### Крок 1 — Надіслати задачу

```http
POST https://py-services.oki-toki.net/api/transcribe/add-task
Authorization: Bearer tr_YOUR_AZURE_KEYYOUR_AZURE_KEY
Content-Type: application/json

{
  "source_url": "https://storage.example.com/calls/call-12345.mp3",
  "locale": "uk",
  "callback_url": "https://your-service.example.com/transcribe/callback"
}
```

**Відповідь:**
```json
{
  "id": "abc123def456..."
}
```

### Крок 2 — Прийняти результат на callback_url

На ваш `callback_url` прийде POST запит з результатом:

```json
{
  "task_id": "abc123def456...",
  "status": "done",
  "locale": "uk",
  "segments": [
    {
      "channel": 1,
      "start_time": 0.5,
      "end_time": 3.2,
      "text": "Добрий день, чим можу допомогти?"
    },
    {
      "channel": 1,
      "start_time": 3.5,
      "end_time": 6.1,
      "text": "Я телефоную щодо мого замовлення."
    }
  ]
}
```

Ваш сервер має повернути **HTTP 2xx** — інакше буде повтор (див. [Retry логіка](#retry-логіка)).

### Приклад на Python

```python
import requests

# 1. Відправити задачу
response = requests.post(
    "https://py-services.oki-toki.net/api/transcribe/add-task",
    headers={
        "Authorization": "Bearer tr_YOUR_AZURE_KEYYOUR_AZURE_KEY",
        "Content-Type": "application/json",
    },
    json={
        "source_url": "https://storage.example.com/call.mp3",
        "locale": "uk",
        "callback_url": "https://your-service.example.com/webhook",
    }
)

task_id = response.json()["id"]
print(f"Задача створена: {task_id}")

# 2. Прийняти результат (на вашому webhook endpoint)
from flask import Flask, request

app = Flask(__name__)

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json
    task_id = data["task_id"]
    segments = data["segments"]
    print(f"Транскрипція задачі {task_id}: {segments}")
    return "", 200
```

---

## API Reference

### POST /add-task

Додає задачу транскрипції в чергу.

**URL:** `POST https://py-services.oki-toki.net/api/transcribe/add-task`

**Заголовки:**
| Заголовок | Значення |
|-----------|----------|
| `Authorization` | `Bearer <TR_API_KEY>` |
| `Content-Type` | `application/json` |

**Тіло запиту:**
| Поле | Тип | Обов'язкове | Опис |
|------|-----|:-----------:|------|
| `source_url` | string | ✅ | URL аудіофайлу. Має бути доступний з IP `65.109.131.32`. Таймаут завантаження: 30 секунд |
| `locale` | string | — | Мова: `uk`, `ru`, `en`, `pl`, `de`, `tr` та інші ISO 639-1. Якщо порожньо — Whisper визначає автоматично. Приймає і `uk_UA`, і `en-US` формати |
| `callback_url` | string | ✅ | URL для отримання результату. Має повертати HTTP 2xx |

**Відповідь 200:**
```json
{
  "id": "YOUR_AZURE_KEY"
}
```

| Поле | Опис |
|------|------|
| `id` | Унікальний ID задачі (MD5 хеш). Зберігається 1 день |

---

### GET /health

Перевірка доступності сервісу. Не потребує авторизації.

**URL:** `GET https://py-services.oki-toki.net/api/transcribe/health`

**Відповідь 200:**
```json
{
  "status": "ok",
  "service": "transcribe",
  "version": "1.0.0",
  "environment": "prod",
  "whisper_url": "http://whisper.oki-toki.net",
  "worker_concurrency": 3
}
```

---

## Формат callback (webhook)

Коли транскрипція завершена, сервіс надсилає POST на ваш `callback_url`.

**Успішна транскрипція:**
```json
{
  "task_id": "YOUR_AZURE_KEY",
  "status": "done",
  "locale": "uk",
  "segments": [
    {
      "channel": 1,
      "start_time": 0.50,
      "end_time": 3.20,
      "text": "Добрий день, чим можу допомогти?"
    },
    {
      "channel": 1,
      "start_time": 3.50,
      "end_time": 6.10,
      "text": "Я телефоную щодо мого замовлення."
    }
  ]
}
```

**Помилка транскрипції:**
```json
{
  "task_id": "YOUR_AZURE_KEY",
  "status": "error",
  "error": "Файл не знайдено: https://storage.example.com/call.mp3"
}
```

**Опис полів сегменту:**
| Поле | Тип | Опис |
|------|-----|------|
| `channel` | int | Завжди `1` (один канал) |
| `start_time` | float | Початок сегменту в секундах |
| `end_time` | float | Кінець сегменту в секундах |
| `text` | string | Розпізнаний текст |

---

## Коди помилок

### HTTP помилки (синхронні — повертаються одразу)

| Код | Причина | Як виправити |
|-----|---------|--------------|
| `401 Not authenticated` | Відсутній заголовок `Authorization` | Додайте `Authorization: Bearer <ключ>` |
| `401 Not authenticated` | Немає префіксу `Bearer ` | Формат: `Bearer <ключ>` |
| `401 Invalid API key` | Невірний API ключ | Перевірте ключ |
| `400` | Порожній `source_url` | Вкажіть URL аудіофайлу |
| `400` | Порожній `callback_url` | Вкажіть URL для отримання результату |
| `422` | Відсутнє обов'язкове поле | Перевірте тіло запиту |

### Фонові помилки (приходять через Discord алерт)

| Ситуація | Поведінка |
|----------|-----------|
| `source_url` повернув 404 | Задача завершується з помилкою, на `callback_url` надходить `{"status": "error"}` |
| `source_url` недоступний (таймаут 30с) | Аналогічно — помилка в callback |
| Whisper API недоступний | Задача завершується з помилкою |
| `callback_url` не відповідає | 4 спроби, потім Discord алерт (див. нижче) |

---

## Змінні оточення

| Змінна | Обов'язкова | За замовч. | Опис |
|--------|:-----------:|-----------|------|
| `TR_API_KEY` | ✅ | — | Bearer-токен для авторизації запитів |
| `TR_WHISPER_URL` | ✅ | — | URL Whisper API (Макс) |
| `TR_WHISPER_MODEL` | — | `istupakov/parakeet-tdt-0.6b-v3-onnx` | Модель транскрипції |
| `TR_REDIS_URL` | — | `redis://localhost:6379/0` | URL Redis для черги |
| `TR_WORKER_CONCURRENCY` | — | `3` | Кількість паралельних воркерів |
| `TR_DISCORD_WEBHOOK` | — | — | Discord webhook для алертів помилок |
| `TR_PORT` | — | `8593` | Порт сервісу |

---

## Архітектура

```
┌─────────────────────────────────────────────┐
│              py-services container           │
│                                              │
│  ┌─────────────┐    ┌────────────────────┐  │
│  │  FastAPI     │    │  TranscribeQueue   │  │
│  │  server.py   │───>│  queue.py          │  │
│  │  port: 8593  │    │                    │  │
│  └─────────────┘    │  Worker-0          │  │
│                      │  Worker-1          │  │
│                      │  Worker-2          │  │
│                      └────────┬───────────┘  │
│                               │              │
└───────────────────────────────│──────────────┘
                                │
                    ┌───────────▼───────────┐
                    │  Redis                │
                    │  queue: transcribe:   │
                    │         queue         │
                    └───────────────────────┘

Потік задачі:
1. POST /add-task → задача кладеться в Redis list
2. Вільний Worker бере задачу через BLPOP
3. Worker завантажує аудіо з source_url
4. Worker надсилає аудіо на Whisper API
5. Worker надсилає результат на callback_url
```

**Компоненти:**
| Файл | Відповідальність |
|------|-----------------|
| `server.py` | FastAPI ендпоінти, авторизація, документація |
| `queue.py` | Redis черга, воркери, завантаження аудіо |
| `whisper_client.py` | HTTP клієнт до Whisper API (Макс) |
| `webhook.py` | Відправка результату на callback_url з retry |

---

## Retry логіка

### Webhook retry (callback_url)

Якщо ваш сервер не відповів або повернув HTTP 5xx:

```
Спроба 1 → одразу після транскрипції
Спроба 2 → через 5 секунд
Спроба 3 → через 30 секунд
Спроба 4 → через 120 секунд (2 хвилини)
─────────────────────────────────────
Всі провалились → Discord алерт в Transcribe_errors
```

**Важливо:** HTTP 4xx (400, 404 і т.д.) вважається **успішною доставкою** — повторів не буде. Поверніть HTTP 2xx для підтвердження отримання.

### Таймаути

| Операція | Таймаут |
|----------|---------|
| Завантаження аудіо (`source_url`) | 30 секунд |
| Підключення до Whisper | 10 секунд |
| Транскрипція на Whisper | 800 секунд |
| Відправка webhook | 15 секунд |

---

## Discord алерти

Алерти надходять у канал **Transcribe_errors** у двох випадках:

1. **Помилка обробки задачі** — не вдалось завантажити аудіо або Whisper повернув помилку
2. **Webhook провалився** — всі 4 спроби відправити результат на `callback_url` не вдались

Приклад алерту:
```
❌ Transcribe: webhook failed
Не вдалось відправити webhook після 4 спроб.
Task ID: abc123...
Callback URL: https://your-service.example.com/webhook
```

