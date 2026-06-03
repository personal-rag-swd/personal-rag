from __future__ import annotations

from pydantic_ai import Embedder
from pydantic_ai.embeddings.google import GoogleEmbeddingModel, GoogleEmbeddingSettings
from pydantic_ai.providers.google import GoogleProvider

from app.notebooks.tools.embeddings.base import PydanticAIEmbeddingAdapter


class GeminiEmbeddingAdapter(PydanticAIEmbeddingAdapter):
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        output_dimensionality: int | None = None,
    ) -> None:
        self.model = model
        self.output_dimensionality = output_dimensionality
        self.provider_url = "https://generativelanguage.googleapis.com"

        provider = GoogleProvider(api_key=api_key)
        embedding_model = GoogleEmbeddingModel(
            model_name=model,
            provider=provider,
        )
        settings = None
        if output_dimensionality and output_dimensionality > 0:
            settings = GoogleEmbeddingSettings(dimensions=output_dimensionality)

        embedder = Embedder(embedding_model, settings=settings)
        super().__init__(embedder)
