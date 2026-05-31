from app.core.config import Settings
from app.notebooks.agent.factory import chat_provider_is_configured, _build_chat_model
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.models.openai import OpenAIChatModel


def test_build_chat_model_openrouter(monkeypatch) -> None:
    settings = Settings(chat_provider="openrouter", chat_api_key="key")
    model = _build_chat_model(settings)
    assert isinstance(model, OpenAIChatModel)


def test_build_chat_model_openai_compatible(monkeypatch) -> None:
    settings = Settings(chat_provider="openai_compatible", chat_api_key="key")
    model = _build_chat_model(settings)
    assert isinstance(model, OpenAIChatModel)


def test_build_chat_model_gemini(monkeypatch) -> None:
    settings = Settings(chat_provider="gemini", chat_api_key="key")
    model = _build_chat_model(settings)
    assert isinstance(model, GoogleModel)


def test_build_chat_model_unsupported() -> None:
    settings = Settings(chat_provider="other", chat_api_key="key")
    try:
        _build_chat_model(settings)
        assert False, "Expected ValueError"
    except ValueError as exc:
        assert "openai_compatible" in str(exc)


def test_chat_provider_is_configured(monkeypatch) -> None:
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
