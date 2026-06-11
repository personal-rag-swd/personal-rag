from __future__ import annotations

import asyncio
import json
import logging
import urllib.parse
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

import aio_pika
from aio_pika import ExchangeType, IncomingMessage
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, select

from app.core.config import Settings
from app.core.database import engine
from app.notebooks.models import NotebookDocument
from app.notebooks.tools.ingestion import (
    TransientIngestionError,
    claim_document_for_ingestion,
    fail_stale_pending_documents,
    fail_stale_processing_documents,
    ingest_document_by_id,
)

logger = logging.getLogger(__name__)


class MinioEventBucket(BaseModel):
    name: str | None = None


class MinioEventObject(BaseModel):
    key: str | None = None
    size: int | None = None


class MinioEventS3(BaseModel):
    bucket: MinioEventBucket | None = None
    object: MinioEventObject | None = None


class MinioEventRecord(BaseModel):
    eventName: str | None = None
    s3: MinioEventS3 | None = None


class MinioEventPayload(BaseModel):
    EventName: str | None = None
    Key: str | None = None
    Records: list[MinioEventRecord] | None = None
    bucket: str | None = None
    eventName: str | None = None
    key: str | None = None
    size: int | None = None

    model_config = {"extra": "ignore"}


@dataclass(frozen=True)
class ParsedMinioEvent:
    bucket: str
    key: str
    size: int | None


class MessageOutcome(StrEnum):
    ACK = "ack"
    RETRY = "retry"


def _is_object_created_event(event_name: str | None) -> bool:
    if not event_name:
        return False
    lowered = event_name.lower()
    return "objectcreated" in lowered or "object_created" in lowered


def _normalize_object_key(bucket: str, key: str) -> str:
    normalized_key = urllib.parse.unquote_plus(key)
    if normalized_key.startswith(f"{bucket}/"):
        normalized_key = normalized_key[len(bucket) + 1 :]
    if normalized_key != key:
        logger.debug(
            "Normalized MinIO object key bucket=%s raw_key=%s normalized_key=%s",
            bucket,
            key,
            normalized_key,
        )
    return normalized_key


def parse_minio_object_created_events(
    payload: dict[str, Any],
) -> list[ParsedMinioEvent]:
    parsed = MinioEventPayload.model_validate(payload)
    events: list[ParsedMinioEvent] = []

    if parsed.Records:
        for record in parsed.Records:
            if not _is_object_created_event(record.eventName):
                continue
            bucket = record.s3.bucket.name if record.s3 and record.s3.bucket else None
            key = record.s3.object.key if record.s3 and record.s3.object else None
            size = record.s3.object.size if record.s3 and record.s3.object else None
            if bucket and key:
                events.append(
                    ParsedMinioEvent(
                        bucket=bucket, key=_normalize_object_key(bucket, key), size=size
                    )
                )
        return events

    if (
        _is_object_created_event(parsed.EventName or parsed.eventName)
        and parsed.bucket
        and parsed.Key
    ):
        events.append(
            ParsedMinioEvent(
                bucket=parsed.bucket,
                key=_normalize_object_key(parsed.bucket, parsed.Key),
                size=parsed.size,
            )
        )
    elif _is_object_created_event(parsed.eventName) and parsed.bucket and parsed.key:
        events.append(
            ParsedMinioEvent(
                bucket=parsed.bucket,
                key=_normalize_object_key(parsed.bucket, parsed.key),
                size=parsed.size,
            )
        )
    return events


def _build_queue_arguments(settings: Settings) -> dict[str, Any] | None:
    arguments: dict[str, Any] = {}
    if settings.rabbitmq_dead_letter_exchange_name:
        arguments["x-dead-letter-exchange"] = (
            settings.rabbitmq_dead_letter_exchange_name
        )
        arguments["x-dead-letter-routing-key"] = (
            settings.rabbitmq_dead_letter_routing_key
        )
    return arguments or None


def recover_stale_notebook_documents(settings: Settings) -> dict[str, int]:
    with Session(engine) as session:
        return {
            "recovered_processing": fail_stale_processing_documents(session, settings),
            "recovered_pending": fail_stale_pending_documents(session, settings),
        }


def _find_document_by_storage_key(
    session: Session, *, bucket: str, key: str
) -> NotebookDocument | None:
    return session.exec(
        select(NotebookDocument).where(
            NotebookDocument.s3_bucket == bucket,
            NotebookDocument.s3_key == key,
        )
    ).first()


def process_minio_notification_payload(
    payload: dict[str, Any], settings: Settings
) -> MessageOutcome:
    events = parse_minio_object_created_events(payload)
    if not events:
        logger.debug("RabbitMQ notification had no object-created events")
        return MessageOutcome.ACK
    logger.debug("RabbitMQ notification parsed %s object-created event(s)", len(events))

    with Session(engine) as session:
        for event in events:
            logger.debug(
                "Processing object-created event bucket=%s key=%s size=%s",
                event.bucket,
                event.key,
                event.size,
            )
            document = _find_document_by_storage_key(
                session, bucket=event.bucket, key=event.key
            )
            if document is None:
                logger.info(
                    "Skipping MinIO event for unknown object %s/%s",
                    event.bucket,
                    event.key,
                )
                continue

            claimed = claim_document_for_ingestion(
                session, document.id, size=event.size
            )
            if claimed is None:
                logger.info(
                    "Skipping MinIO event for already-claimed document %s", document.id
                )
                continue
            logger.debug("Claimed notebook document %s for ingestion", claimed.id)

            try:
                ingest_document_by_id(
                    session,
                    claimed.id,
                    settings,
                    require_processing_status=True,
                )
                logger.debug("Notebook document ingestion completed for %s", claimed.id)
            except TransientIngestionError:
                logger.debug(
                    "Notebook document ingestion will retry for %s", claimed.id
                )
                return MessageOutcome.RETRY
            except SQLAlchemyError:
                logger.exception(
                    "Database failure while processing document %s", claimed.id
                )
                return MessageOutcome.RETRY

    return MessageOutcome.ACK


def process_minio_notification_message(
    body: bytes, settings: Settings
) -> MessageOutcome:
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        logger.warning("Skipping non-JSON RabbitMQ message body")
        return MessageOutcome.ACK
    logger.debug("Received RabbitMQ message body with %s byte(s)", len(body))
    return process_minio_notification_payload(payload, settings)


async def _declare_topology(
    channel: aio_pika.abc.AbstractChannel, settings: Settings
) -> aio_pika.abc.AbstractQueue:
    exchange = await channel.declare_exchange(
        settings.rabbitmq_exchange_name,
        ExchangeType(settings.rabbitmq_exchange_type),
        durable=True,
    )
    if settings.rabbitmq_dead_letter_exchange_name:
        dead_letter_exchange = await channel.declare_exchange(
            settings.rabbitmq_dead_letter_exchange_name,
            ExchangeType.DIRECT,
            durable=True,
        )
        if settings.rabbitmq_dead_letter_queue_name:
            dead_letter_queue = await channel.declare_queue(
                settings.rabbitmq_dead_letter_queue_name,
                durable=True,
            )
            await dead_letter_queue.bind(
                dead_letter_exchange,
                routing_key=settings.rabbitmq_dead_letter_routing_key,
            )

    queue = await channel.declare_queue(
        settings.rabbitmq_queue_name,
        durable=True,
        arguments=_build_queue_arguments(settings),
    )
    await queue.bind(exchange, routing_key=settings.rabbitmq_routing_key)
    return queue


async def _handle_message(message: IncomingMessage, settings: Settings) -> None:
    logger.debug(
        "Handling RabbitMQ delivery_tag=%s routing_key=%s",
        message.delivery_tag,
        message.routing_key,
    )
    outcome = await asyncio.to_thread(
        process_minio_notification_message, message.body, settings
    )
    if outcome is MessageOutcome.RETRY:
        logger.debug("Requeueing RabbitMQ delivery_tag=%s", message.delivery_tag)
        await message.nack(requeue=True)
    else:
        logger.debug("Acknowledging RabbitMQ delivery_tag=%s", message.delivery_tag)
        await message.ack()


async def run_notebook_document_consumer(settings: Settings) -> None:
    logger.info("Notebook document RabbitMQ consumer started")
    while True:
        try:
            logger.debug(
                "Connecting notebook ingestion consumer to RabbitMQ at %s",
                settings.rabbitmq_url,
            )
            connection = await aio_pika.connect_robust(settings.rabbitmq_url)
            async with connection:
                channel = await connection.channel()
                await channel.set_qos(prefetch_count=settings.rabbitmq_prefetch_count)
                queue = await _declare_topology(channel, settings)
                logger.debug(
                    "RabbitMQ consumer ready queue=%s exchange=%s routing_key=%s prefetch=%s",
                    settings.rabbitmq_queue_name,
                    settings.rabbitmq_exchange_name,
                    settings.rabbitmq_routing_key,
                    settings.rabbitmq_prefetch_count,
                )
                stale_stats = await asyncio.to_thread(
                    recover_stale_notebook_documents, settings
                )
                if (
                    stale_stats["recovered_processing"]
                    or stale_stats["recovered_pending"]
                ):
                    logger.info(
                        "Recovered stale notebook documents before consume loop: %s",
                        stale_stats,
                    )

                async with queue.iterator() as queue_iter:
                    async for message in queue_iter:
                        try:
                            await _handle_message(message, settings)
                        except asyncio.CancelledError:
                            await message.nack(requeue=True)
                            logger.info("Notebook document RabbitMQ consumer stopped")
                            raise
                        except Exception:
                            logger.exception(
                                "RabbitMQ message handling failed unexpectedly"
                            )
                            await message.nack(requeue=True)
        except asyncio.CancelledError:
            logger.info("Notebook document RabbitMQ consumer stopped")
            raise
        except Exception:
            logger.exception("RabbitMQ consumer loop failed; retrying")
            await asyncio.sleep(settings.rabbitmq_reconnect_delay_seconds)
