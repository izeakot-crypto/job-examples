import sys, io, time, asyncio, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import edge_tts

TEXT = "Добрий день, я робот Василий, я прийшов тобі на допомогу!Привіт, я робот Вітай, я прийшов прийшов на допомогу!"
VOICE = "uk-UA-PolinaNeural"
RUNS = 10


async def test_save():
    """Звичайний save()"""
    times = []
    for i in range(RUNS):
        start = time.time()
        comm = edge_tts.Communicate(TEXT, VOICE)
        await comm.save(f"_tmp_save_{i}.mp3")
        elapsed = time.time() - start
        times.append(elapsed)
    return times


async def test_stream():
    """Стрімінг stream()"""
    total_times = []
    first_chunk_times = []
    for i in range(RUNS):
        start = time.time()
        comm = edge_tts.Communicate(TEXT, VOICE)
        first_chunk = None
        chunks = []
        async for chunk in comm.stream():
            if chunk["type"] == "audio":
                if first_chunk is None:
                    first_chunk = time.time() - start
                chunks.append(chunk["data"])
        total = time.time() - start
        with open(f"_tmp_stream_{i}.mp3", "wb") as f:
            f.write(b"".join(chunks))
        total_times.append(total)
        first_chunk_times.append(first_chunk)
    return total_times, first_chunk_times


async def main():
    print("=" * 60)
    print("  EDGE TTS: save() vs stream()")
    print(f"  Текст: \"{TEXT}\"")
    print(f"  Голос: {VOICE}")
    print(f"  Прогонів: {RUNS}")
    print("=" * 60)

    print("\n  Тестую save()...")
    save_times = await test_save()

    print("  Тестую stream()...")
    stream_total, stream_first = await test_stream()

    # Таблиця
    print(f"\n  {'Прогін':<8} {'save()':>10} {'stream()':>10} {'1й чанк':>10}")
    print(f"  {'-'*8} {'-'*10} {'-'*10} {'-'*10}")
    for i in range(RUNS):
        print(f"  {i+1:<8} {save_times[i]:>9.3f}с {stream_total[i]:>9.3f}с {stream_first[i]:>9.3f}с")

    avg_save = sum(save_times) / len(save_times)
    avg_stream = sum(stream_total) / len(stream_total)
    avg_first = sum(stream_first) / len(stream_first)

    print(f"  {'-'*8} {'-'*10} {'-'*10} {'-'*10}")
    print(f"  {'Середнє':<8} {avg_save:>9.3f}с {avg_stream:>9.3f}с {avg_first:>9.3f}с")

    min_save = min(save_times)
    min_stream = min(stream_total)
    min_first = min(stream_first)
    print(f"  {'Мін.':<8} {min_save:>9.3f}с {min_stream:>9.3f}с {min_first:>9.3f}с")

    max_save = max(save_times)
    max_stream = max(stream_total)
    max_first = max(stream_first)
    print(f"  {'Макс.':<8} {max_save:>9.3f}с {max_stream:>9.3f}с {max_first:>9.3f}с")

    print(f"\n  ВЕРДИКТ:")
    if avg_stream < avg_save:
        print(f"  stream() швидший за save() у загальному часі: {avg_save:.3f}с vs {avg_stream:.3f}с (x{avg_save/avg_stream:.2f})")
    else:
        print(f"  save() швидший за stream() у загальному часі: {avg_save:.3f}с vs {avg_stream:.3f}с (x{avg_stream/avg_save:.2f} повільніше)")
    print(f"  Перший чанк стрімінгу: {avg_first:.3f}с (на {(avg_save - avg_first)*1000:.0f} мс раніше ніж save)")

    # Прибираємо тимчасові файли
    for i in range(RUNS):
        for f in [f"_tmp_save_{i}.mp3", f"_tmp_stream_{i}.mp3"]:
            if os.path.exists(f):
                os.remove(f)


asyncio.run(main())
