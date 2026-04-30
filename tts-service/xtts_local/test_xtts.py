#!/usr/bin/env python3
"""
XTTS v2 Local Test Script
Тестування всіх 6 мов: UA, EN, RU, PL, ES, TR
"""

import os
import time
from pathlib import Path

# Створити папку для аудіо
OUTPUT_DIR = Path(__file__).parent / "samples"
OUTPUT_DIR.mkdir(exist_ok=True)

print("=" * 60)
print("XTTS v2 Local Test")
print("=" * 60)

print("\nLoading TTS model (this may take a few minutes on first run)...")
start = time.time()

from TTS.api import TTS

# Завантажити XTTS v2 модель
# Модель автоматично завантажиться при першому запуску (~1.8GB)
tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2")

print(f"Model loaded in {time.time() - start:.1f} seconds")

# Тестові фрази для кожної мови
TEST_PHRASES = {
    "uk": {
        "name": "Ukrainian",
        "text": "Привіт! Це тест українського синтезу мовлення. Як справи?"
    },
    "en": {
        "name": "English",
        "text": "Hello! This is a test of English speech synthesis. How are you?"
    },
    "ru": {
        "name": "Russian",
        "text": "Привет! Это тест русского синтеза речи. Как дела?"
    },
    "pl": {
        "name": "Polish",
        "text": "Cześć! To jest test polskiej syntezy mowy. Jak się masz?"
    },
    "es": {
        "name": "Spanish",
        "text": "¡Hola! Esta es una prueba de síntesis de voz en español. ¿Cómo estás?"
    },
    "tr": {
        "name": "Turkish",
        "text": "Merhaba! Bu Türkçe konuşma sentezi testidir. Nasılsın?"
    }
}

print("\n" + "-" * 60)
print("Testing languages...")
print("-" * 60)

results = []

for lang_code, lang_data in TEST_PHRASES.items():
    lang_name = lang_data["name"]
    text = lang_data["text"]

    print(f"\n[{lang_code.upper()}] {lang_name}")
    print(f"    Text: {text[:50]}...")

    output_file = OUTPUT_DIR / f"xtts_{lang_code}.wav"

    try:
        start = time.time()

        # Генерація аудіо
        # XTTS v2 потребує reference audio для клонування голосу,
        # але може працювати і без нього з дефолтним голосом
        tts.tts_to_file(
            text=text,
            file_path=str(output_file),
            language=lang_code,
            split_sentences=True
        )

        elapsed = time.time() - start
        cps = len(text) / elapsed

        print(f"    OK: {elapsed:.2f}s | CPS: {cps:.1f} | File: {output_file.name}")
        results.append({
            "lang": lang_code,
            "name": lang_name,
            "success": True,
            "time": elapsed,
            "cps": cps,
            "file": str(output_file)
        })

    except Exception as e:
        print(f"    ERROR: {str(e)[:100]}")
        results.append({
            "lang": lang_code,
            "name": lang_name,
            "success": False,
            "error": str(e)
        })

# Підсумок
print("\n" + "=" * 60)
print("RESULTS")
print("=" * 60)

successful = [r for r in results if r["success"]]
print(f"\nSuccessful: {len(successful)}/{len(results)}")

if successful:
    avg_cps = sum(r["cps"] for r in successful) / len(successful)
    print(f"Average CPS: {avg_cps:.2f}")

print(f"\nAudio files saved to: {OUTPUT_DIR}")
print("\nFiles:")
for r in results:
    if r["success"]:
        print(f"  [{r['lang'].upper()}] {r['name']}: {r['file']}")

print("\n" + "=" * 60)
print("Test complete! Listen to the samples in the 'samples' folder")
print("=" * 60)
