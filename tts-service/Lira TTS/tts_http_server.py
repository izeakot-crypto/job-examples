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

import sys, io, os, json, time, wave, asyncio, re, uuid
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = r"[USER_HOME]\Downloads\tts-488311-d5a1cbf88094.json"

from aiohttp import web
from google.cloud import texttospeech_v1beta1 as texttospeech

# ============================================================
# Конфігурація
# ============================================================
HOST = "0.0.0.0"
PORT = 8765
MAX_CONCURRENT = 100    # одночасних запитів до Google
GRPC_CLIENTS = 5        # кількість gRPC з'єднань (HTTP/2 мультиплексинг)
SILENCE_MS = 150
SESSION_TIMEOUT = 300   # 5 хвилин

VOICES = {
    "Leda": "uk-UA-Chirp3-HD-Leda",
    "Puck": "uk-UA-Chirp3-HD-Puck",
    "Kore": "uk-UA-Chirp3-HD-Kore",
    "Aoede": "uk-UA-Chirp3-HD-Aoede",
    "Charon": "uk-UA-Chirp3-HD-Charon",
    "Fenrir": "uk-UA-Chirp3-HD-Fenrir",
}

LOG_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(LOG_DIR, "tts_server.log")

# Сесії: {session_id: {last_activity: time, ...}}
sessions = {}
executor = ThreadPoolExecutor(max_workers=MAX_CONCURRENT)
request_counter = 0

# Глобальні прогріті gRPC клієнти (створюються при старті)
warm_clients = []


# ============================================================
# Логування
# ============================================================

def log(msg, level="INFO"):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    line = f"[{ts}] [{level:>8}] {msg}"
    try:
        print(line)
    except UnicodeEncodeError:
        print(line.encode('utf-8', errors='replace').decode('utf-8'))
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


def generate_tts_part(text, voice_name, client_idx):
    """Генерація однієї частини TTS через глобальний gRPC клієнт"""
    client = warm_clients[client_idx % len(warm_clients)]

    synthesis_input = texttospeech.SynthesisInput(text=text)
    voice = texttospeech.VoiceSelectionParams(
        language_code="uk-UA", name=voice_name,
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


def warmup_global_clients():
    """Прогрів глобальних gRPC клієнтів при старті сервера"""
    global warm_clients
    log(f"Прогрів {GRPC_CLIENTS} gRPC каналів...", "WARMUP")
    t0 = time.time()
    for i in range(GRPC_CLIENTS):
        client = texttospeech.TextToSpeechClient()
        try:
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
        except Exception as e:
            log(f"  Warmup client {i} error: {e}", "WARN")
        warm_clients.append(client)
        log(f"  gRPC client [{i+1}/{GRPC_CLIENTS}] готовий", "WARMUP")
    log(f"Прогрів завершено за {(time.time()-t0)*1000:.0f}мс", "WARMUP")


# ============================================================
# Управління сесіями
# ============================================================

def cleanup_session(session_id):
    if session_id in sessions:
        s = sessions.pop(session_id)
        log(f"Сесія {session_id} закрита (запитів: {s['request_count']}, "
            f"тривалість: {int(time.time() - s['created'])}с)", "SESSION")


async def session_watchdog():
    """Фоновий таск — закриває неактивні сесії"""
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


# ============================================================
# HTTP Ендпоінти
# ============================================================

async def handle_start(request):
    """POST /start — почати сесію, прогріти gRPC"""
    t0 = time.time()

    try:
        body = await request.json()
    except Exception:
        body = {}

    call_id = body.get("call_id", "unknown")
    session_id = str(uuid.uuid4())[:8]

    log(f"", "")
    log(f"{'═' * 60}", "")
    log(f"POST /start — нова сесія", "START")
    log(f"  call_id:    {call_id}")
    log(f"  session_id: {session_id}")
    sessions[session_id] = {
        "created": time.time(),
        "last_activity": time.time(),
        "call_id": call_id,
        "request_count": 0,
        "total_gen_ms": 0,
        "total_chars": 0,
    }

    startup_ms = int((time.time() - t0) * 1000)

    log(f"  gRPC: {len(warm_clients)} глобальних каналів (прогріто при старті)", "START")
    log(f"  Сесія {session_id} готова за {startup_ms}мс", "START")

    return web.json_response({
        "status": "ready",
        "session_id": session_id,
        "call_id": call_id,
        "startup_ms": startup_ms,
        "voices": list(VOICES.keys()),
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
    session_id = body.get("session_id", "")

    if not text:
        return web.json_response({"error": "Empty text"}, status=400)

    if not session_id or session_id not in sessions:
        return web.json_response(
            {"error": f"Invalid session_id: '{session_id}'. Call POST /start first."},
            status=400,
        )

    session = sessions[session_id]
    session["last_activity"] = time.time()
    session["request_count"] += 1
    voice_name = VOICES.get(voice_key, VOICES["Leda"])

    log(f"", "")
    log(f"{'─' * 60}", "")
    log(f"POST /tts — запит #{req_num}", "TTS")
    log(f"  session:  {session_id} (call: {session['call_id']})")
    log(f"  голос:    {voice_key} ({voice_name})")
    log(f"  текст:    \"{text}\"")
    log(f"  довжина:  {len(text)} символів")

    # ── Split ──
    t_split = time.time()
    parts = split_sentences(text)
    total_parts = len(parts)
    split_ms = (time.time() - t_split) * 1000

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
            executor, generate_tts_part, part_text, voice_name, i,
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

    # ── Підсумок ──
    total_ms = (time.time() - t_received) * 1000
    total_cps = int(len(text) / (total_ms / 1000)) if total_ms > 0 else 0

    session["total_gen_ms"] += int(gen_ms)
    session["total_chars"] += len(text)

    log_box(f"РЕЗУЛЬТАТ #{req_num} (сесія {session_id})", [
        f"Текст:              {len(text)} символів",
        f"Частин:             {total_parts} (паралельно)",
        f"Голос:              {voice_key}",
        f"",
        f"Розбивка:           {split_ms:.1f}мс",
        f"Генерація Google:   {gen_ms:.0f}мс",
        f"WAV кодування:      {wav_ms:.1f}мс",
        f"ПОВНИЙ ЧАС:         {total_ms:.0f}мс",
        f"",
        f"CPS (загальний):    {total_cps}",
        f"Аудіо тривалість:   {total_audio_sec:.2f}с",
        f"WAV розмір:         {len(wav_data):,} bytes",
        f"",
        f"Запитів у сесії:    {session['request_count']}",
    ])

    # Повертаємо WAV з метаданими в заголовках
    return web.Response(
        body=wav_data,
        content_type="audio/wav",
        headers={
            "X-TTS-Session": session_id,
            "X-TTS-Total-Ms": str(int(total_ms)),
            "X-TTS-Gen-Ms": str(int(gen_ms)),
            "X-TTS-Parts": str(total_parts),
            "X-TTS-CPS": str(total_cps),
            "X-TTS-Audio-Sec": str(round(total_audio_sec, 2)),
            "X-TTS-Text-Len": str(len(text)),
            "X-TTS-Voice": voice_key,
        },
    )


async def handle_stop(request):
    """POST /stop — закрити сесію"""
    try:
        body = await request.json()
    except Exception:
        body = {}

    session_id = body.get("session_id", "")

    if session_id in sessions:
        s = sessions[session_id]
        duration = int(time.time() - s["created"])
        log(f"", "")
        log(f"POST /stop — закриття сесії {session_id}", "STOP")
        log(f"  call_id:     {s['call_id']}")
        log(f"  тривалість:  {duration}с")
        log(f"  запитів:     {s['request_count']}")
        log(f"  символів:    {s['total_chars']}")
        log(f"  генерація:   {s['total_gen_ms']}мс сумарно")
        cleanup_session(session_id)
        return web.json_response({"status": "closed", "session_id": session_id})
    else:
        return web.json_response({"error": "Session not found"}, status=404)


async def handle_status(request):
    """GET /status — статус сервера"""
    now = time.time()
    active = {}
    for sid, s in sessions.items():
        active[sid] = {
            "call_id": s["call_id"],
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
        "voices": list(VOICES.keys()),
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
    log(f"Голоси:         {', '.join(VOICES.keys())}", "SERVER")
    log(f"Розбивка:       кожне речення окремо", "SERVER")
    log(f"gRPC каналів:   {GRPC_CLIENTS}", "SERVER")
    log(f"Одночасних:     до {MAX_CONCURRENT} запитів", "SERVER")
    log(f"Таймаут сесії:  {SESSION_TIMEOUT}с ({SESSION_TIMEOUT//60} хв)", "SERVER")
    log(f"Формат аудіо:   WAV 8kHz 16bit mono", "SERVER")
    log(f"{'═' * 60}", "SERVER")
    log(f"", "SERVER")
    log(f"Ендпоінти:", "SERVER")
    log(f"  POST /start  — почати сесію (прогрів gRPC)", "SERVER")
    log(f"  POST /tts    — згенерувати TTS → WAV", "SERVER")
    log(f"  POST /stop   — закрити сесію", "SERVER")
    log(f"  GET  /status — статус сервера", "SERVER")
    log(f"", "SERVER")
    # Прогрів gRPC при старті сервера
    warmup_global_clients()

    log(f"", "SERVER")
    log(f"Чекаю curl запитів від LIRA...", "SERVER")
    log(f"{'═' * 60}", "SERVER")

    app = web.Application()
    app.router.add_post("/start", handle_start)
    app.router.add_post("/tts", handle_tts)
    app.router.add_post("/stop", handle_stop)
    app.router.add_get("/status", handle_status)
    app.on_startup.append(on_startup)

    web.run_app(app, host=HOST, port=PORT, print=None)


if __name__ == "__main__":
    main()

