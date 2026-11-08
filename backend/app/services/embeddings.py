"""Embedding + vector search.

Default provider is a deterministic, dependency-free hashed TF vectoriser so the
prototype works offline and results are reproducible. It is a lexical embedding,
not a neural one; this limitation is documented in the README. When
EMBEDDINGS_PROVIDER=openai-compatible and a key is configured, real neural
embeddings are used instead.
"""
import hashlib
import math
import re
from functools import lru_cache

import httpx

from app.core.config import settings

STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "if", "then", "than", "that", "this", "these",
    "those", "is", "are", "was", "were", "be", "been", "being", "to", "of", "in", "on",
    "for", "with", "by", "at", "from", "as", "it", "its", "we", "our", "you", "your",
    "they", "their", "has", "have", "had", "do", "does", "did", "will", "would", "can",
    "could", "should", "not", "no", "all", "any", "more", "most", "other", "into", "about",
    "which", "who", "whom", "when", "where", "why", "how", "also", "very", "just", "so",
}

TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9'\-\.]*[a-z0-9]|[a-z0-9]")


def tokenize(text: str) -> list[str]:
    return [t for t in TOKEN_RE.findall(text.lower()) if t not in STOPWORDS and len(t) > 1]


def _bucket(token: str, dim: int) -> int:
    return int(hashlib.md5(token.encode()).hexdigest(), 16) % dim


def local_embed(text: str, dim: int | None = None) -> list[float]:
    dim = dim or settings.EMBEDDING_DIM
    vec = [0.0] * dim
    tokens = tokenize(text)
    if not tokens:
        return vec
    counts: dict[str, int] = {}
    for tok in tokens:
        counts[tok] = counts.get(tok, 0) + 1
    # unigrams + adjacent bigrams give a little word-order signal
    for i, tok in enumerate(tokens):
        counts[f"u_{tok}"] = counts.get(f"u_{tok}", 0) + 1
        if i:
            counts[f"b_{tokens[i-1]}_{tok}"] = counts.get(f"b_{tokens[i-1]}_{tok}", 0) + 1
    for token, count in counts.items():
        weight = (1.0 + math.log(count)) * (1.6 if token.startswith("b_") else 1.0)
        vec[_bucket(token, dim)] += weight
    norm = math.sqrt(sum(v * v for v in vec))
    if norm:
        vec = [v / norm for v in vec]
    return vec


@lru_cache(maxsize=512)
def _api_embed_cached(text: str) -> tuple[float, ...]:
    response = httpx.post(
        f"{settings.AI_BASE_URL.rstrip('/')}/embeddings",
        headers={"Authorization": f"Bearer {settings.AI_API_KEY}"},
        json={"model": settings.EMBEDDING_MODEL, "input": text},
        timeout=settings.AI_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return tuple(response.json()["data"][0]["embedding"])


def embed(text: str) -> list[float]:
    if settings.EMBEDDINGS_PROVIDER == "openai-compatible" and settings.AI_API_KEY:
        try:
            return list(_api_embed_cached(text))
        except Exception:
            # Retrieval must keep working if the embedding endpoint fails.
            return local_embed(text)
    return local_embed(text)


def cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if not na or not nb:
        return 0.0
    return dot / (na * nb)
