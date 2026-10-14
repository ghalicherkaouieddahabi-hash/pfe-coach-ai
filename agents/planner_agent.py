"""Agent PLANIFICATEUR : plan de mémoire, méthodologie et jalons."""

from typing import Optional, Tuple

from agents.gemini_runner import run_gemini_agent
from agents.text_utils import clip_text


def run_planner(merged_context: str) -> Tuple[bool, str, Optional[str]]:
    ctx = clip_text(merged_context, 12_000)
    prompt = (
        "Tu es l'agent PLANIFICATEUR pour un PFE en français.\n"
        "À partir du contexte ci-dessous, produis :\n"
        "- Plan des chapitres (titres + sous-parties)\n"
        "- Méthodologie justifiée\n"
        "- Jalons sur 12 à 16 semaines\n"
        "- Critères de validation par chapitre\n"
        "Markdown léger, 400 à 800 mots.\n\n"
        f"--- Contexte fusionné ---\n{ctx}"
    )
    return run_gemini_agent("PLANIFICATEUR", prompt, temperature=0.4)
