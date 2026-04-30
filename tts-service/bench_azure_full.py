import sys, io, time, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import azure.cognitiveservices.speech as speechsdk

# --- Налаштування ---
AZURE_KEY = "YOUR_SECRET_TOKEN"
AZURE_REGION = "westeurope"

TEXT = "Добрий день, я робот Василий, я прийшов тобі на допомогу!Привіт, я робот Вітай, я прийшов прийшов на допомогу!"
VOICE = "uk-UA-PolinaNeural"
RUNS = 5


def get_latency_details(result):
    """Отримати детальні метрики латентності з результату"""
    props = result.properties
    try:
        first_byte = props.get_property(speechsdk.PropertyId.SpeechServiceResponse_SynthesisFirstByteLatencyMs)
        finish = props.get_property(speechsdk.PropertyId.SpeechServiceResponse_SynthesisFinishLatencyMs)
        network = props.get_property(speechsdk.PropertyId.SpeechServiceResponse_SynthesisNetworkLatencyMs)
        service = props.get_property(speechsdk.PropertyId.SpeechServiceResponse_SynthesisServiceLatencyMs)
        return {
            "first_byte_ms": int(first_byte) if first_byte else None,
            "finish_ms": int(finish) if finish else None,
            "network_ms": int(network) if network else None,
            "service_ms": int(service) if service else None,
        }
    except:
        return None


# --- 1. Базовий (новий synthesizer кожен раз) ---
def test_baseline():
    print("\n=== 1. Базовий (новий synthesizer) ===")
    config = speechsdk.SpeechConfig(subscription=AZURE_KEY, region=AZURE_REGION)
    config.speech_synthesis_voice_name = VOICE
    config.set_speech_synthesis_output_format(
        speechsdk.SpeechSynthesisOutputFormat.Audio16Khz32KBitRateMonoMp3
    )
    times = []
    for i in range(RUNS):
        synth = speechsdk.SpeechSynthesizer(speech_config=config, audio_config=None)
        start = time.time()
        result = synth.speak_text_async(TEXT).get()
        elapsed = time.time() - start
        if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
            times.append(elapsed)
            lat = get_latency_details(result)
            print(f"  Тест {i+1}: {elapsed:.3f} сек | {len(result.audio_data)} байт | service: {lat['service_ms']}мс | network: {lat['network_ms']}мс | first_byte: {lat['first_byte_ms']}мс")
        else:
            print(f"  Тест {i+1}: ПОМИЛКА — {result.cancellation_details.reason}")
        del synth
    avg = sum(times) / len(times) if times else None
    if avg:
        print(f"  Середнє: {avg:.3f} сек")
    return avg


# --- 2. Reuse Synthesizer ---
def test_reuse():
    print("\n=== 2. Reuse Synthesizer ===")
    config = speechsdk.SpeechConfig(subscription=AZURE_KEY, region=AZURE_REGION)
    config.speech_synthesis_voice_name = VOICE
    config.set_speech_synthesis_output_format(
        speechsdk.SpeechSynthesisOutputFormat.Audio16Khz32KBitRateMonoMp3
    )
    synth = speechsdk.SpeechSynthesizer(speech_config=config, audio_config=None)
    times = []
    for i in range(RUNS):
        start = time.time()
        result = synth.speak_text_async(TEXT).get()
        elapsed = time.time() - start
        if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
            times.append(elapsed)
            lat = get_latency_details(result)
            print(f"  Тест {i+1}: {elapsed:.3f} сек | {len(result.audio_data)} байт | service: {lat['service_ms']}мс | network: {lat['network_ms']}мс | first_byte: {lat['first_byte_ms']}мс")
        else:
            print(f"  Тест {i+1}: ПОМИЛКА — {result.cancellation_details.reason}")
    del synth
    avg = sum(times) / len(times) if times else None
    if avg:
        print(f"  Середнє: {avg:.3f} сек")
    return avg


# --- 3. Pre-connect + Reuse ---
def test_preconnect():
    print("\n=== 3. Pre-connect + Reuse Synthesizer ===")
    config = speechsdk.SpeechConfig(subscription=AZURE_KEY, region=AZURE_REGION)
    config.speech_synthesis_voice_name = VOICE
    config.set_speech_synthesis_output_format(
        speechsdk.SpeechSynthesisOutputFormat.Audio16Khz32KBitRateMonoMp3
    )
    synth = speechsdk.SpeechSynthesizer(speech_config=config, audio_config=None)

    # Pre-connect!
    connection = speechsdk.Connection.from_speech_synthesizer(synth)
    print("  Підключаюсь заздалегідь...")
    connection.open(True)
    time.sleep(0.5)  # дати час на підключення
    print("  Підключено!")

    times = []
    for i in range(RUNS):
        start = time.time()
        result = synth.speak_text_async(TEXT).get()
        elapsed = time.time() - start
        if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
            times.append(elapsed)
            lat = get_latency_details(result)
            print(f"  Тест {i+1}: {elapsed:.3f} сек | {len(result.audio_data)} байт | service: {lat['service_ms']}мс | network: {lat['network_ms']}мс | first_byte: {lat['first_byte_ms']}мс")
        else:
            print(f"  Тест {i+1}: ПОМИЛКА — {result.cancellation_details.reason}")
    del synth
    avg = sum(times) / len(times) if times else None
    if avg:
        print(f"  Середнє: {avg:.3f} сек")
    return avg


# --- 4. Streaming + Pre-connect + Reuse ---
def test_streaming():
    print("\n=== 4. Streaming + Pre-connect + Reuse ===")
    config = speechsdk.SpeechConfig(subscription=AZURE_KEY, region=AZURE_REGION)
    config.speech_synthesis_voice_name = VOICE
    config.set_speech_synthesis_output_format(
        speechsdk.SpeechSynthesisOutputFormat.Audio16Khz32KBitRateMonoMp3
    )
    synth = speechsdk.SpeechSynthesizer(speech_config=config, audio_config=None)

    connection = speechsdk.Connection.from_speech_synthesizer(synth)
    connection.open(True)
    time.sleep(0.5)

    times = []
    first_chunk_times = []

    for i in range(RUNS):
        start = time.time()
        first_chunk_time = None

        result = synth.start_speaking_text_async(TEXT).get()
        audio_data_stream = speechsdk.AudioDataStream(result)

        audio_buffer = bytes(4096)
        chunks = []
        filled = audio_data_stream.read_data(audio_buffer)
        while filled > 0:
            if first_chunk_time is None:
                first_chunk_time = time.time() - start
            chunks.append(audio_buffer[:filled])
            filled = audio_data_stream.read_data(audio_buffer)

        elapsed = time.time() - start
        total_audio = b"".join(chunks)
        times.append(elapsed)
        if first_chunk_time:
            first_chunk_times.append(first_chunk_time)

        lat = get_latency_details(result)
        print(f"  Тест {i+1}: {elapsed:.3f} сек | 1й чанк: {first_chunk_time:.3f} сек | {len(total_audio)} байт | service: {lat['service_ms']}мс | first_byte: {lat['first_byte_ms']}мс")

    del synth
    avg = sum(times) / len(times) if times else None
    avg_first = sum(first_chunk_times) / len(first_chunk_times) if first_chunk_times else None
    if avg:
        print(f"  Середнє загальне: {avg:.3f} сек")
    if avg_first:
        print(f"  Середнє 1й чанк: {avg_first:.3f} сек")
    return avg, avg_first


def main():
    print("=" * 70)
    print("  AZURE TTS — ВСІ ОПТИМІЗАЦІЇ (з офіційного гайду Microsoft)")
    print(f"  Текст: \"{TEXT}\"")
    print(f"  Символів: {len(TEXT)}")
    print(f"  Голос: {VOICE}")
    print(f"  Регіон: {AZURE_REGION}")
    print(f"  Прогонів: {RUNS}")
    print("=" * 70)

    results = {}

    r1 = test_baseline()
    if r1:
        results["1. Базовий"] = r1

    r2 = test_reuse()
    if r2:
        results["2. Reuse synth"] = r2

    r3 = test_preconnect()
    if r3:
        results["3. Pre-connect+Reuse"] = r3

    r4_total, r4_first = test_streaming()
    if r4_total:
        results["4. Streaming (total)"] = r4_total
    if r4_first:
        results["4. Streaming (1й чанк)"] = r4_first

    # Підсумок
    print(f"\n{'='*70}")
    print(f"  ПІДСУМОК")
    print(f"{'='*70}")
    print(f"  {'Метод':<30} {'Час':>10}")
    print(f"  {'-'*30} {'-'*10}")
    for name, t in results.items():
        print(f"  {name:<30} {t:>7.3f} сек")

    baseline = results.get("1. Базовий")
    if baseline:
        print(f"\n  Прискорення відносно базового ({baseline:.3f} сек):")
        for name, t in results.items():
            if name != "1. Базовий" and t > 0:
                print(f"    {name}: x{baseline/t:.1f}")


if __name__ == "__main__":
    main()

