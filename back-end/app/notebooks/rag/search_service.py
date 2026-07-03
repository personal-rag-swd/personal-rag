import logging
from uuid import UUID

from bson import Binary
from pydantic import BaseModel

from app.core.config import Settings
from app.core.embedding_provider import embed_text
from app.notebooks.models import Notebook, NotebookDocument, NotebookDocumentChunk
from app.notebooks.rag.query_rewrite_agent import rewrite_query_text
from app.users.models import User


class RetrievedChunk(BaseModel):
    document_id: UUID
    filename: str
    chunk_index: int
    content: str
    metadata: dict[str, object]
    chunk_type: str = "text"


logger = logging.getLogger(__name__)


async def search_notebook_chunks(
    *,
    notebook: Notebook,
    current_user: User,
    query: str,
    settings: Settings,
    top_k: int = 6,
    document_ids: list[UUID] | None = None,
) -> list[RetrievedChunk]:
    # Guard degenerate queries here so every caller is covered: an empty query
    # would otherwise burn an LLM rewrite call and an embedding call for
    # meaningless results (and some embedding providers reject empty input).
    query = query.strip()
    if not query:
        return []

    query = await rewrite_query_text(query, settings)
    query_vector = await embed_text(query)

    search_filter: dict[str, object] = {
        "notebook_id": Binary.from_uuid(notebook.id),
        "user_id": Binary.from_uuid(current_user.id),
    }
    if document_ids:
        search_filter["document_id"] = {
            "$in": [Binary.from_uuid(doc_id) for doc_id in document_ids]
        }

    pipeline = [
        {
            "$vectorSearch": {
                "index": "notebook_chunks_vector_index",
                "path": "embedding",
                "queryVector": query_vector,
                "numCandidates": top_k * 10,
                "limit": top_k,
                "filter": search_filter,
            }
        },
    ]

    results = await NotebookDocumentChunk.aggregate(pipeline).to_list()
    if not results:
        return []

    doc_ids = {_as_uuid(row["document_id"]) for row in results}
    documents = await NotebookDocument.find({"_id": {"$in": list(doc_ids)}}).to_list()
    filename_by_id = {doc.id: doc.filename for doc in documents}

    chunks = []
    for row in results:
        document_id = _as_uuid(row["document_id"])
        metadata = row.get("chunk_metadata", {})
        chunks.append(
            RetrievedChunk(
                document_id=document_id,
                filename=filename_by_id.get(document_id, "unknown"),
                chunk_index=row["chunk_index"],
                content=row["content"],
                metadata=metadata,
                chunk_type="image" if metadata.get("chunk_type") == "image" else "text",
            )
        )
    return chunks


def _as_uuid(value: object) -> UUID:
    """Coerce a raw aggregate row's BSON document_id to a real UUID."""
    if isinstance(value, Binary):
        return value.as_uuid()
    if isinstance(value, UUID):
        return value
    return UUID(str(value))
