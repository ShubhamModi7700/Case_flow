"""Legacy configuration helpers.

New AI calls should go through app.services.ai_provider. These helpers remain so
existing model-name metadata does not need to change all at once.
"""
from app.services.ai_provider import get_ai_provider


def analysis_model() -> str:
    return get_ai_provider().analysis_model()


def embedding_model() -> str:
    return get_ai_provider().embedding_model()


def embedding_dimensions() -> int:
    return get_ai_provider().embedding_dimensions()
