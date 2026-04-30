import sys, io, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from openai import OpenAI
import azure.cognitiveservices.speech as speechsdk

TEXT = "Дякую за дзвінок! Зачекайте будь ласка, зʼєдную вас з оператором."
OPENAI_KEY = "YOUR_OPENAI_API_KEY"
AZURE_KEY = "YOUR_SECRET_TOKEN"
AZURE_REGION = "westeurope"

def calc_cps(text, elapsed):
    clean = ''.join(c for c in text if c.isalpha() or c.isspace())
    return len(clean) / elapsed if elapsed > 0 else 0

print(f'Текст: "{TEXT}" ({len(TEXT)} символів)')
print(f"Формат: найкращий для кожного провайдера\n")

# ═══════════════════════════════════════
# OpenAI TTS-1 HD
# ═══════════════════════════════════════
print(f"{'='*65}")
print(f"  OpenAI TTS-1 HD ($30/1M символів)")
print(f"{'='*65}")

client = OpenAI(api_key=OPENAI_KEY)

VOICES_OAI = ["nova", "alloy", "shimmer"]

for voice in VOICES_OAI:
    start = time.time()
    response = client.audio.speech.create(
        model="tts-1-hd",
        voice=voice,
        input=TEXT,
        response_format="mp3",
    )
    elapsed = time.time() - start
    fname = f"vs_openai_hd_{voice}.mp3"
    response.stream_to_file(fname)
    cps = calc_cps(TEXT, elapsed)
    print(f"  {voice:<10} | {elapsed:.3f}с | CPS: {cps:.0f} | {fname}")

# OpenAI TTS-1 (швидший, дешевший)
print(f"\n{'='*65}")
print(f"  OpenAI TTS-1 ($15/1M символів)")
print(f"{'='*65}")

for voice in VOICES_OAI:
    start = time.time()
    response = client.audio.speech.create(
        model="tts-1",
        voice=voice,
        input=TEXT,
        response_format="mp3",
    )
    elapsed = time.time() - start
    fname = f"vs_openai_1_{voice}.mp3"
    response.stream_to_file(fname)
    cps = calc_cps(TEXT, elapsed)
    print(f"  {voice:<10} | {elapsed:.3f}с | CPS: {cps:.0f} | {fname}")

# ═══════════════════════════════════════
# Azure Neural TTS ($16/1M символів S0)
# ═══════════════════════════════════════
print(f"\n{'='*65}")
print(f"  Azure Neural TTS ($16/1M символів S0)")
print(f"{'='*65}")

config = speechsdk.SpeechConfig(subscription=AZURE_KEY, region=AZURE_REGION)
config.set_speech_synthesis_output_format(
    speechsdk.SpeechSynthesisOutputFormat.Riff8Khz16BitMonoPcm
)

VOICES_AZ = [
    ("uk-UA-PolinaNeural", "Поліна"),
    ("uk-UA-OstapNeural", "Остап"),
]

for voice_id, voice_name in VOICES_AZ:
    config.speech_synthesis_voice_name = voice_id
    synth = speechsdk.SpeechSynthesizer(speech_config=config, audio_config=None)
    conn = speechsdk.Connection.from_speech_synthesizer(synth)
    conn.open(True)
    time.sleep(0.3)
    synth.speak_text_async("тест").get()

    # Звичайний
    start = time.time()
    result = synth.speak_text_async(TEXT).get()
    elapsed = time.time() - start
    if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
        fname = f"vs_azure_{voice_name}_8khz.wav"
        with open(fname, "wb") as f:
            f.write(result.audio_data)
        cps = calc_cps(TEXT, elapsed)
        print(f"  {voice_name:<10} 8kHz WAV   | {elapsed:.3f}с | CPS: {cps:.0f} | {fname}")

    # Стрімінг
    start = time.time()
    result = synth.start_speaking_text_async(TEXT).get()
    t_first = time.time() - start
    stream = speechsdk.AudioDataStream(result)
    audio = bytes()
    buf = bytes(3200)
    while True:
        filled = stream.read_data(buf)
        if filled == 0:
            break
        audio += buf[:filled]
    t_total = time.time() - start
    fname = f"vs_azure_{voice_name}_stream.wav"
    with open(fname, "wb") as f:
        f.write(audio)
    cps = calc_cps(TEXT, t_total)
    print(f"  {voice_name:<10} стрімінг   | {t_total:.3f}с (1й чанк {t_first:.3f}с) | CPS: {cps:.0f} | {fname}")

    del synth

# ═══════════════════════════════════════
# ПІДСУМОК
# ═══════════════════════════════════════
print(f"\n{'='*65}")
print(f"  ПІДСУМОК")
print(f"{'='*65}")
print(f"  OpenAI TTS-1 HD: якість #1, але повільніший, $30/1M")
print(f"  OpenAI TTS-1:    швидший, нижча якість, $15/1M")
print(f"  Azure Neural:    швидкий, нативний 8kHz, $16/1M (S0)")
print(f"  * OpenAI не підтримує 8kHz — тільки MP3/opus/wav 24kHz")
print(f"  * Azure віддає нативний WAV 8kHz одразу")

