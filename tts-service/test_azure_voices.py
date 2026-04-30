import sys, io, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
import azure.cognitiveservices.speech as speechsdk

AZURE_KEY = "YOUR_SECRET_TOKEN"
AZURE_REGION = "westeurope"
TEXT = "Привіт! Я віртуальний помічник компанії Оки-Токі. Чим можу бути корисний?"

VOICES = [
    ("uk-UA-PolinaNeural", "Поліна", "Жіночий, УК"),
    ("uk-UA-OstapNeural", "Остап", "Чоловічий, УК"),
    ("ru-RU-SvetlanaNeural", "Світлана", "Жіночий, РУ"),
    ("ru-RU-DmitryNeural", "Дмитро", "Чоловічий, РУ"),
    ("en-US-AvaMultilingualNeural", "Ava", "Жіночий, EN (мультимовний)"),
    ("en-US-AndrewMultilingualNeural", "Andrew", "Чоловічий, EN (мультимовний)"),
    ("en-US-NovaMultilingualNeural", "Nova", "Жіночий, EN (мультимовний)"),
]

config = speechsdk.SpeechConfig(subscription=AZURE_KEY, region=AZURE_REGION)
config.set_speech_synthesis_output_format(
    speechsdk.SpeechSynthesisOutputFormat.Audio16Khz128KBitRateMonoMp3
)

synth = speechsdk.SpeechSynthesizer(speech_config=config, audio_config=None)

print(f"Текст: \"{TEXT}\"\n")
print(f"{'#':<4} {'Голос':<40} {'Опис':<30} {'Час':>6}  Файл")
print(f"{'─'*4} {'─'*40} {'─'*30} {'─'*6}  {'─'*20}")

for i, (voice_id, name, desc) in enumerate(VOICES):
    ssml = f"""<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='uk-UA'>
        <voice name='{voice_id}'>{TEXT}</voice>
    </speak>"""

    start = time.time()
    result = synth.speak_ssml_async(ssml).get()
    elapsed = time.time() - start

    if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
        fname = f"voice_{i+1}_{name}.mp3"
        with open(fname, "wb") as f:
            f.write(result.audio_data)
        print(f"{i+1:<4} {voice_id:<40} {desc:<30} {elapsed:>5.2f}с  {fname}")
    else:
        c = result.cancellation_details
        print(f"{i+1:<4} {voice_id:<40} {desc:<30} ПОМИЛКА: {c.error_details[:50]}")

del synth
print(f"\nПослухайте всі файли і скажіть який голос подобається!")

