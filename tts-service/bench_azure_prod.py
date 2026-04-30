import sys, io, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
import azure.cognitiveservices.speech as speechsdk

AZURE_KEY = "YOUR_SECRET_TOKEN"
AZURE_REGION = "westeurope"
TEXT = "Привіт, я твій особистий помічник. Як твої справи? Я робот Ілля, радий допомогти"
VOICE = "uk-UA-PolinaNeural"
RUNS = 10

config = speechsdk.SpeechConfig(subscription=AZURE_KEY, region=AZURE_REGION)
config.speech_synthesis_voice_name = VOICE
config.set_speech_synthesis_output_format(speechsdk.SpeechSynthesisOutputFormat.Audio16Khz32KBitRateMonoMp3)

synth = speechsdk.SpeechSynthesizer(speech_config=config, audio_config=None)
conn = speechsdk.Connection.from_speech_synthesizer(synth)
conn.open(True)
time.sleep(0.5)

print(f"Текст: \"{TEXT}\" ({len(TEXT)} символів)")
print(f"Голос: {VOICE} | Регіон: {AZURE_REGION} | Прогонів: {RUNS}\n")

times = []
first_chunks = []

for i in range(RUNS):
    start = time.time()
    first_chunk = None
    result = synth.start_speaking_text_async(TEXT).get()
    stream = speechsdk.AudioDataStream(result)
    buf = bytes(4096)
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
        first_chunks.append(first_chunk)
    lat = result.properties
    fb = lat.get_property(speechsdk.PropertyId.SpeechServiceResponse_SynthesisFirstByteLatencyMs)
    sv = lat.get_property(speechsdk.PropertyId.SpeechServiceResponse_SynthesisServiceLatencyMs)
    nw = lat.get_property(speechsdk.PropertyId.SpeechServiceResponse_SynthesisNetworkLatencyMs)
    print(f"  {i+1:>2}: {elapsed:.3f}с | 1й чанк: {first_chunk:.3f}с | service: {sv}мс | network: {nw}мс | fb: {fb}мс | {len(audio)}б")

with open("azure_prod_sample.mp3", "wb") as f:
    f.write(audio)

print(f"\nСереднє total:   {sum(times)/len(times):.3f} сек")
print(f"Середнє 1й чанк: {sum(first_chunks)/len(first_chunks):.3f} сек")
print(f"Мін total:       {min(times):.3f} сек")
print(f"Макс total:      {max(times):.3f} сек")
print(f"\nФайл збережено: azure_prod_sample.mp3")

