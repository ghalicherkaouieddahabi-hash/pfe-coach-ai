"""Route POST /analyze — pipeline Coach-PFE."""

import logging
from typing import Annotated

from fastapi import APIRouter, Body, HTTPException, status

from models.request_models import (
    AgentOutputs,
    AnalyzeRequest,
    AnalyzeSuccessResponse,
    ErrorResponse,
    PipelineOutputs,
)
from services.gemini_service import build_quota_user_message, iter_gemini_model_chain
from services.pfe_pipeline import run_full_pipeline

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Analyze"])


def _http_status_for_error(content: str, detail: str | None) -> int:
    lowered = content.lower()
    detail_lower = (detail or "").lower()
    if "gemini_api_key" in lowered or ("absente" in lowered and "clé" in lowered):
        return status.HTTP_503_SERVICE_UNAVAILABLE
    if (
        "429" in detail_lower
        or "quota exceeded" in detail_lower
        or "429" in lowered
        or ("quota" in lowered and "gemini" in lowered)
    ):
        return status.HTTP_429_TOO_MANY_REQUESTS
    if "gemini" in lowered:
        return status.HTTP_503_SERVICE_UNAVAILABLE
    return status.HTTP_500_INTERNAL_SERVER_ERROR


def _raise_pipeline_error(content: str, detail: str | None) -> None:
    code = _http_status_for_error(content, detail)
    user_detail = detail
    if code == status.HTTP_429_TOO_MANY_REQUESTS:
        user_detail = build_quota_user_message(
            chain=iter_gemini_model_chain(),
            failures=[],
            last_detail=detail,
        )
        content = (
            content.split(":", 1)[0].strip() if ":" in content else "Quota Gemini dépassé"
        ) + " : consultez le détail ci-dessous."
    raise HTTPException(
        status_code=code,
        detail=ErrorResponse(success=False, error=content, detail=user_detail).model_dump(),
    )


@router.post(
    "/analyze",
    response_model=AnalyzeSuccessResponse,
    responses={
        422: {"model": ErrorResponse},
        429: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
    summary="Pipeline PFE complet",
    description=(
        "Memory → Analyseur → RAG → Planner → Writer/Reviewer → "
        "Anti-hallucination → Export PDF/DOCX. Corps : "
        '`{"topic": "...", "session_id": "..."}`.'
    ),
)
def analyze_pfe_topic(
    payload: Annotated[
        AnalyzeRequest,
        Body(
            openapi_examples={
                "pfe": {
                    "summary": "Analyse complète",
                    "value": {
                        "topic": "Plateforme e-learning pour la formation continue",
                        "session_id": "demo-session",
                    },
                },
            },
        ),
    ],
) -> AnalyzeSuccessResponse:
    logger.info("POST /analyze — %d car., session=%s", len(payload.topic), payload.session_id)

    try:
        ok, data, err_msg, err_detail = run_full_pipeline(
            payload.topic,
            session_id=payload.session_id,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Erreur inattendue sur /analyze.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ErrorResponse(
                success=False,
                error="Erreur interne du serveur.",
                detail=str(exc),
            ).model_dump(),
        ) from exc

    if not ok:
        _raise_pipeline_error(err_msg or "Erreur pipeline", err_detail)

    return AnalyzeSuccessResponse(
        success=True,
        message="Pipeline terminé avec succès.",
        topic=payload.topic,
        pipeline=PipelineOutputs(
            job_id=data["job_id"],
            memory_context=data.get("memory_context"),
            analyzer=data["analyzer"],
            rag_sources=data.get("rag_sources", []),
            planner=data["planner"],
            writer=data["writer"],
            reviewer=data["reviewer"],
            final=data["final"],
            exports=data.get("exports", {}),
            reasoning=data.get("reasoning", {}),
            agents=AgentOutputs(
                analyzer=data["analyzer"],
                planner=data["planner"],
                writer=data["writer"],
                reviewer=data["reviewer"],
                coach=data["final"],
            ),
        ),
    )
