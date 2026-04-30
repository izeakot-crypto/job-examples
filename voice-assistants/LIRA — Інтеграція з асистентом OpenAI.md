# LIRA: Інтеграція з асистентом OpenAI

> API-посередник для підключення OpenAI (GPT-4o, Assistants) до голосових дзвінків LIRA.
> Клієнт дзвонить → LIRA → API → OpenAI → відповідь → LIRA → озвучує клієнту.

## Зміст

- [Посилання](#посилання)
- [Авторизація](#авторизація)
- [Режими OpenAI](#режими-openai)
- [GET /health](#get-health)
- [Ендпоінти](#ендпоінти)
  - [POST /create](#post-create)
  - [POST /message](#post-message)
  - [POST /resume](#post-resume)
  - [POST /close](#post-close)
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

Це ключ доступу до сервісу. Ключ OpenAI — окремо, в `config.api_key` при `/create`.

---

## Режими OpenAI

OpenAI має два окремих API для роботи з AI. Наш сервіс підтримує обидва.

### Chat Completions — "просто поговорити з GPT"

Стандартний режим. Ти відправляєш повідомлення — GPT відповідає. Ніякого стану на стороні OpenAI: всю історію розмови зберігає наш сервіс і відправляє щоразу повністю. Підходить для більшості сценаріїв: відповіді на питання, консультації, скрипти розмов.

**Увімкнення:** НЕ передавати `assistant_id` в config. Вказати `model` і `system_prompt`.

### Assistants API — "поговорити з налаштованим AI-ботом"

Розширений режим. Спочатку створюєш **Assistant** в [OpenAI Dashboard](https://platform.openai.com/assistants) — це бот зі своїми інструкціями, прикріпленими файлами і tools (Code Interpreter, File Search, Function calling). При `/create` наш сервіс створює **Thread** (розмову) в OpenAI і прив'язує до цього Assistant. Історія зберігається і на нашій стороні, і на стороні OpenAI.

Підходить коли потрібно: пошук по файлах (прайс-листи, інструкції), виконання коду, виклик зовнішніх функцій.

**Увімкнення:** передати `assistant_id` в config. `model` і `system_prompt` беруться з налаштувань Assistant.

### Порівняння

| | Chat Completions | Assistants API |
|-|-------------------|----------------|
| Увімкнення | Без `assistant_id` | З `assistant_id` |
| Стан | Наш сервіс зберігає історію | OpenAI зберігає Thread |
| system_prompt | Передається в `config` | Налаштовується в OpenAI Dashboard |
| Файли | Ні | Так (File Search, прикріплені файли) |
| Tools | Ні | Code Interpreter, Function calling |
| При /close | Нічого | Видаляє Thread в OpenAI |
| Швидкість | Швидше | Повільніше (створення Run, polling) |
| Для чого | Прості діалоги, скрипти | Складні боти з файлами і tools |

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

Створює сесію. Повертає `assistant_session_id` (UUID).

**Chat Completions:**

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
      "system_prompt": "Ти оператор колл-центра. Відповідай коротко, українською.",
      "temperature": 0.7,
      "max_tokens": 1000
    }
  }'
```

**Assistants API:**

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

**Відповідь:**
```json
{"assistant_session_id": "550e8400-e29b-41d4-a716-446655440000"}
```

**Поля запиту:**

| Поле | Тип | Обов. | Опис |
|------|-----|-------|------|
| `session_id` | string | + | ID дзвінка з Oki-Toki |
| `comp_id` | int | + | ID компанії |
| `contact_id` | int | + | ID контакту |
| `provider` | string | + | `"openai"` |
| `config` | object | + | Див. нижче |
| `parameters` | dict | — | Додаткові параметри → передаються в OpenAI напряму |

**Поля config:**

| Поле | Тип | Обов. | Default | Опис |
|------|-----|-------|---------|------|
| `api_key` | string | + | — | Ключ OpenAI `sk-proj-...` |
| `model` | string | — | `gpt-4o` | Модель: gpt-4o, gpt-4o-mini, gpt-4-turbo |
| `assistant_id` | string | — | — | ID з OpenAI Dashboard → вмикає Assistants API |
| `system_prompt` | string | — | — | Системний промпт (Chat mode) |
| `temperature` | float | — | 0.7 | 0–2 |
| `max_tokens` | int | — | 1000 | Макс. токенів відповіді |
| `url` | string | — | — | Кастомний base_url (Azure OpenAI, проксі) |

---

### POST /message

Відправляє повідомлення. Повертає відповідь GPT. Кожен виклик відправляє в OpenAI **всю історію** розмови.

```bash
curl -X POST https://py-services.oki-toki.net/api/lira-assistants-api/message \
  -H "Authorization: Bearer <LA_API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{
    "comp_id": 42,
    "assistant_session_id": "550e8400-e29b-41d4-a716-446655440000",
    "messages": [{"role": "user", "content": "Привіт, розкажи про тарифи"}]
  }'
```

**Поля запиту:**

| Поле | Тип | Обов. | Опис |
|------|-----|-------|------|
| `comp_id` | int | + | ID компанії (той самий що при /create) |
| `assistant_session_id` | string | + | UUID сесії з /create |
| `messages` | array | + | Масив повідомлень `[{"role": "user", "content": "..."}]` |

**Поля messages[]:**

| Поле | Значення | Опис |
|------|----------|------|
| `role` | `"user"` | Повідомлення від клієнта |
| `role` | `"assistant"` | Попередня відповідь AI (для ручного відновлення контексту) |
| `content` | string | Текст повідомлення |

**Відповідь (200):**
```json
{
  "completion": {
    "text": "Доброго дня! У нас є три тарифні плани...",
    "tokens_send": 45,
    "tokens_received": 23
  }
}
```

| Поле | Опис |
|------|------|
| `completion.text` | Текст відповіді GPT |
| `completion.tokens_send` | Токени промпта (input) — точний підрахунок з OpenAI API |
| `completion.tokens_received` | Токени відповіді (output) — точний підрахунок з OpenAI API |

---

### POST /resume

Перевіряє, що сесія жива. Історія зберігається. Для reconnect після обриву.

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

Видаляє сесію. В Assistants API — видаляє Thread в OpenAI. В Chat mode — нічого.

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

## Повний цикл

### cURL

```bash
LA_KEY="<LA_API_KEY>"
OAI_KEY="sk-proj-..."
API="https://py-services.oki-toki.net/api/lira-assistants-api"

# Створити
SESSION=$(curl -s -X POST "$API/create" \
  -H "Authorization: Bearer $LA_KEY" -H "Content-Type: application/json" \
  -d "{\"session_id\":\"call-1\",\"comp_id\":42,\"contact_id\":100,\"provider\":\"openai\",\"config\":{\"api_key\":\"$OAI_KEY\",\"model\":\"gpt-4o\",\"system_prompt\":\"Ти оператор.\"}}" \
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
    "provider": "openai",
    "config": {"api_key": "sk-proj-...", "model": "gpt-4o", "system_prompt": "Ти оператор."},
}).json()["assistant_session_id"]

# Повідомлення
r = requests.post(f"{BASE}/message", headers=H, json={
    "comp_id": 42, "assistant_session_id": sid,
    "messages": [{"role": "user", "content": "Привіт!"}],
}).json()
print(r["completion"]["text"])  # відповідь GPT

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
    "provider"=>"openai",
    "config"=>["api_key"=>"sk-proj-...", "model"=>"gpt-4o", "system_prompt"=>"Ти оператор."]
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
| 401 | Немає Authorization | `Not authenticated` | Додати заголовок `Authorization: Bearer <ключ>` |
| 401 | Невірний ключ | `Invalid API key` | Перевірити LA_API_KEY |
| 422 | Пропущене поле | `Field required` | Додати обов'язкове поле з `loc` |
| 422 | Невірний тип | `int_parsing` | comp_id — число, не рядок |
| 422 | Невідомий provider | `Input should be 'openai', 'claude' or 'n8n'` | Виправити provider |
| 400 | Невірний ключ OpenAI | `AuthenticationError: Incorrect API key...` | Перевірити config.api_key |
| 400 | Невідомий assistant_id | `No assistant found...` | Перевірити ID в OpenAI Dashboard |
| 403 | Чужа сесія | `comp_id mismatch` | Передати той самий comp_id що при /create |
| 404 | Сесія не знайдена | `Session '...' not found` | UUID невірний, сесія закрита або сервер рестартнувся → створити нову |
| 500 | Rate limit OpenAI | `RateLimitError: ...` | Зачекати 30–60 сек |
| 500 | Контекст переповнений | `maximum context length...` | Закрити сесію, створити нову |
| 500 | Run failed (Assistants) | `OpenAI run failed: ...` | Перевірити конфіг Assistant |
| 500 | OpenAI недоступний | `Connection error: ...` | Повторити через 5–10 сек |

Повний каталог з прикладами: [ReDoc →](https://py-services.oki-toki.net/api/lira-assistants-api/redoc)

---

## Обмеження

| Що | Деталі |
|----|--------|
| Сесії | In-memory. При рестарті контейнера — втрачаються. Клієнт має обробляти 404 → створювати нову |
| Історія | Кожен /message шле ВСЮ історію. Ліміт GPT-4o: 128k токенів |
| comp_id | Ізоляція компаній. Інший comp_id → 403 |
| Assistants | Створює Thread при /create, видаляє при /close |
| Chat mode | Stateless. system_prompt → перше повідомлення в масиві |
