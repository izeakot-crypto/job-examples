from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    anthropic_api_key: str = ""
    anthropic_base_url: str = ""
    gemini_api_key: str = ""
    supabase_url: str = ""
    supabase_key: str = ""
    frontend_base_url: str = "http://157.180.42.152:3000"
    browser_ws_primary: str = "ws://172.44.1.234:3000/chromium"
    browser_ws_secondary: str = "ws://31.131.19.114:3000/chromium"
    google_cse_key: str = ""
    google_cse_id: str = ""
    wp_base_url: str = ""
    wp_username: str = ""
    wp_app_password: str = ""
    ollama_base_url: str = ""
    ollama_api_key: str = ""
    ollama_model: str = "n8n-opus-sdk"
    host: str = "0.0.0.0"
    port: int = 8000

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()

LANGUAGES = ["en", "ru", "pl", "es", "tr", "uk"]

MAX_ATTEMPTS = 3
MIN_CONTENT_LENGTH = 12000
MAX_CONTENT_LENGTH = 18000
GRAMMAR_MAX_CHARS = 10000
LANGUAGETOOL_URL = "https://api.languagetool.org/v2/check"
TR_GRAMMAR_URL = "https://paraphrasetool.com/langs/turkish-grammar-checker"

PROTECTED_TERMS = [
    "oki-toki", "oki toti", "okitoki",
    "call-center", "contact-center",
    "crm", "api", "sip", "voip",
]

LANG_TO_LANGUAGETOOL = {
    "en": "en-US",
    "ru": "ru-RU",
    "pl": "pl-PL",
    "es": "es",
    "uk": "uk-UA",
}

# Verification thresholds (calibrated for text_stats.py algorithm)
# text_stats water = stop_words/total_words (typically 15-40%)
# text_stats nausea = top_content_word/total_content_words (typically 0.5-3%)
ADVEGO_NAUSEA_RANGE = (0.3, 5.0)
ADVEGO_WATER_RANGE = (10, 50)

# Claude models per language
CLAUDE_MODELS = {
    "en": "claude-sonnet-4-5-20250929",
    "ru": "claude-sonnet-4-20250514",
    "pl": "claude-sonnet-4-20250514",
    "es": "claude-sonnet-4-20250514",
    "tr": "claude-sonnet-4-20250514",
    "uk": "claude-sonnet-4-20250514",
}

QTRANSLATE_LANGS = ["ru", "ua", "en", "pl", "es", "tr"]

# Mapping from pipeline DB lang suffixes to qTranslate lang codes
DB_LANG_TO_QT = {"ru": "ru", "uk": "ua", "en": "en", "pl": "pl", "es": "es", "tr": "tr"}

CLAUDE_MAX_TOKENS = {
    "en": 3500,
    "ru": 8000,
    "pl": 8000,
    "es": 5000,
    "tr": 10000,
    "uk": 8000,
}
