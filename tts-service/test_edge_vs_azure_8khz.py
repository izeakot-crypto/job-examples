import sys, io, time, asyncio, struct, wave
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
import edge_tts
import azure.cognitiveservices.speech as speechsdk

TEXT = "Привіт! Я Ілля, я ваш віртуальний робот помічник. Чим вам допомогти?"
VOICE_EDGE = "uk-UA-PolinaNeural"
VOICE_AZURE = "uk-UA-PolinaNeural"

AZURE_KEY = "YOUR_SECRET_TOKEN"
AZURE_REGION = "westeurope"

def mp3_to_wav_8khz_python(mp3_bytes, out_path):
    """Конвертація MP3 -> WAV 8kHz через minimp3 або io.
    Використовуємо subprocess з ffmpeg якщо є, інакше пишемо MP3 як є."""
    import subprocess, tempfile, os

    # Спробуємо знайти ffmpeg
    for ffmpeg_path in ["ffmpeg", "ffmpeg.exe",
                        r"C:\ffmpeg\bin\ffmpeg.exe",
                        r"C:\Program Files\ffmpeg\bin\ffmpeg.exe"]:
        try:
            tmp_mp3 = tempfile.mktemp(suffix=".mp3")
            with open(tmp_mp3, "wb") as f:
                f.write(mp3_bytes)

            result = subprocess.run([
                ffmpeg_path, "-y", "-i", tmp_mp3,
                "-ar", "8000", "-ac", "1", "-acodec", "pcm_s16le",
                out_path
            ], capture_output=True, timeout=10)

            os.unlink(tmp_mp3)
            if result.returncode == 0:
                return True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            try:
                os.unlink(tmp_mp3)
            except:
                pass
            continue

    # Якщо ffmpeg немає — зберігаємо MP3 і міряємо час без конвертації
    return False

async def test_edge_save(text, voice):
    """Edge TTS save() -> MP3"""
    communicate = edge_tts.Communicate(text, voice)
    start = time.time()
    audio_chunks = b""
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_chunks += chunk["data"]
    elapsed = time.time() - start
    return audio_chunks, elapsed

print(f'Текст: "{TEXT}" ({len(TEXT)} символів)')
print(f"Порівняння: Edge TTS (MP3) vs Azure TTS (WAV 8kHz нативно)\n")

# ═══════════════════════════════════════
# ТЕСТ 1: Azure TTS — нативний 8kHz WAV
# ═══════════════════════════════════════
print(f"{'='*65}")
print(f"  Azure TTS — нативний Riff8Khz16BitMonoPcm (без конвертації)")
print(f"{'='*65}")

config = speechsdk.SpeechConfig(subscription=AZURE_KEY, region=AZURE_REGION)
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
azure_time = time.time() - start

if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
    fname = "compare_azure_8khz.wav"
    with open(fname, "wb") as f:
        f.write(result.audio_data)
    print(f"  Генерація:    {azure_time:.3f}с")
    print(f"  Конвертація:  0.000с (нативний формат)")
    print(f"  ВСЬОГО:       {azure_time:.3f}с")
    print(f"  Файл:         {fname} ({len(result.audio_data)}б)")

del synth

# ═══════════════════════════════════════
# ТЕСТ 2: Edge TTS — MP3 (без конвертації)
# ═══════════════════════════════════════
print(f"\n{'='*65}")
print(f"  Edge TTS — MP3 (оригінал, без конвертації)")
print(f"{'='*65}")

mp3_data, edge_gen_time = asyncio.run(test_edge_save(TEXT, VOICE_EDGE))
fname_mp3 = "compare_edge_original.mp3"
with open(fname_mp3, "wb") as f:
    f.write(mp3_data)
print(f"  Генерація:    {edge_gen_time:.3f}с")
print(f"  Файл:         {fname_mp3} ({len(mp3_data)}б)")

# ═══════════════════════════════════════
# ТЕСТ 3: Edge TTS — MP3 + конвертація в 8kHz WAV
# ═══════════════════════════════════════
print(f"\n{'='*65}")
print(f"  Edge TTS — MP3 + конвертація в WAV 8kHz")
print(f"{'='*65}")

# Генерація
mp3_data2, edge_gen_time2 = asyncio.run(test_edge_save(TEXT, VOICE_EDGE))

# Конвертація
fname_wav = "compare_edge_converted_8khz.wav"
conv_start = time.time()
converted = mp3_to_wav_8khz_python(mp3_data2, fname_wav)
conv_time = time.time() - conv_start

total_edge = edge_gen_time2 + conv_time

if converted:
    print(f"  Генерація:    {edge_gen_time2:.3f}с")
    print(f"  Конвертація:  {conv_time:.3f}с (ffmpeg MP3->WAV 8kHz)")
    print(f"  ВСЬОГО:       {total_edge:.3f}с")
    print(f"  Файл:         {fname_wav}")
else:
    print(f"  Генерація:    {edge_gen_time2:.3f}с")
    print(f"  Конвертація:  ffmpeg НЕ ЗНАЙДЕНО!")
    print(f"  ВСЬОГО (без конвертації): {edge_gen_time2:.3f}с")
    print(f"  ⚠ Для конвертації потрібен ffmpeg:")
    print(f"    pip install ffmpeg-python  # або")
    print(f"    winget install ffmpeg      # або")
    print(f"    choco install ffmpeg")

# ═══════════════════════════════════════
# ПІДСУМОК
# ═══════════════════════════════════════
print(f"\n{'='*65}")
print(f"  ПІДСУМОК")
print(f"{'='*65}")
print(f"  Azure TTS (нативний 8kHz WAV):  {azure_time:.3f}с")
print(f"  Edge TTS (тільки MP3):           {edge_gen_time:.3f}с")
if converted:
    print(f"  Edge TTS (MP3 + ffmpeg->WAV):    {total_edge:.3f}с")
    ratio = total_edge / azure_time if azure_time > 0 else 0
    print(f"\n  Azure швидше за Edge+ffmpeg у {ratio:.1f}x")
else:
    print(f"  Edge TTS (MP3 + ffmpeg->WAV):    ~{edge_gen_time:.3f}с + ~0.1-0.3с конвертація")
    est_total = edge_gen_time + 0.15
    ratio = est_total / azure_time if azure_time > 0 else 0
    print(f"\n  Оцінка: Azure швидше за Edge+ffmpeg у ~{ratio:.1f}x")
    print(f"  (точний час конвертації невідомий — ffmpeg не встановлений)")

