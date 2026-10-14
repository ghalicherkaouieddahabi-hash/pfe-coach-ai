"""Schémas Pydantic pour l'API Coach-PFE."""

from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


class AnalyzeRequest(BaseModel):
    topic: str = Field(..., min_length=1, max_length=10_000)
    session_id: Optional[str] = Field(default=None, max_length=128)

    @field_validator("topic")
    @classmethod
    def topic_not_blank(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Le champ 'topic' ne peut pas être vide.")
        return stripped


class AgentOutputs(BaseModel):
    """Rétrocompatibilité : miroir des sorties (coach = texte final)."""

    analyzer: str
    planner: str
    writer: str = ""
    reviewer: str = ""
    coach: str = Field(description="Texte final (anti-hallucination).")


class PipelineOutputs(BaseModel):
    job_id: str
    memory_context: Optional[str] = None
    analyzer: str
    rag_sources: list[str] = Field(default_factory=list)
    planner: str
    writer: str
    reviewer: str
    final: str
    exports: dict[str, str] = Field(default_factory=dict)
    reasoning: dict[str, Any] = Field(default_factory=dict)
    agents: AgentOutputs


class AnalyzeSuccessResponse(BaseModel):
    success: bool = True
    message: str = "Pipeline terminé avec succès."
    topic: str
    pipeline: PipelineOutputs


class ErrorResponse(BaseModel):
    success: bool = False
    error: str
    detail: Optional[str] = None
