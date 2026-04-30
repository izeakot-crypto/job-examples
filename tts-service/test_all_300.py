import sys, io, time, wave, os, struct
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = r"[USER_HOME]\Downloads\tts-488311-d5a1cbf88094.json"

from google.cloud import texttospeech
import azure.cognitiveservices.speech as speechsdk

AZURE_KEY = "YOUR_SECRET_TOKEN"
AZURE_REGION = "westeurope"

TEXT = "Шановний клієнте, дякуємо що звернулися до нашої компанії Окі-Токі. На жаль, всі оператори зараз зайняті. Будь ласка, залишайтесь на лінії, і перший вільний спеціаліст відповість вам найближчим часом. Орієнтовний час очікування складає три хвилини. Якщо бажаєте, залишіть голосове повідомлення, і ми передзвонимо."

SSML_GOOGLE = """<speak>
<prosody rate="95%" pitch="+2st" volume="+2dB">
Шановний клієнте, <break time="200ms"/> дякуємо що звернулися до нашої компанії Окі-Токі.
<break time="300ms"/>
На жаль, всі оператори зараз зайняті.
<break time="200ms"/>
Будь ласка, залишайтесь на лінії, <break time="150ms"/> і перший вільний спеціаліст відповість вам найближчим часом.
<break time="300ms"/>
Орієнтовний час очікування складає три хвилини.
<break time="250ms"/>
Якщо бажаєте, <break time="150ms"/> залишіть голосове повідомлення, і ми передзвонимо.
</prosody>
</speak>"""

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

print(f"Тест всіх голосів | {len(TEXT)} символів | WAV 8kHz 16bit mono\n")

gclient = texttospeech.TextToSpeechClient()

audio_cfg_tel = texttospeech.AudioConfig(
    audio_encoding=texttospeech.AudioEncoding.LINEAR16,
    sample_rate_hertz=8000,
    effects_profile_id=["telephony-class-application"],
)

print(f"  {'#':<3} {'Модель':<35} {'Час':>7} Файл")
print(f"  {'─'*3} {'─'*35} {'─'*7} {'─'*50}")

# ── 1. Google Standard-B ──
voice = texttospeech.VoiceSelectionParams(language_code="uk-UA", name="uk-UA-Standard-B")
start = time.time()
resp = gclient.synthesize_speech(input=texttospeech.SynthesisInput(ssml=SSML_GOOGLE), voice=voice, audio_config=audio_cfg_tel)
t = time.time() - start
fname = f"{len(TEXT)}sym_google_StandardB_{t:.3f}s.wav"
with open(fname, "wb") as f:
    f.write(resp.audio_content)
print(f"  1   {'Google Standard-B (жін)':<35} {t:>6.3f}с {fname}")

# ── 2. Google Wavenet-B ──
voice = texttospeech.VoiceSelectionParams(language_code="uk-UA", name="uk-UA-Wavenet-B")
start = time.time()
resp = gclient.synthesize_speech(input=texttospeech.SynthesisInput(ssml=SSML_GOOGLE), voice=voice, audio_config=audio_cfg_tel)
t = time.time() - start
fname = f"{len(TEXT)}sym_google_WavenetB_{t:.3f}s.wav"
with open(fname, "wb") as f:
    f.write(resp.audio_content)
print(f"  2   {'Google Wavenet-B (жін)':<35} {t:>6.3f}с {fname}")

# ── 3-5. Google Chirp3-HD (3 голоси) ──
chirp_voices = [
    ("uk-UA-Chirp3-HD-Leda", "Chirp3 Leda (жін)"),
    ("uk-UA-Chirp3-HD-Puck", "Chirp3 Puck (чол)"),
    ("uk-UA-Chirp3-HD-Kore", "Chirp3 Kore (жін)"),
]

for idx, (vname, label) in enumerate(chirp_voices, 3):
    voice_params = texttospeech.VoiceSelectionParams(language_code="uk-UA", name=vname)
    streaming_config = texttospeech.StreamingSynthesizeConfig(voice=voice_params)

    start = time.time()
    t_first = None
    audio_data = b""

    def request_generator():
        yield texttospeech.StreamingSynthesizeRequest(streaming_config=streaming_config)
        yield texttospeech.StreamingSynthesizeRequest(
            input=texttospeech.StreamingSynthesisInput(text=TEXT))

    try:
        responses = gclient.streaming_synthesize(request_generator())
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

        short = vname.replace("uk-UA-Chirp3-HD-", "")
        fname = f"{len(TEXT)}sym_google_Chirp3{short}_{t:.3f}s.wav"
        with open(fname, "wb") as f:
            f.write(wav_data)
        print(f"  {idx}   {'Google ' + label:<35} {t:>6.3f}с {fname}")
    except Exception as e:
        print(f"  {idx}   {'Google ' + label:<35} ПОМИЛКА: {str(e)[:50]}")

# ── 6. Azure Polina ──
config = speechsdk.SpeechConfig(subscription=AZURE_KEY, region=AZURE_REGION)
config.speech_synthesis_voice_name = "uk-UA-PolinaNeural"
config.set_speech_synthesis_output_format(speechsdk.SpeechSynthesisOutputFormat.Raw8Khz16BitMonoPcm)
synth = speechsdk.SpeechSynthesizer(speech_config=config, audio_config=None)
conn = speechsdk.Connection.from_speech_synthesizer(synth)
conn.open(True)
time.sleep(0.3)
synth.speak_text_async("тест").get()

chunks = []
t_first_az = [None]
gen_start = [None]
def on_synth_p(evt, _c=chunks, _t=t_first_az, _s=gen_start):
    if evt.result.audio_data:
        if _t[0] is None:
            _t[0] = time.time() - _s[0]
        _c.append(evt.result.audio_data)
synth.synthesizing.connect(on_synth_p)

gen_start[0] = time.time()
synth.speak_text_async(TEXT).get()
t = time.time() - gen_start[0]

pcm = b"".join(chunks)
wav_data = wrap_pcm_to_wav(pcm, 8000)
fname = f"{len(TEXT)}sym_azure_Polina_{t:.3f}s.wav"
with open(fname, "wb") as f:
    f.write(wav_data)
print(f"  6   {'Azure Polina (жін)':<35} {t:>6.3f}с {fname}")
del synth

# ── 7. Azure Ostap ──
config2 = speechsdk.SpeechConfig(subscription=AZURE_KEY, region=AZURE_REGION)
config2.speech_synthesis_voice_name = "uk-UA-OstapNeural"
config2.set_speech_synthesis_output_format(speechsdk.SpeechSynthesisOutputFormat.Raw8Khz16BitMonoPcm)
synth2 = speechsdk.SpeechSynthesizer(speech_config=config2, audio_config=None)
conn2 = speechsdk.Connection.from_speech_synthesizer(synth2)
conn2.open(True)
time.sleep(0.3)
synth2.speak_text_async("тест").get()

chunks2 = []
t_first_az2 = [None]
gen_start2 = [None]
def on_synth_o(evt, _c=chunks2, _t=t_first_az2, _s=gen_start2):
    if evt.result.audio_data:
        if _t[0] is None:
            _t[0] = time.time() - _s[0]
        _c.append(evt.result.audio_data)
synth2.synthesizing.connect(on_synth_o)

gen_start2[0] = time.time()
synth2.speak_text_async(TEXT).get()
t = time.time() - gen_start2[0]

pcm2 = b"".join(chunks2)
wav_data2 = wrap_pcm_to_wav(pcm2, 8000)
fname = f"{len(TEXT)}sym_azure_Ostap_{t:.3f}s.wav"
with open(fname, "wb") as f:
    f.write(wav_data2)
print(f"  7   {'Azure Ostap (чол)':<35} {t:>6.3f}с {fname}")
del synth2

print(f"\n  Послухайте і оберіть найкращий голос!")


