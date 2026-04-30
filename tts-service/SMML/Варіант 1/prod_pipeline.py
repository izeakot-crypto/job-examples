import sys, io, time, wave, os, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from openai import OpenAI
import azure.cognitiveservices.speech as speechsdk

OPENAI_KEY = "YOUR_OPENAI_API_KEY"
AZURE_KEY = "YOUR_SECRET_TOKEN"
AZURE_REGION = "westeurope"

llm = OpenAI(api_key=OPENAI_KEY)

def wrap_pcm_to_wav(pcm_data, sample_rate=8000):
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_data)
    return buf.getvalue()

# ═══════════════════════════════════════
# СИСТЕМНИЙ ПРОМПТ для бота кол-центру
# ═══════════════════════════════════════
BOT_SYSTEM = """Ти — віртуальний помічник кол-центру компанії Окі-Токі. Тебе звати Оксана.
Правила:
- Відповідай українською мовою
- Будь ввічливою, професійною, емпатичною
- Відповіді короткі — 2-4 речення (для телефонії)
- Якщо не можеш вирішити — переводь на оператора
- Ніколи не вигадуй інформацію"""

# ═══════════════════════════════════════
# СИСТЕМНИЙ ПРОМПТ для SSML розмітника
# ═══════════════════════════════════════
SSML_SYSTEM = """Ти — експерт з SSML розмітки для голосового бота кол-центру.
Твоє завдання: додати SSML розмітку до тексту відповіді бота для Azure TTS (uk-UA-PolinaNeural).

Аналізуй історію діалогу та емоційний контекст:
- Якщо клієнт незадоволений → сповільнений темп, м'який тон, низький pitch
- Якщо гарна новина → швидший темп, вищий pitch, більша гучність
- Якщо рутинна інформація → нейтральний темп, стандартний pitch
- Якщо вибачення → повільний темп, тихий, низький pitch
- Якщо привітання → дружній, трохи вищий pitch
- Якщо прощання → теплий, позитивний тон

Доступні SSML параметри:
- <prosody rate="90-110%" pitch="-3st..+4st" volume="soft/medium/loud/+NdB">
- <break time="100ms-500ms"/>
- <emphasis level="moderate/strong">

Правила:
- Розбивай текст на логічні фрази
- Додавай паузи між фразами (200-400мс)
- Варіюй pitch і rate для природності
- НЕ додавай зайвих тегів
- Повертай ТІЛЬКИ SSML, без пояснень
- Формат: <speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='uk-UA'><voice name='uk-UA-PolinaNeural'>...текст з розміткою...</voice></speak>"""

# ═══════════════════════════════════════
# 10 ДІАЛОГІВ (реальні сценарії кол-центру)
# ═══════════════════════════════════════
DIALOGS = [
    {
        "name": "01_new_client",
        "scenario": "Новий клієнт телефонує вперше",
        "messages": [
            {"role": "user", "content": "Алло, добрий день!"},
        ],
    },
    {
        "name": "02_angry_delivery",
        "scenario": "Клієнт злий — замовлення не доставлено",
        "messages": [
            {"role": "user", "content": "Алло! Де моє замовлення?! Я чекаю вже тиждень! Це неприпустимо!"},
        ],
    },
    {
        "name": "03_refund_request",
        "scenario": "Клієнт вимагає повернення коштів",
        "messages": [
            {"role": "user", "content": "Я хочу повернути гроші за підписку. Мене не влаштовує якість послуг."},
        ],
    },
    {
        "name": "04_tariff_question",
        "scenario": "Клієнт питає про тарифи",
        "messages": [
            {"role": "user", "content": "Добрий день, розкажіть будь ласка які у вас є тарифні плани і скільки коштують?"},
        ],
    },
    {
        "name": "05_problem_solved",
        "scenario": "Продовження діалогу — проблему вирішено",
        "messages": [
            {"role": "user", "content": "У мене не працює особистий кабінет, не можу зайти вже другий день!"},
            {"role": "assistant", "content": "Прошу вибачення за незручності. Зараз перевірю статус вашого акаунту. Назвіть, будь ласка, вашу електронну адресу."},
            {"role": "user", "content": "petrov@gmail.com"},
            {"role": "assistant", "content": "Дякую. Я бачу проблему — ваш акаунт був тимчасово заблокований через оновлення системи. Зараз розблокую."},
            {"role": "user", "content": "Ну і довго ще чекати?"},
        ],
    },
    {
        "name": "06_transfer_operator",
        "scenario": "Складне питання — треба переводити на оператора",
        "messages": [
            {"role": "user", "content": "Мені потрібно змінити юридичну адресу в договорі і переоформити рахунок на іншу компанію."},
        ],
    },
    {
        "name": "07_thank_goodbye",
        "scenario": "Клієнт дякує і прощається",
        "messages": [
            {"role": "user", "content": "Не працює інтеграція з CRM"},
            {"role": "assistant", "content": "Розумію проблему. Спробуйте перезавантажити модуль інтеграції в налаштуваннях. Якщо не допоможе — я зʼєднаю вас з технічним спеціалістом."},
            {"role": "user", "content": "О, спрацювало! Дякую велике, ви мені дуже допомогли!"},
        ],
    },
    {
        "name": "08_waiting_line",
        "scenario": "Всі оператори зайняті — клієнт чекає",
        "messages": [
            {"role": "user", "content": "Мені потрібен оператор, з'єднайте мене будь ласка"},
            {"role": "assistant", "content": "Звичайно, зараз зʼєдную вас з оператором."},
            {"role": "user", "content": "Ну скільки ще чекати? Я вже п'ять хвилин на лінії!"},
        ],
    },
    {
        "name": "09_service_outage",
        "scenario": "Масовий збій сервісу, клієнт хвилюється",
        "messages": [
            {"role": "user", "content": "У нас весь кол-центр не працює! У нас зараз пік дзвінків, ми втрачаємо клієнтів кожну хвилину!"},
        ],
    },
    {
        "name": "10_happy_upgrade",
        "scenario": "Клієнт хоче збільшити план — позитивний настрій",
        "messages": [
            {"role": "user", "content": "Привіт! Ми дуже задоволені вашим сервісом і хочемо перейти на більший тарифний план. Що порекомендуєте?"},
        ],
    },
]

# ═══════════════════════════════════════
# Azure TTS — підготовка з прогрівом
# ═══════════════════════════════════════
config = speechsdk.SpeechConfig(subscription=AZURE_KEY, region=AZURE_REGION)
config.speech_synthesis_voice_name = "uk-UA-PolinaNeural"
config.set_speech_synthesis_output_format(speechsdk.SpeechSynthesisOutputFormat.Raw8Khz16BitMonoPcm)

synth = speechsdk.SpeechSynthesizer(speech_config=config, audio_config=None)
conn = speechsdk.Connection.from_speech_synthesizer(synth)
conn.open(True)
time.sleep(0.3)
synth.speak_text_async("тест").get()

print(f"{'='*70}")
print(f"  ПРОДАКШИН ПАЙПЛАЙН: Діалог → GPT-4o-mini → SSML → Azure TTS")
print(f"{'='*70}\n")

results = []

for dialog in DIALOGS:
    print(f"┌─── {dialog['name']}: {dialog['scenario']}")

    # Показуємо історію
    for msg in dialog["messages"]:
        role = "Клієнт" if msg["role"] == "user" else "Бот"
        print(f"│  {role}: {msg['content'][:80]}")

    # ═══ ЕТАП 1: LLM генерує відповідь ═══
    t1_start = time.time()
    messages_for_bot = [{"role": "system", "content": BOT_SYSTEM}] + dialog["messages"]

    resp1 = llm.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages_for_bot,
        max_tokens=200,
        temperature=0.7,
    )
    bot_answer = resp1.choices[0].message.content
    t1 = time.time() - t1_start

    print(f"│")
    print(f"│  [Етап 1] GPT-4o-mini відповідь ({t1:.3f}с):")
    print(f"│  Бот: {bot_answer[:100]}")

    # ═══ ЕТАП 2: LLM додає SSML розмітку ═══
    t2_start = time.time()

    # Формуємо контекст для розмітника
    history_text = "\n".join([
        f"{'Клієнт' if m['role']=='user' else 'Бот'}: {m['content']}"
        for m in dialog["messages"]
    ])

    ssml_prompt = f"""Історія діалогу:
{history_text}

Відповідь бота (plain text):
{bot_answer}

Додай SSML розмітку з правильною емоційною окраскою."""

    resp2 = llm.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SSML_SYSTEM},
            {"role": "user", "content": ssml_prompt},
        ],
        max_tokens=500,
        temperature=0.3,
    )
    ssml_text = resp2.choices[0].message.content
    t2 = time.time() - t2_start

    # Очистка від можливих ```xml оболонок
    ssml_text = ssml_text.strip()
    if ssml_text.startswith("```"):
        ssml_text = ssml_text.split("\n", 1)[1] if "\n" in ssml_text else ssml_text
        if ssml_text.endswith("```"):
            ssml_text = ssml_text[:-3].strip()

    print(f"│  [Етап 2] SSML розмітка ({t2:.3f}с)")

    # ═══ ЕТАП 3: Azure TTS озвучує ═══
    t3_start = time.time()
    chunks = []
    t_first = [None]
    gen_start = [None]

    def on_synth(evt, _c=chunks, _t=t_first, _s=gen_start):
        if evt.result.audio_data:
            if _t[0] is None:
                _t[0] = time.time() - _s[0]
            _c.append(evt.result.audio_data)

    synth.synthesizing.connect(on_synth)
    gen_start[0] = time.time()

    try:
        result = synth.speak_ssml_async(ssml_text).get()
        t3 = time.time() - gen_start[0]

        if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
            pcm = b"".join(chunks)
            wav_data = wrap_pcm_to_wav(pcm)

            t_total = t1 + t2 + t3
            fname = f"{dialog['name']}_{t_total:.3f}s.wav"
            with open(fname, "wb") as f:
                f.write(wav_data)

            first_str = f"{t_first[0]:.3f}с" if t_first[0] else "—"
            print(f"│  [Етап 3] Azure TTS ({t3:.3f}с, 1й чанк: {first_str})")
            print(f"│")
            print(f"│  ПІДСУМОК: GPT {t1:.3f}с + SSML {t2:.3f}с + TTS {t3:.3f}с = {t_total:.3f}с")
            print(f"│  Файл: {fname}")

            results.append({
                "name": dialog["name"],
                "scenario": dialog["scenario"],
                "answer": bot_answer,
                "t_llm": t1, "t_ssml": t2, "t_tts": t3, "t_total": t_total,
                "file": fname,
            })
        else:
            # SSML помилка — пробуємо plain text
            cancel = result.cancellation_details
            print(f"│  [!] SSML помилка, пробую plain text...")

            chunks2 = []
            t_first2 = [None]
            gen_start2 = [None]

            def on_synth2(evt, _c=chunks2, _t=t_first2, _s=gen_start2):
                if evt.result.audio_data:
                    if _t[0] is None:
                        _t[0] = time.time() - _s[0]
                    _c.append(evt.result.audio_data)

            synth.synthesizing.connect(on_synth2)
            gen_start2[0] = time.time()
            result2 = synth.speak_text_async(bot_answer).get()
            t3 = time.time() - gen_start2[0]

            pcm2 = b"".join(chunks2)
            wav_data = wrap_pcm_to_wav(pcm2)

            t_total = t1 + t2 + t3
            fname = f"{dialog['name']}_fallback_{t_total:.3f}s.wav"
            with open(fname, "wb") as f:
                f.write(wav_data)

            print(f"│  [Етап 3] Fallback plain ({t3:.3f}с)")
            print(f"│  ПІДСУМОК: {t_total:.3f}с | {fname}")

            results.append({
                "name": dialog["name"],
                "scenario": dialog["scenario"],
                "answer": bot_answer,
                "t_llm": t1, "t_ssml": t2, "t_tts": t3, "t_total": t_total,
                "file": fname,
                "fallback": True,
            })
    except Exception as e:
        print(f"│  [!] ПОМИЛКА: {str(e)[:60]}")

    print(f"└{'─'*69}\n")

del synth

# ═══════════════════════════════════════
# ФІНАЛЬНА ТАБЛИЦЯ
# ═══════════════════════════════════════
print(f"\n{'='*70}")
print(f"  ФІНАЛЬНА ТАБЛИЦЯ")
print(f"{'='*70}")
print(f"  {'#':<22} {'GPT':>6} {'SSML':>6} {'TTS':>6} {'РАЗОМ':>7} Файл")
print(f"  {'─'*22} {'─'*6} {'─'*6} {'─'*6} {'─'*7} {'─'*30}")

for r in results:
    fb = " (fb)" if r.get("fallback") else ""
    print(f"  {r['name']:<22} {r['t_llm']:>5.2f}с {r['t_ssml']:>5.2f}с {r['t_tts']:>5.2f}с {r['t_total']:>6.2f}с {r['file']}{fb}")

if results:
    avg_llm = sum(r['t_llm'] for r in results) / len(results)
    avg_ssml = sum(r['t_ssml'] for r in results) / len(results)
    avg_tts = sum(r['t_tts'] for r in results) / len(results)
    avg_total = sum(r['t_total'] for r in results) / len(results)
    print(f"  {'─'*22} {'─'*6} {'─'*6} {'─'*6} {'─'*7}")
    print(f"  {'СЕРЕДНЄ':<22} {avg_llm:>5.2f}с {avg_ssml:>5.2f}с {avg_tts:>5.2f}с {avg_total:>6.2f}с")

print(f"\n  Послухайте файли і оцініть емоційну окраску!")


