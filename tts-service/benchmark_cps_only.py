#!/usr/bin/env python3
"""
StyleTTS2 Ukrainian Benchmark - CPS Only (Fast)
- Тестує всі голоси
- Вимірює тільки CPS (без Whisper)
- Швидкий результат за ~15-20 хвилин
"""

import json
import time
import asyncio
import statistics
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
import httpx

# ============== CONFIGURATION ==============

STYLETTS2_URL = "http://localhost:5002"
LOG_DIR = Path("/opt/tts/benchmark")
LOG_FILE = LOG_DIR / "cps_benchmark.json"
RESULTS_FILE = LOG_DIR / "cps_ratings.json"

DELAY_BETWEEN_TESTS = 0.5  # seconds

# ============== TEST PHRASES (20 phrases for fast test) ==============

TEST_PHRASES = [
    # Basic (5)
    "Доброго дня, мене звати Олександра.",
    "Будь ласка, зачекайте на лінії.",
    "Ваш дзвінок дуже важливий для нас.",
    "Дякуємо, що зателефонували в нашу компанію.",
    "Чим я можу вам допомогти?",
    # Numbers (3)
    "Ваш номер замовлення: сім вісім чотири дев'ять.",
    "Сума до сплати: одна тисяча двісті гривень.",
    "Дата доставки: п'ятнадцяте лютого.",
    # Technical (3)
    "Ваш пароль недійсний, спробуйте ще раз.",
    "Перевірте підключення до інтернету.",
    "Двофакторна автентифікація увімкнена.",
    # Foreign (3)
    "Завантажте файл у форматі PDF.",
    "Оплата через PayPal або Bitcoin.",
    "Підключіться до мережі WiFi.",
    # Questions (3)
    "Ви впевнені, що хочете видалити файл?",
    "Чи можу я поговорити з менеджером?",
    "Скільки це коштує?",
    # Long (3)
    "Шановний клієнте, дякуємо за ваше звернення до нашої служби підтримки.",
    "Натисніть один для продажів, два для підтримки, три для бухгалтерії.",
    "Ваше замовлення буде доставлено завтра, з дев'ятої до вісімнадцятої години.",
]

# ============== BENCHMARK ==============

async def synthesize(text: str, voice: str) -> tuple[int, float]:
    """Synthesize and return (audio_size, time_ms)"""
    start = time.time()
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            f"{STYLETTS2_URL}/tts",
            json={"text": text, "voice": voice, "model": "multi", "speed": 1.0}
        )
        if response.status_code != 200:
            raise Exception(f"HTTP {response.status_code}")
        return len(response.content), (time.time() - start) * 1000


async def test_voice(voice: str) -> Dict[str, Any]:
    """Test all phrases for a voice"""
    results = []
    total = len(TEST_PHRASES)

    for i, phrase in enumerate(TEST_PHRASES, 1):
        try:
            size, time_ms = await synthesize(phrase, voice)
            cps = len(phrase) / (time_ms / 1000)
            results.append({"cps": cps, "time_ms": time_ms, "chars": len(phrase)})
            print(f"  [{i}/{total}] {cps:.1f} CPS | {time_ms:.0f}ms | {len(phrase)} chars")
        except Exception as e:
            print(f"  [{i}/{total}] ERROR: {e}")
            results.append({"error": str(e)})

        await asyncio.sleep(DELAY_BETWEEN_TESTS)

    # Stats
    cps_list = [r["cps"] for r in results if "cps" in r]
    time_list = [r["time_ms"] for r in results if "time_ms" in r]

    if not cps_list:
        return {"voice": voice, "error": "All tests failed"}

    return {
        "voice": voice,
        "tests": len(cps_list),
        "avg_cps": round(statistics.mean(cps_list), 2),
        "min_cps": round(min(cps_list), 2),
        "max_cps": round(max(cps_list), 2),
        "std_cps": round(statistics.stdev(cps_list), 2) if len(cps_list) > 1 else 0,
        "avg_time_ms": round(statistics.mean(time_list), 1),
        "total_time_sec": round(sum(time_list) / 1000, 1)
    }


def calculate_score(stats: Dict) -> float:
    """Score based on CPS and stability (0-100)"""
    if "error" in stats:
        return 0

    # CPS score (70 points max, 15+ CPS = 70)
    cps_score = min(stats["avg_cps"] / 15, 1.0) * 70

    # Stability score (30 points max)
    if stats["avg_cps"] > 0:
        cv = stats["std_cps"] / stats["avg_cps"]
        stability_score = max(0, 30 - (cv * 60))
    else:
        stability_score = 0

    return round(cps_score + stability_score, 1)


async def run_benchmark(voices_to_test: Optional[List[str]] = None):
    """Run full benchmark"""
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    # Load voices
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(f"{STYLETTS2_URL}/voices")
        all_voices = response.json().get("voices", [])

    voices = voices_to_test if voices_to_test else all_voices

    print(f"\n{'='*60}")
    print(f"STYLETTS2 CPS BENCHMARK")
    print(f"Voices: {len(voices)}")
    print(f"Phrases per voice: {len(TEST_PHRASES)}")
    print(f"{'='*60}\n")

    # Run tests
    results = []
    start_time = datetime.now()

    for i, voice in enumerate(voices, 1):
        print(f"\n[{i}/{len(voices)}] {voice}")
        print("-" * 40)

        stats = await test_voice(voice)
        stats["score"] = calculate_score(stats)
        results.append(stats)

        if "error" not in stats:
            print(f"  → AVG: {stats['avg_cps']:.1f} CPS | Score: {stats['score']}/100")

        # Save intermediate
        with open(LOG_FILE, "w", encoding="utf-8") as f:
            json.dump({"timestamp": datetime.now().isoformat(), "results": results}, f, ensure_ascii=False, indent=2)

    # Sort by score
    sorted_results = sorted(results, key=lambda x: x.get("score", 0), reverse=True)

    # Save ratings
    with open(RESULTS_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "generated": datetime.now().isoformat(),
            "duration_sec": (datetime.now() - start_time).total_seconds(),
            "ratings": sorted_results
        }, f, ensure_ascii=False, indent=2)

    # Print report
    elapsed = datetime.now() - start_time
    print(f"\n{'='*60}")
    print(f"RESULTS (sorted by score)")
    print(f"{'='*60}")
    print(f"{'Rank':<5}{'Voice':<35}{'Score':<8}{'CPS':<8}{'Std':<6}")
    print("-" * 60)

    for rank, r in enumerate(sorted_results, 1):
        if "error" in r:
            print(f"{rank:<5}{r['voice']:<35}{'ERROR':<8}")
        else:
            print(f"{rank:<5}{r['voice']:<35}{r['score']:<8.1f}{r['avg_cps']:<8.1f}{r['std_cps']:<6.2f}")

    print("-" * 60)
    print(f"\nTOP 5:")
    for r in sorted_results[:5]:
        if "error" not in r:
            print(f"  • {r['voice']} (Score: {r['score']}, CPS: {r['avg_cps']:.1f})")

    print(f"\nTotal time: {elapsed}")
    print(f"Results saved to: {RESULTS_FILE}")


async def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--voice", type=str, help="Test single voice")
    parser.add_argument("--voices", type=str, help="Comma-separated voices")
    parser.add_argument("--top", type=int, help="Test top N from previous")
    args = parser.parse_args()

    voices = None
    if args.voice:
        voices = [args.voice]
    elif args.voices:
        voices = [v.strip() for v in args.voices.split(",")]
    elif args.top and RESULTS_FILE.exists():
        with open(RESULTS_FILE) as f:
            data = json.load(f)
            voices = [r["voice"] for r in data["ratings"][:args.top]]

    await run_benchmark(voices)


if __name__ == "__main__":
    asyncio.run(main())
