import sys, io, os, re, shutil
from collections import defaultdict
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

ROOT = os.path.join(os.path.expanduser("~"), "OneDrive", "Work.Oki-toki", "TTS для Оки-Токи")

# Збираємо всі аудіо файли (тільки кореневу папку)
audio_files = []
for f in os.listdir(ROOT):
    if f.endswith(('.wav', '.mp3', '.ogg')) and os.path.isfile(os.path.join(ROOT, f)):
        audio_files.append(f)

print(f"Знайдено {len(audio_files)} аудіо файлів\n")

# ============================================================
# Парсимо кожен файл і визначаємо провайдера + метадані
# ============================================================
parsed = []

for f in audio_files:
    name = os.path.splitext(f)[0]
    ext = os.path.splitext(f)[1]
    info = {
        "original": f,
        "ext": ext,
        "provider": "Unknown",
        "model": "",
        "voice": "",
        "lang": "UA",
        "chars": "",
        "time": "",
        "extra": "",
    }

    # Витягуємо кількість символів
    m = re.match(r'^(\d+)sym_', name)
    if m:
        info["chars"] = m.group(1)

    # Витягуємо час генерації
    m_time = re.search(r'_(\d+\.\d+)s', name)
    if m_time:
        info["time"] = m_time.group(1)

    # --- Визначаємо провайдера ---
    name_lower = name.lower()

    # Azure
    if 'azure' in name_lower:
        info["provider"] = "Azure"
        info["model"] = "Neural"
        if 'polina' in name_lower or 'поліна' in name_lower:
            info["voice"] = "Polina"
        elif 'ostap' in name_lower or 'остап' in name_lower:
            info["voice"] = "Ostap"
        else:
            info["voice"] = "Polina"
        if '_en_' in name_lower or '_EN_' in name: info["lang"] = "EN"
        elif '_ru_' in name_lower or '_RU_' in name: info["lang"] = "RU"
        elif '_pl_' in name_lower or '_PL_' in name: info["lang"] = "PL"
        elif '_es_' in name_lower or '_ES_' in name: info["lang"] = "ES"
        elif '_tr_' in name_lower or '_TR_' in name: info["lang"] = "TR"
        if 'stream' in name_lower: info["extra"] = "stream"
        elif 'reuse' in name_lower: info["extra"] = "reuse"
        elif 'prod' in name_lower: info["extra"] = "prod"

    # ElevenLabs
    elif '11labs' in name_lower or 'elevenlabs' in name_lower:
        info["provider"] = "ElevenLabs"
        info["model"] = "MultilingualV2"
        if 'charlotte' in name_lower: info["voice"] = "Charlotte"
        elif 'sarah' in name_lower: info["voice"] = "Sarah"
        else: info["voice"] = "Rachel"
        if 'stream' in name_lower: info["extra"] = "stream"

    # Edge TTS
    elif 'edge' in name_lower or 'efast' in name_lower:
        info["provider"] = "EdgeTTS"
        info["model"] = "Neural"
        info["voice"] = "Polina"
        if 'fast' in name_lower: info["extra"] = "fast"
        elif 'stream' in name_lower: info["extra"] = "stream"
        elif 'parallel' in name_lower: info["extra"] = "parallel"
        elif 'baseline' in name_lower: info["extra"] = "baseline"

    # Google Chirp3-HD (30 голосів)
    elif 'chirp3' in name_lower or 'gstream' in name_lower:
        info["provider"] = "Google"
        info["model"] = "Chirp3HD"
        # Шукаємо ім'я голосу
        voice_match = re.search(r'Chirp3-HD-(\w+)', name, re.IGNORECASE)
        if voice_match:
            info["voice"] = voice_match.group(1)
        else:
            voice_match = re.search(r'Chirp3-(\w+)', name, re.IGNORECASE)
            if voice_match:
                info["voice"] = voice_match.group(1)
            else:
                voice_match = re.search(r'gstream_(\w+)', name, re.IGNORECASE)
                if voice_match:
                    info["voice"] = voice_match.group(1)
                else:
                    info["voice"] = "Leda"
        if 'stream' in name_lower: info["extra"] = "stream"
        if 'rate' in name_lower:
            rm = re.search(r'rate(\d+\.?\d*)', name_lower)
            if rm: info["extra"] = f"rate{rm.group(1)}"

    # Google Wavenet
    elif 'wavenet' in name_lower:
        info["provider"] = "Google"
        info["model"] = "Wavenet"
        info["voice"] = "WavenetB"
        if 'telephony' in name_lower or 'tel' in name_lower: info["extra"] = "telephony"
        elif 'warm' in name_lower: info["extra"] = "warm"
        elif 'rate' in name_lower:
            rm = re.search(r'rate(\d+\.?\d*)', name_lower)
            if rm: info["extra"] = f"rate{rm.group(1)}"

    # Google Standard
    elif 'standard' in name_lower:
        info["provider"] = "Google"
        info["model"] = "Standard"
        info["voice"] = "StandardA"
        if 'rate' in name_lower:
            rm = re.search(r'rate(\d+\.?\d*)', name_lower)
            if rm: info["extra"] = f"rate{rm.group(1)}"

    # OpenAI
    elif 'openai' in name_lower:
        info["provider"] = "OpenAI"
        info["model"] = "TTS1"
        info["voice"] = "nova"

    # Emotion files
    elif 'emotion' in name_lower:
        info["provider"] = "Azure"
        info["model"] = "Neural"
        info["voice"] = "Polina"
        info["extra"] = "emotion"

    # Format comparison
    elif name.startswith('fmt_'):
        info["provider"] = "FormatTest"
        info["extra"] = "format"

    # Compare files
    elif name.startswith('cmp_') or name.startswith('compare_'):
        info["provider"] = "Compare"
        info["extra"] = "compare"

    # Long/natural/other tests
    elif name.startswith('long_') or name.startswith('natural_'):
        info["provider"] = "Azure"
        info["model"] = "Neural"
        info["voice"] = "Polina"
        if 'stream' in name_lower: info["extra"] = "stream"
        elif 'natural' in name_lower: info["extra"] = "natural"
        else: info["extra"] = "longtest"

    # SSML test files from SMML folder
    elif 'happy' in name_lower or 'sad' in name_lower or 'calm' in name_lower:
        info["provider"] = "Google"
        info["model"] = "Chirp3HD"
        info["voice"] = "Leda"
        if 'happy' in name_lower: info["extra"] = "happy"
        elif 'sad' in name_lower: info["extra"] = "sad"
        elif 'calm' in name_lower: info["extra"] = "calm"

    parsed.append(info)

# ============================================================
# Групуємо по провайдерах
# ============================================================
groups = defaultdict(list)
for info in parsed:
    key = f"{info['provider']}_{info['model']}"
    groups[key].append(info)

print("Групи файлів:")
for key, files in sorted(groups.items()):
    print(f"  {key}: {len(files)} файлів")

# ============================================================
# Відбираємо по 10 кращих на групу, перейменовуємо
# ============================================================
print("\n=== Перейменування ===")

# Пріоритет: файли з часом і символами > без інформації
# Для Chirp3-HD: по 1 файлу на кожний голос (перший з часом)

kept = 0
deleted = 0
renamed = 0

# Створюємо папку для видалених
trash_dir = os.path.join(ROOT, "_old_audio")
os.makedirs(trash_dir, exist_ok=True)

for key, files in sorted(groups.items()):
    # Сортуємо: файли з часом і символами першими
    files.sort(key=lambda x: (
        0 if x["time"] and x["chars"] else 1,
        x.get("voice", ""),
        x.get("time", "999"),
    ))

    # Спеціальна логіка для Chirp3-HD: по 1 файлу на голос (макс 10 голосів)
    if "Chirp3HD" in key:
        seen_voices = set()
        selected = []
        for f in files:
            v = f["voice"]
            if v not in seen_voices and len(selected) < 10:
                seen_voices.add(v)
                selected.append(f)
    else:
        selected = files[:10]

    to_delete = [f for f in files if f not in selected]

    for info in selected:
        # Формуємо нове ім'я
        parts = [info["provider"]]
        if info["model"]: parts.append(info["model"])
        if info["voice"]: parts.append(info["voice"])
        parts.append(info["lang"])
        if info["chars"]: parts.append(f"{info['chars']}sym")
        if info["time"]: parts.append(f"{info['time']}s")
        if info["extra"]: parts.append(info["extra"])

        new_name = "_".join(parts) + info["ext"]
        old_path = os.path.join(ROOT, info["original"])
        new_path = os.path.join(ROOT, new_name)

        if old_path != new_path:
            # Уникаємо конфліктів
            counter = 1
            while os.path.exists(new_path):
                new_name = "_".join(parts) + f"_{counter}" + info["ext"]
                new_path = os.path.join(ROOT, new_name)
                counter += 1

            os.rename(old_path, new_path)
            renamed += 1
            print(f"  ✓ {info['original'][:50]:50s} → {new_name}")
        else:
            kept += 1

    # Переміщуємо зайві в _old_audio
    for info in to_delete:
        old_path = os.path.join(ROOT, info["original"])
        if os.path.exists(old_path):
            shutil.move(old_path, os.path.join(trash_dir, info["original"]))
            deleted += 1

print(f"\n✅ Результат:")
print(f"  Перейменовано: {renamed}")
print(f"  Залишено як є: {kept}")
print(f"  Переміщено в _old_audio: {deleted}")

# Рахуємо що залишилось
remaining = [f for f in os.listdir(ROOT) if f.endswith(('.wav', '.mp3')) and os.path.isfile(os.path.join(ROOT, f))]
print(f"  Аудіо файлів після очистки: {len(remaining)}")
