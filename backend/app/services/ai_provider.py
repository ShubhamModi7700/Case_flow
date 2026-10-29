from __future__ import annotations

import os
from functools import lru_cache
from typing import Any, Protocol

from openai import OpenAI


class AIProvider(Protocol):
    """Provider boundary for all externally processed AI operations."""

    @property
    def name(self) -> str: ...

    def analysis_model(self) -> str: ...

    def embedding_model(self) -> str: ...

    def embedding_dimensions(self) -> int: ...

    def structured_parse(self, *, input: Any, text_format: Any, model: str | None = None) -> Any: ...

    def create_embeddings(self, texts: list[str]) -> list[list[float]]: ...


class OpenAIProvider:
    name = "openai"

    def __init__(self) -> None:
        enabled = os.getenv("AI_EXTERNAL_PROCESSING_ENABLED", "true").strip().casefold()
        if enabled not in {"1", "true", "yes", "on"}:
            raise RuntimeError("External AI processing is disabled by configuration.")

        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is not configured.")

        base_url = os.getenv("OPENAI_BASE_URL", "").strip() or None
        kwargs: dict[str, Any] = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        self._client = OpenAI(**kwargs)

    def analysis_model(self) -> str:
        model = os.getenv("OPENAI_ANALYSIS_MODEL", "").strip()
        if not model:
            raise RuntimeError("OPENAI_ANALYSIS_MODEL is not configured.")
        return model

    def embedding_model(self) -> str:
        model = os.getenv("OPENAI_EMBEDDING_MODEL", "").strip()
        if not model:
            raise RuntimeError("OPENAI_EMBEDDING_MODEL is not configured.")
        return model

    def embedding_dimensions(self) -> int:
        value = os.getenv("OPENAI_EMBEDDING_DIMENSIONS", "").strip()
        if not value:
            raise RuntimeError("OPENAI_EMBEDDING_DIMENSIONS is not configured.")
        return int(value)

    def structured_parse(self, *, input: Any, text_format: Any, model: str | None = None) -> Any:
        options: dict[str, Any] = {}
        # Optional: set OPENAI_REASONING_EFFORT to a value supported by the
        # configured model. Unset preserves the previous provider behavior.
        effort = os.getenv("OPENAI_REASONING_EFFORT", "").strip().lower()
        if effort:
            if effort not in {"minimal", "low", "medium", "high", "xhigh"}:
                raise ValueError("Invalid OPENAI_REASONING_EFFORT setting")
            options["reasoning"] = {"effort": effort}
        return self._client.responses.parse(
            model=model or self.analysis_model(),
            input=input,
            text_format=text_format,
            **options,
        )

    def create_embeddings(self, texts: list[str]) -> list[list[float]]:
        response = self._client.embeddings.create(
            model=self.embedding_model(),
            input=texts,
            encoding_format="float",
            dimensions=self.embedding_dimensions(),
        )
        vectors = [item.embedding for item in response.data]
        if len(vectors) != len(texts):
            raise RuntimeError("AI provider did not return one embedding per input text.")
        expected = self.embedding_dimensions()
        invalid = [len(vector) for vector in vectors if len(vector) != expected]
        if invalid:
            raise RuntimeError(
                f"Embedding dimension mismatch: expected {expected}, received {invalid[0]}."
            )
        return vectors


@lru_cache(maxsize=1)
def get_ai_provider() -> AIProvider:
    provider_name = os.getenv("AI_PROVIDER", "openai").strip().casefold()
    if provider_name == "openai":
        return OpenAIProvider()
    raise RuntimeError(f"Unsupported AI_PROVIDER: {provider_name or '<empty>'}")


def configured_provider_name() -> str:
    return os.getenv("AI_PROVIDER", "openai").strip().casefold() or "openai"
