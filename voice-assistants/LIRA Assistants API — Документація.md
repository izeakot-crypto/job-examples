# LIRA Assistants API — Документація для розробників

## Що це

API-посередник між системою голосових дзвінків LIRA (Oki-Toki) та AI-провайдерами (OpenAI, Claude, n8n). Під час дзвінка LIRA створює сесію з AI-асистентом, відправляє повідомлення клієнта, отримує відповідь і озвучує її.

```
Клієнт дзвонить → LIRA → наш API → OpenAI/Claude/n8n → відповідь → LIRA → озвучує клієнту
```

---

## Посилання

| Що | PROD | TEST |
|----|------|------|
| **ReDoc** (повна документація з помилками) | https://py-services.oki-toki.net/api/lira-assistants-api/redoc | https://py-services.oki-toki.net/test/lira-assistants-api/redoc |
| **Swagger UI** (тестування в браузері) | https://py-services.oki-toki.net/api/lira-assistants-api/docs | https://py-services.oki-toki.net/test/lira-assistants-api/docs |
| **Health Check** | https://py-services.oki-toki.net/api/lira-assistants-api/health | https://py-services.oki-toki.net/test/lira-assistants-api/health |
| **Каталог усіх сервісів** | https://py-services.oki-toki.net/docs | |
| **Jira задача** | https://jira.oki-toki.net/browse/PROG-9565 | |

---

## Базовий URL

```
PROD: https://py-services.oki-toki.net/api/lira-assistants-api
TEST: https://py-services.oki-toki.net/test/lira-assistants-api
```

Для тестування інтеграції використовуйте **TEST**.

---

## Авторизація

Всі ендпоінти (крім `/health`) вимагають заголовок:

```
Authorization: Bearer <LA_API_KEY>
```

`LA_API_KEY` — це ключ доступу до **самого сервісу** (не плутати з ключами OpenAI/Claude). Ключі AI-провайдерів передаються в кожному запиті `/create` через поле `config.api_key`.

---

## Порядок роботи

```
1. Дзвінок починається     → POST /create   → отримати assistant_session_id
2. Клієнт щось каже        → POST /message  → отримати відповідь AI
3. Клієнт каже ще           → POST /message  → AI знає контекст (історія зберігається)
4. Втрата з'єднання         → POST /resume   → перевірити що сесія жива
5. Дзвінок закінчується     → POST /close    → очистити ресурси
```

---

## Провайдери

| Провайдер | Режим | Коли використовувати |
|-----------|-------|---------------------|
| `openai` | Chat Completions | Стандартний чат з GPT-4o та іншими моделями |
| `openai` + `assistant_id` | Assistants API | Коли потрібен конкретний OpenAI Assistant (з інструкціями, файлами) |
| `claude` | Messages API | Anthropic Claude |
| `n8n` | Webhook HTTP POST | Коли є свій n8n-воркфлоу (RAG, база знань, складна логіка) |

---

## Ендпоінти

### GET /health

Перевірка доступності сервісу. **Авторизація не потрібна.**

```bash
curl https://py-services.oki-toki.net/api/lira-assistants-api/health
```

Відповідь:
```json
{
  "status": "ok",
  "service": "lira-assistants-api",
  "version": "1.0.0",
  "environment": "prod"
}
```

---

### POST /create — Створення сесії

Створює нову сесію з AI-провайдером. Повертає `assistant_session_id` (UUID) для подальших запитів.

```
POST /api/lira-assistants-api/create
Content-Type: application/json
Authorization: Bearer <LA_API_KEY>
```

#### Схема запиту

```json
{
  "session_id": "string",       // ID дзвінка з Oki-Toki (обов'язково)
  "comp_id": 42,                // ID компанії (обов'язково)
  "contact_id": 7890,           // ID контакту (обов'язково)
  "provider": "openai",         // Провайдер: "openai", "claude", "n8n" (обов'язково)
  "config": {                   // Конфігурація провайдера (обов'язково)
    "api_key": "sk-...",        // API ключ провайдера (обов'язково)
    "url": null,                // URL (обов'язково для n8n, опціонально для інших)
    "model": "gpt-4o",          // Модель (за замовч. gpt-4o / claude-sonnet-4-20250514)
    "assistant_id": null,       // OpenAI Assistant ID (вмикає Assistants API режим)
    "system_prompt": "...",     // Системний промпт
    "temperature": 0.7,         // Температура 0–2 (за замовч. 0.7)
    "max_tokens": 1000          // Макс. токенів у відповіді (за замовч. 1000)
  },
  "parameters": {}              // Додаткові параметри провайдера (опціонально)
}
```

#### Приклад — OpenAI Chat

```bash
curl -X POST https://py-services.oki-toki.net/api/lira-assistants-api/create \
  -H "Authorization: Bearer <LA_API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "call-123",
    "comp_id": 42,
    "contact_id": 7890,
    "provider": "openai",
    "config": {
      "api_key": "sk-proj-...",
      "model": "gpt-4o",
      "system_prompt": "Ти оператор колл-центра Oki-Toki. Відповідай коротко і по справі.",
      "temperature": 0.7,
      "max_tokens": 1000
    }
  }'
```

#### Приклад — OpenAI Assistants API

```bash
curl -X POST https://py-services.oki-toki.net/api/lira-assistants-api/create \
  -H "Authorization: Bearer <LA_API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "call-456",
    "comp_id": 42,
    "contact_id": 7890,
    "provider": "openai",
    "config": {
      "api_key": "sk-proj-...",
      "assistant_id": "asst_abc123def456"
    }
  }'
```

#### Приклад — Claude

```bash
curl -X POST https://py-services.oki-toki.net/api/lira-assistants-api/create \
  -H "Authorization: Bearer <LA_API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "call-789",
    "comp_id": 42,
    "contact_id": 7890,
    "provider": "claude",
    "config": {
      "api_key": "sk-ant-...",
      "model": "claude-sonnet-4-20250514",
      "system_prompt": "Ти оператор колл-центра.",
      "max_tokens": 2000
    }
  }'
```

#### Приклад — n8n

```bash
curl -X POST https://py-services.oki-toki.net/api/lira-assistants-api/create \
  -H "Authorization: Bearer <LA_API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "call-101",
    "comp_id": 42,
    "contact_id": 7890,
    "provider": "n8n",
    "config": {
      "url": "https://n8n.example.com/webhook/my-workflow",
      "api_key": "optional-bearer-token",
      "system_prompt": "Ти оператор."
    },
    "parameters": {
      "timeout": 30,
      "response_path": "data.output"
    }
  }'
```

#### Відповідь (200)

```json
{
  "assistant_session_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

---

### POST /message — Відправка повідомлення

Додає повідомлення в історію сесії, відправляє провайдеру **весь контекст** розмови, повертає відповідь AI.

```
POST /api/lira-assistants-api/message
Content-Type: application/json
Authorization: Bearer <LA_API_KEY>
```

#### Схема запиту

```json
{
  "comp_id": 42,                                           // ID компанії
  "assistant_session_id": "550e8400-...",                   // UUID сесії з /create
  "messages": [                                             // Масив повідомлень
    {"role": "user", "content": "Привіт, розкажи про тарифи"}
  ]
}
```

#### curl

```bash
curl -X POST https://py-services.oki-toki.net/api/lira-assistants-api/message \
  -H "Authorization: Bearer <LA_API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{
    "comp_id": 42,
    "assistant_session_id": "550e8400-e29b-41d4-a716-446655440000",
    "messages": [
      {"role": "user", "content": "Привіт, розкажи про тарифи"}
    ]
  }'
```

#### Відповідь (200)

```json
{
  "completion": {
    "text": "Доброго дня! Наразі у нас є три тарифні плани...",
    "tokens_send": 45,
    "tokens_received": 23
  }
}
```

| Поле | Опис |
|------|------|
| `completion.text` | Текст відповіді AI |
| `completion.tokens_send` | Кількість токенів у промпті (input) |
| `completion.tokens_received` | Кількість токенів у відповіді (output) |

---

### POST /resume — Відновлення сесії

Перевіряє, що сесія існує і належить вказаній компанії. Використовується для reconnect після втрати з'єднання — історія повідомлень зберігається.

```
POST /api/lira-assistants-api/resume
Content-Type: application/json
Authorization: Bearer <LA_API_KEY>
```

#### curl

```bash
curl -X POST https://py-services.oki-toki.net/api/lira-assistants-api/resume \
  -H "Authorization: Bearer <LA_API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{
    "comp_id": 42,
    "assistant_session_id": "550e8400-e29b-41d4-a716-446655440000"
  }'
```

#### Відповідь (200)

```json
{
  "assistant_session_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

---

### POST /close — Закриття сесії

Звільняє ресурси провайдера і видаляє сесію з пам'яті.

```
POST /api/lira-assistants-api/close
Content-Type: application/json
Authorization: Bearer <LA_API_KEY>
```

#### curl

```bash
curl -X POST https://py-services.oki-toki.net/api/lira-assistants-api/close \
  -H "Authorization: Bearer <LA_API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{
    "comp_id": 42,
    "assistant_session_id": "550e8400-e29b-41d4-a716-446655440000"
  }'
```

#### Відповідь (200)

```json
{
  "status": "closed"
}
```

---

## n8n — Формат взаємодії

Наш сервіс відправляє POST на webhook URL:

**Запит до n8n:**
```json
{
  "messages": [
    {"role": "user", "content": "Привіт"}
  ],
  "system_prompt": "Ти оператор колл-центра."
}
```

**n8n-воркфлоу повинен повернути:**
```json
{
  "output": "Доброго дня! Чим можу допомогти?"
}
```

Шлях до тексту налаштовується через `parameters.response_path` (за замовчуванням `"output"`). Підтримується dot-notation: `"data.response.text"` витягне `data → response → text`.

**Параметри n8n (поле `parameters`):**

| Ключ | Тип | За замовч. | Опис |
|------|-----|-----------|------|
| `timeout` | int | 120 | Таймаут HTTP-запиту в секундах |
| `response_path` | string | `"output"` | Шлях до тексту відповіді в JSON |
| `headers` | dict | `{}` | Додаткові HTTP-заголовки |

---

## Повний цикл — Приклад cURL

```bash
LA_KEY="la_zyA_qzp9QS0f6yFFWhyR0-OF8Kf8CqdpXh8HT0uCAVI"
OAI_KEY="sk-proj-..."
API="https://py-services.oki-toki.net/api/lira-assistants-api"

# 1. Створити сесію
RESPONSE=$(curl -s -X POST "$API/create" \
  -H "Authorization: Bearer $LA_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"session_id\": \"call-123\",
    \"comp_id\": 42,
    \"contact_id\": 100,
    \"provider\": \"openai\",
    \"config\": {
      \"api_key\": \"$OAI_KEY\",
      \"model\": \"gpt-4o\",
      \"system_prompt\": \"Ти оператор колл-центра Oki-Toki.\",
      \"temperature\": 0.7,
      \"max_tokens\": 1000
    }
  }")
SESSION=$(echo "$RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin)['assistant_session_id'])")
echo "Сесія створена: $SESSION"

# 2. Перше повідомлення
curl -s -X POST "$API/message" \
  -H "Authorization: Bearer $LA_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"comp_id\": 42,
    \"assistant_session_id\": \"$SESSION\",
    \"messages\": [{\"role\": \"user\", \"content\": \"Привіт, які у вас тарифи?\"}]
  }" | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'AI: {d[\"completion\"][\"text\"]}')"

# 3. Друге повідомлення (AI знає контекст)
curl -s -X POST "$API/message" \
  -H "Authorization: Bearer $LA_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"comp_id\": 42,
    \"assistant_session_id\": \"$SESSION\",
    \"messages\": [{\"role\": \"user\", \"content\": \"А які є знижки?\"}]
  }" | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'AI: {d[\"completion\"][\"text\"]}')"

# 4. Закрити сесію
curl -s -X POST "$API/close" \
  -H "Authorization: Bearer $LA_KEY" \
  -H "Content-Type: application/json" \
  -d "{\"comp_id\": 42, \"assistant_session_id\": \"$SESSION\"}"
echo "Сесію закрито"
```

---

## Приклад — Python

```python
import requests

BASE = "https://py-services.oki-toki.net/api/lira-assistants-api"
HEADERS = {
    "Authorization": "Bearer la_zyA_qzp9QS0f6yFFWhyR0-OF8Kf8CqdpXh8HT0uCAVI",
    "Content-Type": "application/json",
}

# 1. Створити сесію
r = requests.post(f"{BASE}/create", headers=HEADERS, json={
    "session_id": "call-123",
    "comp_id": 42,
    "contact_id": 100,
    "provider": "openai",
    "config": {
        "api_key": "sk-proj-...",
        "model": "gpt-4o",
        "system_prompt": "Ти оператор колл-центра Oki-Toki.",
        "temperature": 0.7,
        "max_tokens": 1000,
    },
})
session_id = r.json()["assistant_session_id"]
print(f"Сесія: {session_id}")

# 2. Відправити повідомлення
r = requests.post(f"{BASE}/message", headers=HEADERS, json={
    "comp_id": 42,
    "assistant_session_id": session_id,
    "messages": [{"role": "user", "content": "Привіт, які у вас тарифи?"}],
})
completion = r.json()["completion"]
print(f"AI: {completion['text']}")
print(f"Токени: {completion['tokens_send']} input + {completion['tokens_received']} output")

# 3. Друге повідомлення (AI знає контекст)
r = requests.post(f"{BASE}/message", headers=HEADERS, json={
    "comp_id": 42,
    "assistant_session_id": session_id,
    "messages": [{"role": "user", "content": "А які є знижки?"}],
})
print(f"AI: {r.json()['completion']['text']}")

# 4. Закрити сесію
requests.post(f"{BASE}/close", headers=HEADERS, json={
    "comp_id": 42,
    "assistant_session_id": session_id,
})
print("Сесію закрито")
```

---

## Приклад — PHP

```php
<?php
$base = "https://py-services.oki-toki.net/api/lira-assistants-api";
$headers = [
    "Authorization: Bearer la_zyA_qzp9QS0f6yFFWhyR0-OF8Kf8CqdpXh8HT0uCAVI",
    "Content-Type: application/json",
];

function apiCall($url, $data, $headers) {
    $ch = curl_init($url);
    curl_setopt($ch, CURLOPT_POST, true);
    curl_setopt($ch, CURLOPT_HTTPHEADER, $headers);
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode($data));
    $response = json_decode(curl_exec($ch), true);
    curl_close($ch);
    return $response;
}

// 1. Створити сесію
$response = apiCall("$base/create", [
    "session_id" => "call-123",
    "comp_id" => 42,
    "contact_id" => 100,
    "provider" => "openai",
    "config" => [
        "api_key" => "sk-proj-...",
        "model" => "gpt-4o",
        "system_prompt" => "Ти оператор колл-центра Oki-Toki.",
        "temperature" => 0.7,
        "max_tokens" => 1000,
    ],
], $headers);
$sessionId = $response["assistant_session_id"];
echo "Сесія: $sessionId\n";

// 2. Відправити повідомлення
$response = apiCall("$base/message", [
    "comp_id" => 42,
    "assistant_session_id" => $sessionId,
    "messages" => [["role" => "user", "content" => "Привіт, які у вас тарифи?"]],
], $headers);
echo "AI: " . $response["completion"]["text"] . "\n";
echo "Токени: " . $response["completion"]["tokens_send"] . " + " . $response["completion"]["tokens_received"] . "\n";

// 3. Закрити сесію
apiCall("$base/close", [
    "comp_id" => 42,
    "assistant_session_id" => $sessionId,
], $headers);
echo "Сесію закрито\n";
?>
```

---

## Каталог помилок

Усі помилки бізнес-логіки (400, 403, 404, 500) повертаються у форматі:
```json
{"error": {"reason": "опис помилки"}}
```

### 401 — Авторизація

| Ситуація | Відповідь | Як виправити |
|----------|-----------|-------------|
| Немає заголовка `Authorization` | `{"detail": "Not authenticated"}` | Додати `Authorization: Bearer <ключ>` |
| Ключ без `Bearer` | `{"detail": "Not authenticated"}` | Формат: `Bearer <ключ>` |
| Невірний ключ | `{"detail": "Invalid API key"}` | Перевірити LA_API_KEY |

### 422 — Валідація полів

| Ситуація | Поле `type` | Як виправити |
|----------|------------|-------------|
| Пропущене обов'язкове поле | `missing` | Додати поле з `loc` |
| comp_id як рядок | `int_parsing` | comp_id — число |
| Невідомий провайдер | `enum` | `provider`: openai, claude, n8n |
| Невалідний JSON | `json_invalid` | Перевірити JSON |
| temperature > 2 | `less_than_equal` | 0 ≤ temperature ≤ 2 |
| max_tokens ≤ 0 | `greater_than` | max_tokens > 0 |

### 400 — Помилка параметрів

| Ситуація | Відповідь | Як виправити |
|----------|-----------|-------------|
| n8n без URL | `n8n provider requires 'url' (webhook endpoint)` | Додати `config.url` |
| Невірний API ключ OpenAI | `AuthenticationError: Incorrect API key...` | Перевірити `config.api_key` |
| Неіснуючий assistant_id | `No assistant found...` | Перевірити ID в OpenAI Dashboard |

### 403 — Чужа сесія

| Ситуація | Відповідь | Як виправити |
|----------|-----------|-------------|
| comp_id не збігається | `comp_id mismatch` | Передати той самий comp_id, що при /create |

### 404 — Сесія не знайдена

| Ситуація | Відповідь | Як виправити |
|----------|-----------|-------------|
| Невірний UUID | `Session '...' not found` | Перевірити ID з /create |
| Сесія закрита | `Session '...' not found` | Створити нову через /create |
| Сервер рестартнувся | `Session '...' not found` | Сесії in-memory — створити нову |

### 500 — Помилка провайдера

| Ситуація | Відповідь | Як виправити |
|----------|-----------|-------------|
| OpenAI rate limit | `RateLimitError: Rate limit reached...` | Зачекати 30–60 сек |
| Claude перевантажений | `OverloadedError: ...` | Зачекати 5–10 сек |
| n8n недоступний | `All connection attempts failed` | Перевірити URL і що n8n запущений |
| n8n HTTP помилка | `Server error '500 INTERNAL SERVER ERROR'...` | Перевірити логи n8n воркфлоу |
| OpenAI Run failed | `OpenAI run failed: failed — ...` | Перевірити конфіг Assistant |
| Перевищено контекст | `BadRequestError: ...maximum context length...` | Закрити сесію, створити нову |

---

## Важливі особливості

| Тема | Деталі |
|------|--------|
| **Сесії** | Зберігаються в пам'яті — при рестарті контейнера втрачаються. Клієнт (LIRA) має обробляти 404 і створювати нову сесію |
| **Історія повідомлень** | Кожен `/message` відправляє провайдеру ВСЮ історію. При довгих діалогах може бути перевищено контекст (128k для GPT-4o) |
| **comp_id** | Ізоляція між компаніями. Сесія прив'язана до comp_id — інший comp_id отримає 403 |
| **Ключі провайдерів** | НЕ зберігаються на сервері. Передаються клієнтом при кожному /create |
| **n8n** | "Чорна скринька" — сервіс відправляє messages + system_prompt на webhook, що всередині воркфлоу — неважливо |
| **OpenAI Assistants** | Створює Thread при /create, видаляє при /close |
| **TEST vs PROD** | Однаковий код, різні URL: `/api/...` (prod), `/test/...` (test) |

---

## Архітектура

```
┌─────────────────────────────────────────────────┐
│                  LIRA (Oki-Toki)                │
└────────┬────────────┬────────────┬──────────────┘
         │ /create    │ /message   │ /close
         ▼            ▼            ▼
┌─────────────────────────────────────────────────┐
│        lira-assistants-api (FastAPI)            │
│        py-services.oki-toki.net                 │
│                                                 │
│  ┌────────────────────────────────────────────┐ │
│  │         SessionManager (in-memory)         │ │
│  │  UUID → {provider, config, history, ...}   │ │
│  └──────────┬──────────┬──────────┬───────────┘ │
│             │          │          │              │
│       ┌─────┴──┐ ┌────┴───┐ ┌───┴────┐         │
│       │ OpenAI │ │ Claude │ │  n8n   │         │
│       │Provider│ │Provider│ │Provider│         │
│       └───┬────┘ └───┬────┘ └───┬────┘         │
└───────────┼──────────┼──────────┼───────────────┘
            ▼          ▼          ▼
      ┌──────────┐ ┌────────┐ ┌────────┐
      │ OpenAI   │ │Anthropic│ │  n8n   │
      │   API    │ │  API   │ │Webhook │
      └──────────┘ └────────┘ └────────┘
```

---

## Структура файлів (в репозиторії)

```
services/lira-assistants-api/
├── server.py              ← FastAPI ендпоінти + документація ReDoc
├── models.py              ← Pydantic-моделі (request/response)
├── session.py             ← SessionManager (in-memory сесії)
├── requirements.txt       ← Залежності (fastapi, openai, anthropic, httpx)
├── __init__.py
├── providers/
│   ├── base.py            ← BaseProvider (абстрактний клас)
│   ├── factory.py         ← get_provider("openai") → OpenAIProvider
│   ├── openai_provider.py ← Chat Completions + Assistants API
│   ├── claude_provider.py ← Anthropic Messages API
│   └── n8n_provider.py    ← HTTP POST на webhook
└── tests/
    └── test_api.py        ← 20 тестів
```

---

## Змінні оточення (.env)

```
LA_PORT=8590                    # Порт сервісу (внутрішній)
LA_API_KEY=la_zyA_...           # Ключ авторизації для доступу до API
LA_DISCORD_WEBHOOK=             # Discord webhook для алертів (опціонально)
```

---

*Документація актуальна на 2026-03-17. Репозиторій: bitbucket.org/dintsin010/py-services*
