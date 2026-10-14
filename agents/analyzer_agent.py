"""
Agent ANALYSEUR : cadrage du sujet PFE, problématique, objectifs et notions clés.
"""

from typing import Optional, Tuple

from agents.gemini_runner import run_gemini_agent


def run_analyzer(topic: str, memory_context: str = "") -> Tuple[bool, str, Optional[str]]:
    """Analyse et cadrage académique du sujet."""
    memory_block = f"\n\n{memory_context}" if memory_context.strip() else ""
    prompt = (
        "Tu es l'agent ANALYSEUR pour un mémoire de fin d'études (PFE) en français.\n"
        "Mission : cadrer le sujet de façon académique.\n"
        "Produis une réponse structurée (Markdown léger) :\n"
        "- Reformulation du sujet et périmètre\n"
        "- Problématique (1 à 2 questions de recherche)\n"
        "- Objectifs (SMART si pertinent)\n"
        "- Concepts à définir\n"
        "- Enjeux académiques ou professionnels\n"
        "Environ 400 à 800 mots.\n\n"
        f"Sujet du PFE :\n{topic}{memory_block}"
    )
    return run_gemini_agent("ANALYSEUR", prompt, temperature=0.35)
