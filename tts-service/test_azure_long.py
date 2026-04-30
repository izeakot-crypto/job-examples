import sys, io, time, wave
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
import azure.cognitiveservices.speech as speechsdk

AZURE_KEY = "YOUR_SECRET_TOKEN"
AZURE_REGION = "westeurope"
VOICE = "uk-UA-PolinaNeural"

TEXTS = [
    "Шановний клієнте, дякуємо що зателефонували до служби підтримки компанії Окі-Токі. На жаль, всі оператори наразі зайняті обслуговуванням інших клієнтів. Ваш дзвінок дуже важливий для нас. Будь ласка, залишайтесь на лінії, і перший вільний спеціаліст відповість вам найближчим часом. Орієнтовний час очікування складає приблизно дві хвилини.",
    "Добрий день! Ви зателефонували на гарячу лінію технічної підтримки. Для вирішення вашого питання, будь ласка, опишіть проблему після звукового сигналу. Наші спеціалісти проаналізують ваше звернення та передзвонять вам протягом тридцяти хвилин. Якщо ваше питання термінове, натисніть один для зʼєднання з черговим оператором. Дякуємо за звернення!",
    "Вітаємо у голосовому меню компанії Окі-Токі! Для зʼєднання з відділом продажів натисніть один. Для технічної підтримки натисніть два. Для бухгалтерії натисніть три. Для звʼязку з менеджером вашого проєкту натисніть чотири. Щоб повторити це меню натисніть зірочку. Якщо ви знаєте внутрішній номер співробітника, наберіть його зараз. Дякуємо що обрали нашу компанію!",
    "Увага! Ваша заявка номер сімсот двадцять три успішно зареєстрована в нашій системі. Відповідальний менеджер Олександр Петренко вже працює над вашим запитом. Очікуваний термін виконання складає два робочі дні. Ви отримаєте повідомлення на вашу електронну пошту та номер телефону коли заявка буде виконана. Якщо у вас виникнуть додаткові питання, зателефонуйте нам або напишіть на електронну адресу підтримки.",
    "Доброго ранку! Це автоматичне повідомлення від компанії Окі-Токі. Нагадуємо вам про заплановану зустріч з нашим менеджером сьогодні о четвертій годині. Зустріч відбудеться онлайн через платформу відеозвʼязку. Посилання для підключення було надіслано на вашу електронну пошту. Якщо вам потрібно перенести зустріч, будь ласка, повідомте нас заздалегідь, зателефонувавши на номер гарячої лінії або написавши повідомлення у чат підтримки на нашому сайті.",
]

def wrap_pcm_to_wav(pcm_data, sample_rate=8000, channels=1, sample_width=2):
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_data)
    return buf.getvalue()

# Звичайний
config_normal = speechsdk.SpeechConfig(subscription=AZURE_KEY, region=AZURE_REGION)
config_normal.speech_synthesis_voice_name = VOICE
config_normal.set_speech_synthesis_output_format(
    speechsdk.SpeechSynthesisOutputFormat.Riff8Khz16BitMonoPcm
)
synth_normal = speechsdk.SpeechSynthesizer(speech_config=config_normal, audio_config=None)
conn1 = speechsdk.Connection.from_speech_synthesizer(synth_normal)
conn1.open(True)
time.sleep(0.5)
synth_normal.speak_text_async("тест").get()

# Стрімінг
config_stream = speechsdk.SpeechConfig(subscription=AZURE_KEY, region=AZURE_REGION)
config_stream.speech_synthesis_voice_name = VOICE
config_stream.set_speech_synthesis_output_format(
    speechsdk.SpeechSynthesisOutputFormat.Raw8Khz16BitMonoPcm
)
synth_stream = speechsdk.SpeechSynthesizer(speech_config=config_stream, audio_config=None)
conn2 = speechsdk.Connection.from_speech_synthesizer(synth_stream)
conn2.open(True)
time.sleep(0.5)
synth_stream.speak_text_async("тест").get()

print(f"Голос: {VOICE} | Формат: WAV 8kHz 16bit mono")
print(f"Тексти: 300+ символів\n")
print(f"  {'#':<3} {'Симв':>5} {'Звичайний':>10} {'Стрімінг':>10} {'1й чанк':>8} {'Різниця':>8}")
print(f"  {'─'*3} {'─'*5} {'─'*10} {'─'*10} {'─'*8} {'─'*8}")

for i, text in enumerate(TEXTS):
    # Звичайний
    start = time.time()
    result = synth_normal.speak_text_async(text).get()
    t_normal = time.time() - start
    fname_n = f"{len(text)}sym_azure_ua_normal_{t_normal:.3f}s.wav"
    with open(fname_n, "wb") as f:
        f.write(result.audio_data)

    # Стрімінг
    chunks = []
    t_first_chunk = [None]
    gen_start = [None]

    def on_synthesizing(evt, _chunks=chunks, _t=t_first_chunk, _s=gen_start):
        if evt.result.audio_data:
            if _t[0] is None:
                _t[0] = time.time() - _s[0]
            _chunks.append(evt.result.audio_data)

    chunks.clear()
    t_first_chunk[0] = None
    synth_stream.synthesizing.connect(on_synthesizing)

    gen_start[0] = time.time()
    result2 = synth_stream.speak_text_async(text).get()
    t_stream = time.time() - gen_start[0]

    pcm_data = b"".join(chunks)
    wav_data = wrap_pcm_to_wav(pcm_data)
    fname_s = f"{len(text)}sym_azure_ua_stream_{t_stream:.3f}s.wav"
    with open(fname_s, "wb") as f:
        f.write(wav_data)

    first_ms = t_first_chunk[0] if t_first_chunk[0] else 0
    ratio = t_normal / t_stream if t_stream > 0 else 0
    print(f"  {i+1:<3} {len(text):>5} {t_normal:>9.3f}с {t_stream:>9.3f}с {first_ms:>7.3f}с {ratio:>7.1f}x")

del synth_normal, synth_stream
print(f"\nФайли: long_1..5_normal.wav та long_1..5_stream.wav")

