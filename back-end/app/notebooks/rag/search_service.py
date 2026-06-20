import logging
from uuid import UUID

from bson import Binary
from pydantic import BaseModel
from pydantic_ai import Agent

from app.core.config import Settings
from app.core.llm_provider import (
    chat_provider_is_configured,
    resolve_chat_provider,
)
from app.notebooks.models import Notebook, NotebookDocument, NotebookDocumentChunk
from app.users.models import User


class RetrievedChunk(BaseModel):
    document_id: UUID
    filename: str
    chunk_index: int
    content: str
    metadata: dict[str, object]


logger = logging.getLogger(__name__)


query_rewrite_agent = Agent(
    instructions=(
        "You are an expert search query optimizer for a RAG (Retrieval-Augmented Generation) system. "
        "Your role is to rewrite the user's input search query to improve vector search retrieval precision. "
        "Apply the following rules:\n"
        "1. Strip out conversational filler, polite phrasing, and meta-questions (e.g., 'please look up', 'can you find information about', 'do we have documents on').\n"
        "2. Focus on the core semantic meaning and search keywords.\n"
        "3. Rephrase the query into a clear, direct, and search-optimized statement or set of search terms that is most likely to match the database text.\n"
        "4. Output ONLY the final rewritten search query. Do not wrap it in quotes, do not add introductory text, and do not provide any explanation."
    ),
)


def rewrite_query_text(query: str, settings: Settings) -> str:
    if not settings.enable_query_rewrite or not chat_provider_is_configured():
        return query

    try:
        model = resolve_chat_provider()
        result = query_rewrite_agent.run_sync(query, model=model)
        rewritten = result.output.strip()
        if rewritten:
            logger.info("Rewrote RAG query: %r -> %r", query, rewritten)
            return rewritten
    except Exception as e:
        logger.warning("Failed to rewrite query %r: %s", query, str(e))
    return query


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
    filename_by_id = {document.id: document.filename for document in documents}

    for chunk in chunks:
        chunk.filename = filename_by_id.get(chunk.document_id, "unknown")

    return chunks
