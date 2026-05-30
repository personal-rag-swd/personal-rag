from __future__ import annotations

from app.notebooks.tools.chunking.base import ChunkingRequest, split_text


def chunk_text(request: ChunkingRequest):
    extracted_text = request.content.decode("utf-8", errors="ignore")
    return split_text(
        extracted_text,
        source=request.source,
        document_id=request.document_id,
    )
