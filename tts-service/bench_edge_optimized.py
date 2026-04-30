import sys, io, time, asyncio, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import edge_tts

TEXT = "Добрий день, я робот Василий, я прийшов тобі на допомогу!Привіт, я робот Вітай, я прийшов прийшов на допомогу!"
VOICE = "uk-UA-PolinaNeural"
RUNS = 3


# --- 1. Базовий (як було) ---
async def test_baseline():
    print("\n=== Edge TTS: Базовий (save) ===")
    times = []
    for i in range(RUNS):
        fname = f"edge_baseline_{i+1}.mp3"
        start = time.time()
        communicate = edge_tts.Communicate(TEXT, VOICE)
        await communicate.save(fname)
        elapsed = time.time() - start
        times.append(elapsed)
        size = os.path.getsize(fname)
        print(f"  Тест {i+1}: {elapsed:.3f} сек | {size} байт")
    avg = sum(times) / len(times)
    print(f"  Середнє: {avg:.3f} сек")
    return avg


# --- 2. Стрімінг ---
async def test_streaming():
    print("\n=== Edge TTS: Стрімінг (stream) ===")
    times = []
    for i in range(RUNS):
        fname = f"edge_stream_{i+1}.mp3"
        start = time.time()
        communicate = edge_tts.Communicate(TEXT, VOICE)
        chunks = []
        first_chunk_time = None
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                if first_chunk_time is None:
                    first_chunk_time = time.time() - start
                chunks.append(chunk["data"])
        audio = b"".join(chunks)
        elapsed = time.time() - start
        times.append(elapsed)
        with open(fname, "wb") as f:
            f.write(audio)
        print(f"  Тест {i+1}: {elapsed:.3f} сек | перший чанк: {first_chunk_time:.3f} сек | {len(audio)} байт")
    avg = sum(times) / len(times)
    print(f"  Середнє: {avg:.3f} сек")
    return avg


# --- 3. Стрімінг + прискорення rate ---
async def test_streaming_fast_rate():
    print("\n=== Edge TTS: Стрімінг + rate=+20% ===")
    times = []
    for i in range(RUNS):
        fname = f"edge_fast_{i+1}.mp3"
        start = time.time()
        communicate = edge_tts.Communicate(TEXT, VOICE, rate="+20%")
        chunks = []
        first_chunk_time = None
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                if first_chunk_time is None:
                    first_chunk_time = time.time() - start
                chunks.append(chunk["data"])
        audio = b"".join(chunks)
        elapsed = time.time() - start
        times.append(elapsed)
        with open(fname, "wb") as f:
            f.write(audio)
        print(f"  Тест {i+1}: {elapsed:.3f} сек | перший чанк: {first_chunk_time:.3f} сек | {len(audio)} байт")
    avg = sum(times) / len(times)
    print(f"  Середнє: {avg:.3f} сек")
    return avg


# --- 4. Паралельна генерація (3 фрази одночасно) ---
async def test_parallel():
    print("\n=== Edge TTS: Паралельна генерація (3 запити одночасно) ===")
    texts = [TEXT] * 3

    start = time.time()
    tasks = []
    for i, t in enumerate(texts):
        async def gen(text, idx):
            communicate = edge_tts.Communicate(text, VOICE)
            fname = f"edge_parallel_{idx+1}.mp3"
            await communicate.save(fname)
            return os.path.getsize(fname)
        tasks.append(gen(t, i))
    sizes = await asyncio.gather(*tasks)
    elapsed = time.time() - start
    for i, s in enumerate(sizes):
        print(f"  Файл {i+1}: {s} байт")
    print(f"  Усі 3 за: {elapsed:.3f} сек (тобто ~{elapsed/3:.3f} сек/шт)")
    return elapsed / 3


async def main():
    print("=" * 60)
    print("  EDGE TTS — БЕНЧМАРК ОПТИМІЗАЦІЙ")
    print(f"  Текст: {len(TEXT)} символів")
    print(f"  Голос: {VOICE}")
    print("=" * 60)

    results = {}
    results["baseline"] = await test_baseline()
    results["streaming"] = await test_streaming()
    results["fast_rate"] = await test_streaming_fast_rate()
    results["parallel"] = await test_parallel()
    print("\n" + "=" * 60)
    print("  ПІДСУМОК Edge TTS")
    print("=" * 60)
    print(f"  {'Метод':<30} {'Середній час':>12}")
    print(f"  {'-'*30} {'-'*12}")
    for name, t in results.items():
        if t < 0.001:
            print(f"  {name:<30} {t*1000:>9.3f} мс")
        else:
            print(f"  {name:<30} {t:>9.3f} сек")
    baseline = results["baseline"]
    print(f"\n  Прискорення відносно базового ({baseline:.3f} сек):")
    for name, t in results.items():
        if name != "baseline" and t > 0:
            speedup = baseline / t
            print(f"    {name}: x{speedup:.1f}")


if __name__ == "__main__":
    asyncio.run(main())
