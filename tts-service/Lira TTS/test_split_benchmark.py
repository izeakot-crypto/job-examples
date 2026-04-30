#!/usr/bin/env python3
"""
Бенчмарк: як час генерації залежить від довжини тексту.
Визначаємо оптимальну стратегію розбивки.
"""

import sys, io, os, time, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = r"[USER_HOME]\Downloads\tts-488311-d5a1cbf88094.json"

from google.cloud import texttospeech_v1beta1 as texttospeech

client = texttospeech.TextToSpeechClient()
# Прогрів
client.synthesize_speech(
    input=texttospeech.SynthesisInput(text="тест"),
    voice=texttospeech.VoiceSelectionParams(language_code="uk-UA", name="uk-UA-Chirp3-HD-Leda"),
    audio_config=texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.LINEAR16, sample_rate_hertz=8000),
)


def gen(text):
    t0 = time.time()
    resp = client.synthesize_speech(
        input=texttospeech.SynthesisInput(text=text),
        voice=texttospeech.VoiceSelectionParams(language_code="uk-UA", name="uk-UA-Chirp3-HD-Leda"),
        audio_config=texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.LINEAR16, sample_rate_hertz=8000),
    )
    ms = int((time.time() - t0) * 1000)
    audio_bytes = len(resp.audio_content)
    audio_sec = (audio_bytes - 44) / (8000 * 2)
    return ms, audio_sec


# Тексти різної довжини
tests = [
    ("1 речення (коротке)", "Дякуємо за дзвінок."),
    ("1 речення (середнє)", "Дякуємо за дзвінок до компанії Окі-Токі."),
    ("1 речення (довге)", "Будь ласка, залишайтесь на лінії або натисніть один для зворотного дзвінка."),
    ("2 речення", "Дякуємо за дзвінок до компанії Окі-Токі. На жаль, всі оператори зайняті."),
    ("3 речення", "Дякуємо за дзвінок до компанії Окі-Токі. На жаль, всі оператори зайняті. Залишайтесь на лінії."),
    ("4 речення", "Дякуємо за дзвінок до компанії Окі-Токі. На жаль, всі оператори зайняті. Залишайтесь на лінії. Ваш дзвінок важливий для нас."),
    ("5 речень", "Дякуємо за дзвінок до компанії Окі-Токі. На жаль, всі оператори зайняті. Залишайтесь на лінії. Ваш дзвінок важливий для нас. Натисніть один для зворотного дзвінка."),
]

print()
print("═" * 70)
print("  Бенчмарк: час генерації vs довжина тексту (Chirp3-HD)")
print("═" * 70)
print()
print(f"  {'Текст':<25} {'Символів':>10} {'Час':>8} {'Аудіо':>8} {'мс/сим':>8}")
print(f"  {'─'*25} {'─'*10} {'─'*8} {'─'*8} {'─'*8}")

results = []
for name, text in tests:
    # Виконуємо 2 рази, беремо кращий (перший може бути повільнішим)
    ms1, audio1 = gen(text)
    ms2, audio2 = gen(text)
    ms = min(ms1, ms2)
    audio = audio2
    per_char = round(ms / len(text), 1)
    results.append((name, len(text), ms, audio, per_char))
    print(f"  {name:<25} {len(text):>10} {ms:>7}мс {audio:>6.1f}с {per_char:>7.1f}")

print()
print("═" * 70)
print("  Висновок:")
print("═" * 70)
print()

# Порівняння: 3 речення одним запитом vs 3 окремих
t_3_together = [r for r in results if r[0] == "3 речення"][0][2]
# Генеруємо 3 речення окремо
sentences = [
    "Дякуємо за дзвінок до компанії Окі-Токі.",
    "На жаль, всі оператори зайняті.",
    "Залишайтесь на лінії.",
]

times_separate = []
for s in sentences:
    ms1, _ = gen(s)
    ms2, _ = gen(s)
    times_separate.append(min(ms1, ms2))

t_3_max_separate = max(times_separate)  # паралельно = найдовший

print(f"  3 речення ОДНИМ запитом:      {t_3_together}мс")
print(f"  3 речення ОКРЕМО (послідовно): {sum(times_separate)}мс ({' + '.join(str(t) for t in times_separate)})")
print(f"  3 речення ОКРЕМО (паралельно): {t_3_max_separate}мс (max з {times_separate})")
print()

if t_3_together <= t_3_max_separate * 1.2:
    print(f"  >>> Розбивати НЕ ВАРТО — одним запитом так само швидко")
else:
    saving = t_3_together - t_3_max_separate
    print(f"  >>> Розбивка економить {saving}мс ({t_3_together}мс → {t_3_max_separate}мс)")

# Порівняння для 5 речень
t_5_together = [r for r in results if r[0] == "5 речень"][0][2]
sentences5 = [
    "Дякуємо за дзвінок до компанії Окі-Токі.",
    "На жаль, всі оператори зайняті.",
    "Залишайтесь на лінії.",
    "Ваш дзвінок важливий для нас.",
    "Натисніть один для зворотного дзвінка.",
]

times5 = []
for s in sentences5:
    ms1, _ = gen(s)
    ms2, _ = gen(s)
    times5.append(min(ms1, ms2))

print()
print(f"  5 речень ОДНИМ запитом:      {t_5_together}мс")
print(f"  5 речень ОКРЕМО (послідовно): {sum(times5)}мс")
print(f"  5 речень ОКРЕМО (паралельно): {max(times5)}мс (max з {times5})")

# Групами по 2-3
g1 = "Дякуємо за дзвінок до компанії Окі-Токі. На жаль, всі оператори зайняті."
g2 = "Залишайтесь на лінії. Ваш дзвінок важливий для нас."
g3 = "Натисніть один для зворотного дзвінка."
times_groups = []
for g in [g1, g2, g3]:
    ms1, _ = gen(g)
    ms2, _ = gen(g)
    times_groups.append(min(ms1, ms2))

print(f"  5 речень 3 ГРУПИ (паралельно): {max(times_groups)}мс (max з {times_groups})")
print()
print("═" * 70)

