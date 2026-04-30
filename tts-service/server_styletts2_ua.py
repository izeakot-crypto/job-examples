#!/usr/bin/env python3
"""
StyleTTS2 Ukrainian TTS API Server
31 voices, high quality Ukrainian speech synthesis
Port: 5002
"""

import os
import re
import glob
import time
import io
import wave
import struct
import random
from typing import Optional, List

import torch
import numpy as np
from unicodedata import normalize

from fastapi import FastAPI, HTTPException
from fastapi.responses import Response, HTMLResponse
from pydantic import BaseModel

# StyleTTS2 dependencies
from ipa_uk import ipa
from styletts2_inference.models import StyleTTS2
from ukrainian_word_stress import Stressifier, StressSymbol

# Initialize
app = FastAPI(title="StyleTTS2 Ukrainian TTS API", version="1.0")

# Global variables
device = 'cuda' if torch.cuda.is_available() else 'cpu'
stressify = Stressifier()
models = {}
voices_list = []

# Paths
VOICES_DIR = '/opt/tts/styletts2-ua/voices'
SINGLE_STYLE_PATH = '/opt/tts/styletts2-ua/filatov.pt'


def split_to_parts(text: str) -> List[str]:
    """Split text into parts for synthesis"""
    split_symbols = '.?!:'
    parts = ['']
    index = 0
    for s in text:
        parts[index] += s
        if s in split_symbols and len(parts[index]) > 20:
            index += 1
            parts.append('')
    return [p for p in parts if p.strip()]


def add_white_noise(audio_data: np.ndarray, noise_level: float, sample_rate: int = 24000) -> np.ndarray:
    """Add white noise to audio"""
    if noise_level <= 0:
        return audio_data

    noise = np.random.normal(0, noise_level * 0.1, len(audio_data))
    return np.clip(audio_data + noise, -1.0, 1.0).astype(np.float32)


def numpy_to_wav(audio: np.ndarray, sample_rate: int = 24000) -> bytes:
    """Convert numpy array to WAV bytes"""
    # Normalize to int16
    audio_int16 = (audio * 32767).astype(np.int16)

    buffer = io.BytesIO()
    with wave.open(buffer, 'wb') as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(audio_int16.tobytes())

    return buffer.getvalue()


def synthesize_text(text: str, model_name: str = 'multi', voice_name: str = None, speed: float = 1.0) -> np.ndarray:
    """Synthesize text to audio"""
    result_wav = []

    for t in split_to_parts(text):
        t = t.strip()
        t = t.replace('"', '')
        if t:
            # Process text with stress marks
            t = t.replace('+', StressSymbol.CombiningAcuteAccent)
            t = normalize('NFKC', t)
            t = re.sub(r'[᠆‐‑‒–—―⁻₋−⸺⸻]', '-', t)
            t = re.sub(r' - ', ': ', t)

            # Convert to IPA
            ps = ipa(stressify(t))

            if ps:
                tokens = models[model_name]['model'].tokenizer.encode(ps)

                if model_name == 'multi' and voice_name and voice_name in models['multi']['styles']:
                    style = models['multi']['styles'][voice_name]
                elif model_name == 'single':
                    style = models['single']['style']
                else:
                    # Default to first voice
                    style = list(models['multi']['styles'].values())[0] if model_name == 'multi' else models['single']['style']

                wav = models[model_name]['model'](tokens, speed=speed, s_prev=style)
                result_wav.append(wav)

    if result_wav:
        return torch.concatenate(result_wav).cpu().numpy()
    return np.array([0.0], dtype=np.float32)


class TTSRequest(BaseModel):
    text: str
    voice: Optional[str] = None  # Voice name for multi-speaker
    model: Optional[str] = "multi"  # "multi" or "single"
    speed: Optional[float] = 1.0  # 0.5 to 2.0
    noise_level: Optional[float] = 0.0  # 0.0 to 1.0


@app.on_event("startup")
async def load_models():
    """Load TTS models on startup"""
    global models, voices_list

    print(f"Loading StyleTTS2 models on {device}...")

    # Load single-speaker model
    print("Loading single-speaker model...")
    single_model = StyleTTS2(hf_path='patriotyk/styletts2_ukrainian_single', device=device)
    single_style = torch.load(SINGLE_STYLE_PATH, map_location=device)

    # Load multi-speaker model
    print("Loading multi-speaker model...")
    multi_model = StyleTTS2(hf_path='patriotyk/styletts2_ukrainian_multispeaker', device=device)

    # Load voice styles
    multi_styles = {}
    prompts_list = sorted(glob.glob(os.path.join(VOICES_DIR, '*.pt')))

    for audio_path in prompts_list:
        voice_name = os.path.splitext(os.path.basename(audio_path))[0]
        multi_styles[voice_name] = torch.load(audio_path, map_location=device)
        print(f"  Loaded voice: {voice_name}")

    voices_list = sorted(multi_styles.keys())

    models = {
        'multi': {
            'model': multi_model,
            'styles': multi_styles
        },
        'single': {
            'model': single_model,
            'style': single_style
        }
    }

    print(f"Loaded {len(voices_list)} voices!")
    print("StyleTTS2 Ukrainian TTS ready!")


@app.get("/", response_class=HTMLResponse)
async def index():
    """Web UI"""
    voices_options = "\n".join([f'<option value="{v}">{v}</option>' for v in voices_list])
    voices_grid_html = "".join([f'<div class="voice-item" onclick="selectVoice(this, \'{v}\')">{v}</div>' for v in voices_list])

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>StyleTTS2 Ukrainian TTS</title>
        <meta charset="utf-8">
        <style>
            body {{ font-family: Arial, sans-serif; max-width: 1200px; margin: 0 auto; padding: 20px; background: #1a1a2e; color: #eee; }}
            h1 {{ color: #ffd700; text-align: center; }}
            .tabs {{ display: flex; gap: 10px; margin-bottom: 20px; }}
            .tab {{ padding: 10px 20px; background: #16213e; border: none; color: #eee; cursor: pointer; border-radius: 5px 5px 0 0; }}
            .tab.active {{ background: #0f3460; color: #ffd700; }}
            .tab-content {{ display: none; padding: 20px; background: #0f3460; border-radius: 0 5px 5px 5px; }}
            .tab-content.active {{ display: block; }}
            textarea {{ width: 100%; height: 120px; padding: 10px; font-size: 16px; background: #16213e; color: #eee; border: 1px solid #444; border-radius: 5px; }}
            select, input[type="range"] {{ width: 100%; padding: 8px; margin: 5px 0; background: #16213e; color: #eee; border: 1px solid #444; border-radius: 5px; }}
            button {{ padding: 12px 24px; font-size: 18px; background: #ffd700; color: #1a1a2e; border: none; border-radius: 5px; cursor: pointer; margin: 10px 5px; }}
            button:hover {{ background: #ffed4a; }}
            .control-group {{ margin: 15px 0; }}
            label {{ display: block; margin-bottom: 5px; color: #ffd700; }}
            audio {{ width: 100%; margin-top: 20px; }}
            .info {{ background: #16213e; padding: 15px; border-radius: 5px; margin: 10px 0; }}
            .voices-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 10px; max-height: 300px; overflow-y: auto; }}
            .voice-item {{ padding: 8px; background: #16213e; border-radius: 5px; cursor: pointer; }}
            .voice-item:hover {{ background: #1a1a3e; }}
            .voice-item.selected {{ background: #ffd700; color: #1a1a2e; }}
            #status {{ color: #4ade80; margin: 10px 0; }}
            .slider-value {{ color: #ffd700; font-weight: bold; }}
        </style>
    </head>
    <body>
        <h1>StyleTTS2 Ukrainian TTS</h1>
        <p style="text-align: center; color: #888;">31 голос, висока якість синтезу</p>

        <div class="tabs">
            <button class="tab active" onclick="showTab('main')">Синтез</button>
            <button class="tab" onclick="showTab('voices')">Голоси ({len(voices_list)})</button>
            <button class="tab" onclick="showTab('intonation')">Тести інтонації</button>
            <button class="tab" onclick="showTab('features')">Можливості</button>
        </div>

        <div id="main" class="tab-content active">
            <div class="control-group">
                <label>Текст для синтезу:</label>
                <textarea id="text" placeholder="Введіть текст українською мовою...">Привіт! Це StyleTTS2 українською мовою. Тридцять один голос на вибір.</textarea>
            </div>

            <div class="control-group">
                <label>Голос:</label>
                <select id="voice">
                    {voices_options}
                </select>
            </div>

            <div class="control-group">
                <label>Швидкість: <span id="speed_val" class="slider-value">1.0x</span></label>
                <input type="range" id="speed" min="0.5" max="2.0" step="0.1" value="1.0" oninput="document.getElementById('speed_val').textContent = this.value + 'x'">
            </div>

            <div class="control-group">
                <label>Білий шум: <span id="noise_val" class="slider-value">0%</span></label>
                <input type="range" id="noise" min="0" max="100" step="1" value="0" oninput="document.getElementById('noise_val').textContent = this.value + '%'">
            </div>

            <button onclick="generate()" style="width: 100%; font-size: 20px; padding: 15px;">Згенерувати</button>

            <div id="status"></div>
            <div id="stats" class="info" style="display: none;">
                <table style="width: 100%;">
                    <tr><td>Символів:</td><td id="stat_chars" style="text-align: right; font-weight: bold;"></td></tr>
                    <tr><td>Час синтезу:</td><td id="stat_time" style="text-align: right; font-weight: bold;"></td></tr>
                    <tr><td>CPS (символів/сек):</td><td id="stat_cps" style="text-align: right; font-weight: bold; color: #4ade80;"></td></tr>
                    <tr><td>Розмір аудіо:</td><td id="stat_size" style="text-align: right; font-weight: bold;"></td></tr>
                    <tr><td>Голос:</td><td id="stat_voice" style="text-align: right; font-weight: bold;"></td></tr>
                    <tr><td>Швидкість:</td><td id="stat_speed" style="text-align: right; font-weight: bold;"></td></tr>
                    <tr><td>Білий шум:</td><td id="stat_noise" style="text-align: right; font-weight: bold;"></td></tr>
                </table>
            </div>

            <div id="avg_stats" class="info" style="background: linear-gradient(135deg, #1a1a3e 0%, #16213e 100%); border: 1px solid #ffd700;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                    <h4 style="margin: 0; color: #ffd700;">Середній CPS</h4>
                    <button onclick="resetCpsStats()" style="padding: 5px 10px; font-size: 12px; background: #ef4444;">Скинути</button>
                </div>
                <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; text-align: center;">
                    <div>
                        <div style="color: #888; font-size: 12px;">Генерацій</div>
                        <div id="avg_count" style="font-size: 24px; font-weight: bold; color: #eee;">0</div>
                    </div>
                    <div>
                        <div style="color: #888; font-size: 12px;">Середній</div>
                        <div id="avg_cps" style="font-size: 24px; font-weight: bold; color: #4ade80;">-</div>
                    </div>
                    <div>
                        <div style="color: #888; font-size: 12px;">Мін</div>
                        <div id="min_cps" style="font-size: 24px; font-weight: bold; color: #60a5fa;">-</div>
                    </div>
                    <div>
                        <div style="color: #888; font-size: 12px;">Макс</div>
                        <div id="max_cps" style="font-size: 24px; font-weight: bold; color: #f472b6;">-</div>
                    </div>
                </div>
                <div style="margin-top: 10px; padding-top: 10px; border-top: 1px solid #444;">
                    <div style="color: #888; font-size: 12px; margin-bottom: 5px;">Історія CPS:</div>
                    <div id="cps_history" style="font-size: 12px; color: #aaa; word-break: break-all;">-</div>
                </div>
            </div>

            <audio id="audio" controls></audio>
        </div>

        <div id="voices" class="tab-content">
            <h3>Доступні голоси ({len(voices_list)})</h3>
            <div class="voices-grid">
                {voices_grid_html}
            </div>
            <div class="info" style="margin-top: 20px;">
                <p>Клікніть на голос щоб обрати його для синтезу</p>
            </div>
        </div>

        <div id="intonation" class="tab-content">
            <h3>Тести інтонації</h3>
            <div class="info">
                <p><strong>Питання:</strong></p>
                <button onclick="testPhrase('Ви впевнені, що хочете видалити цей файл?')">Запитання</button>
                <button onclick="testPhrase('Чи бажаєте ви продовжити оформлення замовлення?')">Пропозиція</button>
            </div>
            <div class="info">
                <p><strong>Оклики:</strong></p>
                <button onclick="testPhrase('Вітаємо! Ви виграли головний приз!')">Радість</button>
                <button onclick="testPhrase('На жаль, ваш запит відхилено.')">Сумно</button>
            </div>
            <div class="info">
                <p><strong>Складні фрази:</strong></p>
                <button onclick="testPhrase('Ваш iPhone 15 Pro Max готовий до видачі в магазині Apple Store на Хрещатику.')">Бренди</button>
                <button onclick="testPhrase('Зателефонуйте за номером плюс три вісім нуль, сорок чотири, сто двадцять три, сорок пять, шістдесят сім.')">Числа</button>
            </div>
            <audio id="audio_test" controls style="margin-top: 20px; width: 100%;"></audio>
        </div>

        <div id="features" class="tab-content">
            <h3>Можливості StyleTTS2 Ukrainian</h3>
            <div class="info">
                <h4>31 унікальний голос</h4>
                <p>Різноманітні голоси: чоловічі, жіночі, дитячі. Кожен голос має унікальний тембр та характер.</p>
            </div>
            <div class="info">
                <h4>Наголоси</h4>
                <p>Використовуйте символ <strong>+</strong> після наголошеного складу для правильного наголосу.</p>
                <p>Приклад: "Ки+їв", "Украї+на", "му+дрий"</p>
            </div>
            <div class="info">
                <h4>Швидкість</h4>
                <p>Регулюйте швидкість мовлення від 0.5x (повільно) до 2.0x (швидко).</p>
            </div>
            <div class="info">
                <h4>Білий шум</h4>
                <p>Додайте білий шум для симуляції телефонної лінії.</p>
            </div>
            <div class="info">
                <h4>API Endpoint</h4>
                <p><code>POST /tts</code> - синтез мовлення</p>
                <pre>{{
  "text": "Привіт!",
  "voice": "Анастасія Павленко",
  "model": "multi",
  "speed": 1.0,
  "noise_level": 0.0
}}</pre>
            </div>
        </div>

        <script>
            // CPS tracking
            let cpsHistory = [];

            function updateCpsStats(cps) {{
                cpsHistory.push(parseFloat(cps));

                const count = cpsHistory.length;
                const avg = (cpsHistory.reduce((a, b) => a + b, 0) / count).toFixed(1);
                const min = Math.min(...cpsHistory).toFixed(1);
                const max = Math.max(...cpsHistory).toFixed(1);

                document.getElementById('avg_count').textContent = count;
                document.getElementById('avg_cps').textContent = avg;
                document.getElementById('min_cps').textContent = min;
                document.getElementById('max_cps').textContent = max;
                document.getElementById('cps_history').textContent = cpsHistory.map(c => c.toFixed(1)).join(' → ');
            }}

            function resetCpsStats() {{
                cpsHistory = [];
                document.getElementById('avg_count').textContent = '0';
                document.getElementById('avg_cps').textContent = '-';
                document.getElementById('min_cps').textContent = '-';
                document.getElementById('max_cps').textContent = '-';
                document.getElementById('cps_history').textContent = '-';
            }}

            function showTab(tabId) {{
                document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
                document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
                document.getElementById(tabId).classList.add('active');
                event.target.classList.add('active');
            }}

            function selectVoice(el, voice) {{
                document.querySelectorAll('.voice-item').forEach(v => v.classList.remove('selected'));
                el.classList.add('selected');
                document.getElementById('voice').value = voice;
            }}

            async function generate() {{
                const text = document.getElementById('text').value;
                const voice = document.getElementById('voice').value;
                const speed = parseFloat(document.getElementById('speed').value);
                const noise = parseInt(document.getElementById('noise').value) / 100;

                document.getElementById('status').textContent = 'Генерую...';
                document.getElementById('status').style.color = '#ffd700';
                document.getElementById('stats').style.display = 'none';

                try {{
                    const start = Date.now();
                    const response = await fetch('/tts', {{
                        method: 'POST',
                        headers: {{'Content-Type': 'application/json'}},
                        body: JSON.stringify({{
                            text: text,
                            voice: voice,
                            model: 'multi',
                            speed: speed,
                            noise_level: noise
                        }})
                    }});

                    if (!response.ok) throw new Error('Помилка синтезу');

                    const blob = await response.blob();
                    const elapsed = Date.now() - start;
                    const cps = (text.length / (elapsed / 1000)).toFixed(1);
                    const sizeKB = (blob.size / 1024).toFixed(1);

                    document.getElementById('status').textContent = 'Готово!';
                    document.getElementById('status').style.color = '#4ade80';

                    document.getElementById('stat_chars').textContent = text.length;
                    document.getElementById('stat_time').textContent = (elapsed / 1000).toFixed(2) + ' сек';
                    document.getElementById('stat_cps').textContent = cps;
                    document.getElementById('stat_size').textContent = sizeKB + ' KB';
                    document.getElementById('stat_voice').textContent = voice;
                    document.getElementById('stat_speed').textContent = speed + 'x';
                    document.getElementById('stat_noise').textContent = Math.round(noise * 100) + '%';
                    document.getElementById('stats').style.display = 'block';

                    // Update average CPS stats
                    updateCpsStats(cps);

                    document.getElementById('audio').src = URL.createObjectURL(blob);
                }} catch (e) {{
                    document.getElementById('status').textContent = 'Помилка: ' + e.message;
                    document.getElementById('status').style.color = '#ef4444';
                }}
            }}

            async function testPhrase(text) {{
                const voice = document.getElementById('voice').value;
                const speed = parseFloat(document.getElementById('speed').value);

                try {{
                    const response = await fetch('/tts', {{
                        method: 'POST',
                        headers: {{'Content-Type': 'application/json'}},
                        body: JSON.stringify({{
                            text: text,
                            voice: voice,
                            model: 'multi',
                            speed: speed,
                            noise_level: 0
                        }})
                    }});

                    if (!response.ok) throw new Error('Synthesis failed');

                    const blob = await response.blob();
                    document.getElementById('audio_test').src = URL.createObjectURL(blob);
                }} catch (e) {{
                    alert('Помилка: ' + e.message);
                }}
            }}
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html)


@app.get("/api")
async def api_info():
    """API information"""
    return {
        "service": "StyleTTS2 Ukrainian TTS",
        "version": "1.0",
        "device": device,
        "voices": voices_list,
        "models": ["multi", "single"],
        "endpoints": {
            "/tts": "POST - Synthesize speech",
            "/voices": "GET - List available voices",
            "/health": "GET - Health check"
        }
    }


@app.get("/voices")
async def get_voices():
    """List available voices"""
    return {"voices": voices_list, "count": len(voices_list)}


@app.get("/health")
async def health():
    """Health check"""
    return {
        "status": "ok",
        "device": device,
        "voices_loaded": len(voices_list),
        "models_loaded": list(models.keys())
    }


@app.post("/tts")
async def tts(request: TTSRequest):
    """Synthesize speech"""
    if not request.text.strip():
        raise HTTPException(status_code=400, detail="Text is required")

    if len(request.text) > 50000:
        raise HTTPException(status_code=400, detail="Text too long (max 50000 chars)")

    # Validate speed
    speed = max(0.5, min(2.0, request.speed))

    # Validate model
    model = request.model if request.model in ['multi', 'single'] else 'multi'

    start_time = time.time()

    try:
        # Synthesize
        audio = synthesize_text(
            text=request.text,
            model_name=model,
            voice_name=request.voice,
            speed=speed
        )

        # Add noise if requested
        if request.noise_level > 0:
            audio = add_white_noise(audio, request.noise_level)

        # Convert to WAV
        wav_bytes = numpy_to_wav(audio)

        synthesis_time = time.time() - start_time

        return Response(
            content=wav_bytes,
            media_type="audio/wav",
            headers={
                "X-Synthesis-Time-Ms": str(int(synthesis_time * 1000)),
                "X-CPS": str(int(len(request.text) / synthesis_time)) if synthesis_time > 0 else "0"
            }
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5002)
