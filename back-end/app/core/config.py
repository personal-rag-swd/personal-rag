from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REQUIRED_EMBEDDING_DIMENSION = 1536


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
    log_level: str = "INFO"

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
    embedding_batch_size: int = 16
    embedding_delay_seconds: float = 0.5
    embedding_max_retries: int = 5
    notebook_retrieval_top_k: int = 6
    notebook_chunk_size: int = 1000
    notebook_chunk_overlap: int = 200
    file_ingestion_processing_timeout_minutes: int = 15
    rabbitmq_consumer_enabled: bool = False
    rabbitmq_url: str = "amqp://guest:guest@rabbitmq:5672/"
    rabbitmq_exchange_name: str = "minio-events"
    rabbitmq_exchange_type: str = "direct"
    rabbitmq_routing_key: str = "minio.object.created"
    rabbitmq_queue_name: str = "notebook-document-ingestion"
    rabbitmq_dead_letter_exchange_name: str | None = "minio-events-dlx"
    rabbitmq_dead_letter_queue_name: str | None = (
        "notebook-document-ingestion-dead-letter"
    )
    rabbitmq_dead_letter_routing_key: str = "notebook-document-ingestion.dead-letter"
    rabbitmq_prefetch_count: int = 1
    rabbitmq_reconnect_delay_seconds: float = 5.0
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:8000",
    ]

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
                # Strip leading/trailing single and double quotes
                origin = part.strip().strip("'\"")
                if origin:
                    origins.append(origin)
            return origins
        if isinstance(v, list):
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


def validate_rag_embedding_dimension(settings: Settings) -> None:
    if settings.embedding_dimension != REQUIRED_EMBEDDING_DIMENSION:
        raise RuntimeError(
            "Invalid EMBEDDING_DIMENSION. This deployment uses a fixed "
            f"{REQUIRED_EMBEDDING_DIMENSION}-dimension pgvector schema, but got "
            f"{settings.embedding_dimension}. Set EMBEDDING_DIMENSION={REQUIRED_EMBEDDING_DIMENSION}."
        )
