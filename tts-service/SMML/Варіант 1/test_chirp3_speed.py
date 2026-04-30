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

def process_chirp_audio(audio_data):
    """Конвертація Chirp3 аудіо в WAV 8kHz"""
    if audio_data[:4] == b'RIFF':
        with io.BytesIO(audio_data) as buf:
            with wave.open(buf, 'rb') as wf:
                sr = wf.getframerate()
                pcm = wf.readframes(wf.getnframes())
        if sr != 8000:
            pcm_8k = downsample_pcm(pcm, sr, 8000)
            return wrap_pcm_to_wav(pcm_8k, 8000)
        return audio_data
    else:
        pcm_8k = downsample_pcm(audio_data, 24000, 8000)
        return wrap_pcm_to_wav(pcm_8k, 8000)

# Тексти різної довжини
TEXT_FULL = "Будь ласка, залишайтесь на лінії. Ваш дзвінок дуже важливий для нас. Перший вільний спеціаліст зʼєднається з вами найближчим часом. Орієнтовний час очікування — дві хвилини."
TEXT_SHORT = "Будь ласка, залишайтесь на лінії. Перший вільний спеціаліст зʼєднається з вами найближчим часом."
TEXT_MINI = "Будь ласка, залишайтесь на лінії. Очікуйте відповіді."

# Розбивка на 2 частини для паралельної генерації
TEXT_PART1 = "Будь ласка, залишайтесь на лінії. Ваш дзвінок дуже важливий для нас."
TEXT_PART2 = "Перший вільний спеціаліст зʼєднається з вами найближчим часом. Орієнтовний час очікування — дві хвилини."

gclient = texttospeech.TextToSpeechClient()

def chirp3_hd_generate(client, text, voice_name="uk-UA-Chirp3-HD-Leda"):
    """Генерація Chirp3-HD через streaming"""
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

def chirp3_generate(client, text, voice_name="uk-UA-Chirp3-HD-Leda"):
    """Генерація Chirp3 через batch API (не streaming)"""
    voice = texttospeech.VoiceSelectionParams(language_code="uk-UA", name=voice_name)
    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.LINEAR16,
        sample_rate_hertz=24000,
    )
    synth_input = texttospeech.SynthesisInput(text=text)
    resp = client.synthesize_speech(input=synth_input, voice=voice, audio_config=audio_config)
    return resp.audio_content

print(f"{'='*70}")
print(f"  Оптимізація швидкості Chirp3-HD Leda")
print(f"{'='*70}\n")
print(f"  {'#':<3} {'Тест':<40} {'Симв':>5} {'Час':>7} Файл")
print(f"  {'─'*3} {'─'*40} {'─'*5} {'─'*7} {'─'*40}")

# ═══════════════════════════════════════
# Тест 1: Базовий (повний текст, streaming)
# ═══════════════════════════════════════
start = time.time()
audio = chirp3_hd_generate(gclient, TEXT_FULL)
t = time.time() - start
wav = process_chirp_audio(audio)
fname = "speed_1_base_full.wav"
with open(fname, "wb") as f:
    f.write(wav)
print(f"  1   {'Базовий (повний текст)':<40} {len(TEXT_FULL):>5} {t:>6.3f}с {fname}")

# ═══════════════════════════════════════
# Тест 2: Коротший текст (92 симв)
# ═══════════════════════════════════════
start = time.time()
audio = chirp3_hd_generate(gclient, TEXT_SHORT)
t = time.time() - start
wav = process_chirp_audio(audio)
fname = "speed_2_short.wav"
with open(fname, "wb") as f:
    f.write(wav)
print(f"  2   {'Коротший текст':<40} {len(TEXT_SHORT):>5} {t:>6.3f}с {fname}")

# ═══════════════════════════════════════
# Тест 3: Міні текст (55 симв)
# ═══════════════════════════════════════
start = time.time()
audio = chirp3_hd_generate(gclient, TEXT_MINI)
t = time.time() - start
wav = process_chirp_audio(audio)
fname = "speed_3_mini.wav"
with open(fname, "wb") as f:
    f.write(wav)
print(f"  3   {'Міні текст':<40} {len(TEXT_MINI):>5} {t:>6.3f}с {fname}")

# ═══════════════════════════════════════
# Тест 4: Паралельна генерація (2 частини)
# ═══════════════════════════════════════
start = time.time()

# Два окремих клієнти для паралельності
gclient2 = texttospeech.TextToSpeechClient()

with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
    f1 = executor.submit(chirp3_hd_generate, gclient, TEXT_PART1)
    f2 = executor.submit(chirp3_hd_generate, gclient2, TEXT_PART2)
    audio1 = f1.result()
    audio2 = f2.result()

t = time.time() - start

# Склеюємо PCM
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

pcm1 = extract_pcm_8k(audio1)
pcm2 = extract_pcm_8k(audio2)
# Додаємо 200мс тиші між частинами (200мс × 8000 = 1600 samples × 2 bytes)
silence = b'\x00' * 3200
combined_pcm = pcm1 + silence + pcm2
wav = wrap_pcm_to_wav(combined_pcm, 8000)

fname = "speed_4_parallel.wav"
with open(fname, "wb") as f:
    f.write(wav)
print(f"  4   {'Паралельно (2 частини)':<40} {len(TEXT_FULL):>5} {t:>6.3f}с {fname}")

# ═══════════════════════════════════════
# Тест 5: Chirp3 (без HD) через batch API
# ═══════════════════════════════════════
chirp3_non_hd_voices = [
    "uk-UA-Chirp3-HD-Leda",  # спробуємо batch замість streaming
]
start = time.time()
try:
    audio = chirp3_generate(gclient, TEXT_FULL, "uk-UA-Chirp3-HD-Leda")
    t = time.time() - start
    wav = process_chirp_audio(audio)
    fname = "speed_5_batch_api.wav"
    with open(fname, "wb") as f:
        f.write(wav)
    print(f"  5   {'Chirp3-HD batch API (не streaming)':<40} {len(TEXT_FULL):>5} {t:>6.3f}с {fname}")
except Exception as e:
    t = time.time() - start
    print(f"  5   {'Chirp3-HD batch API (не streaming)':<40} {len(TEXT_FULL):>5} ПОМИЛКА: {str(e)[:60]}")

# ═══════════════════════════════════════
# Тест 6: Повторний запит (gRPC канал вже відкритий)
# ═══════════════════════════════════════
# Перший запит вже "прогрів" канал, тепер міряємо повторний
start = time.time()
audio = chirp3_hd_generate(gclient, TEXT_FULL)
t = time.time() - start
wav = process_chirp_audio(audio)
fname = "speed_6_warm_channel.wav"
with open(fname, "wb") as f:
    f.write(wav)
print(f"  6   {'Повторний (прогрітий канал)':<40} {len(TEXT_FULL):>5} {t:>6.3f}с {fname}")

# ═══════════════════════════════════════
# Тест 7: Ще 3 повторних запити для статистики
# ═══════════════════════════════════════
times = []
for i in range(3):
    start = time.time()
    audio = chirp3_hd_generate(gclient, TEXT_FULL)
    t = time.time() - start
    times.append(t)
    time.sleep(0.1)

avg = sum(times) / len(times)
print(f"  7   {'3× повторних (avg)':<40} {len(TEXT_FULL):>5} {avg:>6.3f}с ({', '.join(f'{t:.3f}' for t in times)})")

# ═══════════════════════════════════════
# Тест 8: Chirp3 не-HD варіанти (якщо є)
# ═══════════════════════════════════════
non_hd_voices = [
    ("uk-UA-Chirp3-Leda", "Chirp3 Leda (без HD)"),
    ("uk-UA-Chirp-Leda", "Chirp Leda (без 3)"),
]
for vname, label in non_hd_voices:
    start = time.time()
    try:
        voice = texttospeech.VoiceSelectionParams(language_code="uk-UA", name=vname)
        config = texttospeech.StreamingSynthesizeConfig(voice=voice)
        audio = b""
        def req_gen():
            yield texttospeech.StreamingSynthesizeRequest(streaming_config=config)
            yield texttospeech.StreamingSynthesizeRequest(
                input=texttospeech.StreamingSynthesisInput(text=TEXT_FULL))
        for resp in gclient.streaming_synthesize(req_gen()):
            audio += resp.audio_content
        t = time.time() - start
        wav = process_chirp_audio(audio)
        fname = f"speed_8_{vname.split('-')[-1]}_nonHD.wav"
        with open(fname, "wb") as f:
            f.write(wav)
        print(f"  8   {label:<40} {len(TEXT_FULL):>5} {t:>6.3f}с {fname}")
    except Exception as e:
        t = time.time() - start
        print(f"  8   {label:<40} {len(TEXT_FULL):>5} Не існує")

# ═══════════════════════════════════════
# Тест 9: Time to first byte (TTFB)
# ═══════════════════════════════════════
voice = texttospeech.VoiceSelectionParams(language_code="uk-UA", name="uk-UA-Chirp3-HD-Leda")
config = texttospeech.StreamingSynthesizeConfig(voice=voice)
start = time.time()
ttfb = None
audio = b""

def req_ttfb():
    yield texttospeech.StreamingSynthesizeRequest(streaming_config=config)
    yield texttospeech.StreamingSynthesizeRequest(
        input=texttospeech.StreamingSynthesisInput(text=TEXT_FULL))

for resp in gclient.streaming_synthesize(req_ttfb()):
    if ttfb is None:
        ttfb = time.time() - start
    audio += resp.audio_content
t_total = time.time() - start

print(f"\n  TTFB (перший байт): {ttfb:.3f}с")
print(f"  Повний час:         {t_total:.3f}с")
print(f"  Передача аудіо:     {t_total - ttfb:.3f}с")

print(f"\n{'='*70}")
print(f"  Висновок:")
print(f"  Повний текст ({len(TEXT_FULL)} симв) — базовий час Chirp3-HD")
print(f"  Короткий ({len(TEXT_SHORT)} симв) — чи зменшується пропорційно?")
print(f"  Міні ({len(TEXT_MINI)} симв) — мінімальний можливий час")
print(f"  Паралельно — чи дає виграш?")
print(f"{'='*70}")

