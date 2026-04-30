import sys, io, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
import azure.cognitiveservices.speech as speechsdk

AZURE_KEY = "YOUR_SECRET_TOKEN"
AZURE_REGION = "westeurope"
VOICE = "uk-UA-PolinaNeural"

config = speechsdk.SpeechConfig(subscription=AZURE_KEY, region=AZURE_REGION)
config.set_speech_synthesis_output_format(
    speechsdk.SpeechSynthesisOutputFormat.Riff8Khz16BitMonoPcm
)
synth = speechsdk.SpeechSynthesizer(speech_config=config, audio_config=None)
conn = speechsdk.Connection.from_speech_synthesizer(synth)
conn.open(True)
time.sleep(0.5)
# Прогрів
synth.speak_ssml_async(f"""<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='uk-UA'>
    <voice name='{VOICE}'><prosody rate='+20%'>тест</prosody></voice></speak>""").get()

TESTS = [
    ("1. Наголоси + emphasis на привітанні та імені",
     f"""<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis'
     xmlns:mstts='http://www.w3.org/2001/mstts' xml:lang='uk-UA'>
    <voice name='{VOICE}'>
        <prosody rate='+20%' pitch='+5%' volume='+20%'>
            <emphasis level="moderate">Приві́т!</emphasis> <break time="150ms"/>
            Я Ілля́, я ва́ш віртуа́льний ро́бот помічни́к. <break time="100ms"/>
            Чи́м ва́м допомогти́?
        </prosody>
    </voice></speak>"""),

    ("2. Контурна інтонація: підйом на привітанні, спад на питанні",
     f"""<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis'
     xmlns:mstts='http://www.w3.org/2001/mstts' xml:lang='uk-UA'>
    <voice name='{VOICE}'>
        <prosody rate='+15%' volume='+20%'>
            <prosody pitch='+15%' rate='+10%'><emphasis level="strong">Приві́т!</emphasis></prosody>
            <break time="200ms"/>
            <prosody pitch='+5%'>Я Ілля́, я ва́ш віртуа́льний ро́бот помічни́к.</prosody>
            <break time="150ms"/>
            <prosody pitch='+10%' rate='+5%'>Чи́м ва́м <emphasis level="moderate">допомогти́</emphasis>?</prosody>
        </prosody>
    </voice></speak>"""),

    ("3. Привітний стиль: паузи + м'який emphasis + наголоси",
     f"""<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis'
     xmlns:mstts='http://www.w3.org/2001/mstts' xml:lang='uk-UA'>
    <voice name='{VOICE}'>
        <prosody rate='+10%' pitch='+8%' volume='+15%'>
            <emphasis level="moderate">Приві́т!</emphasis>
            <break time="250ms"/>
            Я — <emphasis level="moderate">Ілля́</emphasis>, ва́ш віртуа́льний ро́бот помічни́к.
            <break time="200ms"/>
            <prosody pitch='+12%'>Чи́м ва́м допомогти́?</prosody>
        </prosody>
    </voice></speak>"""),
]

print(f"Голос: {VOICE}")
print(f"Формат: WAV 8kHz 16bit mono (riff-8khz-16bit-mono-pcm)")
print(f"Режим: продакшин (1 запит)\n")

def calc_cps(text, elapsed):
    clean = ''.join(c for c in text if c.isalpha() or c.isspace())
    return len(clean) / elapsed if elapsed > 0 else 0

TEXT_CLEAN = "Привіт Я Ілля я ваш віртуальний робот помічник Чим вам допомогти"

for desc, ssml in TESTS:
    start = time.time()
    result = synth.speak_ssml_async(ssml).get()
    elapsed = time.time() - start

    if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
        num = desc[0]
        fname = f"prod_stress_{num}.wav"
        with open(fname, "wb") as f:
            f.write(result.audio_data)
        cps = calc_cps(TEXT_CLEAN, elapsed)
        print(f"  {desc}")
        print(f"    -> {elapsed:.3f}с | CPS: {cps:.0f} | {len(result.audio_data)}б | {fname}\n")
    else:
        cancel = result.cancellation_details
        print(f"  {desc}")
        print(f"    -> ПОМИЛКА: {cancel.error_details}\n")

del synth
print(f"Послухайте prod_stress_1.wav, prod_stress_2.wav, prod_stress_3.wav!")

