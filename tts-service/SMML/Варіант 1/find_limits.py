import sys, io, time, wave, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
import azure.cognitiveservices.speech as speechsdk

AZURE_KEY = "YOUR_SECRET_TOKEN"
AZURE_REGION = "westeurope"

TEXT = "Добрий день! Дякуємо що зателефонували. Чим можу допомогти?"

def wrap_pcm_to_wav(pcm_data, sample_rate=8000):
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_data)
    return buf.getvalue()

def make_ssml(rate, pitch, volume):
    return f"""<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='uk-UA'>
<voice name='uk-UA-PolinaNeural'>
    <prosody rate="{rate}" pitch="{pitch}" volume="{volume}">
        {TEXT}
    </prosody>
</voice></speak>"""

config = speechsdk.SpeechConfig(subscription=AZURE_KEY, region=AZURE_REGION)
config.speech_synthesis_voice_name = "uk-UA-PolinaNeural"
config.set_speech_synthesis_output_format(speechsdk.SpeechSynthesisOutputFormat.Raw8Khz16BitMonoPcm)
synth = speechsdk.SpeechSynthesizer(speech_config=config, audio_config=None)
conn = speechsdk.Connection.from_speech_synthesizer(synth)
conn.open(True)
time.sleep(0.3)
synth.speak_text_async("тест").get()

# ═══════════════════════════════════════
# Тест 1: Діапазон RATE
# ═══════════════════════════════════════
print(f"{'='*60}")
print(f"  ТЕСТ RATE (швидкість)")
print(f"{'='*60}")

rates = ["50%", "60%", "70%", "80%", "90%", "100%", "110%", "120%", "130%", "150%"]
for rate in rates:
    ssml = make_ssml(rate, "+0st", "medium")
    result = synth.speak_ssml_async(ssml).get()
    if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
        wav = wrap_pcm_to_wav(result.audio_data)
        fname = f"rate_{rate}.wav"
        with open(fname, "wb") as f:
            f.write(wav)
        print(f"  rate={rate:<6} OK  | {len(wav)}б | {fname}")
    else:
        print(f"  rate={rate:<6} ПОМИЛКА")

# ═══════════════════════════════════════
# Тест 2: Діапазон PITCH
# ═══════════════════════════════════════
print(f"\n{'='*60}")
print(f"  ТЕСТ PITCH (висота)")
print(f"{'='*60}")

pitches = ["-6st", "-4st", "-3st", "-2st", "-1st", "+0st", "+1st", "+2st", "+3st", "+4st", "+6st"]
for pitch in pitches:
    ssml = make_ssml("100%", pitch, "medium")
    result = synth.speak_ssml_async(ssml).get()
    if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
        wav = wrap_pcm_to_wav(result.audio_data)
        fname = f"pitch_{pitch.replace('+','p').replace('-','m')}.wav"
        with open(fname, "wb") as f:
            f.write(wav)
        print(f"  pitch={pitch:<6} OK  | {len(wav)}б | {fname}")
    else:
        print(f"  pitch={pitch:<6} ПОМИЛКА")

# ═══════════════════════════════════════
# Тест 3: Діапазон VOLUME
# ═══════════════════════════════════════
print(f"\n{'='*60}")
print(f"  ТЕСТ VOLUME (гучність)")
print(f"{'='*60}")

volumes = ["x-soft", "soft", "medium", "loud", "x-loud", "+0dB", "+3dB", "+6dB"]
for vol in volumes:
    ssml = make_ssml("100%", "+0st", vol)
    result = synth.speak_ssml_async(ssml).get()
    if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
        wav = wrap_pcm_to_wav(result.audio_data)
        fname = f"vol_{vol.replace('+','p').replace('-','m')}.wav"
        with open(fname, "wb") as f:
            f.write(wav)
        print(f"  volume={vol:<8} OK  | {len(wav)}б | {fname}")
    else:
        print(f"  volume={vol:<8} ПОМИЛКА")

# ═══════════════════════════════════════
# Тест 4: КОМБІНОВАНІ емоції (в робочому діапазоні)
# ═══════════════════════════════════════
print(f"\n{'='*60}")
print(f"  КОМБІНОВАНІ ЕМОЦІЇ")
print(f"{'='*60}")

EMOTION_TESTS = [
    ("emo_normal", "100%", "+0st", "medium"),
    ("emo_happy", "110%", "+3st", "loud"),
    ("emo_sad", "80%", "-3st", "soft"),
    ("emo_urgent", "120%", "+2st", "x-loud"),
    ("emo_calm", "85%", "-1st", "soft"),
    ("emo_warm", "95%", "+2st", "medium"),
]

for name, rate, pitch, vol in EMOTION_TESTS:
    ssml = make_ssml(rate, pitch, vol)
    result = synth.speak_ssml_async(ssml).get()
    if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
        wav = wrap_pcm_to_wav(result.audio_data)
        fname = f"{name}.wav"
        with open(fname, "wb") as f:
            f.write(wav)
        print(f"  {name:<15} rate={rate:<5} pitch={pitch:<5} vol={vol:<8} | {len(wav)}б | {fname}")
    else:
        print(f"  {name:<15} ПОМИЛКА")

del synth

print(f"\n  Послухайте emo_* файли — чи чутна різниця?")
print(f"  Якщо ні — Polina ігнорує prosody для української.")

