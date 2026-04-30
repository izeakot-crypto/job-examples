import sys, io, time, wave, os, struct
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = r"[USER_HOME]\Downloads\tts-488311-d5a1cbf88094.json"

import azure.cognitiveservices.speech as speechsdk
from google.cloud import texttospeech

AZURE_KEY = "YOUR_SECRET_TOKEN"
AZURE_REGION = "westeurope"

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

EMOTIONS = {
    "happy": "Чудові новини! Вашу проблему повністю вирішено! Замовлення вже в дорозі і буде у вас завтра вранці. Дякуємо за терпіння, і гарного вам дня!",
    "sad": "На жаль, ми змушені відмовити у вашому запиті... Нам дуже прикро, але повернення коштів неможливе після закінчення гарантійного терміну. Якщо бажаєте, я можу запропонувати знижку на наступне замовлення.",
    "calm": "Будь ласка, залишайтесь на лінії. Ваш дзвінок дуже важливий для нас. Перший вільний спеціаліст зʼєднається з вами найближчим часом. Орієнтовний час очікування — дві хвилини.",
}

# ═══════════════════════════════════════
# Azure Polina — підготовка
# ═══════════════════════════════════════
az_config = speechsdk.SpeechConfig(subscription=AZURE_KEY, region=AZURE_REGION)
az_config.speech_synthesis_voice_name = "uk-UA-PolinaNeural"
az_config.set_speech_synthesis_output_format(speechsdk.SpeechSynthesisOutputFormat.Raw8Khz16BitMonoPcm)
az_synth = speechsdk.SpeechSynthesizer(speech_config=az_config, audio_config=None)
az_conn = speechsdk.Connection.from_speech_synthesizer(az_synth)
az_conn.open(True)
time.sleep(0.3)
az_synth.speak_text_async("тест").get()

# Azure Ostap — підготовка
az_config2 = speechsdk.SpeechConfig(subscription=AZURE_KEY, region=AZURE_REGION)
az_config2.speech_synthesis_voice_name = "uk-UA-OstapNeural"
az_config2.set_speech_synthesis_output_format(speechsdk.SpeechSynthesisOutputFormat.Raw8Khz16BitMonoPcm)
az_synth2 = speechsdk.SpeechSynthesizer(speech_config=az_config2, audio_config=None)
az_conn2 = speechsdk.Connection.from_speech_synthesizer(az_synth2)
az_conn2.open(True)
time.sleep(0.3)
az_synth2.speak_text_async("тест").get()

# Google Chirp3 — підготовка
gclient = texttospeech.TextToSpeechClient()
chirp_leda = texttospeech.VoiceSelectionParams(language_code="uk-UA", name="uk-UA-Chirp3-HD-Leda")
chirp_puck = texttospeech.VoiceSelectionParams(language_code="uk-UA", name="uk-UA-Chirp3-HD-Puck")

print(f"{'='*70}")
print(f"  Azure (Polina + Ostap) vs Chirp3-HD (Leda + Puck)")
print(f"  3 емоції: happy / sad / calm | Той самий текст | WAV 8kHz")
print(f"{'='*70}\n")

print(f"  {'Файл':<45} {'Час':>7} {'Розмір':>8}")
print(f"  {'─'*45} {'─'*7} {'─'*8}")

for emo_name, text in EMOTIONS.items():
    print(f"\n  ── {emo_name.upper()} ──")
    print(f"  \"{text[:70]}...\"")

    # 1. Azure Polina
    start = time.time()
    result = az_synth.speak_text_async(text).get()
    t = time.time() - start
    wav = wrap_pcm_to_wav(result.audio_data)
    fname = f"{emo_name}_azure_Polina.wav"
    with open(fname, "wb") as f:
        f.write(wav)
    print(f"  {fname:<45} {t:>6.3f}с {len(wav):>7}б")

    # 2. Azure Ostap
    start = time.time()
    result2 = az_synth2.speak_text_async(text).get()
    t = time.time() - start
    wav2 = wrap_pcm_to_wav(result2.audio_data)
    fname = f"{emo_name}_azure_Ostap.wav"
    with open(fname, "wb") as f:
        f.write(wav2)
    print(f"  {fname:<45} {t:>6.3f}с {len(wav2):>7}б")

    # 3. Chirp3-HD Leda
    streaming_config = texttospeech.StreamingSynthesizeConfig(voice=chirp_leda)
    start = time.time()
    audio_data = b""

    def req_gen_l():
        yield texttospeech.StreamingSynthesizeRequest(streaming_config=streaming_config)
        yield texttospeech.StreamingSynthesizeRequest(
            input=texttospeech.StreamingSynthesisInput(text=text))

    responses = gclient.streaming_synthesize(req_gen_l())
    for response in responses:
        audio_data += response.audio_content
    t = time.time() - start

    if audio_data[:4] == b'RIFF':
        with io.BytesIO(audio_data) as buf:
            with wave.open(buf, 'rb') as wf:
                sr = wf.getframerate()
                pcm = wf.readframes(wf.getnframes())
        if sr != 8000:
            pcm_8k = downsample_pcm(pcm, sr, 8000)
            wav3 = wrap_pcm_to_wav(pcm_8k, 8000)
        else:
            wav3 = audio_data
    else:
        pcm_8k = downsample_pcm(audio_data, 24000, 8000)
        wav3 = wrap_pcm_to_wav(pcm_8k, 8000)

    fname = f"{emo_name}_chirp3_Leda.wav"
    with open(fname, "wb") as f:
        f.write(wav3)
    print(f"  {fname:<45} {t:>6.3f}с {len(wav3):>7}б")

    # 4. Chirp3-HD Puck
    streaming_config2 = texttospeech.StreamingSynthesizeConfig(voice=chirp_puck)
    start = time.time()
    audio_data2 = b""

    def req_gen_p():
        yield texttospeech.StreamingSynthesizeRequest(streaming_config=streaming_config2)
        yield texttospeech.StreamingSynthesizeRequest(
            input=texttospeech.StreamingSynthesisInput(text=text))

    responses2 = gclient.streaming_synthesize(req_gen_p())
    for response in responses2:
        audio_data2 += response.audio_content
    t = time.time() - start

    if audio_data2[:4] == b'RIFF':
        with io.BytesIO(audio_data2) as buf:
            with wave.open(buf, 'rb') as wf:
                sr = wf.getframerate()
                pcm = wf.readframes(wf.getnframes())
        if sr != 8000:
            pcm_8k = downsample_pcm(pcm, sr, 8000)
            wav4 = wrap_pcm_to_wav(pcm_8k, 8000)
        else:
            wav4 = audio_data2
    else:
        pcm_8k = downsample_pcm(audio_data2, 24000, 8000)
        wav4 = wrap_pcm_to_wav(pcm_8k, 8000)

    fname = f"{emo_name}_chirp3_Puck.wav"
    with open(fname, "wb") as f:
        f.write(wav4)
    print(f"  {fname:<45} {t:>6.3f}с {len(wav4):>7}б")

del az_synth, az_synth2

print(f"\n{'='*70}")
print(f"  12 файлів: 3 емоції × 4 голоси")
print(f"  Порівняйте Azure vs Chirp3 на кожній емоції!")
print(f"{'='*70}")


