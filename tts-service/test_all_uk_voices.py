import sys, io, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
import azure.cognitiveservices.speech as speechsdk

AZURE_KEY = "YOUR_SECRET_TOKEN"
AZURE_REGION = "westeurope"
TEXT = "Привіт! Я віртуальний помічник компанії Оки-Токі. Чим можу бути корисний?"

config = speechsdk.SpeechConfig(subscription=AZURE_KEY, region=AZURE_REGION)
config.set_speech_synthesis_output_format(
    speechsdk.SpeechSynthesisOutputFormat.Audio16Khz128KBitRateMonoMp3
)

synth = speechsdk.SpeechSynthesizer(speech_config=config, audio_config=None)

# Отримати всі голоси
print("Завантажую список голосів...\n")
voices_result = synth.get_voices_async().get()

uk_voices = []
for v in voices_result.voices:
    if "uk" in v.locale.lower():
        uk_voices.append(v)

print(f"Знайдено {len(uk_voices)} українських голосів:\n")
print(f"  {'#':<4} {'Голос':<35} {'Стать':<12} {'Locale':<10}")
print(f"  {'─'*4} {'─'*35} {'─'*12} {'─'*10}")
for i, v in enumerate(uk_voices):
    gender = "Жіночий" if v.gender.value == 2 else "Чоловічий"
    print(f"  {i+1:<4} {v.short_name:<35} {gender:<12} {v.locale:<10}")

# Згенерувати аудіо для кожного
print(f"\nГенерую аудіо для всіх...\n")

conn = speechsdk.Connection.from_speech_synthesizer(synth)
conn.open(True)
time.sleep(0.5)

for i, v in enumerate(uk_voices):
    ssml = f"""<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='{v.locale}'>
    <voice name='{v.short_name}'>{TEXT}</voice>
</speak>"""

    start = time.time()
    result = synth.speak_ssml_async(ssml).get()
    elapsed = time.time() - start

    if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
        fname = f"uk_voice_{i+1}_{v.short_name}.mp3"
        with open(fname, "wb") as f:
            f.write(result.audio_data)
        gender = "Жін" if v.gender.value == 2 else "Чол"
        print(f"  {i+1}. {v.short_name:<35} {gender} | {elapsed:.3f}с | {fname}")
    else:
        print(f"  {i+1}. {v.short_name:<35} ПОМИЛКА")

del synth
print(f"\nГотово! Послухайте всі файли.")

