import os
from functools import lru_cache

from openai import OpenAI


@lru_cache(maxsize=1)
def get_openai_client() -> OpenAI:
    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is not configured."
        )

    return OpenAI(api_key=api_key)


def analysis_model() -> str:
    model = os.getenv("OPENAI_ANALYSIS_MODEL")

    if not model:
        raise RuntimeError(
            "OPENAI_ANALYSIS_MODEL is not configured."
        )

    return model


def embedding_model() -> str:
    model = os.getenv("OPENAI_EMBEDDING_MODEL")

    if not model:
        raise RuntimeError(
            "OPENAI_EMBEDDING_MODEL is not configured."
        )

    return model


def embedding_dimensions() -> int:
    dimensions = os.getenv("OPENAI_EMBEDDING_DIMENSIONS")

    if not dimensions:
        raise RuntimeError(
            "OPENAI_EMBEDDING_DIMENSIONS is not configured."
        )

    return int(dimensions)