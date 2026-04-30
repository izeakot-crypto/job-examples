import sys, io, os, time, struct, wave, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# ============================================================
# ФІНАЛЬНИЙ МУЛЬТИМОВНИЙ ТЕСТ — усі провайдери, одне речення
# 3 спроби на кожну комбінацію, середній час
# ============================================================

SENTENCES = {
    "UA": "Дякуємо за дзвінок до компанії Окі-Токі. На жаль, всі оператори зараз зайняті. Будь ласка, залишайтесь на лінії, вам відповідять найближчим часом.",
    "EN": "Thank you for calling Oki-Toki company. Unfortunately, all operators are currently busy. Please stay on the line, you will be answered as soon as possible.",
    "RU": "Благодарим за звонок в компанию Оки-Токи. К сожалению, все операторы сейчас заняты. Пожалуйста, оставайтесь на линии, вам ответят в ближайшее время.",
    "PL": "Dziękujemy za telefon do firmy Oki-Toki. Niestety wszyscy operatorzy są obecnie zajęci. Prosimy pozostać na linii, odpowiemy najszybciej jak to możliwe.",
    "ES": "Gracias por llamar a la empresa Oki-Toki. Lamentablemente todos los operadores están ocupados. Por favor permanezca en la línea, le atenderemos lo antes posible.",
    "TR": "Oki-Toki şirketini aradığınız için teşekkür ederiz. Maalesef tüm operatörler şu anda meşgul. Lütfen hatta kalın, en kısa sürede size yanıt verilecektir.",
}

print("Тестове речення (привітання колл-центру):")
for lang, text in SENTENCES.items():
    print(f"  {lang}: {len(text)} сим.")

ATTEMPTS = 3
results = {}  # results[provider][lang] = {"times": [], "avg": float, "cps": int}

def avg_result(times, chars):
    a = sum(times) / len(times)
    return {"times": times, "avg": round(a, 2), "cps": int(chars / a)}


# ============================================================
# 1. AZURE NEURAL (S0)
# ============================================================
print("\n" + "="*60)
print("1. AZURE NEURAL TTS")
print("="*60)

import azure.cognitiveservices.speech as speechsdk

AZURE_KEY = "YOUR_SECRET_TOKEN"
AZURE_REGION = "westeurope"

AZURE_VOICES = {
    "UA": "uk-UA-PolinaNeural",
    "EN": "en-US-JennyNeural",
    "RU": "ru-RU-SvetlanaNeural",
    "PL": "pl-PL-AgnieszkaNeural",
    "ES": "es-ES-ElviraNeural",
    "TR": "tr-TR-EmelNeural",
}

results["Azure"] = {}
for lang, text in SENTENCES.items():
    voice = AZURE_VOICES[lang]
    times = []
    for _ in range(ATTEMPTS):
        cfg = speechsdk.SpeechConfig(subscription=AZURE_KEY, region=AZURE_REGION)
        cfg.set_speech_synthesis_output_format(speechsdk.SpeechSynthesisOutputFormat.Riff8Khz16BitMonoPcm)
        cfg.speech_synthesis_voice_name = voice
        synth = speechsdk.SpeechSynthesizer(speech_config=cfg, audio_config=None)
        t0 = time.time()
        r = synth.speak_text(text)
        elapsed = time.time() - t0
        if r.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
            times.append(elapsed)
        else:
            print(f"  {lang}: ПОМИЛКА - {r.reason}")
            break
    if times:
        results["Azure"][lang] = avg_result(times, len(text))
        print(f"  Azure {lang}: {results['Azure'][lang]['avg']}с / {results['Azure'][lang]['cps']} CPS")


# ============================================================
# 2. GOOGLE STANDARD
# ============================================================
print("\n" + "="*60)
print("2. GOOGLE STANDARD")
print("="*60)

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = r"[USER_HOME]\Downloads\tts-488311-d5a1cbf88094.json"
from google.cloud import texttospeech_v1beta1 as texttospeech

G_STANDARD_VOICES = {
    "UA": ("uk-UA", "uk-UA-Standard-A"),
    "EN": ("en-US", "en-US-Standard-C"),
    "RU": ("ru-RU", "ru-RU-Standard-A"),
    "PL": ("pl-PL", "pl-PL-Standard-A"),
    "ES": ("es-ES", "es-ES-Standard-A"),
    "TR": ("tr-TR", "tr-TR-Standard-A"),
}

results["G.Standard"] = {}
for lang, text in SENTENCES.items():
    locale, voice_name = G_STANDARD_VOICES[lang]
    times = []
    for _ in range(ATTEMPTS):
        client = texttospeech.TextToSpeechClient()
        t0 = time.time()
        resp = client.synthesize_speech(
            input=texttospeech.SynthesisInput(text=text),
            voice=texttospeech.VoiceSelectionParams(language_code=locale, name=voice_name),
            audio_config=texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.LINEAR16, sample_rate_hertz=8000),
        )
        elapsed = time.time() - t0
        times.append(elapsed)
    results["G.Standard"][lang] = avg_result(times, len(text))
    print(f"  Standard {lang}: {results['G.Standard'][lang]['avg']}с / {results['G.Standard'][lang]['cps']} CPS")


# ============================================================
# 3. GOOGLE WAVENET
# ============================================================
print("\n" + "="*60)
print("3. GOOGLE WAVENET")
print("="*60)

G_WAVENET_VOICES = {
    "UA": ("uk-UA", "uk-UA-Wavenet-A"),
    "EN": ("en-US", "en-US-Wavenet-C"),
    "RU": ("ru-RU", "ru-RU-Wavenet-A"),
    "PL": ("pl-PL", "pl-PL-Wavenet-A"),
    "ES": ("es-ES", "es-ES-Wavenet-C"),
    "TR": ("tr-TR", "tr-TR-Wavenet-A"),
}

results["G.Wavenet"] = {}
for lang, text in SENTENCES.items():
    locale, voice_name = G_WAVENET_VOICES[lang]
    times = []
    for _ in range(ATTEMPTS):
        client = texttospeech.TextToSpeechClient()
        t0 = time.time()
        resp = client.synthesize_speech(
            input=texttospeech.SynthesisInput(text=text),
            voice=texttospeech.VoiceSelectionParams(language_code=locale, name=voice_name),
            audio_config=texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.LINEAR16, sample_rate_hertz=8000),
        )
        elapsed = time.time() - t0
        times.append(elapsed)
    results["G.Wavenet"][lang] = avg_result(times, len(text))
    print(f"  Wavenet {lang}: {results['G.Wavenet'][lang]['avg']}с / {results['G.Wavenet'][lang]['cps']} CPS")


# ============================================================
# 4. GOOGLE CHIRP3-HD
# ============================================================
print("\n" + "="*60)
print("4. GOOGLE CHIRP3-HD (Leda)")
print("="*60)

CHIRP3_VOICES = {
    "UA": ("uk-UA", "uk-UA-Chirp3-HD-Leda"),
    "EN": ("en-US", "en-US-Chirp3-HD-Leda"),
    "RU": ("ru-RU", "ru-RU-Chirp3-HD-Leda"),
    "PL": ("pl-PL", "pl-PL-Chirp3-HD-Leda"),
    "ES": ("es-ES", "es-ES-Chirp3-HD-Leda"),
    "TR": ("tr-TR", "tr-TR-Chirp3-HD-Leda"),
}

results["Chirp3-HD"] = {}
for lang, text in SENTENCES.items():
    locale, voice_name = CHIRP3_VOICES[lang]
    times = []
    for _ in range(ATTEMPTS):
        client = texttospeech.TextToSpeechClient()
        t0 = time.time()
        try:
            resp = client.synthesize_speech(
                input=texttospeech.SynthesisInput(text=text),
                voice=texttospeech.VoiceSelectionParams(language_code=locale, name=voice_name),
                audio_config=texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.LINEAR16, sample_rate_hertz=8000),
            )
            elapsed = time.time() - t0
            times.append(elapsed)
        except Exception as e:
            print(f"  {lang}: ПОМИЛКА - {e}")
            break
    if times:
        results["Chirp3-HD"][lang] = avg_result(times, len(text))
        print(f"  Chirp3-HD {lang}: {results['Chirp3-HD'][lang]['avg']}с / {results['Chirp3-HD'][lang]['cps']} CPS")
    else:
        results["Chirp3-HD"][lang] = None


# ============================================================
# 5. ELEVENLABS
# ============================================================
print("\n" + "="*60)
print("5. ELEVENLABS (Rachel, multilingual_v2)")
print("="*60)

import requests

ELEVENLABS_KEY = "sk_YOUR_AZURE_KEY6f5e39e76d233f3a"
ELEVENLABS_VOICE = "21m00Tcm4TlvDq8ikWAM"  # Rachel

results["ElevenLabs"] = {}
for lang, text in SENTENCES.items():
    times = []
    for _ in range(ATTEMPTS):
        t0 = time.time()
        resp = requests.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE}",
            headers={"xi-api-key": ELEVENLABS_KEY, "Content-Type": "application/json"},
            json={"text": text, "model_id": "eleven_multilingual_v2",
                  "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}},
            timeout=30,
        )
        elapsed = time.time() - t0
        if resp.status_code == 200:
            times.append(elapsed)
        else:
            print(f"  {lang}: HTTP {resp.status_code}")
            break
    if times:
        results["ElevenLabs"][lang] = avg_result(times, len(text))
        print(f"  ElevenLabs {lang}: {results['ElevenLabs'][lang]['avg']}с / {results['ElevenLabs'][lang]['cps']} CPS")


# ============================================================
# 6. OPENAI TTS-1
# ============================================================
print("\n" + "="*60)
print("6. OPENAI TTS-1 (nova)")
print("="*60)

from openai import OpenAI

openai_client = OpenAI(api_key="YOUR_OPENAI_API_KEY")

results["OpenAI"] = {}
for lang, text in SENTENCES.items():
    times = []
    for _ in range(ATTEMPTS):
        t0 = time.time()
        try:
            response = openai_client.audio.speech.create(model="tts-1", voice="nova", input=text, response_format="pcm")
            _ = response.read()
            elapsed = time.time() - t0
            times.append(elapsed)
        except Exception as e:
            print(f"  {lang}: ПОМИЛКА - {e}")
            break
    if times:
        results["OpenAI"][lang] = avg_result(times, len(text))
        print(f"  OpenAI {lang}: {results['OpenAI'][lang]['avg']}с / {results['OpenAI'][lang]['cps']} CPS")


# ============================================================
# ФІНАЛЬНА ТАБЛИЦЯ
# ============================================================
print("\n" + "="*70)
print("ФІНАЛЬНА ТАБЛИЦЯ 3.2 — Мультимовний тест")
print("Речення: привітання колл-центру ~150 сим. | 3 спроби, середнє")
print("="*70)

providers = ["Azure", "G.Standard", "G.Wavenet", "Chirp3-HD", "ElevenLabs", "OpenAI"]
langs = ["UA", "EN", "RU", "PL", "ES", "TR"]

# Header
hdr = f"{'Мова':<5}"
for p in providers:
    hdr += f" {p:<16}"
print(hdr)
print("-" * 105)

for lang in langs:
    row = f"{lang:<5}"
    for prov in providers:
        d = results.get(prov, {}).get(lang)
        if d:
            row += f" {d['avg']}с/{d['cps']:<11}"
        else:
            row += f" {'—':<16}"
    print(row)

# Save JSON for report script
with open(os.path.join(os.path.dirname(__file__), "multilingual_results.json"), "w", encoding="utf-8") as f:
    # Convert for JSON
    out = {}
    for prov in providers:
        out[prov] = {}
        for lang in langs:
            d = results.get(prov, {}).get(lang)
            if d:
                out[prov][lang] = {"avg": d["avg"], "cps": d["cps"]}
    json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"\nРезультати збережено в multilingual_results.json")




