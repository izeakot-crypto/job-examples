#!/usr/bin/env python3
"""
TTS WebSocket Server — Chirp3-HD з паралельною генерацією
=========================================================
Запуск:  python tts_ws_server.py
Порт:    ws://0.0.0.0:8765

Протокол:
  → Клієнт (LIRA) шле JSON:  {"text": "Текст для озвучки", "voice": "Leda"}
  ← Сервер відповідає:
      1) JSON meta → binary WAV (для кожного чанку)
      2) JSON {"type":"done", ...} з повною статистикою

Логування: консоль + файл tts_server.log
"""

import sys, io, os, json, time, wave, asyncio, re
from datetime import datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# Google Cloud credentials — шукаємо service-account.json поряд з скриптом,
# або використовуємо змінну середовища GOOGLE_APPLICATION_CREDENTIALS
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_SA_PATH = os.path.join(_SCRIPT_DIR, "service-account.json")
if os.path.exists(_SA_PATH):
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = _SA_PATH
elif "GOOGLE_APPLICATION_CREDENTIALS" not in os.environ:
    print("ERROR: service-account.json not found and GOOGLE_APPLICATION_CREDENTIALS not set")
    print(f"  Expected path: {_SA_PATH}")
    sys.exit(1)

import websockets
from google.cloud import texttospeech_v1beta1 as texttospeech
from concurrent.futures import ThreadPoolExecutor

# ============================================================
# Конфігурація
# ============================================================
WS_HOST = "0.0.0.0"
WS_PORT = 8765
MAX_PARALLEL = 3
SILENCE_MS = 150

VOICES = {
    "Leda": "uk-UA-Chirp3-HD-Leda",
    "Puck": "uk-UA-Chirp3-HD-Puck",
    "Kore": "uk-UA-Chirp3-HD-Kore",
    "Aoede": "uk-UA-Chirp3-HD-Aoede",
    "Charon": "uk-UA-Chirp3-HD-Charon",
    "Fenrir": "uk-UA-Chirp3-HD-Fenrir",
}

warm_clients = []
executor = ThreadPoolExecutor(max_workers=MAX_PARALLEL)

# Лог файл поряд з скриптом
LOG_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(LOG_DIR, "tts_server.log")

# Лічильник запитів
request_counter = 0


# ============================================================
# Логування
# ============================================================

def log(msg, level="INFO"):
    """Лог у консоль + файл з таймстемпом"""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    line = f"[{ts}] [{level}] {msg}"
    print(line)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def log_separator():
    sep = "─" * 70
    print(sep)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(sep + "\n")


# ============================================================
# Допоміжні функції
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


def split_sentences(text, max_parts=MAX_PARALLEL):
    parts = re.split(r'(?<=[.!?])\s+', text.strip())
    parts = [p for p in parts if p.strip()]
    if len(parts) <= 1:
        return [text]
    if len(parts) <= max_parts:
        return parts
    group_size = len(parts) / max_parts
    groups = []
    for i in range(max_parts):
        start = int(i * group_size)
        end = int((i + 1) * group_size)
        groups.append(' '.join(parts[start:end]))
    return groups


def generate_tts(text, voice_name, client_idx=0):
    """Генерація TTS — повертає (pcm, elapsed, text_len)"""
    if client_idx < len(warm_clients):
        client = warm_clients[client_idx]
    else:
        client = texttospeech.TextToSpeechClient()

    synthesis_input = texttospeech.SynthesisInput(text=text)
    voice = texttospeech.VoiceSelectionParams(
        language_code="uk-UA",
        name=voice_name,
    )
    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.LINEAR16,
        sample_rate_hertz=8000,
    )

    t0 = time.time()
    response = client.synthesize_speech(
        input=synthesis_input, voice=voice, audio_config=audio_config
    )
    elapsed = time.time() - t0

    pcm, _ = extract_pcm(response.audio_content)
    audio_duration = len(pcm) / (8000 * 2)  # секунди аудіо (8kHz 16bit mono)
    return pcm, elapsed, len(text), audio_duration


def warmup_clients(n=MAX_PARALLEL):
    global warm_clients
    log(f"Прогрів {n} gRPC каналів...", "WARMUP")
    t0 = time.time()
    for i in range(n):
        client = texttospeech.TextToSpeechClient()
        try:
            client.synthesize_speech(
                input=texttospeech.SynthesisInput(text="тест"),
                voice=texttospeech.VoiceSelectionParams(
                    language_code="uk-UA",
                    name="uk-UA-Chirp3-HD-Leda",
                ),
                audio_config=texttospeech.AudioConfig(
                    audio_encoding=texttospeech.AudioEncoding.LINEAR16,
                    sample_rate_hertz=8000,
                ),
            )
        except Exception as e:
            log(f"  Warmup client {i} error: {e}", "WARN")
        warm_clients.append(client)
        log(f"  gRPC client [{i+1}/{n}] готовий", "WARMUP")
    log(f"Прогрів завершено за {time.time()-t0:.1f}с", "WARMUP")


# ============================================================
# WebSocket обробник
# ============================================================

async def handle_client(websocket):
    global request_counter
    remote = websocket.remote_address
    client_ip = f"{remote[0]}:{remote[1]}"

    log_separator()
    log(f"Клієнт підключився: {client_ip}", "CONNECT")

    try:
        async for message in websocket:
            t_received = time.time()
            request_counter += 1
            req_num = request_counter

            try:
                data = json.loads(message)
            except json.JSONDecodeError:
                await websocket.send(json.dumps({"type": "error", "message": "Invalid JSON"}))
                log(f"#{req_num} Невалідний JSON від {client_ip}", "ERROR")
                continue

            text = data.get("text", "")
            voice_key = data.get("voice", "Leda")
            request_id = data.get("request_id", str(req_num))

            if not text:
                await websocket.send(json.dumps({"type": "error", "message": "Empty text", "request_id": request_id}))
                continue

            voice_name = VOICES.get(voice_key, VOICES["Leda"])

            log_separator()
            log(f"ЗАПИТ #{req_num}", "REQUEST")
            log(f"  Від:          {client_ip}")
            log(f"  request_id:   {request_id}")
            log(f"  Голос:        {voice_key} ({voice_name})")
            log(f"  Текст:        {text}")
            log(f"  Довжина:      {len(text)} символів")

            # ── SPLIT ──
            t_split_start = time.time()
            parts = split_sentences(text)
            total_parts = len(parts)
            t_split = (time.time() - t_split_start) * 1000

            log(f"  Розбивка:     {total_parts} частин за {t_split:.1f}мс")
            for i, p in enumerate(parts):
                log(f"    Частина {i+1}: [{len(p)} сим] \"{p}\"")

            # ── PARALLEL GENERATION ──
            log(f"  Генерація:    запуск {total_parts} паралельних gRPC запитів...")
            t_gen_start = time.time()

            loop = asyncio.get_event_loop()
            futures = []
            for i, part_text in enumerate(parts):
                future = loop.run_in_executor(
                    executor, generate_tts, part_text, voice_name, i,
                )
                futures.append(future)

            results = await asyncio.gather(*futures)
            t_gen_total = (time.time() - t_gen_start) * 1000

            log(f"  Генерація:    всі {total_parts} частин готові за {t_gen_total:.0f}мс (паралельно)")

            # ── SEND CHUNKS ──
            silence = b'\x00\x00' * int(8000 * SILENCE_MS / 1000)
            total_pcm_bytes = 0
            total_audio_sec = 0.0
            chunk_details = []

            t_send_start = time.time()

            for i, (pcm, gen_time, text_len, audio_sec) in enumerate(results):
                if i < total_parts - 1:
                    pcm = pcm + silence

                wav = wrap_pcm_to_wav(pcm)
                total_pcm_bytes += len(pcm)
                total_audio_sec += audio_sec
                cps = int(text_len / gen_time) if gen_time > 0 else 0

                detail = {
                    "part": i + 1,
                    "text_len": text_len,
                    "gen_ms": int(gen_time * 1000),
                    "audio_sec": round(audio_sec, 2),
                    "wav_bytes": len(wav),
                    "cps": cps,
                }
                chunk_details.append(detail)

                log(f"    Chunk {i+1}/{total_parts}: генерація {gen_time*1000:.0f}мс | "
                    f"{text_len} сим | {audio_sec:.2f}с аудіо | "
                    f"{len(wav)} bytes | CPS: {cps}")

                # Відправка метаданих
                meta = json.dumps({
                    "type": "audio_chunk",
                    "part": i + 1,
                    "total_parts": total_parts,
                    "gen_time_ms": int(gen_time * 1000),
                    "audio_duration_sec": round(audio_sec, 2),
                    "wav_bytes": len(wav),
                    "cps": cps,
                    "request_id": request_id,
                })
                await websocket.send(meta)
                await websocket.send(wav)

            t_send = (time.time() - t_send_start) * 1000

            # ── DONE ──
            t_total = (time.time() - t_received) * 1000
            total_cps = int(len(text) / (t_total / 1000)) if t_total > 0 else 0

            done_msg = json.dumps({
                "type": "done",
                "request_id": request_id,
                "voice": voice_key,
                "text_len": len(text),
                "parts": total_parts,
                "parallel": total_parts > 1,
                "timing": {
                    "split_ms": round(t_split, 1),
                    "generation_ms": round(t_gen_total),
                    "send_ms": round(t_send),
                    "total_ms": round(t_total),
                },
                "audio": {
                    "total_duration_sec": round(total_audio_sec, 2),
                    "total_bytes": total_pcm_bytes,
                },
                "cps": total_cps,
                "chunks": chunk_details,
            })
            await websocket.send(done_msg)

            # ── ПІДСУМОК В ЛОГ ──
            log(f"")
            log(f"  ╔══════════════ РЕЗУЛЬТАТ #{req_num} ══════════════")
            log(f"  ║ Текст:           {len(text)} символів")
            log(f"  ║ Частин:          {total_parts} (паралельно)")
            log(f"  ║ Голос:           {voice_key}")
            log(f"  ║")
            log(f"  ║ Розбивка:        {t_split:.1f}мс")
            log(f"  ║ Генерація Google: {t_gen_total:.0f}мс")
            log(f"  ║ Відправка WS:    {t_send:.0f}мс")
            log(f"  ║ ПОВНИЙ ЧАС:      {t_total:.0f}мс")
            log(f"  ║")
            log(f"  ║ CPS (загальний): {total_cps}")
            log(f"  ║ Аудіо тривалість: {total_audio_sec:.2f}с")
            log(f"  ║ WAV розмір:      {total_pcm_bytes:,} bytes")
            log(f"  ╚{'═'*42}")
            log(f"")

    except websockets.exceptions.ConnectionClosed:
        log(f"Клієнт відключився: {client_ip}", "DISCONNECT")
    except Exception as e:
        log(f"Помилка: {e}", "ERROR")
        import traceback
        log(traceback.format_exc(), "ERROR")


# ============================================================
# Старт
# ============================================================

async def main():
    # Очищаємо лог файл при старті
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        f.write("")

    log_separator()
    log("TTS WebSocket Server — Chirp3-HD", "SERVER")
    log(f"Лог файл: {LOG_FILE}", "SERVER")
    log_separator()

    warmup_clients(MAX_PARALLEL)

    log(f"", "SERVER")
    log(f"Слухаю:       ws://{WS_HOST}:{WS_PORT}", "SERVER")
    log(f"Голоси:       {', '.join(VOICES.keys())}", "SERVER")
    log(f"Паралельність: ×{MAX_PARALLEL}", "SERVER")
    log(f"Формат:       WAV 8kHz 16bit mono", "SERVER")
    log(f"Тиша між чанками: {SILENCE_MS}мс", "SERVER")
    log(f"", "SERVER")
    log(f"Чекаю підключення від LIRA...", "SERVER")
    log_separator()

    async with websockets.serve(handle_client, WS_HOST, WS_PORT):
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
