import sys, io, time, wave
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from elevenlabs import ElevenLabs

ELEVENLABS_KEY = "sk_YOUR_AZURE_KEY6f5e39e76d233f3a"
TEXT = "Шановний клієнте, дякуємо що зателефонували до служби підтримки компанії Окі-Токі. Чим можу вам допомогти? Зачекайте, зʼєдную вас з оператором."

client = ElevenLabs(api_key=ELEVENLABS_KEY)

print(f'Текст: "{TEXT}" ({len(TEXT)} символів)')
print(f"Голос: Sarah | Модель: eleven_multilingual_v2")
print(f"Формат: pcm_22050 (RAW PCM) -> конвертація в WAV 8kHz 16bit mono\n")

# ── Звичайна генерація (MP3) ──
print(f"{'='*60}")
print(f"  1. Звичайна генерація (MP3)")
print(f"{'='*60}")
start = time.time()
audio_gen = client.text_to_speech.convert(
    text=TEXT,
    voice_id="EXAVITQu4vr4xnSDxMaL",
    model_id="eleven_multilingual_v2",
    output_format="mp3_44100_128",
)
audio_data = b""
for chunk in audio_gen:
    audio_data += chunk
t_normal = time.time() - start
fname = f"{len(TEXT)}sym_11labs_normal_{t_normal:.3f}s.mp3"
with open(fname, "wb") as f:
    f.write(audio_data)
print(f"  {t_normal:.3f}с | {len(audio_data)}б | {fname}")

# ── Стрімінг (PCM -> WAV 8kHz) ──
print(f"\n{'='*60}")
print(f"  2. Стрімінг (PCM 22050 -> WAV 8kHz 16bit mono)")
print(f"{'='*60}")

import struct

def downsample_pcm(pcm_data, from_rate=22050, to_rate=8000):
    """Проста конвертація PCM з 22050 в 8000 Hz"""
    # PCM 16bit signed little-endian
    samples = struct.unpack(f'<{len(pcm_data)//2}h', pcm_data)
    ratio = from_rate / to_rate
    new_len = int(len(samples) / ratio)
    resampled = []
    for i in range(new_len):
        idx = int(i * ratio)
        if idx < len(samples):
            resampled.append(samples[idx])
    return struct.pack(f'<{len(resampled)}h', *resampled)

def wrap_pcm_to_wav(pcm_data, sample_rate=8000):
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_data)
    return buf.getvalue()

start = time.time()
t_first = None
audio_pcm = b""

audio_stream = client.text_to_speech.convert(
    text=TEXT,
    voice_id="EXAVITQu4vr4xnSDxMaL",
    model_id="eleven_multilingual_v2",
    output_format="pcm_22050",
)
for chunk in audio_stream:
    if t_first is None:
        t_first = time.time() - start
    audio_pcm += chunk

t_stream = time.time() - start

# Конвертація в 8kHz
pcm_8khz = downsample_pcm(audio_pcm, 22050, 8000)
wav_data = wrap_pcm_to_wav(pcm_8khz, 8000)
t_total = time.time() - start

fname = f"{len(TEXT)}sym_11labs_stream_8khz_{t_total:.3f}s.wav"
with open(fname, "wb") as f:
    f.write(wav_data)
print(f"  Генерація:    {t_stream:.3f}с")
print(f"  1й чанк:      {t_first:.3f}с")
print(f"  + конвертація: {t_total:.3f}с")
print(f"  Файл: {fname}")

# ── Стрімінг ulaw_8000 (якщо підтримується) ──
print(f"\n{'='*60}")
print(f"  3. Стрімінг ulaw_8000 (нативний 8kHz)")
print(f"{'='*60}")

try:
    start = time.time()
    t_first3 = None
    audio_ulaw = b""

    audio_stream3 = client.text_to_speech.convert(
        text=TEXT,
        voice_id="EXAVITQu4vr4xnSDxMaL",
        model_id="eleven_multilingual_v2",
        output_format="ulaw_8000",
    )
    for chunk in audio_stream3:
        if t_first3 is None:
            t_first3 = time.time() - start
        audio_ulaw += chunk

    t_ulaw = time.time() - start
    fname = f"{len(TEXT)}sym_11labs_ulaw8k_{t_ulaw:.3f}s.raw"
    with open(fname, "wb") as f:
        f.write(audio_ulaw)
    print(f"  {t_ulaw:.3f}с | 1й чанк: {t_first3:.3f}с | {len(audio_ulaw)}б | {fname}")
    print(f"  (ulaw формат — стандарт телефонії, грається в Audacity/ffmpeg)")
except Exception as e:
    print(f"  ПОМИЛКА: {str(e)[:80]}")

print(f"\n{'='*60}")
print(f"  ПІДСУМОК")
print(f"{'='*60}")
print(f"  Звичайна (MP3):      {t_normal:.3f}с")
print(f"  Стрімінг (PCM->8kHz): {t_total:.3f}с (1й чанк {t_first:.3f}с)")

