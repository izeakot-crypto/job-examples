import sys, io, time, asyncio
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
import edge_tts

TEXT = "Привіт, я робот Василий, я прийшов тобі на допомогу!"

VOICES = [
    ("uk-UA-PolinaNeural", "Поліна"),
    ("uk-UA-OstapNeural", "Остап"),
]

RUNS = 3

async def test_save(voice_id, text, fname):
    """Метод save() — чекає повну генерацію, зберігає файл"""
    communicate = edge_tts.Communicate(text, voice_id)
    start = time.time()
    await communicate.save(fname)
    return time.time() - start

async def test_stream(voice_id, text, fname):
    """Метод stream() — отримує чанки по мережі"""
    communicate = edge_tts.Communicate(text, voice_id)
    start = time.time()
    audio_data = b""
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_data += chunk["data"]
    elapsed = time.time() - start
    with open(fname, "wb") as f:
        f.write(audio_data)
    return elapsed

async def main():
    print(f'Текст: "{TEXT}"')
    print(f"Формат: Edge TTS default (mp3)")
    print(f"Кількість прогонів: {RUNS}\n")

    for voice_id, voice_name in VOICES:
        print(f"\n{'='*60}")
        print(f"  {voice_name} ({voice_id})")
        print(f"{'='*60}")

        save_times = []
        stream_times = []

        for run in range(1, RUNS + 1):
            # save()
            fname_save = f"edge8k_save_{voice_name}_{run}.mp3"
            try:
                t = await test_save(voice_id, TEXT, fname_save)
                save_times.append(t)
                print(f"  save()   run {run}: {t:.3f}с | {fname_save}")
            except Exception as e:
                print(f"  save()   run {run}: ПОМИЛКА — {e}")

            # stream()
            fname_stream = f"edge8k_stream_{voice_name}_{run}.mp3"
            try:
                t = await test_stream(voice_id, TEXT, fname_stream)
                stream_times.append(t)
                print(f"  stream() run {run}: {t:.3f}с | {fname_stream}")
            except Exception as e:
                print(f"  stream() run {run}: ПОМИЛКА — {e}")

            print()

        # Підсумок
        if save_times:
            avg_save = sum(save_times) / len(save_times)
            print(f"  save()   середнє: {avg_save:.3f}с (min {min(save_times):.3f}, max {max(save_times):.3f})")
        if stream_times:
            avg_stream = sum(stream_times) / len(stream_times)
            print(f"  stream() середнє: {avg_stream:.3f}с (min {min(stream_times):.3f}, max {max(stream_times):.3f})")
        if save_times and stream_times:
            diff = avg_stream / avg_save
            winner = "save()" if avg_save < avg_stream else "stream()"
            print(f"  >>> {winner} швидше у {max(diff, 1/diff):.2f}x")

    print(f"\n{'='*60}")
    print(f"УВАГА: Edge TTS віддає тільки MP3 (не підтримує riff-8khz-16bit-mono-pcm)")
    print(f"Для 8kHz WAV потрібна конвертація через ffmpeg або Azure TTS SDK")
    print(f"{'='*60}")

asyncio.run(main())
