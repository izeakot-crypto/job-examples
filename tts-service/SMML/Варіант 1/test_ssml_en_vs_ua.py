import sys, io, time, wave, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
import azure.cognitiveservices.speech as speechsdk

AZURE_KEY = "YOUR_SECRET_TOKEN"
AZURE_REGION = "westeurope"

TEXT_UA = "Добрий день! Дякуємо що зателефонували. Чим можу допомогти?"
TEXT_EN = "Good morning! Thank you for calling. How can I help you today?"

def wrap_pcm_to_wav(pcm_data, sample_rate=8000):
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_data)
    return buf.getvalue()

def make_ssml(voice, lang, text, rate, pitch, volume):
    return f"""<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='{lang}'>
<voice name='{voice}'>
    <prosody rate="{rate}" pitch="{pitch}" volume="{volume}">
        {text}
    </prosody>
</voice></speak>"""

config = speechsdk.SpeechConfig(subscription=AZURE_KEY, region=AZURE_REGION)
config.set_speech_synthesis_output_format(speechsdk.SpeechSynthesisOutputFormat.Raw8Khz16BitMonoPcm)
synth = speechsdk.SpeechSynthesizer(speech_config=config, audio_config=None)
conn = speechsdk.Connection.from_speech_synthesizer(synth)
conn.open(True)
time.sleep(0.3)
synth.speak_text_async("test").get()

TESTS = [
    # (назва, голос, мова, текст, rate, pitch, volume)
    # Українська
    ("ua_normal",   "uk-UA-PolinaNeural", "uk-UA", TEXT_UA, "100%", "+0st",  "medium"),
    ("ua_fast",     "uk-UA-PolinaNeural", "uk-UA", TEXT_UA, "130%", "+0st",  "medium"),
    ("ua_slow",     "uk-UA-PolinaNeural", "uk-UA", TEXT_UA, "70%",  "+0st",  "medium"),
    ("ua_high",     "uk-UA-PolinaNeural", "uk-UA", TEXT_UA, "100%", "+4st",  "medium"),
    ("ua_low",      "uk-UA-PolinaNeural", "uk-UA", TEXT_UA, "100%", "-4st",  "medium"),
    ("ua_loud",     "uk-UA-PolinaNeural", "uk-UA", TEXT_UA, "100%", "+0st",  "x-loud"),
    ("ua_soft",     "uk-UA-PolinaNeural", "uk-UA", TEXT_UA, "100%", "+0st",  "x-soft"),
    # Англійська
    ("en_normal",   "en-US-JennyNeural",  "en-US", TEXT_EN, "100%", "+0st",  "medium"),
    ("en_fast",     "en-US-JennyNeural",  "en-US", TEXT_EN, "130%", "+0st",  "medium"),
    ("en_slow",     "en-US-JennyNeural",  "en-US", TEXT_EN, "70%",  "+0st",  "medium"),
    ("en_high",     "en-US-JennyNeural",  "en-US", TEXT_EN, "100%", "+4st",  "medium"),
    ("en_low",      "en-US-JennyNeural",  "en-US", TEXT_EN, "100%", "-4st",  "medium"),
    ("en_loud",     "en-US-JennyNeural",  "en-US", TEXT_EN, "100%", "+0st",  "x-loud"),
    ("en_soft",     "en-US-JennyNeural",  "en-US", TEXT_EN, "100%", "+0st",  "x-soft"),
]

print(f"SSML тест: Українська Polina vs Англійська Jenny\n")
print(f"  {'Тест':<14} {'Rate':>5} {'Pitch':>5} {'Vol':>7} {'Розмір':>8} {'Різн від норм':>14}")
print(f"  {'─'*14} {'─'*5} {'─'*5} {'─'*7} {'─'*8} {'─'*14}")

normal_sizes = {}

for name, voice, lang, text, rate, pitch, vol in TESTS:
    ssml = make_ssml(voice, lang, text, rate, pitch, vol)
    result = synth.speak_ssml_async(ssml).get()

    if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
        wav = wrap_pcm_to_wav(result.audio_data)
        fname = f"cmp_{name}.wav"
        with open(fname, "wb") as f:
            f.write(wav)

        # Запам'ятати normal для порівняння
        prefix = name.split("_")[0]  # ua або en
        if "normal" in name:
            normal_sizes[prefix] = len(wav)

        norm_size = normal_sizes.get(prefix, len(wav))
        diff_pct = ((len(wav) - norm_size) / norm_size * 100) if norm_size else 0
        diff_str = f"{diff_pct:>+.1f}%" if "normal" not in name else "базовий"

        print(f"  {name:<14} {rate:>5} {pitch:>5} {vol:>7} {len(wav):>7}б {diff_str:>14}")
    else:
        print(f"  {name:<14} {rate:>5} {pitch:>5} {vol:>7}    ПОМИЛКА")

    if name == "ua_soft":
        print()

del synth

print(f"\n  Якщо EN має великі різниці а UA ні — SSML не працює для української.")

