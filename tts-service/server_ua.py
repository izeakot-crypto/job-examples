#!/usr/bin/env python3
"""
Ukrainian TTS API Server with Web UI
Features: White noise, Intonation tests, Voice info
"""

from fastapi import FastAPI, HTTPException
from fastapi.responses import Response, HTMLResponse
from pydantic import BaseModel
from typing import Optional
import time
import base64
import wave
import struct
import random
from io import BytesIO

from ukrainian_tts.tts import TTS, Voices, Stress

app = FastAPI(
    title="Ukrainian TTS API",
    description="Text-to-Speech API for Ukrainian language",
    version="1.0.0"
)

tts_engine = None

VOICE_MAP = {
    "dmytro": Voices.Dmytro.value,
    "oleksa": Voices.Oleksa.value,
    "tetiana": Voices.Tetiana.value,
    "lada": Voices.Lada.value,
    "mykyta": Voices.Mykyta.value,
}

STRESS_MAP = {
    "dictionary": Stress.Dictionary.value,
    "model": Stress.Model.value,
}

class TTSRequest(BaseModel):
    text: str
    voice: Optional[str] = "dmytro"
    stress: Optional[str] = "dictionary"
    noise_level: Optional[float] = 0.0  # 0.0 to 1.0

def add_white_noise(audio_bytes: bytes, noise_level: float) -> bytes:
    """Add white noise to WAV audio"""
    if noise_level <= 0:
        return audio_bytes

    # Parse WAV
    audio_io = BytesIO(audio_bytes)
    with wave.open(audio_io, 'rb') as wav:
        params = wav.getparams()
        frames = wav.readframes(params.nframes)

    # Convert to samples
    samples = list(struct.unpack(f'{params.nframes}h', frames))

    # Add noise
    max_amp = 32767
    noise_amp = int(max_amp * noise_level * 0.1)  # 10% of max at full noise

    noisy_samples = []
    for sample in samples:
        noise = random.randint(-noise_amp, noise_amp)
        new_sample = max(-max_amp, min(max_amp, sample + noise))
        noisy_samples.append(int(new_sample))

    # Pack back to bytes
    noisy_frames = struct.pack(f'{len(noisy_samples)}h', *noisy_samples)

    # Write new WAV
    output = BytesIO()
    with wave.open(output, 'wb') as wav:
        wav.setparams(params)
        wav.writeframes(noisy_frames)

    output.seek(0)
    return output.read()

@app.on_event("startup")
async def startup_event():
    global tts_engine
    print("Loading Ukrainian TTS model...")
    tts_engine = TTS(device="cpu")
    tts_engine.tts("Тест", Voices.Dmytro.value, Stress.Dictionary.value, output_fp=BytesIO())
    print("Model loaded and ready!")

HTML_UI = '''<!DOCTYPE html>
<html lang="uk">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Ukrainian TTS - Testing</title>
    <style>
        * { box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 900px;
            margin: 0 auto;
            padding: 20px;
            background: #1a1a2e;
            color: #eee;
        }
        h1 { text-align: center; color: #ffd700; margin-bottom: 10px; }
        h2 { color: #0f9; font-size: 16px; margin: 20px 0 10px; border-bottom: 1px solid #333; padding-bottom: 5px; }
        .flag { font-size: 48px; text-align: center; margin-bottom: 10px; }
        .container {
            background: #16213e;
            padding: 25px;
            border-radius: 15px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.3);
            margin-bottom: 20px;
        }
        label { display: block; margin-bottom: 8px; font-weight: 600; color: #0f9; }
        textarea {
            width: 100%;
            height: 100px;
            padding: 12px;
            border: 2px solid #0f96;
            border-radius: 10px;
            font-size: 15px;
            background: #0d1b2a;
            color: #fff;
            resize: vertical;
        }
        textarea:focus { outline: none; border-color: #0f9; }
        .row { display: flex; gap: 15px; margin: 15px 0; flex-wrap: wrap; }
        .col { flex: 1; min-width: 150px; }
        select, input[type="range"] {
            width: 100%;
            padding: 10px;
            border: 2px solid #0f96;
            border-radius: 10px;
            font-size: 14px;
            background: #0d1b2a;
            color: #fff;
        }
        input[type="range"] { padding: 5px; }
        .range-value { text-align: center; color: #0f9; font-weight: bold; }
        button {
            padding: 12px 25px;
            background: linear-gradient(135deg, #0f9 0%, #0c6 100%);
            color: #000;
            border: none;
            border-radius: 10px;
            font-size: 16px;
            font-weight: bold;
            cursor: pointer;
            transition: transform 0.2s;
        }
        button:hover { transform: translateY(-2px); }
        button:disabled { background: #555; cursor: not-allowed; transform: none; }
        .btn-primary { width: 100%; font-size: 18px; padding: 15px; }
        #result {
            margin-top: 20px;
            padding: 15px;
            background: #0d1b2a;
            border-radius: 10px;
            display: none;
        }
        #result.show { display: block; }
        audio { width: 100%; margin-top: 10px; }
        .stats { display: flex; gap: 15px; margin-top: 15px; flex-wrap: wrap; }
        .stat { background: #16213e; padding: 10px 15px; border-radius: 8px; text-align: center; flex: 1; min-width: 80px; }
        .stat-value { font-size: 20px; font-weight: bold; color: #0f9; }
        .stat-label { font-size: 11px; color: #888; }
        .loading { text-align: center; padding: 20px; color: #ffd700; }
        .error { color: #f66; padding: 15px; background: #400; border-radius: 8px; }

        /* Test sections */
        .test-section { margin-top: 15px; }
        .test-btn {
            background: #0d1b2a;
            border: 1px solid #333;
            color: #aaa;
            padding: 8px 12px;
            border-radius: 8px;
            margin: 3px;
            cursor: pointer;
            font-size: 12px;
        }
        .test-btn:hover { border-color: #0f9; color: #0f9; }
        .test-btn.active { border-color: #ffd700; color: #ffd700; }

        /* Info boxes */
        .info-box {
            background: #0d1b2a;
            border-left: 4px solid #0f9;
            padding: 12px 15px;
            margin: 10px 0;
            border-radius: 0 8px 8px 0;
            font-size: 13px;
        }
        .info-box.warning { border-color: #ffd700; }
        .info-box.error { border-color: #f66; }
        .info-box h4 { margin: 0 0 5px; color: #0f9; }
        .info-box.warning h4 { color: #ffd700; }
        .info-box.error h4 { color: #f66; }

        /* Tabs */
        .tabs { display: flex; gap: 5px; margin-bottom: 15px; }
        .tab {
            padding: 10px 20px;
            background: #0d1b2a;
            border: 1px solid #333;
            color: #888;
            cursor: pointer;
            border-radius: 8px 8px 0 0;
        }
        .tab.active { background: #16213e; color: #0f9; border-bottom-color: #16213e; }
        .tab-content { display: none; }
        .tab-content.active { display: block; }
    </style>
</head>
<body>
    <div class="flag">🇺🇦</div>
    <h1>Ukrainian TTS</h1>
    <p style="text-align:center;color:#888;margin-bottom:20px;">Тестування системи синтезу мовлення</p>

    <div class="container">
        <!-- Tabs -->
        <div class="tabs">
            <div class="tab active" onclick="showTab('main')">Основне</div>
            <div class="tab" onclick="showTab('intonation')">Інтонування</div>
            <div class="tab" onclick="showTab('features')">Можливості</div>
        </div>

        <!-- Main Tab -->
        <div id="tab-main" class="tab-content active">
            <label for="text">Текст для озвучення:</label>
            <textarea id="text" placeholder="Введіть текст українською мовою...">Привіт! Ласкаво просимо до української системи синтезу мовлення.</textarea>

            <div class="row">
                <div class="col">
                    <label for="voice">Голос:</label>
                    <select id="voice">
                        <option value="dmytro">Дмитро (чоловічий)</option>
                        <option value="tetiana">Тетяна (жіночий)</option>
                        <option value="oleksa">Олекса (чоловічий)</option>
                        <option value="lada">Лада (жіночий)</option>
                        <option value="mykyta">Микита (чоловічий)</option>
                    </select>
                </div>
                <div class="col">
                    <label for="stress">Наголоси:</label>
                    <select id="stress">
                        <option value="dictionary">Словник</option>
                        <option value="model">Модель</option>
                    </select>
                </div>
                <div class="col">
                    <label for="noise">Білий шум: <span id="noise-value">0%</span></label>
                    <input type="range" id="noise" min="0" max="100" value="0" oninput="updateNoiseValue()">
                </div>
            </div>

            <button class="btn-primary" id="synthesize" onclick="synthesize()">🔊 Озвучити</button>
        </div>

        <!-- Intonation Tab -->
        <div id="tab-intonation" class="tab-content">
            <h2>🎭 Тест інтонування</h2>
            <p style="color:#888;font-size:13px;">Перевірте як система обробляє різні типи речень</p>

            <div class="test-section">
                <strong style="color:#0f9;">Питальні речення:</strong><br>
                <button class="test-btn" onclick="setExample('Ви впевнені, що хочете видалити цей файл?')">Підтвердження</button>
                <button class="test-btn" onclick="setExample('Коли буде доставлено моє замовлення?')">Коли?</button>
                <button class="test-btn" onclick="setExample('Чи можу я поговорити з менеджером?')">Чи можу?</button>
                <button class="test-btn" onclick="setExample('Скільки це коштує?')">Скільки?</button>
            </div>

            <div class="test-section">
                <strong style="color:#0f9;">Окличні речення:</strong><br>
                <button class="test-btn" onclick="setExample('Вітаємо! Ви виграли головний приз!')">Радість</button>
                <button class="test-btn" onclick="setExample('Увага! Це важливе повідомлення!')">Увага</button>
                <button class="test-btn" onclick="setExample('Дякуємо за покупку!')">Подяка</button>
                <button class="test-btn" onclick="setExample('На жаль, ваш запит відхилено.')">Негатив</button>
            </div>

            <div class="test-section">
                <strong style="color:#0f9;">Складні речення:</strong><br>
                <button class="test-btn" onclick="setExample('Якщо ви хочете продовжити, натисніть один, якщо ні - натисніть два.')">Умова</button>
                <button class="test-btn" onclick="setExample('Ваше замовлення номер 12345 буде доставлено завтра, з девятої до восемнадцятої години.')">Числа</button>
                <button class="test-btn" onclick="setExample('Олександр Петрович Коваленко, ваш рейс PS-752 затримується на дві години.')">Імена</button>
            </div>

            <div class="test-section">
                <strong style="color:#0f9;">Перерахування:</strong><br>
                <button class="test-btn" onclick="setExample('Натисніть один для продажів, два для підтримки, три для бухгалтерії.')">Меню</button>
                <button class="test-btn" onclick="setExample('У вас є три нові повідомлення, два пропущені дзвінки та один голосовий лист.')">Список</button>
            </div>
        </div>

        <!-- Features Tab -->
        <div id="tab-features" class="tab-content">
            <h2>📊 Можливості системи</h2>

            <div class="info-box">
                <h4>✅ Білий шум (Підтримується)</h4>
                <p>Додає фоновий шум для імітації телефонної лінії. Регулюється слайдером 0-100%.</p>
                <p><strong>Як тестувати:</strong> Встановіть шум 30-50% і порівняйте з чистим аудіо.</p>
            </div>

            <div class="info-box warning">
                <h4>⚠️ Клонування голосу (Не підтримується)</h4>
                <p>Система ukrainian-tts використовує тільки вбудовані голоси (5 штук).</p>
                <p>Для клонування потрібні: Chatterbox, XTTS-v2, або Fish-Speech.</p>
            </div>

            <div class="info-box">
                <h4>✅ Швидкість (CPS)</h4>
                <p>Вимірюється автоматично після кожної генерації.</p>
                <p><strong>Очікувана швидкість:</strong> 8-15 CPS (CPU mode)</p>
            </div>

            <div class="info-box">
                <h4>✅ Наголоси</h4>
                <p>Два режими: Словник (точніший) та Модель (швидший).</p>
            </div>

            <h2>🧪 Тести для оцінки</h2>

            <div class="test-section">
                <strong style="color:#ffd700;">Незнайомі слова:</strong><br>
                <button class="test-btn" onclick="setExample('Ваш API-ключ недійсний, оновіть конфігурацію в налаштуваннях.')">Технічні</button>
                <button class="test-btn" onclick="setExample('Зверніться до нашого CRM-менеджера щодо вашого KPI.')">Абревіатури</button>
                <button class="test-btn" onclick="setExample('Прокрастинація та перфекціонізм заважають продуктивності.')">Складні</button>
            </div>

            <div class="test-section">
                <strong style="color:#ffd700;">Іншомовні слова:</strong><br>
                <button class="test-btn" onclick="setExample('Завантажте файл у форматі PDF через Google Drive.')">Англіцизми</button>
                <button class="test-btn" onclick="setExample('Оплата через PayPal або криптовалютою Bitcoin.')">Бренди</button>
                <button class="test-btn" onclick="setExample('Ваш iPhone готовий до видачі в магазині Apple Store.')">Продукти</button>
                <button class="test-btn" onclick="setExample('Підключіться до WiFi мережі для синхронізації з iCloud.')">Змішано</button>
            </div>
        </div>

        <!-- Result -->
        <div id="result">
            <div id="loading" class="loading" style="display:none;">⏳ Генерація аудіо...</div>
            <div id="error" class="error" style="display:none;"></div>
            <div id="audio-container" style="display:none;">
                <audio id="audio" controls></audio>
                <div class="stats">
                    <div class="stat">
                        <div class="stat-value" id="stat-chars">-</div>
                        <div class="stat-label">Символів</div>
                    </div>
                    <div class="stat">
                        <div class="stat-value" id="stat-time">-</div>
                        <div class="stat-label">Час (сек)</div>
                    </div>
                    <div class="stat">
                        <div class="stat-value" id="stat-cps">-</div>
                        <div class="stat-label">CPS</div>
                    </div>
                    <div class="stat">
                        <div class="stat-value" id="stat-noise">-</div>
                        <div class="stat-label">Шум</div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        function showTab(tabName) {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
            document.querySelector(`.tab[onclick="showTab('${tabName}')"]`).classList.add('active');
            document.getElementById('tab-' + tabName).classList.add('active');
        }

        function updateNoiseValue() {
            const val = document.getElementById('noise').value;
            document.getElementById('noise-value').textContent = val + '%';
        }

        function setExample(text) {
            document.getElementById('text').value = text;
            showTab('main');
        }

        async function synthesize() {
            const text = document.getElementById('text').value.trim();
            if (!text) { alert('Введіть текст!'); return; }

            const voice = document.getElementById('voice').value;
            const stress = document.getElementById('stress').value;
            const noise = document.getElementById('noise').value / 100;
            const btn = document.getElementById('synthesize');
            const result = document.getElementById('result');
            const loading = document.getElementById('loading');
            const error = document.getElementById('error');
            const audioContainer = document.getElementById('audio-container');

            btn.disabled = true;
            btn.textContent = '⏳ Генерація...';
            result.classList.add('show');
            loading.style.display = 'block';
            error.style.display = 'none';
            audioContainer.style.display = 'none';

            try {
                const response = await fetch('/tts/json', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ text, voice, stress, noise_level: noise })
                });

                if (!response.ok) throw new Error('Server error');

                const data = await response.json();

                const audio = document.getElementById('audio');
                audio.src = 'data:audio/wav;base64,' + data.audio_base64;

                document.getElementById('stat-chars').textContent = data.characters;
                document.getElementById('stat-time').textContent = (data.synthesis_time_ms / 1000).toFixed(2);
                document.getElementById('stat-cps').textContent = data.cps;
                document.getElementById('stat-noise').textContent = Math.round(noise * 100) + '%';

                loading.style.display = 'none';
                audioContainer.style.display = 'block';
                audio.play();

            } catch (e) {
                loading.style.display = 'none';
                error.style.display = 'block';
                error.textContent = 'Error: ' + e.message;
            }

            btn.disabled = false;
            btn.textContent = '🔊 Озвучити';
        }

        document.getElementById('text').addEventListener('keydown', (e) => {
            if (e.ctrlKey && e.key === 'Enter') synthesize();
        });
    </script>
</body>
</html>'''

@app.get("/", response_class=HTMLResponse)
async def root():
    return HTML_UI

@app.get("/api")
async def api_info():
    return {
        "service": "Ukrainian TTS",
        "status": "ready",
        "voices": list(VOICE_MAP.keys()),
        "stress_modes": list(STRESS_MAP.keys()),
        "features": {
            "white_noise": True,
            "voice_cloning": False,
            "intonation_control": False,
            "ssml": False,
        }
    }

@app.get("/health")
async def health():
    return {"status": "healthy", "model_loaded": tts_engine is not None}

@app.post("/tts")
async def synthesize_audio(request: TTSRequest):
    if tts_engine is None:
        raise HTTPException(status_code=503, detail="Model not loaded")

    voice = VOICE_MAP.get(request.voice.lower(), Voices.Dmytro.value)
    stress = STRESS_MAP.get(request.stress.lower(), Stress.Dictionary.value)

    output_buffer = BytesIO()

    start = time.time()
    audio_io, processed_text = tts_engine.tts(request.text, voice, stress, output_fp=output_buffer)
    end = time.time()

    synthesis_time = (end - start) * 1000
    cps = len(request.text) / (synthesis_time / 1000) if synthesis_time > 0 else 0

    audio_io.seek(0)
    audio_bytes = audio_io.read()

    # Add white noise if requested
    if request.noise_level and request.noise_level > 0:
        audio_bytes = add_white_noise(audio_bytes, request.noise_level)

    return Response(
        content=audio_bytes,
        media_type="audio/wav",
        headers={
            "X-Voice": request.voice,
            "X-Characters": str(len(request.text)),
            "X-Synthesis-Time-Ms": f"{synthesis_time:.2f}",
            "X-CPS": f"{cps:.1f}",
        }
    )

@app.post("/tts/json")
async def synthesize_json(request: TTSRequest):
    if tts_engine is None:
        raise HTTPException(status_code=503, detail="Model not loaded")

    voice = VOICE_MAP.get(request.voice.lower(), Voices.Dmytro.value)
    stress = STRESS_MAP.get(request.stress.lower(), Stress.Dictionary.value)

    output_buffer = BytesIO()

    start = time.time()
    audio_io, processed_text = tts_engine.tts(request.text, voice, stress, output_fp=output_buffer)
    end = time.time()

    synthesis_time = (end - start) * 1000
    cps = len(request.text) / (synthesis_time / 1000) if synthesis_time > 0 else 0

    audio_io.seek(0)
    audio_bytes = audio_io.read()

    # Add white noise if requested
    if request.noise_level and request.noise_level > 0:
        audio_bytes = add_white_noise(audio_bytes, request.noise_level)

    audio_b64 = base64.b64encode(audio_bytes).decode()

    return {
        "text": request.text,
        "processed_text": processed_text,
        "voice": request.voice,
        "characters": len(request.text),
        "synthesis_time_ms": round(synthesis_time, 2),
        "cps": round(cps, 1),
        "noise_level": request.noise_level or 0,
        "audio_base64": audio_b64,
        "audio_format": "wav",
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5001)
