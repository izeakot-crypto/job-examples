import sys, io, time, wave, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = r"[USER_HOME]\Downloads\tts-488311-d5a1cbf88094.json"

from google.cloud import texttospeech

TEXT = "Добрий день! Дякуємо що зателефонували до компанії Окі-Токі. Зараз усі оператори зайняті, але ваш дзвінок дуже важливий для нас. Залишайтесь на лінії, будь ласка."

SSML = """<speak>
<prosody rate="95%" pitch="+2st" volume="+2dB">
Добрий день! <break time="350ms"/>
Дякуємо що зателефонували до компанії Окі-Токі.
<break time="250ms"/>
Зараз усі оператори зайняті, <break time="200ms"/> але ваш дзвінок дуже важливий для нас.
<break time="300ms"/>
Залишайтесь на лінії, <break time="100ms"/> будь ласка.
</prosody>
</speak>"""

gclient = texttospeech.TextToSpeechClient()

# Отримуємо всі українські голоси
voices_response = gclient.list_voices(language_code="uk-UA")

print(f"Всі українські голоси Google Cloud TTS:")
print(f"{'─'*60}")

standard = []
wavenet = []
chirp = []

for v in voices_response.voices:
    gender = "Жін" if v.ssml_gender == texttospeech.SsmlVoiceGender.FEMALE else "Чол"
    if "Standard" in v.name:
        standard.append((v.name, gender))
    elif "Wavenet" in v.name:
        wavenet.append((v.name, gender))
    elif "Chirp" in v.name:
        chirp.append((v.name, gender))

print(f"\n  Standard ({len(standard)}):")
for name, g in standard:
    print(f"    {name} ({g})")

print(f"\n  Wavenet ({len(wavenet)}):")
for name, g in wavenet:
    print(f"    {name} ({g})")

print(f"\n  Chirp3-HD ({len(chirp)}):")
for name, g in chirp:
    print(f"    {name} ({g})")

print(f"\n  Всього: {len(standard) + len(wavenet) + len(chirp)} голосів")

# Тестуємо тільки Standard + Wavenet (бо вони < 1с)
fast_voices = standard + wavenet
audio_cfg = texttospeech.AudioConfig(
    audio_encoding=texttospeech.AudioEncoding.LINEAR16,
    sample_rate_hertz=8000,
    effects_profile_id=["telephony-class-application"],
)

print(f"\n{'='*60}")
print(f"  Тест: Standard + Wavenet з telephony profile + SSML")
print(f"{'='*60}")
print(f"  {'Голос':<30} {'Стать':>5} {'Час':>7} Файл")
print(f"  {'─'*30} {'─'*5} {'─'*7} {'─'*45}")

for voice_name, gender in fast_voices:
    voice_params = texttospeech.VoiceSelectionParams(language_code="uk-UA", name=voice_name)
    synth_input = texttospeech.SynthesisInput(ssml=SSML)

    start = time.time()
    resp = gclient.synthesize_speech(input=synth_input, voice=voice_params, audio_config=audio_cfg)
    t = time.time() - start

    short = voice_name.replace("uk-UA-", "")
    fname = f"{len(TEXT)}sym_g_{short}_tel_{t:.3f}s.wav"
    with open(fname, "wb") as f:
        f.write(resp.audio_content)
    print(f"  {voice_name:<30} {gender:>5} {t:>6.3f}с {fname}")

print(f"\n  Послухайте всі та оберіть!")

