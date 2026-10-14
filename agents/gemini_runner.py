"""Exécution homogène d'un agent Gemini."""

import logging
from typing import Optional, Tuple

from services.gemini_service import GeminiServiceError, generate_text

logger = logging.getLogger(__name__)


def run_gemini_agent(
    agent_label: str,
    prompt: str,
    *,
    temperature: float = 0.4,
) -> Tuple[bool, str, Optional[str]]:
    try:
        logger.info("Agent %s", agent_label)
        return True, generate_text(prompt, temperature=temperature), None
    except GeminiServiceError as exc:
        logger.warning("Échec %s : %s", agent_label, exc)
        return False, str(exc), exc.detail
    except Exception as exc:  # noqa: BLE001
        logger.exception("Erreur inattendue (%s).", agent_label)
        return False, f"Erreur interne ({agent_label}).", str(exc)
