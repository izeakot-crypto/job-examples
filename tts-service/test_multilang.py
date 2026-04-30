import sys, io, time, wave, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = r"[USER_HOME]\Downloads\tts-488311-d5a1cbf88094.json"

from google.cloud import texttospeech
import azure.cognitiveservices.speech as speechsdk

AZURE_KEY = "YOUR_SECRET_TOKEN"
AZURE_REGION = "westeurope"

LANGS = {
    "UA": {
        "text": "Шановний клієнте, дякуємо що звернулися до нашої компанії Окі-Токі. На жаль, всі оператори зараз зайняті. Будь ласка, залишайтесь на лінії, і перший вільний спеціаліст відповість вам найближчим часом. Орієнтовний час очікування складає три хвилини. Якщо бажаєте, залишіть голосове повідомлення, і ми передзвонимо.",
        "azure_voice": "uk-UA-PolinaNeural",
        "google_voice": "uk-UA-Wavenet-B",
        "google_lang": "uk-UA",
    },
    "EN": {
        "text": "Dear customer, thank you for contacting our company Oki-Toki. Unfortunately, all operators are currently busy. Please stay on the line and the first available specialist will answer your call as soon as possible. The estimated waiting time is about three minutes. If you prefer, please leave a voice message and we will call you back within one hour.",
        "azure_voice": "en-US-JennyNeural",
        "google_voice": "en-US-Wavenet-F",
        "google_lang": "en-US",
    },
    "RU": {
        "text": "Уважаемый клиент, благодарим вас за обращение в нашу компанию Оки-Токи. К сожалению, все операторы сейчас заняты. Пожалуйста, оставайтесь на линии, и первый свободный специалист ответит вам в ближайшее время. Ориентировочное время ожидания составляет три минуты. Если желаете, оставьте голосовое сообщение.",
        "azure_voice": "ru-RU-SvetlanaNeural",
        "google_voice": "ru-RU-Wavenet-A",
        "google_lang": "ru-RU",
    },
    "PL": {
        "text": "Szanowny kliencie, dziękujemy za kontakt z naszą firmą Oki-Toki. Niestety, wszyscy operatorzy są obecnie zajęci. Prosimy o pozostanie na linii, a pierwszy wolny specjalista odpowie na Państwa połączenie w najbliższym czasie. Przewidywany czas oczekiwania wynosi około trzech minut. Prosimy o pozostawienie wiadomości głosowej.",
        "azure_voice": "pl-PL-AgnieszkaNeural",
        "google_voice": "pl-PL-Wavenet-A",
        "google_lang": "pl-PL",
    },
    "ES": {
        "text": "Estimado cliente, gracias por contactar con nuestra empresa Oki-Toki. Lamentablemente, todos los operadores están ocupados en este momento. Por favor, permanezca en la línea y el primer especialista disponible le atenderá lo antes posible. El tiempo estimado de espera es de aproximadamente tres minutos. Si lo desea, deje un mensaje de voz.",
        "azure_voice": "es-ES-ElviraNeural",
        "google_voice": "es-ES-Wavenet-C",
        "google_lang": "es-ES",
    },
    "TR": {
        "text": "Sayın müşterimiz, Oki-Toki şirketimizle iletişime geçtiğiniz için teşekkür ederiz. Maalesef tüm operatörlerimiz şu anda meşgul. Lütfen hatta kalın, ilk müsait uzman en kısa sürede size yanıt verecektir. Tahmini bekleme süresi yaklaşık üç dakikadır. Dilerseniz sesli mesaj bırakabilirsiniz, sizi bir saat içinde arayacağız.",
        "azure_voice": "tr-TR-EmelNeural",
        "google_voice": "tr-TR-Wavenet-C",
        "google_lang": "tr-TR",
    },
}

def wrap_pcm_to_wav(pcm_data, sample_rate=8000):
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_data)
    return buf.getvalue()

# ═══════════════════════════════════════
# Azure — підготовка всіх синтезаторів з прогрівом
# ═══════════════════════════════════════
azure_synths = {}
for lang, cfg in LANGS.items():
    config = speechsdk.SpeechConfig(subscription=AZURE_KEY, region=AZURE_REGION)
    config.speech_synthesis_voice_name = cfg["azure_voice"]
    config.set_speech_synthesis_output_format(speechsdk.SpeechSynthesisOutputFormat.Raw8Khz16BitMonoPcm)
    synth = speechsdk.SpeechSynthesizer(speech_config=config, audio_config=None)
    conn = speechsdk.Connection.from_speech_synthesizer(synth)
    conn.open(True)
    time.sleep(0.2)
    synth.speak_text_async("тест").get()
    azure_synths[lang] = synth

# Google — підготовка
gclient = texttospeech.TextToSpeechClient()
audio_cfg = texttospeech.AudioConfig(
    audio_encoding=texttospeech.AudioEncoding.LINEAR16,
    sample_rate_hertz=8000,
    effects_profile_id=["telephony-class-application"],
)

print(f"Azure vs Google Wavenet | 6 мов | WAV 8kHz 16bit mono | Прогрів Azure\n")
print(f"  {'Мова':<4} {'Модель':<30} {'Симв':>5} {'Час':>7} Файл")
print(f"  {'─'*4} {'─'*30} {'─'*5} {'─'*7} {'─'*50}")

for lang, cfg in LANGS.items():
    text = cfg["text"]

    # ── Azure (з прогрівом) ──
    synth = azure_synths[lang]
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
    synth.speak_text_async(text).get()
    t_az = time.time() - gen_start[0]

    pcm = b"".join(chunks)
    wav_data = wrap_pcm_to_wav(pcm, 8000)
    fname = f"{len(text)}sym_azure_{lang}_{t_az:.3f}s.wav"
    with open(fname, "wb") as f:
        f.write(wav_data)
    print(f"  {lang:<4} {'Azure ' + cfg['azure_voice']:<30} {len(text):>5} {t_az:>6.3f}с {fname}")

    # ── Google Wavenet ──
    voice = texttospeech.VoiceSelectionParams(language_code=cfg["google_lang"], name=cfg["google_voice"])
    synth_input = texttospeech.SynthesisInput(text=text)

    start = time.time()
    resp = gclient.synthesize_speech(input=synth_input, voice=voice, audio_config=audio_cfg)
    t_gw = time.time() - start

    fname = f"{len(text)}sym_google_{lang}_{t_gw:.3f}s.wav"
    with open(fname, "wb") as f:
        f.write(resp.audio_content)
    print(f"  {lang:<4} {'Google ' + cfg['google_voice']:<30} {len(text):>5} {t_gw:>6.3f}с {fname}")
    print()

# Очистка
for s in azure_synths.values():
    del s

print(f"{'='*60}")
print(f"  Послухайте і порівняйте!")
print(f"{'='*60}")


