from app.core.config import Settings
from app.notebooks.agent.factory import resolve_chat_provider
from app.notebooks.agent.providers import GeminiChatProvider, OpenAICompatibleChatProvider, OpenRouterChatProvider


def test_resolve_chat_provider_openrouter(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.notebooks.agent.factory.get_settings",
        lambda: Settings(chat_provider="openrouter"),
    )
    assert isinstance(resolve_chat_provider(), OpenRouterChatProvider)


def test_resolve_chat_provider_openai_compatible(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.notebooks.agent.factory.get_settings",
        lambda: Settings(chat_provider="openai_compatible"),
    )
    assert isinstance(resolve_chat_provider(), OpenAICompatibleChatProvider)


def test_resolve_chat_provider_gemini(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.notebooks.agent.factory.get_settings",
        lambda: Settings(chat_provider="gemini"),
    )
    assert isinstance(resolve_chat_provider(), GeminiChatProvider)


def test_resolve_chat_provider_unsupported(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.notebooks.agent.factory.get_settings",
        lambda: Settings(chat_provider="other"),
    )
    try:
        resolve_chat_provider()
        assert False, "Expected ValueError"
    except ValueError as exc:
        assert "openai_compatible" in str(exc)
