#!/usr/bin/env python3
"""Multilingual Chirp3-HD TTS Test via Google Cloud gRPC API."""

import sys, io, os, json, time, wave
from datetime import datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from google.cloud import texttospeech_v1 as texttospeech
from google.oauth2 import service_account

CREDENTIALS_PATH = "C:/Users/izeak/Downloads/tts-488311-d5a1cbf88094.json"
OUTPUT_DIR = "C:/Users/izeak/OneDrive/Work.Oki-toki/TTS для Оки-Токи/Lira TTS/multilingual_test_output"
ATTEMPTS = 3
SAMPLE_RATE = 8000

SENTENCES = {
    "UA": "Дякуємо за дзвінок до компанії Окі-Токі. На жаль, всі оператори зараз зайняті. Будь ласка, залишайтесь на лінії, вам відповідять найближчим часом.",
    "EN": "Thank you for calling Oki-Toki company. Unfortunately, all operators are currently busy. Please stay on the line, you will be answered as soon as possible.",
    "RU": "Благодарим за звонок в компанию Оки-Токи. К сожалению, все операторы сейчас заняты. Пожалуйста, оставайтесь на линии, вам ответят в ближайшее время.",
    "PL": "Dziękujemy za telefon do firmy Oki-Toki. Niestety wszyscy operatorzy są obecnie zajęci. Prosimy pozostać na linii, odpowiemy najszybciej jak to możliwe.",
    "ES": "Gracias por llamar a la empresa Oki-Toki. Lamentablemente todos los operadores están ocupados. Por favor permanezca en la línea, le atenderemos lo antes posible.",
    "TR": "Oki-Toki şirketini aradığınız için teşekkür ederiz. Maalesef tüm operatörler şu anda meşgul. Lütfen hatta kalın, en kısa sürede size yanıt verilecektir.",
}

CHIRP3_VOICES = {
    "UA": ("uk-UA", "uk-UA-Chirp3-HD-Leda"),
    "EN": ("en-US", "en-US-Chirp3-HD-Leda"),
    "RU": ("ru-RU", "ru-RU-Chirp3-HD-Leda"),
    "PL": ("pl-PL", "pl-PL-Chirp3-HD-Leda"),
    "ES": ("es-ES", "es-ES-Chirp3-HD-Leda"),
    "TR": ("tr-TR", "tr-TR-Chirp3-HD-Leda"),
}

def create_client():
    credentials = service_account.Credentials.from_service_account_file(CREDENTIALS_PATH)
    return texttospeech.TextToSpeechClient(credentials=credentials)


def synthesize(client, text, lang_code, voice_name):
    synthesis_input = texttospeech.SynthesisInput(text=text)
    voice_params = texttospeech.VoiceSelectionParams(
        language_code=lang_code, name=voice_name)
    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.LINEAR16,
        sample_rate_hertz=SAMPLE_RATE)
    t0 = time.perf_counter()
    response = client.synthesize_speech(
        input=synthesis_input, voice=voice_params, audio_config=audio_config)
    elapsed_ms = (time.perf_counter() - t0) * 1000
    return response.audio_content, elapsed_ms


def pcm_to_wav(pcm_data, sr=8000, sw=2, ch=1):
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as wf:
        wf.setnchannels(ch)
        wf.setsampwidth(sw)
        wf.setframerate(sr)
        wf.writeframes(pcm_data)
    return buf.getvalue()


def get_audio_duration(pcm_data, sr=8000, sw=2, ch=1):
    return len(pcm_data) // (sw * ch) / sr

def main():
    print("=" * 80)
    print("  MULTILINGUAL CHIRP3-HD TTS TEST")
    print(f"  Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("  Voice: Chirp3-HD-Leda | Format: WAV 8kHz 16bit mono")
    print(f"  Attempts per language: {ATTEMPTS} (best time taken)")
    print("=" * 80)
    print()

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("[*] Creating Google Cloud TTS gRPC client...")
    client = create_client()
    print("[+] Client created successfully.")
    print()

    results = {}
    all_results = []

    for lang, text in SENTENCES.items():
        lang_code, voice_name = CHIRP3_VOICES[lang]
        char_count = len(text)

        print(f"--- {lang} ({lang_code}) | {voice_name} | {char_count} chars ---")
        print(f"    Text: {text[:80]}...")
        print()

        best_time = float("inf")
        best_audio = None
        best_duration = 0
        best_size = 0
        attempt_times = []

        for attempt in range(1, ATTEMPTS + 1):
            try:
                audio_data, elapsed_ms = synthesize(client, text, lang_code, voice_name)

                if audio_data[:4] == b"RIFF":
                    wav_data = audio_data
                    pcm_data = audio_data[44:]
                else:
                    pcm_data = audio_data
                    wav_data = pcm_to_wav(pcm_data)

                audio_duration = get_audio_duration(pcm_data)
                attempt_times.append(elapsed_ms)
                print(f"    Attempt {attempt}: {elapsed_ms:.0f} ms | "
                      f"audio={audio_duration:.2f}s | "
                      f"size={len(wav_data)} bytes")

                if elapsed_ms < best_time:
                    best_time = elapsed_ms
                    best_audio = wav_data
                    best_duration = audio_duration
                    best_size = len(wav_data)

            except Exception as e:
                attempt_times.append(None)
                print(f"    Attempt {attempt}: ERROR - {e}")

        if best_audio is None:
            print(f"    [!] ALL ATTEMPTS FAILED for {lang}")
            print()
            results[lang] = {"error": "all attempts failed"}
            continue

        filename = (f"Chirp3HD_Leda_{lang}_{char_count}sym_"
                    f"{best_time:.0f}ms_{best_duration:.1f}s.wav")
        filepath = os.path.join(OUTPUT_DIR, filename)
        with open(filepath, "wb") as f:
            f.write(best_audio)

        valid_times = [t for t in attempt_times if t is not None]
        avg_time = sum(valid_times) / len(valid_times)

        result = {
            "language": lang,
            "lang_code": lang_code,
            "voice": voice_name,
            "text": text,
            "char_count": char_count,
            "best_time_ms": round(best_time, 1),
            "avg_time_ms": round(avg_time, 1),
            "all_attempts_ms": [round(t, 1) if t else None for t in attempt_times],
            "audio_duration_s": round(best_duration, 2),
            "file_size_bytes": best_size,
            "filename": filename,
        }
        results[lang] = result
        all_results.append(result)

        print(f"    >>> Best: {best_time:.0f} ms | Avg: {avg_time:.0f} ms | "
              f"Audio: {best_duration:.2f}s | File: {filename}")
        print()
    # --- Summary ---
    print()
    print("=" * 80)
    print("  RESULTS SUMMARY")
    print("=" * 80)
    print()
    lang_h = 'Lang'
    chars_h = 'Chars'
    best_h = 'Best ms'
    avg_h = 'Avg ms'
    audio_h = 'Audio s'
    ratio_h = 'Ratio'
    stat_h = 'Status'
    sep = '---'
    print(f"  {lang_h:<6} {chars_h:<7} {best_h:<10} {avg_h:<10} {audio_h:<10} {ratio_h:<10} {stat_h}")
    print(f"  {sep:<6} {sep:<7} {sep:<10} {sep:<10} {sep:<10} {sep:<10} {sep:<8}")

    valid = [r for r in all_results if "error" not in r]

    for lang in SENTENCES:
        r = results.get(lang)
        if r and "error" not in r:
            ratio = r["best_time_ms"] / 1000 / r["audio_duration_s"] if r["audio_duration_s"] > 0 else 0
            status = "OK" if r["best_time_ms"] < 5000 else "SLOW"
            cc = r["char_count"]
            bt = r["best_time_ms"]
            at = r["avg_time_ms"]
            ad = r["audio_duration_s"]
            print(f"  {lang:<6} {cc:<7} {bt:<10.0f} {at:<10.0f} {ad:<10.2f} {ratio:<10.2f} {status}")
        else:
            dd = "--"
            ff = "FAILED"
            fl = "FAIL"
            print(f"  {lang:<6} {dd:<7} {ff:<10} {dd:<10} {dd:<10} {dd:<10} {fl}")

    if valid:
        avg_best = sum(r["best_time_ms"] for r in valid) / len(valid)
        min_best = min(r["best_time_ms"] for r in valid)
        max_best = max(r["best_time_ms"] for r in valid)
        total_audio = sum(r["audio_duration_s"] for r in valid)
        print()
        print(f"  Overall: avg_best={avg_best:.0f}ms | min={min_best:.0f}ms | max={max_best:.0f}ms")
        print(f"  Total audio generated: {total_audio:.1f}s across {len(valid)} languages")
        print(f"  Total files saved: {len(valid)}")
    else:
        avg_best = min_best = max_best = total_audio = None
    # --- Save JSON report ---
    report = {
        "test": "Multilingual Chirp3-HD TTS",
        "timestamp": datetime.now().isoformat(),
        "model": "Chirp3-HD-Leda",
        "format": "WAV 8kHz 16bit mono (LINEAR16)",
        "attempts_per_language": ATTEMPTS,
        "credentials": os.path.basename(CREDENTIALS_PATH),
        "output_dir": OUTPUT_DIR,
        "results": all_results,
        "summary": {
            "languages_tested": len(SENTENCES),
            "languages_ok": len(valid),
            "avg_best_ms": round(avg_best, 1) if avg_best else None,
            "min_best_ms": round(min_best, 1) if min_best else None,
            "max_best_ms": round(max_best, 1) if max_best else None,
            "total_audio_s": round(total_audio, 2) if total_audio else None,
        }
    }

    json_path = os.path.join(OUTPUT_DIR, "multilingual_chirp3hd_results.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"\n  JSON report saved: {json_path}")
    print()
    print("=" * 80)
    print("  TEST COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()
