from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(BASE_DIR / ".env"), extra="ignore")

    APP_NAME: str = "BrandProof API"
    ENV: str = "development"
    API_PREFIX: str = "/api"

    DATABASE_URL: str = f"sqlite:///{(BASE_DIR / 'brandproof.db').as_posix()}"
    JWT_SECRET: str = "change-me-in-production-brandproof-dev-secret"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24
    RESET_TOKEN_EXPIRE_MINUTES: int = 30

    UPLOAD_DIR: str = str(BASE_DIR / "uploads")
    MAX_UPLOAD_MB: int = 15
    ALLOWED_UPLOAD_EXTENSIONS: List[str] = [
        ".pdf", ".txt", ".md", ".docx", ".png", ".jpg", ".jpeg", ".webp",
    ]

    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"

    # AI is provider-agnostic. Any OpenAI-compatible chat completions endpoint works.
    AI_PROVIDER: str = "none"  # none | openai-compatible
    AI_API_KEY: str = ""
    AI_BASE_URL: str = "https://api.openai.com/v1"
    AI_MODEL: str = "gpt-4o-mini"
    AI_TIMEOUT_SECONDS: int = 45

    # Embeddings: local deterministic vectoriser (default) or API embeddings.
    EMBEDDINGS_PROVIDER: str = "local"  # local | openai-compatible
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_DIM: int = 512

    SEED_DEMO_DATA: bool = True

    @property
    def ai_enabled(self) -> bool:
        return self.AI_PROVIDER != "none" and bool(self.AI_API_KEY)

    @property
    def cors_origin_list(self) -> List[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
Path(settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
