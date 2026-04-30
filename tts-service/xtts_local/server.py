#!/usr/bin/env python3
"""
XTTS v2 Local Web Server
Веб-інтерфейс для тестування TTS на всіх 6 мовах
"""

import io
import time
from flask import Flask, render_template_string, request, send_file, jsonify

app = Flask(__name__)

# Глобальна змінна для моделі
tts_model = None

LANGUAGES = {
    "uk": "Українська",
    "en": "English",
    "ru": "Русский",
    "pl": "Polski",
    "es": "Español",
    "tr": "Türkçe"
}

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>XTTS v2 - Local TTS</title>
    <meta charset="utf-8">
    <style>
        * { box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Arial, sans-serif;
            max-width: 900px;
            margin: 0 auto;
            padding: 20px;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            color: #eee;
            min-height: 100vh;
        }
        h1 {
            color: #00d4ff;
            text-align: center;
            margin-bottom: 10px;
        }
        .subtitle {
            text-align: center;
            color: #888;
            margin-bottom: 30px;
        }
        .card {
            background: rgba(255,255,255,0.05);
            border-radius: 15px;
            padding: 25px;
            margin-bottom: 20px;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255,255,255,0.1);
        }
        label {
            display: block;
            margin-bottom: 8px;
            color: #00d4ff;
            font-weight: 500;
        }
        select, textarea {
            width: 100%;
            padding: 12px;
            border: 1px solid #333;
            border-radius: 8px;
            background: #1a1a2e;
            color: #eee;
            font-size: 16px;
            margin-bottom: 15px;
        }
        textarea {
            height: 120px;
            resize: vertical;
        }
        select:focus, textarea:focus {
            outline: none;
            border-color: #00d4ff;
        }
        button {
            width: 100%;
            padding: 15px;
            font-size: 18px;
            font-weight: bold;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.3s;
        }
        .btn-primary {
            background: linear-gradient(135deg, #00d4ff 0%, #0099cc 100%);
            color: #1a1a2e;
        }
        .btn-primary:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 20px rgba(0,212,255,0.4);
        }
        .btn-primary:disabled {
            background: #444;
            cursor: not-allowed;
            transform: none;
            box-shadow: none;
        }
        audio {
            width: 100%;
            margin-top: 15px;
        }
        .stats {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 15px;
            margin-top: 20px;
        }
        .stat-box {
            background: rgba(0,212,255,0.1);
            padding: 15px;
            border-radius: 10px;
            text-align: center;
        }
        .stat-value {
            font-size: 24px;
            font-weight: bold;
            color: #00d4ff;
        }
        .stat-label {
            font-size: 12px;
            color: #888;
            margin-top: 5px;
        }
        .loading {
            display: none;
            text-align: center;
            padding: 20px;
        }
        .loading.active {
            display: block;
        }
        .spinner {
            border: 3px solid #333;
            border-top: 3px solid #00d4ff;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            animation: spin 1s linear infinite;
            margin: 0 auto 15px;
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        .lang-grid {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 10px;
            margin-bottom: 15px;
        }
        .lang-btn {
            padding: 10px;
            border: 2px solid #333;
            border-radius: 8px;
            background: transparent;
            color: #eee;
            cursor: pointer;
            transition: all 0.2s;
        }
        .lang-btn:hover {
            border-color: #00d4ff;
        }
        .lang-btn.active {
            border-color: #00d4ff;
            background: rgba(0,212,255,0.2);
        }
        .error {
            background: rgba(255,0,0,0.2);
            border: 1px solid #ff4444;
            padding: 15px;
            border-radius: 8px;
            margin-top: 15px;
            display: none;
        }
        .history {
            margin-top: 20px;
        }
        .history-item {
            background: rgba(255,255,255,0.03);
            padding: 10px 15px;
            border-radius: 8px;
            margin-bottom: 10px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .history-text {
            flex: 1;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            margin-right: 15px;
        }
        .history-lang {
            background: #00d4ff;
            color: #1a1a2e;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: bold;
        }
    </style>
</head>
<body>
    <h1>XTTS v2 - Local TTS</h1>
    <p class="subtitle">6 мов: UA, EN, RU, PL, ES, TR</p>

    <div class="card">
        <label>Мова:</label>
        <div class="lang-grid">
            <button type="button" class="lang-btn active" data-lang="uk">🇺🇦 Українська</button>
            <button type="button" class="lang-btn" data-lang="en">🇬🇧 English</button>
            <button type="button" class="lang-btn" data-lang="ru">🇷🇺 Русский</button>
            <button type="button" class="lang-btn" data-lang="pl">🇵🇱 Polski</button>
            <button type="button" class="lang-btn" data-lang="es">🇪🇸 Español</button>
            <button type="button" class="lang-btn" data-lang="tr">🇹🇷 Türkçe</button>
        </div>

        <label>Текст:</label>
        <textarea id="text" placeholder="Введіть текст для синтезу...">Привіт! Це тест українського синтезу мовлення.</textarea>

        <button class="btn-primary" id="synthesize" onclick="synthesize()">
            🔊 Синтезувати
        </button>

        <div class="loading" id="loading">
            <div class="spinner"></div>
            <div>Генерація аудіо...</div>
        </div>

        <div class="error" id="error"></div>

        <audio id="audio" controls style="display:none;"></audio>

        <div class="stats" id="stats" style="display:none;">
            <div class="stat-box">
                <div class="stat-value" id="stat-cps">-</div>
                <div class="stat-label">CPS (симв/сек)</div>
            </div>
            <div class="stat-box">
                <div class="stat-value" id="stat-time">-</div>
                <div class="stat-label">Час (сек)</div>
            </div>
            <div class="stat-box">
                <div class="stat-value" id="stat-chars">-</div>
                <div class="stat-label">Символів</div>
            </div>
        </div>
    </div>

    <div class="card history" id="history-card" style="display:none;">
        <label>Історія:</label>
        <div id="history"></div>
    </div>

    <script>
        let selectedLang = 'uk';
        let history = [];

        // Language buttons
        document.querySelectorAll('.lang-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('.lang-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                selectedLang = btn.dataset.lang;

                // Default text for each language
                const defaults = {
                    'uk': 'Привіт! Це тест українського синтезу мовлення.',
                    'en': 'Hello! This is a test of English speech synthesis.',
                    'ru': 'Привет! Это тест русского синтеза речи.',
                    'pl': 'Cześć! To jest test polskiej syntezy mowy.',
                    'es': '¡Hola! Esta es una prueba de síntesis de voz en español.',
                    'tr': 'Merhaba! Bu Türkçe konuşma sentezi testidir.'
                };
                document.getElementById('text').value = defaults[selectedLang] || '';
            });
        });

        async function synthesize() {
            const text = document.getElementById('text').value.trim();
            if (!text) {
                alert('Введіть текст!');
                return;
            }

            const btn = document.getElementById('synthesize');
            const loading = document.getElementById('loading');
            const audio = document.getElementById('audio');
            const stats = document.getElementById('stats');
            const error = document.getElementById('error');

            btn.disabled = true;
            loading.classList.add('active');
            audio.style.display = 'none';
            stats.style.display = 'none';
            error.style.display = 'none';

            try {
                const startTime = Date.now();

                const response = await fetch('/synthesize', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ text, language: selectedLang })
                });

                if (!response.ok) {
                    const data = await response.json();
                    throw new Error(data.error || 'Synthesis failed');
                }

                const blob = await response.blob();
                const elapsed = (Date.now() - startTime) / 1000;
                const cps = text.length / elapsed;

                // Update audio
                audio.src = URL.createObjectURL(blob);
                audio.style.display = 'block';
                audio.play();

                // Update stats
                document.getElementById('stat-cps').textContent = cps.toFixed(1);
                document.getElementById('stat-time').textContent = elapsed.toFixed(2);
                document.getElementById('stat-chars').textContent = text.length;
                stats.style.display = 'grid';

                // Add to history
                addToHistory(text, selectedLang, cps.toFixed(1));

            } catch (e) {
                error.textContent = 'Помилка: ' + e.message;
                error.style.display = 'block';
            } finally {
                btn.disabled = false;
                loading.classList.remove('active');
            }
        }

        function addToHistory(text, lang, cps) {
            history.unshift({ text, lang, cps });
            if (history.length > 10) history.pop();

            const historyDiv = document.getElementById('history');
            const historyCard = document.getElementById('history-card');

            historyCard.style.display = 'block';
            historyDiv.innerHTML = history.map(h => `
                <div class="history-item">
                    <span class="history-lang">${h.lang.toUpperCase()}</span>
                    <span class="history-text">${h.text}</span>
                    <span style="color:#00d4ff">${h.cps} CPS</span>
                </div>
            `).join('');
        }

        // Enter key to synthesize
        document.getElementById('text').addEventListener('keydown', (e) => {
            if (e.ctrlKey && e.key === 'Enter') {
                synthesize();
            }
        });
    </script>
</body>
</html>
"""

def load_model():
    """Завантажити модель TTS"""
    global tts_model
    if tts_model is None:
        print("Loading XTTS v2 model (first time may take a while)...")
        from TTS.api import TTS
        tts_model = TTS("tts_models/multilingual/multi-dataset/xtts_v2")
        print("Model loaded!")
    return tts_model


@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route('/synthesize', methods=['POST'])
def synthesize():
    try:
        data = request.json
        text = data.get('text', '')
        language = data.get('language', 'uk')

        if not text:
            return jsonify({'error': 'No text provided'}), 400

        if language not in LANGUAGES:
            return jsonify({'error': f'Unsupported language: {language}'}), 400

        # Завантажити модель
        tts = load_model()

        # Генерація в пам'ять
        start_time = time.time()

        # Створити тимчасовий файл
        import tempfile
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            temp_path = f.name

        tts.tts_to_file(
            text=text,
            file_path=temp_path,
            language=language,
            split_sentences=True
        )

        elapsed = time.time() - start_time
        print(f"[{language.upper()}] Generated in {elapsed:.2f}s | CPS: {len(text)/elapsed:.1f}")

        # Прочитати і відправити файл
        with open(temp_path, 'rb') as f:
            audio_data = f.read()

        # Видалити тимчасовий файл
        import os
        os.unlink(temp_path)

        return send_file(
            io.BytesIO(audio_data),
            mimetype='audio/wav'
        )

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/health')
def health():
    return jsonify({
        'status': 'ok',
        'model_loaded': tts_model is not None,
        'languages': list(LANGUAGES.keys())
    })


if __name__ == '__main__':
    print("=" * 60)
    print("XTTS v2 Local Web Server")
    print("=" * 60)
    print("\nInstalling dependencies if needed...")

    # Перевірка залежностей
    try:
        import flask
    except ImportError:
        import subprocess
        subprocess.run(["pip", "install", "flask"], check=True)

    try:
        from TTS.api import TTS
    except ImportError:
        print("\nTTS not installed! Run first:")
        print("  pip install TTS torch torchaudio")
        exit(1)

    print("\nPre-loading model...")
    load_model()

    print("\n" + "=" * 60)
    print("Server starting at: http://localhost:5555")
    print("=" * 60)
    print("\nOpen in browser: http://localhost:5555")
    print("Press Ctrl+C to stop\n")

    app.run(host='0.0.0.0', port=5555, debug=False)
