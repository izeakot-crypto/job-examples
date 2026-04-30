import sys, io, time, wave, os, struct, concurrent.futures
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = r"[USER_HOME]\Downloads\tts-488311-d5a1cbf88094.json"

from google.cloud import texttospeech

def wrap_pcm_to_wav(pcm_data, sample_rate=8000):
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_data)
    return buf.getvalue()

def downsample_pcm(pcm_data, from_rate, to_rate):
    samples = struct.unpack(f'<{len(pcm_data)//2}h', pcm_data)
    ratio = from_rate / to_rate
    new_len = int(len(samples) / ratio)
    resampled = [samples[int(i * ratio)] for i in range(new_len) if int(i * ratio) < len(samples)]
    return struct.pack(f'<{len(resampled)}h', *resampled)

def extract_pcm_8k(audio_data):
    if audio_data[:4] == b'RIFF':
        with io.BytesIO(audio_data) as buf:
            with wave.open(buf, 'rb') as wf:
                sr = wf.getframerate()
                pcm = wf.readframes(wf.getnframes())
        if sr != 8000:
            return downsample_pcm(pcm, sr, 8000)
        return pcm
    else:
        return downsample_pcm(audio_data, 24000, 8000)

def chirp3_stream(client, text, voice_name="uk-UA-Chirp3-HD-Leda"):
    voice = texttospeech.VoiceSelectionParams(language_code="uk-UA", name=voice_name)
    config = texttospeech.StreamingSynthesizeConfig(voice=voice)
    audio = b""
    def req():
        yield texttospeech.StreamingSynthesizeRequest(streaming_config=config)
        yield texttospeech.StreamingSynthesizeRequest(
            input=texttospeech.StreamingSynthesisInput(text=text))
    for resp in client.streaming_synthesize(req()):
        audio += resp.audio_content
    return audio

# ═══════════════════════════════════════
# 3 емоції з текстами ~150 символів
# ═══════════════════════════════════════
EMOTIONS = {
    "happy": {
        "text": "Чудові новини! Вашу проблему повністю вирішено! Замовлення вже в дорозі і буде у вас завтра вранці. Дякуємо за терпіння, і гарного вам дня!",
        "parts": [
            "Чудові новини! Вашу проблему повністю вирішено!",
            "Замовлення вже в дорозі і буде у вас завтра вранці.",
            "Дякуємо за терпіння, і гарного вам дня!",
        ],
    },
    "sad": {
        "text": "На жаль, ми змушені відмовити у вашому запиті. Нам дуже прикро, але повернення коштів неможливе після закінчення гарантійного терміну. Вибачте.",
        "parts": [
            "На жаль, ми змушені відмовити у вашому запиті.",
            "Нам дуже прикро, але повернення коштів неможливе після закінчення гарантійного терміну.",
            "Вибачте.",
        ],
    },
    "calm": {
        "text": "Будь ласка, залишайтесь на лінії. Ваш дзвінок дуже важливий для нас. Перший вільний спеціаліст зʼєднається з вами найближчим часом. Очікуйте.",
        "parts": [
            "Будь ласка, залишайтесь на лінії. Ваш дзвінок дуже важливий для нас.",
            "Перший вільний спеціаліст зʼєднається з вами найближчим часом.",
            "Очікуйте.",
        ],
    },
}

VOICE = "uk-UA-Chirp3-HD-Leda"
VOICE_SHORT = "Leda"

# Прогрів 3 клієнтів
print("Прогрів 3 gRPC клієнтів...")
clients = [texttospeech.TextToSpeechClient() for _ in range(3)]

def warmup(client):
    voice = texttospeech.VoiceSelectionParams(language_code="uk-UA", name=VOICE)
    config = texttospeech.StreamingSynthesizeConfig(voice=voice)
    def req():
        yield texttospeech.StreamingSynthesizeRequest(streaming_config=config)
        yield texttospeech.StreamingSynthesizeRequest(
            input=texttospeech.StreamingSynthesisInput(text="тест"))
    for resp in client.streaming_synthesize(req()):
        pass

with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:
    list(ex.map(warmup, clients))
print("Готово!\n")

print(f"{'='*70}")
print(f"  Google Chirp3-HD | Голос: {VOICE_SHORT} (жін)")
print(f"  Метод: паралельна генерація 3 частин (3 gRPC клієнти)")
print(f"  Формат: WAV 8kHz 16bit mono")
print(f"{'='*70}\n")

for emo_name, emo in EMOTIONS.items():
    text = emo["text"]
    parts = emo["parts"]

    print(f"  ── {emo_name.upper()} ({len(text)} симв) ──")
    print(f"  \"{text[:80]}...\"")

    # Паралельна генерація 3 частин
    start = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:
        futures = [ex.submit(chirp3_stream, clients[i], parts[i], VOICE) for i in range(3)]
        audios = [f.result() for f in futures]
    gen_time = time.time() - start

    # Склейка PCM з тишею 150мс між частинами
    silence = b'\x00' * 2400  # 150мс × 8000Hz × 2 bytes
    pcm_parts = [extract_pcm_8k(a) for a in audios]
    combined = pcm_parts[0]
    for p in pcm_parts[1:]:
        combined += silence + p
    wav = wrap_pcm_to_wav(combined, 8000)

    fname = f"{emo_name}_{gen_time:.3f}s_GoogleChirp3HD_parallel3_{VOICE_SHORT}.wav"
    with open(fname, "wb") as f:
        f.write(wav)

    print(f"  Час: {gen_time:.3f}с | Файл: {fname}")
    print(f"  Розмір: {len(wav)} байт\n")

print(f"{'='*70}")
print(f"  TTS: Google Cloud Text-to-Speech")
print(f"  Модель: Chirp3-HD (найновіша, автоемоції)")
print(f"  Голос: {VOICE} ({VOICE_SHORT}, жіночий)")
print(f"  Метод: паралельна генерація 3 частин × 3 gRPC клієнти")
print(f"  API: streaming_synthesize")
print(f"{'='*70}")

