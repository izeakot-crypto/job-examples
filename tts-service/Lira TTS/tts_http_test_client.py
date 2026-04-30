#!/usr/bin/env python3
"""
Тестовий HTTP клієнт — імітує LIRA curl запити.
Послідовність: /start → /tts (кілька запитів) → /stop

Запуск: python tts_http_test_client.py
"""

import sys, io, os, json, time, urllib.request
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

SERVER_URL = "http://localhost:8765"
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_output")


def post(path, data=None):
    body = json.dumps(data or {}).encode('utf-8')
    req = urllib.request.Request(
        f"{SERVER_URL}{path}",
        data=body,
        headers={"Content-Type": "application/json; charset=utf-8"},
    )
    return urllib.request.urlopen(req, timeout=30)


def get(path):
    return urllib.request.urlopen(f"{SERVER_URL}{path}", timeout=5)


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("=" * 60)
    print("  TTS HTTP Test Client (імітація LIRA curl)")
    print(f"  Сервер: {SERVER_URL}")
    print("=" * 60)

    # ── 1. START SESSION ──
    print(f"\n{'─'*60}")
    print("  POST /start — створення сесії")
    t0 = time.time()
    resp = post("/start", {"call_id": "test-auto"})
    start_data = json.loads(resp.read())
    session_id = start_data["session_id"]
    print(f"  session_id:  {session_id}")
    print(f"  startup_ms:  {start_data['startup_ms']}мс")
    print(f"  voices:      {', '.join(start_data['voices'])}")

    # ── 2. TTS REQUESTS ──
    tests = [
        ("Дякуємо за дзвінок.", "Leda"),
        ("Дякуємо за дзвінок до компанії Окі-Токі. На жаль, всі оператори зараз зайняті. Будь ласка, залишайтесь на лінії.", "Leda"),
        ("Вітаємо вас у компанії Окі-Токі. Ваш дзвінок дуже важливий для нас. Зараз усі оператори зайняті. Будь ласка, залишайтесь на лінії або натисніть один для зворотного дзвінка.", "Puck"),
        ("Натисніть один для з'єднання з оператором. Натисніть два для зворотного дзвінка. Натисніть нуль для повторного прослуховування.", "Kore"),
    ]

    total_time = 0
    total_chars = 0

    for i, (text, voice) in enumerate(tests, 1):
        print(f"\n{'─'*60}")
        print(f"  POST /tts — запит #{i}")
        print(f"  Текст [{len(text)} сим]: {text[:70]}{'...' if len(text) > 70 else ''}")
        print(f"  Голос: {voice}")

        resp = post("/tts", {
            "session_id": session_id,
            "text": text,
            "voice": voice,
        })

        wav_data = resp.read()
        h = resp.headers

        total_ms = int(h["X-TTS-Total-Ms"])
        gen_ms = int(h["X-TTS-Gen-Ms"])
        parts = int(h["X-TTS-Parts"])
        cps = int(h["X-TTS-CPS"])
        audio_sec = float(h["X-TTS-Audio-Sec"])
        text_len = int(h["X-TTS-Text-Len"])

        total_time += total_ms
        total_chars += text_len

        # Зберігаємо WAV
        wav_path = os.path.join(OUTPUT_DIR, f"tts_{i}_{voice.lower()}.wav")
        with open(wav_path, 'wb') as f:
            f.write(wav_data)

        print(f"  Результат:")
        print(f"    Частин:      {parts} (паралельно)")
        print(f"    Генерація:   {gen_ms}мс")
        print(f"    ПОВНИЙ ЧАС:  {total_ms}мс")
        print(f"    CPS:         {cps}")
        print(f"    Аудіо:       {audio_sec}с")
        print(f"    WAV:         {len(wav_data):,} bytes → {wav_path}")

    # ── 3. STATUS ──
    print(f"\n{'─'*60}")
    print("  GET /status")
    resp = get("/status")
    status = json.loads(resp.read())
    s = status["sessions"].get(session_id, {})
    print(f"  Запитів:     {s.get('request_count', '?')}")
    print(f"  Символів:    {s.get('total_chars', '?')}")
    print(f"  Таймаут:     {s.get('timeout_in', '?')}с")

    # ── 4. STOP SESSION ──
    print(f"\n{'─'*60}")
    print("  POST /stop — закриття сесії")
    resp = post("/stop", {"session_id": session_id})
    print(f"  {json.loads(resp.read())}")

    # ── SUMMARY ──
    print(f"\n{'='*60}")
    print(f"  ПІДСУМОК")
    print(f"  Запитів:        {len(tests)}")
    print(f"  Символів:       {total_chars}")
    print(f"  Сумарний час:   {total_time}мс")
    print(f"  Середній час:   {total_time // len(tests)}мс")
    print(f"  WAV файли:      {OUTPUT_DIR}")
    print(f"  Лог сервера:    tts_server.log")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
