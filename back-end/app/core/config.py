from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "mongodb://localhost:27017/personal-rag"
    jwt_secret_key: str = "change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 30
    otp_expire_minutes: int = 10
    otp_max_attempts: int = 5
    resend_api_key: str = ""
    resend_from_email: str = "noreply@example.com"
    log_level: str = "INFO"

    chat_api_key: str = ""
    chat_model: str = "openai/gpt-4o-mini"

    embedding_model: str = "google/gemini-embedding-2"
    embedding_dimension: int = 1536

    notebook_retrieval_top_k: int = 6
    enable_query_rewrite: bool = True
    notebook_chunk_size: int = 1000
    notebook_chunk_overlap: int = 200
    file_ingestion_processing_timeout_minutes: int = 15
    rabbitmq_consumer_enabled: bool = False
    # When disabled, use process_unprocessed_notebook_documents() polling fallback
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

            parts = v_clean.split(",")
            origins = []
            for part in parts:
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

    polar_api_key: str = ""
    polar_webhook_secret: str = ""
    polar_environment: str = "sandbox"
    polar_organization_id: str = ""
    polar_product_id: str = ""
    polar_llm_tokens_meter_id: str = ""
    polar_success_url: str = "http://localhost:5173/settings/billing?checkout=success"
    polar_usage_emit_interval_seconds: int = 60
    polar_usage_emit_batch_size: int = 100
    polar_usage_emit_max_retries: int = 5
    free_tier_llm_tokens_allowance: int = 50_000

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
