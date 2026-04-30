import sys, io, time, wave, os, struct
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = r"[USER_HOME]\Downloads\tts-488311-d5a1cbf88094.json"

from google.cloud import texttospeech

VOICES = [
    ("uk-UA-Chirp3-HD-Leda", "Жін"),
    ("uk-UA-Chirp3-HD-Kore", "Жін"),
    ("uk-UA-Chirp3-HD-Achernar", "Жін"),
    ("uk-UA-Chirp3-HD-Puck", "Чол"),
    ("uk-UA-Chirp3-HD-Achird", "Чол"),
    ("uk-UA-Wavenet-B", "Жін"),
]

TEXTS = [
    "Дякую за дзвінок! Зачекайте, зʼєдную вас з оператором.",
    "Добрий день! Мене звати Оксана, я ваш віртуальний помічник. Чим можу допомогти?",
    "Ваш запит прийнято. Очікуйте відповідь оператора протягом хвилини. Дякуємо за терпіння, ми цінуємо ваш час.",
    "Привіт! На жаль, всі оператори зараз зайняті. Будь ласка, залишайтесь на лінії, і перший вільний спеціаліст відповість вам найближчим часом.",
    "Шановний клієнте, дякуємо що звернулися до нашої компанії Окі-Токі. Орієнтовний час очікування складає три хвилини. Якщо бажаєте, залишіть голосове повідомлення, і ми передзвонимо протягом години.",
]

def wrap_pcm_to_wav(pcm_data, sample_rate=8000, channels=1, sample_width=2):
    """Обгортає raw PCM дані у WAV заголовок"""
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_data)
    return buf.getvalue()

def downsample_pcm(pcm_data, from_rate, to_rate):
    """Проста конвертація PCM з однієї частоти в іншу"""
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

audio_config = texttospeech.AudioConfig(
    audio_encoding=texttospeech.AudioEncoding.LINEAR16,
    sample_rate_hertz=8000,
)

print(f"Google Cloud TTS | Формат: WAV 8kHz 16bit mono | Стрімінг + Звичайна")
print(f"Голосів: {len(VOICES)} | Текстів: {len(TEXTS)}\n")

print(f"  {'Голос':<32} {'Симв':>5} {'Час':>7} {'1й чанк':>8} Файл")
print(f"  {'─'*32} {'─'*5} {'─'*7} {'─'*8} {'─'*40}")

for voice_name, gender in VOICES:
    for i, text in enumerate(TEXTS):
        voice_params = texttospeech.VoiceSelectionParams(
            language_code="uk-UA",
            name=voice_name,
        )
        synthesis_input = texttospeech.SynthesisInput(text=text)

        # Спроба стрімінгу
        start = time.time()
        t_first = None
        audio_data = b""

        streaming_config = texttospeech.StreamingSynthesizeConfig(
            voice=voice_params,
        )

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
            t_stream = time.time() - start

            short_name = voice_name.replace("uk-UA-Chirp3-HD-", "").replace("uk-UA-", "")
            fname = f"{len(text)}sym_gstream_{short_name}_{t_stream:.3f}s.wav"

            # Перевіряємо чи це вже WAV чи raw PCM
            if audio_data[:4] == b'RIFF':
                # Вже WAV — перевіримо sample rate
                with io.BytesIO(audio_data) as buf:
                    with wave.open(buf, 'rb') as wf:
                        sr = wf.getframerate()
                        ch = wf.getnchannels()
                        sw = wf.getsampwidth()
                        pcm = wf.readframes(wf.getnframes())
                if sr != 8000:
                    pcm_8k = downsample_pcm(pcm, sr, 8000)
                    wav_data = wrap_pcm_to_wav(pcm_8k, 8000, ch, sw)
                else:
                    wav_data = audio_data
            else:
                # Raw PCM — streaming часто повертає 24kHz
                # Спробуємо визначити sample rate по розміру
                # Якщо не 8kHz — конвертуємо з 24kHz (дефолт streaming)
                duration_guess_24k = len(audio_data) / (24000 * 2)
                duration_guess_8k = len(audio_data) / (8000 * 2)
                # Якщо тривалість при 8kHz нереально велика — це 24kHz
                if duration_guess_8k > 60:  # більше 60 сек для короткого тексту
                    pcm_8k = downsample_pcm(audio_data, 24000, 8000)
                    wav_data = wrap_pcm_to_wav(pcm_8k, 8000)
                else:
                    # Спробуємо 24kHz як дефолт для стрімінгу
                    pcm_8k = downsample_pcm(audio_data, 24000, 8000)
                    wav_data = wrap_pcm_to_wav(pcm_8k, 8000)

            with open(fname, "wb") as f:
                f.write(wav_data)

            first_ms = t_first if t_first else 0
            print(f"  {voice_name:<32} {len(text):>5} {t_stream:>6.3f}с {first_ms:>7.3f}с {fname}")

        except Exception as e:
            # Якщо стрімінг не підтримується — звичайна генерація (вже має WAV header з 8kHz)
            start = time.time()
            response = gclient.synthesize_speech(
                input=synthesis_input,
                voice=voice_params,
                audio_config=audio_config,
            )
            t_normal = time.time() - start

            short_name = voice_name.replace("uk-UA-Chirp3-HD-", "").replace("uk-UA-", "")
            fname = f"{len(text)}sym_google_{short_name}_{t_normal:.3f}s.wav"
            with open(fname, "wb") as f:
                f.write(response.audio_content)
            print(f"  {voice_name:<32} {len(text):>5} {t_normal:>6.3f}с     —    {fname} (без стрімінгу)")

    print()

print(f"Послухайте файли і оберіть найкращий голос!")

