import sys, io, time, wave, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = r"[USER_HOME]\Downloads\tts-488311-d5a1cbf88094.json"

from google.cloud import texttospeech
import azure.cognitiveservices.speech as speechsdk

AZURE_KEY = "YOUR_SECRET_TOKEN"
AZURE_REGION = "westeurope"

TEXT = "Шановний клієнте, дякуємо що зателефонували до служби підтримки компанії Окі-Токі. Чим можу вам допомогти? Зачекайте, зʼєдную вас з оператором."

print(f'Текст: "{TEXT}" ({len(TEXT)} символів)\n')

# ═══════════════════════════════════════
# Google Cloud TTS
# ═══════════════════════════════════════
print(f"{'='*60}")
print(f"  Google Cloud TTS — українські голоси")
print(f"{'='*60}")

gclient = texttospeech.TextToSpeechClient()

# Список українських голосів
voices_response = gclient.list_voices(language_code="uk-UA")
print(f"  Українських голосів: {len(voices_response.voices)}")
for v in voices_response.voices:
    gender = "Жін" if v.ssml_gender == texttospeech.SsmlVoiceGender.FEMALE else "Чол"
    print(f"    - {v.name} ({gender})")
print()

# Тестуємо всі українські голоси у форматі 8kHz 16bit
synthesis_input = texttospeech.SynthesisInput(text=TEXT)

audio_config_8khz = texttospeech.AudioConfig(
    audio_encoding=texttospeech.AudioEncoding.LINEAR16,
    sample_rate_hertz=8000,
)

for v in voices_response.voices:
    voice_params = texttospeech.VoiceSelectionParams(
        language_code="uk-UA",
        name=v.name,
    )
    start = time.time()
    response = gclient.synthesize_speech(
        input=synthesis_input,
        voice=voice_params,
        audio_config=audio_config_8khz,
    )
    elapsed = time.time() - start

    gender = "F" if v.ssml_gender == texttospeech.SsmlVoiceGender.FEMALE else "M"
    fname = f"{len(TEXT)}sym_google_{v.name}_{elapsed:.3f}s.wav"
    with open(fname, "wb") as f:
        f.write(response.audio_content)
    print(f"  {v.name:<30} {gender} | {elapsed:.3f}с | {len(response.audio_content)}б | {fname}")

# ═══════════════════════════════════════
# Azure TTS
# ═══════════════════════════════════════
print(f"\n{'='*60}")
print(f"  Azure Neural TTS (8kHz WAV)")
print(f"{'='*60}")

config = speechsdk.SpeechConfig(subscription=AZURE_KEY, region=AZURE_REGION)
config.set_speech_synthesis_output_format(
    speechsdk.SpeechSynthesisOutputFormat.Riff8Khz16BitMonoPcm
)

for voice_id, voice_name in [("uk-UA-PolinaNeural", "Поліна"), ("uk-UA-OstapNeural", "Остап")]:
    config.speech_synthesis_voice_name = voice_id
    synth = speechsdk.SpeechSynthesizer(speech_config=config, audio_config=None)
    conn = speechsdk.Connection.from_speech_synthesizer(synth)
    conn.open(True)
    time.sleep(0.3)
    synth.speak_text_async("тест").get()

    start = time.time()
    result = synth.speak_text_async(TEXT).get()
    elapsed = time.time() - start

    fname = f"{len(TEXT)}sym_azure_{voice_name}_{elapsed:.3f}s.wav"
    with open(fname, "wb") as f:
        f.write(result.audio_data)
    print(f"  {voice_id:<30}   | {elapsed:.3f}с | {len(result.audio_data)}б | {fname}")
    del synth

print(f"\n{'='*60}")
print(f"  ПОРІВНЯННЯ")
print(f"{'='*60}")
print(f"  Google Cloud TTS: $16/1M, 8kHz нативно, більше голосів")
print(f"  Azure Neural TTS: $16/1M, 8kHz нативно, 2 голоси UK")
print(f"  Послухайте і порівняйте!")


