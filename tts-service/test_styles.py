import sys, io, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
import azure.cognitiveservices.speech as speechsdk

AZURE_KEY = "YOUR_SECRET_TOKEN"
AZURE_REGION = "westeurope"
TEXT = "Добрий день! Дякую що зателефонували. Чим можу вам допомогти?"

config = speechsdk.SpeechConfig(subscription=AZURE_KEY, region=AZURE_REGION)
config.set_speech_synthesis_output_format(
    speechsdk.SpeechSynthesisOutputFormat.Riff8Khz16BitMonoPcm
)
synth = speechsdk.SpeechSynthesizer(speech_config=config, audio_config=None)
conn = speechsdk.Connection.from_speech_synthesizer(synth)
conn.open(True)
time.sleep(0.5)
synth.speak_text_async("тест").get()

TEXTS_BY_LANG = {
    "uk": "Добрий день! Дякую що зателефонували. Чим можу вам допомогти?",
    "en": "Hello! Thank you for calling. How can I help you today?",
    "ru": "Здравствуйте! Спасибо что позвонили. Чем могу вам помочь?",
}

TESTS = [
    # Українська
    ("uk_neutral", "uk-UA-PolinaNeural", None, "uk"),
    ("uk_cheerful", "uk-UA-PolinaNeural", "cheerful", "uk"),
    ("uk_friendly", "uk-UA-PolinaNeural", "friendly", "uk"),
    ("uk_customerservice", "uk-UA-PolinaNeural", "customerservice", "uk"),
    # Англійська (підтримує стилі)
    ("en_neutral", "en-US-JennyNeural", None, "en"),
    ("en_cheerful", "en-US-JennyNeural", "cheerful", "en"),
    ("en_friendly", "en-US-JennyNeural", "friendly", "en"),
    ("en_customerservice", "en-US-JennyNeural", "customerservice", "en"),
    # Російська
    ("ru_neutral", "ru-RU-SvetlanaNeural", None, "ru"),
    ("ru_cheerful", "ru-RU-SvetlanaNeural", "cheerful", "ru"),
    ("ru_friendly", "ru-RU-SvetlanaNeural", "friendly", "ru"),
    ("ru_customerservice", "ru-RU-SvetlanaNeural", "customerservice", "ru"),
]

print(f"Тест: чи працюють стилі на українських голосах?\n")

for name, voice, style, lang in TESTS:
    text = TEXTS_BY_LANG[lang]
    lang_map = {"uk": "uk-UA", "en": "en-US", "ru": "ru-RU"}
    xml_lang = lang_map[lang]
    if style:
        ssml = f"""<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis'
         xmlns:mstts='https://www.w3.org/2001/mstts' xml:lang='{xml_lang}'>
        <voice name='{voice}'>
            <mstts:express-as style='{style}'>
                {text}
            </mstts:express-as>
        </voice></speak>"""
    else:
        ssml = f"""<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='{xml_lang}'>
        <voice name='{voice}'>{text}</voice></speak>"""

    start = time.time()
    result = synth.speak_ssml_async(ssml).get()
    elapsed = time.time() - start

    if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
        fname = f"style_{name}.wav"
        with open(fname, "wb") as f:
            f.write(result.audio_data)
        print(f"  {name:<25} | {elapsed:.3f}с | {len(result.audio_data)}б | {fname}")
    else:
        cancel = result.cancellation_details
        err = cancel.error_details[:80] if cancel.error_details else "невідомо"
        print(f"  {name:<25} | ПОМИЛКА: {err}")

del synth
print(f"\nПорівняйте розмір файлів: якщо однаковий — стиль не працює")

