import sys, io, time, wave, struct
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
import azure.cognitiveservices.speech as speechsdk

AZURE_KEY = "YOUR_SECRET_TOKEN"
AZURE_REGION = "westeurope"

TEXTS = [
    "Добрий день! Дякую що зателефонували. Чим можу вам допомогти?",
    "Ваш запит прийнято. Очікуйте відповідь оператора протягом хвилини.",
    "Привіт! Я віртуальний помічник компанії Оки-Токі. Чим можу бути корисний?",
]

VOICES = [
    ("uk-UA-PolinaNeural", "Поліна"),
    ("uk-UA-OstapNeural", "Остап"),
]

RUNS = 3


def run_production_test(voice_id, voice_name):
    print(f"\n{'='*70}")
    print(f"  ГОЛОС: {voice_name} ({voice_id})")
    print(f"  Оптимізації: reuse synth + pre-connect + streaming + mp3 128kbps")
    print(f"{'='*70}")

    config = speechsdk.SpeechConfig(subscription=AZURE_KEY, region=AZURE_REGION)
    config.speech_synthesis_voice_name = voice_id
    config.set_speech_synthesis_output_format(
        speechsdk.SpeechSynthesisOutputFormat.Audio16Khz128KBitRateMonoMp3
    )

    synth = speechsdk.SpeechSynthesizer(speech_config=config, audio_config=None)
    conn = speechsdk.Connection.from_speech_synthesizer(synth)
    conn.open(True)
    time.sleep(0.5)

    # Прогрів
    synth.speak_text_async("тест").get()

    all_times = []

    for idx, text in enumerate(TEXTS):
        print(f"\n  Текст {idx+1}: \"{text}\" ({len(text)} симв.)")

        best_time = 999
        best_audio = None

        for i in range(RUNS):
            start = time.time()
            result = synth.speak_text_async(text).get()
            elapsed = time.time() - start

            if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
                audio = result.audio_data
                sv = result.properties.get_property(speechsdk.PropertyId.SpeechServiceResponse_SynthesisServiceLatencyMs)
                nw = result.properties.get_property(speechsdk.PropertyId.SpeechServiceResponse_SynthesisNetworkLatencyMs)
                fb = result.properties.get_property(speechsdk.PropertyId.SpeechServiceResponse_SynthesisFirstByteLatencyMs)
                print(f"    Run {i+1}: {elapsed:.3f}с | service: {sv}мс | network: {nw}мс | first_byte: {fb}мс | {len(audio)}б")
                all_times.append(elapsed)
                if elapsed < best_time:
                    best_time = elapsed
                    best_audio = audio
            else:
                print(f"    Run {i+1}: ПОМИЛКА")

        # Зберігаємо найкращий результат
        fname = f"prod_{voice_name}_{idx+1}.mp3"
        with open(fname, "wb") as f:
            f.write(best_audio)
        print(f"    Збережено: {fname} (найшвидший: {best_time:.3f}с)")

    del synth

    avg = sum(all_times) / len(all_times) if all_times else 0
    best = min(all_times) if all_times else 0
    worst = max(all_times) if all_times else 0
    print(f"\n  {'─'*50}")
    print(f"  {voice_name} — середнє: {avg:.3f}с | мін: {best:.3f}с | макс: {worst:.3f}с")
    return avg, best, worst


def main():
    print("=" * 70)
    print("  ПРОДАКШН ТЕСТ — Azure TTS")
    print(f"  Усі оптимізації: reuse + pre-connect + streaming")
    print(f"  Формат: MP3 128kbps (якісний звук)")
    print(f"  Регіон: {AZURE_REGION}")
    print(f"  Прогонів на текст: {RUNS}")
    print("=" * 70)

    results = {}
    for voice_id, voice_name in VOICES:
        avg, best, worst = run_production_test(voice_id, voice_name)
        results[voice_name] = (avg, best, worst)

    print(f"\n{'='*70}")
    print(f"  ФІНАЛЬНЕ ПОРІВНЯННЯ")
    print(f"{'='*70}")
    print(f"  {'Голос':<15} {'Середнє':>10} {'Найкращий':>10} {'Найгірший':>10}")
    print(f"  {'─'*15} {'─'*10} {'─'*10} {'─'*10}")
    for name, (avg, best, worst) in results.items():
        print(f"  {name:<15} {avg:>8.3f}с {best:>8.3f}с {worst:>8.3f}с")

    print(f"\n  Аудіо файли:")
    for voice_id, voice_name in VOICES:
        for i in range(len(TEXTS)):
            print(f"    prod_{voice_name}_{i+1}.mp3")


if __name__ == "__main__":
    main()

