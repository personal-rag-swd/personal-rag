import logging
from urllib.parse import urlparse
from uuid import UUID

from bson import Binary
from pydantic import BaseModel

from app.core.config import Settings
from app.core.s3 import generate_presigned_get_url, presign_endpoint_url
from app.notebooks.agent.query_rewrite_agent import rewrite_query_text
from app.notebooks.models import Notebook, NotebookDocument, NotebookDocumentChunk
from app.users.models import User

# Hosts a remote LLM provider almost certainly cannot reach when handed an
# image URL; used to warn once during retrieval.
_INTERNAL_PRESIGN_HOSTS = {"localhost", "127.0.0.1", "minio"}
_presign_endpoint_warned: list[bool] = [False]


def _warn_if_unreachable_presign_endpoint(settings: Settings) -> None:
    """Warn once if image URLs are signed against an internally-only host."""
    if _presign_endpoint_warned[0]:
        return
    host = urlparse(presign_endpoint_url(settings) or "").hostname or ""
    if host in _INTERNAL_PRESIGN_HOSTS:
        _presign_endpoint_warned[0] = True
        logger.warning(
            "Image presigned URLs are signed against %r, which a remote LLM "
            "provider likely cannot reach. Set S3_PUBLIC_ENDPOINT_URL to a "
            "publicly reachable host for image-grounded chat to work.",
            host,
        )


class RetrievedChunk(BaseModel):
    document_id: UUID
    filename: str
    chunk_index: int
    content: str
    metadata: dict[str, object]
    chunk_type: str = "text"
    image_presigned_url: str | None = None


logger = logging.getLogger(__name__)


async def search_notebook_chunks(
    *,
    notebook: Notebook,
    current_user: User,
    query: str,
    settings: Settings,
    top_k: int = 6,
) -> list[RetrievedChunk]:
    query = rewrite_query_text(query, settings)

    pipeline = [
        {
            "$vectorSearch": {
                "index": "notebook_chunks_vector_index",
                "path": "content",
                "query": query,
                "numCandidates": top_k * 10,
                "limit": top_k,
                "similarity": "cosine",
                "filter": {
                    "notebook_id": Binary.from_uuid(notebook.id),
                    "user_id": Binary.from_uuid(current_user.id),
                },
            }
        },
    ]

    results = await NotebookDocumentChunk.aggregate(pipeline).to_list()

    # Raw aggregate rows carry document_id as a BSON value; RetrievedChunk's
    # ``UUID`` field coerces it so the downstream lookup uses real UUIDs.
    chunks = [
        RetrievedChunk(
            document_id=row["document_id"],
            filename="",
            chunk_index=row["chunk_index"],
            content=row["content"],
            metadata=row.get("chunk_metadata", {}),
        )
        for row in results
    ]

    doc_ids = {chunk.document_id for chunk in chunks}
    documents = await NotebookDocument.find({"_id": {"$in": list(doc_ids)}}).to_list()
    filename_by_id = {doc.id: doc.filename for doc in documents}

    for chunk in chunks:
        chunk.filename = filename_by_id.get(chunk.document_id, "unknown")
        if chunk.metadata.get("chunk_type") != "image":
            continue
        chunk.chunk_type = "image"
        s3_key = chunk.metadata.get("s3_key")
        s3_bucket = chunk.metadata.get("s3_bucket")
        if not (s3_key and s3_bucket):
            continue
        _warn_if_unreachable_presign_endpoint(settings)
        try:
            chunk.image_presigned_url = generate_presigned_get_url(
                settings, bucket=str(s3_bucket), key=str(s3_key)
            )
        except Exception:
            logger.warning(
                "Failed to generate presigned URL for image chunk %s",
                chunk.chunk_index,
            )

    return chunks
