import sys, io, time, wave, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = r"[USER_HOME]\Downloads\tts-488311-d5a1cbf88094.json"

from google.cloud import texttospeech
import azure.cognitiveservices.speech as speechsdk

AZURE_KEY = "YOUR_SECRET_TOKEN"
AZURE_REGION = "westeurope"

TEXT = "Шановний клієнте, дякуємо що звернулися до нашої компанії Окі-Токі. На жаль, всі оператори зараз зайняті. Будь ласка, залишайтесь на лінії, і перший вільний спеціаліст відповість вам найближчим часом. Орієнтовний час очікування складає три хвилини. Якщо бажаєте, залишіть голосове повідомлення, і ми передзвонимо."

print(f'Текст: ({len(TEXT)} символів)')
print(f'"{TEXT}"\n')

def wrap_pcm_to_wav(pcm_data, sample_rate=8000):
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_data)
    return buf.getvalue()

# ═══════════════════════════════════════
# 1. Google Standard-A
# ═══════════════════════════════════════
print(f"{'='*60}")
print(f"  1. Google Standard-A (uk-UA)")
print(f"{'='*60}")

gclient = texttospeech.TextToSpeechClient()

voice_std = texttospeech.VoiceSelectionParams(language_code="uk-UA", name="uk-UA-Standard-A")
audio_cfg = texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.LINEAR16, sample_rate_hertz=8000)
synth_input = texttospeech.SynthesisInput(text=TEXT)

start = time.time()
resp = gclient.synthesize_speech(input=synth_input, voice=voice_std, audio_config=audio_cfg)
t1 = time.time() - start

fname1 = f"{len(TEXT)}sym_google_StandardA_{t1:.3f}s.wav"
with open(fname1, "wb") as f:
    f.write(resp.audio_content)
print(f"  {t1:.3f}с | {len(resp.audio_content)}б | {fname1}")

# ═══════════════════════════════════════
# 2. Google Wavenet-B
# ═══════════════════════════════════════
print(f"\n{'='*60}")
print(f"  2. Google Wavenet-B (uk-UA)")
print(f"{'='*60}")

voice_wn = texttospeech.VoiceSelectionParams(language_code="uk-UA", name="uk-UA-Wavenet-B")

start = time.time()
resp = gclient.synthesize_speech(input=synth_input, voice=voice_wn, audio_config=audio_cfg)
t2 = time.time() - start

fname2 = f"{len(TEXT)}sym_google_WavenetB_{t2:.3f}s.wav"
with open(fname2, "wb") as f:
    f.write(resp.audio_content)
print(f"  {t2:.3f}с | {len(resp.audio_content)}б | {fname2}")

# ═══════════════════════════════════════
# 3. Azure Polina (streaming)
# ═══════════════════════════════════════
print(f"\n{'='*60}")
print(f"  3. Azure Polina Neural (uk-UA, streaming)")
print(f"{'='*60}")

config = speechsdk.SpeechConfig(subscription=AZURE_KEY, region=AZURE_REGION)
config.speech_synthesis_voice_name = "uk-UA-PolinaNeural"
config.set_speech_synthesis_output_format(speechsdk.SpeechSynthesisOutputFormat.Raw8Khz16BitMonoPcm)

synth = speechsdk.SpeechSynthesizer(speech_config=config, audio_config=None)
conn = speechsdk.Connection.from_speech_synthesizer(synth)
conn.open(True)
time.sleep(0.3)
synth.speak_text_async("тест").get()

chunks = []
t_first = [None]
gen_start = [None]

def on_synthesizing(evt):
    if evt.result.audio_data:
        if t_first[0] is None:
            t_first[0] = time.time() - gen_start[0]
        chunks.append(evt.result.audio_data)

synth.synthesizing.connect(on_synthesizing)
gen_start[0] = time.time()
result = synth.speak_text_async(TEXT).get()
t3 = time.time() - gen_start[0]

pcm = b"".join(chunks)
wav_data = wrap_pcm_to_wav(pcm, 8000)

fname3 = f"{len(TEXT)}sym_azure_Polina_stream_{t3:.3f}s.wav"
with open(fname3, "wb") as f:
    f.write(wav_data)

first_str = f"{t_first[0]:.3f}с" if t_first[0] else "—"
print(f"  {t3:.3f}с | 1й чанк: {first_str} | {len(wav_data)}б | {fname3}")

del synth

# ═══════════════════════════════════════
# Підсумок
# ═══════════════════════════════════════
print(f"\n{'='*60}")
print(f"  ПІДСУМОК ({len(TEXT)} символів)")
print(f"{'='*60}")
print(f"  Google Standard-A:  {t1:.3f}с  | {fname1}")
print(f"  Google Wavenet-B:   {t2:.3f}с  | {fname2}")
print(f"  Azure Polina:       {t3:.3f}с  (1й чанк: {first_str}) | {fname3}")
print(f"\n  Послухайте і порівняйте якість!")


