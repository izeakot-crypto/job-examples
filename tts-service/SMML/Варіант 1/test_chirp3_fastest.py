import sys, io, time, wave, os, struct, concurrent.futures, threading
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

def process_chirp_audio(audio_data):
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

# ═══════════════════════════════════════
# Текст ~150 символів
# ═══════════════════════════════════════
TEXT = "Дякуємо за дзвінок до компанії Окі-Токі. На жаль, всі оператори зараз зайняті. Будь ласка, залишайтесь на лінії, вам відповідять найближчим часом."
print(f"Текст: {len(TEXT)} символів")
print(f"\"{TEXT}\"\n")

# Розбивка на 2 частини (приблизно порівну по реченню)
PART1 = "Дякуємо за дзвінок до компанії Окі-Токі. На жаль, всі оператори зараз зайняті."
PART2 = "Будь ласка, залишайтесь на лінії, вам відповідять найближчим часом."

# Розбивка на 3 частини
P1 = "Дякуємо за дзвінок до компанії Окі-Токі."
P2 = "На жаль, всі оператори зараз зайняті."
P3 = "Будь ласка, залишайтесь на лінії, вам відповідять найближчим часом."

print(f"2 частини: {len(PART1)} + {len(PART2)} = {len(PART1)+len(PART2)} симв")
print(f"3 частини: {len(P1)} + {len(P2)} + {len(P3)} = {len(P1)+len(P2)+len(P3)} симв\n")

# Прогрів — створюємо всі клієнти заздалегідь
print("Прогрів клієнтів...")
clients = [texttospeech.TextToSpeechClient() for _ in range(4)]

# Прогрів gRPC каналів — один маленький запит кожним клієнтом
def warmup(client):
    voice = texttospeech.VoiceSelectionParams(language_code="uk-UA", name="uk-UA-Chirp3-HD-Leda")
    config = texttospeech.StreamingSynthesizeConfig(voice=voice)
    def req():
        yield texttospeech.StreamingSynthesizeRequest(streaming_config=config)
        yield texttospeech.StreamingSynthesizeRequest(
            input=texttospeech.StreamingSynthesisInput(text="тест"))
    for resp in client.streaming_synthesize(req()):
        pass

with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
    list(ex.map(warmup, clients))
print("Прогрів завершено!\n")

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

print(f"{'='*70}")
print(f"  Chirp3-HD Leda | {len(TEXT)} символів | Всі методи оптимізації")
print(f"{'='*70}\n")
print(f"  {'#':<3} {'Метод':<45} {'Час':>7}")
print(f"  {'─'*3} {'─'*45} {'─'*7}")

# ═══════════════════════════════════════
# 1. Базовий (1 клієнт, повний текст)
# ═══════════════════════════════════════
start = time.time()
audio = chirp3_stream(clients[0], TEXT)
t1 = time.time() - start
wav = process_chirp_audio(audio)
with open("fastest_1_base.wav", "wb") as f:
    f.write(wav)
print(f"  1   {'Базовий (1 запит, прогрітий канал)':<45} {t1:>6.3f}с")

# ═══════════════════════════════════════
# 2. Паралельно 2 частини (2 клієнти)
# ═══════════════════════════════════════
start = time.time()
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
    f1 = ex.submit(chirp3_stream, clients[0], PART1)
    f2 = ex.submit(chirp3_stream, clients[1], PART2)
    a1, a2 = f1.result(), f2.result()
t2 = time.time() - start

pcm1 = extract_pcm_8k(a1)
pcm2 = extract_pcm_8k(a2)
silence = b'\x00' * 2400  # 150мс тиша
wav = wrap_pcm_to_wav(pcm1 + silence + pcm2, 8000)
with open("fastest_2_parallel2.wav", "wb") as f:
    f.write(wav)
print(f"  2   {'Паралельно 2 частини (2 клієнти)':<45} {t2:>6.3f}с")

# ═══════════════════════════════════════
# 3. Паралельно 3 частини (3 клієнти)
# ═══════════════════════════════════════
start = time.time()
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:
    f1 = ex.submit(chirp3_stream, clients[0], P1)
    f2 = ex.submit(chirp3_stream, clients[1], P2)
    f3 = ex.submit(chirp3_stream, clients[2], P3)
    a1, a2, a3 = f1.result(), f2.result(), f3.result()
t3 = time.time() - start

pcm1 = extract_pcm_8k(a1)
pcm2 = extract_pcm_8k(a2)
pcm3 = extract_pcm_8k(a3)
silence = b'\x00' * 2400
wav = wrap_pcm_to_wav(pcm1 + silence + pcm2 + silence + pcm3, 8000)
with open("fastest_3_parallel3.wav", "wb") as f:
    f.write(wav)
print(f"  3   {'Паралельно 3 частини (3 клієнти)':<45} {t3:>6.3f}с")

# ═══════════════════════════════════════
# 4. Паралельно 2 + Leda & Puck (race — хто швидше)
# ═══════════════════════════════════════
start = time.time()
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
    # Кожну частину генеруємо двома голосами, беремо той що прийшов першим
    f1a = ex.submit(chirp3_stream, clients[0], PART1, "uk-UA-Chirp3-HD-Leda")
    f1b = ex.submit(chirp3_stream, clients[1], PART1, "uk-UA-Chirp3-HD-Puck")
    f2a = ex.submit(chirp3_stream, clients[2], PART2, "uk-UA-Chirp3-HD-Leda")
    f2b = ex.submit(chirp3_stream, clients[3], PART2, "uk-UA-Chirp3-HD-Puck")

    # Чекаємо перший результат для кожної частини
    done1, _ = concurrent.futures.wait([f1a, f1b], return_when=concurrent.futures.FIRST_COMPLETED)
    done2, _ = concurrent.futures.wait([f2a, f2b], return_when=concurrent.futures.FIRST_COMPLETED)
    a1 = list(done1)[0].result()
    a2 = list(done2)[0].result()

t4 = time.time() - start
pcm1 = extract_pcm_8k(a1)
pcm2 = extract_pcm_8k(a2)
wav = wrap_pcm_to_wav(pcm1 + silence + pcm2, 8000)
with open("fastest_4_race.wav", "wb") as f:
    f.write(wav)
print(f"  4   {'Race: 2 частини × 2 голоси (хто швидше)':<45} {t4:>6.3f}с")

# ═══════════════════════════════════════
# 5. Повторити найкращий 5 разів для статистики
# ═══════════════════════════════════════
print(f"\n  ── Стабільність найкращого методу (5 запусків) ──")

# Визначаємо найкращий
methods = {
    "base": t1,
    "parallel2": t2,
    "parallel3": t3,
    "race": t4,
}
best_name = min(methods, key=methods.get)
best_time = methods[best_name]
print(f"  Найкращий: {best_name} ({best_time:.3f}с)\n")

times = []
for i in range(5):
    if best_name == "parallel3":
        start = time.time()
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:
            f1 = ex.submit(chirp3_stream, clients[0], P1)
            f2 = ex.submit(chirp3_stream, clients[1], P2)
            f3 = ex.submit(chirp3_stream, clients[2], P3)
            f1.result(); f2.result(); f3.result()
        t = time.time() - start
    elif best_name == "parallel2":
        start = time.time()
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
            f1 = ex.submit(chirp3_stream, clients[0], PART1)
            f2 = ex.submit(chirp3_stream, clients[1], PART2)
            f1.result(); f2.result()
        t = time.time() - start
    elif best_name == "race":
        start = time.time()
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
            f1a = ex.submit(chirp3_stream, clients[0], PART1, "uk-UA-Chirp3-HD-Leda")
            f1b = ex.submit(chirp3_stream, clients[1], PART1, "uk-UA-Chirp3-HD-Puck")
            f2a = ex.submit(chirp3_stream, clients[2], PART2, "uk-UA-Chirp3-HD-Leda")
            f2b = ex.submit(chirp3_stream, clients[3], PART2, "uk-UA-Chirp3-HD-Puck")
            done1, _ = concurrent.futures.wait([f1a, f1b], return_when=concurrent.futures.FIRST_COMPLETED)
            done2, _ = concurrent.futures.wait([f2a, f2b], return_when=concurrent.futures.FIRST_COMPLETED)
            list(done1)[0].result(); list(done2)[0].result()
        t = time.time() - start
    else:
        start = time.time()
        chirp3_stream(clients[0], TEXT)
        t = time.time() - start
    times.append(t)
    print(f"    Запуск {i+1}: {t:.3f}с")

avg = sum(times) / len(times)
mn = min(times)
mx = max(times)
print(f"\n    Середній: {avg:.3f}с | Мін: {mn:.3f}с | Макс: {mx:.3f}с")

print(f"\n{'='*70}")
print(f"  ПІДСУМОК для {len(TEXT)} символів:")
print(f"  ─────────────────────────────────────────")
print(f"  Базовий:         {t1:.3f}с")
print(f"  Паралель ×2:     {t2:.3f}с  ({(1-t2/t1)*100:+.0f}%)")
print(f"  Паралель ×3:     {t3:.3f}с  ({(1-t3/t1)*100:+.0f}%)")
print(f"  Race ×2 голоси:  {t4:.3f}с  ({(1-t4/t1)*100:+.0f}%)")
print(f"{'='*70}")

