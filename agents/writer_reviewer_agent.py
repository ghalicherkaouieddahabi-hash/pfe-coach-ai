"""Agent WRITER + REVIEWER : brouillon et relecture en un appel Gemini."""

import re
from typing import Optional, Tuple

from agents.gemini_runner import run_gemini_agent
from agents.text_utils import clip_text


def _split_writer_reviewer(raw: str) -> Tuple[str, str]:
    text = raw.strip()
    w_match = re.search(
        r"##\s*WRITER\s*\n(.*?)(?=##\s*REVIEWER\s*\n|$)",
        text,
        re.DOTALL | re.IGNORECASE,
    )
    r_match = re.search(r"##\s*REVIEWER\s*\n(.*)$", text, re.DOTALL | re.IGNORECASE)
    writer = w_match.group(1).strip() if w_match else ""
    reviewer = r_match.group(1).strip() if r_match else ""
    if writer and reviewer:
        return writer, reviewer
    if len(text) > 400:
        mid = len(text) // 2
        return text[:mid].strip(), text[mid:].strip()
    return text, text


def run_writer_reviewer(
    merged_context: str,
    planner_output: str,
) -> Tuple[bool, str, str, Optional[str]]:
    ctx = clip_text(merged_context)
    plan = clip_text(planner_output)
    prompt = (
        "Tu es les agents WRITER puis REVIEWER pour un PFE en français.\n"
        "Réponds en DEUX sections avec exactement ces titres :\n\n"
        "## WRITER\n"
        "Introduction développée (600 à 900 mots) : problématique, objectifs, annonce du plan.\n\n"
        "## REVIEWER\n"
        "Version corrigée du texte WRITER + 3 à 5 points de modifications en fin de section.\n\n"
        f"--- Contexte ---\n{ctx}\n\n--- Plan ---\n{plan}"
    )
    ok, raw, detail = run_gemini_agent("WRITER+REVIEWER", prompt, temperature=0.42)
    if not ok:
        return False, "", "", detail
    writer, reviewer = _split_writer_reviewer(raw)
    return True, writer or raw.strip(), reviewer or writer, None
