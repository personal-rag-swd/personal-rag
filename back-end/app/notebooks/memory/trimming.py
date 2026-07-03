"""Context-window trimming policy applied before each agent run.

Keeps all system prompts plus the most recent conversational turns, so long
notebooks don't blow the model's context while system instructions survive.
"""

from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    RetryPromptPart,
    SystemPromptPart,
    ToolReturnPart,
    UserPromptPart,
)

_RECENT_MESSAGE_LIMIT = 15


async def keep_recent_messages(messages: list[ModelMessage]) -> list[ModelMessage]:
    system_prompts = []
    other_messages = []
    for msg in messages:
        is_system = False
        if isinstance(msg, ModelRequest):
            has_system_part = any(
                isinstance(part, SystemPromptPart) for part in msg.parts
            )
            has_conversational_part = any(
                isinstance(part, (UserPromptPart, ToolReturnPart, RetryPromptPart))
                for part in msg.parts
            )
            if has_system_part or (msg.instructions and not has_conversational_part):
                is_system = True
        if is_system:
            system_prompts.append(msg)
        else:
            other_messages.append(msg)

    recent_others = other_messages[-_RECENT_MESSAGE_LIMIT:]
    # The slice can land between a tool call and its return, leaving the window
    # starting with an orphaned ToolReturnPart — which chat providers reject.
    # Drop leading tool-return requests until the window starts on a clean turn.
    while recent_others and _is_tool_return_request(recent_others[0]):
        recent_others.pop(0)

    keep_set = {id(msg) for msg in system_prompts} | {id(msg) for msg in recent_others}
    return [msg for msg in messages if id(msg) in keep_set]


def _is_tool_return_request(message: ModelMessage) -> bool:
    return isinstance(message, ModelRequest) and any(
        isinstance(part, ToolReturnPart) for part in message.parts
    )
