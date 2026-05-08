"""Lightweight deterministic embeddings for PRD10 search.

This is intentionally local and dependency-free. It gives PRD10 V1 a real
semantic vector path on SQLite and Postgres without downloading model files.
The vector is stable across processes, so rows can persist ``embedding`` and
``embedding_id`` while tests and demo data remain deterministic.

§15.43 — Chinese-aware tokenization. The original regex
``[\\w\\u4e00-\\u9fff]+`` collapsed an entire Chinese phrase into ONE token
because CJK characters have no whitespace separators. The fix splits Chinese
into per-character tokens **and** sliding bigrams while keeping latin words
intact, so:

    "请基于知识库总结一下产品设计"
    → ["请", "请基", "基", "基于", "于", ..., "知识", "识库", ...]

This gives ``embed_text`` a fighting chance at non-zero cosine similarity
between sentences that share characters/concepts even when they don't
share a literal substring.

The embedding dimension is bumped from 64 → 128 so the bigger Chinese
n-gram alphabet fits with fewer hash collisions, but all helpers stay
bytes-for-bytes API-compatible.
"""

from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Iterable

EMBEDDING_DIMENSION = 128
EMBEDDING_VERSION = "hash128-v2-cjk"

_LATIN_PATTERN = re.compile(r"[A-Za-z0-9_]+", flags=re.UNICODE)
_CJK_PATTERN = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf]")


def tokenize(text: str | None) -> list[str]:
    """Tokenize ``text`` into a Chinese-aware multiset.

    The output is intentionally lossy and overlapping:
    * latin words → single lowercase token
    * Chinese characters → per-char + bigram tokens
    * digits / mixed runs → preserved as single token

    Calling tokenize twice on the same input is idempotent.
    """

    if not text:
        return []

    tokens: list[str] = []

    for match in _LATIN_PATTERN.finditer(text):
        word = match.group(0).lower()
        if word:
            tokens.append(word)

    cjk_chars = _CJK_PATTERN.findall(text)
    if not cjk_chars:
        return tokens

    full_cjk_chunks = re.findall(r"[\u4e00-\u9fff\u3400-\u4dbf]+", text)
    for chunk in full_cjk_chunks:
        for ch in chunk:
            tokens.append(ch)
        if len(chunk) > 1:
            for i in range(len(chunk) - 1):
                tokens.append(chunk[i : i + 2])
    return tokens


def embed_text(text: str | None, *, dimension: int = EMBEDDING_DIMENSION) -> list[float]:
    """Return a normalized hashing vector for ``text``.

    The signed-hashing trick keeps dimensions fixed and gives related text a
    non-zero cosine score when they share meaningful tokens. It is not a
    substitute for a neural model, but it is a real embedding representation
    and a useful deterministic fallback for V1/demo/local installs.
    """

    vector = [0.0] * dimension
    for token in tokenize(text):
        digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
        bucket = int.from_bytes(digest[:4], "big") % dimension
        sign = 1.0 if (digest[4] & 1) == 0 else -1.0
        vector[bucket] += sign

    norm = math.sqrt(sum(value * value for value in vector))
    if norm <= 0:
        return vector
    return [round(value / norm, 8) for value in vector]


def embedding_id_for_text(text: str | None) -> str:
    digest = hashlib.sha256((text or "").encode("utf-8")).hexdigest()[:24]
    return f"{EMBEDDING_VERSION}:{digest}"


def cosine_similarity(left: Iterable[float] | None, right: Iterable[float] | None) -> float:
    if left is None or right is None:
        return 0.0
    left_values = [float(value) for value in left]
    right_values = [float(value) for value in right]
    if not left_values or not right_values or len(left_values) != len(right_values):
        return 0.0

    dot = sum(a * b for a, b in zip(left_values, right_values))
    left_norm = math.sqrt(sum(a * a for a in left_values))
    right_norm = math.sqrt(sum(b * b for b in right_values))
    if left_norm <= 0 or right_norm <= 0:
        return 0.0
    return dot / (left_norm * right_norm)


def text_for_search_embedding(*parts: str | None) -> str:
    return " ".join(part.strip() for part in parts if part and part.strip())

