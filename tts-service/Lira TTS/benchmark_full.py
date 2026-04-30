#!/usr/bin/env python3
"""
Повний бенчмарк TTS HTTP Server — Chirp3-HD
Збирає дані для звіту: час генерації, голоси, довжини, паралельність.
Результати: benchmark_results.json
"""

import sys, io, os, json, time, urllib.request, wave, asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

SERVER = "http://localhost:8765"
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "benchmark_output")
RESULTS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "benchmark_results.json")
os.makedirs(OUTPUT_DIR, exist_ok=True)

ALL_RESULTS = {
    "timestamp": datetime.now().isoformat(),
    "server": SERVER,
    "model": "Chirp3-HD (uk-UA)",
    "format": "WAV 8kHz 16bit mono",
    "tests": {}
}


def post(path, data):
    body = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(
        f"{SERVER}{path}", data=body,
        headers={"Content-Type": "application/json; charset=utf-8"},
    )
    resp = urllib.request.urlopen(req, timeout=60)
    return resp


def tts(sid, text, voice="Leda"):
    """Один TTS запит, повертає dict з результатами"""
    t0 = time.time()
    resp = post("/tts", {"session_id": sid, "text": text, "voice": voice})
    wav_data = resp.read()
    wall_ms = int((time.time() - t0) * 1000)

    h = resp.headers
    return {
        "text": text,
        "text_len": len(text),
        "voice": voice,
        "server_ms": int(h["X-TTS-Total-Ms"]),
        "gen_ms": int(h["X-TTS-Gen-Ms"]),
        "wall_ms": wall_ms,
        "parts": int(h["X-TTS-Parts"]),
        "cps": int(h["X-TTS-CPS"]),
        "audio_sec": float(h["X-TTS-Audio-Sec"]),
        "wav_bytes": len(wav_data),
    }


def start_session(call_id="bench"):
    resp = post("/start", {"call_id": call_id})
    return json.loads(resp.read())["session_id"]


def stop_session(sid):
    post("/stop", {"session_id": sid})


def run_n_times(sid, text, voice, n=3):
    """Запустити n разів, повернути всі + найкращий результат"""
    results = []
    for _ in range(n):
        r = tts(sid, text, voice)
        results.append(r)
        time.sleep(0.3)
    best = min(results, key=lambda x: x["server_ms"])
    avg = int(sum(r["server_ms"] for r in results) / len(results))
    best["avg_ms"] = avg
    best["runs"] = n
    return best, results


# ============================================================
# ТЕСТ 1: Довжина тексту → час генерації
# ============================================================
def test_text_length(sid):
    print("\n" + "═" * 70)
    print("  ТЕСТ 1: Залежність часу від довжини тексту")
    print("═" * 70)

    texts = [
        ("10 сим", "Привіт вам."),
        ("20 сим", "Дякуємо за дзвінок."),
        ("40 сим", "Дякуємо за дзвінок до компанії Окі-Токі."),
        ("60 сим", "Будь ласка, залишайтесь на лінії, оператор скоро відповість."),
        ("80 сим", "Дякуємо за дзвінок до компанії Окі-Токі, усі оператори зараз зайняті обслуговуванням."),
        ("100 сим", "Дякуємо за дзвінок до компанії Окі-Токі. На жаль, усі оператори зараз зайняті. Будь ласка, зачекайте."),
        ("130 сим", "Натисніть один для з'єднання з оператором. Натисніть два для зворотного дзвінка. Натисніть нуль для повторного прослуховування."),
        ("170 сим", "Вітаємо вас у компанії Окі-Токі. Ваш дзвінок дуже важливий для нас. Зараз усі оператори зайняті. Будь ласка, залишайтесь на лінії або натисніть один для зворотного дзвінка."),
        ("250 сим", "Вітаємо вас у компанії Окі-Токі. Ваш дзвінок дуже важливий для нас. Зараз усі оператори зайняті обслуговуванням інших клієнтів. Будь ласка, залишайтесь на лінії. Орієнтовний час очікування складає дві хвилини. Натисніть один для зворотного дзвінка."),
    ]

    results = []
    print(f"\n  {'Назва':<12} {'Символів':>10} {'Частин':>8} {'Сервер мс':>10} {'Середн мс':>10} {'CPS':>6} {'Аудіо':>8}")
    print(f"  {'─'*12} {'─'*10} {'─'*8} {'─'*10} {'─'*10} {'─'*6} {'─'*8}")

    for name, text in texts:
        best, _ = run_n_times(sid, text, "Leda", n=3)
        results.append(best)
        print(f"  {name:<12} {best['text_len']:>10} {best['parts']:>8} {best['server_ms']:>9}мс {best['avg_ms']:>9}мс {best['cps']:>6} {best['audio_sec']:>6.1f}с")

    ALL_RESULTS["tests"]["text_length"] = results
    return results


# ============================================================
# ТЕСТ 2: Кількість речень → час генерації
# ============================================================
def test_sentence_count(sid):
    print("\n" + "═" * 70)
    print("  ТЕСТ 2: Кількість речень (паралельна розбивка)")
    print("═" * 70)

    base_sentences = [
        "Дякуємо за дзвінок до компанії Окі-Токі.",
        "На жаль, усі оператори зараз зайняті.",
        "Залишайтесь на лінії.",
        "Ваш дзвінок дуже важливий для нас.",
        "Натисніть один для зворотного дзвінка.",
        "Орієнтовний час очікування дві хвилини.",
        "Дякуємо за ваше терпіння.",
    ]

    results = []
    print(f"\n  {'Речень':>8} {'Символів':>10} {'Частин':>8} {'Сервер мс':>10} {'Середн мс':>10} {'CPS':>6}")
    print(f"  {'─'*8} {'─'*10} {'─'*8} {'─'*10} {'─'*10} {'─'*6}")

    for n in [1, 2, 3, 4, 5, 6, 7]:
        text = " ".join(base_sentences[:n])
        best, _ = run_n_times(sid, text, "Leda", n=3)
        results.append({"sentences": n, **best})
        print(f"  {n:>8} {best['text_len']:>10} {best['parts']:>8} {best['server_ms']:>9}мс {best['avg_ms']:>9}мс {best['cps']:>6}")

    ALL_RESULTS["tests"]["sentence_count"] = results
    return results


# ============================================================
# ТЕСТ 3: Порівняння голосів
# ============================================================
def test_voices(sid):
    print("\n" + "═" * 70)
    print("  ТЕСТ 3: Порівняння голосів (однаковий текст)")
    print("═" * 70)

    text = "Дякуємо за дзвінок до компанії Окі-Токі. Будь ласка, зачекайте."
    voices = ["Leda", "Puck", "Kore", "Aoede", "Charon", "Fenrir"]

    results = []
    print(f"\n  {'Голос':<10} {'Сервер мс':>10} {'Середн мс':>10} {'CPS':>6} {'Аудіо':>8} {'WAV':>12}")
    print(f"  {'─'*10} {'─'*10} {'─'*10} {'─'*6} {'─'*8} {'─'*12}")

    for voice in voices:
        best, _ = run_n_times(sid, text, voice, n=3)
        results.append(best)

        wav_path = os.path.join(OUTPUT_DIR, f"voice_{voice.lower()}.wav")
        # Зберігаємо останній WAV для прослуховування
        resp = post("/tts", {"session_id": sid, "text": text, "voice": voice})
        with open(wav_path, "wb") as f:
            f.write(resp.read())

        print(f"  {voice:<10} {best['server_ms']:>9}мс {best['avg_ms']:>9}мс {best['cps']:>6} {best['audio_sec']:>6.1f}с {best['wav_bytes']:>11,}B")

    ALL_RESULTS["tests"]["voices"] = results
    return results


# ============================================================
# ТЕСТ 4: Перший запит vs наступні (прогрів)
# ============================================================
def test_warmup():
    print("\n" + "═" * 70)
    print("  ТЕСТ 4: Перший запит vs наступні (прогрів ефект)")
    print("═" * 70)

    text = "Дякуємо за дзвінок."
    sid = start_session("bench-warmup")

    results = []
    print(f"\n  {'Запит #':>8} {'Сервер мс':>10}")
    print(f"  {'─'*8} {'─'*10}")

    for i in range(6):
        r = tts(sid, text, "Leda")
        results.append({"request_num": i + 1, **r})
        print(f"  {i+1:>8} {r['server_ms']:>9}мс{'  ← перший' if i == 0 else ''}")
        time.sleep(0.2)

    stop_session(sid)
    ALL_RESULTS["tests"]["warmup_effect"] = results
    return results


# ============================================================
# ТЕСТ 5: Одночасні дзвінки (конкурентність)
# ============================================================
def test_concurrent():
    print("\n" + "═" * 70)
    print("  ТЕСТ 5: Одночасні дзвінки (конкурентність)")
    print("═" * 70)

    text = "Дякуємо за дзвінок до компанії Окі-Токі."
    results = []

    for concurrent in [1, 2, 3, 5, 10]:
        sessions = [start_session(f"bench-c{i}") for i in range(concurrent)]

        def do_tts(sid):
            return tts(sid, text, "Leda")

        t0 = time.time()
        with ThreadPoolExecutor(max_workers=concurrent) as ex:
            futures = [ex.submit(do_tts, s) for s in sessions]
            call_results = [f.result() for f in futures]
        total_wall = int((time.time() - t0) * 1000)

        server_times = [r["server_ms"] for r in call_results]
        avg_server = int(sum(server_times) / len(server_times))
        max_server = max(server_times)

        for s in sessions:
            stop_session(s)

        results.append({
            "concurrent_calls": concurrent,
            "wall_ms": total_wall,
            "avg_server_ms": avg_server,
            "max_server_ms": max_server,
            "server_times": server_times,
        })
        print(f"  {concurrent:>3} дзвінків: wall={total_wall}мс | avg={avg_server}мс | max={max_server}мс | кожний: {server_times}")
        time.sleep(1)

    ALL_RESULTS["tests"]["concurrent"] = results
    return results


# ============================================================
# ТЕСТ 6: Реальні IVR сценарії
# ============================================================
def test_real_scenarios(sid):
    print("\n" + "═" * 70)
    print("  ТЕСТ 6: Реальні IVR сценарії")
    print("═" * 70)

    scenarios = [
        ("Коротке привітання", "Здрастуйте.", "Leda"),
        ("Привітання компанії", "Дякуємо за дзвінок до компанії Окі-Токі.", "Leda"),
        ("IVR з 3 пунктами", "Натисніть один для з'єднання з оператором. Натисніть два для зворотного дзвінка. Натисніть нуль для повторного прослуховування.", "Leda"),
        ("Очікування", "Всі оператори зараз зайняті обслуговуванням інших клієнтів. Ваш дзвінок дуже важливий для нас. Будь ласка, залишайтесь на лінії.", "Puck"),
        ("Переведення", "З'єдную вас з оператором. Одну мить, будь ласка.", "Leda"),
        ("Повна фраза IVR", "Вітаємо вас у компанії Окі-Токі. Ваш дзвінок дуже важливий для нас. Зараз усі оператори зайняті. Будь ласка, залишайтесь на лінії або натисніть один для зворотного дзвінка.", "Leda"),
        ("Номер у черзі", "Ви третій у черзі. Орієнтовний час очікування — одна хвилина.", "Kore"),
        ("Неробочий час", "Дякуємо за дзвінок. На жаль, зараз неробочий час. Наш графік роботи: з понеділка по п'ятницю, з дев'ятої до вісімнадцятої години. Будь ласка, передзвоніть у робочий час або залиште повідомлення після сигналу.", "Leda"),
    ]

    results = []
    print(f"\n  {'Сценарій':<25} {'Сим':>5} {'Ч-н':>4} {'Сервер':>8} {'CPS':>5} {'Аудіо':>7} {'Голос':<8}")
    print(f"  {'─'*25} {'─'*5} {'─'*4} {'─'*8} {'─'*5} {'─'*7} {'─'*8}")

    for name, text, voice in scenarios:
        best, _ = run_n_times(sid, text, voice, n=3)
        best["scenario"] = name
        results.append(best)

        wav_path = os.path.join(OUTPUT_DIR, f"scenario_{name.lower().replace(' ', '_')}.wav")
        resp = post("/tts", {"session_id": sid, "text": text, "voice": voice})
        with open(wav_path, "wb") as f:
            f.write(resp.read())

        print(f"  {name:<25} {best['text_len']:>5} {best['parts']:>4} {best['server_ms']:>6}мс {best['cps']:>5} {best['audio_sec']:>5.1f}с {voice:<8}")

    ALL_RESULTS["tests"]["real_scenarios"] = results
    return results


# ============================================================
# ТЕСТ 7: Стабільність (10 однакових запитів)
# ============================================================
def test_stability(sid):
    print("\n" + "═" * 70)
    print("  ТЕСТ 7: Стабільність (10 однакових запитів)")
    print("═" * 70)

    text = "Дякуємо за дзвінок до компанії Окі-Токі. Будь ласка, зачекайте."
    results = []

    print(f"\n  {'#':>4} {'Сервер мс':>10} {'Генерація мс':>12} {'CPS':>6}")
    print(f"  {'─'*4} {'─'*10} {'─'*12} {'─'*6}")

    for i in range(10):
        r = tts(sid, text, "Leda")
        results.append(r)
        print(f"  {i+1:>4} {r['server_ms']:>9}мс {r['gen_ms']:>11}мс {r['cps']:>6}")
        time.sleep(0.5)

    times = [r["server_ms"] for r in results]
    print(f"\n  min={min(times)}мс  max={max(times)}мс  avg={int(sum(times)/len(times))}мс  spread={max(times)-min(times)}мс")

    ALL_RESULTS["tests"]["stability"] = {
        "results": results,
        "min_ms": min(times),
        "max_ms": max(times),
        "avg_ms": int(sum(times) / len(times)),
        "spread_ms": max(times) - min(times),
    }
    return results


# ============================================================
# MAIN
# ============================================================
def main():
    print("═" * 70)
    print("  ПОВНИЙ БЕНЧМАРК TTS HTTP SERVER — Chirp3-HD")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("═" * 70)

    sid = start_session("benchmark")

    test_text_length(sid)
    test_sentence_count(sid)
    test_voices(sid)
    test_warmup()
    test_concurrent()
    test_real_scenarios(sid)
    test_stability(sid)

    stop_session(sid)

    # Зберігаємо результати
    with open(RESULTS_FILE, "w", encoding="utf-8") as f:
        json.dump(ALL_RESULTS, f, ensure_ascii=False, indent=2)

    print("\n" + "═" * 70)
    print(f"  ГОТОВО! Результати збережено: {RESULTS_FILE}")
    print(f"  WAV файли: {OUTPUT_DIR}")
    print("═" * 70)


if __name__ == "__main__":
    main()
