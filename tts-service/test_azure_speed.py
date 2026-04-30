import sys, io, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
import azure.cognitiveservices.speech as speechsdk

AZURE_KEY = "YOUR_SECRET_TOKEN"
AZURE_REGION = "westeurope"
TEXT = "Привіт! Я віртуальний помічник компанії Оки-Токі. Чим можу бути корисний?"

SPEEDS = [
    ("-30%", "Повільна"),
    ("-15%", "Трохи повільна"),
    ("0%", "Нормальна"),
    ("+15%", "Трохи швидша"),
    ("+30%", "Швидка"),
    ("+50%", "Дуже швидка"),
]

config = speechsdk.SpeechConfig(subscription=AZURE_KEY, region=AZURE_REGION)
config.set_speech_synthesis_output_format(
    speechsdk.SpeechSynthesisOutputFormat.Audio16Khz128KBitRateMonoMp3
)
synth = speechsdk.SpeechSynthesizer(speech_config=config, audio_config=None)
conn = speechsdk.Connection.from_speech_synthesizer(synth)
conn.open(True)
time.sleep(0.5)
synth.speak_text_async("тест").get()

print(f"Текст: \"{TEXT}\"\n")

for rate, desc in SPEEDS:
    ssml = f"""<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='uk-UA'>
    <voice name='uk-UA-PolinaNeural'>
        <prosody rate='{rate}'>{TEXT}</prosody>
    </voice>
</speak>"""

    start = time.time()
    result = synth.speak_ssml_async(ssml).get()
    elapsed = time.time() - start

    if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
        fname = f"speed_{rate.replace('+','plus').replace('-','minus')}.mp3"
        with open(fname, "wb") as f:
            f.write(result.audio_data)
        print(f"  rate={rate:<5} | {desc:<20} | {elapsed:.3f}с | {len(result.audio_data)}б | {fname}")

del synth
print(f"\nПослухайте і оберіть яка швидкість підходить!")

