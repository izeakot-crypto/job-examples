import sys, io, time, wave, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = r"[USER_HOME]\Downloads\tts-488311-d5a1cbf88094.json"

from google.cloud import texttospeech

TEXT = "Добрий день! Дякуємо що зателефонували. Чим можу допомогти?"

def make_ssml(text, rate, pitch, volume):
    return f"""<speak>
<prosody rate="{rate}" pitch="{pitch}" volume="{volume}">
    {text}
</prosody>
</speak>"""

gclient = texttospeech.TextToSpeechClient()
voice = texttospeech.VoiceSelectionParams(language_code="uk-UA", name="uk-UA-Wavenet-B")
audio_cfg = texttospeech.AudioConfig(
    audio_encoding=texttospeech.AudioEncoding.LINEAR16,
    sample_rate_hertz=8000,
)

# ═══════════════════════════════════════
# Тест 1: RATE
# ═══════════════════════════════════════
print(f"Google Wavenet-B | SSML тест | WAV 8kHz\n")
print(f"{'='*60}")
print(f"  ТЕСТ RATE (швидкість)")
print(f"{'='*60}")

rates = ["x-slow", "slow", "medium", "fast", "x-fast", "50%", "70%", "85%", "100%", "115%", "130%", "150%"]
normal_size = None
for rate in rates:
    ssml = make_ssml(TEXT, rate, "+0st", "medium")
    inp = texttospeech.SynthesisInput(ssml=ssml)
    resp = gclient.synthesize_speech(input=inp, voice=voice, audio_config=audio_cfg)
    size = len(resp.audio_content)
    if rate == "100%" or rate == "medium":
        normal_size = size
    diff = ((size - normal_size) / normal_size * 100) if normal_size else 0
    diff_str = f"{diff:>+.1f}%" if rate not in ["100%", "medium"] else "базовий"
    fname = f"g_rate_{rate.replace('%','pct')}.wav"
    with open(fname, "wb") as f:
        f.write(resp.audio_content)
    print(f"  rate={rate:<8} {size:>7}б {diff_str:>10} | {fname}")

# ═══════════════════════════════════════
# Тест 2: PITCH
# ═══════════════════════════════════════
print(f"\n{'='*60}")
print(f"  ТЕСТ PITCH (висота)")
print(f"{'='*60}")

pitches = ["x-low", "low", "medium", "high", "x-high", "-6st", "-4st", "-2st", "+0st", "+2st", "+4st", "+6st"]
normal_size_p = None
for pitch in pitches:
    ssml = make_ssml(TEXT, "medium", pitch, "medium")
    inp = texttospeech.SynthesisInput(ssml=ssml)
    resp = gclient.synthesize_speech(input=inp, voice=voice, audio_config=audio_cfg)
    size = len(resp.audio_content)
    if pitch == "+0st" or pitch == "medium":
        normal_size_p = size
    diff = ((size - normal_size_p) / normal_size_p * 100) if normal_size_p else 0
    diff_str = f"{diff:>+.1f}%" if pitch not in ["+0st", "medium"] else "базовий"
    fname = f"g_pitch_{pitch.replace('+','p').replace('-','m')}.wav"
    with open(fname, "wb") as f:
        f.write(resp.audio_content)
    print(f"  pitch={pitch:<8} {size:>7}б {diff_str:>10} | {fname}")

# ═══════════════════════════════════════
# Тест 3: VOLUME
# ═══════════════════════════════════════
print(f"\n{'='*60}")
print(f"  ТЕСТ VOLUME (гучність)")
print(f"{'='*60}")

volumes = ["silent", "x-soft", "soft", "medium", "loud", "x-loud"]
for vol in volumes:
    ssml = make_ssml(TEXT, "medium", "+0st", vol)
    inp = texttospeech.SynthesisInput(ssml=ssml)
    resp = gclient.synthesize_speech(input=inp, voice=voice, audio_config=audio_cfg)
    fname = f"g_vol_{vol}.wav"
    with open(fname, "wb") as f:
        f.write(resp.audio_content)
    print(f"  volume={vol:<8} {len(resp.audio_content):>7}б | {fname}")

# ═══════════════════════════════════════
# Тест 4: КОМБІНОВАНІ ЕМОЦІЇ
# ═══════════════════════════════════════
print(f"\n{'='*60}")
print(f"  КОМБІНОВАНІ ЕМОЦІЇ")
print(f"{'='*60}")

EMOTIONS = [
    ("g_emo_normal",  "medium", "+0st",  "medium"),
    ("g_emo_happy",   "fast",   "+4st",  "loud"),
    ("g_emo_sad",     "slow",   "-4st",  "soft"),
    ("g_emo_urgent",  "x-fast", "+2st",  "x-loud"),
    ("g_emo_calm",    "slow",   "-1st",  "soft"),
    ("g_emo_warm",    "95%",    "+2st",  "medium"),
]

for name, rate, pitch, vol in EMOTIONS:
    ssml = make_ssml(TEXT, rate, pitch, vol)
    inp = texttospeech.SynthesisInput(ssml=ssml)
    resp = gclient.synthesize_speech(input=inp, voice=voice, audio_config=audio_cfg)
    fname = f"{name}.wav"
    with open(fname, "wb") as f:
        f.write(resp.audio_content)
    print(f"  {name:<16} rate={rate:<7} pitch={pitch:<5} vol={vol:<8} | {len(resp.audio_content):>7}б")

# ═══════════════════════════════════════
# Тест 5: BREAK паузи + текстові трюки
# ═══════════════════════════════════════
print(f"\n{'='*60}")
print(f"  ТЕКСТОВІ ТРЮКИ + BREAK")
print(f"{'='*60}")

TEXT_TRICKS = [
    ("g_trick_plain", "<speak>Добрий день! Дякуємо що зателефонували. Чим можу допомогти?</speak>"),

    ("g_trick_breaks", """<speak>
Добрий день! <break time="400ms"/>
Дякуємо що зателефонували. <break time="300ms"/>
Чим можу допомогти?
</speak>"""),

    ("g_trick_emphasis", """<speak>
<emphasis level="strong">Добрий день!</emphasis> <break time="300ms"/>
Дякуємо що зателефонували. <break time="200ms"/>
Чим можу <emphasis level="moderate">допомогти</emphasis>?
</speak>"""),

    ("g_trick_combo", """<speak>
<prosody rate="95%" pitch="+1st">
    Добрий день!
</prosody>
<break time="400ms"/>
<prosody rate="90%" pitch="+0st">
    Дякуємо що зателефонували.
</prosody>
<break time="350ms"/>
<prosody rate="95%" pitch="+2st">
    Чим можу допомогти?
</prosody>
</speak>"""),

    ("g_trick_punctuation", """<speak>
Добрий день!! <break time="300ms"/>
Дякуємо, що зателефонували... <break time="400ms"/>
Чим можу вам допомогти?
</speak>"""),
]

for name, ssml in TEXT_TRICKS:
    inp = texttospeech.SynthesisInput(ssml=ssml)
    resp = gclient.synthesize_speech(input=inp, voice=voice, audio_config=audio_cfg)
    fname = f"{name}.wav"
    with open(fname, "wb") as f:
        f.write(resp.audio_content)
    print(f"  {name:<22} | {len(resp.audio_content):>7}б | {fname}")

print(f"\n  Послухайте і порівняйте!")

