#!/usr/bin/env python3
"""
Тестовий WebSocket клієнт — імітує LIRA.
Надсилає текст → отримує WAV → показує статистику.
"""

import sys, io, os, json, time, asyncio
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import websockets

SERVER_URL = "ws://localhost:8765"
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_output")


async def tts_request(text, voice="Leda"):
    """Один TTS запит — як це робитиме LIRA"""

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    request_id = str(int(time.time() * 1000))

    async with websockets.connect(SERVER_URL) as ws:
        await ws.send(json.dumps({
            "text": text,
            "voice": voice,
            "request_id": request_id,
        }))

        chunks_received = 0
        done_data = None

        while True:
            msg = await asyncio.wait_for(ws.recv(), timeout=30)

            if isinstance(msg, str):
                data = json.loads(msg)

                if data.get("type") == "audio_chunk":
                    pass

                elif data.get("type") == "done":
                    done_data = data
                    break

                elif data.get("type") == "error":
                    print(f"  ПОМИЛКА: {data.get('message')}")
                    return

            elif isinstance(msg, bytes):
                chunks_received += 1
                filepath = os.path.join(OUTPUT_DIR, f"chunk_{request_id}_{chunks_received}.wav")
                with open(filepath, 'wb') as f:
                    f.write(msg)

    if done_data:
        t = done_data["timing"]
        a = done_data["audio"]
        print(f"  Результат:")
        print(f"    Частин:        {done_data['parts']} (паралельно: {done_data['parallel']})")
        print(f"    Генерація:     {t['generation_ms']}мс")
        print(f"    Відправка WS:  {t['send_ms']}мс")
        print(f"    ПОВНИЙ ЧАС:    {t['total_ms']}мс")
        print(f"    CPS:           {done_data['cps']}")
        print(f"    Аудіо:         {a['total_duration_sec']}с")
        print(f"    Файли: {OUTPUT_DIR}")


async def main():
    print("=" * 60)
    print("  TTS WebSocket Test Client (імітація LIRA)")
    print(f"  Сервер: {SERVER_URL}")
    print("=" * 60)

    tests = [
        ("Дякуємо за дзвінок.", "Leda"),
        ("Дякуємо за дзвінок до компанії Окі-Токі. На жаль, всі оператори зараз зайняті. Будь ласка, залишайтесь на лінії.", "Leda"),
        ("Вітаємо вас у компанії Окі-Токі. Ваш дзвінок дуже важливий для нас. Зараз усі оператори зайняті. Будь ласка, залишайтесь на лінії або натисніть один для зворотного дзвінка.", "Puck"),
    ]

    for text, voice in tests:
        print(f"\n{'─'*60}")
        print(f"  Текст [{len(text)} сим]: {text[:70]}{'...' if len(text)>70 else ''}")
        print(f"  Голос: {voice}")
        await tts_request(text, voice)

    print(f"\n{'='*60}")
    print("  Готово! Детальний лог: tts_server.log")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
