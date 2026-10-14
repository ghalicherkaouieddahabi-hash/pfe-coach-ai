"""Utilitaires texte partagés par les agents."""


def clip_text(text: str, max_chars: int = 10_000, *, suffix: str = "\n\n[... contexte tronqué ...]") -> str:
    """Tronque un texte pour respecter les limites de prompt."""
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + suffix
