import sys, io, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
import azure.cognitiveservices.speech as speechsdk

AZURE_KEY = "YOUR_SECRET_TOKEN"
AZURE_REGION = "westeurope"

TEXT_PLAIN = "Привіт! Я віртуальний помічник компанії Окі-Токі. Чим можу бути корисний?"
TEXT_STRESS = "Приві́т! Я́ віртуа́льний помічни́к компа́нії Окі́-То́кі. Чи́м можу́ бу́ти кори́сний?"

RUNS = 3
VOICE = "uk-UA-PolinaNeural"

def make_ssml(text):
    return f"""<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='uk-UA'>
    <voice name='{VOICE}'>
        <prosody rate='+20%' pitch='+5%' volume='+20%'>{text}</prosody>
    </voice></speak>"""

def calc_cps(text, elapsed):
    """Characters per second"""
    clean = ''.join(c for c in text if c.isalpha() or c.isspace())
    return len(clean) / elapsed if elapsed > 0 else 0

config = speechsdk.SpeechConfig(subscription=AZURE_KEY, region=AZURE_REGION)
config.set_speech_synthesis_output_format(
    speechsdk.SpeechSynthesisOutputFormat.Audio16Khz128KBitRateMonoMp3
)
synth = speechsdk.SpeechSynthesizer(speech_config=config, audio_config=None)
conn = speechsdk.Connection.from_speech_synthesizer(synth)
conn.open(True)
time.sleep(0.5)
# Прогрів SSML
synth.speak_ssml_async(make_ssml("тест")).get()

print(f"Голос: {VOICE}")
print(f"Prosody: rate=+20%, pitch=+5%, volume=+20%")
print(f"Прогонів: {RUNS}")
print(f"\nТекст без наголосів: \"{TEXT_PLAIN}\" ({len(TEXT_PLAIN)} символів)")
print(f"Текст з наголосами:  \"{TEXT_STRESS}\" ({len(TEXT_STRESS)} символів)")

# ═══════════════════════════════════════════════
# ТЕСТ 1: Звичайна генерація (speak_ssml_async)
# ═══════════════════════════════════════════════
print(f"\n{'='*70}")
print(f"  ТЕСТ A: speak_ssml_async — БЕЗ наголосів")
print(f"{'='*70}")
for run in range(1, RUNS + 1):
    ssml = make_ssml(TEXT_PLAIN)
    start = time.time()
    result = synth.speak_ssml_async(ssml).get()
    elapsed = time.time() - start
    if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
        fname = f"stresstest_A_plain_{run}.mp3"
        with open(fname, "wb") as f:
            f.write(result.audio_data)
        cps = calc_cps(TEXT_PLAIN, elapsed)
        print(f"  run {run}: {elapsed:.3f}с | CPS: {cps:.0f} | {len(result.audio_data)}б | {fname}")
    else:
        print(f"  run {run}: ПОМИЛКА")

print(f"\n{'='*70}")
print(f"  ТЕСТ B: speak_ssml_async — З наголосами на кожне слово")
print(f"{'='*70}")
for run in range(1, RUNS + 1):
    ssml = make_ssml(TEXT_STRESS)
    start = time.time()
    result = synth.speak_ssml_async(ssml).get()
    elapsed = time.time() - start
    if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
        fname = f"stresstest_B_stress_{run}.mp3"
        with open(fname, "wb") as f:
            f.write(result.audio_data)
        cps = calc_cps(TEXT_STRESS, elapsed)
        print(f"  run {run}: {elapsed:.3f}с | CPS: {cps:.0f} | {len(result.audio_data)}б | {fname}")
    else:
        print(f"  run {run}: ПОМИЛКА")

# ═══════════════════════════════════════════════
# ТЕСТ 2: Стрімінг (start_speaking_ssml_async)
# ═══════════════════════════════════════════════
print(f"\n{'='*70}")
print(f"  ТЕСТ C: СТРІМІНГ start_speaking_ssml_async — БЕЗ наголосів")
print(f"{'='*70}")
for run in range(1, RUNS + 1):
    ssml = make_ssml(TEXT_PLAIN)
    start = time.time()
    result = synth.start_speaking_ssml_async(ssml).get()
    first_chunk_time = time.time() - start

    stream = speechsdk.AudioDataStream(result)
    audio_data = bytes()
    buf = bytes(3200)
    while True:
        filled = stream.read_data(buf)
        if filled == 0:
            break
        audio_data += buf[:filled]
    total_time = time.time() - start

    fname = f"stresstest_C_stream_plain_{run}.mp3"
    with open(fname, "wb") as f:
        f.write(audio_data)
    cps = calc_cps(TEXT_PLAIN, total_time)
    print(f"  run {run}: перший чанк {first_chunk_time:.3f}с | всього {total_time:.3f}с | CPS: {cps:.0f} | {len(audio_data)}б | {fname}")

print(f"\n{'='*70}")
print(f"  ТЕСТ D: СТРІМІНГ start_speaking_ssml_async — З наголосами")
print(f"{'='*70}")
for run in range(1, RUNS + 1):
    ssml = make_ssml(TEXT_STRESS)
    start = time.time()
    result = synth.start_speaking_ssml_async(ssml).get()
    first_chunk_time = time.time() - start

    stream = speechsdk.AudioDataStream(result)
    audio_data = bytes()
    buf = bytes(3200)
    while True:
        filled = stream.read_data(buf)
        if filled == 0:
            break
        audio_data += buf[:filled]
    total_time = time.time() - start

    fname = f"stresstest_D_stream_stress_{run}.mp3"
    with open(fname, "wb") as f:
        f.write(audio_data)
    cps = calc_cps(TEXT_STRESS, total_time)
    print(f"  run {run}: перший чанк {first_chunk_time:.3f}с | всього {total_time:.3f}с | CPS: {cps:.0f} | {len(audio_data)}б | {fname}")

del synth

print(f"\n{'='*70}")
print(f"  ПІДСУМОК")
print(f"{'='*70}")
print(f"  speak_ssml_async  — чекає повну генерацію, потім віддає все аудіо")
print(f"  start_speaking_ssml_async — СТРІМІНГ: віддає чанки по мірі генерації")
print(f"  'перший чанк' = час до першого шматка аудіо (можна починати грати)")
print(f"  CPS = символів на секунду (більше = краще)")

