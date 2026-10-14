"""
Retriever RAG léger : recherche dans des fichiers Markdown locaux (sans base vectorielle externe).
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

_RAG_DIR = Path(__file__).resolve().parent.parent / "data" / "rag"
_TOP_K = 4


def _tokenize(text: str) -> set[str]:
    words = re.findall(r"[a-zA-ZàâäéèêëïîôùûüçÀ-ÿ0-9]{3,}", text.lower())
    return set(words)


def _load_chunks() -> list[dict[str, str]]:
    chunks: list[dict[str, str]] = []
    if not _RAG_DIR.is_dir():
        return chunks
    for path in sorted(_RAG_DIR.glob("*.md")):
        try:
            raw = path.read_text(encoding="utf-8")
        except OSError as exc:
            logger.warning("Lecture RAG impossible %s : %s", path, exc)
            continue
        parts = re.split(r"\n(?=#{1,3}\s)", raw)
        for i, part in enumerate(parts):
            part = part.strip()
            if len(part) < 40:
                continue
            chunks.append({"source": path.name, "id": f"{path.stem}_{i}", "text": part})
    return chunks


_CHUNKS_CACHE: list[dict[str, str]] | None = None


def _get_chunks() -> list[dict[str, str]]:
    global _CHUNKS_CACHE  # noqa: PLW0603
    if _CHUNKS_CACHE is None:
        _CHUNKS_CACHE = _load_chunks()
        logger.info("RAG : %d fragments chargés depuis %s.", len(_CHUNKS_CACHE), _RAG_DIR)
    return _CHUNKS_CACHE


def retrieve(query: str, *, top_k: int = _TOP_K) -> list[dict[str, str]]:
    """
    Score par recouvrement lexical et renvoie les meilleurs fragments.
    """
    chunks = _get_chunks()
    if not chunks:
        return []
    q_tokens = _tokenize(query)
    if not q_tokens:
        return []
    scored: list[tuple[float, dict[str, str]]] = []
    for ch in chunks:
        t_tokens = _tokenize(ch["text"])
        if not t_tokens:
            continue
        overlap = len(q_tokens & t_tokens)
        if overlap == 0:
            continue
        score = overlap / (len(q_tokens) ** 0.5)
        scored.append((score, ch))
    scored.sort(key=lambda x: x[0], reverse=True)
    result = [ch for _, ch in scored[:top_k]]
    logger.info("RAG : %d fragments retenus pour la requête.", len(result))
    return result


def format_retrieved_chunks(chunks: list[dict[str, str]]) -> str:
    """Formate les passages pour injection dans les prompts."""
    if not chunks:
        return "(Aucun document de référence local trouvé.)"
    parts = []
    for ch in chunks:
        parts.append(f"#### Source : {ch['source']} / {ch['id']}\n{ch['text']}")
    return "\n\n".join(parts)
