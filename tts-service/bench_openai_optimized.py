import sys, io, time, os
from concurrent.futures import ThreadPoolExecutor
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from openai import OpenAI

API_KEY = os.environ.get("OPENAI_API_KEY",
    "YOUR_OPENAI_API_KEY")

client = OpenAI(api_key=API_KEY)

TEXT = "Добрий день, я робот Василий, я прийшов тобі на допомогу!Привіт, я робот Вітай, я прийшов прийшов на допомогу!"
VOICE = "nova"
RUNS = 3


# --- 1. Базовий (як було) — mp3 ---
def test_baseline():
    print("\n=== OpenAI TTS: Базовий (tts-1, mp3) ===")
    times = []
    for i in range(RUNS):
        start = time.time()
        response = client.audio.speech.create(
            model="tts-1",
            voice=VOICE,
            input=TEXT,
            response_format="mp3",
        )
        content = response.read()
        elapsed = time.time() - start
        times.append(elapsed)
        fname = f"openai_baseline_{i+1}.mp3"
        with open(fname, "wb") as f:
            f.write(content)
        print(f"  Тест {i+1}: {elapsed:.3f} сек | {len(content)} байт")
    avg = sum(times) / len(times)
    print(f"  Середнє: {avg:.3f} сек")
    return avg


# --- 2. Стрімінг ---
def test_streaming():
    print("\n=== OpenAI TTS: Стрімінг (tts-1, mp3) ===")
    times = []
    for i in range(RUNS):
        fname = f"openai_stream_{i+1}.mp3"
        start = time.time()
        first_chunk_time = None
        with client.audio.speech.with_streaming_response.create(
            model="tts-1",
            voice=VOICE,
            input=TEXT,
            response_format="mp3",
        ) as response:
            with open(fname, "wb") as f:
                for chunk in response.iter_bytes(chunk_size=4096):
                    if first_chunk_time is None:
                        first_chunk_time = time.time() - start
                    f.write(chunk)
        elapsed = time.time() - start
        times.append(elapsed)
        size = os.path.getsize(fname)
        print(f"  Тест {i+1}: {elapsed:.3f} сек | перший чанк: {first_chunk_time:.3f} сек | {size} байт")
    avg = sum(times) / len(times)
    print(f"  Середнє: {avg:.3f} сек")
    return avg


# --- 3. Формат opus (найменший розмір) ---
def test_opus():
    print("\n=== OpenAI TTS: Opus формат (tts-1) ===")
    times = []
    for i in range(RUNS):
        start = time.time()
        response = client.audio.speech.create(
            model="tts-1",
            voice=VOICE,
            input=TEXT,
            response_format="opus",
        )
        content = response.read()
        elapsed = time.time() - start
        times.append(elapsed)
        fname = f"openai_opus_{i+1}.opus"
        with open(fname, "wb") as f:
            f.write(content)
        print(f"  Тест {i+1}: {elapsed:.3f} сек | {len(content)} байт")
    avg = sum(times) / len(times)
    print(f"  Середнє: {avg:.3f} сек")
    return avg


# --- 4. Стрімінг + opus ---
def test_streaming_opus():
    print("\n=== OpenAI TTS: Стрімінг + Opus ===")
    times = []
    for i in range(RUNS):
        fname = f"openai_stream_opus_{i+1}.opus"
        start = time.time()
        first_chunk_time = None
        with client.audio.speech.with_streaming_response.create(
            model="tts-1",
            voice=VOICE,
            input=TEXT,
            response_format="opus",
        ) as response:
            with open(fname, "wb") as f:
                for chunk in response.iter_bytes(chunk_size=4096):
                    if first_chunk_time is None:
                        first_chunk_time = time.time() - start
                    f.write(chunk)
        elapsed = time.time() - start
        times.append(elapsed)
        size = os.path.getsize(fname)
        print(f"  Тест {i+1}: {elapsed:.3f} сек | перший чанк: {first_chunk_time:.3f} сек | {size} байт")
    avg = sum(times) / len(times)
    print(f"  Середнє: {avg:.3f} сек")
    return avg


# --- 5. Паралельні запити (3 одночасно) ---
def test_parallel():
    print("\n=== OpenAI TTS: Паралельна генерація (3 запити) ===")

    def gen_one(idx):
        response = client.audio.speech.create(
            model="tts-1",
            voice=VOICE,
            input=TEXT,
            response_format="mp3",
        )
        content = response.read()
        fname = f"openai_parallel_{idx+1}.mp3"
        with open(fname, "wb") as f:
            f.write(content)
        return len(content)

    start = time.time()
    with ThreadPoolExecutor(max_workers=3) as pool:
        sizes = list(pool.map(gen_one, range(3)))
    elapsed = time.time() - start
    for i, s in enumerate(sizes):
        print(f"  Файл {i+1}: {s} байт")
    print(f"  Усі 3 за: {elapsed:.3f} сек (тобто ~{elapsed/3:.3f} сек/шт)")
    return elapsed / 3


def main():
    print("=" * 60)
    print("  OPENAI TTS — БЕНЧМАРК ОПТИМІЗАЦІЙ")
    print(f"  Текст: {len(TEXT)} символів")
    print(f"  Голос: {VOICE}")
    print("=" * 60)

    results = {}
    results["baseline_mp3"] = test_baseline()
    results["streaming_mp3"] = test_streaming()
    results["opus"] = test_opus()
    results["streaming_opus"] = test_streaming_opus()
    results["parallel"] = test_parallel()

    print("\n" + "=" * 60)
    print("  ПІДСУМОК OpenAI TTS")
    print("=" * 60)
    print(f"  {'Метод':<30} {'Середній час':>12}")
    print(f"  {'-'*30} {'-'*12}")
    for name, t in results.items():
        if t < 0.001:
            print(f"  {name:<30} {t*1000:>9.3f} мс")
        else:
            print(f"  {name:<30} {t:>9.3f} сек")
    baseline = results["baseline_mp3"]
    print(f"\n  Прискорення відносно базового ({baseline:.3f} сек):")
    for name, t in results.items():
        if name != "baseline_mp3" and t > 0:
            speedup = baseline / t
            print(f"    {name}: x{speedup:.1f}")


if __name__ == "__main__":
    main()

