import sys, io, time, wave, os, threading
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = r"[USER_HOME]\Downloads\tts-488311-d5a1cbf88094.json"

from openai import OpenAI
import azure.cognitiveservices.speech as speechsdk
from google.cloud import texttospeech

OPENAI_KEY = "YOUR_OPENAI_API_KEY"
AZURE_KEY = "YOUR_SECRET_TOKEN"
AZURE_REGION = "westeurope"

llm = OpenAI(api_key=OPENAI_KEY)

def wrap_pcm_to_wav(pcm_data, sample_rate=8000):
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_data)
    return buf.getvalue()

# Azure — підготовка з прогрівом
az_config = speechsdk.SpeechConfig(subscription=AZURE_KEY, region=AZURE_REGION)
az_config.speech_synthesis_voice_name = "uk-UA-PolinaNeural"
az_config.set_speech_synthesis_output_format(speechsdk.SpeechSynthesisOutputFormat.Raw8Khz16BitMonoPcm)
az_synth = speechsdk.SpeechSynthesizer(speech_config=az_config, audio_config=None)
az_conn = speechsdk.Connection.from_speech_synthesizer(az_synth)
az_conn.open(True)
time.sleep(0.3)
az_synth.speak_text_async("тест").get()

# Google — підготовка
gclient = texttospeech.TextToSpeechClient()

BOT_SYSTEM = """Ти — віртуальний помічник кол-центру Окі-Токі на імʼя Оксана.
Відповідай українською, коротко (2-3 речення), ввічливо, емпатично.
Використовуй пунктуацію для емоцій: ! для радості, ... для співчуття, — для пауз."""

# Тестовий діалог
DIALOG = [
    {"role": "user", "content": "Алло! Де моє замовлення?! Я чекаю вже тиждень! Це неприпустимо!"},
]

print(f"{'='*70}")
print(f"  ТЕСТ ШВИДКОСТІ: 5 варіантів оптимізації")
print(f"{'='*70}")
print(f"  Діалог: клієнт злий через затримку доставки\n")

# ═══════════════════════════════════════
# Варіант 0: Оригінал (2 GPT запити + TTS) — baseline
# ═══════════════════════════════════════
print(f"── Варіант 0: Оригінал (GPT відповідь + GPT SSML + Azure TTS) ──")
t0_start = time.time()

resp1 = llm.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "system", "content": BOT_SYSTEM}] + DIALOG,
    max_tokens=150, temperature=0.7,
)
bot_text = resp1.choices[0].message.content
t0_gpt1 = time.time() - t0_start

t0_s2 = time.time()
resp2 = llm.chat.completions.create(
    model="gpt-4o-mini",
    messages=[
        {"role": "system", "content": "Додай SSML розмітку для Azure TTS uk-UA-PolinaNeural. Повертай тільки SSML."},
        {"role": "user", "content": bot_text},
    ],
    max_tokens=300, temperature=0.3,
)
t0_gpt2 = time.time() - t0_s2

t0_s3 = time.time()
az_synth.speak_text_async(bot_text).get()
t0_tts = time.time() - t0_s3
t0_total = time.time() - t0_start

print(f"  GPT1: {t0_gpt1:.2f}с + GPT2: {t0_gpt2:.2f}с + TTS: {t0_tts:.2f}с = {t0_total:.2f}с")
print(f"  Відповідь: {bot_text[:80]}")

# ═══════════════════════════════════════
# Варіант 1: Один GPT запит (бот одразу відповідає)
# ═══════════════════════════════════════
print(f"\n── Варіант 1: Один GPT запит + Azure TTS ──")
t1_start = time.time()

resp = llm.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "system", "content": BOT_SYSTEM}] + DIALOG,
    max_tokens=150, temperature=0.7,
)
text_v1 = resp.choices[0].message.content
t1_gpt = time.time() - t1_start

t1_s2 = time.time()
result = az_synth.speak_text_async(text_v1).get()
t1_tts = time.time() - t1_s2
t1_total = time.time() - t1_start

wav_v1 = wrap_pcm_to_wav(result.audio_data)
with open("v1_one_gpt_azure.wav", "wb") as f:
    f.write(wav_v1)
print(f"  GPT: {t1_gpt:.2f}с + TTS: {t1_tts:.2f}с = {t1_total:.2f}с")
print(f"  Відповідь: {text_v1[:80]}")

# ═══════════════════════════════════════
# Варіант 2: Шаблони (без GPT для SSML) + Azure
# ═══════════════════════════════════════
print(f"\n── Варіант 2: GPT + шаблон SSML + Azure TTS ──")
t2_start = time.time()

resp = llm.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "system", "content": BOT_SYSTEM}] + DIALOG,
    max_tokens=150, temperature=0.7,
)
text_v2 = resp.choices[0].message.content
t2_gpt = time.time() - t2_start

# Шаблонний SSML (0мс — просто string format)
t2_s2 = time.time()
# Визначаємо емоцію по ключових словах
lower = text_v2.lower()
if any(w in lower for w in ["вибач", "шкода", "прикро", "на жаль"]):
    rate = "90%"
elif any(w in lower for w in ["чудов", "радий", "вітаю", "молодц"]):
    rate = "105%"
else:
    rate = "95%"

# Розбиваємо на речення і додаємо паузи
sentences = [s.strip() for s in text_v2.replace("!", "!|").replace(".", ".|").replace("?", "?|").split("|") if s.strip()]
ssml_parts = []
for s in sentences:
    ssml_parts.append(f'<prosody rate="{rate}">{s}</prosody>')
    ssml_parts.append('<break time="250ms"/>')

ssml_v2 = f"""<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='uk-UA'>
<voice name='uk-UA-PolinaNeural'>
{"".join(ssml_parts)}
</voice></speak>"""
t2_template = time.time() - t2_s2

t2_s3 = time.time()
result2 = az_synth.speak_ssml_async(ssml_v2).get()
t2_tts = time.time() - t2_s3
t2_total = time.time() - t2_start

if result2.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
    wav_v2 = wrap_pcm_to_wav(result2.audio_data)
    with open("v2_template_azure.wav", "wb") as f:
        f.write(wav_v2)
print(f"  GPT: {t2_gpt:.2f}с + шаблон: {t2_template:.4f}с + TTS: {t2_tts:.2f}с = {t2_total:.2f}с")

# ═══════════════════════════════════════
# Варіант 3: GPT + Chirp3-HD (без SSML, сам розуміє емоції)
# ═══════════════════════════════════════
print(f"\n── Варіант 3: GPT + Google Chirp3-HD (без SSML) ──")
t3_start = time.time()

resp = llm.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "system", "content": BOT_SYSTEM}] + DIALOG,
    max_tokens=150, temperature=0.7,
)
text_v3 = resp.choices[0].message.content
t3_gpt = time.time() - t3_start

t3_s2 = time.time()
voice_chirp = texttospeech.VoiceSelectionParams(language_code="uk-UA", name="uk-UA-Chirp3-HD-Leda")
streaming_config = texttospeech.StreamingSynthesizeConfig(voice=voice_chirp)

audio_data = b""
t_first_chirp = None

def req_gen():
    yield texttospeech.StreamingSynthesizeRequest(streaming_config=streaming_config)
    yield texttospeech.StreamingSynthesizeRequest(
        input=texttospeech.StreamingSynthesisInput(text=text_v3))

import struct
def downsample_pcm(pcm_data, from_rate, to_rate):
    samples = struct.unpack(f'<{len(pcm_data)//2}h', pcm_data)
    ratio = from_rate / to_rate
    new_len = int(len(samples) / ratio)
    resampled = [samples[int(i * ratio)] for i in range(new_len) if int(i * ratio) < len(samples)]
    return struct.pack(f'<{len(resampled)}h', *resampled)

responses = gclient.streaming_synthesize(req_gen())
for response in responses:
    if t_first_chirp is None:
        t_first_chirp = time.time() - t3_s2
    audio_data += response.audio_content
t3_tts = time.time() - t3_s2
t3_total = time.time() - t3_start

if audio_data[:4] == b'RIFF':
    with io.BytesIO(audio_data) as buf:
        with wave.open(buf, 'rb') as wf:
            sr = wf.getframerate()
            pcm = wf.readframes(wf.getnframes())
    if sr != 8000:
        pcm_8k = downsample_pcm(pcm, sr, 8000)
        wav_v3 = wrap_pcm_to_wav(pcm_8k, 8000)
    else:
        wav_v3 = audio_data
else:
    pcm_8k = downsample_pcm(audio_data, 24000, 8000)
    wav_v3 = wrap_pcm_to_wav(pcm_8k, 8000)

with open("v3_chirp3_no_ssml.wav", "wb") as f:
    f.write(wav_v3)
print(f"  GPT: {t3_gpt:.2f}с + Chirp3 TTS: {t3_tts:.2f}с (1й чанк: {t_first_chirp:.2f}с) = {t3_total:.2f}с")

# ═══════════════════════════════════════
# Варіант 4: Кеш типових фраз + Azure
# ═══════════════════════════════════════
print(f"\n── Варіант 4: Кеш типових фраз (без GPT) + Azure TTS ──")

# Заздалегідь підготовлені відповіді для типових ситуацій
CACHE = {
    "angry_delivery": "Прошу вибачення за затримку. Я розумію ваше невдоволення — зараз перевірю статус замовлення. Зачекайте, будь ласка, хвильку.",
    "greeting": "Добрий день! Раді вас чути! Чим можу допомогти?",
    "waiting": "Залишайтесь на лінії, будь ласка. Оператор відповість найближчим часом.",
}

t4_start = time.time()
# Пошук в кеші — миттєвий
cached_text = CACHE["angry_delivery"]
t4_cache = time.time() - t4_start

t4_s2 = time.time()
result4 = az_synth.speak_text_async(cached_text).get()
t4_tts = time.time() - t4_s2
t4_total = time.time() - t4_start

wav_v4 = wrap_pcm_to_wav(result4.audio_data)
with open("v4_cache_azure.wav", "wb") as f:
    f.write(wav_v4)
print(f"  Кеш: {t4_cache:.4f}с + TTS: {t4_tts:.2f}с = {t4_total:.2f}с")

# ═══════════════════════════════════════
# Варіант 5: GPT streaming → Azure TTS паралельно
# ═══════════════════════════════════════
print(f"\n── Варіант 5: GPT streaming → збираємо текст → Azure TTS ──")
t5_start = time.time()
t5_first_token = None

stream = llm.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "system", "content": BOT_SYSTEM}] + DIALOG,
    max_tokens=150, temperature=0.7,
    stream=True,
)

full_text = ""
for chunk in stream:
    if chunk.choices[0].delta.content:
        if t5_first_token is None:
            t5_first_token = time.time() - t5_start
        full_text += chunk.choices[0].delta.content

t5_gpt = time.time() - t5_start

# Відразу в Azure TTS
t5_s2 = time.time()
result5 = az_synth.speak_text_async(full_text).get()
t5_tts = time.time() - t5_s2
t5_total = time.time() - t5_start

wav_v5 = wrap_pcm_to_wav(result5.audio_data)
with open("v5_stream_gpt_azure.wav", "wb") as f:
    f.write(wav_v5)
print(f"  GPT stream: {t5_gpt:.2f}с (1й токен: {t5_first_token:.2f}с) + TTS: {t5_tts:.2f}с = {t5_total:.2f}с")
print(f"  Відповідь: {full_text[:80]}")

del az_synth

# ═══════════════════════════════════════
# ФІНАЛЬНА ТАБЛИЦЯ
# ═══════════════════════════════════════
print(f"\n{'='*70}")
print(f"  ФІНАЛЬНА ТАБЛИЦЯ")
print(f"{'='*70}")
print(f"  {'Варіант':<45} {'Час':>7}")
print(f"  {'─'*45} {'─'*7}")
print(f"  {'0. Оригінал (2×GPT + Azure)':<45} {t0_total:>6.2f}с")
print(f"  {'1. Один GPT + Azure':<45} {t1_total:>6.2f}с")
print(f"  {'2. GPT + шаблон SSML + Azure':<45} {t2_total:>6.02f}с")
print(f"  {'3. GPT + Chirp3-HD (без SSML)':<45} {t3_total:>6.2f}с")
print(f"  {'4. Кеш (без GPT) + Azure':<45} {t4_total:>6.2f}с")
print(f"  {'5. GPT streaming + Azure':<45} {t5_total:>6.2f}с")



