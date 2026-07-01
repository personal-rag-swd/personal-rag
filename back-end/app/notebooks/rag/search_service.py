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
                "similarity": "cosine",
                "filter": search_filter,
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
        if chunk.metadata.get("chunk_type") == "image":
            chunk.chunk_type = "image"

    return chunks
