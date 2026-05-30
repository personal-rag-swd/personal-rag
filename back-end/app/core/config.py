from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = ""
    jwt_secret_key: str = "change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 30
    otp_expire_minutes: int = 10
    otp_max_attempts: int = 5
    resend_api_key: str = ""
    resend_from_email: str = "noreply@example.com"
    
    # Centralized Chat / LLM settings
    chat_provider: str = "openrouter"
    chat_api_key: str = ""
    chat_provider_url: str = ""
    chat_model: str = "openai/gpt-4o-mini"
    
    # Centralized Embedding settings
    embedding_provider: str = "auto"
    embedding_api_key: str = ""
    embedding_provider_url: str = ""
    embedding_model: str = "text-embedding-3-small"
    embedding_dimension: int = 1536
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:5173", "http://localhost:8000"]

    @field_validator("cors_origins", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str):
            v_clean = v.strip()
            if v_clean.startswith("[") and v_clean.endswith("]"):
                v_clean = v_clean[1:-1]
            
            # Split by comma
            parts = v_clean.split(",")
            origins = []
            for part in parts:
                part = part.strip()
                # Strip leading/trailing single and double quotes
                part = part.strip("'\"")
                if part:
                    origins.append(part)
            return origins
        elif isinstance(v, list):
            return [str(item).strip() for item in v]
        return v
    cookie_secure: bool | None = None
    cookie_samesite: str = "lax"
    s3_bucket: str = "personal-rag-users-files"
    s3_region: str = "us-east-1"
    s3_endpoint_url: str | None = None
    s3_public_endpoint_url: str | None = None
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    logfire_token: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


def get_database_url() -> str:
    database_url = get_settings().database_url
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    return database_url
