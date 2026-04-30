import sys, io, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
import azure.cognitiveservices.speech as speechsdk

AZURE_KEY = "YOUR_SECRET_TOKEN"
AZURE_REGION = "westeurope"

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
    ("1. Без наголосів (базовий)", """<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='uk-UA'>
    <voice name='uk-UA-PolinaNeural'>
        <prosody rate='+20%' pitch='+5%' volume='+20%'>
            Привіт! Я віртуальний помічник компанії Окі-Токі. Чим можу бути корисний?
        </prosody>
    </voice></speak>"""),

    ("2. Юнікод наголоси (U+0301)", """<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='uk-UA'>
    <voice name='uk-UA-PolinaNeural'>
        <prosody rate='+20%' pitch='+5%' volume='+20%'>
            Приві́т! Я віртуа́льний помічни́к компа́нії Окі-То́кі. Чим можу́ бу́ти кори́сний?
        </prosody>
    </voice></speak>"""),

    ("3. Emphasis strong на ключових словах", """<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis'
     xmlns:mstts='http://www.w3.org/2001/mstts' xml:lang='uk-UA'>
    <voice name='uk-UA-PolinaNeural'>
        <prosody rate='+20%' pitch='+5%' volume='+20%'>
            <emphasis level="strong">Привіт!</emphasis> Я віртуальний помічник компанії <emphasis level="strong">Окі-Токі</emphasis>. Чим можу бути <emphasis level="moderate">корисний</emphasis>?
        </prosody>
    </voice></speak>"""),

    ("4. Emphasis moderate + паузи", """<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis'
     xmlns:mstts='http://www.w3.org/2001/mstts' xml:lang='uk-UA'>
    <voice name='uk-UA-PolinaNeural'>
        <prosody rate='+20%' pitch='+5%' volume='+20%'>
            <emphasis level="moderate">Привіт!</emphasis> <break time="200ms"/> Я віртуальний помічник компанії Окі-Токі. <break time="150ms"/> Чим можу бути <emphasis level="moderate">корисний</emphasis>?
        </prosody>
    </voice></speak>"""),

    ("5. Юнікод наголоси + emphasis + паузи", """<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis'
     xmlns:mstts='http://www.w3.org/2001/mstts' xml:lang='uk-UA'>
    <voice name='uk-UA-PolinaNeural'>
        <prosody rate='+20%' pitch='+5%' volume='+20%'>
            <emphasis level="moderate">Приві́т!</emphasis> <break time="200ms"/> Я віртуа́льний помічни́к компа́нії <emphasis level="moderate">Окі-То́кі</emphasis>. <break time="150ms"/> Чим можу́ бу́ти <emphasis level="moderate">кори́сний</emphasis>?
        </prosody>
    </voice></speak>"""),
]

print(f"Тестуємо наголоси та emphasis в Azure TTS\n")

for i, (desc, ssml) in enumerate(TESTS):
    start = time.time()
    result = synth.speak_ssml_async(ssml).get()
    elapsed = time.time() - start

    if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
        fname = f"stress_{i+1}.mp3"
        with open(fname, "wb") as f:
            f.write(result.audio_data)
        print(f"  {desc:<55} | {elapsed:.3f}с | {fname}")
    else:
        cancel = result.cancellation_details
        print(f"  {desc:<55} | ПОМИЛКА: {cancel.reason} — {cancel.error_details}")

del synth
print(f"\nПослухайте і порівняйте!")

