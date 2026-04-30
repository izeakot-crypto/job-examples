import sys, io, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
import azure.cognitiveservices.speech as speechsdk

AZURE_KEY = "YOUR_SECRET_TOKEN"
AZURE_REGION = "westeurope"
VOICE = "uk-UA-PolinaNeural"

TEXTS = [
    "Добрий день! Дякую що зателефонували. Чим можу вам допомогти?",
    "Ваш запит прийнято. Очікуйте відповідь оператора протягом хвилини.",
    "Привіт! Я віртуальний помічник компанії Оки-Токі. Чим можу бути корисний?",
]

# 8kHz 16bit mono — ідеально для телефонії
config = speechsdk.SpeechConfig(subscription=AZURE_KEY, region=AZURE_REGION)
config.speech_synthesis_voice_name = VOICE
config.set_speech_synthesis_output_format(
    speechsdk.SpeechSynthesisOutputFormat.Riff8Khz16BitMonoPcm
)

synth = speechsdk.SpeechSynthesizer(speech_config=config, audio_config=None)
conn = speechsdk.Connection.from_speech_synthesizer(synth)
conn.open(True)
time.sleep(0.5)

# Прогрів
synth.speak_text_async("тест").get()

print(f"Голос: {VOICE} | Регіон: {AZURE_REGION}")
print(f"Формат: WAV 8kHz 16bit mono (телефонія)")
print(f"Оптимізації: reuse synth + pre-connect + streaming\n")

all_times = []
all_first = []

for idx, text in enumerate(TEXTS):
    print(f"{'─'*70}")
    print(f"  Текст {idx+1}: \"{text}\" ({len(text)} симв.)\n")

    times = []
    firsts = []
    for i in range(3):
        start = time.time()
        first_chunk = None
        result = synth.start_speaking_text_async(text).get()
        stream = speechsdk.AudioDataStream(result)
        buf = bytes(8000)
        chunks = []
        filled = stream.read_data(buf)
        while filled > 0:
            if first_chunk is None:
                first_chunk = time.time() - start
            chunks.append(buf[:filled])
            filled = stream.read_data(buf)
        elapsed = time.time() - start
        audio = b"".join(chunks)
        times.append(elapsed)
        if first_chunk:
            firsts.append(first_chunk)
        sv = result.properties.get_property(speechsdk.PropertyId.SpeechServiceResponse_SynthesisServiceLatencyMs)
        nw = result.properties.get_property(speechsdk.PropertyId.SpeechServiceResponse_SynthesisNetworkLatencyMs)
        fb = result.properties.get_property(speechsdk.PropertyId.SpeechServiceResponse_SynthesisFirstByteLatencyMs)
        print(f"    Run {i+1}: {elapsed:.3f}с | 1й чанк: {first_chunk:.3f}с | service: {sv}мс | network: {nw}мс | fb: {fb}мс | {len(audio)}б")

    avg_t = sum(times) / len(times)
    avg_f = sum(firsts) / len(firsts) if firsts else 0
    print(f"    Середнє: {avg_t:.3f}с | 1й чанк: {avg_f:.3f}с")
    all_times.append(avg_t)
    all_first.append(avg_f)

    # Зберігаємо і стрімінг і повний варіант
    fname_stream = f"azure_8khz_stream_{idx+1}.wav"
    with open(fname_stream, "wb") as f:
        f.write(audio)

    # Також зберігаємо повним speak_text_async для перевірки якості
    result2 = synth.speak_text_async(text).get()
    fname_full = f"azure_8khz_full_{idx+1}.wav"
    with open(fname_full, "wb") as f:
        f.write(result2.audio_data)
    print(f"    Збережено: {fname_stream} (stream) | {fname_full} (full)")

del synth

print(f"\n{'='*70}")
print(f"  ПІДСУМОК — 3 ТЕКСТИ (8kHz 16bit mono)")
print(f"{'='*70}")
print(f"  {'#':<4} {'Симв':>5} {'Total':>8} {'1й чанк':>9}  Текст")
print(f"  {'─'*4} {'─'*5} {'─'*8} {'─'*9}  {'─'*35}")
for idx, text in enumerate(TEXTS):
    print(f"  {idx+1:<4} {len(text):>5} {all_times[idx]:>6.3f}с {all_first[idx]:>7.3f}с  {text[:40]}...")

grand_avg_t = sum(all_times) / len(all_times)
grand_avg_f = sum(all_first) / len(all_first)
print(f"\n  Загальне середнє: total={grand_avg_t:.3f}с | 1й чанк={grand_avg_f:.3f}с")
print(f"\n  Послухайте: azure_8khz_full_1.wav, azure_8khz_full_2.wav, azure_8khz_full_3.wav")

