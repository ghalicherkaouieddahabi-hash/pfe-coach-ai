"""
Serveur MCP pour Coach-PFE.

Expose le pipeline PFE, la santé Gemini et le corpus RAG aux clients MCP (stdio).
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_PROJECT_ROOT / ".env", override=False)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("coach_pfe.mcp")

mcp = FastMCP(
    "Coach-PFE",
    instructions=(
        "Assistant de rédaction académique PFE. Utilisez analyze_pfe pour lancer "
        "le pipeline complet (2–5 min). Utilisez rag_search pour une recherche "
        "rapide dans la méthodologie sans appeler Gemini."
    ),
)

_RAG_DIR = _PROJECT_ROOT / "data" / "rag"


def _json(data: object) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


@mcp.tool()
def health_check() -> str:
    """Vérifie la configuration Coach-PFE et la chaîne de modèles Gemini."""
    from services.gemini_service import get_effective_gemini_model, iter_gemini_model_chain

    return _json(
        {
            "service": "Coach-PFE",
            "gemini_api_key_configured": bool(os.getenv("GEMINI_API_KEY", "").strip()),
            "gemini_model": get_effective_gemini_model(),
            "gemini_model_chain": iter_gemini_model_chain(),
            "api_docs": "http://127.0.0.1:8000/docs",
            "ui": "http://127.0.0.1:8000/ui/",
        }
    )


@mcp.tool()
def analyze_pfe(topic: str, session_id: str | None = None) -> str:
    """
    Lance le pipeline complet PFE sur un sujet (Memory → Analyseur → RAG → Planner
    → Writer/Reviewer → Anti-hallucination → Export PDF/DOCX).

    Durée typique : 2 à 5 minutes (~6 appels Gemini). Nécessite GEMINI_API_KEY.
    """
    topic = topic.strip()
    if not topic:
        return _json({"success": False, "error": "Le sujet (topic) ne peut pas être vide."})

    from services.pfe_pipeline import run_full_pipeline

    logger.info("MCP analyze_pfe — %d car.", len(topic))
    ok, data, err_msg, err_detail = run_full_pipeline(topic, session_id=session_id)

    if not ok:
        return _json(
            {
                "success": False,
                "error": err_msg,
                "detail": err_detail,
            }
        )

    return _json(
        {
            "success": True,
            "topic": topic,
            "job_id": data["job_id"],
            "analyzer": data["analyzer"][:2000] + ("…" if len(data["analyzer"]) > 2000 else ""),
            "planner": data["planner"][:2000] + ("…" if len(data["planner"]) > 2000 else ""),
            "writer": data["writer"][:1500] + ("…" if len(data["writer"]) > 1500 else ""),
            "reviewer": data["reviewer"][:1500] + ("…" if len(data["reviewer"]) > 1500 else ""),
            "final_preview": data["final"][:2500]
            + ("…" if len(data["final"]) > 2500 else ""),
            "rag_sources": data.get("rag_sources", []),
            "exports": data.get("exports", {}),
            "full_lengths": {
                "analyzer": len(data["analyzer"]),
                "planner": len(data["planner"]),
                "writer": len(data["writer"]),
                "reviewer": len(data["reviewer"]),
                "final": len(data["final"]),
            },
            "note": "Textes tronqués dans cette réponse ; relancez via API ou lisez les exports.",
        }
    )


@mcp.tool()
def rag_search(query: str, top_k: int = 4) -> str:
    """
    Recherche dans le corpus RAG local (méthodologie PFE) sans appel Gemini.
    Utile pour cadrer un sujet avant analyze_pfe.
    """
    from services.rag_service import format_retrieved_chunks, retrieve

    query = query.strip()
    if not query:
        return _json({"success": False, "error": "La requête ne peut pas être vide."})

    chunks = retrieve(query, top_k=max(1, min(top_k, 10)))
    return _json(
        {
            "success": True,
            "query": query,
            "count": len(chunks),
            "sources": [f"{c['source']}#{c['id']}" for c in chunks],
            "formatted": format_retrieved_chunks(chunks),
        }
    )


@mcp.tool()
def list_rag_documents() -> str:
    """Liste les fichiers Markdown du corpus RAG (data/rag/)."""
    if not _RAG_DIR.is_dir():
        return _json({"documents": [], "path": str(_RAG_DIR)})
    docs = sorted(p.name for p in _RAG_DIR.glob("*.md"))
    return _json({"path": str(_RAG_DIR), "documents": docs})


@mcp.resource("rag://{filename}")
def read_rag_document(filename: str) -> str:
    """Lit un document RAG par nom de fichier (ex. methodologie_pfe.md)."""
    safe = Path(filename).name
    path = _RAG_DIR / safe
    if not path.is_file() or path.suffix.lower() != ".md":
        raise FileNotFoundError(f"Document RAG introuvable : {filename}")
    return path.read_text(encoding="utf-8")


@mcp.resource("coach-pfe://config")
def config_resource() -> str:
    """Configuration Gemini active (modèles et clé présente ou non)."""
    return health_check()


@mcp.prompt()
def pfe_coaching_prompt(topic: str) -> str:
    """Prompt modèle pour demander une analyse structurée d'un sujet PFE."""
    return (
        f"Tu accompagnes un étudiant sur son PFE. Sujet : « {topic} ».\n"
        "Utilise l'outil MCP analyze_pfe pour obtenir analyse, plan, brouillon et version relue, "
        "ou rag_search pour la méthodologie seule.\n"
        "Réponds en français, style académique, en citant les sources RAG quand pertinent."
    )
