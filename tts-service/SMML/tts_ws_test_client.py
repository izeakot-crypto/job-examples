#!/usr/bin/env python3
"""
Тестовий WebSocket клієнт для перевірки TTS сервера.
Запуск: python tts_ws_test_client.py

Підключається до ws://localhost:8765, відправляє текст,
отримує WAV чанки, зберігає на диск.
"""

import sys, io, os, json, time, asyncio
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import websockets

SERVER_URL = "ws://localhost:8765"
OUTPUT_DIR = os.path.join(os.path.expanduser("~"), "Desktop", "tts_ws_test")

async def test_tts(text, voice="Leda", request_id=None):
    """Один тестовий запит"""
    if request_id is None:
        request_id = str(int(time.time() * 1000))

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print(f"\n{'='*60}")
    print(f"Текст ({len(text)} сим): {text[:80]}...")
    print(f"Голос: {voice}")
    print(f"{'='*60}")

    t_start = time.time()

    async with websockets.connect(SERVER_URL) as ws:
        # Надсилаємо запит
        request = json.dumps({
            "text": text,
            "voice": voice,
            "request_id": request_id,
        })
        await ws.send(request)

        chunks = []
        done = False

        while not done:
            msg = await asyncio.wait_for(ws.recv(), timeout=30)

            if isinstance(msg, str):
                data = json.loads(msg)

                if data.get("type") == "audio_chunk":
                    part = data["part"]
                    total = data["total_parts"]
                    gen_ms = data["gen_time_ms"]
                    print(f"  Chunk {part}/{total}: генерація {gen_ms}мс, чекаю WAV...")

                elif data.get("type") == "done":
                    total_ms = data["total_ms"]
                    parts = data["parts"]
                    print(f"\n  DONE: {total_ms}мс, {parts} частин")
                    done = True

                elif data.get("type") == "error":
                    print(f"  ERROR: {data.get('message')}")
                    done = True

            elif isinstance(msg, bytes):
                # Binary WAV data
                chunks.append(msg)
                filename = f"chunk_{request_id}_{len(chunks)}.wav"
                filepath = os.path.join(OUTPUT_DIR, filename)
                with open(filepath, 'wb') as f:
                    f.write(msg)
                print(f"  WAV збережено: {filename} ({len(msg)} bytes)")

    elapsed = time.time() - t_start
    print(f"\n  Загальний час (з мережею): {elapsed:.3f}с")
    print(f"  CPS: {int(len(text) / elapsed)}")
    print(f"  Файли у: {OUTPUT_DIR}")

    return chunks


async def main():
    print("TTS WebSocket Test Client")
    print(f"Сервер: {SERVER_URL}\n")

    # Тест 1: Коротке речення
    await test_tts(
        "Дякуємо за дзвінок.",
        voice="Leda",
    )

    # Тест 2: Стандартний текст (привітання колл-центру)
    await test_tts(
        "Дякуємо за дзвінок до компанії Окі-Токі. На жаль, всі оператори зараз зайняті. Будь ласка, залишайтесь на лінії, вам відповідять найближчим часом.",
        voice="Leda",
    )

    # Тест 3: Довгий текст
    await test_tts(
        "Вітаємо вас у компанії Окі-Токі. Ваш дзвінок дуже важливий для нас. "
        "Зараз усі оператори зайняті обслуговуванням інших клієнтів. "
        "Будь ласка, залишайтесь на лінії або натисніть один для зворотного дзвінка. "
        "Середній час очікування складає менше двох хвилин. Дякуємо за ваше терпіння.",
        voice="Puck",
    )

    # Тест 4: Різні голоси
    for v in ["Leda", "Puck", "Kore"]:
        await test_tts(
            "Здрастуйте! Ваше замовлення успішно оформлене.",
            voice=v,
        )

    print(f"\n\nВсі файли збережено у: {OUTPUT_DIR}")


if __name__ == "__main__":
    asyncio.run(main())
