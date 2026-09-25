from app.services.ai_provider import get_ai_provider


def create_embeddings(texts: list[str]) -> list[list[float]]:
    cleaned = [text.strip() for text in texts if text and text.strip()]
    if not cleaned:
        return []
    return get_ai_provider().create_embeddings(cleaned)


def create_query_embedding(text: str) -> list[float]:
    vectors = create_embeddings([text])
    if not vectors:
        raise ValueError("Für eine leere Suchanfrage kann kein Embedding erstellt werden.")
    return vectors[0]
