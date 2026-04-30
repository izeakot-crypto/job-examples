#!/usr/bin/env python3
"""
TTS WebSocket Server — Chirp3-HD з паралельною генерацією
=========================================================
Запуск:  python tts_ws_server.py
Порт:    ws://0.0.0.0:8765

Протокол:
  → Клієнт шле JSON:  {"text": "Текст для озвучки", "voice": "Leda", "request_id": "123"}
  ← Сервер шле:
      1) binary WAV chunks (частини аудіо, по порядку)
      2) JSON {"type":"done", "request_id":"123", "total_ms": 847, "parts": 3}

Кожен WAV chunk — повноцінний WAV файл 8kHz 16bit mono, який можна зразу грати.
"""

import sys, io, os, json, time, struct, wave, asyncio, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = r"[USER_HOME]\Downloads\tts-488311-d5a1cbf88094.json"

import websockets
from google.cloud import texttospeech_v1beta1 as texttospeech
from concurrent.futures import ThreadPoolExecutor

# ============================================================
# Конфігурація
# ============================================================
WS_HOST = "0.0.0.0"
WS_PORT = 8765
MAX_PARALLEL = 3
SILENCE_MS = 150  # тиша між частинами (мс)

# Доступні голоси Chirp3-HD
VOICES = {
    "Leda": "uk-UA-Chirp3-HD-Leda",
    "Puck": "uk-UA-Chirp3-HD-Puck",
    "Kore": "uk-UA-Chirp3-HD-Kore",
    "Aoede": "uk-UA-Chirp3-HD-Aoede",
    "Charon": "uk-UA-Chirp3-HD-Charon",
    "Fenrir": "uk-UA-Chirp3-HD-Fenrir",
}

# Прогріті gRPC клієнти
warm_clients = []
executor = ThreadPoolExecutor(max_workers=MAX_PARALLEL)

# ============================================================
# Допоміжні функції
# ============================================================

def wrap_pcm_to_wav(pcm_data, sample_rate=8000):
    """PCM → WAV файл"""
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_data)
    return buf.getvalue()


def extract_pcm(audio_data):
    """Витягти чистий PCM з WAV або raw audio"""
    if audio_data[:4] == b'RIFF':
        buf = io.BytesIO(audio_data)
        with wave.open(buf, 'rb') as wf:
            return wf.readframes(wf.getnframes()), wf.getframerate()
    return audio_data, 8000


def split_sentences(text, max_parts=MAX_PARALLEL):
    """Розбити текст на речення для паралельної генерації"""
    # Розбиваємо по реченнях
    parts = re.split(r'(?<=[.!?])\s+', text.strip())
    parts = [p for p in parts if p.strip()]

    if len(parts) <= 1:
        return [text]

    if len(parts) <= max_parts:
        return parts

    # Групуємо речення щоб було max_parts частин
    group_size = len(parts) / max_parts
    groups = []
    for i in range(max_parts):
        start = int(i * group_size)
        end = int((i + 1) * group_size)
        groups.append(' '.join(parts[start:end]))
    return groups


def generate_tts(text, voice_name, client_idx=0):
    """Генерація TTS через Chirp3-HD (синхронна, для ThreadPool)"""
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
    return pcm, elapsed


def warmup_clients(n=MAX_PARALLEL):
    """Прогрів gRPC каналів"""
    global warm_clients
    print(f"[WARMUP] Прогріваю {n} gRPC каналів...")
    t0 = time.time()
    for i in range(n):
        client = texttospeech.TextToSpeechClient()
        # Warmup запит
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
        except Exception:
            pass
        warm_clients.append(client)
    print(f"[WARMUP] Готово за {time.time()-t0:.1f}с")


# ============================================================
# WebSocket обробник
# ============================================================

async def handle_client(websocket):
    """Обробка одного WebSocket клієнта"""
    remote = websocket.remote_address
    print(f"[CONNECT] {remote[0]}:{remote[1]}")

    try:
        async for message in websocket:
            try:
                data = json.loads(message)
            except json.JSONDecodeError:
                await websocket.send(json.dumps({
                    "type": "error",
                    "message": "Invalid JSON"
                }))
                continue

            text = data.get("text", "")
            voice_key = data.get("voice", "Leda")
            request_id = data.get("request_id", str(int(time.time()*1000)))

            if not text:
                await websocket.send(json.dumps({
                    "type": "error",
                    "message": "Empty text",
                    "request_id": request_id,
                }))
                continue

            voice_name = VOICES.get(voice_key, VOICES["Leda"])

            print(f"[REQUEST] id={request_id} voice={voice_key} text={text[:60]}...")

            # Розбиваємо текст
            parts = split_sentences(text)
            total_parts = len(parts)

            print(f"[SPLIT] {total_parts} частин: {[len(p) for p in parts]} символів")

            t_start = time.time()

            # Паралельна генерація
            loop = asyncio.get_event_loop()
            futures = []
            for i, part_text in enumerate(parts):
                future = loop.run_in_executor(
                    executor,
                    generate_tts,
                    part_text,
                    voice_name,
                    i,
                )
                futures.append(future)

            # Збираємо результати ПО ПОРЯДКУ і відправляємо
            results = await asyncio.gather(*futures)

            silence = b'\x00\x00' * int(8000 * SILENCE_MS / 1000)  # 150мс тиші

            for i, (pcm, gen_time) in enumerate(results):
                # Додаємо тишу між частинами (крім останньої)
                if i < total_parts - 1:
                    pcm = pcm + silence

                wav = wrap_pcm_to_wav(pcm)

                # Відправляємо метадані
                meta = json.dumps({
                    "type": "audio_chunk",
                    "part": i + 1,
                    "total_parts": total_parts,
                    "gen_time_ms": int(gen_time * 1000),
                    "pcm_bytes": len(pcm),
                    "wav_bytes": len(wav),
                    "request_id": request_id,
                })
                await websocket.send(meta)

                # Відправляємо binary WAV
                await websocket.send(wav)

                print(f"  [CHUNK {i+1}/{total_parts}] {gen_time:.3f}с, {len(wav)} bytes")

            total_ms = int((time.time() - t_start) * 1000)

            # Фінальне повідомлення
            done_msg = json.dumps({
                "type": "done",
                "request_id": request_id,
                "total_ms": total_ms,
                "parts": total_parts,
                "voice": voice_key,
                "text_len": len(text),
            })
            await websocket.send(done_msg)

            print(f"[DONE] id={request_id} total={total_ms}мс parts={total_parts}")

    except websockets.exceptions.ConnectionClosed:
        print(f"[DISCONNECT] {remote[0]}:{remote[1]}")
    except Exception as e:
        print(f"[ERROR] {e}")


# ============================================================
# Старт сервера
# ============================================================

async def main():
    print("=" * 60)
    print("  TTS WebSocket Server — Chirp3-HD")
    print("=" * 60)

    # Прогрів
    warmup_clients(MAX_PARALLEL)

    print(f"\n[SERVER] Слухаю ws://{WS_HOST}:{WS_PORT}")
    print(f"[SERVER] Голоси: {', '.join(VOICES.keys())}")
    print(f"[SERVER] Паралельність: ×{MAX_PARALLEL}")
    print(f"[SERVER] Чекаю підключення...\n")

    async with websockets.serve(handle_client, WS_HOST, WS_PORT):
        await asyncio.Future()  # run forever


if __name__ == "__main__":
    asyncio.run(main())

