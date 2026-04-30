# Lira TTS Server — API Reference & curl Examples

## Архітектура

```
┌─────────────┐     curl/HTTP      ┌──────────────────┐    gRPC    ┌─────────────────┐
│   Клієнт    │ ──────────────────▶│  Lira TTS Server │──────────▶│  Google Cloud    │
│ (LIRA/curl) │ ◀────────────────── │  (Python/aiohttp)│◀──────────│  Chirp3-HD API   │
│             │     WAV 8kHz        │  PORT: 8765      │  LINEAR16 │  (us-central1)   │
└─────────────┘                     └──────────────────┘           └─────────────────┘
                                           │
                                    ┌──────┴──────┐
                                    │  5 gRPC     │
                                    │  клієнтів   │
                                    │  (pool)     │
                                    └─────────────┘
```

## Формат аудіо

- **WAV 8kHz 16bit mono** (стандарт телефонії)
- Content-Type: `audio/wav`

---

## HTTP API

### 1. POST /start — Ініціалізація сесії

Створює сесію, робить warmup gRPC-з'єднань.

```bash
curl -X POST http://localhost:8765/start \
  -H "Content-Type: application/json" \
  -d '{"call_id": "test_call_001"}'
```

**Відповідь:**
```json
{
  "status": "ready",
  "session_id": "a1b2c3d4",
  "call_id": "test_call_001",
  "startup_ms": 245,
  "voices": ["Leda", "Puck", "Kore", "Aoede", "Charon", "Fenrir"],
  "timeout_sec": 300
}
```

---

### 2. POST /tts — Генерація озвучення

Приймає текст, повертає WAV-файл.

```bash
# Базовий запит — зберегти в файл
curl -X POST http://localhost:8765/tts \
  -H "Content-Type: application/json" \
  -d '{"session_id": "a1b2c3d4", "text": "Дякуємо за дзвінок до компанії Окі-Токі.", "voice": "Leda"}' \
  --output response.wav

# Подивитись заголовки (без збереження аудіо)
curl -X POST http://localhost:8765/tts \
  -H "Content-Type: application/json" \
  -d '{"session_id": "a1b2c3d4", "text": "Дякуємо за дзвінок.", "voice": "Leda"}' \
  -I
```

**Відповідь:** Binary WAV + HTTP-заголовки:

| Заголовок | Опис | Приклад |
|---|---|---|
| `X-TTS-Total-Ms` | Повний час обробки (мс) | `782` |
| `X-TTS-Gen-Ms` | Час генерації Google (мс) | `680` |
| `X-TTS-Parts` | Кількість речень (частин) | `3` |
| `X-TTS-CPS` | Символів за секунду | `236` |
| `X-TTS-Audio-Sec` | Тривалість аудіо (с) | `12.0` |
| `X-TTS-Text-Len` | Довжина тексту | `185` |
| `X-TTS-Voice` | Голос | `Leda` |

---

### 3. POST /stop — Закриття сесії

```bash
curl -X POST http://localhost:8765/stop \
  -H "Content-Type: application/json" \
  -d '{"session_id": "a1b2c3d4"}'
```

**Відповідь:**
```json
{
  "status": "closed",
  "session_id": "a1b2c3d4"
}
```

---

### 4. GET /status — Статус сервера

```bash
curl http://localhost:8765/status
```

**Відповідь:**
```json
{
  "status": "running",
  "total_requests": 42,
  "active_sessions": 2,
  "sessions": { ... },
  "voices": ["Leda", "Puck", "Kore", "Aoede", "Charon", "Fenrir"],
  "config": {
    "max_concurrent": 100,
    "grpc_clients": 5,
    "silence_ms": 150,
    "session_timeout": 300
  }
}
```

---

## Повний сценарій (start → tts → stop)

```bash
#!/bin/bash
SERVER="http://localhost:8765"

# 1. Старт сесії
SESSION=$(curl -s -X POST $SERVER/start \
  -H "Content-Type: application/json" \
  -d '{"call_id": "demo_001"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['session_id'])")

echo "Session: $SESSION"

# 2. Генерація аудіо
curl -s -X POST $SERVER/tts \
  -H "Content-Type: application/json" \
  -d "{\"session_id\": \"$SESSION\", \"text\": \"Дякуємо за дзвінок до компанії Окі-Токі. На жаль, всі оператори зараз зайняті. Будь ласка, залишайтесь на лінії.\", \"voice\": \"Leda\"}" \
  --output greeting.wav

echo "Saved: greeting.wav"

# 3. Ще один запит (інший голос)
curl -s -X POST $SERVER/tts \
  -H "Content-Type: application/json" \
  -d "{\"session_id\": \"$SESSION\", \"text\": \"Зачекайте, будь ласка.\", \"voice\": \"Puck\"}" \
  --output wait.wav

echo "Saved: wait.wav"

# 4. Закриття сесії
curl -s -X POST $SERVER/stop \
  -H "Content-Type: application/json" \
  -d "{\"session_id\": \"$SESSION\"}"

echo "Session closed."
```

---

## Голоси

| Коротка назва | Повна назва Google | Стать |
|---|---|---|
| `Leda` | uk-UA-Chirp3-HD-Leda | Жіночий |
| `Puck` | uk-UA-Chirp3-HD-Puck | Чоловічий |
| `Kore` | uk-UA-Chirp3-HD-Kore | Жіночий |
| `Aoede` | uk-UA-Chirp3-HD-Aoede | Жіночий |
| `Charon` | uk-UA-Chirp3-HD-Charon | Чоловічий |
| `Fenrir` | uk-UA-Chirp3-HD-Fenrir | Чоловічий |

Усього Chirp3-HD має **30 українських голосів** (14 жін. + 16 чол.).

---

## WebSocket API

**Підключення:** `ws://localhost:8765`

### Запит (клієнт → сервер)
```json
{
  "text": "Текст для озвучення",
  "voice": "Leda",
  "request_id": "req_123"
}
```

### Відповідь (сервер → клієнт)

Для кожного речення:
1. **JSON** (метадані чанку):
```json
{
  "type": "audio_chunk",
  "part": 1,
  "total_parts": 3,
  "gen_time_ms": 480,
  "wav_bytes": 34568,
  "request_id": "req_123"
}
```
2. **Binary** (WAV-файл чанку — можна програвати одразу)

Після всіх чанків:
```json
{
  "type": "done",
  "request_id": "req_123",
  "total_ms": 893,
  "parts": 3,
  "voice": "Leda",
  "text_len": 150
}
```

---

## Конфігурація сервера

| Параметр | Значення | Опис |
|---|---|---|
| `PORT` | 8765 | Порт HTTP/WS |
| `MAX_CONCURRENT` | 100 | Макс. одночасних gRPC-запитів |
| `GRPC_CLIENTS` | 5 | Пул gRPC-з'єднань |
| `SILENCE_MS` | 150 | Тиша між реченнями |
| `SESSION_TIMEOUT` | 300с | Автозакриття неактивної сесії |

## Залежності

```
pip install aiohttp google-cloud-texttospeech google-auth
```

## Credentials

Google Cloud Service Account JSON:
```bash
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/tts-488311-d5a1cbf88094.json"
```

## Запуск сервера

```bash
cd "Lira TTS"
python tts_http_server.py
# Server started on http://0.0.0.0:8765
```
