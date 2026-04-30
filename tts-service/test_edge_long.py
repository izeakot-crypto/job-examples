import sys, io, time, asyncio
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
import edge_tts

VOICE = "uk-UA-PolinaNeural"

TEXTS = [
    "Шановний клієнте, дякуємо що зателефонували до служби підтримки компанії Окі-Токі. На жаль, всі оператори наразі зайняті обслуговуванням інших клієнтів. Ваш дзвінок дуже важливий для нас. Будь ласка, залишайтесь на лінії, і перший вільний спеціаліст відповість вам найближчим часом. Орієнтовний час очікування складає приблизно дві хвилини.",
    "Добрий день! Ви зателефонували на гарячу лінію технічної підтримки. Для вирішення вашого питання, будь ласка, опишіть проблему після звукового сигналу. Наші спеціалісти проаналізують ваше звернення та передзвонять вам протягом тридцяти хвилин. Якщо ваше питання термінове, натисніть один для зʼєднання з черговим оператором. Дякуємо за звернення!",
    "Вітаємо у голосовому меню компанії Окі-Токі! Для зʼєднання з відділом продажів натисніть один. Для технічної підтримки натисніть два. Для бухгалтерії натисніть три. Для звʼязку з менеджером вашого проєкту натисніть чотири. Щоб повторити це меню натисніть зірочку. Якщо ви знаєте внутрішній номер співробітника, наберіть його зараз. Дякуємо що обрали нашу компанію!",
    "Увага! Ваша заявка номер сімсот двадцять три успішно зареєстрована в нашій системі. Відповідальний менеджер Олександр Петренко вже працює над вашим запитом. Очікуваний термін виконання складає два робочі дні. Ви отримаєте повідомлення на вашу електронну пошту та номер телефону коли заявка буде виконана. Якщо у вас виникнуть додаткові питання, зателефонуйте нам або напишіть на електронну адресу підтримки.",
    "Доброго ранку! Це автоматичне повідомлення від компанії Окі-Токі. Нагадуємо вам про заплановану зустріч з нашим менеджером сьогодні о четвертій годині. Зустріч відбудеться онлайн через платформу відеозвʼязку. Посилання для підключення було надіслано на вашу електронну пошту. Якщо вам потрібно перенести зустріч, будь ласка, повідомте нас заздалегідь, зателефонувавши на номер гарячої лінії або написавши повідомлення у чат підтримки на нашому сайті.",
]

async def edge_save(text, voice, fname):
    comm = edge_tts.Communicate(text, voice)
    start = time.time()
    await comm.save(fname)
    return time.time() - start

async def edge_stream(text, voice, fname):
    comm = edge_tts.Communicate(text, voice)
    start = time.time()
    t_first = None
    audio = b""
    async for chunk in comm.stream():
        if chunk["type"] == "audio":
            if t_first is None:
                t_first = time.time() - start
            audio += chunk["data"]
    elapsed = time.time() - start
    with open(fname, "wb") as f:
        f.write(audio)
    return elapsed, t_first or 0

async def main():
    print(f"Голос: {VOICE} | Формат: MP3 24kHz (Edge TTS)")
    print(f"Тексти: 300+ символів\n")
    print(f"  {'#':<3} {'Симв':>5} {'save()':>10} {'stream()':>10} {'1й чанк':>8} {'Різниця':>8}")
    print(f"  {'─'*3} {'─'*5} {'─'*10} {'─'*10} {'─'*8} {'─'*8}")

    for i, text in enumerate(TEXTS):
        # save()
        fname_s = f"_tmp_save.mp3"
        t_save = await edge_save(text, VOICE, fname_s)
        import os
        fname_save = f"{len(text)}sym_edge_ua_save_{t_save:.3f}s.mp3"
        os.rename(fname_s, fname_save)

        # stream()
        fname_st = f"_tmp_stream.mp3"
        t_stream, t_first = await edge_stream(text, VOICE, fname_st)
        fname_stream = f"{len(text)}sym_edge_ua_stream_{t_stream:.3f}s.mp3"
        os.rename(fname_st, fname_stream)

        ratio = t_save / t_stream if t_stream > 0 else 0
        print(f"  {i+1:<3} {len(text):>5} {t_save:>9.3f}с {t_stream:>9.3f}с {t_first:>7.3f}с {ratio:>7.1f}x")

asyncio.run(main())
