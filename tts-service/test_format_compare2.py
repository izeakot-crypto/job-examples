import sys, io, time, asyncio
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
import edge_tts
import azure.cognitiveservices.speech as speechsdk

TEXT = "Добрий день! Мене звати Оксана. Я допоможу вам оформити замовлення. Що саме вас цікавить?"
VOICE = "uk-UA-PolinaNeural"

AZURE_KEY = "YOUR_SECRET_TOKEN"
AZURE_REGION = "westeurope"

def make_ssml(text, voice="uk-UA-PolinaNeural"):
    return f"""<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='uk-UA'>
    <voice name='{voice}'>{text}</voice></speak>"""

print(f'Текст: "{TEXT}"')
print(f"Голос: {VOICE}\n")

# ── Edge TTS ──
async def gen_edge():
    comm = edge_tts.Communicate(TEXT, VOICE)
    start = time.time()
    await comm.save("cmp_0_edge.mp3")
    return time.time() - start

t = asyncio.run(gen_edge())
print(f"  0. Edge TTS (MP3 24kHz)                  {t:.3f}с  cmp_0_edge.mp3")

# ── Azure TTS різні формати ──
FORMATS = [
    ("Riff8Khz16BitMonoPcm",         "Azure WAV 8kHz (телефонія)", ".wav"),
]

for i, (fmt_name, desc, ext) in enumerate(FORMATS):
    fmt_enum = getattr(speechsdk.SpeechSynthesisOutputFormat, fmt_name)
    config = speechsdk.SpeechConfig(subscription=AZURE_KEY, region=AZURE_REGION)
    config.set_speech_synthesis_output_format(fmt_enum)

    synth = speechsdk.SpeechSynthesizer(speech_config=config, audio_config=None)
    conn = speechsdk.Connection.from_speech_synthesizer(synth)
    conn.open(True)
    time.sleep(0.3)
    synth.speak_ssml_async(make_ssml("тест")).get()

    ssml = make_ssml(TEXT)
    start = time.time()
    result = synth.speak_ssml_async(ssml).get()
    elapsed = time.time() - start

    idx = i + 1
    fname = f"cmp_{idx}_{fmt_name}{ext}"

    if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
        with open(fname, "wb") as f:
            f.write(result.audio_data)
        print(f"  {idx}. {desc:<40} {elapsed:.3f}с  {fname}")
    else:
        cancel = result.cancellation_details
        print(f"  {idx}. {desc:<40} ПОМИЛКА: {cancel.error_details[:80]}")

    del synth

print(f"\nПослухайте cmp_0 — cmp_5!")

