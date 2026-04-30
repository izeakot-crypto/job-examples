# Edge TTS (Microsoft) — Гайд для розробника

## Що це?
Безкоштовний хмарний TTS від Microsoft. Працює через WebSocket — імітує браузер Edge.
**API-ключ не потрібен. Біллінг = 0.**


## Встановлення на сервері

```bash
pip install edge-tts
```

Перевірка:
```bash
edge-tts --text "Hello" --write-media test.mp3
# Якщо створився test.mp3 — працює
```

---

## Використання в Python

```python
import asyncio
import edge_tts

async def generate(text, voice, output_file):
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output_file)

asyncio.run(generate("Добрий день", "uk-UA-PolinaNeural", "output.mp3"))
```

### З параметрами швидкості/гучності
```python
communicate = edge_tts.Communicate(
    "Добрий день",
    "uk-UA-PolinaNeural",
    rate="-10%",       # швидкість: від -50% до +100%
    volume="+0%",      # гучність: від -50% до +50%
    pitch="+0Hz",      # тон: від -50Hz до +50Hz
)
await communicate.save("output.mp3")
```

---

## Голоси

| Мова | Код  | Жіночий               | Чоловічий              |
|------|------|------------------------|------------------------|
| UK   | uk   | uk-UA-PolinaNeural     | uk-UA-OstapNeural      |
| EN   | en   | en-US-AvaNeural        | en-US-AndrewNeural     |
| RU   | ru   | ru-RU-SvetlanaNeural   | ru-RU-DmitryNeural     |
| PL   | pl   | pl-PL-ZofiaNeural      | pl-PL-MarekNeural      |
| ES   | es   | es-ES-ElviraNeural     | es-ES-AlvaroNeural     |
| TR   | tr   | tr-TR-EmelNeural       | tr-TR-AhmetNeural      |

Отримати повний список голосів:
```bash
edge-tts --list-voices
```

---

## Формат аудіо

- Вихід: **MP3, 24kHz**
- Для телефонії потрібна конвертація в **WAV 8000Hz / 16bit / mono**

Конвертація через ffmpeg:
```bash
ffmpeg -i input.mp3 -ar 8000 -ac 1 -sample_fmt s16 output.wav
```

Або через Python (librosa):
```python
import librosa
import numpy as np
import wave

data, sr = librosa.load("input.mp3", sr=8000, mono=True)
data_int16 = np.clip(data * 32767, -32768, 32767).astype(np.int16)

with wave.open("output.wav", "wb") as wf:
    wf.setnchannels(1)
    wf.setsampwidth(2)
    wf.setframerate(8000)
    wf.writeframes(data_int16.tobytes())
```

---

## HTTP API (приклад для інтеграції з Lira)

```python
from flask import Flask, request, send_file
import edge_tts, asyncio, tempfile

app = Flask(__name__)

@app.route("/tts", methods=["POST"])
def tts():
    data = request.json
    text = data["text"]
    voice = data.get("voice", "uk-UA-PolinaNeural")

    tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
    tmp.close()
    asyncio.run(edge_tts.Communicate(text, voice).save(tmp.name))

    return send_file(tmp.name, mimetype="audio/mpeg")

app.run(host="0.0.0.0", port=5000)
```

Запит:
```bash
curl -X POST http://localhost:5000/tts \
     -H "Content-Type: application/json" \
     -d '{"text": "Добрий день", "voice": "uk-UA-PolinaNeural"}' \
     --output result.mp3
```

---

## Обмеження

- Максимум тексту на запит: ~5000 символів
- Потрібен інтернет (хмарний сервіс)
- Немає гарантії SLA (це неофіційний API)
- Немає клонування голосу
- Немає SSML (тільки rate/volume/pitch)

---

## Посилання

- GitHub: https://github.com/rany2/edge-tts
- PyPI: https://pypi.org/project/edge-tts/
- Аналог задачі: PROG-6513 (OpenAI TTS драйвер для Lira)
