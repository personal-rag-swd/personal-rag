from __future__ import annotations

from pydantic_ai import Embedder
from pydantic_ai.embeddings import EmbeddingSettings
from pydantic_ai.embeddings.openai import OpenAIEmbeddingModel
from pydantic_ai.providers.openai import OpenAIProvider

from app.notebooks.tools.embeddings.base import PydanticAIEmbeddingAdapter


from typing import Any

class OpenRouterEmbeddingModel(OpenAIEmbeddingModel):
    def __init__(
        self,
        model_name: str,
        *,
        provider: Any = "openai",
        settings: EmbeddingSettings | None = None,
        check_embedding_ctx_length: bool = True,
        model_kwargs: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(model_name, provider=provider, settings=settings)
        self.check_embedding_ctx_length = check_embedding_ctx_length
        self.model_kwargs = model_kwargs or {}


class OpenAICompatibleEmbeddingAdapter(PydanticAIEmbeddingAdapter):
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str | None = None,
        output_dimensionality: int | None = None,
    ) -> None:
        self.model = model
        self.provider_url = base_url or "https://api.openai.com/v1"
        self.output_dimensionality = output_dimensionality

        provider = OpenAIProvider(api_key=api_key, base_url=base_url)

        is_openrouter = base_url is not None and "openrouter.ai" in base_url.lower()

        if is_openrouter:
            embedding_model = OpenRouterEmbeddingModel(
                model_name=model,
                provider=provider,
                check_embedding_ctx_length=False,
                model_kwargs={"encoding_format": "float"},
            )
        else:
            embedding_model = OpenAIEmbeddingModel(
                model_name=model,
                provider=provider,
            )

        settings = None
        extra_body = {}
        if is_openrouter:
            extra_body["encoding_format"] = "float"

        if output_dimensionality and output_dimensionality > 0:
            if extra_body:
                settings = EmbeddingSettings(dimensions=output_dimensionality, extra_body=extra_body)
            else:
                settings = EmbeddingSettings(dimensions=output_dimensionality)
        elif extra_body:
            settings = EmbeddingSettings(extra_body=extra_body)

        embedder = Embedder(embedding_model, settings=settings)
        super().__init__(embedder)
