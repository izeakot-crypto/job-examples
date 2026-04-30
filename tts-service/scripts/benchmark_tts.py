#!/usr/bin/env python3
"""
TTS Benchmark Script for Oki-Toki
Tests multiple TTS engines across 6 languages: UA, EN, RU, PL, ES, TR

Metrics:
- CPS (Characters Per Second)
- TTFB (Time To First Byte)
- Audio quality (manual evaluation)
"""

import os
import sys
import json
import time
import asyncio
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import Optional, Dict, List, Any
import warnings
warnings.filterwarnings('ignore')

# Add parent dir to path
sys.path.insert(0, str(Path(__file__).parent.parent))

@dataclass
class BenchmarkResult:
    """Result of a single TTS benchmark"""
    engine: str
    language: str
    category: str
    phrase: str
    char_count: int
    synthesis_time_ms: float
    cps: float  # Characters per second
    ttfb_ms: Optional[float]  # Time to first byte (for streaming)
    audio_duration_ms: Optional[float]
    output_file: str
    success: bool
    error: Optional[str] = None


class TTSBenchmark:
    """Main benchmark class for TTS evaluation"""

    def __init__(self, output_dir: str = "results"):
        self.project_root = Path(__file__).parent.parent
        self.output_dir = self.project_root / output_dir
        self.audio_dir = self.project_root / "audio_samples"
        self.phrases_file = self.project_root / "test_phrases" / "phrases.json"

        # Create directories
        self.output_dir.mkdir(exist_ok=True)
        self.audio_dir.mkdir(exist_ok=True)

        # Load phrases
        with open(self.phrases_file, 'r', encoding='utf-8') as f:
            self.phrases = json.load(f)

        self.results: List[BenchmarkResult] = []

    def get_phrases_for_language(self, lang: str) -> Dict[str, List[str]]:
        """Get all phrases for a specific language"""
        return self.phrases.get(lang, {}).get("phrases", {})

    async def benchmark_edge_tts(self, lang: str, text: str, category: str) -> BenchmarkResult:
        """Benchmark Edge-TTS (Microsoft free API)"""
        try:
            import edge_tts
        except ImportError:
            return self._error_result("edge-tts", lang, category, text, "edge-tts not installed")

        # Voice mapping
        voices = {
            "UA": "uk-UA-PolinaNeural",
            "EN": "en-US-JennyNeural",
            "RU": "ru-RU-SvetlanaNeural",
            "PL": "pl-PL-AgnieszkaNeural",
            "ES": "es-ES-ElviraNeural",
            "TR": "tr-TR-EmelNeural"
        }

        voice = voices.get(lang, "en-US-JennyNeural")
        output_file = self.audio_dir / f"edge-tts_{lang}_{category}_{int(time.time())}.mp3"

        start_time = time.perf_counter()
        try:
            communicate = edge_tts.Communicate(text, voice)
            await communicate.save(str(output_file))
            end_time = time.perf_counter()

            synthesis_time = (end_time - start_time) * 1000  # ms
            char_count = len(text)
            cps = char_count / (synthesis_time / 1000)

            # Get audio duration
            audio_duration = self._get_audio_duration(output_file)

            return BenchmarkResult(
                engine="edge-tts",
                language=lang,
                category=category,
                phrase=text[:50] + "..." if len(text) > 50 else text,
                char_count=char_count,
                synthesis_time_ms=synthesis_time,
                cps=cps,
                ttfb_ms=None,
                audio_duration_ms=audio_duration,
                output_file=str(output_file),
                success=True
            )
        except Exception as e:
            return self._error_result("edge-tts", lang, category, text, str(e))

    def benchmark_silero(self, lang: str, text: str, category: str) -> BenchmarkResult:
        """Benchmark Silero TTS"""
        try:
            import torch
        except ImportError:
            return self._error_result("silero", lang, category, text, "torch not installed")

        # Silero supports: RU, EN, DE, ES, FR, UA, UZ, XAL, Indic
        supported = ["RU", "EN", "ES", "UA"]
        if lang not in supported:
            return self._error_result("silero", lang, category, text, f"Language {lang} not supported by Silero")

        lang_map = {"UA": "ua", "EN": "en", "RU": "ru", "ES": "es"}
        silero_lang = lang_map.get(lang, "en")

        output_file = self.audio_dir / f"silero_{lang}_{category}_{int(time.time())}.wav"

        start_time = time.perf_counter()
        try:
            # Load model
            device = torch.device('cpu')
            model, _ = torch.hub.load(
                repo_or_dir='snakers4/silero-models',
                model='silero_tts',
                language=silero_lang,
                speaker='v3_1_ru' if silero_lang == 'ru' else f'v3_{silero_lang}'
            )
            model.to(device)

            # Synthesize
            audio = model.apply_tts(text=text, sample_rate=48000)

            end_time = time.perf_counter()

            # Save audio
            import soundfile as sf
            sf.write(str(output_file), audio.numpy(), 48000)

            synthesis_time = (end_time - start_time) * 1000
            char_count = len(text)
            cps = char_count / (synthesis_time / 1000)
            audio_duration = self._get_audio_duration(output_file)

            return BenchmarkResult(
                engine="silero",
                language=lang,
                category=category,
                phrase=text[:50] + "..." if len(text) > 50 else text,
                char_count=char_count,
                synthesis_time_ms=synthesis_time,
                cps=cps,
                ttfb_ms=None,
                audio_duration_ms=audio_duration,
                output_file=str(output_file),
                success=True
            )
        except Exception as e:
            return self._error_result("silero", lang, category, text, str(e))

    def benchmark_openai_tts(self, lang: str, text: str, category: str) -> BenchmarkResult:
        """Benchmark OpenAI TTS"""
        try:
            from openai import OpenAI
        except ImportError:
            return self._error_result("openai", lang, category, text, "openai not installed")

        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            return self._error_result("openai", lang, category, text, "OPENAI_API_KEY not set")

        output_file = self.audio_dir / f"openai_{lang}_{category}_{int(time.time())}.mp3"

        start_time = time.perf_counter()
        try:
            client = OpenAI(api_key=api_key)
            response = client.audio.speech.create(
                model="tts-1",  # or "tts-1-hd" for higher quality
                voice="alloy",  # alloy, echo, fable, onyx, nova, shimmer
                input=text
            )
            response.stream_to_file(str(output_file))
            end_time = time.perf_counter()

            synthesis_time = (end_time - start_time) * 1000
            char_count = len(text)
            cps = char_count / (synthesis_time / 1000)
            audio_duration = self._get_audio_duration(output_file)

            return BenchmarkResult(
                engine="openai",
                language=lang,
                category=category,
                phrase=text[:50] + "..." if len(text) > 50 else text,
                char_count=char_count,
                synthesis_time_ms=synthesis_time,
                cps=cps,
                ttfb_ms=None,
                audio_duration_ms=audio_duration,
                output_file=str(output_file),
                success=True
            )
        except Exception as e:
            return self._error_result("openai", lang, category, text, str(e))

    def benchmark_elevenlabs(self, lang: str, text: str, category: str) -> BenchmarkResult:
        """Benchmark ElevenLabs TTS"""
        try:
            from elevenlabs import generate, set_api_key
        except ImportError:
            return self._error_result("elevenlabs", lang, category, text, "elevenlabs not installed")

        api_key = os.environ.get("ELEVENLABS_API_KEY")
        if not api_key:
            return self._error_result("elevenlabs", lang, category, text, "ELEVENLABS_API_KEY not set")

        output_file = self.audio_dir / f"elevenlabs_{lang}_{category}_{int(time.time())}.mp3"

        start_time = time.perf_counter()
        try:
            set_api_key(api_key)
            audio = generate(
                text=text,
                voice="Rachel",  # Default multilingual voice
                model="eleven_multilingual_v2"
            )

            with open(output_file, 'wb') as f:
                f.write(audio)

            end_time = time.perf_counter()

            synthesis_time = (end_time - start_time) * 1000
            char_count = len(text)
            cps = char_count / (synthesis_time / 1000)
            audio_duration = self._get_audio_duration(output_file)

            return BenchmarkResult(
                engine="elevenlabs",
                language=lang,
                category=category,
                phrase=text[:50] + "..." if len(text) > 50 else text,
                char_count=char_count,
                synthesis_time_ms=synthesis_time,
                cps=cps,
                ttfb_ms=None,
                audio_duration_ms=audio_duration,
                output_file=str(output_file),
                success=True
            )
        except Exception as e:
            return self._error_result("elevenlabs", lang, category, text, str(e))

    def _get_audio_duration(self, file_path: Path) -> Optional[float]:
        """Get audio duration in milliseconds"""
        try:
            from pydub import AudioSegment
            audio = AudioSegment.from_file(str(file_path))
            return len(audio)  # Duration in ms
        except Exception:
            return None

    def _error_result(self, engine: str, lang: str, category: str, text: str, error: str) -> BenchmarkResult:
        """Create error result"""
        return BenchmarkResult(
            engine=engine,
            language=lang,
            category=category,
            phrase=text[:50] + "..." if len(text) > 50 else text,
            char_count=len(text),
            synthesis_time_ms=0,
            cps=0,
            ttfb_ms=None,
            audio_duration_ms=None,
            output_file="",
            success=False,
            error=error
        )

    async def run_benchmark(self, engines: List[str] = None, languages: List[str] = None,
                           categories: List[str] = None, limit: int = None):
        """Run full benchmark"""
        if engines is None:
            engines = ["edge-tts", "silero", "openai", "elevenlabs"]
        if languages is None:
            languages = ["UA", "EN", "RU", "PL", "ES", "TR"]
        if categories is None:
            categories = ["basic", "technical", "numbers", "foreign_words", "intonation", "mixed"]

        print(f"\n{'='*60}")
        print("TTS Benchmark for Oki-Toki")
        print(f"{'='*60}")
        print(f"Engines: {', '.join(engines)}")
        print(f"Languages: {', '.join(languages)}")
        print(f"Categories: {', '.join(categories)}")
        print(f"{'='*60}\n")

        total_tests = 0
        successful_tests = 0

        for lang in languages:
            phrases_data = self.get_phrases_for_language(lang)

            for category in categories:
                if category not in phrases_data:
                    continue

                phrases = phrases_data[category]
                if limit:
                    phrases = phrases[:limit]

                for phrase in phrases:
                    for engine in engines:
                        print(f"Testing: {engine} | {lang} | {category[:10]}... ", end="", flush=True)

                        if engine == "edge-tts":
                            result = await self.benchmark_edge_tts(lang, phrase, category)
                        elif engine == "silero":
                            result = self.benchmark_silero(lang, phrase, category)
                        elif engine == "openai":
                            result = self.benchmark_openai_tts(lang, phrase, category)
                        elif engine == "elevenlabs":
                            result = self.benchmark_elevenlabs(lang, phrase, category)
                        else:
                            continue

                        self.results.append(result)
                        total_tests += 1

                        if result.success:
                            successful_tests += 1
                            print(f"✓ CPS: {result.cps:.1f}")
                        else:
                            print(f"✗ {result.error}")

        # Save results
        self._save_results()
        self._print_summary(total_tests, successful_tests)

    def _save_results(self):
        """Save benchmark results to JSON"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = self.output_dir / f"benchmark_{timestamp}.json"

        results_dict = {
            "timestamp": timestamp,
            "total_tests": len(self.results),
            "successful_tests": sum(1 for r in self.results if r.success),
            "results": [asdict(r) for r in self.results]
        }

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results_dict, f, indent=2, ensure_ascii=False)

        print(f"\nResults saved to: {output_file}")

    def _print_summary(self, total: int, successful: int):
        """Print benchmark summary"""
        print(f"\n{'='*60}")
        print("BENCHMARK SUMMARY")
        print(f"{'='*60}")
        print(f"Total tests: {total}")
        print(f"Successful: {successful}")
        print(f"Failed: {total - successful}")

        # Calculate average CPS per engine
        engine_stats: Dict[str, List[float]] = {}
        for result in self.results:
            if result.success:
                if result.engine not in engine_stats:
                    engine_stats[result.engine] = []
                engine_stats[result.engine].append(result.cps)

        print(f"\nAverage CPS by Engine:")
        print("-" * 30)
        for engine, cps_values in sorted(engine_stats.items()):
            avg_cps = sum(cps_values) / len(cps_values)
            print(f"  {engine}: {avg_cps:.1f} CPS")

        # Calculate average CPS per language
        lang_stats: Dict[str, List[float]] = {}
        for result in self.results:
            if result.success:
                if result.language not in lang_stats:
                    lang_stats[result.language] = []
                lang_stats[result.language].append(result.cps)

        print(f"\nAverage CPS by Language:")
        print("-" * 30)
        for lang, cps_values in sorted(lang_stats.items()):
            avg_cps = sum(cps_values) / len(cps_values)
            print(f"  {lang}: {avg_cps:.1f} CPS")


async def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="TTS Benchmark for Oki-Toki")
    parser.add_argument("--engines", nargs="+",
                       choices=["edge-tts", "silero", "openai", "elevenlabs"],
                       help="TTS engines to test")
    parser.add_argument("--languages", nargs="+",
                       choices=["UA", "EN", "RU", "PL", "ES", "TR"],
                       help="Languages to test")
    parser.add_argument("--categories", nargs="+",
                       choices=["basic", "technical", "numbers", "foreign_words", "intonation", "mixed"],
                       help="Categories to test")
    parser.add_argument("--limit", type=int, default=1,
                       help="Limit phrases per category (default: 1)")

    args = parser.parse_args()

    benchmark = TTSBenchmark()
    await benchmark.run_benchmark(
        engines=args.engines,
        languages=args.languages,
        categories=args.categories,
        limit=args.limit
    )


if __name__ == "__main__":
    asyncio.run(main())
