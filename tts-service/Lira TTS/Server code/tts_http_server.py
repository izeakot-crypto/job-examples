#!/usr/bin/env python3
"""
TTS HTTP Server — Chirp3-HD з паралельною генерацією
=====================================================
Запуск:  python tts_http_server.py
URL:     http://0.0.0.0:8765

API:
  POST /start  — почати сесію (прогрів gRPC)
  POST /tts    — згенерувати аудіо (повертає WAV)
  POST /stop   — закрити сесію
  GET  /status — статус сервера та сесій

Сесія автоматично закривається через 5 хвилин без запитів.
Лог: tts_server.log (поряд з скриптом)
"""

import sys, os, json, time, wave, asyncio, re, uuid, io, hashlib
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

print("TTS Server starting...", flush=True)

print("Loading libraries...", flush=True)
from aiohttp import web
from google.cloud import texttospeech
print("Libraries loaded.", flush=True)

# Google Cloud credentials — ПІСЛЯ імпорту, щоб не блокувати завантаження
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_SA_PATH = os.path.join(_SCRIPT_DIR, "service-account.json")
if os.path.exists(_SA_PATH):
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = _SA_PATH
elif "GOOGLE_APPLICATION_CREDENTIALS" not in os.environ:
    print("ERROR: service-account.json not found and GOOGLE_APPLICATION_CREDENTIALS not set", flush=True)
    sys.exit(1)
print("Ready.", flush=True)

# ============================================================
# Конфігурація
# ============================================================
HOST = "0.0.0.0"
PORT = 8765
MAX_CONCURRENT = 100    # одночасних запитів до Google
GRPC_CLIENTS = 5        # кількість gRPC з'єднань (HTTP/2 мультиплексинг)
SILENCE_MS = 150
SESSION_TIMEOUT = 300   # 5 хвилин
CACHE_TTL = 86400       # 24 години (секунди)

VOICE_NAMES = ["Leda", "Puck", "Kore", "Aoede", "Charon", "Fenrir"]

SUPPORTED_LOCALES = {
    "uk_UA", "ru_RU", "en_US", "pl_PL", "es_ES", "tr_TR",
}

DEFAULT_LOCALE = "uk_UA"


def normalize_locale(locale):
    """Приймає uk-UA або uk_UA → повертає uk_UA (підкреслення)"""
    return locale.replace("-", "_")


def get_voice_name(voice_key, locale):
    """Повертає повне ім'я голосу: {google_locale}-Chirp3-HD-{voice_key}"""
    if voice_key not in VOICE_NAMES:
        voice_key = "Leda"
    google_locale = locale.replace("_", "-")
    return f"{google_locale}-Chirp3-HD-{voice_key}"

LOG_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(LOG_DIR, "tts_server.log")

# Сесії: {session_id: {last_activity: time, ...}}
sessions = {}
executor = ThreadPoolExecutor(max_workers=MAX_CONCURRENT)
request_counter = 0

# gRPC клієнти — створюються лінво при першому /start
warm_clients = []
grpc_ready = False


# ============================================================
# Логування
# ============================================================

def log(msg, level="INFO"):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    line = f"[{ts}] [{level:>8}] {msg}"
    try:
        sys.stderr.write(line + "\n")
        sys.stderr.flush()
    except Exception:
        pass
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def log_box(title, lines):
    """Красивий блок з результатами"""
    w = max(len(l) for l in lines) + 4
    w = max(w, len(title) + 4)
    log(f"╔{'═' * w}╗")
    log(f"║  {title:<{w-3}}║")
    log(f"╠{'═' * w}╣")
    for l in lines:
        log(f"║  {l:<{w-3}}║")
    log(f"╚{'═' * w}╝")


# ============================================================
# Кеш аудіо (disk)
# ============================================================

CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache")
os.makedirs(CACHE_DIR, exist_ok=True)

cache_hits = 0
cache_misses = 0


def cache_key(text, voice_key, locale):
    """MD5 хеш від locale+voice+text → ім'я файлу"""
    raw = f"{locale}_{voice_key}_{text}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def cache_get(key):
    """Отримати WAV з кешу. Повертає bytes або None."""
    path = os.path.join(CACHE_DIR, f"{key}.wav")
    if not os.path.exists(path):
        return None
    # Перевірити TTL
    age = time.time() - os.path.getmtime(path)
    if age > CACHE_TTL:
        os.remove(path)
        return None
    return open(path, "rb").read()


def cache_put(key, wav_data):
    """Зберегти WAV в кеш."""
    path = os.path.join(CACHE_DIR, f"{key}.wav")
    with open(path, "wb") as f:
        f.write(wav_data)


def cache_cleanup():
    """Видалити файли старші за CACHE_TTL."""
    now = time.time()
    removed = 0
    for fname in os.listdir(CACHE_DIR):
        fpath = os.path.join(CACHE_DIR, fname)
        if os.path.isfile(fpath) and now - os.path.getmtime(fpath) > CACHE_TTL:
            os.remove(fpath)
            removed += 1
    return removed


def cache_stats():
    """Статистика кешу."""
    files = [f for f in os.listdir(CACHE_DIR) if f.endswith(".wav")]
    total_size = sum(os.path.getsize(os.path.join(CACHE_DIR, f)) for f in files)
    return {
        "cached_files": len(files),
        "total_size_mb": round(total_size / (1024 * 1024), 2),
        "cache_hits": cache_hits,
        "cache_misses": cache_misses,
        "hit_rate": f"{cache_hits / max(cache_hits + cache_misses, 1) * 100:.1f}%",
        "ttl_hours": CACHE_TTL // 3600,
    }


# ============================================================
# TTS функції
# ============================================================

def wrap_pcm_to_wav(pcm_data, sample_rate=8000):
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_data)
    return buf.getvalue()


def extract_pcm(audio_data):
    if audio_data[:4] == b'RIFF':
        buf = io.BytesIO(audio_data)
        with wave.open(buf, 'rb') as wf:
            return wf.readframes(wf.getnframes()), wf.getframerate()
    return audio_data, 8000


def split_sentences(text):
    """Розбити текст на окремі речення. Кожне речення — окремий запит."""
    parts = re.split(r'(?<=[.!?])\s+', text.strip())
    parts = [p for p in parts if p.strip()]
    if len(parts) <= 1:
        return [text]
    return parts


def downsample_pcm(pcm_data, from_rate, to_rate):
    """Знизити sample rate PCM"""
    import struct
    samples = struct.unpack(f'<{len(pcm_data)//2}h', pcm_data)
    ratio = from_rate / to_rate
    new_len = int(len(samples) / ratio)
    resampled = [samples[int(i * ratio)] for i in range(new_len) if int(i * ratio) < len(samples)]
    return struct.pack(f'<{len(resampled)}h', *resampled)


def generate_tts_part(text, voice_name, google_locale, client_idx):
    """Генерація однієї частини TTS через глобальний gRPC клієнт"""
    client = warm_clients[client_idx % len(warm_clients)]

    synthesis_input = texttospeech.SynthesisInput(text=text)
    voice = texttospeech.VoiceSelectionParams(
        language_code=google_locale, name=voice_name,
    )
    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.LINEAR16,
        sample_rate_hertz=8000,
    )

    t0 = time.time()
    response = client.synthesize_speech(
        input=synthesis_input, voice=voice, audio_config=audio_config
    )
    gen_time = time.time() - t0

    pcm, actual_rate = extract_pcm(response.audio_content)

    if actual_rate != 8000:
        pcm = downsample_pcm(pcm, actual_rate, 8000)

    audio_sec = len(pcm) / (8000 * 2)
    return pcm, gen_time, len(text), audio_sec


def _warmup_single_client(idx):
    """Прогрів одного gRPC клієнта (для паралельного запуску)"""
    client = texttospeech.TextToSpeechClient()
    client.synthesize_speech(
        input=texttospeech.SynthesisInput(text="тест"),
        voice=texttospeech.VoiceSelectionParams(
            language_code="uk-UA", name="uk-UA-Chirp3-HD-Leda",
        ),
        audio_config=texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.LINEAR16,
            sample_rate_hertz=8000,
        ),
    )
    return client


def warmup_global_clients():
    """Прогрів gRPC клієнтів ПАРАЛЕЛЬНО — викликається при першому /start"""
    global warm_clients, grpc_ready
    if grpc_ready:
        return  # вже прогріто
    log(f"Прогрів {GRPC_CLIENTS} gRPC каналів (паралельно)...", "WARMUP")
    t0 = time.time()
    from concurrent.futures import ThreadPoolExecutor as WarmupPool
    with WarmupPool(max_workers=GRPC_CLIENTS) as pool:
        futures = [pool.submit(_warmup_single_client, i) for i in range(GRPC_CLIENTS)]
        for i, f in enumerate(futures):
            try:
                warm_clients.append(f.result(timeout=30))
                log(f"  gRPC client [{i+1}/{GRPC_CLIENTS}] готовий", "WARMUP")
            except Exception as e:
                log(f"  Warmup client {i} error: {e}", "WARN")
    grpc_ready = True
    log(f"Прогрів завершено за {(time.time()-t0)*1000:.0f}мс ({len(warm_clients)} каналів)", "WARMUP")


def shutdown_global_clients():
    """Закриття gRPC каналів коли немає активних сесій"""
    global warm_clients, grpc_ready
    if not grpc_ready:
        return
    log(f"Закриття {len(warm_clients)} gRPC каналів (немає активних сесій)...", "SHUTDOWN")
    for client in warm_clients:
        try:
            client.transport.close()
        except Exception:
            pass
    warm_clients = []
    grpc_ready = False
    log(f"gRPC канали закриті", "SHUTDOWN")


# ============================================================
# Управління сесіями
# ============================================================

def cleanup_session(session_id):
    if session_id in sessions:
        s = sessions.pop(session_id)
        log(f"Сесія {session_id} закрита (запитів: {s['request_count']}, "
            f"тривалість: {int(time.time() - s['created'])}с)", "SESSION")
        # Якщо більше немає сесій — закриваємо gRPC канали
        if not sessions:
            shutdown_global_clients()


async def session_watchdog():
    """Фоновий таск — закриває неактивні сесії + чистить кеш"""
    cache_check_interval = 0
    while True:
        await asyncio.sleep(30)
        now = time.time()
        expired = [
            sid for sid, s in sessions.items()
            if now - s["last_activity"] > SESSION_TIMEOUT
        ]
        for sid in expired:
            log(f"Сесія {sid} — таймаут {SESSION_TIMEOUT}с без активності", "TIMEOUT")
            cleanup_session(sid)
        # Чистка кешу кожні 30 хвилин
        cache_check_interval += 30
        if cache_check_interval >= 1800:
            cache_check_interval = 0
            removed = cache_cleanup()
            if removed > 0:
                log(f"Кеш: видалено {removed} файлів (TTL {CACHE_TTL//3600}г)", "CACHE")


# ============================================================
# HTTP Ендпоінти
# ============================================================

async def handle_start(request):
    """POST /start — почати сесію, прогріти gRPC якщо потрібно"""
    t0 = time.time()

    try:
        body = await request.json()
    except Exception:
        body = {}

    session_id = body.get("session_id", "")
    comp_schema = body.get("comp_schema", "")

    if not session_id:
        return web.json_response(
            {"error": "session_id is required (your variable)"},
            status=400,
        )
    if not comp_schema:
        return web.json_response(
            {"error": "comp_schema is required (billing variable)"},
            status=400,
        )

    # Ключ сесії = session_id + comp_schema
    session_key = f"{session_id}_{comp_schema}"

    log(f"", "")
    log(f"{'═' * 60}", "")
    log(f"POST /start — нова сесія", "START")
    log(f"  session_id:  {session_id}")
    log(f"  comp_schema: {comp_schema}")
    log(f"  session_key: {session_key}")

    # Прогрів gRPC при першому запиті (або після закриття всіх сесій)
    if not grpc_ready:
        log(f"  gRPC не прогрітий — запускаю прогрів...", "START")
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(executor, warmup_global_clients)
    else:
        log(f"  gRPC: {len(warm_clients)} каналів (вже прогріті)", "START")

    sessions[session_key] = {
        "created": time.time(),
        "last_activity": time.time(),
        "session_id": session_id,
        "comp_schema": comp_schema,
        "request_count": 0,
        "total_gen_ms": 0,
        "total_chars": 0,
    }

    startup_ms = int((time.time() - t0) * 1000)
    log(f"  Сесія {session_key} готова за {startup_ms}мс", "START")

    return web.json_response({
        "status": "ready",
        "session_id": session_id,
        "comp_schema": comp_schema,
        "session_key": session_key,
        "startup_ms": startup_ms,
        "voices": VOICE_NAMES,
        "timeout_sec": SESSION_TIMEOUT,
    })


async def handle_tts(request):
    """POST /tts — згенерувати TTS, повернути WAV"""
    global request_counter
    t_received = time.time()
    request_counter += 1
    req_num = request_counter

    try:
        body = await request.json()
    except Exception:
        return web.json_response({"error": "Invalid JSON"}, status=400)

    text = body.get("text", "")
    voice_key = body.get("voice", "Leda")
    locale = normalize_locale(body.get("locale", DEFAULT_LOCALE))
    session_id = body.get("session_id", "")
    comp_schema = body.get("comp_schema", "")

    if not text:
        return web.json_response({"error": "Empty text"}, status=400)

    if locale not in SUPPORTED_LOCALES:
        return web.json_response(
            {"error": f"Unsupported locale: '{locale}'. Supported: {', '.join(sorted(SUPPORTED_LOCALES))}"},
            status=400,
        )

    session_key = f"{session_id}_{comp_schema}"

    if not session_id or session_key not in sessions:
        return web.json_response(
            {"error": f"Invalid session. session_id='{session_id}', comp_schema='{comp_schema}'. Call POST /start first."},
            status=400,
        )

    google_locale = locale.replace("_", "-")
    session = sessions[session_key]
    session["last_activity"] = time.time()
    session["request_count"] += 1
    voice_name = get_voice_name(voice_key, locale)

    log(f"", "")
    log(f"{'─' * 60}", "")
    log(f"POST /tts — запит #{req_num}", "TTS")
    log(f"  session:  {session_id} | comp: {comp_schema}")
    log(f"  locale:   {locale}")
    log(f"  голос:    {voice_key} ({voice_name})")
    log(f"  текст:    \"{text}\"")
    log(f"  довжина:  {len(text)} символів")

    # ── Кеш ──
    global cache_hits, cache_misses
    ckey = cache_key(text, voice_key, locale)
    cached_wav = cache_get(ckey)

    if cached_wav is not None:
        # CACHE HIT
        cache_hits += 1
        total_ms = (time.time() - t_received) * 1000
        total_audio_sec = (len(cached_wav) - 44) / (8000 * 2)
        session["total_chars"] += len(text)

        log(f"  CACHE HIT: {ckey[:12]}... | {total_ms:.1f}мс | {len(cached_wav):,} bytes", "CACHE")

        return web.Response(
            body=cached_wav,
            content_type="audio/wav",
            headers={
                "X-TTS-Session": session_key,
                "X-TTS-Comp-Schema": comp_schema,
                "X-TTS-Total-Ms": str(int(total_ms)),
                "X-TTS-Gen-Ms": "0",
                "X-TTS-Parts": "0",
                "X-TTS-CPS": str(int(len(text) / (total_ms / 1000)) if total_ms > 0 else 0),
                "X-TTS-Audio-Sec": str(round(total_audio_sec, 2)),
                "X-TTS-Text-Len": str(len(text)),
                "X-TTS-Voice": voice_key,
                "X-TTS-Locale": locale,
                "X-TTS-Cache": "HIT",
            },
        )

    # CACHE MISS — генеруємо
    cache_misses += 1

    # ── Split ──
    t_split = time.time()
    parts = split_sentences(text)
    total_parts = len(parts)
    split_ms = (time.time() - t_split) * 1000

    log(f"  CACHE MISS — генерація...", "CACHE")
    log(f"  розбивка: {total_parts} частин за {split_ms:.1f}мс")
    for i, p in enumerate(parts):
        log(f"    [{i+1}] {len(p)} сим: \"{p}\"")

    # ── Parallel Generation ──
    log(f"  генерація: запуск {total_parts} паралельних gRPC...", "TTS")
    t_gen = time.time()

    loop = asyncio.get_event_loop()
    futures = []
    for i, part_text in enumerate(parts):
        future = loop.run_in_executor(
            executor, generate_tts_part, part_text, voice_name, google_locale, i,
        )
        futures.append(future)

    results = await asyncio.gather(*futures)
    gen_ms = (time.time() - t_gen) * 1000

    # ── Збираємо PCM ──
    silence = b'\x00\x00' * int(8000 * SILENCE_MS / 1000)
    all_pcm = b''
    total_audio_sec = 0.0
    chunk_log = []

    for i, (pcm, part_gen_time, part_chars, audio_sec) in enumerate(results):
        if i < total_parts - 1:
            pcm = pcm + silence
        all_pcm += pcm
        total_audio_sec += audio_sec
        cps = int(part_chars / part_gen_time) if part_gen_time > 0 else 0
        chunk_log.append(
            f"Chunk {i+1}: {part_gen_time*1000:.0f}мс | {part_chars} сим | "
            f"{audio_sec:.2f}с аудіо | CPS {cps}"
        )
        log(f"    chunk {i+1}/{total_parts}: {part_gen_time*1000:.0f}мс | "
            f"{part_chars} сим | {audio_sec:.2f}с аудіо | CPS: {cps}")

    # ── WAV ──
    t_wav = time.time()
    wav_data = wrap_pcm_to_wav(all_pcm)
    wav_ms = (time.time() - t_wav) * 1000

    # ── Зберігаємо в кеш ──
    cache_put(ckey, wav_data)

    # ── Підсумок ──
    total_ms = (time.time() - t_received) * 1000
    total_cps = int(len(text) / (total_ms / 1000)) if total_ms > 0 else 0

    session["total_gen_ms"] += int(gen_ms)
    session["total_chars"] += len(text)

    log_box(f"РЕЗУЛЬТАТ #{req_num} (сесія {session_key})", [
        f"Текст:              {len(text)} символів",
        f"Частин:             {total_parts} (паралельно)",
        f"Голос:              {voice_key} | Locale: {locale}",
        f"",
        f"Розбивка:           {split_ms:.1f}мс",
        f"Генерація Google:   {gen_ms:.0f}мс",
        f"WAV кодування:      {wav_ms:.1f}мс",
        f"ПОВНИЙ ЧАС:         {total_ms:.0f}мс",
        f"",
        f"CPS (загальний):    {total_cps}",
        f"Аудіо тривалість:   {total_audio_sec:.2f}с",
        f"WAV розмір:         {len(wav_data):,} bytes",
        f"Кеш:                SAVED ({ckey[:12]}...)",
        f"",
        f"Запитів у сесії:    {session['request_count']}",
    ])

    # Повертаємо WAV з метаданими в заголовках
    return web.Response(
        body=wav_data,
        content_type="audio/wav",
        headers={
            "X-TTS-Session": session_key,
            "X-TTS-Comp-Schema": comp_schema,
            "X-TTS-Total-Ms": str(int(total_ms)),
            "X-TTS-Gen-Ms": str(int(gen_ms)),
            "X-TTS-Parts": str(total_parts),
            "X-TTS-CPS": str(total_cps),
            "X-TTS-Audio-Sec": str(round(total_audio_sec, 2)),
            "X-TTS-Text-Len": str(len(text)),
            "X-TTS-Voice": voice_key,
            "X-TTS-Locale": locale,
            "X-TTS-Cache": "MISS",
        },
    )


async def handle_stop(request):
    """POST /stop — закрити сесію"""
    try:
        body = await request.json()
    except Exception:
        body = {}

    session_id = body.get("session_id", "")
    comp_schema = body.get("comp_schema", "")
    session_key = f"{session_id}_{comp_schema}"

    if session_key in sessions:
        s = sessions[session_key]
        duration = int(time.time() - s["created"])
        log(f"", "")
        log(f"POST /stop — закриття сесії {session_key}", "STOP")
        log(f"  session_id:  {session_id}")
        log(f"  comp_schema: {comp_schema}")
        log(f"  тривалість:  {duration}с")
        log(f"  запитів:     {s['request_count']}")
        log(f"  символів:    {s['total_chars']}")
        log(f"  генерація:   {s['total_gen_ms']}мс сумарно")
        cleanup_session(session_key)
        return web.json_response({"status": "closed", "session_id": session_id, "comp_schema": comp_schema})
    else:
        return web.json_response({"error": f"Session not found: session_id='{session_id}', comp_schema='{comp_schema}'"}, status=404)


async def handle_status(request):
    """GET /status — статус сервера"""
    now = time.time()
    active = {}
    for sid, s in sessions.items():
        active[sid] = {
            "session_id": s["session_id"],
            "comp_schema": s["comp_schema"],
            "age_sec": int(now - s["created"]),
            "idle_sec": int(now - s["last_activity"]),
            "request_count": s["request_count"],
            "total_chars": s["total_chars"],
            "timeout_in": max(0, SESSION_TIMEOUT - int(now - s["last_activity"])),
        }

    return web.json_response({
        "status": "running",
        "total_requests": request_counter,
        "active_sessions": len(sessions),
        "sessions": active,
        "voices": VOICE_NAMES,
        "locales": sorted(SUPPORTED_LOCALES),
        "cache": cache_stats(),
        "config": {
            "max_concurrent": MAX_CONCURRENT,
            "grpc_clients": GRPC_CLIENTS,
            "session_timeout_sec": SESSION_TIMEOUT,
            "silence_between_chunks_ms": SILENCE_MS,
            "audio_format": "WAV 8kHz 16bit mono",
        },
    })


# ============================================================
# Старт
# ============================================================

async def on_startup(app):
    asyncio.create_task(session_watchdog())


def main():
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        f.write("")

    log(f"{'═' * 60}", "SERVER")
    log(f"TTS HTTP Server — Chirp3-HD", "SERVER")
    log(f"{'═' * 60}", "SERVER")
    log(f"URL:            http://{HOST}:{PORT}", "SERVER")
    log(f"Лог:            {LOG_FILE}", "SERVER")
    log(f"Голоси:         {', '.join(VOICE_NAMES)}", "SERVER")
    log(f"Розбивка:       кожне речення окремо", "SERVER")
    log(f"gRPC каналів:   {GRPC_CLIENTS}", "SERVER")
    log(f"Одночасних:     до {MAX_CONCURRENT} запитів", "SERVER")
    log(f"Таймаут сесії:  {SESSION_TIMEOUT}с ({SESSION_TIMEOUT//60} хв)", "SERVER")
    log(f"Формат аудіо:   WAV 8kHz 16bit mono", "SERVER")
    log(f"Кеш:            {CACHE_DIR} (TTL {CACHE_TTL//3600}г)", "SERVER")
    existing = cache_stats()
    log(f"Кеш файлів:     {existing['cached_files']} ({existing['total_size_mb']} MB)", "SERVER")
    log(f"{'═' * 60}", "SERVER")
    log(f"", "SERVER")
    log(f"Ендпоінти:", "SERVER")
    log(f"  POST /start  — почати сесію (прогріє gRPC при першому виклику)", "SERVER")
    log(f"  POST /tts    — згенерувати TTS → WAV", "SERVER")
    log(f"  POST /stop   — закрити сесію", "SERVER")
    log(f"  GET  /status — статус сервера", "SERVER")
    log(f"", "SERVER")
    log(f"gRPC прогрів: лінивий (при першому POST /start)", "SERVER")
    log(f"", "SERVER")
    log(f"Чекаю curl запитів від LIRA...", "SERVER")
    log(f"{'═' * 60}", "SERVER")

    app = web.Application()
    app.router.add_post("/py-services/tts/open", handle_start)
    app.router.add_post("/py-services/tts/generate", handle_tts)
    app.router.add_post("/py-services/tts/close", handle_stop)
    app.router.add_get("/py-services/tts/status", handle_status)
    app.on_startup.append(on_startup)

    web.run_app(app, host=HOST, port=PORT, print=None)


if __name__ == "__main__":
    main()
