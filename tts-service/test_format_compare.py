import sys, io, time, asyncio
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
import edge_tts
import azure.cognitiveservices.speech as speechsdk

TEXT = "Привіт! Я Ілля, я ваш віртуальний робот помічник. Чим вам допомогти?"
VOICE = "uk-UA-PolinaNeural"

AZURE_KEY = "YOUR_SECRET_TOKEN"
AZURE_REGION = "westeurope"

FORMATS = [
    ("Audio24Khz48KBitRateMonoMp3",  "MP3 24kHz 48kbps (як Edge TTS)", ".mp3"),
    ("Audio24Khz96KBitRateMonoMp3",  "MP3 24kHz 96kbps (краща якість)", ".mp3"),
    ("Audio16Khz128KBitRateMonoMp3", "MP3 16kHz 128kbps", ".mp3"),
    ("Riff24Khz16BitMonoPcm",        "WAV 24kHz 16bit (найкраща якість)", ".wav"),
    ("Riff16Khz16BitMonoPcm",        "WAV 16kHz 16bit", ".wav"),
    ("Riff8Khz16BitMonoPcm",         "WAV 8kHz 16bit (телефонія — глухий)", ".wav"),
]

print(f'Текст: "{TEXT}"')
print(f"Голос: {VOICE}")
print(f"\n{'='*65}")
print(f"  Порівняння форматів: чому Azure звучить 'мертво'")
print(f"{'='*65}\n")

# 1. Edge TTS
async def gen_edge():
    comm = edge_tts.Communicate(TEXT, VOICE)
    start = time.time()
    await comm.save("fmt_0_edge_24khz.mp3")
    return time.time() - start

t = asyncio.run(gen_edge())
print(f"  0. Edge TTS (MP3 24kHz 48kbps)              | {t:.3f}с | fmt_0_edge_24khz.mp3")

# 2. Azure TTS — різні формати
for fmt_name, desc, ext in FORMATS:
    fmt_enum = getattr(speechsdk.SpeechSynthesisOutputFormat, fmt_name)

    config = speechsdk.SpeechConfig(subscription=AZURE_KEY, region=AZURE_REGION)
    config.set_speech_synthesis_output_format(fmt_enum)
    synth = speechsdk.SpeechSynthesizer(speech_config=config, audio_config=None)
    conn = speechsdk.Connection.from_speech_synthesizer(synth)
    conn.open(True)
    time.sleep(0.3)
    synth.speak_text_async("тест").get()

    start = time.time()
    result = synth.speak_text_async(TEXT).get()
    elapsed = time.time() - start

    if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
        idx = FORMATS.index((fmt_name, desc, ext)) + 1
        fname = f"fmt_{idx}_azure_{fmt_name}{ext}"
        with open(fname, "wb") as f:
            f.write(result.audio_data)
        print(f"  {idx}. Azure {desc:<42} | {elapsed:.3f}с | {fname}")

    del synth

print(f"""
{'='*65}
  ПОРІВНЯЙТЕ:
{'='*65}
  fmt_0 = Edge TTS MP3 24kHz     — "живий" звук
  fmt_1 = Azure MP3 24kHz 48kbps — ТАКИЙ САМИЙ як Edge TTS!
  fmt_2 = Azure MP3 24kHz 96kbps — ще краще
  fmt_4 = Azure WAV 24kHz        — найкраща якість
  fmt_6 = Azure WAV 8kHz         — "мертвий" звук (телефонія)

  Edge TTS = Azure TTS = один і той самий движок Microsoft Neural TTS
  Різниця тільки у форматі: 24kHz живий, 8kHz глухий
""")

