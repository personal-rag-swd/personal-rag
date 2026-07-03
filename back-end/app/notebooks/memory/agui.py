"""Parsing of inbound AG-UI chat request bodies.

The chat route hands raw AG-UI JSON here to recover the latest user turn and
the optional document scope, keeping request-shape knowledge out of the router.
"""

from pydantic_ai.messages import ModelRequest, UserPromptPart


def build_user_message_from_agui_payload(
    payload: object,
) -> ModelRequest | None:
    """Extract the latest user turn from an AG-UI chat request body.

    Args:
        payload: The raw AG-UI request body, expected to be a dict with a
            ``messages`` list.

    Returns:
        A ``ModelRequest`` containing the latest user text, or ``None`` when
        no user text is present (e.g. an empty ``messages`` array).
    """
    if not isinstance(payload, dict):
        return None
    messages = payload.get("messages")
    if not isinstance(messages, list):
        return None

    for message in reversed(messages):
        if not isinstance(message, dict) or message.get("role") != "user":
            continue
        content = message.get("content")
        text = ""
        if isinstance(content, str):
            text = content
        elif isinstance(content, list):
            text = "".join(
                part.get("text", "")
                for part in content
                if isinstance(part, dict) and part.get("type") == "text"
            )
        if text.strip():
            return ModelRequest(parts=[UserPromptPart(content=text)])
        return None
    return None


def extract_scoped_document_ids(payload: object) -> list[object]:
    """Extract the optional document-scope ids from an AG-UI request body.

    The frontend sends the selected document ids under
    ``forwardedProps.documentIds`` to scope chat retrieval to a subset of
    sources. Returns an empty list when no scope is present; the ids are
    returned raw (unvalidated) for the service layer to resolve.
    """
    if not isinstance(payload, dict):
        return []
    forwarded_props = payload.get("forwardedProps")
    if not isinstance(forwarded_props, dict):
        return []
    raw_document_ids = forwarded_props.get("documentIds")
    if not isinstance(raw_document_ids, list):
        return []
    return raw_document_ids
