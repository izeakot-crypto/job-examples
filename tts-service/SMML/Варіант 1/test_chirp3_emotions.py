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

# Тестуємо 3 голоси Chirp3-HD
VOICES = [
    ("uk-UA-Chirp3-HD-Leda", "Leda", "жін"),
    ("uk-UA-Chirp3-HD-Puck", "Puck", "чол"),
    ("uk-UA-Chirp3-HD-Kore", "Kore", "жін"),
]

# Ті самі 10 сценаріїв — але Chirp3 через streaming (без SSML, бо streaming не підтримує)
# + звичайна генерація з SSML для порівняння
TEXTS = [
    ("01_happy",        "Добрий день! Раді вас чути! Дякуємо що зателефонували до компанії Окі-Токі. Мене звати Оксана, чим можу вам допомогти?"),
    ("02_sad",          "На жаль, ми змушені відмовити у вашому запиті. Нам дуже прикро, але ця послуга більше недоступна. Якщо бажаєте, я можу запропонувати альтернативний варіант."),
    ("03_urgent",       "Увага! Це термінове повідомлення! Ваш акаунт буде заблоковано через годину, якщо не підтвердити дані. Будь ласка, зайдіть в особистий кабінет негайно!"),
    ("04_calm",         "Будь ласка, залишайтесь на лінії. Ваш дзвінок дуже важливий для нас. Перший вільний спеціаліст відповість вам найближчим часом."),
    ("05_empathy",      "Вибачте за незручності. Ми розуміємо, як це неприємно, і щиро перепрошуємо. Наша команда вже працює над вирішенням проблеми. Дякуємо за ваше терпіння."),
    ("06_good_news",    "Чудові новини! Вашу проблему повністю вирішено! Все працює як слід. Дякуємо за звернення і гарного вам дня!"),
    ("07_professional", "Я розумію ваше питання. Для детальної консультації я зараз зʼєдную вас з нашим спеціалістом. Зачекайте, будь ласка, декілька секунд."),
    ("08_deescalation", "Я вас розумію і мені дуже шкода, що так сталося. Повірте, ми зробимо все можливе, щоб виправити ситуацію. Зараз я оформлю повернення коштів на вашу картку."),
    ("09_info",         "Звичайно, розповім про наші тарифи. Базовий план — двісті гривень на місяць, включає пʼятсот хвилин розмов. Професійний план — чотириста гривень з необмеженими дзвінками."),
    ("10_farewell",     "Дякуємо за ваш дзвінок! Була рада вам допомогти. Якщо виникнуть питання — телефонуйте будь-коли. Гарного вам дня!"),
]

print(f"Google Chirp3-HD | Streaming | 3 голоси × 10 емоцій | WAV 8kHz\n")

for voice_name, short, gender in VOICES:
    print(f"{'='*65}")
    print(f"  {voice_name} ({gender})")
    print(f"{'='*65}")
    print(f"  {'#':<20} {'Симв':>5} {'Час':>7} {'1й чанк':>8}")
    print(f"  {'─'*20} {'─'*5} {'─'*7} {'─'*8}")

    voice_params = texttospeech.VoiceSelectionParams(language_code="uk-UA", name=voice_name)

    for test_name, text in TEXTS:
        streaming_config = texttospeech.StreamingSynthesizeConfig(voice=voice_params)

        start = time.time()
        t_first = None
        audio_data = b""

        def request_generator():
            yield texttospeech.StreamingSynthesizeRequest(streaming_config=streaming_config)
            yield texttospeech.StreamingSynthesizeRequest(
                input=texttospeech.StreamingSynthesisInput(text=text))

        try:
            responses = gclient.streaming_synthesize(request_generator())
            for response in responses:
                if t_first is None:
                    t_first = time.time() - start
                audio_data += response.audio_content
            t = time.time() - start

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

            fname = f"chirp3_{short}_{test_name}_{t:.3f}s.wav"
            with open(fname, "wb") as f:
                f.write(wav_data)

            first_str = f"{t_first:.3f}с" if t_first else "—"
            print(f"  {test_name:<20} {len(text):>5} {t:>6.3f}с {first_str:>8}")

        except Exception as e:
            print(f"  {test_name:<20} {len(text):>5} ПОМИЛКА: {str(e)[:50]}")

    print()

print(f"  Послухайте і порівняйте голоси та емоції!")
print(f"  Chirp3-HD сам розуміє контекст тексту і додає інтонації.")

