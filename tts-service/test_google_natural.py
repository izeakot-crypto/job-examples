import sys, io, time, wave, os, struct
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = r"[USER_HOME]\Downloads\tts-488311-d5a1cbf88094.json"

from google.cloud import texttospeech

TEXT = "Добрий день! Дякуємо що зателефонували до компанії Окі-Токі. Зараз усі оператори зайняті, але ваш дзвінок дуже важливий для нас. Залишайтесь на лінії, будь ласка."

SSML_NATURAL = """<speak>
<prosody rate="97%" pitch="+1st">
Добрий день! <break time="300ms"/>
Дякуємо що зателефонували до компанії Окі-Токі.
<break time="200ms"/>
Зараз усі оператори зайняті, <break time="150ms"/> але ваш дзвінок дуже важливий для нас.
<break time="250ms"/>
Залишайтесь на лінії, будь ласка.
</prosody>
</speak>"""

SSML_WARM = """<speak>
<prosody rate="95%" pitch="+2st" volume="+2dB">
Добрий день! <break time="350ms"/>
Дякуємо що зателефонували до компанії Окі-Токі.
<break time="250ms"/>
Зараз усі оператори зайняті, <break time="200ms"/> але ваш дзвінок дуже важливий для нас.
<break time="300ms"/>
Залишайтесь на лінії, <break time="100ms"/> будь ласка.
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

gclient = texttospeech.TextToSpeechClient()

audio_cfg_8k = texttospeech.AudioConfig(
    audio_encoding=texttospeech.AudioEncoding.LINEAR16,
    sample_rate_hertz=8000,
)

audio_cfg_8k_telephony = texttospeech.AudioConfig(
    audio_encoding=texttospeech.AudioEncoding.LINEAR16,
    sample_rate_hertz=8000,
    effects_profile_id=["telephony-class-application"],
)

print(f"Google TTS — тест природності | WAV 8kHz 16bit mono")
print(f'Текст: ({len(TEXT)} сим)\n')

TESTS = [
    # (назва, голос, ssml/text, audio_config, тип)
    ("WavenetB_plain",       "uk-UA-Wavenet-B",       None,         audio_cfg_8k,           "text"),
    ("WavenetB_ssml",        "uk-UA-Wavenet-B",       SSML_NATURAL, audio_cfg_8k,           "ssml"),
    ("WavenetB_warm_ssml",   "uk-UA-Wavenet-B",       SSML_WARM,    audio_cfg_8k,           "ssml"),
    ("WavenetB_telephony",   "uk-UA-Wavenet-B",       SSML_WARM,    audio_cfg_8k_telephony, "ssml"),
    ("Chirp3_Leda",          "uk-UA-Chirp3-HD-Leda",  None,         None,                   "stream"),
    ("Chirp3_Kore",          "uk-UA-Chirp3-HD-Kore",  None,         None,                   "stream"),
    ("Chirp3_Puck",          "uk-UA-Chirp3-HD-Puck",  None,         None,                   "stream"),
    ("Chirp3_Achernar",      "uk-UA-Chirp3-HD-Achernar", None,      None,                   "stream"),
]

print(f"  {'Тест':<25} {'Час':>7} {'1й чанк':>8} Файл")
print(f"  {'─'*25} {'─'*7} {'─'*8} {'─'*45}")

for test_name, voice_name, ssml, acfg, gen_type in TESTS:
    voice_params = texttospeech.VoiceSelectionParams(language_code="uk-UA", name=voice_name)

    if gen_type == "stream":
        # Chirp3-HD streaming
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
            t_total = time.time() - start

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

            fname = f"{len(TEXT)}sym_g_{test_name}_{t_total:.3f}s.wav"
            with open(fname, "wb") as f:
                f.write(wav_data)

            first_str = f"{t_first:.3f}с" if t_first else "—"
            print(f"  {test_name:<25} {t_total:>6.3f}с {first_str:>8} {fname}")
        except Exception as e:
            print(f"  {test_name:<25} ПОМИЛКА: {str(e)[:60]}")
    else:
        # Wavenet normal/ssml
        if gen_type == "ssml":
            synth_input = texttospeech.SynthesisInput(ssml=ssml)
        else:
            synth_input = texttospeech.SynthesisInput(text=TEXT)

        start = time.time()
        resp = gclient.synthesize_speech(input=synth_input, voice=voice_params, audio_config=acfg)
        t_total = time.time() - start

        fname = f"{len(TEXT)}sym_g_{test_name}_{t_total:.3f}s.wav"
        with open(fname, "wb") as f:
            f.write(resp.audio_content)
        print(f"  {test_name:<25} {t_total:>6.3f}с      —   {fname}")

print(f"\n  Порівняйте: plain vs ssml vs Chirp3-HD!")

