#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TTS Engine — Google Chirp3-HD: gRPC, кеш, паралельна генерація.
"""
import os
import io
import re
import time
import wave
import hashlib
from concurrent.futures import ThreadPoolExecutor

from google.cloud import texttospeech

from shared.logger import get_logger

logger = get_logger("tts-google-chirp3")

# ============================================================
# Конфігурація (з env-змінних з префіксом TGC_)
# ============================================================
GRPC_CLIENTS = int(os.environ.get("TGC_GRPC_CLIENTS", 5))
MAX_CONCURRENT = int(os.environ.get("TGC_MAX_CONCURRENT", 100))
SILENCE_MS = int(os.environ.get("TGC_SILENCE_MS", 150))
SESSION_TIMEOUT = int(os.environ.get("TGC_SESSION_TIMEOUT", 300))
CACHE_TTL = int(os.environ.get("TGC_CACHE_TTL", 86400))

VOICE_NAMES = ["Leda", "Puck", "Kore", "Aoede", "Charon", "Fenrir"]

SUPPORTED_LOCALES = {
    "uk_UA", "ru_RU", "en_US", "pl_PL", "es_ES", "tr_TR",
}
DEFAULT_LOCALE = "uk_UA"

# ============================================================
# gRPC клієнти
# ============================================================
warm_clients: list = []
grpc_ready = False
executor = ThreadPoolExecutor(max_workers=MAX_CONCURRENT)


def normalize_locale(locale: str) -> str:
    """uk-UA або uk_UA → uk_UA"""
    return locale.replace("-", "_")


def to_google_locale(locale: str) -> str:
    """uk_UA → uk-UA (формат Google API)"""
    return locale.replace("_", "-")


def get_voice_name(voice_key: str, locale: str) -> str:
    """Повне ім'я голосу: en-US-Chirp3-HD-Leda"""
    if voice_key not in VOICE_NAMES:
        voice_key = "Leda"
    google_locale = to_google_locale(locale)
    return f"{google_locale}-Chirp3-HD-{voice_key}"


def _warmup_single_client(idx: int):
    """Прогрів одного gRPC клієнта."""
    client = texttospeech.TextToSpeechClient()
    client.synthesize_speech(
        input=texttospeech.SynthesisInput(text="test"),
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
    """Прогрів gRPC клієнтів паралельно."""
    global warm_clients, grpc_ready
    if grpc_ready:
        return
    logger.info(f"Прогрів {GRPC_CLIENTS} gRPC каналів (паралельно)...")
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=GRPC_CLIENTS) as pool:
        futures = [pool.submit(_warmup_single_client, i) for i in range(GRPC_CLIENTS)]
        for i, f in enumerate(futures):
            try:
                warm_clients.append(f.result(timeout=30))
                logger.info(f"  gRPC client [{i+1}/{GRPC_CLIENTS}] готовий")
            except Exception as e:
                logger.warning(f"  Warmup client {i} error: {e}")
    grpc_ready = True
    logger.info(f"Прогрів завершено за {(time.time()-t0)*1000:.0f}мс ({len(warm_clients)} каналів)")


def shutdown_global_clients():
    """Закриття gRPC каналів."""
    global warm_clients, grpc_ready
    if not grpc_ready:
        return
    logger.info(f"Закриття {len(warm_clients)} gRPC каналів...")
    for client in warm_clients:
        try:
            client.transport.close()
        except Exception:
            pass
    warm_clients = []
    grpc_ready = False
    logger.info("gRPC канали закриті")


# ============================================================
# Аудіо обробка
# ============================================================
def wrap_pcm_to_wav(pcm_data: bytes, sample_rate: int = 8000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_data)
    return buf.getvalue()


def extract_pcm(audio_data: bytes) -> tuple:
    if audio_data[:4] == b'RIFF':
        buf = io.BytesIO(audio_data)
        with wave.open(buf, 'rb') as wf:
            return wf.readframes(wf.getnframes()), wf.getframerate()
    return audio_data, 8000


def downsample_pcm(pcm_data: bytes, from_rate: int, to_rate: int) -> bytes:
    import struct
    samples = struct.unpack(f'<{len(pcm_data)//2}h', pcm_data)
    ratio = from_rate / to_rate
    new_len = int(len(samples) / ratio)
    resampled = [samples[int(i * ratio)] for i in range(new_len) if int(i * ratio) < len(samples)]
    return struct.pack(f'<{len(resampled)}h', *resampled)


def split_sentences(text: str) -> list:
    """Розбити текст на речення."""
    parts = re.split(r'(?<=[.!?])\s+', text.strip())
    parts = [p for p in parts if p.strip()]
    if len(parts) <= 1:
        return [text]
    return parts


def generate_tts_part(text: str, voice_name: str, google_locale: str, client_idx: int) -> tuple:
    """Генерація однієї частини TTS через gRPC."""
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


# ============================================================
# Кеш (disk)
# ============================================================
CACHE_DIR = os.environ.get(
    "TGC_CACHE_DIR",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache"),
)
os.makedirs(CACHE_DIR, exist_ok=True)

cache_hits = 0
cache_misses = 0


def cache_key(text: str, voice_key: str, locale: str) -> str:
    """MD5 хеш від locale+voice+text."""
    raw = f"{locale}_{voice_key}_{text}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def cache_get(key: str):
    """Отримати WAV з кешу. Повертає bytes або None."""
    path = os.path.join(CACHE_DIR, f"{key}.wav")
    if not os.path.exists(path):
        return None
    age = time.time() - os.path.getmtime(path)
    if age > CACHE_TTL:
        os.remove(path)
        return None
    with open(path, "rb") as f:
        return f.read()


def cache_put(key: str, wav_data: bytes):
    """Зберегти WAV в кеш."""
    path = os.path.join(CACHE_DIR, f"{key}.wav")
    with open(path, "wb") as f:
        f.write(wav_data)


def cache_cleanup() -> int:
    """Видалити файли старші за CACHE_TTL."""
    now = time.time()
    removed = 0
    for fname in os.listdir(CACHE_DIR):
        fpath = os.path.join(CACHE_DIR, fname)
        if os.path.isfile(fpath) and now - os.path.getmtime(fpath) > CACHE_TTL:
            os.remove(fpath)
            removed += 1
    return removed


def cache_stats() -> dict:
    """Статистика кешу."""
    files = [f for f in os.listdir(CACHE_DIR) if f.endswith(".wav")]
    total_size = sum(os.path.getsize(os.path.join(CACHE_DIR, f)) for f in files)
    total = cache_hits + cache_misses
    return {
        "cached_files": len(files),
        "total_size_mb": round(total_size / (1024 * 1024), 2),
        "cache_hits": cache_hits,
        "cache_misses": cache_misses,
        "hit_rate": f"{cache_hits / max(total, 1) * 100:.1f}%",
        "ttl_hours": CACHE_TTL // 3600,
    }
