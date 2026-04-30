from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "LIRA Voice Assistants API"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8000

    class Config:
        env_prefix = "LIRA_"


settings = Settings()
