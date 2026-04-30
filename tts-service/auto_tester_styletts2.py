#!/usr/bin/env python3
"""
Автоматичний тестер StyleTTS2 Ukrainian
- 50+ тестових фраз різних категорій
- Всі 31 голос
- Оцінка: Whisper WER + CPS + стабільність
- Результат: рейтинг голосів
"""

import os
import json
import time
import wave
import httpx
import asyncio
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from collections import defaultdict
import statistics

# Whisper for transcription
try:
    import whisper
    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False
    print("WARNING: Whisper not installed. Run: pip install openai-whisper")

# ============== CONFIGURATION ==============

STYLETTS2_URL = "http://localhost:5002"
OUTPUT_DIR = Path("/opt/tts/test-platform/benchmark_results")
AUDIO_DIR = OUTPUT_DIR / "audio"

# Whisper model (tiny=fast, base=balanced, small=accurate)
WHISPER_MODEL = "base"

# ============== TEST PHRASES (50+) ==============

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
        "Сума до сплати: одна тисяча двісті тридцять чотири гривні п'ятдесят шість копійок.",
        "Дата доставки: п'ятнадцяте лютого дві тисячі двадцять п'ятого року.",
        "Зателефонуйте за номером плюс три вісім нуль, сорок чотири, сто двадцять три, сорок п'ять, шістдесят сім.",
        "Ваш баланс становить дві тисячі п'ятсот гривень.",
        "Номер вашого рахунку: два шість один чотири нуль вісім три.",
        "Час очікування: приблизно три хвилини.",
    ],
    "technical": [
        "Ваш API ключ недійсний, оновіть його в налаштуваннях.",
        "Системний адміністратор виконує технічне обслуговування сервера.",
        "Будь ласка, введіть ваш ідентифікаційний номер платника податків.",
        "Завантажте останню версію програмного забезпечення з офіційного сайту.",
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
    "complex_sentences": [
        "Якщо ви хочете продовжити, натисніть один, якщо ні, натисніть два.",
        "Ваше замовлення номер дванадцять тисяч триста сорок п'ять буде доставлено завтра, з дев'ятої до вісімнадцятої години.",
        "Олександр Петрович Коваленко, ваш рейс PS сімсот п'ятдесят два затримується на дві години.",
        "Натисніть один для продажів, два для підтримки, три для бухгалтерії, або залишайтеся на лінії для з'єднання з оператором.",
        "У вас є три нові повідомлення, два пропущені дзвінки та один голосовий лист.",
    ],
    "names": [
        "Тарас Григорович Шевченко народився в селі Моринці.",
        "Пані Оксана Володимирівна, ваш документ готовий.",
        "Пан Ігор Михайлович запрошує вас на зустріч.",
        "Директор Андрій Степанович підписав наказ.",
        "Лікар Наталія Сергіївна приймає з дев'ятої до сімнадцятої.",
    ],
    "addresses": [
        "Вулиця Хрещатик, будинок двадцять два, квартира п'ять.",
        "Місто Київ, проспект Перемоги, сто тридцять сім.",
        "Львівська область, місто Дрогобич, вулиця Шевченка.",
        "Відділення Нової Пошти номер три у місті Одеса.",
    ],
    "long_text": [
        "Шановний клієнте, дякуємо за ваше звернення до нашої служби підтримки. Ваш запит зареєстровано під номером сто двадцять три. Наш спеціаліст зв'яжеться з вами протягом двадцяти чотирьох годин для вирішення вашого питання. Якщо у вас виникнуть додаткові запитання, будь ласка, зателефонуйте на гарячу лінію.",
        "Компанія Оки-Токи пропонує сучасні рішення для автоматизації кол-центрів. Наша платформа дозволяє ефективно обробляти вхідні та вихідні дзвінки, використовуючи технології штучного інтелекту та синтезу мовлення. Зверніться до нашого менеджера для отримання детальної консультації.",
    ],
}

# ============== DATA CLASSES ==============

@dataclass
class PhraseResult:
    phrase: str
    category: str
    voice: str
    synthesis_time_ms: float
    cps: float
    audio_size_bytes: int
    transcription: Optional[str] = None
    wer: Optional[float] = None  # Word Error Rate (0-100%)
    cer: Optional[float] = None  # Character Error Rate (0-100%)

@dataclass
class VoiceResult:
    voice: str
    total_phrases: int
    avg_cps: float
    min_cps: float
    max_cps: float
    std_cps: float
    avg_wer: Optional[float] = None
    avg_cer: Optional[float] = None
    total_time_sec: float = 0
    score: float = 0  # Final score 0-100

# ============== UTILITY FUNCTIONS ==============

def calculate_wer(reference: str, hypothesis: str) -> float:
    """Calculate Word Error Rate"""
    ref_words = reference.lower().split()
    hyp_words = hypothesis.lower().split()

    # Levenshtein distance for words
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
                d[i][j] = min(d[i-1][j] + 1,      # deletion
                             d[i][j-1] + 1,      # insertion
                             d[i-1][j-1] + 1)    # substitution

    if len(ref_words) == 0:
        return 0.0 if len(hyp_words) == 0 else 100.0

    return (d[len(ref_words)][len(hyp_words)] / len(ref_words)) * 100


def calculate_cer(reference: str, hypothesis: str) -> float:
    """Calculate Character Error Rate"""
    ref_chars = list(reference.lower().replace(" ", ""))
    hyp_chars = list(hypothesis.lower().replace(" ", ""))

    d = [[0] * (len(hyp_chars) + 1) for _ in range(len(ref_chars) + 1)]

    for i in range(len(ref_chars) + 1):
        d[i][0] = i
    for j in range(len(hyp_chars) + 1):
        d[0][j] = j

    for i in range(1, len(ref_chars) + 1):
        for j in range(1, len(hyp_chars) + 1):
            if ref_chars[i-1] == hyp_chars[j-1]:
                d[i][j] = d[i-1][j-1]
            else:
                d[i][j] = min(d[i-1][j] + 1,
                             d[i][j-1] + 1,
                             d[i-1][j-1] + 1)

    if len(ref_chars) == 0:
        return 0.0 if len(hyp_chars) == 0 else 100.0

    return (d[len(ref_chars)][len(hyp_chars)] / len(ref_chars)) * 100


def calculate_voice_score(voice_result: VoiceResult) -> float:
    """
    Calculate final score for a voice (0-100)
    Weights:
    - WER: 50% (lower is better)
    - CPS: 30% (higher is better, normalized to 0-20 CPS range)
    - Stability: 20% (lower std is better)
    """
    score = 0

    # WER score (50 points max, 0% WER = 50 points, 100% WER = 0 points)
    if voice_result.avg_wer is not None:
        wer_score = max(0, 50 - (voice_result.avg_wer / 2))
        score += wer_score
    else:
        score += 25  # Default if no WER

    # CPS score (30 points max, 20+ CPS = 30 points, 0 CPS = 0 points)
    cps_normalized = min(voice_result.avg_cps / 20, 1.0)
    score += cps_normalized * 30

    # Stability score (20 points max, lower std = higher score)
    if voice_result.avg_cps > 0:
        cv = voice_result.std_cps / voice_result.avg_cps  # Coefficient of variation
        stability_score = max(0, 20 - (cv * 40))
        score += stability_score

    return round(score, 1)


# ============== MAIN TESTER CLASS ==============

class StyleTTS2Tester:
    def __init__(self):
        self.voices: List[str] = []
        self.results: List[PhraseResult] = []
        self.whisper_model = None
        self.start_time = None

    async def load_voices(self):
        """Load available voices from StyleTTS2"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(f"{STYLETTS2_URL}/voices")
            if response.status_code == 200:
                data = response.json()
                self.voices = data.get("voices", [])
                print(f"Loaded {len(self.voices)} voices")
            else:
                raise Exception(f"Failed to load voices: {response.status_code}")

    def load_whisper(self):
        """Load Whisper model"""
        if not WHISPER_AVAILABLE:
            print("Whisper not available, skipping transcription")
            return

        print(f"Loading Whisper model '{WHISPER_MODEL}'...")
        self.whisper_model = whisper.load_model(WHISPER_MODEL)
        print("Whisper model loaded")

    async def synthesize(self, text: str, voice: str) -> tuple[bytes, float]:
        """Synthesize text with StyleTTS2"""
        start = time.time()

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{STYLETTS2_URL}/tts",
                json={
                    "text": text,
                    "voice": voice,
                    "model": "multi",
                    "speed": 1.0,
                    "noise_level": 0.0
                }
            )

            if response.status_code != 200:
                raise Exception(f"Synthesis failed: {response.status_code}")

            elapsed_ms = (time.time() - start) * 1000
            return response.content, elapsed_ms

    def transcribe(self, audio_path: str) -> str:
        """Transcribe audio with Whisper"""
        if self.whisper_model is None:
            return ""

        result = self.whisper_model.transcribe(
            audio_path,
            language="uk",
            task="transcribe"
        )
        return result["text"].strip()

    async def test_phrase(self, text: str, category: str, voice: str, save_audio: bool = True) -> PhraseResult:
        """Test a single phrase"""
        # Synthesize
        audio_bytes, synthesis_time_ms = await self.synthesize(text, voice)
        cps = len(text) / (synthesis_time_ms / 1000) if synthesis_time_ms > 0 else 0

        # Save audio if needed
        audio_path = None
        if save_audio:
            safe_voice = voice.replace(" ", "_").replace("/", "_")
            safe_text = text[:30].replace(" ", "_").replace("/", "_").replace("?", "").replace("!", "")
            audio_path = AUDIO_DIR / f"{safe_voice}" / f"{category}_{safe_text}.wav"
            audio_path.parent.mkdir(parents=True, exist_ok=True)
            with open(audio_path, "wb") as f:
                f.write(audio_bytes)

        # Transcribe
        transcription = ""
        wer = None
        cer = None

        if self.whisper_model and audio_path:
            try:
                transcription = self.transcribe(str(audio_path))
                wer = calculate_wer(text, transcription)
                cer = calculate_cer(text, transcription)
            except Exception as e:
                print(f"  Transcription error: {e}")

        return PhraseResult(
            phrase=text,
            category=category,
            voice=voice,
            synthesis_time_ms=synthesis_time_ms,
            cps=cps,
            audio_size_bytes=len(audio_bytes),
            transcription=transcription,
            wer=wer,
            cer=cer
        )

    async def test_voice(self, voice: str, phrases: Dict[str, List[str]]) -> VoiceResult:
        """Test all phrases for a voice"""
        print(f"\n{'='*60}")
        print(f"Testing voice: {voice}")
        print(f"{'='*60}")

        voice_results = []
        total_phrases = sum(len(p) for p in phrases.values())
        completed = 0

        for category, category_phrases in phrases.items():
            print(f"\n  Category: {category} ({len(category_phrases)} phrases)")

            for phrase in category_phrases:
                try:
                    result = await self.test_phrase(phrase, category, voice)
                    voice_results.append(result)
                    self.results.append(result)
                    completed += 1

                    wer_str = f"WER:{result.wer:.1f}%" if result.wer is not None else "WER:N/A"
                    print(f"    [{completed}/{total_phrases}] CPS:{result.cps:.1f} {wer_str} - {phrase[:40]}...")

                except Exception as e:
                    print(f"    ERROR: {phrase[:30]}... - {e}")
                    completed += 1

        # Calculate voice statistics
        cps_values = [r.cps for r in voice_results]
        wer_values = [r.wer for r in voice_results if r.wer is not None]
        cer_values = [r.cer for r in voice_results if r.cer is not None]

        voice_result = VoiceResult(
            voice=voice,
            total_phrases=len(voice_results),
            avg_cps=statistics.mean(cps_values) if cps_values else 0,
            min_cps=min(cps_values) if cps_values else 0,
            max_cps=max(cps_values) if cps_values else 0,
            std_cps=statistics.stdev(cps_values) if len(cps_values) > 1 else 0,
            avg_wer=statistics.mean(wer_values) if wer_values else None,
            avg_cer=statistics.mean(cer_values) if cer_values else None,
            total_time_sec=sum(r.synthesis_time_ms for r in voice_results) / 1000
        )

        voice_result.score = calculate_voice_score(voice_result)

        print(f"\n  Results for {voice}:")
        print(f"    Avg CPS: {voice_result.avg_cps:.1f}")
        print(f"    Avg WER: {voice_result.avg_wer:.1f}%" if voice_result.avg_wer else "    Avg WER: N/A")
        print(f"    Score: {voice_result.score}/100")

        return voice_result

    async def run_full_test(self):
        """Run full test on all voices"""
        self.start_time = datetime.now()

        # Setup
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        AUDIO_DIR.mkdir(parents=True, exist_ok=True)

        # Load resources
        await self.load_voices()
        self.load_whisper()

        # Count total
        total_phrases = sum(len(p) for p in TEST_PHRASES.values())
        total_tests = total_phrases * len(self.voices)

        print(f"\n{'#'*60}")
        print(f"# StyleTTS2 Ukrainian Benchmark")
        print(f"# Voices: {len(self.voices)}")
        print(f"# Phrases per voice: {total_phrases}")
        print(f"# Total tests: {total_tests}")
        print(f"# Whisper model: {WHISPER_MODEL if WHISPER_AVAILABLE else 'N/A'}")
        print(f"{'#'*60}\n")

        # Test all voices
        voice_results = []
        for i, voice in enumerate(self.voices):
            print(f"\n[{i+1}/{len(self.voices)}] Testing voice: {voice}")
            result = await self.test_voice(voice, TEST_PHRASES)
            voice_results.append(result)

            # Save intermediate results
            self.save_results(voice_results)

        # Generate final report
        self.generate_report(voice_results)

        elapsed = datetime.now() - self.start_time
        print(f"\n{'#'*60}")
        print(f"# BENCHMARK COMPLETE")
        print(f"# Total time: {elapsed}")
        print(f"# Results saved to: {OUTPUT_DIR}")
        print(f"{'#'*60}")

    def save_results(self, voice_results: List[VoiceResult]):
        """Save results to JSON"""
        # Save voice results
        voice_data = [asdict(vr) for vr in voice_results]
        with open(OUTPUT_DIR / "voice_results.json", "w", encoding="utf-8") as f:
            json.dump(voice_data, f, ensure_ascii=False, indent=2)

        # Save detailed phrase results
        phrase_data = [asdict(pr) for pr in self.results]
        with open(OUTPUT_DIR / "phrase_results.json", "w", encoding="utf-8") as f:
            json.dump(phrase_data, f, ensure_ascii=False, indent=2)

    def generate_report(self, voice_results: List[VoiceResult]):
        """Generate final report"""
        # Sort by score
        sorted_results = sorted(voice_results, key=lambda x: x.score, reverse=True)

        report = []
        report.append("=" * 70)
        report.append("STYLETTS2 UKRAINIAN BENCHMARK REPORT")
        report.append(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("=" * 70)
        report.append("")
        report.append("VOICE RANKING (by score):")
        report.append("-" * 70)
        report.append(f"{'Rank':<6}{'Voice':<30}{'Score':<10}{'CPS':<10}{'WER%':<10}")
        report.append("-" * 70)

        for i, vr in enumerate(sorted_results, 1):
            wer_str = f"{vr.avg_wer:.1f}" if vr.avg_wer is not None else "N/A"
            report.append(f"{i:<6}{vr.voice:<30}{vr.score:<10.1f}{vr.avg_cps:<10.1f}{wer_str:<10}")

        report.append("-" * 70)
        report.append("")
        report.append("TOP 5 VOICES:")
        for i, vr in enumerate(sorted_results[:5], 1):
            report.append(f"  {i}. {vr.voice} (Score: {vr.score})")

        report.append("")
        report.append("STATISTICS:")
        report.append(f"  Total voices tested: {len(voice_results)}")
        report.append(f"  Total phrases: {len(self.results)}")

        avg_scores = [vr.score for vr in voice_results]
        report.append(f"  Average score: {statistics.mean(avg_scores):.1f}")
        report.append(f"  Best score: {max(avg_scores):.1f}")
        report.append(f"  Worst score: {min(avg_scores):.1f}")

        report_text = "\n".join(report)

        # Print report
        print("\n" + report_text)

        # Save report
        with open(OUTPUT_DIR / "benchmark_report.txt", "w", encoding="utf-8") as f:
            f.write(report_text)

        # Save CSV for Excel
        csv_lines = ["Voice,Score,Avg_CPS,Min_CPS,Max_CPS,Std_CPS,Avg_WER,Avg_CER,Total_Time_Sec"]
        for vr in sorted_results:
            wer = f"{vr.avg_wer:.2f}" if vr.avg_wer is not None else ""
            cer = f"{vr.avg_cer:.2f}" if vr.avg_cer is not None else ""
            csv_lines.append(f"{vr.voice},{vr.score},{vr.avg_cps:.2f},{vr.min_cps:.2f},{vr.max_cps:.2f},{vr.std_cps:.2f},{wer},{cer},{vr.total_time_sec:.2f}")

        with open(OUTPUT_DIR / "benchmark_results.csv", "w", encoding="utf-8") as f:
            f.write("\n".join(csv_lines))


# ============== MAIN ==============

async def main():
    tester = StyleTTS2Tester()
    await tester.run_full_test()


if __name__ == "__main__":
    asyncio.run(main())
