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
conn = speechsdk.Connection.from_speech_synthesizer(synth)
conn.open(True)
time.sleep(0.5)
synth.speak_text_async("тест").get()

TESTS = [
    ("Звичайний (без змін)", f"""<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='uk-UA'>
    <voice name='uk-UA-PolinaNeural'>{TEXT}</voice></speak>"""),

    ("Швидше +15%, вищий тон +10%", f"""<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='uk-UA'>
    <voice name='uk-UA-PolinaNeural'>
        <prosody rate='+15%' pitch='+10%'>{TEXT}</prosody>
    </voice></speak>"""),

    ("Швидше +10%, вищий тон +20%", f"""<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='uk-UA'>
    <voice name='uk-UA-PolinaNeural'>
        <prosody rate='+10%' pitch='+20%'>{TEXT}</prosody>
    </voice></speak>"""),

    ("Швидше +20%, вищий тон +5%, голосніше", f"""<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='uk-UA'>
    <voice name='uk-UA-PolinaNeural'>
        <prosody rate='+20%' pitch='+5%' volume='+20%'>{TEXT}</prosody>
    </voice></speak>"""),

    ("Вищий тон +15%, гучний", f"""<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='uk-UA'>
    <voice name='uk-UA-PolinaNeural'>
        <prosody pitch='+15%' volume='loud'>{TEXT}</prosody>
    </voice></speak>"""),

    ("Енергійний: +20% rate, +15% pitch, loud", f"""<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='uk-UA'>
    <voice name='uk-UA-PolinaNeural'>
        <prosody rate='+20%' pitch='+15%' volume='loud'>{TEXT}</prosody>
    </voice></speak>"""),

    ("Остап звичайний", f"""<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='uk-UA'>
    <voice name='uk-UA-OstapNeural'>{TEXT}</voice></speak>"""),

    ("Остап енергійний: +15% rate, +10% pitch, loud", f"""<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='uk-UA'>
    <voice name='uk-UA-OstapNeural'>
        <prosody rate='+15%' pitch='+10%' volume='loud'>{TEXT}</prosody>
    </voice></speak>"""),
]

print(f"Текст: \"{TEXT}\"\n")

for i, (desc, ssml) in enumerate(TESTS):
    start = time.time()
    result = synth.speak_ssml_async(ssml).get()
    elapsed = time.time() - start

    if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
        fname = f"emotion_{i+1}.mp3"
        with open(fname, "wb") as f:
            f.write(result.audio_data)
        print(f"  {i+1}. {desc:<50} | {elapsed:.3f}с | {fname}")
    else:
        print(f"  {i+1}. {desc:<50} | ПОМИЛКА")

del synth
print(f"\nПослухайте і оберіть який варіант живіший!")

