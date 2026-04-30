import sys, io, time, wave, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from openai import OpenAI
import azure.cognitiveservices.speech as speechsdk

OPENAI_KEY = "YOUR_OPENAI_API_KEY"
AZURE_KEY = "YOUR_SECRET_TOKEN"
AZURE_REGION = "westeurope"

llm = OpenAI(api_key=OPENAI_KEY)

def wrap_pcm_to_wav(pcm_data, sample_rate=8000):
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_data)
    return buf.getvalue()

TEXT = "Добрий день! Дякуємо що зателефонували до компанії Окі-Токі. Чим можу вам допомогти?"

# ═══════════════════════════════════════
# ТЕСТ 1: Що генерує GPT? Подивимось SSML
# ═══════════════════════════════════════
print(f"{'='*70}")
print(f"  ДІАГНОСТИКА: Що GPT генерує як SSML?")
print(f"{'='*70}\n")

SSML_SYSTEM = """Ти — експерт SSML розмітки для Azure TTS (uk-UA-PolinaNeural).
Додай SSML з ДУЖЕ РІЗНИМИ емоціями. Параметри мають СУТТЄВО відрізнятись!

Формат відповіді — ТІЛЬКИ SSML, нічого більше:
<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='uk-UA'>
<voice name='uk-UA-PolinaNeural'>...розмітка...</voice></speak>"""

emotions = [
    ("радісний", "Клієнт щасливий, бот радіє разом"),
    ("сумний", "Клієнт скаржиться, бот співчуває і вибачається"),
    ("терміновий", "Термінове повідомлення, бот попереджує клієнта"),
]

for emo_name, context in emotions:
    resp = llm.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SSML_SYSTEM},
            {"role": "user", "content": f"Контекст: {context}\nТекст: {TEXT}\nЕмоція: {emo_name}"},
        ],
        max_tokens=500, temperature=0.3,
    )
    ssml = resp.choices[0].message.content.strip()
    if ssml.startswith("```"):
        ssml = ssml.split("\n", 1)[1] if "\n" in ssml else ssml
        if ssml.endswith("```"):
            ssml = ssml[:-3].strip()

    print(f"  [{emo_name}] GPT згенерував:")
    print(f"  {ssml[:300]}")
    print()

# ═══════════════════════════════════════
# ТЕСТ 2: Ручний SSML з КРАЙНІМИ різницями
# ═══════════════════════════════════════
print(f"\n{'='*70}")
print(f"  ТЕСТ: Ручний SSML з ЕКСТРЕМАЛЬНИМИ різницями")
print(f"{'='*70}\n")

EXTREME_TESTS = [
    ("extreme_happy", """<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='uk-UA'>
<voice name='uk-UA-PolinaNeural'>
    <prosody rate="115%" pitch="+5st" volume="+6dB">
        Добрий день!
    </prosody>
    <break time="400ms"/>
    <prosody rate="110%" pitch="+4st" volume="+4dB">
        Дякуємо що зателефонували до компанії Окі-Токі!
    </prosody>
    <break time="300ms"/>
    <prosody rate="108%" pitch="+3st">
        Чим можу вам допомогти?
    </prosody>
</voice></speak>"""),

    ("extreme_sad", """<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='uk-UA'>
<voice name='uk-UA-PolinaNeural'>
    <prosody rate="75%" pitch="-4st" volume="-4dB">
        Добрий день...
    </prosody>
    <break time="600ms"/>
    <prosody rate="70%" pitch="-5st" volume="x-soft">
        Дякуємо що зателефонували до компанії Окі-Токі.
    </prosody>
    <break time="500ms"/>
    <prosody rate="75%" pitch="-3st" volume="soft">
        Чим можу вам допомогти?
    </prosody>
</voice></speak>"""),

    ("extreme_fast", """<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='uk-UA'>
<voice name='uk-UA-PolinaNeural'>
    <prosody rate="140%" pitch="+3st" volume="loud">
        Добрий день! Дякуємо що зателефонували до компанії Окі-Токі!
    </prosody>
    <break time="150ms"/>
    <prosody rate="135%" pitch="+2st" volume="+4dB">
        Чим можу вам допомогти?
    </prosody>
</voice></speak>"""),

    ("extreme_slow", """<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='uk-UA'>
<voice name='uk-UA-PolinaNeural'>
    <prosody rate="60%" pitch="-2st" volume="soft">
        Добрий день.
    </prosody>
    <break time="700ms"/>
    <prosody rate="55%" pitch="-3st" volume="x-soft">
        Дякуємо... що зателефонували... до компанії Окі-Токі.
    </prosody>
    <break time="600ms"/>
    <prosody rate="65%" pitch="-1st">
        Чим можу вам допомогти?
    </prosody>
</voice></speak>"""),

    ("normal_plain", None),  # plain text без SSML для порівняння
]

# Azure з прогрівом
config = speechsdk.SpeechConfig(subscription=AZURE_KEY, region=AZURE_REGION)
config.speech_synthesis_voice_name = "uk-UA-PolinaNeural"
config.set_speech_synthesis_output_format(speechsdk.SpeechSynthesisOutputFormat.Raw8Khz16BitMonoPcm)
synth = speechsdk.SpeechSynthesizer(speech_config=config, audio_config=None)
conn = speechsdk.Connection.from_speech_synthesizer(synth)
conn.open(True)
time.sleep(0.3)
synth.speak_text_async("тест").get()

print(f"  {'Тест':<20} {'Час':>7} {'Розмір':>8} Файл")
print(f"  {'─'*20} {'─'*7} {'─'*8} {'─'*35}")

for test_name, ssml in EXTREME_TESTS:
    start = time.time()

    if ssml is None:
        result = synth.speak_text_async(TEXT).get()
    else:
        result = synth.speak_ssml_async(ssml).get()

    t = time.time() - start

    if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
        pcm = result.audio_data
        wav = wrap_pcm_to_wav(pcm)
        fname = f"debug_{test_name}_{t:.3f}s.wav"
        with open(fname, "wb") as f:
            f.write(wav)
        print(f"  {test_name:<20} {t:>6.3f}с {len(wav):>7}б {fname}")
    else:
        cancel = result.cancellation_details
        err = cancel.error_details[:80] if cancel.error_details else "невідомо"
        print(f"  {test_name:<20} ПОМИЛКА: {err}")

del synth

print(f"\n  Якщо extreme_happy і extreme_sad звучать ОДНАКОВО —")
print(f"  значить Polina НЕ РЕАГУЄ на prosody параметри для української.")
print(f"\n  Якщо РІЗНІ — проблема була в тому що GPT генерує занадто")
print(f"  схожі параметри (rate 95-105%, pitch ±2st).")


