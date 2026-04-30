import sys, io, time, asyncio, subprocess, tempfile, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
import edge_tts
import azure.cognitiveservices.speech as speechsdk

TEXT = "Дякую за дзвінок! Зачекайте будь ласка, зʼєдную вас з оператором."
VOICE = "uk-UA-PolinaNeural"

AZURE_KEY = "YOUR_SECRET_TOKEN"
AZURE_REGION = "westeurope"

print(f'Текст: "{TEXT}" ({len(TEXT)} символів)')
print(f"Голос: {VOICE}")
print(f"Формат: WAV 8kHz 16bit mono\n")

# ═══════════════════════════════════════
# Azure TTS — нативний 8kHz
# ═══════════════════════════════════════
print(f"{'='*60}")
print(f"  Azure TTS (нативний 8kHz WAV)")
print(f"{'='*60}")

config = speechsdk.SpeechConfig(subscription=AZURE_KEY, region=AZURE_REGION)
config.set_speech_synthesis_output_format(
    speechsdk.SpeechSynthesisOutputFormat.Riff8Khz16BitMonoPcm
)
synth = speechsdk.SpeechSynthesizer(speech_config=config, audio_config=None)
conn = speechsdk.Connection.from_speech_synthesizer(synth)
conn.open(True)
time.sleep(0.5)
synth.speak_text_async("тест").get()

# Звичайний
start = time.time()
result = synth.speak_text_async(TEXT).get()
t_azure = time.time() - start
with open("final_azure_8khz.wav", "wb") as f:
    f.write(result.audio_data)
print(f"  Звичайний:  {t_azure:.3f}с | final_azure_8khz.wav")

# З prosody rate +15%
ssml = f"""<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='uk-UA'>
    <voice name='{VOICE}'>
        <prosody rate='+15%'>{TEXT}</prosody>
    </voice></speak>"""
start = time.time()
result = synth.speak_ssml_async(ssml).get()
t_azure_fast = time.time() - start
with open("final_azure_8khz_fast.wav", "wb") as f:
    f.write(result.audio_data)
print(f"  Rate +15%:  {t_azure_fast:.3f}с | final_azure_8khz_fast.wav")

# Стрімінг
start = time.time()
result = synth.start_speaking_text_async(TEXT).get()
t_first = time.time() - start
stream = speechsdk.AudioDataStream(result)
audio = bytes()
buf = bytes(3200)
while True:
    filled = stream.read_data(buf)
    if filled == 0:
        break
    audio += buf[:filled]
t_azure_stream = time.time() - start
with open("final_azure_8khz_stream.wav", "wb") as f:
    f.write(audio)
print(f"  Стрімінг:   {t_azure_stream:.3f}с (1й чанк {t_first:.3f}с) | final_azure_8khz_stream.wav")

del synth

# ═══════════════════════════════════════
# Edge TTS — MP3 (без конвертації)
# ═══════════════════════════════════════
print(f"\n{'='*60}")
print(f"  Edge TTS (MP3, без конвертації в 8kHz)")
print(f"{'='*60}")

async def edge_gen(text, voice, rate="+0%"):
    comm = edge_tts.Communicate(text, voice, rate=rate)
    start = time.time()
    await comm.save("_tmp_edge.mp3")
    elapsed = time.time() - start
    with open("_tmp_edge.mp3", "rb") as f:
        data = f.read()
    return data, elapsed

# Звичайний
data, t_edge = asyncio.run(edge_gen(TEXT, VOICE))
with open("final_edge.mp3", "wb") as f:
    f.write(data)
print(f"  Звичайний:  {t_edge:.3f}с | final_edge.mp3")

# Rate +15%
data, t_edge_fast = asyncio.run(edge_gen(TEXT, VOICE, rate="+15%"))
with open("final_edge_fast.mp3", "wb") as f:
    f.write(data)
print(f"  Rate +15%:  {t_edge_fast:.3f}с | final_edge_fast.mp3")

# ═══════════════════════════════════════
# ПІДСУМОК
# ═══════════════════════════════════════
print(f"\n{'='*60}")
print(f"  ПІДСУМОК")
print(f"{'='*60}")
print(f"  Azure звичайний:    {t_azure:.3f}с  (WAV 8kHz нативно)")
print(f"  Azure rate +15%:    {t_azure_fast:.3f}с  (WAV 8kHz нативно)")
print(f"  Azure стрімінг:     {t_azure_stream:.3f}с  (1й чанк {t_first:.3f}с)")
print(f"  Edge звичайний:     {t_edge:.3f}с  (MP3, треба ще ffmpeg)")
print(f"  Edge rate +15%:     {t_edge_fast:.3f}с  (MP3, треба ще ffmpeg)")
print(f"\n  * Edge TTS НЕ підтримує 8kHz — потрібен ffmpeg (+0.1-0.3с)")
print(f"  * Azure віддає 8kHz WAV одразу")

try:
    os.unlink("_tmp_edge.mp3")
except:
    pass

