import sys, io, time, asyncio
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import edge_tts

text = "Привіт, я робот Василий, я прийшов тобі на допомогу!Привіт, я робот Василий, я прийшов тобі на допомогу!"
voice = "uk-UA-PolinaNeural"

async def test():
    for i in range(3):
        filename = f"test_edge_{i+1}.mp3"
        start = time.time()
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(filename)
        elapsed = time.time() - start
        size = len(open(filename, "rb").read())
        print(f"Edge   Тест {i+1}: {elapsed:.2f} сек | Розмір: {size} байт")

    print("Готово")

asyncio.run(test())
