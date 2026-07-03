"""Notebook chat-memory package.

Split by responsibility — persistence, context-window trimming, AG-UI request
parsing, and transcript rendering — while preserving the historical
``app.notebooks.memory`` import surface.
"""

from app.notebooks.memory.agui import (
    build_user_message_from_agui_payload,
    extract_scoped_document_ids,
)
from app.notebooks.memory.persistence import (
    append_notebook_chat_history,
    load_notebook_chat_history,
)
from app.notebooks.memory.transcript import extract_notebook_chat_transcript
from app.notebooks.memory.trimming import keep_recent_messages

__all__ = [
    "append_notebook_chat_history",
    "build_user_message_from_agui_payload",
    "extract_notebook_chat_transcript",
    "extract_scoped_document_ids",
    "keep_recent_messages",
    "load_notebook_chat_history",
]
