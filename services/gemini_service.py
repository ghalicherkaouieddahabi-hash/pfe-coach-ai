"""
Service d'accès à l'API Google Gemini pour Coach-PFE.
Centralise l'initialisation du client, la chaîne de modèles de secours et l'appel au modèle.
"""

import logging
import os
import re
import time
from typing import Optional

import google.generativeai as genai

logger = logging.getLogger(__name__)

# Modèles souvent sans quota gratuit (limit: 0) — exclus des défauts
_DEPRECATED_FREE_TIER = frozenset(
    {
        "gemini-2.0-flash",
        "gemini-2.0-flash-exp",
    }
)

_DEFAULT_PRIMARY = "gemini-2.5-flash"
_DEFAULT_FALLBACKS = "gemini-2.5-flash-lite,gemini-2.0-flash-lite,gemini-1.5-flash"


def get_effective_gemini_model() -> str:
    """
    Premier modèle de la chaîne (prioritaire).

    Défaut : ``gemini-2.5-flash``. Surcharge : ``GEMINI_MODEL``.
    """
    raw = (os.getenv("GEMINI_MODEL") or _DEFAULT_PRIMARY).strip()
    return raw or _DEFAULT_PRIMARY


def iter_gemini_model_chain() -> list[str]:
    """
    Liste ordonnée des modèles à essayer (sans doublon).

    - ``GEMINI_MODEL`` en tête
    - puis ``GEMINI_MODEL_FALLBACKS`` (liste séparée par des virgules)
    """
    primary = get_effective_gemini_model()
    raw = os.getenv("GEMINI_MODEL_FALLBACKS", _DEFAULT_FALLBACKS)
    fallbacks = [x.strip() for x in raw.split(",") if x.strip()]
    seen: set[str] = set()
    out: list[str] = []
    for m in [primary, *fallbacks]:
        if m not in seen:
            seen.add(m)
            out.append(m)
    return out


def _api_key_present() -> bool:
    key = os.getenv("GEMINI_API_KEY")
    return bool(key and str(key).strip())


def _is_zero_quota_error(exc: BaseException) -> bool:
    """Quota gratuit à 0 pour ce modèle — inutile de réessayer ou d'attendre."""
    return "limit: 0" in str(exc).lower()


def _extract_model_from_quota_detail(detail: str) -> Optional[str]:
    match = re.search(r'model:\s*([a-z0-9._-]+)', detail, re.IGNORECASE)
    return match.group(1) if match else None


def build_quota_user_message(
    *,
    chain: list[str],
    failures: list[str],
    last_detail: Optional[str],
) -> str:
    """Message lisible pour l'interface / les réponses HTTP 429."""
    failed_model = _extract_model_from_quota_detail(last_detail or "") if last_detail else None
    lines = [
        "Quota Google Gemini dépassé ou indisponible (erreur 429).",
        f"Modèles configurés : {', '.join(chain) or '(aucun)'}.",
    ]
    if failures:
        lines.append("Détail par modèle : " + " | ".join(failures[:4]))
    if failed_model and failed_model in _DEPRECATED_FREE_TIER:
        lines.append(
            f"Le modèle « {failed_model} » n'a souvent plus de quota gratuit (limit: 0). "
            "Retirez-le de GEMINI_MODEL / GEMINI_MODEL_FALLBACKS dans .env."
        )
    lines.extend(
        [
            "À faire : (1) Redémarrer Uvicorn après modification du .env. "
            "(2) Utiliser GEMINI_MODEL=gemini-2.5-flash et des fallbacks récents. "
            "(3) Attendre 1–2 min entre deux analyses. "
            "(4) Consulter https://ai.dev/rate-limit ou activer la facturation sur Google AI Studio.",
        ]
    )
    return " ".join(lines)


def _build_quota_error_message(exc: BaseException, *, model_name: str) -> str:
    detail = str(exc)
    if _is_zero_quota_error(exc):
        return (
            f"Quota gratuit indisponible pour « {model_name} » (limit: 0). "
            "Changez GEMINI_MODEL dans .env (ex. gemini-2.5-flash)."
        )
    return f"Quota ou limite Gemini (429) sur « {model_name} »."


class GeminiServiceError(Exception):
    """Erreur levée lorsque l'appel à Gemini échoue ou la clé est absente."""

    def __init__(self, message: str, *, detail: Optional[str] = None) -> None:
        super().__init__(message)
        self.detail = detail


def _get_api_key() -> str:
    key = os.getenv("GEMINI_API_KEY")
    if not key or not key.strip():
        raise GeminiServiceError(
            "La variable d'environnement GEMINI_API_KEY est absente ou vide.",
            detail="Ajoutez GEMINI_API_KEY dans votre fichier .env à la racine du projet.",
        )
    return key.strip()


def configure_genai() -> None:
    """Configure le SDK google-generativeai avec la clé API."""
    genai.configure(api_key=_get_api_key())
    logger.info("SDK Gemini configuré (clé API chargée).")


def _extract_text_from_response(response: object) -> Optional[str]:
    """
    Extrait le texte renvoyé par Gemini de façon tolérante aux variantes du SDK.
    `response.text` peut lever si le contenu est bloqué ou si la structure diffère.
    """
    try:
        direct = getattr(response, "text", None)
        if direct and str(direct).strip():
            return str(direct).strip()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Lecture response.text impossible (%s), tentative via candidats.", exc)

    candidates = getattr(response, "candidates", None) or []
    if not candidates:
        return None

    first = candidates[0]
    content = getattr(first, "content", None)
    parts = getattr(content, "parts", None) if content is not None else None
    if not parts:
        return None

    chunks: list[str] = []
    for part in parts:
        t = getattr(part, "text", None)
        if t:
            chunks.append(str(t))
    merged = "".join(chunks).strip()
    return merged or None


def _is_rate_limit_or_quota_error(exc: BaseException) -> bool:
    """Détecte 429 / quota / ResourceExhausted renvoyés par l'API ou le SDK."""
    text = str(exc).lower()
    if "429" in text:
        return True
    if "quota" in text and "exceed" in text:
        return True
    if "resource exhausted" in text:
        return True
    if "rate limit" in text:
        return True
    return "too many requests" in text


def _parse_retry_after_seconds(message: str) -> float:
    """Extrait le délai conseillé par Google (ex. « Please retry in 23.85s »)."""
    match = re.search(r"please retry in ([0-9.]+)\s*s", message, re.IGNORECASE)
    if match:
        return min(max(float(match.group(1)), 1.0), 120.0)
    match2 = re.search(r"retry in ([0-9.]+)\s*s", message, re.IGNORECASE)
    if match2:
        return min(max(float(match2.group(1)), 1.0), 120.0)
    match3 = re.search(r"seconds:\s*([0-9]+)", message, re.IGNORECASE)
    if match3:
        return min(max(float(match3.group(1)), 1.0), 120.0)
    return 12.0


def _generate_with_retries_for_model(
    model_name: str,
    prompt: str,
    *,
    temperature: float,
) -> str:
    """Un modèle donné : tentatives avec backoff sur 429 (sauf limit: 0)."""
    model = genai.GenerativeModel(model_name)
    max_attempts = max(1, int(os.getenv("GEMINI_MAX_RETRIES_ON_429", "3")))
    retry_cap = float(os.getenv("GEMINI_RETRY_CAP_SECONDS", "55"))

    for attempt in range(1, max_attempts + 1):
        try:
            logger.info(
                "Appel Gemini (tentative %d/%d, model=%s).",
                attempt,
                max_attempts,
                model_name,
            )
            response = model.generate_content(
                prompt,
                generation_config={"temperature": temperature},
            )
        except Exception as exc:  # noqa: BLE001
            if _is_rate_limit_or_quota_error(exc):
                if _is_zero_quota_error(exc):
                    logger.warning(
                        "Modèle %s : quota gratuit à 0 — passage immédiat au modèle suivant.",
                        model_name,
                    )
                    raise GeminiServiceError(
                        _build_quota_error_message(exc, model_name=model_name),
                        detail=str(exc),
                    ) from exc
                if attempt < max_attempts:
                    delay = min(_parse_retry_after_seconds(str(exc)), retry_cap)
                    logger.warning(
                        "Gemini 429 / quota (model=%s) — attente %.1f s puis retry.",
                        model_name,
                        delay,
                    )
                    time.sleep(delay)
                    continue
                logger.warning(
                    "Modèle %s toujours saturé après %d tentatives.",
                    model_name,
                    max_attempts,
                )
                raise GeminiServiceError(
                    _build_quota_error_message(exc, model_name=model_name),
                    detail=str(exc),
                ) from exc
            logger.warning("Erreur Gemini (model=%s) : %s", model_name, exc)
            raise GeminiServiceError(
                "L'API Gemini a renvoyé une erreur ou n'a pas pu être contactée.",
                detail=str(exc),
            ) from exc

        text = _extract_text_from_response(response)
        if text:
            logger.info(
                "Réponse Gemini reçue (%d caractères, model=%s).",
                len(text),
                model_name,
            )
            return text

        feedback = getattr(response, "prompt_feedback", None)
        logger.error("Réponse vide (model=%s). prompt_feedback=%s", model_name, feedback)
        raise GeminiServiceError(
            "La réponse du modèle Gemini est vide ou invalide.",
            detail="Vérifiez les filtres de sécurité et le contenu du prompt.",
        )


def generate_text(prompt: str, *, temperature: float = 0.4) -> str:
    """
    Envoie un prompt à Gemini en essayant **plusieurs modèles** à la suite si nécessaire.

    Chaque modèle bénéficie d’un petit cycle de **retry** sur erreur 429 / quota.
    Les erreurs ``limit: 0`` passent tout de suite au modèle suivant (sans 3 retries).

    :raises GeminiServiceError: Si aucun modèle n’a pu produire de texte.
    """
    if not _api_key_present():
        raise GeminiServiceError(
            "GEMINI_API_KEY absente ou vide.",
            detail="Sans clé API, le mode cloud Gemini n'est pas disponible.",
        )

    configure_genai()

    chain = iter_gemini_model_chain()
    failures: list[str] = []
    last_error: Optional[GeminiServiceError] = None

    for model_name in chain:
        try:
            return _generate_with_retries_for_model(
                model_name,
                prompt,
                temperature=temperature,
            )
        except GeminiServiceError as exc:
            last_error = exc
            failures.append(f"{model_name}: {exc}")
            logger.warning(
                "Échec sur le modèle %s, passage au suivant dans la chaîne. Raison : %s",
                model_name,
                exc,
            )
            continue

    user_msg = build_quota_user_message(
        chain=chain,
        failures=failures,
        last_detail=str(last_error.detail) if last_error and last_error.detail else None,
    )
    raise GeminiServiceError(
        "Tous les modèles Gemini configurés ont échoué.",
        detail=user_msg,
    ) from last_error
