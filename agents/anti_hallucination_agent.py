"""Agent ANTI-HALLUCINATION : contrôle du texte par rapport aux sources RAG."""

from typing import Optional, Tuple

from agents.gemini_runner import run_gemini_agent
from agents.text_utils import clip_text


def run_anti_hallucination(
    reviewed_text: str,
    rag_formatted: str,
    topic: str,
) -> Tuple[bool, str, Optional[str]]:
    prompt = (
        "Tu es l'agent ANTI-HALLUCINATION pour un PFE en français.\n"
        "Tu disposes de sources de référence (RAG) et d'un texte relu.\n"
        "Mission :\n"
        "- Identifier toute affirmation factuelle non étayée par les sources ou le sujet\n"
        "- Proposer une VERSION FINALE du texte sans invention ni données chiffrées inventées\n"
        "- Ajouter une section « Vigilance » (3 à 5 points) en fin de réponse\n"
        "Si une information manque, formuler prudemment (« à vérifier », « selon l'enquête à mener »).\n\n"
        f"Sujet : {topic}\n\n"
        f"--- Sources RAG ---\n{clip_text(rag_formatted)}\n\n"
        f"--- Texte relu ---\n{clip_text(reviewed_text)}"
    )
    return run_gemini_agent("ANTI-HALLUCINATION", prompt, temperature=0.25)
