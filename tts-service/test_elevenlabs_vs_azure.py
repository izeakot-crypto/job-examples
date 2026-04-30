import sys, io, time, wave
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from elevenlabs import ElevenLabs
import azure.cognitiveservices.speech as speechsdk

ELEVENLABS_KEY = "sk_YOUR_AZURE_KEY6f5e39e76d233f3a"
AZURE_KEY = "YOUR_SECRET_TOKEN"
AZURE_REGION = "westeurope"

TEXT = "Добрий день! Дякую що зателефонували до служби підтримки. Чим можу вам допомогти?"

print(f'Текст: "{TEXT}" ({len(TEXT)} символів)\n')

# ═══════════════════════════════════════
# ElevenLabs
# ═══════════════════════════════════════
print(f"{'='*60}")
print(f"  ElevenLabs (Multilingual v2)")
print(f"{'='*60}")

client = ElevenLabs(api_key=ELEVENLABS_KEY)

# Спершу подивимось доступні голоси
voices = client.voices.get_all()
print(f"  Доступних голосів: {len(voices.voices)}")
print(f"  Перші 5:")
for v in voices.voices[:5]:
    print(f"    - {v.name} ({v.voice_id})")
print()

# Тестуємо кілька голосів
TEST_VOICES = [
    ("Rachel", "21m00Tcm4TlvDq8ikWAM"),
    ("Sarah", "EXAVITQu4vr4xnSDxMaL"),
    ("Charlotte", "XB0fDUnXU5powFXDhCwa"),
]

for voice_name, voice_id in TEST_VOICES:
    try:
        start = time.time()
        audio_gen = client.text_to_speech.convert(
            text=TEXT,
            voice_id=voice_id,
            model_id="eleven_multilingual_v2",
            output_format="mp3_44100_128",
        )
        # Збираємо всі чанки
        audio_data = b""
        for chunk in audio_gen:
            audio_data += chunk
        elapsed = time.time() - start

        fname = f"{len(TEXT)}sym_elevenlabs_{voice_name}_{elapsed:.3f}s.mp3"
        with open(fname, "wb") as f:
            f.write(audio_data)
        print(f"  {voice_name:<15} | {elapsed:.3f}с | {len(audio_data)}б | {fname}")
    except Exception as e:
        print(f"  {voice_name:<15} | ПОМИЛКА: {str(e)[:80]}")

# ═══════════════════════════════════════
# Azure TTS
# ═══════════════════════════════════════
print(f"\n{'='*60}")
print(f"  Azure Neural TTS (8kHz WAV)")
print(f"{'='*60}")

config = speechsdk.SpeechConfig(subscription=AZURE_KEY, region=AZURE_REGION)
config.speech_synthesis_voice_name = "uk-UA-PolinaNeural"
config.set_speech_synthesis_output_format(
    speechsdk.SpeechSynthesisOutputFormat.Riff8Khz16BitMonoPcm
)
synth = speechsdk.SpeechSynthesizer(speech_config=config, audio_config=None)
conn = speechsdk.Connection.from_speech_synthesizer(synth)
conn.open(True)
time.sleep(0.5)
synth.speak_text_async("тест").get()

start = time.time()
result = synth.speak_text_async(TEXT).get()
t_azure = time.time() - start
fname = f"{len(TEXT)}sym_azure_Polina_{t_azure:.3f}s.wav"
with open(fname, "wb") as f:
    f.write(result.audio_data)
print(f"  Поліна         | {t_azure:.3f}с | {len(result.audio_data)}б | {fname}")

del synth

# ═══════════════════════════════════════
print(f"\n{'='*60}")
print(f"  ПОРІВНЯННЯ")
print(f"{'='*60}")
print(f"  ElevenLabs: multilingual v2, якість топ, але ~$30/1M символів")
print(f"  Azure:      нативний 8kHz, швидкий, $16/1M символів")
print(f"  Послухайте і порівняйте якість!")


