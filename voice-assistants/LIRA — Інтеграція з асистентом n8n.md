# LIRA: Інтеграція з асистентом n8n

> API-посередник для підключення n8n-воркфлоу як AI-асистента до голосових дзвінків LIRA.
> Клієнт дзвонить → LIRA → API → n8n Webhook → Воркфлоу → відповідь → LIRA → озвучує.
> n8n — "чорна скринька": всередині може бути ChatGPT, RAG, БД, бізнес-логіка.

## Зміст

- [Посилання](#посилання)
- [Авторизація](#авторизація)
- [Як працює n8n інтеграція](#як-працює-n8n-інтеграція)
  - [Що API відправляє в n8n](#що-api-відправляє-в-n8n)
  - [Що n8n повинен повернути](#що-n8n-повинен-повернути)
  - [response_path](#response_path)
- [GET /health](#get-health)
- [Ендпоінти](#ендпоінти)
  - [POST /create](#post-create)
  - [POST /message](#post-message)
  - [POST /resume](#post-resume)
  - [POST /close](#post-close)
- [Приклад n8n-воркфлоу](#приклад-n8n-воркфлоу)
- [Повний цикл](#повний-цикл)
  - [cURL](#curl)
  - [Python](#python)
  - [PHP](#php)
- [Помилки](#помилки)
- [Обмеження](#обмеження)

---

## Посилання

| | PROD | TEST |
|-|------|------|
| ReDoc | https://py-services.oki-toki.net/api/lira-assistants-api/redoc | https://py-services.oki-toki.net/test/lira-assistants-api/redoc |
| Swagger | https://py-services.oki-toki.net/api/lira-assistants-api/docs | https://py-services.oki-toki.net/test/lira-assistants-api/docs |
| Health | https://py-services.oki-toki.net/api/lira-assistants-api/health | https://py-services.oki-toki.net/test/lira-assistants-api/health |

```
PROD: https://py-services.oki-toki.net/api/lira-assistants-api
TEST: https://py-services.oki-toki.net/test/lira-assistants-api
```

---

## Авторизація

Заголовок для всіх запитів (крім `/health`):

```
Authorization: Bearer <LA_API_KEY>
```

Це ключ доступу до сервісу. URL та ключ n8n — окремо, в `config` при `/create`.

---

## Як працює n8n інтеграція

### Що API відправляє в n8n

При кожному `/message` сервіс робить **HTTP POST** на webhook URL:

```json
{
  "messages": [
    {"role": "user", "content": "Привіт"},
    {"role": "assistant", "content": "Доброго дня!"},
    {"role": "user", "content": "Які тарифи?"}
  ],
  "system_prompt": "Ти оператор колл-центра."
}
```

`messages` — **повна історія** розмови. `system_prompt` — якщо був вказаний при `/create`.

### Що n8n повинен повернути

Мінімум:
```json
{"output": "Наразі є три тарифні плани..."}
```

З токенами (опціонально):
```json
{
  "output": "Відповідь асистента",
  "tokens_send": 150,
  "tokens_received": 42
}
```

Без `tokens_send`/`tokens_received` — буде 0.

### response_path

За замовчуванням відповідь береться з ключа `output`. Налаштовується через `parameters.response_path`:

| response_path | JSON від n8n | Результат |
|---------------|-------------|-----------|
| `"output"` | `{"output": "текст"}` | `"текст"` |
| `"data.text"` | `{"data": {"text": "текст"}}` | `"текст"` |
| `"result.response.content"` | `{"result": {"response": {"content": "текст"}}}` | `"текст"` |

---

## GET /health

Перевірка доступності. Авторизація не потрібна.

```bash
curl https://py-services.oki-toki.net/api/lira-assistants-api/health
```

```json
{"status": "ok", "service": "lira-assistants-api", "version": "1.0.0", "environment": "prod"}
```

---

## Ендпоінти

Порядок: `/create` → `/message` (N разів) → `/close`. При обриві зв'язку: `/resume`.

### POST /create

Створює сесію. `config.url` — **обов'язковий** для n8n.

```bash
curl -X POST https://py-services.oki-toki.net/api/lira-assistants-api/create \
  -H "Authorization: Bearer <LA_API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "call-123",
    "comp_id": 42,
    "contact_id": 7890,
    "provider": "n8n",
    "config": {
      "url": "https://n8n.example.com/webhook/my-assistant",
      "api_key": "optional-bearer-token",
      "system_prompt": "Ти оператор колл-центра."
    },
    "parameters": {
      "timeout": 30,
      "response_path": "output"
    }
  }'
```

**Відповідь (200):**
```json
{"assistant_session_id": "550e8400-e29b-41d4-a716-446655440000"}
```

**Поля запиту:**

| Поле | Тип | Обов. | Опис |
|------|-----|-------|------|
| `session_id` | string | + | ID дзвінка з Oki-Toki |
| `comp_id` | int | + | ID компанії |
| `contact_id` | int | + | ID контакту |
| `provider` | string | + | `"n8n"` |
| `config` | object | + | Див. нижче |
| `parameters` | dict | — | Див. нижче |

**Поля config:**

| Поле | Тип | Обов. | Опис |
|------|-----|-------|------|
| `url` | string | **+** | URL webhook ноди в n8n |
| `api_key` | string | — | Bearer токен (якщо webhook захищений) |
| `system_prompt` | string | — | Передається в кожному запиті до n8n |

**Поля parameters:**

| Ключ | Тип | Default | Опис |
|------|-----|---------|------|
| `timeout` | int | 120 | Таймаут запиту до n8n (сек) |
| `response_path` | string | `"output"` | Шлях до тексту в JSON відповіді (dot-notation) |
| `headers` | dict | `{}` | Додаткові HTTP-заголовки |

---

### POST /message

Відправляє повідомлення на n8n webhook. Повертає відповідь воркфлоу.

```bash
curl -X POST https://py-services.oki-toki.net/api/lira-assistants-api/message \
  -H "Authorization: Bearer <LA_API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{
    "comp_id": 42,
    "assistant_session_id": "550e8400-e29b-41d4-a716-446655440000",
    "messages": [{"role": "user", "content": "Які у вас тарифи?"}]
  }'
```

**Поля запиту:**

| Поле | Тип | Обов. | Опис |
|------|-----|-------|------|
| `comp_id` | int | + | ID компанії (той самий що при /create) |
| `assistant_session_id` | string | + | UUID сесії з /create |
| `messages` | array | + | Масив повідомлень `[{"role": "user", "content": "..."}]` |

**Відповідь (200):**
```json
{
  "completion": {
    "text": "У нас є три тарифні плани...",
    "tokens_send": 0,
    "tokens_received": 0
  }
}
```

| Поле | Опис |
|------|------|
| `completion.text` | Текст відповіді від n8n воркфлоу |
| `completion.tokens_send` | Токени input (0, якщо n8n не повертає) |
| `completion.tokens_received` | Токени output (0, якщо n8n не повертає) |

---

### POST /resume

Перевіряє, що сесія жива. Для reconnect після обриву.

```bash
curl -X POST https://py-services.oki-toki.net/api/lira-assistants-api/resume \
  -H "Authorization: Bearer <LA_API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{"comp_id": 42, "assistant_session_id": "550e8400-..."}'
```

**Поля запиту:**

| Поле | Тип | Обов. | Опис |
|------|-----|-------|------|
| `comp_id` | int | + | ID компанії |
| `assistant_session_id` | string | + | UUID сесії з /create |

**Відповідь (200):**
```json
{"assistant_session_id": "550e8400-e29b-41d4-a716-446655440000"}
```

---

### POST /close

Видаляє сесію з пам'яті. n8n stateless — додаткових дій немає.

```bash
curl -X POST https://py-services.oki-toki.net/api/lira-assistants-api/close \
  -H "Authorization: Bearer <LA_API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{"comp_id": 42, "assistant_session_id": "550e8400-..."}'
```

**Поля запиту:**

| Поле | Тип | Обов. | Опис |
|------|-----|-------|------|
| `comp_id` | int | + | ID компанії |
| `assistant_session_id` | string | + | UUID сесії з /create |

**Відповідь (200):**
```json
{"status": "closed"}
```

---

## Приклад n8n-воркфлоу

### Мінімальна схема

```
[Webhook Trigger] → [Code / AI Node] → [Respond to Webhook]
```

### Code нода (JavaScript)

```javascript
const messages = $input.first().json.messages;
const systemPrompt = $input.first().json.system_prompt;
const lastMessage = messages[messages.length - 1].content;

// Ваша логіка: RAG, БД, AI, правила...
const response = `Ви сказали: "${lastMessage}". Чим можу допомогти?`;

return [{ json: { output: response } }];
```

### З OpenAI всередині n8n

```
[Webhook] → [OpenAI Chat Node] → [Set output] → [Respond to Webhook]
```

В OpenAI Chat ноді підставити `{{ $json.messages }}` і `{{ $json.system_prompt }}`.
В Set ноді зібрати `{ "output": "{{ $json.message.content }}" }`.

---

## Повний цикл

### cURL

```bash
LA_KEY="<LA_API_KEY>"
API="https://py-services.oki-toki.net/api/lira-assistants-api"

# Створити
SESSION=$(curl -s -X POST "$API/create" \
  -H "Authorization: Bearer $LA_KEY" -H "Content-Type: application/json" \
  -d '{"session_id":"call-1","comp_id":42,"contact_id":100,"provider":"n8n","config":{"url":"https://n8n.example.com/webhook/test","system_prompt":"Ти оператор."},"parameters":{"timeout":30}}' \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['assistant_session_id'])")

# Повідомлення
curl -s -X POST "$API/message" \
  -H "Authorization: Bearer $LA_KEY" -H "Content-Type: application/json" \
  -d "{\"comp_id\":42,\"assistant_session_id\":\"$SESSION\",\"messages\":[{\"role\":\"user\",\"content\":\"Привіт!\"}]}"

# Закрити
curl -s -X POST "$API/close" \
  -H "Authorization: Bearer $LA_KEY" -H "Content-Type: application/json" \
  -d "{\"comp_id\":42,\"assistant_session_id\":\"$SESSION\"}"
```

### Python

```python
import requests

BASE = "https://py-services.oki-toki.net/api/lira-assistants-api"
H = {"Authorization": "Bearer <LA_API_KEY>"}

# Створити
sid = requests.post(f"{BASE}/create", headers=H, json={
    "session_id": "call-1", "comp_id": 42, "contact_id": 100,
    "provider": "n8n",
    "config": {
        "url": "https://n8n.example.com/webhook/test",
        "system_prompt": "Ти оператор.",
    },
    "parameters": {"timeout": 30},
}).json()["assistant_session_id"]

# Повідомлення
r = requests.post(f"{BASE}/message", headers=H, json={
    "comp_id": 42, "assistant_session_id": sid,
    "messages": [{"role": "user", "content": "Привіт!"}],
}).json()
print(r["completion"]["text"])

# Закрити
requests.post(f"{BASE}/close", headers=H, json={"comp_id": 42, "assistant_session_id": sid})
```

### PHP

```php
<?php
$base = "https://py-services.oki-toki.net/api/lira-assistants-api";
$h = ["Authorization: Bearer <LA_API_KEY>", "Content-Type: application/json"];

function api($url, $data, $h) {
    $ch = curl_init($url);
    curl_setopt_array($ch, [CURLOPT_POST=>1, CURLOPT_HTTPHEADER=>$h,
        CURLOPT_RETURNTRANSFER=>1, CURLOPT_POSTFIELDS=>json_encode($data)]);
    $r = json_decode(curl_exec($ch), true); curl_close($ch); return $r;
}

// Створити
$sid = api("$base/create", [
    "session_id"=>"call-1", "comp_id"=>42, "contact_id"=>100,
    "provider"=>"n8n",
    "config"=>["url"=>"https://n8n.example.com/webhook/test", "system_prompt"=>"Ти оператор."],
    "parameters"=>["timeout"=>30],
], $h)["assistant_session_id"];

// Повідомлення
$r = api("$base/message", [
    "comp_id"=>42, "assistant_session_id"=>$sid,
    "messages"=>[["role"=>"user","content"=>"Привіт!"]]
], $h);
echo $r["completion"]["text"];

// Закрити
api("$base/close", ["comp_id"=>42, "assistant_session_id"=>$sid], $h);
```

---

## Помилки

Формат бізнес-помилок: `{"error": {"reason": "..."}}`. Авторизація/валідація — стандарт FastAPI.

| Код | Причина | Відповідь | Що робити |
|-----|---------|-----------|-----------|
| 401 | Немає Authorization | `Not authenticated` | Додати заголовок |
| 401 | Невірний ключ | `Invalid API key` | Перевірити LA_API_KEY |
| 422 | Пропущене поле | `Field required` | Додати поле з `loc` |
| 422 | Невірний provider | `Input should be 'openai', 'claude' or 'n8n'` | Виправити |
| **400** | **n8n без URL** | `n8n provider requires 'url' (webhook endpoint)` | Додати `config.url` |
| 403 | Чужа сесія | `comp_id mismatch` | Передати той самий comp_id |
| 404 | Сесія не знайдена | `Session '...' not found` | UUID невірний, закрита або сервер рестартнувся → нова сесія |
| **500** | **n8n недоступний** | `All connection attempts failed` | Перевірити URL, чи n8n запущений |
| **500** | **n8n HTTP помилка** | `Server error '500 INTERNAL SERVER ERROR'...` | Перевірити логи воркфлоу |
| **500** | **Таймаут** | `ReadTimeout: ...` | Збільшити `parameters.timeout` або оптимізувати воркфлоу |

Повний каталог з прикладами: [ReDoc →](https://py-services.oki-toki.net/api/lira-assistants-api/redoc)

---

## Обмеження

| Що | Деталі |
|----|--------|
| `config.url` | Обов'язковий. Без нього — 400 |
| Сесії | In-memory. При рестарті — втрачаються. Клієнт обробляє 404 → нова сесія |
| Історія | Кожен /message шле в n8n ВСЮ історію розмови |
| Таймаут | Default 120 сек. Налаштовується через `parameters.timeout` |
| Статусність | n8n stateless. /close — тільки видаляє сесію з пам'яті |
| Bearer auth | Якщо `config.api_key` вказаний → передається як `Authorization: Bearer` в запитах до n8n |
