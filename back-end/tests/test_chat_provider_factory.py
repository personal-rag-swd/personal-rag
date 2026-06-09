import pytest

from app.core.config import Settings
from app.notebooks.agent.factory import (
    GeminiChatProvider,
    OpenAICompatibleChatProvider,
    OpenRouterChatProvider,
    resolve_chat_provider,
)


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
    with pytest.raises(ValueError, match="openai_compatible"):
        resolve_chat_provider()


def test_chat_provider_is_configured(monkeypatch) -> None:
    from app.notebooks.agent.factory import chat_provider_is_configured

    # Gemini with API key
    monkeypatch.setattr(
        "app.notebooks.agent.factory.get_settings",
        lambda: Settings(chat_provider="gemini", chat_api_key="key"),
    )
    assert chat_provider_is_configured() is True

    # Gemini without API key
    monkeypatch.setattr(
        "app.notebooks.agent.factory.get_settings",
        lambda: Settings(chat_provider="gemini", chat_api_key=""),
    )
    assert chat_provider_is_configured() is False

    # OpenRouter with API key
    monkeypatch.setattr(
        "app.notebooks.agent.factory.get_settings",
        lambda: Settings(chat_provider="openrouter", chat_api_key="key"),
    )
    assert chat_provider_is_configured() is True

    # OpenRouter without API key
    monkeypatch.setattr(
        "app.notebooks.agent.factory.get_settings",
        lambda: Settings(chat_provider="openrouter", chat_api_key=""),
    )
    assert chat_provider_is_configured() is False

    # OpenAI Compatible with API key
    monkeypatch.setattr(
        "app.notebooks.agent.factory.get_settings",
        lambda: Settings(chat_provider="openai_compatible", chat_api_key="key"),
    )
    assert chat_provider_is_configured() is True

    # OpenAI Compatible without API key
    monkeypatch.setattr(
        "app.notebooks.agent.factory.get_settings",
        lambda: Settings(chat_provider="openai_compatible", chat_api_key=""),
    )
    assert chat_provider_is_configured() is False

    # Unsupported provider
    monkeypatch.setattr(
        "app.notebooks.agent.factory.get_settings",
        lambda: Settings(chat_provider="unsupported", chat_api_key="key"),
    )
    assert chat_provider_is_configured() is False
