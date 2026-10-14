"""
Logs + Reasoning : trace structurée de chaque étape du pipeline.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ReasoningLog:
    """Journal d'exécution du pipeline multi-agents."""

    job_id: str
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    steps: list[dict[str, Any]] = field(default_factory=list)

    def add(self, step: str, status: str, *, detail: str | None = None, chars: int | None = None) -> None:
        entry: dict[str, Any] = {
            "step": step,
            "status": status,
            "at": datetime.now(timezone.utc).isoformat(),
        }
        if detail:
            entry["detail"] = detail[:500]
        if chars is not None:
            entry["output_chars"] = chars
        self.steps.append(entry)
        logger.info("Pipeline [%s] %s — %s", self.job_id[:8], step, status)

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "started_at": self.started_at,
            "steps": self.steps,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }
