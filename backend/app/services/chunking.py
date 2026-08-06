from dataclasses import dataclass

import tiktoken


@dataclass
class Chunk:
    content: str
    token_count: int


def _encoding():
    try:
        return tiktoken.get_encoding("cl100k_base")
    except Exception:
        return None


def split_text(
    text: str,
    *,
    max_tokens: int = 700,
    overlap_tokens: int = 100,
) -> list[Chunk]:
    normalized = "\n".join(line.strip() for line in text.splitlines() if line.strip())
    if not normalized:
        return []

    encoding = _encoding()
    if encoding is None:
        size = 3000
        overlap = 400
        return [
            Chunk(normalized[start:start + size], len(normalized[start:start + size]) // 4)
            for start in range(0, len(normalized), max(1, size - overlap))
            if normalized[start:start + size].strip()
        ]

    tokens = encoding.encode(normalized)
    step = max(1, max_tokens - overlap_tokens)
    chunks: list[Chunk] = []
    for start in range(0, len(tokens), step):
        token_slice = tokens[start:start + max_tokens]
        if not token_slice:
            break
        content = encoding.decode(token_slice).strip()
        if content:
            chunks.append(Chunk(content=content, token_count=len(token_slice)))
        if start + max_tokens >= len(tokens):
            break
    return chunks
