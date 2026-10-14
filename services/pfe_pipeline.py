"""
Pipeline Coach-PFE :

Memory → Analyseur → RAG → Merge → Planner → Writer+Reviewer
→ Anti-hallucination → Export → Logs
"""

from __future__ import annotations

import logging
import os
import time
import uuid
from typing import Any, Callable, Optional, Tuple

from agents.analyzer_agent import run_analyzer
from agents.anti_hallucination_agent import run_anti_hallucination
from agents.planner_agent import run_planner
from agents.writer_reviewer_agent import run_writer_reviewer
from services.context_service import merge_context
from services.export_service import export_documents
from services.memory_service import append_memory, get_memory_context
from services.rag_service import format_retrieved_chunks, retrieve
from services.reasoning_logger import ReasoningLog

logger = logging.getLogger(__name__)

AgentFn = Callable[[], Tuple[bool, str, Optional[str]]]

_STAGE_LABELS = {
    "analyzer": "ANALYSEUR",
    "planner": "PLANIFICATEUR",
    "writer": "WRITER",
    "reviewer": "REVIEWER",
    "anti_hallucination": "ANTI-HALLUCINATION",
}


def _sleep_between_steps() -> None:
    try:
        gap = float(os.getenv("GEMINI_DELAY_BETWEEN_AGENTS_SECONDS", "3"))
    except ValueError:
        gap = 3.0
    if gap > 0:
        time.sleep(gap)


def _stage_msg(stage: str, message: str | None) -> str:
    label = _STAGE_LABELS.get(stage, stage.upper())
    return f"Échec à l'étape « {label} » : {message or 'erreur inconnue'}"


def _run_step(
    log: ReasoningLog,
    step_name: str,
    fn: AgentFn,
) -> Tuple[bool, str, Optional[str], Optional[str]]:
    ok, text, detail = fn()
    if ok:
        log.add(step_name, "ok", chars=len(text))
        return True, text, None, None
    log.add(step_name, "error", detail=detail or text)
    return False, "", text, detail


def _run_writer_reviewer(
    log: ReasoningLog,
    merged: str,
    planner_text: str,
) -> Tuple[bool, str, str, Optional[str], Optional[str]]:
    ok, writer, reviewer, detail = run_writer_reviewer(merged, planner_text)
    if ok:
        log.add("writer", "ok", chars=len(writer))
        log.add("reviewer", "ok", chars=len(reviewer))
        return True, writer, reviewer, None, None
    log.add("writer", "error", detail=detail or "échec writer+reviewer")
    return False, "", "", detail, detail


def run_full_pipeline(
    topic: str,
    session_id: str | None = None,
) -> Tuple[bool, dict[str, Any], Optional[str], Optional[str]]:
    """
    Exécute le pipeline complet.

    :return: ``(succès, payload, message_erreur, détail)``.
    """
    job_id = str(uuid.uuid4())
    log = ReasoningLog(job_id=job_id)
    log.add("pipeline", "started", detail=f"topic_len={len(topic)}")

    memory_context = get_memory_context(session_id)
    log.add("memory", "ok", chars=len(memory_context))
    _sleep_between_steps()

    ok, analyzer_text, err, detail = _run_step(
        log, "analyzer", lambda: run_analyzer(topic, memory_context)
    )
    if not ok:
        return False, {}, _stage_msg("analyzer", err), detail

    _sleep_between_steps()

    rag_query = f"{topic}\n{analyzer_text[:1500]}"
    rag_chunks = retrieve(rag_query)
    rag_formatted = format_retrieved_chunks(rag_chunks)
    rag_sources = [f"{c['source']}#{c['id']}" for c in rag_chunks]
    log.add("rag", "ok", detail=f"{len(rag_chunks)} fragments", chars=len(rag_formatted))

    merged = merge_context(topic, memory_context, analyzer_text, rag_formatted)
    log.add("merge_context", "ok", chars=len(merged))
    _sleep_between_steps()

    ok, planner_text, err, detail = _run_step(log, "planner", lambda: run_planner(merged))
    if not ok:
        return False, {}, _stage_msg("planner", err), detail

    _sleep_between_steps()

    ok_wr, writer_text, reviewer_text, err, detail = _run_writer_reviewer(
        log, merged, planner_text
    )
    if not ok_wr:
        return False, {}, _stage_msg("writer", err), detail

    _sleep_between_steps()

    ok, final_text, err, detail = _run_step(
        log,
        "anti_hallucination",
        lambda: run_anti_hallucination(reviewer_text, rag_formatted, topic),
    )
    if not ok:
        return False, {}, _stage_msg("anti_hallucination", err), detail

    export_paths: dict[str, str] = {}
    try:
        export_paths = export_documents(job_id, topic, final_text)
        log.add("export", "ok", detail=str(export_paths))
    except Exception as exc:  # noqa: BLE001
        logger.exception("Export fichiers échoué.")
        log.add("export", "warning", detail=str(exc))

    log.add("pipeline", "completed")
    append_memory(session_id, "assistant", final_text[:1500])
    append_memory(session_id, "user", topic[:500])

    payload: dict[str, Any] = {
        "job_id": job_id,
        "memory_context": memory_context or None,
        "analyzer": analyzer_text,
        "rag_sources": rag_sources,
        "planner": planner_text,
        "writer": writer_text,
        "reviewer": reviewer_text,
        "final": final_text,
        "exports": export_paths,
        "reasoning": log.to_dict(),
    }
    logger.info("Pipeline %s terminé.", job_id[:8])
    return True, payload, None, None
