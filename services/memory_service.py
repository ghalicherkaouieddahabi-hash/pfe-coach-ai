"""Mémoire de session par identifiant (stockage en mémoire process)."""

from __future__ import annotations

import logging
from collections import defaultdict

logger = logging.getLogger(__name__)

_MAX_ENTRIES = 20
_store: dict[str, list[dict[str, str]]] = defaultdict(list)


def get_memory_context(session_id: str | None) -> str:
    if not session_id or not session_id.strip():
        return ""
    entries = _store.get(session_id.strip(), [])
    if not entries:
        return ""
    lines = ["### Historique de session"]
    for item in entries[-5:]:
        lines.append(f"- [{item.get('role', 'info')}] {item.get('content', '')[:500]}")
    return "\n".join(lines)


def append_memory(session_id: str | None, role: str, content: str) -> None:
    if not session_id or not session_id.strip():
        return
    sid = session_id.strip()
    _store[sid].append({"role": role, "content": content[:2000]})
    if len(_store[sid]) > _MAX_ENTRIES:
        _store[sid] = _store[sid][-_MAX_ENTRIES:]
    logger.debug("Mémoire %s : +1 (%s).", sid[:8], role)
