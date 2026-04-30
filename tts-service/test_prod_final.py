import sys, io, time, wave, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = r"[USER_HOME]\Downloads\tts-488311-d5a1cbf88094.json"

from google.cloud import texttospeech
import azure.cognitiveservices.speech as speechsdk

AZURE_KEY = "YOUR_SECRET_TOKEN"
AZURE_REGION = "westeurope"

TEXTS = [
    "Добрий день! Дякуємо що зателефонували до компанії Окі-Токі. Зараз усі оператори зайняті, але ваш дзвінок дуже важливий для нас. Залишайтесь на лінії, будь ласка.",
    "Вітаємо вас! Ви зателефонували до служби технічної підтримки. Для зʼєднання з оператором натисніть один, для перевірки статусу заявки натисніть два, або залишайтесь на лінії і вам відповість перший вільний спеціаліст.",
    "Шановний клієнте, ваш запит прийнято та зареєстровано під номером сімнадцять. Очікуйте відповідь оператора протягом двох хвилин. Дякуємо за терпіння, ми цінуємо ваш час і намагаємось відповісти якнайшвидше.",
]

def wrap_pcm_to_wav(pcm_data, sample_rate=8000):
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_data)
    return buf.getvalue()

# ═══════════════════════════════════════
# Azure Polina — підготовка
# ═══════════════════════════════════════
config = speechsdk.SpeechConfig(subscription=AZURE_KEY, region=AZURE_REGION)
config.speech_synthesis_voice_name = "uk-UA-PolinaNeural"
config.set_speech_synthesis_output_format(speechsdk.SpeechSynthesisOutputFormat.Raw8Khz16BitMonoPcm)

synth_az = speechsdk.SpeechSynthesizer(speech_config=config, audio_config=None)
conn = speechsdk.Connection.from_speech_synthesizer(synth_az)
conn.open(True)
time.sleep(0.3)
synth_az.speak_text_async("тест").get()

# Google — підготовка
gclient = texttospeech.TextToSpeechClient()
audio_cfg = texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.LINEAR16, sample_rate_hertz=8000)

print(f"Продакшин тест: Azure Polina vs Google Wavenet-B | WAV 8kHz 16bit mono\n")
print(f"  {'#':<3} {'Модель':<20} {'Симв':>5} {'Час':>7} {'1й чанк':>8} Файл")
print(f"  {'─'*3} {'─'*20} {'─'*5} {'─'*7} {'─'*8} {'─'*45}")

for i, text in enumerate(TEXTS, 1):
    # ── Azure Polina streaming ──
    chunks = []
    t_first = [None]
    gen_start = [None]

    def on_synth(evt, _c=chunks, _t=t_first, _s=gen_start):
        if evt.result.audio_data:
            if _t[0] is None:
                _t[0] = time.time() - _s[0]
            _c.append(evt.result.audio_data)

    synth_az.synthesizing.connect(on_synth)
    gen_start[0] = time.time()
    synth_az.speak_text_async(text).get()
    t_az = time.time() - gen_start[0]

    pcm = b"".join(chunks)
    wav_az = wrap_pcm_to_wav(pcm, 8000)

    fname_az = f"{len(text)}sym_azure_Polina_{t_az:.3f}s.wav"
    with open(fname_az, "wb") as f:
        f.write(wav_az)

    first_az = f"{t_first[0]:.3f}с" if t_first[0] else "—"
    print(f"  {i:<3} {'Azure Polina':<20} {len(text):>5} {t_az:>6.3f}с {first_az:>8} {fname_az}")

    # ── Google Wavenet-B ──
    voice_wn = texttospeech.VoiceSelectionParams(language_code="uk-UA", name="uk-UA-Wavenet-B")
    synth_input = texttospeech.SynthesisInput(text=text)

    start = time.time()
    resp = gclient.synthesize_speech(input=synth_input, voice=voice_wn, audio_config=audio_cfg)
    t_gw = time.time() - start

    fname_gw = f"{len(text)}sym_google_WavenetB_{t_gw:.3f}s.wav"
    with open(fname_gw, "wb") as f:
        f.write(resp.audio_content)

    print(f"  {i:<3} {'Google Wavenet-B':<20} {len(text):>5} {t_gw:>6.3f}с      —   {fname_gw}")
    print()

del synth_az

print(f"{'='*60}")
print(f"  Послухайте і порівняйте!")
print(f"{'='*60}")


