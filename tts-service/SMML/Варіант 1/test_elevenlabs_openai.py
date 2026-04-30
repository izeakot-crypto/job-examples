import sys, io, time, os, struct, wave
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = r"[USER_HOME]\Downloads\tts-488311-d5a1cbf88094.json"

ELEVENLABS_KEY = "sk_YOUR_AZURE_KEY6f5e39e76d233f3a"
OPENAI_KEY = "YOUR_OPENAI_API_KEY"

TEXT_UA = "Дякуємо за дзвінок до компанії Окі-Токі. На жаль, всі оператори зараз зайняті. Будь ласка, залишайтесь на лінії, вам відповідять найближчим часом."
TEXT_EN = "Thank you for calling Oki-Toki company. Unfortunately, all operators are currently busy. Please stay on the line, you will be answered shortly."
TEXT_RU = "Благодарим вас за звонок в компанию Оки-Токи. К сожалению, все операторы сейчас заняты. Пожалуйста, оставайтесь на линии, вам ответят в ближайшее время."

def wrap_pcm_to_wav(pcm_data, sample_rate=8000):
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_data)
    return buf.getvalue()

def downsample_pcm(pcm_data, from_rate, to_rate):
    samples = struct.unpack(f'<{len(pcm_data)//2}h', pcm_data)
    ratio = from_rate / to_rate
    new_len = int(len(samples) / ratio)
    resampled = [samples[int(i * ratio)] for i in range(new_len) if int(i * ratio) < len(samples)]
    return struct.pack(f'<{len(resampled)}h', *resampled)

print(f"{'='*70}")
print(f"  ElevenLabs + OpenAI TTS тест")
print(f"  Текст UA: {len(TEXT_UA)} символів")
print(f"{'='*70}\n")

# ═══════════════════════════════════════
# ElevenLabs
# ═══════════════════════════════════════
print("  ── ElevenLabs ──")

try:
    from elevenlabs import ElevenLabs

    el_client = ElevenLabs(api_key=ELEVENLABS_KEY)

    # Список голосів
    voices = el_client.voices.get_all()
    print(f"  Доступних голосів: {len(voices.voices)}")
    for v in voices.voices[:5]:
        print(f"    {v.name} ({v.voice_id})")

    # Тест UA
    for lang, text, label in [("UA", TEXT_UA, "українська"), ("EN", TEXT_EN, "англійська"), ("RU", TEXT_RU, "російська")]:
        start = time.time()
        audio_gen = el_client.text_to_speech.convert(
            voice_id="21m00Tcm4TlvDq8ikWAM",  # Rachel
            text=text,
            model_id="eleven_multilingual_v2",
            output_format="pcm_16000",
        )
        audio_data = b""
        for chunk in audio_gen:
            audio_data += chunk
        t = time.time() - start

        # Даунсемплінг 16kHz → 8kHz
        pcm_8k = downsample_pcm(audio_data, 16000, 8000)
        wav = wrap_pcm_to_wav(pcm_8k, 8000)

        cps = len(text) / t
        fname = f"elevenlabs_{lang}_{t:.3f}s.wav"
        with open(fname, "wb") as f:
            f.write(wav)
        print(f"  {lang} ({label}): {t:.3f}с | CPS: {cps:.1f} | {len(text)} симв | {fname}")

except Exception as e:
    print(f"  ElevenLabs ПОМИЛКА: {str(e)[:80]}")

# ═══════════════════════════════════════
# OpenAI TTS
# ═══════════════════════════════════════
print(f"\n  ── OpenAI TTS ──")

try:
    from openai import OpenAI

    oa_client = OpenAI(api_key=OPENAI_KEY)

    for model_name in ["tts-1", "tts-1-hd"]:
        print(f"\n  Модель: {model_name}")
        for lang, text, label in [("UA", TEXT_UA, "українська"), ("EN", TEXT_EN, "англійська"), ("RU", TEXT_RU, "російська")]:
            start = time.time()
            response = oa_client.audio.speech.create(
                model=model_name,
                voice="nova",
                input=text,
                response_format="pcm",
                speed=1.0,
            )
            audio_data = response.read()
            t = time.time() - start

            # OpenAI PCM = 24kHz 16bit mono
            pcm_8k = downsample_pcm(audio_data, 24000, 8000)
            wav = wrap_pcm_to_wav(pcm_8k, 8000)

            cps = len(text) / t
            fname = f"openai_{model_name}_{lang}_{t:.3f}s.wav"
            with open(fname, "wb") as f:
                f.write(wav)
            print(f"  {lang} ({label}): {t:.3f}с | CPS: {cps:.1f} | {len(text)} симв | {fname}")

except Exception as e:
    print(f"  OpenAI ПОМИЛКА: {str(e)[:80]}")

print(f"\n{'='*70}")
print(f"  Тест завершено!")
print(f"{'='*70}")



