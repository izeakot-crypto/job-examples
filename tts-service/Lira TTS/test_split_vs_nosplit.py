#!/usr/bin/env python3
"""
Тест: з розбивкою vs без розбивки на різних довжинах.
Всі тексти — одне речення (без крапок всередині) vs кілька речень тієї ж довжини.
Модель: Chirp3-HD, голос: Leda
"""

import sys, io, os, json, time, urllib.request
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

SERVER = "http://localhost:8765"
RESULTS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_split_vs_nosplit_results.json")


def post(path, data):
    body = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(
        f"{SERVER}{path}", data=body,
        headers={"Content-Type": "application/json; charset=utf-8"},
    )
    return urllib.request.urlopen(req, timeout=120)


def tts(sid, text, voice="Leda"):
    resp = post("/tts", {"session_id": sid, "text": text, "voice": voice})
    wav = resp.read()
    h = resp.headers
    return {
        "server_ms": int(h["X-TTS-Total-Ms"]),
        "gen_ms": int(h["X-TTS-Gen-Ms"]),
        "parts": int(h["X-TTS-Parts"]),
        "cps": int(h["X-TTS-CPS"]),
        "audio_sec": float(h["X-TTS-Audio-Sec"]),
        "wav_bytes": len(wav),
    }


def best_of_3(sid, text):
    results = []
    for attempt in range(3):
        try:
            r = tts(sid, text)
            results.append(r)
        except Exception as e:
            print(f"    [!] Спроба {attempt+1} помилка: {e}")
        time.sleep(0.5)
    if not results:
        return None, None
    best = min(results, key=lambda x: x["server_ms"])
    avg = int(sum(r["server_ms"] for r in results) / len(results))
    return best, avg


# Тексти: одне речення (без крапок) і кілька речень (з крапками) приблизно однакової довжини
tests = [
    {
        "target": "~10 сим",
        "single": "Привіт вам",
        "multi":  "Привіт вам",  # нема що розбивати
    },
    {
        "target": "~20 сим",
        "single": "Дякуємо за ваш дзвінок",
        "multi":  "Дякуємо. За ваш дзвінок.",
    },
    {
        "target": "~50 сим",
        "single": "Дякуємо за дзвінок до нашої компанії Окі-Токі сьогодні",
        "multi":  "Дякуємо за дзвінок. До нашої компанії. Окі-Токі сьогодні.",
    },
    {
        "target": "~100 сим",
        "single": "Дякуємо за дзвінок до компанії Окі-Токі, на жаль усі оператори зараз зайняті обслуговуванням інших клієнтів",
        "multi":  "Дякуємо за дзвінок до компанії Окі-Токі. На жаль усі оператори зараз зайняті. Обслуговуванням інших клієнтів.",
    },
    {
        "target": "~150 сим",
        "single": "Дякуємо за дзвінок до компанії Окі-Токі, на жаль усі оператори зараз зайняті обслуговуванням інших клієнтів, будь ласка залишайтесь на лінії і вам відповідять",
        "multi":  "Дякуємо за дзвінок до компанії Окі-Токі. На жаль усі оператори зараз зайняті. Обслуговуванням інших клієнтів. Будь ласка залишайтесь на лінії. І вам відповідять.",
    },
    {
        "target": "~300 сим",
        "single": "Дякуємо за дзвінок до компанії Окі-Токі, на жаль усі оператори зараз зайняті обслуговуванням інших клієнтів, будь ласка залишайтесь на лінії і вам обов'язково відповідять найближчим часом, ваш дзвінок дуже важливий для нас, орієнтовний час очікування складає приблизно дві хвилини",
        "multi":  "Дякуємо за дзвінок до компанії Окі-Токі. На жаль усі оператори зараз зайняті. Обслуговуванням інших клієнтів. Будь ласка залишайтесь на лінії. І вам обов'язково відповідять найближчим часом. Ваш дзвінок дуже важливий для нас. Орієнтовний час очікування складає приблизно дві хвилини.",
    },
    {
        "target": "~600 сим",
        "single": "Дякуємо за дзвінок до компанії Окі-Токі, на жаль усі оператори зараз зайняті обслуговуванням інших клієнтів, будь ласка залишайтесь на лінії і вам обов'язково відповідять найближчим часом, ваш дзвінок дуже важливий для нас, орієнтовний час очікування складає приблизно дві хвилини, якщо ви не бажаєте чекати натисніть один для зворотного дзвінка і наш оператор передзвонить вам протягом десяти хвилин, або натисніть два щоб залишити голосове повідомлення, також ви можете написати нам на електронну пошту або звернутися через наш веб сайт де є онлайн чат з підтримкою",
        "multi":  "Дякуємо за дзвінок до компанії Окі-Токі. На жаль усі оператори зараз зайняті. Обслуговуванням інших клієнтів. Будь ласка залишайтесь на лінії. І вам обов'язково відповідять найближчим часом. Ваш дзвінок дуже важливий для нас. Орієнтовний час очікування складає приблизно дві хвилини. Якщо ви не бажаєте чекати натисніть один для зворотного дзвінка. І наш оператор передзвонить вам протягом десяти хвилин. Або натисніть два щоб залишити голосове повідомлення. Також ви можете написати нам на електронну пошту. Або звернутися через наш веб сайт де є онлайн чат з підтримкою.",
    },
]

def main():
    print()
    print("=" * 90)
    print("  ТЕСТ: З розбивкою vs без розбивки | Модель: Chirp3-HD | Голос: Leda")
    print("=" * 90)

    resp = post("/start", {"call_id": "split-test"})
    sid = json.loads(resp.read())["session_id"]

    all_results = []

    print()
    print(f"  {'Довжина':<10} {'|':>2} {'БЕЗ розбивки':^30} {'|':>2} {'З розбивкою':^35} {'|':>2} {'Різниця':>8}")
    print(f"  {'':─<10} {'|':>2} {'Сим':>5} {'Ч-н':>4} {'Час мс':>8} {'Avg мс':>8} {'|':>2} {'Сим':>5} {'Ч-н':>4} {'Час мс':>8} {'Avg мс':>8} {'|':>2} {'':>8}")
    print(f"  {'─'*10} {'─':>2} {'─'*5} {'─'*4} {'─'*8} {'─'*8} {'─':>2} {'─'*5} {'─'*4} {'─'*8} {'─'*8} {'─':>2} {'─'*8}")

    for t in tests:
        single_text = t["single"]
        multi_text = t["multi"]

        # Без розбивки (одне речення)
        s_best, s_avg = best_of_3(sid, single_text)

        # З розбивкою (кілька речень)
        m_best, m_avg = best_of_3(sid, multi_text)

        if s_best is None and m_best is None:
            print(f"  {t['target']:<10} | ПОМИЛКА обох варіантів")
            continue
        elif s_best is None:
            print(f"  {t['target']:<10} | БЕЗ розбивки ПОМИЛКА | {len(multi_text):>5} {m_best['parts']:>4} {m_best['server_ms']:>6}мс {m_avg:>6}мс | single FAIL")
            diff = None
            diff_str = "FAIL"
        elif m_best is None:
            print(f"  {t['target']:<10} | {len(single_text):>5} {s_best['parts']:>4} {s_best['server_ms']:>6}мс {s_avg:>6}мс | З розбивкою ПОМИЛКА | multi FAIL")
            diff = None
            diff_str = "FAIL"
        else:
            diff = s_best["server_ms"] - m_best["server_ms"]
            diff_str = f"+{diff}" if diff > 0 else str(diff)
            print(f"  {t['target']:<10} | {len(single_text):>5} {s_best['parts']:>4} {s_best['server_ms']:>6}мс {s_avg:>6}мс | {len(multi_text):>5} {m_best['parts']:>4} {m_best['server_ms']:>6}мс {m_avg:>6}мс | {diff_str:>6}мс")

        all_results.append({
            "target": t["target"],
            "single": {
                "text": single_text,
                "text_len": len(single_text),
                **(s_best if s_best else {"error": "timeout/500"}),
                "avg_ms": s_avg,
            },
            "multi": {
                "text": multi_text,
                "text_len": len(multi_text),
                **(m_best if m_best else {"error": "timeout/500"}),
                "avg_ms": m_avg,
            },
            "diff_ms": diff,
        })

    post("/stop", {"session_id": sid})

    # Зберігаємо
    with open(RESULTS_FILE, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)

    print()
    print(f"  Різниця > 0 = без розбивки повільніше")
    print(f"  Результати: {RESULTS_FILE}")
    print("=" * 90)


if __name__ == "__main__":
    main()
