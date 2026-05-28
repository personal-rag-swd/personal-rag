import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from scalar_fastapi import get_scalar_api_reference

from app.auth.router import router as auth_router
from app.core.config import get_settings
from app.file.router import router as file_router
from app.notebooks.router import router as notebooks_router
from app.users.router import router as users_router

# Patch AGUIEventStream to avoid "No active text message found" protocol violations.
def _patch_agui_event_stream():
    try:
        from pydantic_ai.ui.ag_ui import AGUIEventStream
        from pydantic_ai.messages import TextPart, TextPartDelta
        from ag_ui.core import TextMessageStartEvent, TextMessageContentEvent, TextMessageEndEvent, BaseEvent
        from collections.abc import AsyncIterator

        async def patched_handle_text_start(
            self: AGUIEventStream, part: TextPart, follows_text: bool = False
        ) -> AsyncIterator[BaseEvent]:
            if not hasattr(self, "_active_message_ids"):
                self._active_message_ids = set()

            if follows_text and self.message_id in self._active_message_ids:
                message_id = self.message_id
            else:
                message_id = self.new_message_id()
                self._active_message_ids.add(message_id)
                yield TextMessageStartEvent(message_id=message_id)

            if part.content:
                yield TextMessageContentEvent(message_id=message_id, delta=part.content)

        async def patched_handle_text_delta(
            self: AGUIEventStream, delta: TextPartDelta
        ) -> AsyncIterator[BaseEvent]:
            if not hasattr(self, "_active_message_ids"):
                self._active_message_ids = set()

            if self.message_id not in self._active_message_ids:
                self._active_message_ids.add(self.message_id)
                yield TextMessageStartEvent(message_id=self.message_id)

            if delta.content_delta:
                yield TextMessageContentEvent(message_id=self.message_id, delta=delta.content_delta)

        async def patched_handle_text_end(
            self: AGUIEventStream, part: TextPart, followed_by_text: bool = False
        ) -> AsyncIterator[BaseEvent]:
            if not followed_by_text:
                if hasattr(self, "_active_message_ids") and self.message_id in self._active_message_ids:
                    self._active_message_ids.remove(self.message_id)
                yield TextMessageEndEvent(message_id=self.message_id)

        AGUIEventStream.handle_text_start = patched_handle_text_start
        AGUIEventStream.handle_text_delta = patched_handle_text_delta
        AGUIEventStream.handle_text_end = patched_handle_text_end

        logging.getLogger("uvicorn").info("Successfully patched AGUIEventStream text message start/end lifecycle.")
    except Exception as e:
        logging.getLogger("uvicorn").error(f"Failed to patch AGUIEventStream: {e}")

_patch_agui_event_stream()

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s:     %(name)s - %(message)s",
)

app = FastAPI(title="Personal RAG", docs_url=None, redoc_url=None)
API_V1_PREFIX = "/api/v1"


app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/docs", include_in_schema=False)
async def scalar_html():
    return get_scalar_api_reference(
        openapi_url=app.openapi_url,
        title=app.title,
    )


@app.get("/ping")
async def ping():
    return {"ping": "pong"}

app.include_router(auth_router, prefix=API_V1_PREFIX)
app.include_router(users_router, prefix=API_V1_PREFIX)
app.include_router(file_router, prefix=API_V1_PREFIX)
app.include_router(notebooks_router, prefix=API_V1_PREFIX)
