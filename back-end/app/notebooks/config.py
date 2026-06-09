from __future__ import annotations

from dataclasses import dataclass

from app.core.config import Settings


@dataclass(frozen=True)
class NotebookChatSettings:
    chat_provider: str
    chat_api_key: str
    chat_provider_url: str
    chat_model: str
    notebook_retrieval_top_k: int


@dataclass(frozen=True)
class NotebookEmbeddingSettings:
    embedding_provider: str
    embedding_api_key: str
    embedding_provider_url: str
    embedding_model: str
    embedding_dimension: int


@dataclass(frozen=True)
class NotebookIngestionSettings:
    file_ingestion_processing_timeout_minutes: int


@dataclass(frozen=True)
class NotebookRabbitMQSettings:
    rabbitmq_url: str
    rabbitmq_exchange_name: str
    rabbitmq_exchange_type: str
    rabbitmq_routing_key: str
    rabbitmq_queue_name: str
    rabbitmq_dead_letter_exchange_name: str | None
    rabbitmq_dead_letter_queue_name: str | None
    rabbitmq_dead_letter_routing_key: str
    rabbitmq_prefetch_count: int
    rabbitmq_reconnect_delay_seconds: float


def get_notebook_chat_settings(settings: Settings) -> NotebookChatSettings:
    return NotebookChatSettings(
        chat_provider=settings.chat_provider,
        chat_api_key=settings.chat_api_key,
        chat_provider_url=settings.chat_provider_url,
        chat_model=settings.chat_model,
        notebook_retrieval_top_k=settings.notebook_retrieval_top_k,
    )


def get_notebook_embedding_settings(settings: Settings) -> NotebookEmbeddingSettings:
    return NotebookEmbeddingSettings(
        embedding_provider=settings.embedding_provider,
        embedding_api_key=settings.embedding_api_key,
        embedding_provider_url=settings.embedding_provider_url,
        embedding_model=settings.embedding_model,
        embedding_dimension=settings.embedding_dimension,
    )


def get_notebook_ingestion_settings(settings: Settings) -> NotebookIngestionSettings:
    return NotebookIngestionSettings(
        file_ingestion_processing_timeout_minutes=settings.file_ingestion_processing_timeout_minutes,
    )


def get_notebook_rabbitmq_settings(settings: Settings) -> NotebookRabbitMQSettings:
    return NotebookRabbitMQSettings(
        rabbitmq_url=settings.rabbitmq_url,
        rabbitmq_exchange_name=settings.rabbitmq_exchange_name,
        rabbitmq_exchange_type=settings.rabbitmq_exchange_type,
        rabbitmq_routing_key=settings.rabbitmq_routing_key,
        rabbitmq_queue_name=settings.rabbitmq_queue_name,
        rabbitmq_dead_letter_exchange_name=settings.rabbitmq_dead_letter_exchange_name,
        rabbitmq_dead_letter_queue_name=settings.rabbitmq_dead_letter_queue_name,
        rabbitmq_dead_letter_routing_key=settings.rabbitmq_dead_letter_routing_key,
        rabbitmq_prefetch_count=settings.rabbitmq_prefetch_count,
        rabbitmq_reconnect_delay_seconds=settings.rabbitmq_reconnect_delay_seconds,
    )
