import sys, io, time, asyncio, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import edge_tts
from openai import OpenAI

API_KEY = os.environ.get("OPENAI_API_KEY",
    "YOUR_OPENAI_API_KEY")
client = OpenAI(api_key=API_KEY)

TEXT = "Добрий день, я робот Василий, я прийшов тобі на допомогу!Привіт, я робот Вітай, я прийшов прийшов на допомогу!"
VOICE_EDGE = "uk-UA-PolinaNeural"
VOICE_OPENAI = "nova"
RUNS = 5  # 5 прогонів для точності


# ===================== EDGE TTS =====================

async def edge_baseline():
    """Edge TTS — звичайний save()"""
    times = []
    for i in range(RUNS):
        start = time.time()
        comm = edge_tts.Communicate(TEXT, VOICE_EDGE)
        await comm.save(f"_tmp_edge_base_{i}.mp3")
        times.append(time.time() - start)
    return times


async def edge_streaming():
    """Edge TTS — стрімінг stream()"""
    total_times = []
    first_chunk_times = []
    for i in range(RUNS):
        start = time.time()
        comm = edge_tts.Communicate(TEXT, VOICE_EDGE)
        first_chunk = None
        chunks = []
        async for chunk in comm.stream():
            if chunk["type"] == "audio":
                if first_chunk is None:
                    first_chunk = time.time() - start
                chunks.append(chunk["data"])
        total = time.time() - start
        with open(f"_tmp_edge_stream_{i}.mp3", "wb") as f:
            f.write(b"".join(chunks))
        total_times.append(total)
        first_chunk_times.append(first_chunk)
    return total_times, first_chunk_times


# ===================== OPENAI TTS =====================

def openai_baseline():
    """OpenAI TTS — звичайний read()"""
    times = []
    for i in range(RUNS):
        start = time.time()
        resp = client.audio.speech.create(
            model="tts-1", voice=VOICE_OPENAI, input=TEXT, response_format="mp3",
        )
        resp.read()
        times.append(time.time() - start)
    return times


def openai_streaming():
    """OpenAI TTS — стрімінг"""
    total_times = []
    first_chunk_times = []
    for i in range(RUNS):
        start = time.time()
        first_chunk = None
        with client.audio.speech.with_streaming_response.create(
            model="tts-1", voice=VOICE_OPENAI, input=TEXT, response_format="mp3",
        ) as resp:
            for chunk in resp.iter_bytes(chunk_size=4096):
                if first_chunk is None:
                    first_chunk = time.time() - start
        total = time.time() - start
        total_times.append(total)
        first_chunk_times.append(first_chunk)
    return total_times, first_chunk_times


def avg(lst):
    return sum(lst) / len(lst)


def print_results(label, baseline_times, stream_total, stream_first):
    b = avg(baseline_times)
    st = avg(stream_total)
    sf = avg(stream_first)

    print(f"\n{'='*55}")
    print(f"  {label} ({RUNS} прогонів)")
    print(f"{'='*55}")
    print(f"  {'Прогін':<10} {'Базовий':>10} {'Стрім total':>12} {'Стрім 1й чанк':>14}")
    print(f"  {'-'*10} {'-'*10} {'-'*12} {'-'*14}")
    for i in range(RUNS):
        print(f"  {i+1:<10} {baseline_times[i]:>9.3f}с {stream_total[i]:>11.3f}с {stream_first[i]:>13.3f}с")
    print(f"  {'-'*10} {'-'*10} {'-'*12} {'-'*14}")
    print(f"  {'Середнє':<10} {b:>9.3f}с {st:>11.3f}с {sf:>13.3f}с")

    print(f"\n  ВИСНОВКИ:")
    print(f"  Загальний час:  базовий {b:.3f}с  vs  стрімінг {st:.3f}с  → різниця {abs(b-st)/b*100:.0f}%")
    if st < b:
        print(f"  Стрімінг швидший у загальному часі: x{b/st:.1f}")
    else:
        print(f"  Стрімінг НЕ швидший у загальному часі (x{b/st:.1f})")
    print(f"  Перший звук:    базовий {b:.3f}с  vs  стрімінг {sf:.3f}с  → x{b/sf:.1f} швидше")
    print(f"  Користувач чує звук на {(b - sf)*1000:.0f} мс раніше")


async def main():
    print("=" * 55)
    print("  ПЕРЕВІРКА: ЧИ СТРІМІНГ РЕАЛЬНО ШВИДШИЙ?")
    print(f"  Текст: {len(TEXT)} символів")
    print(f"  Прогонів: {RUNS}")
    print("=" * 55)

    # Edge TTS
    print("\n  Тестую Edge TTS базовий...")
    edge_base = await edge_baseline()
    print("  Тестую Edge TTS стрімінг...")
    edge_str_total, edge_str_first = await edge_streaming()
    print_results("EDGE TTS", edge_base, edge_str_total, edge_str_first)

    # OpenAI TTS
    print("\n  Тестую OpenAI TTS базовий...")
    openai_base = openai_baseline()
    print("  Тестую OpenAI TTS стрімінг...")
    openai_str_total, openai_str_first = openai_streaming()
    print_results("OPENAI TTS", openai_base, openai_str_total, openai_str_first)

    # Фінал
    print(f"\n{'='*55}")
    print(f"  ЗАГАЛЬНИЙ ВЕРДИКТ")
    print(f"{'='*55}")
    eb = avg(edge_base)
    esf = avg(edge_str_first)
    ob = avg(openai_base)
    osf = avg(openai_str_first)
    print(f"  Edge TTS:   перший звук x{eb/esf:.1f} швидше зі стрімінгом")
    print(f"  OpenAI TTS: перший звук x{ob/osf:.1f} швидше зі стрімінгом")
    print(f"\n  Стрімінг не прискорює ГЕНЕРАЦІЮ на сервері.")
    print(f"  Він прискорює ОТРИМАННЯ першого звуку клієнтом.")
    print(f"  Для телефонії це = менша затримка відповіді.")


asyncio.run(main())

