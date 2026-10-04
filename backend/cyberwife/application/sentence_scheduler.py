"""Bounded semantic sentence scheduling for low-latency TTS."""
from __future__ import annotations

import re


_BOUNDARY = re.compile(r"(?<=[。！？!?；;])")
_PREFIX_BOUNDARIES = frozenset("。！？!?；;，,、：:")


def playable_prefix(text: str, *, min_chars: int = 10, hard_limit: int = 18) -> str | None:
    """Return a stable, lossless prefix once enough sanitized text exists.

    The function never rewrites text: callers can append ``text[len(prefix):]``
    without losing or duplicating a character.  A semantic boundary is
    preferred after the minimum; otherwise exactly ``min_chars`` are emitted.
    """
    if not 4 <= min_chars <= 18:
        raise ValueError("min_chars must be between 4 and 18")
    if hard_limit < min_chars:
        raise ValueError("hard_limit must be >= min_chars")
    if len(text) < min_chars:
        return None
    upper = min(len(text), hard_limit)
    for index in range(min_chars - 1, upper):
        if text[index] in _PREFIX_BOUNDARIES:
            return text[: index + 1]
    return text[:min_chars]


def semantic_sentences(text: str, *, soft_limit: int = 8, hard_limit: int = 18) -> list[str]:
    """Split text at semantic boundaries, with a bounded fallback for long prose.

    Punctuation stays with the preceding sentence.  Commas are only used after
    ``soft_limit`` so normal short clauses are not fragmented into choppy TTS.
    """
    normalized = " ".join(text.strip().split())
    if not normalized:
        return []
    result: list[str] = []
    for sentence in filter(None, (part.strip() for part in _BOUNDARY.split(normalized))):
        remaining = sentence
        while len(remaining) > hard_limit:
            cut = max(
                remaining.rfind(mark, soft_limit, hard_limit + 1)
                for mark in ("，", ",", "、", "：", ":")
            )
            if cut < soft_limit:
                cut = hard_limit
            else:
                cut += 1
            result.append(remaining[:cut].strip())
            remaining = remaining[cut:].strip()
        if remaining:
            result.append(remaining)
    return result
