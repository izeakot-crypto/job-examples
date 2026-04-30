import sys, io, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
import azure.cognitiveservices.speech as speechsdk

AZURE_KEY = "YOUR_SECRET_TOKEN"
AZURE_REGION = "westeurope"

config = speechsdk.SpeechConfig(subscription=AZURE_KEY, region=AZURE_REGION)
config.set_speech_synthesis_output_format(
    speechsdk.SpeechSynthesisOutputFormat.Riff8Khz16BitMonoPcm
)
synth = speechsdk.SpeechSynthesizer(speech_config=config, audio_config=None)
conn = speechsdk.Connection.from_speech_synthesizer(synth)
conn.open(True)
time.sleep(0.5)
synth.speak_text_async("тест").get()

TESTS = [
    ("1. Чистий текст, без SSML тюнінгу — Поліна",
     """<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='uk-UA'>
    <voice name='uk-UA-PolinaNeural'>
        Привіт! Я Ілля, я ваш віртуальний робот помічник. Чим вам допомогти?
    </voice></speak>"""),

    ("2. Чистий текст — Остап",
     """<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='uk-UA'>
    <voice name='uk-UA-OstapNeural'>
        Привіт! Я Ілля, я ваш віртуальний робот помічник. Чим вам допомогти?
    </voice></speak>"""),

    ("3. Тільки паузи між фразами — Поліна",
     """<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='uk-UA'>
    <voice name='uk-UA-PolinaNeural'>
        Привіт! <break time="300ms"/>
        Я Ілля, я ваш віртуальний робот помічник. <break time="200ms"/>
        Чим вам допомогти?
    </voice></speak>"""),

    ("4. Паузи + трохи швидше — Поліна",
     """<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='uk-UA'>
    <voice name='uk-UA-PolinaNeural'>
        <prosody rate='+10%'>
            Привіт! <break time="250ms"/>
            Я Ілля, я ваш віртуальний робот помічник. <break time="200ms"/>
            Чим вам допомогти?
        </prosody>
    </voice></speak>"""),

    ("5. Паузи + трохи швидше — Остап",
     """<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='uk-UA'>
    <voice name='uk-UA-OstapNeural'>
        <prosody rate='+10%'>
            Привіт! <break time="250ms"/>
            Я Ілля, я ваш віртуальний робот помічник. <break time="200ms"/>
            Чим вам допомогти?
        </prosody>
    </voice></speak>"""),

    ("6. Розділені речення окремими prosody — Поліна",
     """<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='uk-UA'>
    <voice name='uk-UA-PolinaNeural'>
        <prosody rate='+5%' pitch='+5%'>Привіт!</prosody>
        <break time="300ms"/>
        <prosody rate='+10%'>Я Ілля, я ваш віртуальний робот помічник.</prosody>
        <break time="200ms"/>
        <prosody rate='+5%' pitch='+3%'>Чим вам допомогти?</prosody>
    </voice></speak>"""),
]

print(f"Формат: WAV 8kHz 16bit mono")
print(f"Текст: Привіт! Я Ілля, я ваш віртуальний робот помічник. Чим вам допомогти?")
print(f"Без наголосів Unicode — чистий текст, мінімальний SSML\n")

for desc, ssml in TESTS:
    start = time.time()
    result = synth.speak_ssml_async(ssml).get()
    elapsed = time.time() - start

    if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
        num = desc[0]
        fname = f"natural_{num}.wav"
        with open(fname, "wb") as f:
            f.write(result.audio_data)
        print(f"  {desc}")
        print(f"    -> {elapsed:.3f}с | {len(result.audio_data)}б | {fname}\n")
    else:
        cancel = result.cancellation_details
        print(f"  {desc}")
        print(f"    -> ПОМИЛКА: {cancel.error_details}\n")

del synth
print(f"Послухайте natural_1.wav — natural_6.wav!")

