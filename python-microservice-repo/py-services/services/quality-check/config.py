from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # --- Общие (без префикса, как в py-services) ---
    log_dir: str = "/var/log/py-services"
    log_level: str = "INFO"
    discord_webhook: str = ""

    # LLM
    llm_provider: str = "gemini"
    llm_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai"
    llm_model: str = "gemini-2.5-flash"
    llm_api_key: str = ""
    llm_max_retries: int = 3
    llm_temperature: float = 0.1

    # --- Quality Check (QC_ префикс) ---
    qc_port: int = 8591
    qc_api_key: str = ""
    qc_discord_webhook: str = ""
    qc_oki_toki_api_token: str = ""
    qc_oki_toki_base_url: str = "https://one.oki-toki.net"
    qc_oki_toki_comp_id: int = 1
    qc_max_concurrent_llm: int = 3
    qc_skip_short_calls_sec: int = 3
    qc_poll_interval_sec: int = 300  # 5 минут
    qc_poll_enabled: bool = False
    qc_report_secret: str = ""  # HMAC-ключ для подписи ссылок на отчёты

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
