from app.notebooks.agent.base import ChatModelProvider
from app.notebooks.agent.factory import (
    chat_provider_is_configured,
    get_notebook_chat_agent,
    resolve_chat_provider,
)
from app.notebooks.agent.providers import GeminiChatProvider, OpenRouterChatProvider
from app.notebooks.agent.report import (
    generate_briefing_doc,
    generate_blog_post,
    generate_custom_report,
    generate_study_guide,
    generate_mindmap,
)

__all__ = [
    "ChatModelProvider",
    "GeminiChatProvider",
    "OpenRouterChatProvider",
    "chat_provider_is_configured",
    "get_notebook_chat_agent",
    "resolve_chat_provider",
    "generate_briefing_doc",
    "generate_blog_post",
    "generate_custom_report",
    "generate_study_guide",
    "generate_mindmap",
]
