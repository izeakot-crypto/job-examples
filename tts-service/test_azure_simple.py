import sys, io, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
import azure.cognitiveservices.speech as speechsdk

AZURE_KEY = "YOUR_SECRET_TOKEN"
AZURE_REGION = "westeurope"
VOICE = "uk-UA-PolinaNeural"

TEXTS = [
    "Добрий день! Дякую що зателефонували.",
    "Привіт, я твій особистий помічник.",
    "Зачекайте будь ласка, я переключаю вас на оператора.",
]

config = speechsdk.SpeechConfig(subscription=AZURE_KEY, region=AZURE_REGION)
config.speech_synthesis_voice_name = VOICE
config.set_speech_synthesis_output_format(
    speechsdk.SpeechSynthesisOutputFormat.Audio16Khz128KBitRateMonoMp3
)

synth = speechsdk.SpeechSynthesizer(speech_config=config, audio_config=None)

for i, text in enumerate(TEXTS):
    print(f"\nТекст {i+1}: \"{text}\"")

    start = time.time()
    result = synth.speak_text_async(text).get()
    elapsed = time.time() - start

    if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
        fname = f"test_simple_{i+1}.mp3"
        with open(fname, "wb") as f:
            f.write(result.audio_data)
        print(f"  OK: {elapsed:.3f}с | {len(result.audio_data)} байт | збережено: {fname}")
    elif result.reason == speechsdk.ResultReason.Canceled:
        c = result.cancellation_details
        print(f"  ПОМИЛКА: {c.reason}")
        print(f"  Деталі: {c.error_details}")

# Тест з SSML для точного контролю
print("\n--- Тест з SSML ---")
ssml = """<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='uk-UA'>
    <voice name='uk-UA-PolinaNeural'>
        Привіт! Я віртуальний помічник Оки-Токі. Скажіть, що вас цікавить?
    </voice>
</speak>"""

start = time.time()
result = synth.speak_ssml_async(ssml).get()
elapsed = time.time() - start

if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
    fname = "test_ssml.mp3"
    with open(fname, "wb") as f:
        f.write(result.audio_data)
    print(f"  OK: {elapsed:.3f}с | {len(result.audio_data)} байт | збережено: {fname}")
else:
    c = result.cancellation_details
    print(f"  ПОМИЛКА: {c.reason}")
    print(f"  Деталі: {c.error_details}")

del synth
print("\nГотово! Послухайте файли: test_simple_1.mp3, test_simple_2.mp3, test_simple_3.mp3, test_ssml.mp3")

