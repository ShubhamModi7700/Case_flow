from app.services.openai_client import (
    embedding_dimensions,
    embedding_model,
    get_openai_client,
)


def create_embeddings(texts: list[str]) -> list[list[float]]:
    cleaned = [text.strip() for text in texts if text and text.strip()]
    if not cleaned:
        return []

    response = get_openai_client().embeddings.create(
        model=embedding_model(),
        input=cleaned,
        encoding_format="float",
        dimensions=embedding_dimensions(),
    )
    vectors = [item.embedding for item in response.data]

    if len(vectors) != len(cleaned):
        raise RuntimeError("OpenAI hat nicht für jeden Text ein Embedding geliefert.")

    expected = embedding_dimensions()
    invalid = [len(vector) for vector in vectors if len(vector) != expected]
    if invalid:
        raise RuntimeError(
            f"Embedding-Dimension stimmt nicht: erwartet {expected}, erhalten {invalid[0]}."
        )

    return vectors


def create_query_embedding(text: str) -> list[float]:
    vectors = create_embeddings([text])
    if not vectors:
        raise ValueError("Für eine leere Suchanfrage kann kein Embedding erstellt werden.")
    return vectors[0]
