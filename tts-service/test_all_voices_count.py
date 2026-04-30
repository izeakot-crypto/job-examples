import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
import azure.cognitiveservices.speech as speechsdk

AZURE_KEY = "YOUR_SECRET_TOKEN"
AZURE_REGION = "westeurope"

config = speechsdk.SpeechConfig(subscription=AZURE_KEY, region=AZURE_REGION)
synth = speechsdk.SpeechSynthesizer(speech_config=config, audio_config=None)

voices_result = synth.get_voices_async().get()

# Порахувати по мовах
langs = {}
for v in voices_result.voices:
    lang = v.locale
    if lang not in langs:
        langs[lang] = []
    langs[lang].append(v)

print(f"Всього голосів в Azure: {len(voices_result.voices)}")
print(f"Всього мов: {len(langs)}\n")

# Показати слов'янські та популярні мови
interesting = ["uk-UA", "ru-RU", "pl-PL", "en-US", "en-GB", "de-DE", "fr-FR", "es-ES", "tr-TR", "zh-CN", "ja-JP"]

print(f"{'Мова':<8} {'Кількість':>10}  Приклади голосів")
print(f"{'─'*8} {'─'*10}  {'─'*50}")

for loc in interesting:
    if loc in langs:
        voices = langs[loc]
        examples = ", ".join([v.short_name.split("-")[-1] for v in voices[:5]])
        if len(voices) > 5:
            examples += f" (+{len(voices)-5} ще)"
        print(f"{loc:<8} {len(voices):>10}  {examples}")

# Окремо мови з найбільшою кількістю голосів
print(f"\nТОП-10 мов по кількості голосів:")
sorted_langs = sorted(langs.items(), key=lambda x: len(x[1]), reverse=True)
for i, (loc, voices) in enumerate(sorted_langs[:10]):
    print(f"  {i+1}. {loc:<8} — {len(voices)} голосів")

del synth

