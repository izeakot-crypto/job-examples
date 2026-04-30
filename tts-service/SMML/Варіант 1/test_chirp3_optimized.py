import sys, io, time, wave, os, struct, concurrent.futures
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = r"[USER_HOME]\Downloads\tts-488311-d5a1cbf88094.json"

from google.cloud import texttospeech
from google.api_core.client_options import ClientOptions

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

TEXT = "Дякуємо за дзвінок до компанії Окі-Токі. На жаль, всі оператори зараз зайняті. Будь ласка, залишайтесь на лінії, вам відповідять найближчим часом."
PART1 = "Дякуємо за дзвінок до компанії Окі-Токі. На жаль, всі оператори зараз зайняті."
PART2 = "Будь ласка, залишайтесь на лінії, вам відповідять найближчим часом."

VOICE = "uk-UA-Chirp3-HD-Leda"

print(f"{'='*70}")
print(f"  Оптимізація Chirp3-HD | {len(TEXT)} символів | 5 методів")
print(f"{'='*70}\n")

# ═══════════════════════════════════════
# 1. Без оптимізації — холодний запит
# ═══════════════════════════════════════
print("  1. Холодний запит (новий клієнт, без прогріву)")
client_cold = texttospeech.TextToSpeechClient()
start = time.time()
audio = chirp3_stream(client_cold, TEXT, VOICE)
t1 = time.time() - start
wav = wrap_pcm_to_wav(extract_pcm_8k(audio), 8000)
with open("opt_1_cold.wav", "wb") as f:
    f.write(wav)
print(f"     Час: {t1:.3f}с\n")

# ═══════════════════════════════════════
# 2. Прогрітий gRPC канал (як WebSocket warmup)
# ═══════════════════════════════════════
print("  2. Прогрітий gRPC канал (warmup запит перед основним)")
client_warm = texttospeech.TextToSpeechClient()
# Прогрів — маленький запит щоб відкрити з'єднання
chirp3_stream(client_warm, "тест", VOICE)

start = time.time()
audio = chirp3_stream(client_warm, TEXT, VOICE)
t2 = time.time() - start
wav = wrap_pcm_to_wav(extract_pcm_8k(audio), 8000)
with open("opt_2_warm.wav", "wb") as f:
    f.write(wav)
print(f"     Час: {t2:.3f}с (виграш: {(1-t2/t1)*100:+.0f}%)\n")

# ═══════════════════════════════════════
# 3. Прогрітий + паралельно 2 частини
# ═══════════════════════════════════════
print("  3. Прогрітий + паралельно 2 частини")
c1 = texttospeech.TextToSpeechClient()
c2 = texttospeech.TextToSpeechClient()
# Прогрів обох
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
    ex.submit(chirp3_stream, c1, "тест", VOICE).result()
    ex.submit(chirp3_stream, c2, "тест", VOICE).result()

start = time.time()
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
    f1 = ex.submit(chirp3_stream, c1, PART1, VOICE)
    f2 = ex.submit(chirp3_stream, c2, PART2, VOICE)
    a1, a2 = f1.result(), f2.result()
t3 = time.time() - start

pcm1, pcm2 = extract_pcm_8k(a1), extract_pcm_8k(a2)
silence = b'\x00' * 2400
wav = wrap_pcm_to_wav(pcm1 + silence + pcm2, 8000)
with open("opt_3_warm_parallel2.wav", "wb") as f:
    f.write(wav)
print(f"     Час: {t3:.3f}с (виграш: {(1-t3/t1)*100:+.0f}%)\n")

# ═══════════════════════════════════════
# 4. Європейський endpoint (ближче до нас)
# ═══════════════════════════════════════
print("  4. Європейський endpoint (europe-west4)")
try:
    eu_options = ClientOptions(api_endpoint="europe-west4-texttospeech.googleapis.com")
    client_eu = texttospeech.TextToSpeechClient(client_options=eu_options)
    # Прогрів
    chirp3_stream(client_eu, "тест", VOICE)

    start = time.time()
    audio = chirp3_stream(client_eu, TEXT, VOICE)
    t4 = time.time() - start
    wav = wrap_pcm_to_wav(extract_pcm_8k(audio), 8000)
    with open("opt_4_eu_endpoint.wav", "wb") as f:
        f.write(wav)
    print(f"     Час: {t4:.3f}с (виграш: {(1-t4/t1)*100:+.0f}%)\n")
except Exception as e:
    t4 = -1
    print(f"     Помилка: {str(e)[:60]}\n")

# ═══════════════════════════════════════
# 5. EU endpoint + паралельно 2 частини (ВСЕ РАЗОМ)
# ═══════════════════════════════════════
print("  5. EU endpoint + прогрів + паралельно 2 частини (MAX)")
try:
    eu1 = texttospeech.TextToSpeechClient(client_options=ClientOptions(api_endpoint="europe-west4-texttospeech.googleapis.com"))
    eu2 = texttospeech.TextToSpeechClient(client_options=ClientOptions(api_endpoint="europe-west4-texttospeech.googleapis.com"))
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
        ex.submit(chirp3_stream, eu1, "тест", VOICE).result()
        ex.submit(chirp3_stream, eu2, "тест", VOICE).result()

    start = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
        f1 = ex.submit(chirp3_stream, eu1, PART1, VOICE)
        f2 = ex.submit(chirp3_stream, eu2, PART2, VOICE)
        a1, a2 = f1.result(), f2.result()
    t5 = time.time() - start

    pcm1, pcm2 = extract_pcm_8k(a1), extract_pcm_8k(a2)
    wav = wrap_pcm_to_wav(pcm1 + silence + pcm2, 8000)
    with open("opt_5_eu_parallel2.wav", "wb") as f:
        f.write(wav)
    print(f"     Час: {t5:.3f}с (виграш: {(1-t5/t1)*100:+.0f}%)\n")
except Exception as e:
    t5 = -1
    print(f"     Помилка: {str(e)[:60]}\n")

# ═══════════════════════════════════════
# Стабільність найкращого — 5 запусків
# ═══════════════════════════════════════
print("  6. Стабільність найкращого методу (5 запусків)")
methods = {"cold": t1, "warm": t2, "warm+parallel": t3}
if t4 > 0:
    methods["EU"] = t4
if t5 > 0:
    methods["EU+parallel"] = t5

best_name = min(methods, key=methods.get)
print(f"     Найкращий: {best_name}\n")

times = []
for i in range(5):
    if "EU" in best_name and "parallel" in best_name:
        start = time.time()
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
            f1 = ex.submit(chirp3_stream, eu1, PART1, VOICE)
            f2 = ex.submit(chirp3_stream, eu2, PART2, VOICE)
            f1.result(); f2.result()
        t = time.time() - start
    elif "EU" in best_name:
        start = time.time()
        chirp3_stream(client_eu, TEXT, VOICE)
        t = time.time() - start
    elif "parallel" in best_name:
        start = time.time()
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
            f1 = ex.submit(chirp3_stream, c1, PART1, VOICE)
            f2 = ex.submit(chirp3_stream, c2, PART2, VOICE)
            f1.result(); f2.result()
        t = time.time() - start
    else:
        start = time.time()
        chirp3_stream(client_warm, TEXT, VOICE)
        t = time.time() - start
    times.append(t)
    print(f"     Запуск {i+1}: {t:.3f}с")

avg = sum(times) / len(times)
print(f"\n     Середній: {avg:.3f}с | Мін: {min(times):.3f}с | Макс: {max(times):.3f}с")

# ═══════════════════════════════════════
# ПІДСУМОК
# ═══════════════════════════════════════
print(f"\n{'='*70}")
print(f"  ПІДСУМОК ({len(TEXT)} символів):")
print(f"  {'─'*50}")
print(f"  1. Холодний запит:              {t1:.3f}с")
print(f"  2. Прогрітий gRPC:              {t2:.3f}с")
print(f"  3. Прогрів + паралель ×2:       {t3:.3f}с")
if t4 > 0:
    print(f"  4. EU endpoint:                 {t4:.3f}с")
if t5 > 0:
    print(f"  5. EU + паралель ×2 (MAX):      {t5:.3f}с")
print(f"  {'─'*50}")
print(f"  Стабільний результат (avg 5x):  {avg:.3f}с")
print(f"{'='*70}")

