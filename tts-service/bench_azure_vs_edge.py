import sys, io, time, asyncio, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import azure.cognitiveservices.speech as speechsdk
import edge_tts

# --- Налаштування ---
AZURE_KEY = "YOUR_SECRET_TOKEN"
AZURE_REGION = "westeurope"

TEXT = "Добрий день, я робот Василий, я прийшов тобі на допомогу!Привіт, я робот Вітай, я прийшов прийшов на допомогу!"
VOICE = "uk-UA-PolinaNeural"
RUNS = 5


# ===================== AZURE TTS =====================

def test_azure():
    """Azure TTS — офіційний SDK"""
    print("\n=== Azure TTS (офіційний API) ===")

    speech_config = speechsdk.SpeechConfig(subscription=AZURE_KEY, region=AZURE_REGION)
    speech_config.speech_synthesis_voice_name = VOICE
    speech_config.set_speech_synthesis_output_format(
        speechsdk.SpeechSynthesisOutputFormat.Audio16Khz32KBitRateMonoMp3
    )

    times = []
    for i in range(RUNS):
        start = time.time()

        synthesizer = speechsdk.SpeechSynthesizer(
            speech_config=speech_config, audio_config=None
        )
        result = synthesizer.speak_text_async(TEXT).get()

        elapsed = time.time() - start

        if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
            audio_data = result.audio_data
            fname = f"azure_test_{i+1}.mp3"
            with open(fname, "wb") as f:
                f.write(audio_data)
            times.append(elapsed)
            print(f"  Тест {i+1}: {elapsed:.3f} сек | {len(audio_data)} байт")
        else:
            cancellation = result.cancellation_details
            print(f"  Тест {i+1}: ПОМИЛКА — {cancellation.reason}")
            if cancellation.error_details:
                print(f"    Деталі: {cancellation.error_details}")
            times.append(elapsed)

    if times:
        avg = sum(times) / len(times)
        print(f"  Середнє: {avg:.3f} сек")
        return avg
    return None


def test_azure_reuse_synthesizer():
    """Azure TTS — з перевикористанням synthesizer (оптимізовано)"""
    print("\n=== Azure TTS (reuse synthesizer) ===")

    speech_config = speechsdk.SpeechConfig(subscription=AZURE_KEY, region=AZURE_REGION)
    speech_config.speech_synthesis_voice_name = VOICE
    speech_config.set_speech_synthesis_output_format(
        speechsdk.SpeechSynthesisOutputFormat.Audio16Khz32KBitRateMonoMp3
    )

    # Створюємо synthesizer ОДИН раз
    synthesizer = speechsdk.SpeechSynthesizer(
        speech_config=speech_config, audio_config=None
    )

    times = []
    for i in range(RUNS):
        start = time.time()
        result = synthesizer.speak_text_async(TEXT).get()
        elapsed = time.time() - start

        if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
            audio_data = result.audio_data
            fname = f"azure_reuse_{i+1}.mp3"
            with open(fname, "wb") as f:
                f.write(audio_data)
            times.append(elapsed)
            print(f"  Тест {i+1}: {elapsed:.3f} сек | {len(audio_data)} байт")
        else:
            cancellation = result.cancellation_details
            print(f"  Тест {i+1}: ПОМИЛКА — {cancellation.reason}")
            if cancellation.error_details:
                print(f"    Деталі: {cancellation.error_details}")
            times.append(elapsed)

    del synthesizer

    if times:
        avg = sum(times) / len(times)
        print(f"  Середнє: {avg:.3f} сек")
        return avg
    return None


# ===================== EDGE TTS =====================

async def test_edge():
    """Edge TTS — безкоштовний"""
    print("\n=== Edge TTS (безкоштовний) ===")
    times = []
    for i in range(RUNS):
        try:
            start = time.time()
            comm = edge_tts.Communicate(TEXT, VOICE)
            await comm.save(f"edge_test_{i+1}.mp3")
            elapsed = time.time() - start
            size = os.path.getsize(f"edge_test_{i+1}.mp3")
            times.append(elapsed)
            print(f"  Тест {i+1}: {elapsed:.3f} сек | {size} байт")
        except Exception as e:
            print(f"  Тест {i+1}: ПОМИЛКА — {e}")
            await asyncio.sleep(2)
    if times:
        avg = sum(times) / len(times)
        print(f"  Середнє: {avg:.3f} сек")
        return avg
    print("  Всі тести Edge TTS провалились!")
    return None


# ===================== MAIN =====================

async def main():
    print("=" * 60)
    print("  AZURE TTS vs EDGE TTS — ПОРІВНЯННЯ")
    print(f"  Текст: \"{TEXT}\"")
    print(f"  Символів: {len(TEXT)}")
    print(f"  Голос: {VOICE}")
    print(f"  Регіон Azure: {AZURE_REGION}")
    print(f"  Прогонів: {RUNS}")
    print("=" * 60)

    results = {}

    # Azure
    r = test_azure()
    if r:
        results["Azure (новий synth)"] = r

    r2 = test_azure_reuse_synthesizer()
    if r2:
        results["Azure (reuse synth)"] = r2

    # Edge
    edge_avg = await test_edge()
    results["Edge TTS"] = edge_avg

    # Підсумок
    print(f"\n{'='*60}")
    print(f"  ПІДСУМОК")
    print(f"{'='*60}")
    print(f"  {'Метод':<25} {'Середній час':>12}")
    print(f"  {'-'*25} {'-'*12}")
    for name, t in results.items():
        print(f"  {name:<25} {t:>9.3f} сек")

    if "Edge TTS" in results and len(results) > 1:
        edge = results["Edge TTS"]
        print(f"\n  Порівняння з Edge TTS ({edge:.3f} сек):")
        for name, t in results.items():
            if name != "Edge TTS":
                if t < edge:
                    print(f"    {name}: x{edge/t:.1f} ШВИДШЕ")
                else:
                    print(f"    {name}: x{t/edge:.1f} повільніше")


asyncio.run(main())

