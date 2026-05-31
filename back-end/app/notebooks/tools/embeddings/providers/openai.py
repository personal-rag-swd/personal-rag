from __future__ import annotations

from pydantic_ai import Embedder
from pydantic_ai.embeddings import EmbeddingSettings
from pydantic_ai.embeddings.openai import OpenAIEmbeddingModel
from pydantic_ai.providers.openai import OpenAIProvider

from app.notebooks.tools.embeddings.base import PydanticAIEmbeddingAdapter


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

        provider = OpenAIProvider(api_key=api_key, base_url=base_url)
        embedding_model = OpenAIEmbeddingModel(
            model_name=model,
            provider=provider,
        )

        settings = None
        if output_dimensionality and output_dimensionality > 0:
            settings = EmbeddingSettings(dimensions=output_dimensionality)

        embedder = Embedder(embedding_model, settings=settings)
        super().__init__(embedder)
