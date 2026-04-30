import sys, io, time, os, asyncio
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import azure.cognitiveservices.speech as speechsdk
import edge_tts

# --- Налаштування ---
AZURE_KEY = "YOUR_SECRET_TOKEN"
AZURE_REGION = "westeurope"

TEXT = "Привіт, я твій особистий помічник. Як твої справи? Я робот Ілля, радий допомогти"
VOICE_UA = "uk-UA-PolinaNeural"
RUNS = 10


def get_latency(result):
    props = result.properties
    try:
        return {
            "first_byte": int(props.get_property(speechsdk.PropertyId.SpeechServiceResponse_SynthesisFirstByteLatencyMs) or 0),
            "finish": int(props.get_property(speechsdk.PropertyId.SpeechServiceResponse_SynthesisFinishLatencyMs) or 0),
            "network": int(props.get_property(speechsdk.PropertyId.SpeechServiceResponse_SynthesisNetworkLatencyMs) or 0),
            "service": int(props.get_property(speechsdk.PropertyId.SpeechServiceResponse_SynthesisServiceLatencyMs) or 0),
        }
    except:
        return None


# ==================== AZURE: PRODUCTION MODE ====================

def test_azure_production():
    """
    Симуляція продакшну:
    1. Сервер стартує → створює synthesizer + pre-connect (один раз)
    2. Приходить запит → streaming генерація
    """
    print("\n" + "=" * 70)
    print("  AZURE TTS — ПРОДАКШН РЕЖИМ")
    print("  (reuse synthesizer + pre-connect + streaming)")
    print("=" * 70)

    # === СТАРТ СЕРВЕРА (один раз) ===
    print("\n  [SERVER START] Ініціалізація...")
    server_start = time.time()

    config = speechsdk.SpeechConfig(subscription=AZURE_KEY, region=AZURE_REGION)
    config.speech_synthesis_voice_name = VOICE_UA
    config.set_speech_synthesis_output_format(
        speechsdk.SpeechSynthesisOutputFormat.Audio16Khz32KBitRateMonoMp3
    )

    synth = speechsdk.SpeechSynthesizer(speech_config=config, audio_config=None)
    conn = speechsdk.Connection.from_speech_synthesizer(synth)
    conn.open(True)
    time.sleep(0.5)

    server_ready = time.time() - server_start
    print(f"  [SERVER START] Готовий за {server_ready:.3f} сек (один раз)")

    # === ОБРОБКА ЗАПИТІВ ===
    print(f"\n  [REQUESTS] Симуляція {RUNS} вхідних дзвінків...\n")

    total_times = []
    first_chunk_times = []
    latencies = []

    for i in range(RUNS):
        # Запит прийшов — починаємо генерацію
        start = time.time()
        first_chunk = None

        result = synth.start_speaking_text_async(TEXT).get()
        stream = speechsdk.AudioDataStream(result)

        audio_buffer = bytes(4096)
        chunks = []
        filled = stream.read_data(audio_buffer)
        while filled > 0:
            if first_chunk is None:
                first_chunk = time.time() - start
            chunks.append(audio_buffer[:filled])
            filled = stream.read_data(audio_buffer)

        elapsed = time.time() - start
        audio = b"".join(chunks)

        total_times.append(elapsed)
        if first_chunk:
            first_chunk_times.append(first_chunk)

        lat = get_latency(result)
        if lat:
            latencies.append(lat)

        print(f"  Дзвінок {i+1:>2}: total={elapsed:.3f}с | 1й чанк={first_chunk:.3f}с | service={lat['service']:>3}мс | network={lat['network']:>3}мс | first_byte={lat['first_byte']:>3}мс | {len(audio)} байт")

    # Зберегти останній файл для перевірки якості
    with open("azure_production_sample.mp3", "wb") as f:
        f.write(audio)

    del synth

    # Статистика
    avg_total = sum(total_times) / len(total_times)
    avg_first = sum(first_chunk_times) / len(first_chunk_times) if first_chunk_times else 0
    min_total = min(total_times)
    max_total = max(total_times)
    avg_service = sum(l["service"] for l in latencies) / len(latencies) if latencies else 0
    avg_network = sum(l["network"] for l in latencies) / len(latencies) if latencies else 0
    avg_fb = sum(l["first_byte"] for l in latencies) / len(latencies) if latencies else 0

    print(f"\n  {'─'*50}")
    print(f"  Середній total:       {avg_total:.3f} сек")
    print(f"  Середній 1й чанк:     {avg_first:.3f} сек")
    print(f"  Мін/Макс total:       {min_total:.3f} / {max_total:.3f} сек")
    print(f"  Середній service:     {avg_service:.0f} мс")
    print(f"  Середній network:     {avg_network:.0f} мс")
    print(f"  Середній first_byte:  {avg_fb:.0f} мс")

    return avg_total, avg_first


# ==================== EDGE TTS: PRODUCTION MODE ====================

async def test_edge_production():
    print("\n" + "=" * 70)
    print("  EDGE TTS — ПРОДАКШН РЕЖИМ")
    print("  (save — найшвидший метод для Edge)")
    print("=" * 70)

    print(f"\n  [REQUESTS] Симуляція {RUNS} вхідних дзвінків...\n")

    times = []
    for i in range(RUNS):
        try:
            fname = f"_edge_prod_{i}.mp3"
            start = time.time()
            comm = edge_tts.Communicate(TEXT, VOICE_UA)
            await comm.save(fname)
            elapsed = time.time() - start
            size = os.path.getsize(fname)
            times.append(elapsed)
            print(f"  Дзвінок {i+1:>2}: {elapsed:.3f} сек | {size} байт")
            os.remove(fname)
        except Exception as e:
            print(f"  Дзвінок {i+1:>2}: ПОМИЛКА — {e}")
            await asyncio.sleep(1)

    if times:
        avg = sum(times) / len(times)
        print(f"\n  {'─'*50}")
        print(f"  Середнє:         {avg:.3f} сек")
        print(f"  Мін/Макс:        {min(times):.3f} / {max(times):.3f} сек")
        return avg
    return None


# ==================== MAIN ====================

async def main():
    print("=" * 70)
    print("  ПРОДАКШН ТЕСТ — AZURE vs EDGE TTS")
    print(f"  Текст: \"{TEXT}\"")
    print(f"  Символів: {len(TEXT)}")
    print(f"  Голос: {VOICE_UA}")
    print(f"  Прогонів: {RUNS}")
    print("=" * 70)

    azure_total, azure_first = test_azure_production()
    edge_avg = await test_edge_production()

    # Фінальне порівняння
    print(f"\n{'='*70}")
    print(f"  ФІНАЛЬНЕ ПОРІВНЯННЯ (ПРОДАКШН)")
    print(f"{'='*70}")
    print(f"")
    print(f"  {'Метрика':<30} {'Azure TTS':>12} {'Edge TTS':>12} {'Різниця':>12}")
    print(f"  {'─'*30} {'─'*12} {'─'*12} {'─'*12}")

    if azure_total and edge_avg:
        print(f"  {'Повна генерація':<30} {azure_total:>9.3f} с  {edge_avg:>9.3f} с  x{edge_avg/azure_total:.1f}")
    if azure_first:
        print(f"  {'Перший звук':<30} {azure_first:>9.3f} с  {'= total':>12} {'—':>12}")
    print(f"  {'Ціна':<30} {'$16/1M':>12} {'$0':>12} {'—':>12}")
    print(f"  {'Потрібен ключ':<30} {'Так':>12} {'Ні':>12} {'—':>12}")

    if azure_total and edge_avg:
        print(f"\n  Azure швидше за Edge у {edge_avg/azure_total:.1f} разів")
        print(f"  Клієнт чує перший звук через {azure_first*1000:.0f} мс (Azure) vs {edge_avg*1000:.0f} мс (Edge)")


asyncio.run(main())

