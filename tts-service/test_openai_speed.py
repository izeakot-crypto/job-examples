import sys, io, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from openai import OpenAI

client = OpenAI(api_key='YOUR_OPENAI_API_KEY')

text = "Привіт, я робот Василий, я прийшов тобі на допомогу!Привіт, я робот Василий, я прийшов тобі на допомогу!"

for i in range(3):
    start = time.time()
    response = client.audio.speech.create(
        model="tts-1",
        voice="nova",
        input=text,
    )
    content = response.read()
    elapsed = time.time() - start
    filename = f"test_openai_{i+1}.mp3"
    with open(filename, "wb") as f:
        f.write(content)
    size = len(content)
    print(f"OpenAI Тест {i+1}: {elapsed:.2f} сек | Розмір: {size} байт")

print("Готово")

