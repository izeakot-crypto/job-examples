import sys, io, time, wave, os, struct
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

gclient = texttospeech.TextToSpeechClient()

# 3 емоції — різні тексти
EMOTIONS = {
    "happy": {
        "text": "Чудові новини! Вашу проблему повністю вирішено! Замовлення вже в дорозі і буде у вас завтра вранці. Дякуємо за терпіння, і гарного вам дня!",
        "ssml": """<speak>
<prosody rate="110%" pitch="+3st">
    Чудові новини!
</prosody>
<break time="300ms"/>
<prosody rate="108%" pitch="+2st">
    Вашу проблему повністю вирішено!
</prosody>
<break time="250ms"/>
<prosody rate="105%" pitch="+1st">
    Замовлення вже в дорозі і буде у вас завтра вранці.
</prosody>
<break time="300ms"/>
<prosody rate="108%" pitch="+3st">
    Дякуємо за терпіння, і гарного вам дня!
</prosody>
</speak>""",
    },
    "sad": {
        "text": "На жаль, ми змушені відмовити у вашому запиті... Нам дуже прикро, але повернення коштів неможливе після закінчення гарантійного терміну. Якщо бажаєте, я можу запропонувати знижку на наступне замовлення.",
        "ssml": """<speak>
<prosody rate="82%" pitch="-2st">
    На жаль, ми змушені відмовити у вашому запиті...
</prosody>
<break time="500ms"/>
<prosody rate="80%" pitch="-2st">
    Нам дуже прикро, але повернення коштів неможливе після закінчення гарантійного терміну.
</prosody>
<break time="450ms"/>
<prosody rate="88%" pitch="+0st">
    Якщо бажаєте, я можу запропонувати знижку на наступне замовлення.
</prosody>
</speak>""",
    },
    "calm": {
        "text": "Будь ласка, залишайтесь на лінії. Ваш дзвінок дуже важливий для нас. Перший вільний спеціаліст зʼєднається з вами найближчим часом. Орієнтовний час очікування — дві хвилини.",
        "ssml": """<speak>
<prosody rate="85%" pitch="-1st">
    Будь ласка, залишайтесь на лінії.
</prosody>
<break time="500ms"/>
<prosody rate="82%">
    Ваш дзвінок дуже важливий для нас.
</prosody>
<break time="450ms"/>
<prosody rate="85%">
    Перший вільний спеціаліст зʼєднається з вами найближчим часом.
</prosody>
<break time="400ms"/>
<prosody rate="88%">
    Орієнтовний час очікування — дві хвилини.
</prosody>
</speak>""",
    },
}

# Голоси
CHIRP_VOICE = texttospeech.VoiceSelectionParams(language_code="uk-UA", name="uk-UA-Chirp3-HD-Leda")
WAVENET_VOICE = texttospeech.VoiceSelectionParams(language_code="uk-UA", name="uk-UA-Wavenet-B")

audio_cfg = texttospeech.AudioConfig(
    audio_encoding=texttospeech.AudioEncoding.LINEAR16,
    sample_rate_hertz=8000,
    effects_profile_id=["telephony-class-application"],
)

print(f"{'='*70}")
print(f"  Chirp3-HD (без SSML) vs Wavenet-B (з SSML) vs Wavenet-B (без SSML)")
print(f"  3 емоції: happy / sad / calm")
print(f"{'='*70}\n")

print(f"  {'Файл':<40} {'Час':>7} {'Розмір':>8}")
print(f"  {'─'*40} {'─'*7} {'─'*8}")

for emo_name, data in EMOTIONS.items():
    print(f"\n  ── {emo_name.upper()} ──")

    # 1. Chirp3-HD — plain text (сама розуміє емоції)
    streaming_config = texttospeech.StreamingSynthesizeConfig(voice=CHIRP_VOICE)
    start = time.time()
    t_first = None
    audio_data = b""

    def req_gen():
        yield texttospeech.StreamingSynthesizeRequest(streaming_config=streaming_config)
        yield texttospeech.StreamingSynthesizeRequest(
            input=texttospeech.StreamingSynthesisInput(text=data["text"]))

    responses = gclient.streaming_synthesize(req_gen())
    for response in responses:
        if t_first is None:
            t_first = time.time() - start
        audio_data += response.audio_content
    t = time.time() - start

    if audio_data[:4] == b'RIFF':
        with io.BytesIO(audio_data) as buf:
            with wave.open(buf, 'rb') as wf:
                sr = wf.getframerate()
                pcm = wf.readframes(wf.getnframes())
        if sr != 8000:
            pcm_8k = downsample_pcm(pcm, sr, 8000)
            wav_data = wrap_pcm_to_wav(pcm_8k, 8000)
        else:
            wav_data = audio_data
    else:
        pcm_8k = downsample_pcm(audio_data, 24000, 8000)
        wav_data = wrap_pcm_to_wav(pcm_8k, 8000)

    fname = f"{emo_name}_chirp3_bez_ssml.wav"
    with open(fname, "wb") as f:
        f.write(wav_data)
    print(f"  {fname:<40} {t:>6.3f}с {len(wav_data):>7}б")

    # 2. Wavenet-B — plain text (без SSML)
    inp_plain = texttospeech.SynthesisInput(text=data["text"])
    start = time.time()
    resp = gclient.synthesize_speech(input=inp_plain, voice=WAVENET_VOICE, audio_config=audio_cfg)
    t = time.time() - start

    fname = f"{emo_name}_wavenet_bez_ssml.wav"
    with open(fname, "wb") as f:
        f.write(resp.audio_content)
    print(f"  {fname:<40} {t:>6.3f}с {len(resp.audio_content):>7}б")

    # 3. Wavenet-B — з SSML розміткою
    inp_ssml = texttospeech.SynthesisInput(ssml=data["ssml"])
    start = time.time()
    resp = gclient.synthesize_speech(input=inp_ssml, voice=WAVENET_VOICE, audio_config=audio_cfg)
    t = time.time() - start

    fname = f"{emo_name}_wavenet_z_ssml.wav"
    with open(fname, "wb") as f:
        f.write(resp.audio_content)
    print(f"  {fname:<40} {t:>6.3f}с {len(resp.audio_content):>7}б")

print(f"\n{'='*70}")
print(f"  Порівняйте 9 файлів:")
print(f"  - *_chirp3_bez_ssml  → Chirp3 сама додає інтонації")
print(f"  - *_wavenet_bez_ssml → Wavenet без нічого (роботний)")
print(f"  - *_wavenet_z_ssml   → Wavenet з SSML (rate, pitch, паузи)")
print(f"{'='*70}")

