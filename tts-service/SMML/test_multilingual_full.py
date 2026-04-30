import sys, io, os, time, struct, wave, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# ============================================================
# Мультимовний тест: Chirp3-HD, ElevenLabs, OpenAI
# ~150 символів на кожній мові (привітання колл-центру)
# ============================================================

SENTENCES = {
    "UA": "Дякуємо за дзвінок до компанії Окі-Токі. На жаль, всі оператори зараз зайняті. Будь ласка, залишайтесь на лінії, вам відповідять найближчим часом.",
    "EN": "Thank you for calling Oki-Toki company. Unfortunately, all operators are currently busy. Please stay on the line, you will be answered as soon as possible.",
    "RU": "Благодарим за звонок в компанию Оки-Токи. К сожалению, все операторы сейчас заняты. Пожалуйста, оставайтесь на линии, вам ответят в ближайшее время.",
    "PL": "Dziękujemy za telefon do firmy Oki-Toki. Niestety wszyscy operatorzy są obecnie zajęci. Prosimy pozostać na linii, odpowiemy najszybciej jak to możliwe.",
    "ES": "Gracias por llamar a la empresa Oki-Toki. Lamentablemente todos los operadores están ocupados. Por favor permanezca en la línea, le atenderemos lo antes posible.",
    "TR": "Oki-Toki şirketini aradığınız için teşekkür ederiz. Maalesef tüm operatörler şu anda meşgul. Lütfen hatta kalın, en kısa sürede size yanıt verilecektir.",
}

for lang, text in SENTENCES.items():
    print(f"  {lang}: {len(text)} символів")

# ============================================================
# 1. Google Chirp3-HD — тест усіх мов
# ============================================================
print("\n" + "="*60)
print("1. GOOGLE CHIRP3-HD — мультимовний тест")
print("="*60)

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = r"[USER_HOME]\Downloads\tts-488311-d5a1cbf88094.json"

from google.cloud import texttospeech_v1beta1 as texttospeech

# Маппінг мов до locale та голосів Chirp3-HD
CHIRP3_VOICES = {
    "UA": ("uk-UA", "uk-UA-Chirp3-HD-Leda"),
    "EN": ("en-US", "en-US-Chirp3-HD-Leda"),
    "RU": ("ru-RU", "ru-RU-Chirp3-HD-Leda"),
    "PL": ("pl-PL", "pl-PL-Chirp3-HD-Leda"),
    "ES": ("es-ES", "es-ES-Chirp3-HD-Leda"),
    "TR": ("tr-TR", "tr-TR-Chirp3-HD-Leda"),
}

chirp3_results = {}

for lang, text in SENTENCES.items():
    locale, voice_name = CHIRP3_VOICES[lang]
    client = texttospeech.TextToSpeechClient()

    synthesis_input = texttospeech.SynthesisInput(text=text)
    voice = texttospeech.VoiceSelectionParams(
        language_code=locale,
        name=voice_name,
    )
    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.LINEAR16,
        sample_rate_hertz=8000,
    )

    # 3 спроби, беремо середнє
    times = []
    for attempt in range(3):
        t0 = time.time()
        try:
            response = client.synthesize_speech(
                input=synthesis_input, voice=voice, audio_config=audio_config
            )
            elapsed = time.time() - t0
            times.append(elapsed)
        except Exception as e:
            print(f"  {lang}: ПОМИЛКА - {e}")
            break

    if times:
        avg_time = sum(times) / len(times)
        cps = int(len(text) / avg_time)
        chirp3_results[lang] = {"avg": avg_time, "cps": cps, "chars": len(text)}
        print(f"  Chirp3-HD {lang}: {avg_time:.2f}с / {cps} CPS (спроби: {', '.join(f'{t:.2f}' for t in times)})")
    else:
        chirp3_results[lang] = None
        print(f"  Chirp3-HD {lang}: НЕ ПІДТРИМУЄТЬСЯ")


# ============================================================
# 2. ElevenLabs — тест PL, ES, TR (UA, EN, RU вже є)
# ============================================================
print("\n" + "="*60)
print("2. ELEVENLABS — мультимовний тест (PL, ES, TR)")
print("="*60)

import requests

ELEVENLABS_KEY = "sk_YOUR_AZURE_KEY6f5e39e76d233f3a"
ELEVENLABS_VOICE = "21m00Tcm4TlvDq8ikWAM"  # Rachel

elevenlabs_results = {}

for lang in ["PL", "ES", "TR"]:
    text = SENTENCES[lang]

    times = []
    for attempt in range(3):
        t0 = time.time()
        try:
            resp = requests.post(
                f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE}",
                headers={
                    "xi-api-key": ELEVENLABS_KEY,
                    "Content-Type": "application/json",
                },
                json={
                    "text": text,
                    "model_id": "eleven_multilingual_v2",
                    "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
                },
                timeout=30,
            )
            elapsed = time.time() - t0
            if resp.status_code == 200:
                times.append(elapsed)
            else:
                print(f"  {lang}: HTTP {resp.status_code} - {resp.text[:100]}")
                break
        except Exception as e:
            print(f"  {lang}: ПОМИЛКА - {e}")
            break

    if times:
        avg_time = sum(times) / len(times)
        cps = int(len(text) / avg_time)
        elevenlabs_results[lang] = {"avg": avg_time, "cps": cps}
        print(f"  ElevenLabs {lang}: {avg_time:.2f}с / {cps} CPS (спроби: {', '.join(f'{t:.2f}' for t in times)})")
    else:
        elevenlabs_results[lang] = None
        print(f"  ElevenLabs {lang}: ПОМИЛКА")


# ============================================================
# 3. OpenAI tts-1 — тест усіх 6 мов
# ============================================================
print("\n" + "="*60)
print("3. OPENAI TTS-1 — мультимовний тест (усі 6 мов)")
print("="*60)

from openai import OpenAI

openai_client = OpenAI(api_key="YOUR_OPENAI_API_KEY")

openai_results = {}

for lang, text in SENTENCES.items():
    times = []
    for attempt in range(3):
        t0 = time.time()
        try:
            response = openai_client.audio.speech.create(
                model="tts-1",
                voice="nova",
                input=text,
                response_format="pcm",
            )
            audio_data = response.read()
            elapsed = time.time() - t0
            times.append(elapsed)
        except Exception as e:
            print(f"  {lang}: ПОМИЛКА - {e}")
            break

    if times:
        avg_time = sum(times) / len(times)
        cps = int(len(text) / avg_time)
        openai_results[lang] = {"avg": avg_time, "cps": cps}
        print(f"  OpenAI tts-1 {lang}: {avg_time:.2f}с / {cps} CPS (спроби: {', '.join(f'{t:.2f}' for t in times)})")
    else:
        openai_results[lang] = None
        print(f"  OpenAI tts-1 {lang}: ПОМИЛКА")


# ============================================================
# ПІДСУМОК
# ============================================================
print("\n" + "="*60)
print("ПІДСУМКОВА ТАБЛИЦЯ ДЛЯ 3.2 МУЛЬТИМОВНИЙ ТЕСТ")
print("="*60)
print(f"{'Мова':<5} {'Azure':<18} {'Wavenet':<18} {'Chirp3-HD':<18} {'ElevenLabs':<18} {'OpenAI tts-1':<18}")
print("-" * 95)

# Existing data from report
existing = {
    "Azure": {"UA": "0.27с / 541", "EN": "0.32с / 447", "RU": "0.29с / 524", "PL": "0.35с / 414", "ES": "0.31с / 468", "TR": "0.28с / 518"},
    "Wavenet": {"UA": "0.75с / 195", "EN": "0.68с / 210", "RU": "0.71с / 214", "PL": "0.82с / 177", "ES": "0.74с / 196", "TR": "0.79с / 184"},
    "ElevenLabs_old": {"UA": "1.94с / 75", "EN": "1.38с / 104", "RU": "1.52с / 100"},
}

for lang in ["UA", "EN", "RU", "PL", "ES", "TR"]:
    azure = existing["Azure"].get(lang, "—")
    wavenet = existing["Wavenet"].get(lang, "—")

    if chirp3_results.get(lang):
        c = chirp3_results[lang]
        chirp3 = f"{c['avg']:.2f}с / {c['cps']}"
    else:
        chirp3 = "—"

    if lang in existing["ElevenLabs_old"]:
        el = existing["ElevenLabs_old"][lang]
    elif elevenlabs_results.get(lang):
        e = elevenlabs_results[lang]
        el = f"{e['avg']:.2f}с / {e['cps']}"
    else:
        el = "—"

    if openai_results.get(lang):
        o = openai_results[lang]
        oai = f"{o['avg']:.2f}с / {o['cps']}"
    else:
        oai = "—"

    print(f"{lang:<5} {azure:<18} {wavenet:<18} {chirp3:<18} {el:<18} {oai:<18}")



