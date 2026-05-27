from functools import lru_cache

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
    cors_origins: list[str] = ["http://localhost:3000"]
    s3_bucket: str = "personal-rag-bucket"
    s3_region: str = "us-east-1"
    s3_endpoint_url: str | None = None
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None

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
