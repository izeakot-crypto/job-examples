#!/usr/bin/env python3
"""
Імітація повного дзвінка: керівник шле curl запити з LIRA
Сценарій: Вхідний дзвінок → Вітання → IVR меню → Очікування → Переведення
"""

import sys, io, json, time, urllib.request, os, wave

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

SERVER = "http://localhost:8765"
WAV_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_output")
os.makedirs(WAV_DIR, exist_ok=True)


def post(path, data):
    body = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(
        f"{SERVER}{path}",
        data=body,
        headers={"Content-Type": "application/json; charset=utf-8"},
    )
    return urllib.request.urlopen(req, timeout=30)


def tts(sid, text, voice, wav_name):
    """Один TTS запит — як LIRA curl"""
    t0 = time.time()
    resp = post("/tts", {"session_id": sid, "text": text, "voice": voice})
    wav_data = resp.read()
    wall_ms = int((time.time() - t0) * 1000)

    h = resp.headers
    ms = h["X-TTS-Total-Ms"]
    parts = h["X-TTS-Parts"]
    audio = h["X-TTS-Audio-Sec"]
    cps = h["X-TTS-CPS"]

    wav_path = os.path.join(WAV_DIR, wav_name)
    with open(wav_path, "wb") as f:
        f.write(wav_data)

    print(f"  Відповідь ({wall_ms}мс):")
    print(f"    Генерація:  {ms}мс (сервер)")
    print(f"    Частин:     {parts} (паралельно)")
    print(f"    Аудіо:      {audio}с")
    print(f"    CPS:        {cps}")
    print(f"    WAV:        {len(wav_data):,} bytes → {wav_name}")
    return len(wav_data), float(audio)


def main():
    print()
    print("═" * 70)
    print("  ІМІТАЦІЯ ДЗВІНКА: Керівник шле curl запити з LIRA")
    print("  Сценарій: Вхідний дзвінок → Вітання → IVR → Очікування → Переведення")
    print("═" * 70)

    all_results = []

    # ── КРОК 1: Дзвінок почався — LIRA шле /start ──
    print()
    print("─" * 70)
    print("  КРОК 1: Дзвінок почався, LIRA шле POST /start")
    print('  curl -X POST http://SERVER:8765/start \\')
    print('       -H "Content-Type: application/json" \\')
    print('       -d \'{"call_id": "lira-call-7842"}\'')
    print()

    t0 = time.time()
    resp = post("/start", {"call_id": "lira-call-7842"})
    start = json.loads(resp.read())
    sid = start["session_id"]

    print(f"  Відповідь ({(time.time()-t0)*1000:.0f}мс):")
    print(f"    status:     {start['status']}")
    print(f"    session_id: {sid}")
    print(f"    startup_ms: {start['startup_ms']}мс")
    print(f"    voices:     {', '.join(start['voices'])}")
    print(f"    timeout:    {start['timeout_sec']}с")

    # ── КРОК 2: Вітання клієнта ──
    print()
    print("─" * 70)
    text2 = "Дякуємо за дзвінок до компанії Окі-Токі."
    print(f"  КРОК 2: Вітання клієнта")
    print(f'  curl -X POST http://SERVER:8765/tts \\')
    print(f'       -H "Content-Type: application/json" \\')
    print(f'       -d \'{{"session_id":"{sid}","text":"{text2}","voice":"Leda"}}\' \\')
    print(f"       -o greeting.wav")
    print()

    wav_sz, audio_sec = tts(sid, text2, "Leda", "call_greeting.wav")
    all_results.append(("Вітання", len(text2), wav_sz, audio_sec))
    print(f"    >> LIRA: play_file greeting.wav → клієнт чує вітання")

    # ── КРОК 3: IVR меню ──
    print()
    print("─" * 70)
    text3 = "Натисніть один для з'єднання з оператором. Натисніть два для зворотнього дзвінка. Натисніть нуль для повторного прослуховування."
    print(f"  КРОК 3: IVR меню")
    print(f'  curl -X POST http://SERVER:8765/tts \\')
    print(f'       -d \'{{"session_id":"{sid}","text":"{text3[:50]}...","voice":"Leda"}}\' \\')
    print(f"       -o ivr_menu.wav")
    print()

    wav_sz, audio_sec = tts(sid, text3, "Leda", "call_ivr_menu.wav")
    all_results.append(("IVR меню", len(text3), wav_sz, audio_sec))
    print(f"    >> Клієнт натиснув 1 — з'єднання з оператором")

    # ── КРОК 4: Очікування оператора ──
    print()
    print("─" * 70)
    text4 = "Всі оператори зараз зайняті. Ваш дзвінок дуже важливий для нас. Будь ласка, залишайтесь на лінії."
    print(f"  КРОК 4: Очікування оператора (голос Puck)")
    print(f'  curl -X POST http://SERVER:8765/tts \\')
    print(f'       -d \'{{"session_id":"{sid}","text":"{text4[:50]}...","voice":"Puck"}}\' \\')
    print(f"       -o hold.wav")
    print()

    wav_sz, audio_sec = tts(sid, text4, "Puck", "call_hold.wav")
    all_results.append(("Очікування", len(text4), wav_sz, audio_sec))
    print(f"    >> LIRA: play_file hold.wav → клієнт чекає")

    # ── КРОК 5: Переведення на оператора ──
    print()
    print("─" * 70)
    text5 = "З'єдную вас з оператором. Одну мить, будь ласка."
    print(f"  КРОК 5: Переведення на оператора")
    print(f'  curl -X POST http://SERVER:8765/tts \\')
    print(f'       -d \'{{"session_id":"{sid}","text":"{text5}","voice":"Leda"}}\' \\')
    print(f"       -o transfer.wav")
    print()

    wav_sz, audio_sec = tts(sid, text5, "Leda", "call_transfer.wav")
    all_results.append(("Переведення", len(text5), wav_sz, audio_sec))
    print(f"    >> LIRA: переводить дзвінок на оператора")

    # ── КРОК 6: Дзвінок завершився — /stop ──
    print()
    print("─" * 70)
    print(f"  КРОК 6: Дзвінок завершився, LIRA шле POST /stop")
    print(f'  curl -X POST http://SERVER:8765/stop \\')
    print(f'       -d \'{{"session_id":"{sid}"}}\'')
    print()

    t0 = time.time()
    resp = post("/stop", {"session_id": sid})
    stop = json.loads(resp.read())
    print(f"  Відповідь ({(time.time()-t0)*1000:.0f}мс): {stop}")

    # ── ПІДСУМОК ──
    print()
    print("═" * 70)
    print("  ПІДСУМОК ДЗВІНКА")
    print("═" * 70)
    print()
    print(f"  {'Крок':<15} {'Символів':>10} {'WAV bytes':>12} {'Аудіо':>8}")
    print(f"  {'─'*15} {'─'*10} {'─'*12} {'─'*8}")

    total_chars = 0
    total_wav = 0
    total_audio = 0

    for name, chars, wav_sz, audio_sec in all_results:
        print(f"  {name:<15} {chars:>10} {wav_sz:>12,} {audio_sec:>7.1f}с")
        total_chars += chars
        total_wav += wav_sz
        total_audio += audio_sec

    print(f"  {'─'*15} {'─'*10} {'─'*12} {'─'*8}")
    print(f"  {'ВСЬОГО':<15} {total_chars:>10} {total_wav:>12,} {total_audio:>7.1f}с")

    print()

    # Перевіряємо WAV файли
    print("  WAV файли (верифікація):")
    for fn in ["call_greeting.wav", "call_ivr_menu.wav", "call_hold.wav", "call_transfer.wav"]:
        fp = os.path.join(WAV_DIR, fn)
        with wave.open(fp, "rb") as wf:
            dur = wf.getnframes() / wf.getframerate()
            rate = wf.getframerate()
            ch = wf.getnchannels()
            bps = wf.getsampwidth() * 8
            print(f"    {fn:<25} {rate}Hz {bps}bit {ch}ch  {dur:.1f}с  {os.path.getsize(fp):,}B")

    print()
    print(f"  Сесія:        {sid}")
    print(f"  Запитів TTS:  {len(all_results)}")
    print(f"  Символів:     {total_chars}")
    print(f"  Аудіо:        {total_audio:.1f}с")
    print(f"  WAV дані:     {total_wav:,} bytes ({total_wav // 1024} KB)")
    print(f"  Лог:          tts_server.log")
    print("═" * 70)


if __name__ == "__main__":
    main()
