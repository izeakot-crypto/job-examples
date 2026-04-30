import sys, io, time, asyncio
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
import edge_tts

TEXT = "Привіт! Я Ілля, я ваш віртуальний робот помічник. Чим вам допомогти?"
VOICE_P = "uk-UA-PolinaNeural"
VOICE_O = "uk-UA-OstapNeural"

async def gen(text, voice, rate="+0%"):
    comm = edge_tts.Communicate(text, voice, rate=rate)
    start = time.time()
    audio = b""
    async for chunk in comm.stream():
        if chunk["type"] == "audio":
            audio += chunk["data"]
    return audio, time.time() - start

async def gen_save(text, voice, rate="+0%", fname="tmp.mp3"):
    comm = edge_tts.Communicate(text, voice, rate=rate)
    start = time.time()
    await comm.save(fname)
    return time.time() - start

async def main():
    print(f'Текст: "{TEXT}" ({len(TEXT)} символів)\n')

    tests = []

    # 1. Базовий stream — Поліна
    audio, t = await gen(TEXT, VOICE_P)
    with open("efast_1.mp3", "wb") as f: f.write(audio)
    tests.append(("1. Поліна stream() дефолт", t, len(audio), "efast_1.mp3"))

    # 2. Базовий save — Поліна
    t = await gen_save(TEXT, VOICE_P, fname="efast_2.mp3")
    tests.append(("2. Поліна save() дефолт", t, 0, "efast_2.mp3"))

    # 3. Rate +15%
    audio, t = await gen(TEXT, VOICE_P, rate="+15%")
    with open("efast_3.mp3", "wb") as f: f.write(audio)
    tests.append(("3. Поліна stream() rate=+15%", t, len(audio), "efast_3.mp3"))

    # 4. Rate +30%
    audio, t = await gen(TEXT, VOICE_P, rate="+30%")
    with open("efast_4.mp3", "wb") as f: f.write(audio)
    tests.append(("4. Поліна stream() rate=+30%", t, len(audio), "efast_4.mp3"))

    # 5. Остап stream
    audio, t = await gen(TEXT, VOICE_O)
    with open("efast_5.mp3", "wb") as f: f.write(audio)
    tests.append(("5. Остап stream() дефолт", t, len(audio), "efast_5.mp3"))

    # 6. Остап rate +15%
    audio, t = await gen(TEXT, VOICE_O, rate="+15%")
    with open("efast_6.mp3", "wb") as f: f.write(audio)
    tests.append(("6. Остап stream() rate=+15%", t, len(audio), "efast_6.mp3"))

    # 7. Прогрів: генеруємо коротке слово, потім реальний текст
    await gen("тест", VOICE_P)  # прогрів DNS + TLS
    audio, t = await gen(TEXT, VOICE_P)
    with open("efast_7.mp3", "wb") as f: f.write(audio)
    tests.append(("7. Поліна stream() після прогріву", t, len(audio), "efast_7.mp3"))

    # 8. Прогрів + rate +15%
    await gen("тест", VOICE_P, rate="+15%")
    audio, t = await gen(TEXT, VOICE_P, rate="+15%")
    with open("efast_8.mp3", "wb") as f: f.write(audio)
    tests.append(("8. Поліна stream() прогрів + rate=+15%", t, len(audio), "efast_8.mp3"))

    # Вивід
    print(f"  {'Тест':<45} {'Час':>7} {'Розмір':>8}  Файл")
    print(f"  {'─'*45} {'─'*7} {'─'*8}  {'─'*15}")
    for desc, t, size, fname in tests:
        sz = f"{size}б" if size else "—"
        print(f"  {desc:<45} {t:.3f}с {sz:>8}  {fname}")

    best = min(tests, key=lambda x: x[1])
    print(f"\n  >>> Найшвидший: {best[0]} — {best[1]:.3f}с")

asyncio.run(main())
