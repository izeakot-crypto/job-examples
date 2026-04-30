import sys, io, time, wave, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = r"[USER_HOME]\Downloads\tts-488311-d5a1cbf88094.json"

from google.cloud import texttospeech

gclient = texttospeech.TextToSpeechClient()
voice = texttospeech.VoiceSelectionParams(language_code="uk-UA", name="uk-UA-Wavenet-B")
audio_cfg = texttospeech.AudioConfig(
    audio_encoding=texttospeech.AudioEncoding.LINEAR16,
    sample_rate_hertz=8000,
    effects_profile_id=["telephony-class-application"],
)

TESTS = [
    # ── 1. Happy — радісне привітання ──
    ("01_happy", "Радісне привітання", """<speak>
<prosody rate="108%" pitch="+2st">
    Добрий день! Раді вас чути!
</prosody>
<break time="350ms"/>
<prosody rate="105%" pitch="+1st">
    Дякуємо що зателефонували до компанії Окі-Токі.
</prosody>
<break time="250ms"/>
<prosody rate="103%" pitch="+2st">
    Мене звати Оксана, чим можу вам допомогти?
</prosody>
</speak>"""),

    # ── 2. Sad — відмова клієнту ──
    ("02_sad", "Відмова клієнту", """<speak>
<prosody rate="85%" pitch="-2st">
    На жаль, ми змушені відмовити у вашому запиті.
</prosody>
<break time="500ms"/>
<prosody rate="80%" pitch="-1st">
    Нам дуже прикро, але ця послуга більше недоступна.
</prosody>
<break time="400ms"/>
<prosody rate="88%" pitch="+0st">
    Якщо бажаєте, я можу запропонувати альтернативний варіант.
</prosody>
</speak>"""),

    # ── 3. Urgent — термінове попередження ──
    ("03_urgent", "Термінове повідомлення", """<speak>
<prosody rate="115%" pitch="+1st">
    Увага! Це термінове повідомлення!
</prosody>
<break time="300ms"/>
<prosody rate="110%" pitch="+1st">
    Ваш акаунт буде заблоковано через годину, якщо не підтвердити дані.
</prosody>
<break time="250ms"/>
<prosody rate="108%">
    Будь ласка, зайдіть в особистий кабінет негайно!
</prosody>
</speak>"""),

    # ── 4. Calm — очікування на лінії ──
    ("04_calm", "Спокійне очікування", """<speak>
<prosody rate="85%" pitch="-1st">
    Будь ласка, залишайтесь на лінії.
</prosody>
<break time="500ms"/>
<prosody rate="82%" pitch="-1st">
    Ваш дзвінок дуже важливий для нас.
</prosody>
<break time="450ms"/>
<prosody rate="85%">
    Перший вільний спеціаліст відповість вам найближчим часом.
</prosody>
</speak>"""),

    # ── 5. Empathy — вибачення за проблему ──
    ("05_empathy", "Вибачення за збій", """<speak>
<prosody rate="82%" pitch="-2st">
    Вибачте за незручності.
</prosody>
<break time="500ms"/>
<prosody rate="80%" pitch="-1st">
    Ми розуміємо, як це неприємно, і щиро перепрошуємо.
</prosody>
<break time="400ms"/>
<prosody rate="88%">
    Наша команда вже працює над вирішенням проблеми.
</prosody>
<break time="300ms"/>
<prosody rate="90%" pitch="+1st">
    Дякуємо за ваше терпіння.
</prosody>
</speak>"""),

    # ── 6. Good news — проблему вирішено ──
    ("06_good_news", "Проблему вирішено", """<speak>
<prosody rate="108%" pitch="+2st">
    Чудові новини!
</prosody>
<break time="350ms"/>
<prosody rate="105%" pitch="+1st">
    Вашу проблему повністю вирішено! Все працює як слід.
</prosody>
<break time="300ms"/>
<prosody rate="103%" pitch="+2st">
    Дякуємо за звернення і гарного вам дня!
</prosody>
</speak>"""),

    # ── 7. Professional — переведення на оператора ──
    ("07_professional", "Переведення на оператора", """<speak>
<prosody rate="95%">
    Я розумію ваше питання.
</prosody>
<break time="300ms"/>
<prosody rate="93%">
    Для детальної консультації я зараз зʼєдную вас з нашим спеціалістом.
</prosody>
<break time="350ms"/>
<prosody rate="88%">
    Зачекайте, будь ласка, декілька секунд.
</prosody>
</speak>"""),

    # ── 8. Angry client — заспокоєння ──
    ("08_deescalation", "Заспокоєння злого клієнта", """<speak>
<prosody rate="82%" pitch="-2st">
    Я вас розумію і мені дуже шкода, що так сталося.
</prosody>
<break time="500ms"/>
<prosody rate="80%" pitch="-1st">
    Повірте, ми зробимо все можливе, щоб виправити ситуацію.
</prosody>
<break time="450ms"/>
<prosody rate="90%">
    Зараз я оформлю повернення коштів на вашу картку.
</prosody>
<break time="300ms"/>
<prosody rate="95%" pitch="+1st">
    Кошти надійдуть протягом двох робочих днів.
</prosody>
</speak>"""),

    # ── 9. Info — розповідь про тарифи ──
    ("09_info", "Інформація про тарифи", """<speak>
<prosody rate="95%">
    Звичайно, розповім про наші тарифи.
</prosody>
<break time="400ms"/>
<prosody rate="90%">
    Базовий план — двісті гривень на місяць, включає пʼятсот хвилин розмов.
</prosody>
<break time="350ms"/>
<prosody rate="90%">
    Професійний план — чотириста гривень з необмеженими дзвінками.
</prosody>
<break time="400ms"/>
<prosody rate="95%" pitch="+1st">
    Який тариф вас цікавить більше?
</prosody>
</speak>"""),

    # ── 10. Farewell — тепле прощання ──
    ("10_farewell", "Тепле прощання", """<speak>
<prosody rate="95%" pitch="+1st">
    Дякуємо за ваш дзвінок!
</prosody>
<break time="350ms"/>
<prosody rate="90%">
    Була рада вам допомогти.
</prosody>
<break time="300ms"/>
<prosody rate="88%">
    Якщо виникнуть питання — телефонуйте будь-коли.
</prosody>
<break time="400ms"/>
<prosody rate="105%" pitch="+3st">
    Гарного вам дня!
</prosody>
</speak>"""),
]

print(f"Google Wavenet-B | SSML Емоції | WAV 8kHz telephony\n")
print(f"  {'#':<20} {'Сценарій':<28} {'Час':>7} {'Розмір':>8}")
print(f"  {'─'*20} {'─'*28} {'─'*7} {'─'*8}")

for name, scenario, ssml in TESTS:
    inp = texttospeech.SynthesisInput(ssml=ssml)
    start = time.time()
    resp = gclient.synthesize_speech(input=inp, voice=voice, audio_config=audio_cfg)
    t = time.time() - start

    fname = f"{name}_{t:.3f}s.wav"
    with open(fname, "wb") as f:
        f.write(resp.audio_content)
    print(f"  {name:<20} {scenario:<28} {t:>6.3f}с {len(resp.audio_content):>7}б")

print(f"\n  Послухайте і порівняйте емоції!")

