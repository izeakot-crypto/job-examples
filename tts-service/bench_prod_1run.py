import sys, io, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
import azure.cognitiveservices.speech as speechsdk

AZURE_KEY = "YOUR_SECRET_TOKEN"
AZURE_REGION = "westeurope"

TEXTS = [
    "Добрий день! Дякую що зателефонували. Чим можу вам допомогти?",
    "Ваш запит прийнято. Очікуйте відповідь оператора протягом хвилини.",
    "Привіт! Я віртуальний помічник компанії Оки-Токі. Чим можу бути корисний?",
]

VOICES = [
    ("uk-UA-PolinaNeural", "Поліна"),
    ("uk-UA-OstapNeural", "Остап"),
]

for voice_id, voice_name in VOICES:
    print(f"\n{'='*60}")
    print(f"  {voice_name} ({voice_id})")
    print(f"{'='*60}")

    config = speechsdk.SpeechConfig(subscription=AZURE_KEY, region=AZURE_REGION)
    config.speech_synthesis_voice_name = voice_id
    config.set_speech_synthesis_output_format(
        speechsdk.SpeechSynthesisOutputFormat.Audio16Khz128KBitRateMonoMp3
    )

    synth = speechsdk.SpeechSynthesizer(speech_config=config, audio_config=None)
    conn = speechsdk.Connection.from_speech_synthesizer(synth)
    conn.open(True)
    time.sleep(0.5)
    synth.speak_text_async("тест").get()  # прогрів

    for idx, text in enumerate(TEXTS):
        start = time.time()
        result = synth.speak_text_async(text).get()
        elapsed = time.time() - start

        if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
            fname = f"prod_{voice_name}_{idx+1}.mp3"
            with open(fname, "wb") as f:
                f.write(result.audio_data)
            fb = result.properties.get_property(speechsdk.PropertyId.SpeechServiceResponse_SynthesisFirstByteLatencyMs)
            sv = result.properties.get_property(speechsdk.PropertyId.SpeechServiceResponse_SynthesisServiceLatencyMs)
            print(f"  {fname:<25} {elapsed:.3f}с | first_byte: {fb}мс | service: {sv}мс | \"{text[:45]}...\"")

    del synth

print(f"\n{'='*60}")
print(f"  Готово! Послухайте файли.")
print(f"{'='*60}")

