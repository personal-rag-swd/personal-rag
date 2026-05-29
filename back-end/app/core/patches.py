import logging
from collections.abc import AsyncIterator

logger = logging.getLogger("app.patches")

try:
    from pydantic_ai.ui.ag_ui import AGUIEventStream
    from pydantic_ai.messages import TextPart, TextPartDelta
    from ag_ui.core import TextMessageStartEvent, TextMessageContentEvent, TextMessageEndEvent, BaseEvent
    _AGUI_PATCH_AVAILABLE = True
except ImportError:
    _AGUI_PATCH_AVAILABLE = False


def patch_agui_event_stream() -> None:
    """Patch AGUIEventStream to avoid 'No active text message found' protocol violations."""
    if not _AGUI_PATCH_AVAILABLE:
        return
    try:
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

        logger.info("Successfully patched AGUIEventStream text message start/end lifecycle.")
    except Exception as e:
        logger.error(f"Failed to patch AGUIEventStream: {e}")
