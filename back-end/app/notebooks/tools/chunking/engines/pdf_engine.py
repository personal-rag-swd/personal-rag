from __future__ import annotations

import io

from pypdf import PdfReader

from app.notebooks.tools.chunking.base import ChunkingRequest, split_text


def chunk_pdf(request: ChunkingRequest):
    reader = PdfReader(io.BytesIO(request.content))
    extracted_text = "\n".join((page.extract_text() or "") for page in reader.pages)
    return split_text(
        extracted_text,
        source=request.source,
        document_id=request.document_id,
    )
