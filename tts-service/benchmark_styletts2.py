#!/usr/bin/env python3
"""
StyleTTS2 Ukrainian Benchmark
- Тестує всі 31 голос
- 50+ фраз різних категорій
- Оцінка: WER (Whisper) + CPS + стабільність
- Логи БЕЗ збереження аудіо (економія місця)
- Автоматичний рейтинг голосів
"""

import os
import json
import time
import tempfile
import asyncio
import statistics
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict, field
import httpx

# Whisper
try:
    import whisper
    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False
    print("⚠️  Whisper not installed. Run: pip install openai-whisper")

# ============== CONFIGURATION ==============

STYLETTS2_URL = "http://localhost:5002"
LOG_DIR = Path("/opt/tts/benchmark")
LOG_FILE = LOG_DIR / "benchmark_log.json"
RESULTS_FILE = LOG_DIR / "voice_ratings.json"

WHISPER_MODEL = "tiny"  # tiny/base/small (tiny uses less RAM)
DELAY_BETWEEN_TESTS = 1.0  # seconds between tests to avoid overload

# ============== TEST PHRASES (59 total) ==============

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
    ],
    "numbers": [
        "Ваш номер замовлення: сім вісім чотири дев'ять два три п'ять.",
        "Сума до сплати: одна тисяча двісті тридцять чотири гривні.",
        "Дата доставки: п'ятнадцяте лютого дві тисячі двадцять п'ятого року.",
        "Зателефонуйте за номером плюс три вісім нуль, сорок чотири.",
        "Ваш баланс становить дві тисячі п'ятсот гривень.",
        "Номер рахунку: два шість один чотири нуль вісім три.",
        "Час очікування: приблизно три хвилини.",
    ],
    "technical": [
        "Ваш API ключ недійсний, оновіть його в налаштуваннях.",
        "Системний адміністратор виконує технічне обслуговування.",
        "Будь ласка, введіть ваш ідентифікаційний номер.",
        "Завантажте останню версію програмного забезпечення.",
        "Перевірте підключення до інтернету та спробуйте ще раз.",
        "Ваш пароль має містити мінімум вісім символів.",
        "Двофакторна автентифікація успішно увімкнена.",
    ],
    "foreign_words": [
        "Завантажте файл у форматі PDF або Microsoft Word.",
        "Оплата через PayPal або криптовалютою Bitcoin.",
        "Ваш логін та пароль надіслано на email.",
        "Підключіться до мережі WiFi для синхронізації.",
        "Ваш iPhone готовий до видачі в магазині Apple Store.",
        "Відкрийте Google Chrome та перейдіть на YouTube.",
        "Зателефонуйте через Viber або WhatsApp.",
        "Перегляньте відео на TikTok або Instagram.",
    ],
    "questions": [
        "Ви впевнені, що хочете видалити цей файл?",
        "Чи бажаєте ви продовжити оформлення замовлення?",
        "Коли буде доставлено моє замовлення?",
        "Чи можу я поговорити з менеджером?",
        "Скільки це коштує?",
        "Як довго триває гарантія?",
        "Чи є у вас знижки для постійних клієнтів?",
    ],
    "exclamations": [
        "Вітаємо! Ви виграли головний приз!",
        "Увага! Це важливе повідомлення!",
        "Дякуємо за покупку!",
        "На жаль, ваш запит відхилено.",
        "Чудово! Ваше замовлення підтверджено!",
        "Обережно! Термін дії пропозиції закінчується!",
    ],
    "complex": [
        "Якщо ви хочете продовжити, натисніть один, якщо ні, натисніть два.",
        "Ваше замовлення буде доставлено завтра, з дев'ятої до вісімнадцятої.",
        "Олександр Петрович, ваш рейс затримується на дві години.",
        "Натисніть один для продажів, два для підтримки, три для бухгалтерії.",
        "У вас є три нові повідомлення та два пропущені дзвінки.",
    ],
    "names": [
        "Тарас Григорович Шевченко народився в селі Моринці.",
        "Пані Оксана Володимирівна, ваш документ готовий.",
        "Пан Ігор Михайлович запрошує вас на зустріч.",
        "Директор Андрій Степанович підписав наказ.",
        "Лікар Наталія Сергіївна приймає з дев'ятої години.",
    ],
    "addresses": [
        "Вулиця Хрещатик, будинок двадцять два.",
        "Місто Київ, проспект Перемоги, сто тридцять сім.",
        "Львівська область, місто Дрогобич, вулиця Шевченка.",
        "Відділення Нової Пошти номер три у місті Одеса.",
    ],
    "long_text": [
        "Шановний клієнте, дякуємо за ваше звернення до нашої служби підтримки. Ваш запит зареєстровано під номером сто двадцять три. Наш спеціаліст зв'яжеться з вами протягом двадцяти чотирьох годин.",
        "Компанія Оки-Токи пропонує сучасні рішення для автоматизації кол-центрів. Наша платформа дозволяє ефективно обробляти вхідні та вихідні дзвінки, використовуючи технології штучного інтелекту.",
    ],
}

# ============== UTILITY FUNCTIONS ==============

def calculate_wer(reference: str, hypothesis: str) -> float:
    """Word Error Rate (0-100%)"""
    ref_words = reference.lower().split()
    hyp_words = hypothesis.lower().split()

    if not ref_words:
        return 0.0 if not hyp_words else 100.0

    d = [[0] * (len(hyp_words) + 1) for _ in range(len(ref_words) + 1)]
    for i in range(len(ref_words) + 1):
        d[i][0] = i
    for j in range(len(hyp_words) + 1):
        d[0][j] = j

    for i in range(1, len(ref_words) + 1):
        for j in range(1, len(hyp_words) + 1):
            if ref_words[i-1] == hyp_words[j-1]:
                d[i][j] = d[i-1][j-1]
            else:
                d[i][j] = min(d[i-1][j], d[i][j-1], d[i-1][j-1]) + 1

    return (d[len(ref_words)][len(hyp_words)] / len(ref_words)) * 100


def calculate_score(avg_cps: float, avg_wer: Optional[float], std_cps: float) -> float:
    """
    Score 0-100:
    - WER: 50% (lower better)
    - CPS: 30% (higher better, 0-20 range)
    - Stability: 20% (lower std better)
    """
    score = 0

    # WER (50 points max)
    if avg_wer is not None:
        score += max(0, 50 - (avg_wer / 2))
    else:
        score += 25

    # CPS (30 points max, normalized to 0-20 range)
    score += min(avg_cps / 20, 1.0) * 30

    # Stability (20 points max)
    if avg_cps > 0:
        cv = std_cps / avg_cps
        score += max(0, 20 - (cv * 40))

    return round(score, 1)


# ============== LOG MANAGEMENT ==============

def load_logs() -> Dict[str, Any]:
    """Load existing logs"""
    if LOG_FILE.exists():
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"runs": [], "last_updated": None}


def save_logs(logs: Dict[str, Any]):
    """Save logs"""
    logs["last_updated"] = datetime.now().isoformat()
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(logs, f, ensure_ascii=False, indent=2)


def save_ratings(ratings: List[Dict[str, Any]]):
    """Save voice ratings"""
    with open(RESULTS_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "generated": datetime.now().isoformat(),
            "ratings": ratings
        }, f, ensure_ascii=False, indent=2)


# ============== BENCHMARK CLASS ==============

class Benchmark:
    def __init__(self):
        self.voices: List[str] = []
        self.whisper_model = None
        self.current_run: Dict[str, Any] = {}

    async def load_voices(self):
        """Load voices from StyleTTS2"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(f"{STYLETTS2_URL}/voices")
            data = response.json()
            self.voices = data.get("voices", [])
        print(f"✓ Loaded {len(self.voices)} voices")

    def load_whisper(self):
        """Load Whisper model"""
        if not WHISPER_AVAILABLE:
            print("⚠️  Whisper not available")
            return
        print(f"Loading Whisper '{WHISPER_MODEL}'...")
        self.whisper_model = whisper.load_model(WHISPER_MODEL)
        print("✓ Whisper loaded")

    async def synthesize(self, text: str, voice: str) -> tuple[bytes, float]:
        """Synthesize and return (audio_bytes, time_ms)"""
        start = time.time()
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{STYLETTS2_URL}/tts",
                json={"text": text, "voice": voice, "model": "multi", "speed": 1.0}
            )
            if response.status_code != 200:
                raise Exception(f"HTTP {response.status_code}")
            return response.content, (time.time() - start) * 1000

    def transcribe(self, audio_bytes: bytes) -> str:
        """Transcribe audio with Whisper (using temp file)"""
        if not self.whisper_model:
            return ""

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(audio_bytes)
            temp_path = f.name

        try:
            result = self.whisper_model.transcribe(temp_path, language="uk")
            return result["text"].strip()
        finally:
            os.unlink(temp_path)

    async def test_voice(self, voice: str) -> Dict[str, Any]:
        """Test all phrases for a voice"""
        results = []
        total = sum(len(p) for p in TEST_PHRASES.values())
        done = 0

        for category, phrases in TEST_PHRASES.items():
            for phrase in phrases:
                done += 1
                try:
                    audio, time_ms = await self.synthesize(phrase, voice)
                    cps = len(phrase) / (time_ms / 1000)

                    transcription = self.transcribe(audio)
                    wer = calculate_wer(phrase, transcription) if transcription else None

                    results.append({
                        "phrase": phrase,
                        "category": category,
                        "time_ms": round(time_ms, 1),
                        "cps": round(cps, 2),
                        "wer": round(wer, 1) if wer is not None else None,
                        "transcription": transcription
                    })

                    wer_str = f"WER:{wer:.0f}%" if wer is not None else ""
                    print(f"  [{done}/{total}] {cps:.1f} CPS {wer_str}")

                except Exception as e:
                    print(f"  [{done}/{total}] ERROR: {e}")
                    results.append({
                        "phrase": phrase,
                        "category": category,
                        "error": str(e)
                    })

                # Delay between tests to avoid server overload
                await asyncio.sleep(DELAY_BETWEEN_TESTS)

        # Calculate stats
        cps_list = [r["cps"] for r in results if "cps" in r]
        wer_list = [r["wer"] for r in results if r.get("wer") is not None]

        stats = {
            "voice": voice,
            "total_phrases": len(results),
            "successful": len(cps_list),
            "avg_cps": round(statistics.mean(cps_list), 2) if cps_list else 0,
            "min_cps": round(min(cps_list), 2) if cps_list else 0,
            "max_cps": round(max(cps_list), 2) if cps_list else 0,
            "std_cps": round(statistics.stdev(cps_list), 2) if len(cps_list) > 1 else 0,
            "avg_wer": round(statistics.mean(wer_list), 1) if wer_list else None,
            "results": results
        }

        stats["score"] = calculate_score(stats["avg_cps"], stats["avg_wer"], stats["std_cps"])

        return stats

    async def run(self, voices_to_test: Optional[List[str]] = None):
        """Run full benchmark"""
        LOG_DIR.mkdir(parents=True, exist_ok=True)

        await self.load_voices()
        self.load_whisper()

        if voices_to_test:
            test_voices = [v for v in voices_to_test if v in self.voices]
        else:
            test_voices = self.voices

        total_phrases = sum(len(p) for p in TEST_PHRASES.values())

        print(f"\n{'='*60}")
        print(f"STYLETTS2 BENCHMARK")
        print(f"Voices: {len(test_voices)}")
        print(f"Phrases: {total_phrases}")
        print(f"Total tests: {len(test_voices) * total_phrases}")
        print(f"{'='*60}\n")

        # Run tests
        run_data = {
            "timestamp": datetime.now().isoformat(),
            "total_voices": len(test_voices),
            "total_phrases": total_phrases,
            "whisper_model": WHISPER_MODEL if WHISPER_AVAILABLE else None,
            "voice_results": []
        }

        for i, voice in enumerate(test_voices, 1):
            print(f"\n[{i}/{len(test_voices)}] Testing: {voice}")
            print("-" * 40)

            stats = await self.test_voice(voice)
            run_data["voice_results"].append(stats)

            wer_str = f"WER: {stats['avg_wer']:.1f}%" if stats['avg_wer'] else "WER: N/A"
            print(f"\n  → Score: {stats['score']}/100 | CPS: {stats['avg_cps']:.1f} | {wer_str}")

            # Save intermediate results
            logs = load_logs()
            logs["runs"] = [run_data]  # Keep only current run
            save_logs(logs)

        # Generate rankings
        sorted_results = sorted(run_data["voice_results"], key=lambda x: x["score"], reverse=True)

        ratings = []
        for rank, r in enumerate(sorted_results, 1):
            ratings.append({
                "rank": rank,
                "voice": r["voice"],
                "score": r["score"],
                "avg_cps": r["avg_cps"],
                "avg_wer": r["avg_wer"],
                "std_cps": r["std_cps"]
            })

        save_ratings(ratings)

        # Print final report
        print(f"\n{'='*60}")
        print("FINAL RANKINGS")
        print(f"{'='*60}")
        print(f"{'Rank':<6}{'Voice':<30}{'Score':<10}{'CPS':<10}{'WER%':<10}")
        print("-" * 60)

        for r in ratings:
            wer = f"{r['avg_wer']:.1f}" if r['avg_wer'] else "N/A"
            print(f"{r['rank']:<6}{r['voice']:<30}{r['score']:<10.1f}{r['avg_cps']:<10.1f}{wer:<10}")

        print(f"\n{'='*60}")
        print(f"TOP 3 VOICES:")
        for r in ratings[:3]:
            print(f"  {r['rank']}. {r['voice']} (Score: {r['score']})")
        print(f"\nResults saved to: {LOG_DIR}")
        print(f"{'='*60}")


# ============== MAIN ==============

async def main():
    import argparse

    parser = argparse.ArgumentParser(description="StyleTTS2 Benchmark")
    parser.add_argument("--voice", type=str, help="Test specific voice only")
    parser.add_argument("--voices", type=str, help="Comma-separated list of voices")
    parser.add_argument("--top", type=int, help="Test only top N voices from previous run")
    args = parser.parse_args()

    benchmark = Benchmark()

    voices_to_test = None
    if args.voice:
        voices_to_test = [args.voice]
    elif args.voices:
        voices_to_test = [v.strip() for v in args.voices.split(",")]
    elif args.top and RESULTS_FILE.exists():
        with open(RESULTS_FILE) as f:
            data = json.load(f)
            voices_to_test = [r["voice"] for r in data["ratings"][:args.top]]

    await benchmark.run(voices_to_test)


if __name__ == "__main__":
    asyncio.run(main())
