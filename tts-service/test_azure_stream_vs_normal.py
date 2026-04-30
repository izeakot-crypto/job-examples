import sys, io, time, wave
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
import azure.cognitiveservices.speech as speechsdk

AZURE_KEY = "YOUR_SECRET_TOKEN"
AZURE_REGION = "westeurope"
VOICE = "uk-UA-PolinaNeural"

TEXTS = [
    "Дякую за дзвінок! Зачекайте, зʼєдную вас з оператором.",
    "Добрий день! Мене звати Оксана, я ваш віртуальний помічник. Чим можу допомогти?",
    "Ваш запит прийнято. Очікуйте відповідь оператора протягом хвилини. Дякуємо за терпіння, ми цінуємо ваш час.",
    "Привіт! На жаль, всі оператори зараз зайняті. Ваш дзвінок дуже важливий для нас. Будь ласка, залишайтесь на лінії, і перший вільний оператор відповість вам найближчим часом.",
    "Шановний клієнте, дякуємо що звернулися до нашої компанії Окі-Токі. На даний момент ми обробляємо вашу заявку. Орієнтовний час очікування складає три хвилини. Якщо бажаєте, можете залишити голосове повідомлення, і ми передзвонимо вам протягом години.",
]

def wrap_pcm_to_wav(pcm_data, sample_rate=8000, channels=1, sample_width=2):
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_data)
    return buf.getvalue()

# ── Звичайний синтезатор (Riff — з заголовком) ──
config_normal = speechsdk.SpeechConfig(subscription=AZURE_KEY, region=AZURE_REGION)
config_normal.speech_synthesis_voice_name = VOICE
config_normal.set_speech_synthesis_output_format(
    speechsdk.SpeechSynthesisOutputFormat.Riff8Khz16BitMonoPcm
)
synth_normal = speechsdk.SpeechSynthesizer(speech_config=config_normal, audio_config=None)
conn1 = speechsdk.Connection.from_speech_synthesizer(synth_normal)
conn1.open(True)
time.sleep(0.5)
synth_normal.speak_text_async("тест").get()

# ── Стрімінг синтезатор (Raw — без заголовка) ──
config_stream = speechsdk.SpeechConfig(subscription=AZURE_KEY, region=AZURE_REGION)
config_stream.speech_synthesis_voice_name = VOICE
config_stream.set_speech_synthesis_output_format(
    speechsdk.SpeechSynthesisOutputFormat.Raw8Khz16BitMonoPcm
)
synth_stream = speechsdk.SpeechSynthesizer(speech_config=config_stream, audio_config=None)
conn2 = speechsdk.Connection.from_speech_synthesizer(synth_stream)
conn2.open(True)
time.sleep(0.5)
synth_stream.speak_text_async("тест").get()

print(f"Голос: {VOICE} | Формат: WAV 8kHz 16bit mono\n")
print(f"  {'#':<3} {'Символів':>8} {'Звичайний':>10} {'Стрімінг':>10} {'1й чанк':>8} {'Різниця':>10}")
print(f"  {'─'*3} {'─'*8} {'─'*10} {'─'*10} {'─'*8} {'─'*10}")

for i, text in enumerate(TEXTS):
    # ── Звичайний ──
    start = time.time()
    result = synth_normal.speak_text_async(text).get()
    t_normal = time.time() - start
    fname_n = f"svn_{i+1}_normal.wav"
    with open(fname_n, "wb") as f:
        f.write(result.audio_data)

    # ── Стрімінг через Synthesizing event (Raw PCM) ──
    chunks = []
    t_first_chunk = [None]
    gen_start = [None]

    def on_synthesizing(evt, _chunks=chunks, _t=t_first_chunk, _s=gen_start):
        if evt.result.audio_data:
            if _t[0] is None:
                _t[0] = time.time() - _s[0]
            _chunks.append(evt.result.audio_data)

    chunks.clear()
    t_first_chunk[0] = None
    synth_stream.synthesizing.connect(on_synthesizing)

    gen_start[0] = time.time()
    result2 = synth_stream.speak_text_async(text).get()
    t_stream = time.time() - gen_start[0]

    pcm_data = b"".join(chunks)
    wav_data = wrap_pcm_to_wav(pcm_data)
    fname_s = f"svn_{i+1}_stream.wav"
    with open(fname_s, "wb") as f:
        f.write(wav_data)

    first_ms = t_first_chunk[0] if t_first_chunk[0] else 0
    ratio = t_normal / t_stream if t_stream > 0 else 0
    print(f"  {i+1:<3} {len(text):>8} {t_normal:>9.3f}с {t_stream:>9.3f}с {first_ms:>7.3f}с {ratio:>9.1f}x")

del synth_normal, synth_stream
print(f"\nФайли: svn_1..5_normal.wav та svn_1..5_stream.wav")

