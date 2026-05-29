from __future__ import annotations

import io

from docx import Document as DocxDocument

from app.notebooks.tools.chunking.base import ChunkingRequest, split_text


def chunk_docx(request: ChunkingRequest):
    doc = DocxDocument(io.BytesIO(request.content))
    extracted_text = "\n".join(paragraph.text for paragraph in doc.paragraphs)
    return split_text(
        extracted_text,
        source=request.source,
        document_id=request.document_id,
    )
