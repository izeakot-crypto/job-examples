#!/usr/bin/env python3
"""
TTS Test Platform - Unified testing interface for all TTS services
All languages, all services - one interface on port 5000
"""

import os
import json
import time
import httpx
from datetime import datetime
from typing import Optional, Dict, List, Any
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import Response, HTMLResponse, JSONResponse
from pydantic import BaseModel

app = FastAPI(title="TTS Test Platform", version="1.0")

# Configuration
LOG_DIR = Path(__file__).parent / "test_logs"
LOG_DIR.mkdir(exist_ok=True)

# TTS Services configuration
# Each service has: url, supported languages, voices per language
TTS_SERVICES = {
    "ukrainian-tts": {
        "name": "Ukrainian TTS",
        "url": "http://localhost:5001",
        "languages": ["UA"],
        "voices": {
            "UA": [
                {"id": "dmytro", "name": "Дмитро (чоловічий)"},
                {"id": "tetiana", "name": "Тетяна (жіночий)"},
                {"id": "oleksa", "name": "Олекса (чоловічий)"},
                {"id": "lada", "name": "Лада (жіночий)"},
                {"id": "mykyta", "name": "Микита (чоловічий)"},
            ]
        },
        "supports_speed": False,
        "supports_noise": True,
    },
    "styletts2-ua": {
        "name": "StyleTTS2 Ukrainian",
        "url": "http://localhost:5002",
        "languages": ["UA"],
        "voices": {
            "UA": []  # Will be loaded dynamically
        },
        "supports_speed": True,
        "supports_noise": True,
    },
    "chatterbox": {
        "name": "Chatterbox",
        "url": "http://localhost:5003",
        "languages": ["EN", "ES"],
        "voices": {
            "EN": [{"id": "default", "name": "Default English"}],
            "ES": [{"id": "default", "name": "Default Spanish"}],
        },
        "supports_speed": True,
        "supports_noise": True,
    },
    "silero": {
        "name": "Silero",
        "url": "http://localhost:5004",
        "languages": ["RU"],
        "voices": {
            "RU": [
                {"id": "aidar", "name": "Айдар"},
                {"id": "baya", "name": "Бая"},
                {"id": "kseniya", "name": "Ксенія"},
                {"id": "xenia", "name": "Ксенія (alt)"},
            ]
        },
        "supports_speed": True,
        "supports_noise": True,
    },
    "xtts-v2": {
        "name": "XTTS-v2",
        "url": "http://localhost:5005",
        "languages": ["PL", "TR"],
        "voices": {
            "PL": [{"id": "default", "name": "Default Polish"}],
            "TR": [{"id": "default", "name": "Default Turkish"}],
        },
        "supports_speed": True,
        "supports_noise": True,
    },
}

# Language info
LANGUAGES = {
    "UA": {"name": "Українська", "flag": "🇺🇦"},
    "EN": {"name": "English", "flag": "🇬🇧"},
    "RU": {"name": "Русский", "flag": "🇷🇺"},
    "PL": {"name": "Polski", "flag": "🇵🇱"},
    "ES": {"name": "Español", "flag": "🇪🇸"},
    "TR": {"name": "Türkçe", "flag": "🇹🇷"},
}

# Test phrases cache
test_phrases = {}


class TTSRequest(BaseModel):
    text: str
    language: str
    service: str
    voice: Optional[str] = None
    speed: Optional[float] = 1.0
    noise_level: Optional[float] = 0.0


class TestResult(BaseModel):
    language: str
    service: str
    voice: str
    text: str
    quality_rating: int  # 0-5
    notes: Optional[str] = ""


def load_test_phrases():
    """Load test phrases from JSON file"""
    global test_phrases
    phrases_path = Path(__file__).parent / "test_phrases" / "phrases.json"
    if phrases_path.exists():
        with open(phrases_path, "r", encoding="utf-8") as f:
            test_phrases = json.load(f)


def get_log_file_path() -> Path:
    """Get today's log file path"""
    today = datetime.now().strftime("%Y%m%d")
    return LOG_DIR / f"test_log_{today}.json"


def load_test_logs() -> Dict[str, Any]:
    """Load or create today's log file"""
    log_path = get_log_file_path()
    if log_path.exists():
        with open(log_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"date": datetime.now().strftime("%Y-%m-%d"), "tests": []}


def save_test_log(log_entry: Dict[str, Any]):
    """Save a test result to log file"""
    logs = load_test_logs()
    logs["tests"].append(log_entry)
    log_path = get_log_file_path()
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(logs, f, ensure_ascii=False, indent=2)


def get_services_for_language(lang: str) -> List[Dict[str, Any]]:
    """Get available services for a language"""
    services = []
    for svc_id, svc in TTS_SERVICES.items():
        if lang in svc["languages"]:
            services.append({
                "id": svc_id,
                "name": svc["name"],
                "supports_speed": svc["supports_speed"],
                "supports_noise": svc["supports_noise"],
            })
    return services


def get_voices_for_service(service_id: str, lang: str) -> List[Dict[str, str]]:
    """Get available voices for a service and language"""
    if service_id not in TTS_SERVICES:
        return []
    svc = TTS_SERVICES[service_id]
    return svc["voices"].get(lang, [])


@app.on_event("startup")
async def startup():
    """Load resources on startup"""
    load_test_phrases()

    # Try to load StyleTTS2 voices dynamically
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get("http://localhost:5002/voices")
            if response.status_code == 200:
                data = response.json()
                voices = [{"id": v, "name": v} for v in data.get("voices", [])]
                TTS_SERVICES["styletts2-ua"]["voices"]["UA"] = voices
    except Exception:
        # Use default voices if service not available
        TTS_SERVICES["styletts2-ua"]["voices"]["UA"] = [
            {"id": "Анастасія Павленко", "name": "Анастасія Павленко"}
        ]


@app.get("/", response_class=HTMLResponse)
async def index():
    """Main web interface"""
    # Generate language options
    lang_options = ""
    for lang_id, lang_info in LANGUAGES.items():
        lang_options += f'<option value="{lang_id}">{lang_info["flag"]} {lang_info["name"]}</option>\n'

    # Generate phrases data for JavaScript
    phrases_json = json.dumps(test_phrases, ensure_ascii=False)
    services_json = json.dumps(TTS_SERVICES, ensure_ascii=False)
    languages_json = json.dumps(LANGUAGES, ensure_ascii=False)

    html = f'''<!DOCTYPE html>
<html lang="uk">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TTS Test Platform</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
            min-height: 100vh;
            color: #eee;
            padding: 20px;
        }}
        .container {{
            max-width: 900px;
            margin: 0 auto;
        }}
        h1 {{
            text-align: center;
            color: #ffd700;
            font-size: 28px;
            margin-bottom: 5px;
        }}
        .subtitle {{
            text-align: center;
            color: #888;
            margin-bottom: 20px;
        }}
        .panel {{
            background: rgba(22, 33, 62, 0.9);
            border-radius: 15px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.3);
        }}
        .row {{
            display: flex;
            gap: 15px;
            margin-bottom: 15px;
            flex-wrap: wrap;
        }}
        .col {{
            flex: 1;
            min-width: 200px;
        }}
        label {{
            display: block;
            color: #ffd700;
            font-weight: 600;
            margin-bottom: 8px;
            font-size: 14px;
        }}
        select, textarea, input[type="text"] {{
            width: 100%;
            padding: 12px;
            border: 2px solid #0f3460;
            border-radius: 10px;
            background: #0d1b2a;
            color: #fff;
            font-size: 15px;
        }}
        select:focus, textarea:focus {{
            outline: none;
            border-color: #ffd700;
        }}
        textarea {{
            height: 100px;
            resize: vertical;
        }}
        .slider-group {{
            padding: 10px 0;
        }}
        .slider-header {{
            display: flex;
            justify-content: space-between;
            margin-bottom: 8px;
        }}
        .slider-value {{
            color: #4ade80;
            font-weight: bold;
        }}
        input[type="range"] {{
            width: 100%;
            height: 8px;
            -webkit-appearance: none;
            background: #0d1b2a;
            border-radius: 4px;
        }}
        input[type="range"]::-webkit-slider-thumb {{
            -webkit-appearance: none;
            width: 20px;
            height: 20px;
            background: #ffd700;
            border-radius: 50%;
            cursor: pointer;
        }}
        .btn {{
            padding: 15px 30px;
            border: none;
            border-radius: 10px;
            font-size: 18px;
            font-weight: bold;
            cursor: pointer;
            transition: all 0.3s;
        }}
        .btn-primary {{
            background: linear-gradient(135deg, #ffd700 0%, #ffed4a 100%);
            color: #1a1a2e;
            width: 100%;
        }}
        .btn-primary:hover {{
            transform: translateY(-2px);
            box-shadow: 0 5px 20px rgba(255, 215, 0, 0.4);
        }}
        .btn-primary:disabled {{
            background: #555;
            cursor: not-allowed;
            transform: none;
        }}
        .btn-save {{
            background: linear-gradient(135deg, #4ade80 0%, #22c55e 100%);
            color: #1a1a2e;
            width: 100%;
            margin-top: 15px;
        }}
        .btn-save:hover {{
            box-shadow: 0 5px 20px rgba(74, 222, 128, 0.4);
        }}
        audio {{
            width: 100%;
            margin: 15px 0;
        }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 10px;
            margin: 15px 0;
        }}
        .stat-box {{
            background: #0d1b2a;
            padding: 15px;
            border-radius: 10px;
            text-align: center;
        }}
        .stat-value {{
            font-size: 24px;
            font-weight: bold;
            color: #4ade80;
        }}
        .stat-label {{
            font-size: 12px;
            color: #888;
            margin-top: 5px;
        }}
        .rating-section {{
            background: #0d1b2a;
            padding: 20px;
            border-radius: 10px;
            margin-top: 15px;
        }}
        .rating-title {{
            color: #ffd700;
            margin-bottom: 15px;
            font-size: 16px;
        }}
        .stars {{
            display: flex;
            gap: 10px;
            margin-bottom: 15px;
        }}
        .star {{
            width: 40px;
            height: 40px;
            background: #16213e;
            border: 2px solid #333;
            border-radius: 8px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 18px;
            cursor: pointer;
            transition: all 0.2s;
        }}
        .star:hover {{
            border-color: #ffd700;
            transform: scale(1.1);
        }}
        .star.selected {{
            background: #ffd700;
            color: #1a1a2e;
            border-color: #ffd700;
        }}
        .notes-input {{
            width: 100%;
            padding: 12px;
            border: 2px solid #333;
            border-radius: 10px;
            background: #16213e;
            color: #fff;
            font-size: 14px;
        }}
        .notes-input:focus {{
            outline: none;
            border-color: #ffd700;
        }}
        .phrases-section {{
            margin-top: 15px;
        }}
        .category-tabs {{
            display: flex;
            gap: 5px;
            flex-wrap: wrap;
            margin-bottom: 10px;
        }}
        .cat-tab {{
            padding: 8px 15px;
            background: #0d1b2a;
            border: 1px solid #333;
            border-radius: 20px;
            color: #888;
            cursor: pointer;
            font-size: 13px;
            transition: all 0.2s;
        }}
        .cat-tab:hover {{
            border-color: #ffd700;
            color: #ffd700;
        }}
        .cat-tab.active {{
            background: #ffd700;
            color: #1a1a2e;
            border-color: #ffd700;
        }}
        .phrase-buttons {{
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
        }}
        .phrase-btn {{
            padding: 8px 15px;
            background: #16213e;
            border: 1px solid #333;
            border-radius: 8px;
            color: #aaa;
            cursor: pointer;
            font-size: 13px;
            max-width: 100%;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }}
        .phrase-btn:hover {{
            border-color: #4ade80;
            color: #4ade80;
        }}
        .avg-stats {{
            background: linear-gradient(135deg, #1a1a3e 0%, #16213e 100%);
            border: 1px solid #ffd700;
            border-radius: 10px;
            padding: 15px;
            margin-top: 15px;
        }}
        .avg-stats-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
        }}
        .avg-stats-header h4 {{
            color: #ffd700;
            margin: 0;
        }}
        .btn-reset {{
            padding: 5px 10px;
            background: #ef4444;
            border: none;
            border-radius: 5px;
            color: #fff;
            cursor: pointer;
            font-size: 12px;
        }}
        .avg-stats-grid {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 10px;
            text-align: center;
        }}
        .avg-stat-label {{
            color: #888;
            font-size: 12px;
        }}
        .avg-stat-value {{
            font-size: 24px;
            font-weight: bold;
        }}
        .cps-history {{
            margin-top: 15px;
            padding-top: 15px;
            border-top: 1px solid #333;
            font-size: 12px;
            color: #888;
        }}
        #result {{
            display: none;
        }}
        #result.show {{
            display: block;
        }}
        .status {{
            text-align: center;
            padding: 15px;
            font-size: 16px;
        }}
        .status.loading {{
            color: #ffd700;
        }}
        .status.success {{
            color: #4ade80;
        }}
        .status.error {{
            color: #ef4444;
        }}
        .service-status {{
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 12px;
            color: #888;
            margin-top: 5px;
        }}
        .status-dot {{
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: #888;
        }}
        .status-dot.online {{
            background: #4ade80;
        }}
        .status-dot.offline {{
            background: #ef4444;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>TTS Test Platform</h1>
        <p class="subtitle">Єдина платформа тестування TTS сервісів</p>

        <div class="panel">
            <div class="row">
                <div class="col">
                    <label>🌐 Мова</label>
                    <select id="language" onchange="onLanguageChange()">
                        {lang_options}
                    </select>
                </div>
                <div class="col">
                    <label>🔊 Сервіс</label>
                    <select id="service" onchange="onServiceChange()">
                        <option value="">-- Оберіть мову --</option>
                    </select>
                    <div class="service-status">
                        <span class="status-dot" id="serviceDot"></span>
                        <span id="serviceStatus">Перевірка...</span>
                    </div>
                </div>
                <div class="col">
                    <label>🎤 Голос</label>
                    <select id="voice">
                        <option value="">-- Оберіть сервіс --</option>
                    </select>
                </div>
            </div>

            <div>
                <label>📝 Текст для синтезу</label>
                <textarea id="text" placeholder="Введіть текст..."></textarea>
            </div>

            <div class="row" style="margin-top: 15px;">
                <div class="col">
                    <div class="slider-group">
                        <div class="slider-header">
                            <label>⚡ Швидкість</label>
                            <span class="slider-value" id="speedValue">1.0x</span>
                        </div>
                        <input type="range" id="speed" min="0.5" max="2.0" step="0.1" value="1.0"
                               oninput="document.getElementById('speedValue').textContent = this.value + 'x'">
                    </div>
                </div>
                <div class="col">
                    <div class="slider-group">
                        <div class="slider-header">
                            <label>📞 Білий шум</label>
                            <span class="slider-value" id="noiseValue">0%</span>
                        </div>
                        <input type="range" id="noise" min="0" max="100" step="1" value="0"
                               oninput="document.getElementById('noiseValue').textContent = this.value + '%'">
                    </div>
                </div>
            </div>

            <button class="btn btn-primary" id="generateBtn" onclick="generate()">
                ЗГЕНЕРУВАТИ
            </button>
        </div>

        <!-- Test Phrases Section -->
        <div class="panel phrases-section">
            <label>📋 Тестові фрази</label>
            <div class="category-tabs" id="categoryTabs"></div>
            <div class="phrase-buttons" id="phraseButtons"></div>
        </div>

        <!-- Results Section -->
        <div class="panel" id="result">
            <div class="status" id="status"></div>

            <audio id="audio" controls></audio>

            <div class="stats-grid">
                <div class="stat-box">
                    <div class="stat-value" id="statChars">-</div>
                    <div class="stat-label">Символів</div>
                </div>
                <div class="stat-box">
                    <div class="stat-value" id="statTime">-</div>
                    <div class="stat-label">Час (сек)</div>
                </div>
                <div class="stat-box">
                    <div class="stat-value" id="statCps">-</div>
                    <div class="stat-label">CPS</div>
                </div>
                <div class="stat-box">
                    <div class="stat-value" id="statSize">-</div>
                    <div class="stat-label">Розмір (KB)</div>
                </div>
            </div>

            <div class="avg-stats">
                <div class="avg-stats-header">
                    <h4>📊 Середній CPS</h4>
                    <button class="btn-reset" onclick="resetCpsStats()">Скинути</button>
                </div>
                <div class="avg-stats-grid">
                    <div>
                        <div class="avg-stat-label">Генерацій</div>
                        <div class="avg-stat-value" id="avgCount" style="color: #eee;">0</div>
                    </div>
                    <div>
                        <div class="avg-stat-label">Середній</div>
                        <div class="avg-stat-value" id="avgCps" style="color: #4ade80;">-</div>
                    </div>
                    <div>
                        <div class="avg-stat-label">Мін</div>
                        <div class="avg-stat-value" id="minCps" style="color: #60a5fa;">-</div>
                    </div>
                    <div>
                        <div class="avg-stat-label">Макс</div>
                        <div class="avg-stat-value" id="maxCps" style="color: #f472b6;">-</div>
                    </div>
                </div>
                <div class="cps-history">
                    <span>Історія: </span>
                    <span id="cpsHistory">-</span>
                </div>
            </div>

            <div class="rating-section">
                <div class="rating-title">⭐ Оцінка якості</div>
                <div class="stars" id="stars">
                    <div class="star" data-rating="0" onclick="setRating(0)">0</div>
                    <div class="star" data-rating="1" onclick="setRating(1)">1</div>
                    <div class="star" data-rating="2" onclick="setRating(2)">2</div>
                    <div class="star" data-rating="3" onclick="setRating(3)">3</div>
                    <div class="star" data-rating="4" onclick="setRating(4)">4</div>
                    <div class="star" data-rating="5" onclick="setRating(5)">5</div>
                </div>
                <input type="text" class="notes-input" id="notes" placeholder="📝 Нотатки (опціонально)...">
                <button class="btn btn-save" onclick="saveResult()">
                    💾 ЗБЕРЕГТИ РЕЗУЛЬТАТ
                </button>
            </div>
        </div>
    </div>

    <script>
        // Data
        const phrases = {phrases_json};
        const services = {services_json};
        const languages = {languages_json};

        // State
        let cpsHistory = [];
        let currentRating = -1;
        let lastSynthesisData = null;
        let selectedCategory = 'basic';

        // Initialize
        document.addEventListener('DOMContentLoaded', () => {{
            onLanguageChange();
        }});

        function onLanguageChange() {{
            const lang = document.getElementById('language').value;
            const serviceSelect = document.getElementById('service');

            // Clear service options
            serviceSelect.innerHTML = '<option value="">-- Оберіть сервіс --</option>';

            // Add available services for this language
            for (const [svcId, svc] of Object.entries(services)) {{
                if (svc.languages.includes(lang)) {{
                    const opt = document.createElement('option');
                    opt.value = svcId;
                    opt.textContent = svc.name;
                    serviceSelect.appendChild(opt);
                }}
            }}

            // Auto-select first service if only one
            if (serviceSelect.options.length === 2) {{
                serviceSelect.selectedIndex = 1;
            }}

            onServiceChange();
            updatePhrases();
        }}

        async function onServiceChange() {{
            const lang = document.getElementById('language').value;
            const serviceId = document.getElementById('service').value;
            const voiceSelect = document.getElementById('voice');
            const speedSlider = document.getElementById('speed');

            // Reset voice select
            voiceSelect.innerHTML = '<option value="">-- Оберіть голос --</option>';

            if (!serviceId) {{
                document.getElementById('serviceDot').className = 'status-dot';
                document.getElementById('serviceStatus').textContent = 'Оберіть сервіс';
                return;
            }}

            const svc = services[serviceId];

            // Disable speed slider if not supported
            speedSlider.disabled = !svc.supports_speed;
            if (!svc.supports_speed) {{
                speedSlider.value = 1.0;
                document.getElementById('speedValue').textContent = '1.0x (не підтримується)';
            }} else {{
                document.getElementById('speedValue').textContent = speedSlider.value + 'x';
            }}

            // Check service status and load voices
            try {{
                document.getElementById('serviceDot').className = 'status-dot';
                document.getElementById('serviceStatus').textContent = 'Перевірка...';

                const response = await fetch(`/api/service/${{serviceId}}/status`);
                const data = await response.json();

                if (data.online) {{
                    document.getElementById('serviceDot').className = 'status-dot online';
                    document.getElementById('serviceStatus').textContent = 'Онлайн';

                    // Load voices from API
                    const voices = data.voices || [];
                    if (voices.length > 0) {{
                        voices.forEach(v => {{
                            const opt = document.createElement('option');
                            opt.value = v.id || v;
                            opt.textContent = v.name || v;
                            voiceSelect.appendChild(opt);
                        }});
                    }} else {{
                        // Fallback to config voices
                        const configVoices = svc.voices[lang] || [];
                        configVoices.forEach(v => {{
                            const opt = document.createElement('option');
                            opt.value = v.id;
                            opt.textContent = v.name;
                            voiceSelect.appendChild(opt);
                        }});
                    }}
                }} else {{
                    document.getElementById('serviceDot').className = 'status-dot offline';
                    document.getElementById('serviceStatus').textContent = 'Офлайн - ' + (data.error || 'недоступний');
                }}
            }} catch (e) {{
                document.getElementById('serviceDot').className = 'status-dot offline';
                document.getElementById('serviceStatus').textContent = 'Помилка перевірки';
            }}
        }}

        function updatePhrases() {{
            const lang = document.getElementById('language').value;
            const tabsContainer = document.getElementById('categoryTabs');
            const buttonsContainer = document.getElementById('phraseButtons');

            tabsContainer.innerHTML = '';
            buttonsContainer.innerHTML = '';

            if (!phrases[lang]) return;

            const langPhrases = phrases[lang].phrases;
            const categories = Object.keys(langPhrases);

            // Create category tabs
            categories.forEach(cat => {{
                const tab = document.createElement('div');
                tab.className = 'cat-tab' + (cat === selectedCategory ? ' active' : '');
                tab.textContent = cat;
                tab.onclick = () => {{
                    selectedCategory = cat;
                    updatePhrases();
                }};
                tabsContainer.appendChild(tab);
            }});

            // Create phrase buttons for selected category
            const categoryPhrases = langPhrases[selectedCategory] || [];
            categoryPhrases.forEach(phrase => {{
                const btn = document.createElement('button');
                btn.className = 'phrase-btn';
                btn.textContent = phrase.substring(0, 50) + (phrase.length > 50 ? '...' : '');
                btn.title = phrase;
                btn.onclick = () => {{
                    document.getElementById('text').value = phrase;
                }};
                buttonsContainer.appendChild(btn);
            }});
        }}

        async function generate() {{
            const text = document.getElementById('text').value.trim();
            const language = document.getElementById('language').value;
            const service = document.getElementById('service').value;
            const voice = document.getElementById('voice').value;
            const speed = parseFloat(document.getElementById('speed').value);
            const noise = parseInt(document.getElementById('noise').value) / 100;

            if (!text) {{
                alert('Введіть текст!');
                return;
            }}
            if (!service) {{
                alert('Оберіть сервіс!');
                return;
            }}

            const btn = document.getElementById('generateBtn');
            const resultDiv = document.getElementById('result');
            const statusDiv = document.getElementById('status');

            btn.disabled = true;
            btn.textContent = '⏳ Генерація...';
            resultDiv.classList.add('show');
            statusDiv.className = 'status loading';
            statusDiv.textContent = 'Генерую аудіо...';

            try {{
                const startTime = Date.now();

                const response = await fetch('/api/synthesize', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{
                        text: text,
                        language: language,
                        service: service,
                        voice: voice || null,
                        speed: speed,
                        noise_level: noise
                    }})
                }});

                if (!response.ok) {{
                    const error = await response.json();
                    throw new Error(error.detail || 'Помилка синтезу');
                }}

                const blob = await response.blob();
                const elapsed = Date.now() - startTime;
                const cps = (text.length / (elapsed / 1000)).toFixed(1);
                const sizeKB = (blob.size / 1024).toFixed(1);

                // Update stats
                document.getElementById('statChars').textContent = text.length;
                document.getElementById('statTime').textContent = (elapsed / 1000).toFixed(2);
                document.getElementById('statCps').textContent = cps;
                document.getElementById('statSize').textContent = sizeKB;

                // Update CPS history
                updateCpsStats(parseFloat(cps));

                // Play audio
                const audio = document.getElementById('audio');
                audio.src = URL.createObjectURL(blob);

                statusDiv.className = 'status success';
                statusDiv.textContent = 'Готово!';

                // Store synthesis data for saving
                lastSynthesisData = {{
                    text: text,
                    language: language,
                    service: service,
                    voice: voice,
                    speed: speed,
                    noise_level: noise,
                    chars: text.length,
                    synthesis_time_ms: elapsed,
                    cps: parseFloat(cps),
                    audio_size_kb: parseFloat(sizeKB)
                }};

                // Reset rating
                currentRating = -1;
                document.querySelectorAll('.star').forEach(s => s.classList.remove('selected'));
                document.getElementById('notes').value = '';

            }} catch (e) {{
                statusDiv.className = 'status error';
                statusDiv.textContent = 'Помилка: ' + e.message;
            }}

            btn.disabled = false;
            btn.textContent = 'ЗГЕНЕРУВАТИ';
        }}

        function updateCpsStats(cps) {{
            cpsHistory.push(cps);

            const count = cpsHistory.length;
            const avg = (cpsHistory.reduce((a, b) => a + b, 0) / count).toFixed(1);
            const min = Math.min(...cpsHistory).toFixed(1);
            const max = Math.max(...cpsHistory).toFixed(1);

            document.getElementById('avgCount').textContent = count;
            document.getElementById('avgCps').textContent = avg;
            document.getElementById('minCps').textContent = min;
            document.getElementById('maxCps').textContent = max;
            document.getElementById('cpsHistory').textContent = cpsHistory.map(c => c.toFixed(1)).join(' → ');
        }}

        function resetCpsStats() {{
            cpsHistory = [];
            document.getElementById('avgCount').textContent = '0';
            document.getElementById('avgCps').textContent = '-';
            document.getElementById('minCps').textContent = '-';
            document.getElementById('maxCps').textContent = '-';
            document.getElementById('cpsHistory').textContent = '-';
        }}

        function setRating(rating) {{
            currentRating = rating;
            document.querySelectorAll('.star').forEach(s => {{
                s.classList.toggle('selected', parseInt(s.dataset.rating) === rating);
            }});
        }}

        async function saveResult() {{
            if (!lastSynthesisData) {{
                alert('Спочатку згенеруйте аудіо!');
                return;
            }}
            if (currentRating < 0) {{
                alert('Оберіть оцінку якості!');
                return;
            }}

            const notes = document.getElementById('notes').value.trim();

            try {{
                const response = await fetch('/api/save-result', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{
                        ...lastSynthesisData,
                        quality_rating: currentRating,
                        notes: notes
                    }})
                }});

                if (response.ok) {{
                    alert('Результат збережено!');
                }} else {{
                    throw new Error('Помилка збереження');
                }}
            }} catch (e) {{
                alert('Помилка: ' + e.message);
            }}
        }}

        // Keyboard shortcut
        document.getElementById('text').addEventListener('keydown', (e) => {{
            if (e.ctrlKey && e.key === 'Enter') generate();
        }});
    </script>
</body>
</html>'''
    return HTMLResponse(content=html)


@app.get("/api/languages")
async def get_languages():
    """Get available languages"""
    return LANGUAGES


@app.get("/api/services/{language}")
async def get_services(language: str):
    """Get available services for a language"""
    return get_services_for_language(language)


@app.get("/api/service/{service_id}/status")
async def check_service_status(service_id: str):
    """Check if a service is online and get its voices"""
    if service_id not in TTS_SERVICES:
        return {"online": False, "error": "Unknown service"}

    svc = TTS_SERVICES[service_id]

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            # Try health endpoint
            response = await client.get(f"{svc['url']}/health")
            if response.status_code != 200:
                return {"online": False, "error": "Health check failed"}

            # Try to get voices
            voices = []
            try:
                voice_response = await client.get(f"{svc['url']}/voices")
                if voice_response.status_code == 200:
                    data = voice_response.json()
                    raw_voices = data.get("voices", [])
                    voices = [{"id": v, "name": v} if isinstance(v, str) else v for v in raw_voices]
            except Exception:
                pass

            # Fallback to API endpoint
            if not voices:
                try:
                    api_response = await client.get(f"{svc['url']}/api")
                    if api_response.status_code == 200:
                        data = api_response.json()
                        raw_voices = data.get("voices", [])
                        voices = [{"id": v, "name": v} if isinstance(v, str) else v for v in raw_voices]
                except Exception:
                    pass

            return {"online": True, "voices": voices}

    except Exception as e:
        return {"online": False, "error": str(e)}


@app.get("/api/voices/{service_id}/{language}")
async def get_voices(service_id: str, language: str):
    """Get voices for a service and language"""
    return get_voices_for_service(service_id, language)


@app.get("/api/phrases/{language}")
async def get_phrases(language: str):
    """Get test phrases for a language"""
    if language in test_phrases:
        return test_phrases[language]
    return {"phrases": {}}


@app.post("/api/synthesize")
async def synthesize(request: TTSRequest):
    """Synthesize speech via the appropriate TTS service"""
    if request.service not in TTS_SERVICES:
        raise HTTPException(status_code=400, detail=f"Unknown service: {request.service}")

    svc = TTS_SERVICES[request.service]

    if request.language not in svc["languages"]:
        raise HTTPException(
            status_code=400,
            detail=f"Language {request.language} not supported by {svc['name']}"
        )

    # Build request for the TTS service
    tts_request = {
        "text": request.text,
    }

    # Add voice if specified
    if request.voice:
        tts_request["voice"] = request.voice

    # Add speed if supported
    if svc["supports_speed"] and request.speed:
        tts_request["speed"] = request.speed

    # Add noise if supported
    if svc["supports_noise"] and request.noise_level:
        tts_request["noise_level"] = request.noise_level

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{svc['url']}/tts",
                json=tts_request
            )

            if response.status_code != 200:
                error_detail = "TTS service error"
                try:
                    error_data = response.json()
                    error_detail = error_data.get("detail", error_detail)
                except Exception:
                    pass
                raise HTTPException(status_code=response.status_code, detail=error_detail)

            return Response(
                content=response.content,
                media_type="audio/wav",
                headers={
                    "X-Service": request.service,
                    "X-Language": request.language,
                }
            )

    except httpx.RequestError as e:
        raise HTTPException(status_code=503, detail=f"Service unavailable: {str(e)}")


@app.post("/api/save-result")
async def save_result(data: Dict[str, Any]):
    """Save a test result to the log file"""
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "language": data.get("language"),
        "service": data.get("service"),
        "voice": data.get("voice"),
        "text": data.get("text"),
        "chars": data.get("chars"),
        "synthesis_time_ms": data.get("synthesis_time_ms"),
        "cps": data.get("cps"),
        "audio_size_kb": data.get("audio_size_kb"),
        "speed": data.get("speed"),
        "noise_level": data.get("noise_level"),
        "quality_rating": data.get("quality_rating"),
        "notes": data.get("notes", ""),
    }

    save_test_log(log_entry)

    return {"status": "saved", "timestamp": log_entry["timestamp"]}


@app.get("/api/logs")
async def get_logs():
    """Get today's test logs"""
    return load_test_logs()


@app.get("/api/logs/{date}")
async def get_logs_by_date(date: str):
    """Get logs for a specific date (YYYYMMDD format)"""
    log_path = LOG_DIR / f"test_log_{date}.json"
    if log_path.exists():
        with open(log_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"date": date, "tests": []}


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "ok", "service": "TTS Test Platform"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)
