import sys, io, time, wave, os, struct
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = r"[USER_HOME]\Downloads\tts-488311-d5a1cbf88094.json"

from google.cloud import texttospeech

TEXTS = [
    "Дякую за дзвінок! Зачекайте, зʼєдную вас з оператором.",
    "Добрий день! Мене звати Оксана, я ваш віртуальний помічник. Чим можу допомогти?",
    "Ваш запит прийнято. Очікуйте відповідь оператора протягом хвилини. Дякуємо за терпіння, ми цінуємо ваш час.",
]

def wrap_pcm_to_wav(pcm_data, sample_rate=8000, channels=1, sample_width=2):
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_data)
    return buf.getvalue()

def downsample_pcm(pcm_data, from_rate, to_rate):
    samples = struct.unpack(f'<{len(pcm_data)//2}h', pcm_data)
    ratio = from_rate / to_rate
    new_len = int(len(samples) / ratio)
    resampled = []
    for i in range(new_len):
        idx = int(i * ratio)
        if idx < len(samples):
            resampled.append(samples[idx])
    return struct.pack(f'<{len(resampled)}h', *resampled)

gclient = texttospeech.TextToSpeechClient()

# ═══════════════════════════════════════════════════
# Тести на швидкість генерації
# ═══════════════════════════════════════════════════

TESTS = [
    # (назва, голос, speaking_rate, тип)
    ("Wavenet-B normal", "uk-UA-Wavenet-B", 1.0, "normal"),
    ("Wavenet-B rate1.2", "uk-UA-Wavenet-B", 1.2, "normal"),
    ("Wavenet-B rate1.5", "uk-UA-Wavenet-B", 1.5, "normal"),
    ("Standard-A normal", "uk-UA-Standard-A", 1.0, "normal"),
    ("Standard-A rate1.2", "uk-UA-Standard-A", 1.2, "normal"),
    ("Chirp3-Puck stream", "uk-UA-Chirp3-HD-Puck", 1.0, "stream"),
    ("Chirp3-Puck rate1.2", "uk-UA-Chirp3-HD-Puck", 1.2, "stream"),
    ("Chirp3-Leda stream", "uk-UA-Chirp3-HD-Leda", 1.0, "stream"),
]

print(f"Google Cloud TTS — тест швидкості | WAV 8kHz 16bit mono")
print(f"Тестів: {len(TESTS)} | Текстів: {len(TEXTS)}\n")
print(f"  {'Тест':<25} {'Симв':>5} {'Час':>7} {'1й чанк':>8} Файл")
print(f"  {'─'*25} {'─'*5} {'─'*7} {'─'*8} {'─'*40}")

for test_name, voice_name, rate, gen_type in TESTS:
    for text in TEXTS:
        voice_params = texttospeech.VoiceSelectionParams(
            language_code="uk-UA",
            name=voice_name,
        )

        if gen_type == "stream":
            # Стрімінг (Chirp3-HD)
            streaming_config = texttospeech.StreamingSynthesizeConfig(
                voice=voice_params,
            )

            start = time.time()
            t_first = None
            audio_data = b""

            def request_generator():
                yield texttospeech.StreamingSynthesizeRequest(
                    streaming_config=streaming_config
                )
                yield texttospeech.StreamingSynthesizeRequest(
                    input=texttospeech.StreamingSynthesisInput(text=text)
                )

            try:
                responses = gclient.streaming_synthesize(request_generator())
                for response in responses:
                    if t_first is None:
                        t_first = time.time() - start
                    audio_data += response.audio_content
                t_total = time.time() - start

                # Конвертація в 8kHz WAV
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

                short = test_name.replace(" ", "_")
                fname = f"{len(text)}sym_g_{short}_{t_total:.3f}s.wav"
                with open(fname, "wb") as f:
                    f.write(wav_data)

                first_str = f"{t_first:.3f}с" if t_first else "  —  "
                print(f"  {test_name:<25} {len(text):>5} {t_total:>6.3f}с {first_str:>8} {fname}")
            except Exception as e:
                print(f"  {test_name:<25} {len(text):>5} ПОМИЛКА: {str(e)[:60]}")

        else:
            # Звичайна генерація
            audio_config = texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.LINEAR16,
                sample_rate_hertz=8000,
                speaking_rate=rate,
            )
            synthesis_input = texttospeech.SynthesisInput(text=text)

            start = time.time()
            response = gclient.synthesize_speech(
                input=synthesis_input,
                voice=voice_params,
                audio_config=audio_config,
            )
            t_total = time.time() - start

            short = test_name.replace(" ", "_")
            fname = f"{len(text)}sym_g_{short}_{t_total:.3f}s.wav"
            with open(fname, "wb") as f:
                f.write(response.audio_content)

            print(f"  {test_name:<25} {len(text):>5} {t_total:>6.3f}с      —   {fname}")

    print()

print(f"Послухайте і порівняйте!")

