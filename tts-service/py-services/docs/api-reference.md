# API Reference

## Базовый URL

```
https://py-services.oki-toki.net
```

| Среда | Префикс | Пример |
|-------|---------|--------|
| Prod | `/api/` | `/api/translation-checker/health` |
| Test | `/test/` | `/test/translation-checker/health` |

Swagger UI:
- Prod: `/api/<service>/docs`
- Test: `/test/<service>/docs`
- Каталог: `/docs` (prod), `/test-docs` (test)

## Авторизация

Все эндпоинты (кроме health) требуют заголовок:

```
Authorization: Bearer <api_key>
```

---

## Translation Checker

Сервис проверки качества переводов. Режим fire-and-forget — мгновенный ответ, анализ в фоне.

### Health Check

```
GET /api/translation-checker/health
```

Авторизация: не требуется.

**Ответ:**
```json
{
  "status": "ok",
  "service": "translation-checker",
  "version": "2.0.0",
  "mode": "fire-and-forget",
  "ollama_available": true,
  "notifiers": ["TelegramNotifier", "DiscordNotifier"]
}
```

### Проверка переводов (JSON)

```
POST /api/translation-checker/check
Content-Type: application/json
Authorization: Bearer <api_key>
```

**Тело запроса:**
```json
{
  "items": [
    {
      "Оригинал": "Сохранить",
      "EN": "Save",
      "UA": "Зберегти",
      "DE": "Speichern"
    }
  ]
}
```

**Ответ:**
```json
{
  "status": "accepted",
  "message": "Принято 1 элементов для анализа",
  "total_items": 1
}
```

### Проверка переводов (файл)

```
POST /api/translation-checker/check-file
Authorization: Bearer <api_key>
Content-Type: multipart/form-data
```

Поддерживаемые форматы: **JSON**, **CSV**.

**Пример CSV:**
```csv
Оригинал,EN,UA,DE
Сохранить,Save,Зберегти,Speichern
Отменить,Cancel,Скасувати,Abbrechen
```

**cURL:**
```bash
curl -X POST https://py-services.oki-toki.net/api/translation-checker/check-file \
  -H "Authorization: Bearer <api_key>" \
  -F "file=@translations.csv"
```

**Ответ:**
```json
{
  "status": "accepted",
  "message": "Файл 'translations.csv' принят. 2 элементов для анализа",
  "total_items": 2
}
```

### Swagger UI

Интерактивная документация API доступна по адресу:

```
https://py-services.oki-toki.net/api/translation-checker/docs
```

---

## Примеры

### cURL

```bash
# Health check
curl https://py-services.oki-toki.net/api/translation-checker/health

# Отправка JSON
curl -X POST https://py-services.oki-toki.net/api/translation-checker/check \
  -H "Authorization: Bearer tm_..." \
  -H "Content-Type: application/json" \
  -d '{"items": [{"Оригинал": "Тест", "EN": "Test"}]}'

# Отправка файла
curl -X POST https://py-services.oki-toki.net/api/translation-checker/check-file \
  -H "Authorization: Bearer tm_..." \
  -F "file=@data.csv"
```

### Python

```python
import requests

url = "https://py-services.oki-toki.net/api/translation-checker/check"
headers = {"Authorization": "Bearer tm_..."}
data = {
    "items": [
        {"Оригинал": "Сохранить", "EN": "Save", "UA": "Зберегти"}
    ]
}

r = requests.post(url, json=data, headers=headers)
print(r.json())
```

### PHP

```php
$url = "https://py-services.oki-toki.net/api/translation-checker/check";
$headers = ["Authorization: Bearer tm_..."];
$data = json_encode([
    "items" => [
        ["Оригинал" => "Сохранить", "EN" => "Save", "UA" => "Зберегти"]
    ]
]);

$ch = curl_init($url);
curl_setopt($ch, CURLOPT_POST, true);
curl_setopt($ch, CURLOPT_POSTFIELDS, $data);
curl_setopt($ch, CURLOPT_HTTPHEADER, array_merge($headers, ["Content-Type: application/json"]));
curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
$response = curl_exec($ch);
curl_close($ch);

echo $response;
```

---

## TTS Google Chirp3-HD

Сервис синтеза речи через Google Chirp3-HD. Поддерживает 6 голосов, 6 языков, параллельную генерацию и кеширование.

### Health Check

```
GET /api/tts-google-chirp3/health
```

Авторизация: не требуется.

**Ответ:**
```json
{
  "status": "ok",
  "service": "tts-google-chirp3",
  "version": "1.0.0",
  "grpc_ready": true,
  "grpc_clients": 5,
  "active_sessions": 2
}
```

### Открытие сессии

```
POST /api/tts-google-chirp3/open
Content-Type: application/json
Authorization: Bearer <api_key>
```

**Тело запроса:**
```json
{
  "session_id": "call-12345",
  "comp_schema": "billing_1"
}
```

**Ответ (200):**
```json
{
  "status": "ready",
  "session_id": "call-12345",
  "comp_schema": "billing_1",
  "session_key": "call-12345_billing_1",
  "startup_ms": 3200,
  "voices": ["Leda", "Puck", "Kore", "Aoede", "Charon", "Fenrir"],
  "timeout_sec": 300
}
```

### Генерация аудио

```
POST /api/tts-google-chirp3/generate
Content-Type: application/json
Authorization: Bearer <api_key>
```

**Тело запроса:**
```json
{
  "session_id": "call-12345",
  "comp_schema": "billing_1",
  "text": "Дякуємо за дзвінок до компанії Окі-Токі.",
  "voice": "Leda",
  "locale": "uk_UA"
}
```

**Ответ (200):** binary WAV (8kHz 16bit mono) с метаданными в заголовках:

| Заголовок | Описание |
|-----------|----------|
| X-TTS-Session | Ключ сессии |
| X-TTS-Total-Ms | Общее время (мс) |
| X-TTS-Gen-Ms | Время генерации (мс) |
| X-TTS-Parts | Количество частей |
| X-TTS-Audio-Sec | Длительность аудио (с) |
| X-TTS-Text-Len | Длина текста (символов) |
| X-TTS-Voice | Голос |
| X-TTS-Locale | Locale |
| X-TTS-Cache | HIT или MISS |

**Голоса:** Leda, Puck, Kore, Aoede, Charon, Fenrir

**Locales:** uk_UA, ru_RU, en_US, pl_PL, es_ES, tr_TR

### Закрытие сессии

```
POST /api/tts-google-chirp3/close
Content-Type: application/json
Authorization: Bearer <api_key>
```

**Тело запроса:**
```json
{
  "session_id": "call-12345",
  "comp_schema": "billing_1"
}
```

**Ответ (200):**
```json
{
  "status": "closed",
  "session_id": "call-12345",
  "comp_schema": "billing_1"
}
```

### Статус сервера

```
GET /api/tts-google-chirp3/status
Authorization: Bearer <api_key>
```

**Ответ (200):** JSON со статусом сервера, активными сессиями, статистикой кеша и конфигурацией.

### Swagger UI / ReDoc

```
https://py-services.oki-toki.net/api/tts-google-chirp3/docs
https://py-services.oki-toki.net/api/tts-google-chirp3/redoc
```

### Каталог ошибок TTS Google Chirp3-HD

| Код | Ситуация | Тело ответа | Описание |
|-----|----------|-------------|----------|
| 400 | Неизвестная locale | `{"error": "Unsupported locale: 'fr_FR'. Supported: en_US, es_ES, pl_PL, ru_RU, tr_TR, uk_UA"}` | Locale отсутствует в списке поддерживаемых |
| 400 | Сессия не существует | `{"error": "Invalid session. session_id='test', comp_schema='test'. Call POST /open first."}` | /generate без предварительного /open |
| 401 | Неверный API ключ | `{"detail": "Invalid API key"}` | Неверный Bearer-токен в Authorization |
| 401 | Нет Authorization | `{"detail": "Not authenticated"}` | Заголовок Authorization отсутствует или без Bearer |
| 404 | Сессия не найдена | `{"error": "Session not found: session_id='test', comp_schema='test'"}` | /close для уже закрытой или несуществующей сессии |
| 404 | Неизвестный эндпоинт | `{"detail": "Not Found"}` | Несуществующий URL |
| 405 | Неверный HTTP метод | `{"detail": "Method Not Allowed"}` | GET вместо POST или наоборот |
| 422 | Ошибка валидации | `{"detail": [{"type": "missing", "loc": ["body", "session_id"], "msg": "Field required"}]}` | Пропущены обязательные поля или невалидный JSON |
| 500 | Ошибка gRPC warmup | `{"error": "gRPC warmup failed: ServiceUnavailable: ..."}` | Проблема с Google Cloud credentials или сетью при /open |
| 500 | Ошибка Google TTS API | `{"error": "TTS generation failed: ServiceUnavailable: ..."}` | Квота, credentials или сеть при /generate |

### Примеры (cURL)

```bash
# Health check
curl https://py-services.oki-toki.net/api/tts-google-chirp3/health

# Открыть сессию
curl -X POST https://py-services.oki-toki.net/api/tts-google-chirp3/open \
  -H "Authorization: Bearer <api_key>" \
  -H "Content-Type: application/json" \
  -d '{"session_id": "call-123", "comp_schema": "billing_1"}'

# Сгенерировать аудио (WAV)
curl -X POST https://py-services.oki-toki.net/api/tts-google-chirp3/generate \
  -H "Authorization: Bearer <api_key>" \
  -H "Content-Type: application/json" \
  -d '{"session_id": "call-123", "comp_schema": "billing_1", "text": "Привіт!", "voice": "Leda", "locale": "uk_UA"}' \
  -o output.wav

# Закрыть сессию
curl -X POST https://py-services.oki-toki.net/api/tts-google-chirp3/close \
  -H "Authorization: Bearer <api_key>" \
  -H "Content-Type: application/json" \
  -d '{"session_id": "call-123", "comp_schema": "billing_1"}'
```

---

## LIRA Assistants API

Универсальный API-посредник для подключения AI-ассистентов к системе голосовых звонков LIRA (Oki-Toki). Поддерживает три провайдера: OpenAI, Claude, n8n.

### Интерактивная документация

| Среда | Swagger UI | ReDoc |
|-------|-----------|-------|
| **PROD** | [/api/lira-assistants-api/docs](https://py-services.oki-toki.net/api/lira-assistants-api/docs) | [/api/lira-assistants-api/redoc](https://py-services.oki-toki.net/api/lira-assistants-api/redoc) |
| **TEST** | [/test/lira-assistants-api/docs](https://py-services.oki-toki.net/test/lira-assistants-api/docs) | [/test/lira-assistants-api/redoc](https://py-services.oki-toki.net/test/lira-assistants-api/redoc) |

> В ReDoc описаны **все ошибки** с таблицами причин и способов исправления для каждого HTTP-статуса.

### Как это работает

```
Клиент звонит → LIRA → /create → сессия создана (UUID)
                LIRA → /message → "Привет" → OpenAI/Claude/n8n → ответ → LIRA → озвучивает
                LIRA → /message → "Хочу сменить тариф" → (вся история) → ответ
                LIRA → /close → сессия удалена
```

Сервис — **посредник**: принимает запросы от LIRA, перенаправляет в выбранный AI-провайдер и возвращает ответ. Сессия хранит историю сообщений — каждый `/message` отправляет провайдеру полный контекст разговора.

### Авторизация

Все эндпоинты (кроме `/health`) требуют заголовок:

```
Authorization: Bearer <LA_API_KEY>
```

Это ключ доступа к **самому сервису** (задается в `.env` на сервере). Ключи AI-провайдеров (OpenAI, Claude) передает клиент (LIRA) в каждом запросе `/create` через поле `config.api_key`.

### Провайдеры

| Провайдер | Режим | Обязательные поля `config` | Описание |
|-----------|-------|---------------------------|----------|
| `openai` | Chat Completions | `api_key` | Стандартный чат GPT (gpt-4o и др.) |
| `openai` + `assistant_id` | Assistants API | `api_key`, `assistant_id` | Создает Thread, привязывает к Assistant |
| `claude` | Messages API | `api_key` | Anthropic Claude (claude-sonnet-4-20250514 и др.) |
| `n8n` | Webhook HTTP POST | `url` | POST на webhook n8n-воркфлоу |

**Поля `config` (все провайдеры):**

| Поле | Тип | Обяз. | По умолч. | Описание |
|------|-----|-------|-----------|----------|
| `api_key` | string | да | — | API ключ провайдера (OpenAI/Claude) или Bearer токен (n8n) |
| `url` | string | n8n | — | URL эндпоинта (для n8n — webhook URL, для OpenAI/Claude — кастомный base_url) |
| `model` | string | нет | gpt-4o / claude-sonnet-4-20250514 | Модель AI |
| `assistant_id` | string | нет | — | OpenAI Assistant ID (включает режим Assistants API) |
| `system_prompt` | string | нет | — | Системный промпт |
| `temperature` | float | нет | 0.7 | Температура генерации (0–2) |
| `max_tokens` | int | нет | 1000 | Максимум токенов в ответе |

**Поле `parameters`** — словарь vendor-specific параметров (зависит от провайдера):

| Провайдер | Ключ | Описание |
|-----------|------|----------|
| `n8n` | `timeout` | Таймаут HTTP-запроса в секундах (по умолч. 120) |
| `n8n` | `response_path` | Путь к тексту ответа в JSON (по умолч. `"output"`, поддерживает dot-notation: `"data.response.text"`) |
| `n8n` | `headers` | Дополнительные HTTP-заголовки (dict) |
| `openai`, `claude` | любой | Передаются напрямую в API провайдера |

---

### Health Check

```
GET /api/lira-assistants-api/health
```

Авторизация: **не требуется**.

**Ответ (200):**
```json
{
  "status": "ok",
  "service": "lira-assistants-api",
  "version": "1.0.0",
  "environment": "prod"
}
```

---

### POST /create — Создание сессии

```
POST /api/lira-assistants-api/create
Content-Type: application/json
Authorization: Bearer <LA_API_KEY>
```

**Запрос (OpenAI Chat):**
```json
{
  "session_id": "call-123",
  "comp_id": 42,
  "contact_id": 7890,
  "provider": "openai",
  "config": {
    "api_key": "sk-proj-...",
    "model": "gpt-4o",
    "system_prompt": "Ты оператор колл-центра Oki-Toki. Отвечай коротко и по делу.",
    "temperature": 0.7,
    "max_tokens": 1000
  },
  "parameters": {}
}
```

**Запрос (OpenAI Assistants API):**
```json
{
  "session_id": "call-456",
  "comp_id": 42,
  "contact_id": 7890,
  "provider": "openai",
  "config": {
    "api_key": "sk-proj-...",
    "assistant_id": "asst_abc123"
  },
  "parameters": {}
}
```

**Запрос (Claude):**
```json
{
  "session_id": "call-789",
  "comp_id": 42,
  "contact_id": 7890,
  "provider": "claude",
  "config": {
    "api_key": "sk-ant-...",
    "model": "claude-sonnet-4-20250514",
    "system_prompt": "Ты оператор колл-центра.",
    "max_tokens": 2000
  },
  "parameters": {}
}
```

**Запрос (n8n):**
```json
{
  "session_id": "call-101",
  "comp_id": 42,
  "contact_id": 7890,
  "provider": "n8n",
  "config": {
    "url": "https://n8n.example.com/webhook/my-workflow",
    "api_key": "optional-bearer-token",
    "system_prompt": "Ты оператор."
  },
  "parameters": {
    "timeout": 30,
    "response_path": "data.output"
  }
}
```

**Ответ (200):**
```json
{
  "assistant_session_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

---

### POST /resume — Возобновление сессии

Проверяет, что сессия существует и принадлежит указанной компании. Используется для reconnect после потери соединения — история сообщений сохраняется.

```
POST /api/lira-assistants-api/resume
Content-Type: application/json
Authorization: Bearer <LA_API_KEY>
```

**Запрос:**
```json
{
  "comp_id": 42,
  "assistant_session_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Ответ (200):**
```json
{
  "assistant_session_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

---

### POST /message — Отправка сообщения

Добавляет сообщения в историю сессии, отправляет провайдеру **полный контекст** разговора (все предыдущие сообщения + новые) и возвращает ответ.

```
POST /api/lira-assistants-api/message
Content-Type: application/json
Authorization: Bearer <LA_API_KEY>
```

**Запрос:**
```json
{
  "comp_id": 42,
  "assistant_session_id": "550e8400-e29b-41d4-a716-446655440000",
  "messages": [
    {"role": "user", "content": "Привіт, я хочу дізнатися про тарифи"}
  ]
}
```

**Ответ (200):**
```json
{
  "completion": {
    "text": "Здравствуйте! Как я могу помочь вам сегодня?",
    "tokens_send": 33,
    "tokens_received": 12
  }
}
```

| Поле | Описание |
|------|----------|
| `completion.text` | Текст ответа ассистента |
| `completion.tokens_send` | Токены промпта (input) |
| `completion.tokens_received` | Токены ответа (output) |

**Подсчет токенов:** OpenAI и Claude — точный (из `usage` API). n8n — зависит от воркфлоу (если вернет `tokens_send`/`tokens_received` в JSON, они будут учтены; иначе — 0).

---

### POST /close — Закрытие сессии

Освобождает ресурсы провайдера и удаляет сессию из памяти. Для OpenAI Assistants — удаляет Thread.

```
POST /api/lira-assistants-api/close
Content-Type: application/json
Authorization: Bearer <LA_API_KEY>
```

**Запрос:**
```json
{
  "comp_id": 42,
  "assistant_session_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Ответ (200):**
```json
{
  "status": "closed"
}
```

---

### n8n — формат взаимодействия

Сервис отправляет POST на webhook URL:

```json
{
  "messages": [
    {"role": "user", "content": "Привет"}
  ],
  "system_prompt": "Ты оператор колл-центра."
}
```

n8n-воркфлоу должен вернуть JSON с текстом ответа:

```json
{
  "output": "Доброго дня! Чим можу допомогти?"
}
```

Путь к тексту настраивается через `parameters.response_path` (по умолчанию `"output"`). Dot-notation: `"data.response.text"` извлечёт `data → response → text`.

Если воркфлоу вернет `tokens_send` и `tokens_received`, они будут учтены:

```json
{
  "output": "Ответ ассистента",
  "tokens_send": 150,
  "tokens_received": 42
}
```

---

### Каталог ошибок

Все ошибки бизнес-логики (400, 403, 404, 500) возвращаются в формате:
```json
{"error": {"reason": "описание ошибки"}}
```

Ошибки авторизации (401) и валидации (422) — стандартный формат FastAPI.

#### 401 — Авторизация

| Ситуация | Ответ | Решение |
|----------|-------|---------|
| Нет заголовка `Authorization` | `{"detail": "Not authenticated"}` | Добавить `Authorization: Bearer <ключ>` |
| Ключ без `Bearer` | `{"detail": "Not authenticated"}` | Формат: `Bearer <ключ>` |
| Неверный ключ | `{"detail": "Invalid API key"}` | Проверить `LA_API_KEY` в `.env` |

#### 422 — Валидация

| Ситуация | Поле `type` | Решение |
|----------|------------|---------|
| Пропущено обязательное поле | `missing` | Добавить поле из `loc` |
| Неверный тип (comp_id как строка) | `int_parsing` | `comp_id` — число |
| Неизвестный провайдер | `enum` | `provider`: `openai`, `claude`, `n8n` |
| Невалидный JSON | `json_invalid` | Проверить синтаксис JSON |
| temperature > 2 | `less_than_equal` | 0 ≤ temperature ≤ 2 |
| max_tokens ≤ 0 | `greater_than` | max_tokens > 0 |

#### 400 — Ошибка параметров

| Ситуация | Тело ответа | Решение |
|----------|-------------|---------|
| n8n без URL | `{"error":{"reason":"n8n provider requires 'url' (webhook endpoint)"}}` | Добавить `config.url` |
| Невалидный API ключ OpenAI | `{"error":{"reason":"AuthenticationError: Incorrect API key..."}}` | Проверить `config.api_key` |
| Несуществующий assistant_id | `{"error":{"reason":"No assistant found..."}}` | Проверить ID в OpenAI Dashboard |

#### 403 — Чужая сессия

| Ситуация | Тело ответа | Решение |
|----------|-------------|---------|
| comp_id не совпадает | `{"error":{"reason":"comp_id mismatch"}}` | Передать тот же comp_id, что при `/create` |

#### 404 — Сессия не найдена

| Ситуация | Тело ответа | Решение |
|----------|-------------|---------|
| Неверный ID | `{"error":{"reason":"Session '...' not found"}}` | Проверить UUID из `/create` |
| Сессия уже закрыта | то же | Создать новую через `/create` |
| Сервер перезапущен | то же | Сессии in-memory — создать новую |

#### 500 — Ошибка провайдера

| Ситуация | Тело ответа | Решение |
|----------|-------------|---------|
| OpenAI rate limit | `{"error":{"reason":"RateLimitError: Rate limit reached..."}}` | Подождать 30–60 сек |
| Claude перегружен | `{"error":{"reason":"OverloadedError: ..."}}` | Подождать 5–10 сек |
| n8n недоступен | `{"error":{"reason":"All connection attempts failed"}}` | Проверить URL и что n8n запущен |
| n8n HTTP ошибка | `{"error":{"reason":"Server error '500 INTERNAL SERVER ERROR'..."}}` | Проверить логи n8n |
| OpenAI Run failed | `{"error":{"reason":"OpenAI run failed: failed — ..."}}` | Проверить конфиг Assistant |
| Превышен контекст | `{"error":{"reason":"BadRequestError: ...maximum context length..."}}` | Закрыть сессию, создать новую |

---

### Интеграция — Порядок подключения

1. **Получите `LA_API_KEY`** — ключ для доступа к сервису (выдается администратором)
2. **Выберите провайдер** — `openai`, `claude` или `n8n`
3. **Подготовьте API-ключ провайдера** — ключ OpenAI (`sk-proj-...`) или Claude (`sk-ant-...`) или URL n8n-вебхука
4. **Интеграция**:

```
При начале звонка:
  → POST /create (провайдер + ключ + system_prompt) → получить assistant_session_id

При каждой реплике клиента:
  → POST /message (assistant_session_id + сообщения) → получить ответ ассистента

При потере соединения:
  → POST /resume (assistant_session_id) → проверить что сессия жива

При завершении звонка:
  → POST /close (assistant_session_id) → очистить ресурсы
```

---

### Примеры интеграции

#### cURL — полный цикл

```bash
LA_KEY="la_..."     # Ключ доступа к сервису
OAI_KEY="sk-proj-..." # Ключ OpenAI

# 1. Создать сессию
SESSION=$(curl -s -X POST https://py-services.oki-toki.net/api/lira-assistants-api/create \
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
      \"system_prompt\": \"Ты оператор колл-центра Oki-Toki.\",
      \"temperature\": 0.7,
      \"max_tokens\": 1000
    }
  }" | python -c "import sys,json; print(json.load(sys.stdin)['assistant_session_id'])")

echo "Session: $SESSION"

# 2. Отправить сообщение
curl -s -X POST https://py-services.oki-toki.net/api/lira-assistants-api/message \
  -H "Authorization: Bearer $LA_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"comp_id\": 42,
    \"assistant_session_id\": \"$SESSION\",
    \"messages\": [{\"role\": \"user\", \"content\": \"Привет, расскажи о тарифах\"}]
  }"

# 3. Закрыть сессию
curl -s -X POST https://py-services.oki-toki.net/api/lira-assistants-api/close \
  -H "Authorization: Bearer $LA_KEY" \
  -H "Content-Type: application/json" \
  -d "{\"comp_id\": 42, \"assistant_session_id\": \"$SESSION\"}"
```

#### Python

```python
import requests

BASE = "https://py-services.oki-toki.net/api/lira-assistants-api"
HEADERS = {
    "Authorization": "Bearer la_...",
    "Content-Type": "application/json",
}

# 1. Создать сессию
r = requests.post(f"{BASE}/create", headers=HEADERS, json={
    "session_id": "call-123",
    "comp_id": 42,
    "contact_id": 100,
    "provider": "openai",
    "config": {
        "api_key": "sk-proj-...",
        "model": "gpt-4o",
        "system_prompt": "Ты оператор колл-центра.",
    },
})
session_id = r.json()["assistant_session_id"]

# 2. Отправить сообщение
r = requests.post(f"{BASE}/message", headers=HEADERS, json={
    "comp_id": 42,
    "assistant_session_id": session_id,
    "messages": [{"role": "user", "content": "Привет!"}],
})
answer = r.json()["completion"]["text"]
tokens = r.json()["completion"]["tokens_send"] + r.json()["completion"]["tokens_received"]
print(f"Ответ: {answer} ({tokens} токенов)")

# 3. Закрыть
requests.post(f"{BASE}/close", headers=HEADERS, json={
    "comp_id": 42,
    "assistant_session_id": session_id,
})
```

#### PHP

```php
$base = "https://py-services.oki-toki.net/api/lira-assistants-api";
$headers = [
    "Authorization: Bearer la_...",
    "Content-Type: application/json",
];

// 1. Создать сессию
$ch = curl_init("$base/create");
curl_setopt($ch, CURLOPT_POST, true);
curl_setopt($ch, CURLOPT_HTTPHEADER, $headers);
curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode([
    "session_id" => "call-123",
    "comp_id" => 42,
    "contact_id" => 100,
    "provider" => "openai",
    "config" => [
        "api_key" => "sk-proj-...",
        "model" => "gpt-4o",
        "system_prompt" => "Ты оператор колл-центра.",
    ],
]));
$response = json_decode(curl_exec($ch), true);
$session_id = $response["assistant_session_id"];

// 2. Отправить сообщение
curl_setopt($ch, CURLOPT_URL, "$base/message");
curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode([
    "comp_id" => 42,
    "assistant_session_id" => $session_id,
    "messages" => [["role" => "user", "content" => "Привет!"]],
]));
$response = json_decode(curl_exec($ch), true);
echo "Ответ: " . $response["completion"]["text"];

// 3. Закрыть
curl_setopt($ch, CURLOPT_URL, "$base/close");
curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode([
    "comp_id" => 42,
    "assistant_session_id" => $session_id,
]));
curl_exec($ch);
curl_close($ch);
```

---

### Важные особенности

| Тема | Описание |
|------|----------|
| **Сессии** | In-memory — при рестарте контейнера все сессии теряются. LIRA должна обрабатывать 404 и создавать новую сессию |
| **История** | Каждый `/message` отправляет провайдеру ВСЮ историю. При длинных диалогах может быть превышен контекст (128k для GPT-4o) |
| **comp_id** | Изоляция между компаниями. Сессия привязана к comp_id из `/create` — другой comp_id получит 403 |
| **Ключи провайдеров** | НЕ хранятся на сервере. Передаются клиентом в каждом `/create` |
| **n8n** | "Чёрная скринька" — наш сервис отправляет `messages` + `system_prompt` на webhook, а что внутри воркфлоу — неважно |
| **OpenAI Assistants** | Создает Thread в OpenAI при `/create`, удаляет при `/close`. `/message` добавляет сообщение в Thread и запускает Run |
| **TEST vs PROD** | Одинаковый код, разные URL: `/api/...` (prod) vs `/test/...` (test). Используйте TEST для тестирования интеграции |

---

## Коды ответов (общие)

| Код | Описание |
|-----|----------|
| 200 | Успех |
| 400 | Неверный формат данных / невалидные параметры |
| 401 | Нет авторизации или неверный ключ |
| 404 | Эндпоинт не найден / ресурс не найден |
| 405 | Неверный HTTP метод |
| 422 | Ошибка валидации полей запроса |
| 500 | Внутренняя ошибка сервера |
