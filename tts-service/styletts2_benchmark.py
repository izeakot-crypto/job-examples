#!/usr/bin/env python3
"""
StyleTTS2 Ukrainian Full Benchmark
- Тестує всі голоси
- Зберігає логи БЕЗ аудіо файлів
- CPS, час генерації, середній CPS
- Система оцінювання
- Оптимізовано для низького споживання RAM
"""

import os
import json
import time
import gc
import asyncio
import statistics
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
import httpx

# ============== CONFIGURATION ==============

STYLETTS2_URL = os.environ.get("STYLETTS2_URL", "http://localhost:5002")
LOG_DIR = Path("/opt/tts/benchmark")
RESULTS_DIR = LOG_DIR / "results"

# Timing
DELAY_BETWEEN_PHRASES = 0.3  # seconds
DELAY_BETWEEN_VOICES = 2.0  # seconds (дати серверу відпочити)

# ============== 60 TEST PHRASES ==============

TEST_PHRASES = {
    "basic": [
        "Доброго дня, мене звати Олександра.",
        "Будь ласка, зачекайте на лінії.",
        "Ваш дзвінок дуже важливий для нас.",
        "Дякуємо, що зателефонували в нашу компанію.",
        "Я передзвоню вам через п'ять хвилин.",
        "Вибачте за незручності.",
        "Чим я можу вам допомогти?",
        "Гарного вам дня!",
        "Будь ласка, назвіть ваше прізвище.",
        "Одну хвилинку, я перевірю інформацію.",
    ],
    "numbers": [
        "Ваш номер замовлення: сім вісім чотири дев'ять.",
        "Сума до сплати: одна тисяча двісті гривень.",
        "Дата доставки: п'ятнадцяте лютого.",
        "Ваш баланс: дві тисячі п'ятсот гривень.",
        "Номер рахунку: два шість один чотири.",
        "Час очікування: три хвилини.",
        "Ваш код підтвердження: сім два дев'ять п'ять.",
        "Знижка становить двадцять відсотків.",
    ],
    "technical": [
        "Ваш пароль недійсний, спробуйте ще раз.",
        "Перевірте підключення до інтернету.",
        "Двофакторна автентифікація увімкнена.",
        "Системна помилка, зверніться до адміністратора.",
        "Ваш обліковий запис заблоковано.",
        "Оновлення програми доступне для завантаження.",
        "Резервне копіювання завершено успішно.",
        "Сесія закінчилась, увійдіть знову.",
    ],
    "foreign": [
        "Завантажте файл у форматі PDF.",
        "Оплата через PayPal або Bitcoin.",
        "Підключіться до мережі WiFi.",
        "Ваш iPhone готовий до видачі.",
        "Відкрийте Google Chrome.",
        "Зателефонуйте через Viber або WhatsApp.",
        "Перегляньте відео на YouTube.",
        "Замовлення з Amazon доставлено.",
    ],
    "questions": [
        "Ви впевнені, що хочете видалити файл?",
        "Чи бажаєте продовжити замовлення?",
        "Коли буде доставлено моє замовлення?",
        "Чи можу я поговорити з менеджером?",
        "Скільки це коштує?",
        "Як довго триває гарантія?",
        "Чи є знижки для постійних клієнтів?",
        "Коли ви працюєте?",
    ],
    "exclamations": [
        "Вітаємо! Ви виграли головний приз!",
        "Увага! Це важливе повідомлення!",
        "Дякуємо за покупку!",
        "На жаль, ваш запит відхилено.",
        "Чудово! Замовлення підтверджено!",
        "Обережно! Термін пропозиції закінчується!",
    ],
    "complex": [
        "Натисніть один для продажів, два для підтримки.",
        "Ваше замовлення буде доставлено завтра з дев'ятої до вісімнадцятої.",
        "Олександр Петрович, ваш рейс затримується на дві години.",
        "У вас три нові повідомлення та два пропущені дзвінки.",
        "Для з'єднання з оператором залишайтеся на лінії.",
        "Якщо ви згодні з умовами, натисніть один.",
    ],
    "names": [
        "Тарас Григорович Шевченко.",
        "Пані Оксана Володимирівна.",
        "Пан Ігор Михайлович.",
        "Директор Андрій Степанович.",
        "Лікар Наталія Сергіївна.",
        "Менеджер Олена Петрівна.",
    ],
    "long": [
        "Шановний клієнте, дякуємо за звернення до нашої служби підтримки, ваш запит зареєстровано під номером сто двадцять три.",
        "Компанія пропонує сучасні рішення для автоматизації кол-центрів з використанням технологій штучного інтелекту.",
        "Для отримання детальної інформації про наші послуги та актуальні ціни відвідайте наш офіційний веб-сайт.",
        "Наші спеціалісти працюють цілодобово без вихідних і завжди готові допомогти вам з будь-яким питанням.",
    ],
}

# ============== SCORING SYSTEM ==============

def calculate_score(avg_cps: float, std_cps: float, success_rate: float) -> float:
    """
    Scoring system (0-100):
    - CPS Performance: 50 points (15+ CPS = max)
    - Stability: 30 points (low std = high score)
    - Reliability: 20 points (100% success = max)
    """
    # CPS score (50 points)
    cps_score = min(avg_cps / 15, 1.0) * 50

    # Stability score (30 points)
    if avg_cps > 0:
        cv = std_cps / avg_cps  # coefficient of variation
        stability_score = max(0, 30 - (cv * 60))
    else:
        stability_score = 0

    # Reliability score (20 points)
    reliability_score = success_rate * 20

    return round(cps_score + stability_score + reliability_score, 1)


def get_grade(score: float) -> str:
    """Convert score to letter grade"""
    if score >= 90: return "A+"
    if score >= 85: return "A"
    if score >= 80: return "A-"
    if score >= 75: return "B+"
    if score >= 70: return "B"
    if score >= 65: return "B-"
    if score >= 60: return "C+"
    if score >= 55: return "C"
    if score >= 50: return "C-"
    if score >= 40: return "D"
    return "F"


# ============== LOGGING ==============

class BenchmarkLogger:
    def __init__(self):
        self.run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = RESULTS_DIR / f"benchmark_{self.run_id}.json"
        self.summary_file = RESULTS_DIR / "latest_summary.json"
        self.rankings_file = RESULTS_DIR / "voice_rankings.json"

        RESULTS_DIR.mkdir(parents=True, exist_ok=True)

        self.data = {
            "run_id": self.run_id,
            "started": datetime.now().isoformat(),
            "config": {
                "url": STYLETTS2_URL,
                "total_phrases": sum(len(p) for p in TEST_PHRASES.values()),
                "categories": list(TEST_PHRASES.keys()),
            },
            "voices": {},
            "rankings": [],
        }

    def log_phrase(self, voice: str, category: str, phrase: str,
                   time_ms: float, cps: float, chars: int, error: str = None):
        """Log single phrase result"""
        if voice not in self.data["voices"]:
            self.data["voices"][voice] = {"phrases": [], "stats": {}}

        self.data["voices"][voice]["phrases"].append({
            "category": category,
            "phrase": phrase[:50],  # Truncate for log size
            "chars": chars,
            "time_ms": round(time_ms, 1),
            "cps": round(cps, 2) if cps else None,
            "error": error,
        })

    def calculate_voice_stats(self, voice: str):
        """Calculate statistics for a voice"""
        phrases = self.data["voices"][voice]["phrases"]

        successful = [p for p in phrases if p["cps"] is not None]
        failed = [p for p in phrases if p["error"] is not None]

        if not successful:
            self.data["voices"][voice]["stats"] = {
                "status": "failed",
                "error_count": len(failed),
            }
            return

        cps_values = [p["cps"] for p in successful]
        time_values = [p["time_ms"] for p in successful]

        stats = {
            "status": "ok",
            "total_phrases": len(phrases),
            "successful": len(successful),
            "failed": len(failed),
            "success_rate": round(len(successful) / len(phrases), 3),

            "avg_cps": round(statistics.mean(cps_values), 2),
            "min_cps": round(min(cps_values), 2),
            "max_cps": round(max(cps_values), 2),
            "std_cps": round(statistics.stdev(cps_values), 2) if len(cps_values) > 1 else 0,

            "avg_time_ms": round(statistics.mean(time_values), 1),
            "total_time_sec": round(sum(time_values) / 1000, 1),

            "by_category": {},
        }

        # Per-category stats
        for cat in TEST_PHRASES.keys():
            cat_phrases = [p for p in successful if p["category"] == cat]
            if cat_phrases:
                cat_cps = [p["cps"] for p in cat_phrases]
                stats["by_category"][cat] = {
                    "count": len(cat_phrases),
                    "avg_cps": round(statistics.mean(cat_cps), 2),
                }

        # Calculate score
        stats["score"] = calculate_score(
            stats["avg_cps"],
            stats["std_cps"],
            stats["success_rate"]
        )
        stats["grade"] = get_grade(stats["score"])

        self.data["voices"][voice]["stats"] = stats

    def generate_rankings(self):
        """Generate voice rankings"""
        rankings = []

        for voice, data in self.data["voices"].items():
            stats = data.get("stats", {})
            if stats.get("status") == "ok":
                rankings.append({
                    "voice": voice,
                    "score": stats["score"],
                    "grade": stats["grade"],
                    "avg_cps": stats["avg_cps"],
                    "std_cps": stats["std_cps"],
                    "success_rate": stats["success_rate"],
                })

        rankings.sort(key=lambda x: x["score"], reverse=True)

        for i, r in enumerate(rankings, 1):
            r["rank"] = i

        self.data["rankings"] = rankings
        return rankings

    def save(self):
        """Save all logs"""
        self.data["finished"] = datetime.now().isoformat()

        # Full log
        with open(self.log_file, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)

        # Summary (without phrase details)
        summary = {
            "run_id": self.run_id,
            "started": self.data["started"],
            "finished": self.data["finished"],
            "total_voices": len(self.data["voices"]),
            "rankings": self.data["rankings"][:10],  # Top 10
            "voice_stats": {v: d["stats"] for v, d in self.data["voices"].items()},
        }
        with open(self.summary_file, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)

        # Rankings only
        with open(self.rankings_file, "w", encoding="utf-8") as f:
            json.dump({
                "generated": datetime.now().isoformat(),
                "rankings": self.data["rankings"]
            }, f, ensure_ascii=False, indent=2)


# ============== BENCHMARK ==============

class StyleTTS2Benchmark:
    def __init__(self):
        self.voices: List[str] = []
        self.logger = BenchmarkLogger()
        self.client = None

    async def init(self):
        """Initialize benchmark"""
        self.client = httpx.AsyncClient(timeout=60.0)

        # Load voices
        response = await self.client.get(f"{STYLETTS2_URL}/voices")
        self.voices = response.json().get("voices", [])
        print(f"✓ Loaded {len(self.voices)} voices")

    async def close(self):
        """Cleanup"""
        if self.client:
            await self.client.aclose()

    async def synthesize(self, text: str, voice: str) -> tuple[int, float]:
        """Synthesize and return (size_bytes, time_ms)"""
        start = time.time()
        response = await self.client.post(
            f"{STYLETTS2_URL}/tts",
            json={"text": text, "voice": voice, "model": "multi", "speed": 1.0}
        )
        elapsed = (time.time() - start) * 1000

        if response.status_code != 200:
            raise Exception(f"HTTP {response.status_code}")

        return len(response.content), elapsed

    async def test_voice(self, voice: str, voice_num: int, total_voices: int):
        """Test single voice"""
        total_phrases = sum(len(p) for p in TEST_PHRASES.values())
        done = 0

        print(f"\n[{voice_num}/{total_voices}] {voice}")
        print("-" * 50)

        for category, phrases in TEST_PHRASES.items():
            for phrase in phrases:
                done += 1
                chars = len(phrase)

                try:
                    size, time_ms = await self.synthesize(phrase, voice)
                    cps = chars / (time_ms / 1000)

                    self.logger.log_phrase(voice, category, phrase, time_ms, cps, chars)
                    print(f"  [{done}/{total_phrases}] {cps:5.1f} CPS | {time_ms:6.0f}ms | {chars:3d}ch")

                except Exception as e:
                    self.logger.log_phrase(voice, category, phrase, 0, None, chars, str(e))
                    print(f"  [{done}/{total_phrases}] ERROR: {str(e)[:40]}")

                await asyncio.sleep(DELAY_BETWEEN_PHRASES)

                # Memory cleanup every 20 phrases
                if done % 20 == 0:
                    gc.collect()

        # Calculate stats
        self.logger.calculate_voice_stats(voice)
        stats = self.logger.data["voices"][voice]["stats"]

        if stats.get("status") == "ok":
            print(f"  → CPS: {stats['avg_cps']:.1f} | Score: {stats['score']}/100 | Grade: {stats['grade']}")
        else:
            print(f"  → FAILED")

        # Save intermediate results
        self.logger.save()

        # Rest before next voice
        await asyncio.sleep(DELAY_BETWEEN_VOICES)
        gc.collect()

    async def run(self, voices_to_test: List[str] = None, start_from: int = 0):
        """Run full benchmark"""
        await self.init()

        voices = voices_to_test if voices_to_test else self.voices
        voices = voices[start_from:]  # Allow resuming

        total_phrases = sum(len(p) for p in TEST_PHRASES.values())

        print(f"\n{'='*60}")
        print(f"STYLETTS2 BENCHMARK")
        print(f"{'='*60}")
        print(f"Voices: {len(voices)}")
        print(f"Phrases per voice: {total_phrases}")
        print(f"Total tests: {len(voices) * total_phrases}")
        print(f"Estimated time: ~{len(voices) * 3} minutes")
        print(f"{'='*60}")

        start_time = datetime.now()

        for i, voice in enumerate(voices, 1):
            await self.test_voice(voice, i, len(voices))

        # Generate final rankings
        rankings = self.logger.generate_rankings()
        self.logger.save()

        await self.close()

        # Print final report
        elapsed = datetime.now() - start_time

        print(f"\n{'='*60}")
        print(f"FINAL RANKINGS")
        print(f"{'='*60}")
        print(f"{'Rank':<5}{'Voice':<30}{'Score':<8}{'Grade':<6}{'CPS':<8}")
        print("-" * 60)

        for r in rankings[:15]:
            print(f"{r['rank']:<5}{r['voice']:<30}{r['score']:<8.1f}{r['grade']:<6}{r['avg_cps']:<8.1f}")

        if len(rankings) > 15:
            print(f"... and {len(rankings) - 15} more voices")

        print(f"\n{'='*60}")
        print(f"TOP 5 RECOMMENDED VOICES:")
        for r in rankings[:5]:
            print(f"  {r['rank']}. {r['voice']} (Score: {r['score']}, Grade: {r['grade']})")

        print(f"\nTotal time: {elapsed}")
        print(f"Results: {self.logger.rankings_file}")
        print(f"Full log: {self.logger.log_file}")
        print(f"{'='*60}")


# ============== CLI ==============

async def main():
    import argparse

    parser = argparse.ArgumentParser(description="StyleTTS2 Benchmark")
    parser.add_argument("--voice", type=str, help="Test single voice")
    parser.add_argument("--voices", type=str, help="Comma-separated voices")
    parser.add_argument("--start-from", type=int, default=0, help="Start from voice N")
    parser.add_argument("--url", type=str, help="StyleTTS2 URL")
    args = parser.parse_args()

    if args.url:
        global STYLETTS2_URL
        STYLETTS2_URL = args.url

    benchmark = StyleTTS2Benchmark()

    voices = None
    if args.voice:
        voices = [args.voice]
    elif args.voices:
        voices = [v.strip() for v in args.voices.split(",")]

    await benchmark.run(voices, args.start_from)


if __name__ == "__main__":
    asyncio.run(main())
