from functools import lru_cache
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')

    ENVIRONMENT: str = 'development'
    PROJECT_NAME: str = 'Scores 2026'
    DATABASE_URL: str = 'sqlite:///./scores2026.db'
    REDIS_URL: str = 'redis://localhost:6379/0'
    SECRET_KEY: str = 'dev-secret-change-me'
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 720
    CORS_ORIGINS: str = 'http://localhost:8080,http://localhost:5173'
    CORS_ORIGIN_REGEX: str = ''

    FIRST_SUPERUSER_EMAIL: str = 'admin@scores.local'
    FIRST_SUPERUSER_USERNAME: str = 'admin'
    FIRST_SUPERUSER_PASSWORD: str = 'Admin@123456'

    SOFASCORE_BASE_URL: str = 'https://api.sofascore.com/api/v1'
    SOFASCORE_TOURNAMENT_ID: int = 325
    SOFASCORE_SEASON_ID: int = 87678
    SOFASCORE_SERIE_A_TOURNAMENT_ID: int = 325
    SOFASCORE_SERIE_A_SEASON_ID: int = 87678
    SOFASCORE_SERIE_B_TOURNAMENT_ID: int = 390
    SOFASCORE_SERIE_B_SEASON_ID: int = 89840
    SOFASCORE_COPA_BRASIL_TOURNAMENT_ID: int = 373
    SOFASCORE_COPA_BRASIL_SEASON_ID: int = 89353
    SOFASCORE_WORLD_CUP_TOURNAMENT_ID: int = 16
    SOFASCORE_WORLD_CUP_SEASON_ID: int = 58210
    SOFASCORE_USER_AGENT: str = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
    SOFASCORE_REFERER: str = 'https://www.sofascore.com/'
    SOFASCORE_COOKIE: str = ''

    TELEGRAM_BOT_TOKEN: str = ''
    TELEGRAM_ALLOWED_CHAT_IDS: str = ''

    OPENAI_API_KEY: str = ''
    OPENAI_MODEL: str = 'gpt-4.1-mini'
    OPENAI_BASE_URL: str = ''
    OPENAI_TEMPERATURE: float = 0.2
    OPENAI_MAX_TOKENS: int = 1400

    @property
    def cors_origin_list(self) -> List[str]:
        return [item.strip() for item in self.CORS_ORIGINS.split(',') if item.strip()]

    @property
    def cors_origin_regex_value(self) -> str | None:
        value = self.CORS_ORIGIN_REGEX.strip()
        return value or None

    @property
    def telegram_allowed_chat_ids(self) -> set[int]:
        ids: set[int] = set()
        for raw in self.TELEGRAM_ALLOWED_CHAT_IDS.split(','):
            raw = raw.strip()
            if raw and raw.lstrip('-').isdigit():
                ids.add(int(raw))
        return ids


@lru_cache
def get_settings() -> Settings:
    return Settings()

settings = get_settings()
