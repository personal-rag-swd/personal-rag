from __future__ import annotations

import asyncio
import json
import logging
import urllib.parse
from dataclasses import dataclass
from typing import Any

import aio_pika
from aio_pika import ExchangeType
from aio_pika.abc import AbstractIncomingMessage
from pydantic import BaseModel

from app.core.config import Settings
from app.notebooks.models import NotebookDocument
from app.notebooks.rag.ingestion_service import (
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

    # Flat payloads come in two casings ("EventName"/"Key" and "eventName"/"key").
    event_name = parsed.EventName or parsed.eventName
    key = parsed.Key or parsed.key
    if _is_object_created_event(event_name) and parsed.bucket and key:
        events.append(
            ParsedMinioEvent(
                bucket=parsed.bucket,
                key=_normalize_object_key(parsed.bucket, key),
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


async def recover_stale_notebook_documents(settings: Settings) -> dict[str, int]:
    return {
        "recovered_processing": await fail_stale_processing_documents(settings),
        "recovered_pending": await fail_stale_pending_documents(settings),
    }


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


async def _process_message(body: bytes, settings: Settings) -> None:
    """Process a raw RabbitMQ message body.

    Returns normally to ack. Raises to trigger nack + requeue.
    """
    try:
        payload = json.loads(body.decode("utf-8"))
    except UnicodeDecodeError, json.JSONDecodeError:
        logger.warning("Skipping non-JSON RabbitMQ message body")
        return

    events = parse_minio_object_created_events(payload)
    if not events:
        logger.debug("RabbitMQ notification had no object-created events")
        return

    for event in events:
        logger.info(
            "Processing object-created event: bucket=%s key=%s size=%s",
            event.bucket,
            event.key,
            event.size,
        )
        document = await NotebookDocument.find_one(
            {"s3_bucket": event.bucket, "s3_key": event.key}
        )
        if document is None:
            logger.info(
                "Skipping MinIO event for unknown object %s/%s", event.bucket, event.key
            )
            continue

        await ingest_document_by_id(document.id, settings, size=event.size)
        logger.info(
            "Ingestion handled for document %s (%s)", document.id, document.filename
        )


async def run_notebook_document_consumer(settings: Settings) -> None:
    logger.info("Notebook document RabbitMQ consumer starting")

    async def on_message(message: AbstractIncomingMessage) -> None:
        logger.info(
            "Received message delivery_tag=%s routing_key=%s",
            message.delivery_tag,
            message.routing_key,
        )
        async with message.process(requeue=True):
            await _process_message(message.body, settings)

    # Supervised loop: connect_robust only auto-reconnects AFTER a first
    # successful connect, so a startup/broker race on the initial connect would
    # otherwise kill this (fire-and-forget) task permanently. Retry with backoff.
    while True:
        try:
            connection = await aio_pika.connect_robust(settings.rabbitmq_url)
            async with connection:
                channel = await connection.channel()
                await channel.set_qos(prefetch_count=settings.rabbitmq_prefetch_count)
                queue = await _declare_topology(channel, settings)

                stale_stats = await recover_stale_notebook_documents(settings)
                if any(stale_stats.values()):
                    logger.info("Recovered stale notebook documents: %s", stale_stats)

                await queue.consume(on_message)
                logger.info(
                    "RabbitMQ consumer ready queue=%s exchange=%s routing_key=%s prefetch=%s",
                    settings.rabbitmq_queue_name,
                    settings.rabbitmq_exchange_name,
                    settings.rabbitmq_routing_key,
                    settings.rabbitmq_prefetch_count,
                )
                await asyncio.Future()  # run until cancelled or the connection drops
        except asyncio.CancelledError:
            logger.info("Notebook document RabbitMQ consumer stopped")
            raise
        except Exception:
            logger.exception(
                "RabbitMQ consumer loop failed; retrying in %ss",
                settings.rabbitmq_reconnect_delay_seconds,
            )
            await asyncio.sleep(settings.rabbitmq_reconnect_delay_seconds)
