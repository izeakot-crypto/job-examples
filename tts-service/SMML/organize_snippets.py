import sys, io, os, re, shutil
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

root = os.path.join(os.path.expanduser("~"), "OneDrive", "Work.Oki-toki", "TTS для Оки-Токи", "snippets")

files = [f for f in os.listdir(root) if os.path.isfile(os.path.join(root, f)) and f.endswith(('.wav', '.mp3'))]
print(f"Файлів: {len(files)}\n")

# ============================================================
# Парсимо і класифікуємо
# ============================================================
classified = []

for f in files:
    name = os.path.splitext(f)[0]
    ext = os.path.splitext(f)[1]
    info = {"original": f, "ext": ext, "folder": "", "new_name": ""}

    name_lower = name.lower()

    # --- EdgeTTS (вже добре підписані) ---
    if name.startswith("EdgeTTS_"):
        info["folder"] = "EdgeTTS"
        # Вже гарне ім'я, трохи скоротимо
        # EdgeTTS_8kHz_UK_Polina_speed1.0_gen0.73s_audio8.33s_RTF0.088_CPS168.5_test3.wav
        m = re.match(r'EdgeTTS_8kHz_(\w+)_(\w+)_speed[\d.]+_gen([\d.]+)s_audio([\d.]+)s_RTF[\d.]+_CPS([\d.]+)_test(\d+)', name)
        if m:
            lang, voice, gen_time, audio_dur, cps, test = m.groups()
            info["new_name"] = f"EdgeTTS_{voice}_{lang}_{gen_time}s_{cps}cps_test{test}{ext}"
        else:
            info["new_name"] = f

    # --- OpenAI tts-1-hd (вже підписані) ---
    elif name.startswith("OpenAI_tts-1-hd_"):
        info["folder"] = "OpenAI"
        m = re.match(r'OpenAI_tts-1-hd_(\w+)_(\w+)_speed[\d.]+_gen([\d.]+)s_audio([\d.]+)s_RTF[\d.]+_CPS([\d.]+)_test(\d+)', name)
        if m:
            lang, voice, gen_time, audio_dur, cps, test = m.groups()
            info["new_name"] = f"OpenAI_tts1hd_{voice}_{lang}_{gen_time}s_{cps}cps_test{test}{ext}"
        else:
            info["new_name"] = f

    # --- openai_tts-1_EN_1.291s / openai_tts-1-hd_EN_4.110s ---
    elif name.startswith("openai_"):
        info["folder"] = "OpenAI"
        m = re.match(r'openai_(tts-1(?:-hd)?)_(\w+)_([\d.]+)s', name)
        if m:
            model, lang, gen_time = m.groups()
            model_short = "tts1hd" if "hd" in model else "tts1"
            info["new_name"] = f"OpenAI_{model_short}_nova_{lang}_{gen_time}s{ext}"
        else:
            info["new_name"] = f

    # --- StyleTTS2 ---
    elif name.startswith("StyleTTS2_"):
        info["folder"] = "StyleTTS2"
        m = re.match(r'StyleTTS2_(\w+)_speed\d+_gen([\d.]+)s_audio([\d.]+)s_RTF[\d.]+_CPS([\d.]+)', name)
        if m:
            lang, gen_time, audio_dur, cps = m.groups()
            info["new_name"] = f"StyleTTS2_{lang}_{gen_time}s_{cps}cps{ext}"
        else:
            info["new_name"] = f

    # --- XTTS v2 ---
    elif name.startswith("XTTS_v2_"):
        info["folder"] = "XTTS_v2"
        m = re.match(r'XTTS_v2_(\w+)_[\w_]+_speed[\d.]+_gen([\d.]+)s_audio([\d.]+)s_RTF[\d.]+_CPS([\d.]+)', name)
        if m:
            lang, gen_time, audio_dur, cps = m.groups()
            info["new_name"] = f"XTTS_v2_{lang}_{gen_time}s_{cps}cps{ext}"
        else:
            info["new_name"] = f

    # --- ElevenLabs ---
    elif 'elevenlabs' in name_lower:
        info["folder"] = "ElevenLabs"
        m = re.match(r'elevenlabs_(\w+)_([\d.]+)s', name)
        if m:
            lang, gen_time = m.groups()
            info["new_name"] = f"ElevenLabs_MultiV2_Rachel_{lang}_{gen_time}s{ext}"
        else:
            info["new_name"] = f

    # --- Google Chirp3-HD (emotion files) ---
    elif any(x in name_lower for x in ['happy_', 'sad_', 'calm_']):
        info["folder"] = "Google_Chirp3HD"
        m = re.match(r'(\w+)_([\d.]+)s_GoogleChirp3HD_(\w+)_(\w+)', name)
        if m:
            emotion, gen_time, method, voice = m.groups()
            info["new_name"] = f"Chirp3HD_{voice}_UA_{gen_time}s_{emotion}_{method}{ext}"
        else:
            info["new_name"] = f

    # --- Azure multilingual: 306sym_azure_RU_1.042s ---
    elif 'azure' in name_lower:
        info["folder"] = "Azure"
        m = re.match(r'(\d+)sym_azure_(\w+)_([\d.]+)s', name)
        if m:
            chars, lang_or_voice, gen_time = m.groups()
            # Визначаємо мову і голос
            lang = lang_or_voice.upper()
            if lang in ("UA", "EN", "RU", "PL", "ES", "TR"):
                info["new_name"] = f"Azure_Polina_{lang}_{chars}sym_{gen_time}s{ext}"
            elif lang_or_voice.lower() in ("polina", "поліна"):
                info["new_name"] = f"Azure_Polina_UA_{chars}sym_{gen_time}s{ext}"
            elif lang_or_voice.lower() in ("ostap", "остап"):
                info["new_name"] = f"Azure_Ostap_UA_{chars}sym_{gen_time}s{ext}"
            else:
                info["new_name"] = f"Azure_{lang_or_voice}_UA_{chars}sym_{gen_time}s{ext}"
        elif 'stream' in name_lower:
            m2 = re.match(r'(\d+)sym_azure_ua_stream_([\d.]+)s', name)
            if m2:
                chars, gen_time = m2.groups()
                info["new_name"] = f"Azure_Polina_UA_{chars}sym_{gen_time}s_stream{ext}"
            else:
                info["new_name"] = f
        else:
            info["new_name"] = f

    # --- prod_Остап / prod_Поліна ---
    elif name.startswith("prod_"):
        info["folder"] = "Azure"
        if 'остап' in name_lower:
            num = name.split('_')[-1]
            info["new_name"] = f"Azure_Ostap_UA_prod_{num}{ext}"
        elif 'поліна' in name_lower:
            num = name.split('_')[-1]
            info["new_name"] = f"Azure_Polina_UA_prod_{num}{ext}"
        else:
            info["new_name"] = f

    # --- Google multilingual: 313sym_google_UA_1.154s ---
    elif 'google' in name_lower:
        info["folder"] = "Google_Wavenet"
        m = re.match(r'(\d+)sym_google_(\w+)_([\d.]+)s', name)
        if m:
            chars, lang, gen_time = m.groups()
            info["new_name"] = f"Wavenet_{lang}_{chars}sym_{gen_time}s{ext}"
        else:
            info["new_name"] = f

    # --- 341sym_azure_ES_0.803s (без префіксу) ---
    elif re.match(r'\d+sym_', name):
        m = re.match(r'(\d+)sym_(\w+)_(\w+)_([\d.]+)s', name)
        if m:
            chars, provider, lang_or_voice, gen_time = m.groups()
            if 'azure' in provider.lower():
                info["folder"] = "Azure"
                info["new_name"] = f"Azure_Polina_{lang_or_voice}_{chars}sym_{gen_time}s{ext}"
            elif 'google' in provider.lower():
                info["folder"] = "Google_Wavenet"
                info["new_name"] = f"Wavenet_{lang_or_voice}_{chars}sym_{gen_time}s{ext}"
            else:
                info["folder"] = "Other"
                info["new_name"] = f
        else:
            info["folder"] = "Other"
            info["new_name"] = f

    else:
        info["folder"] = "Other"
        info["new_name"] = f

    classified.append(info)

# ============================================================
# Створюємо папки і переміщуємо
# ============================================================
print("=== Організація по папках ===\n")

from collections import defaultdict
folders = defaultdict(list)
for info in classified:
    folders[info["folder"]].append(info)

for folder_name, items in sorted(folders.items()):
    folder_path = os.path.join(root, folder_name)
    os.makedirs(folder_path, exist_ok=True)
    print(f"📁 {folder_name}/ ({len(items)} файлів)")

    for info in items:
        old_path = os.path.join(root, info["original"])
        new_path = os.path.join(folder_path, info["new_name"])

        # Уникаємо конфліктів
        counter = 1
        base_new = os.path.splitext(info["new_name"])[0]
        ext = info["ext"]
        while os.path.exists(new_path):
            info["new_name"] = f"{base_new}_{counter}{ext}"
            new_path = os.path.join(folder_path, info["new_name"])
            counter += 1

        shutil.move(old_path, new_path)
        print(f"   {info['original'][:55]:55s} → {info['new_name']}")

# Перевірка
print(f"\n✅ Готово!")
remaining = [f for f in os.listdir(root) if os.path.isfile(os.path.join(root, f))]
print(f"Файлів без папки: {len(remaining)}")
for d in sorted(os.listdir(root)):
    dp = os.path.join(root, d)
    if os.path.isdir(dp):
        count = len([f for f in os.listdir(dp) if os.path.isfile(os.path.join(dp, f))])
        print(f"  📁 {d}/  — {count} файлів")
