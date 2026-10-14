"""
Fusion du contexte (Merge Context) : sujet, mémoire, analyse, passages RAG.
"""

from __future__ import annotations


def merge_context(
    topic: str,
    memory_context: str,
    analyzer_output: str,
    rag_formatted: str,
) -> str:
    """
    Produit un bloc unique injecté dans Planner, Writer, Reviewer et Anti-hallucination.
    """
    sections = [
        "## Sujet du PFE",
        topic.strip(),
        "## Analyse initiale (Agent Analyseur)",
        analyzer_output.strip(),
        "## Documents de référence (RAG)",
        rag_formatted.strip(),
    ]
    if memory_context and memory_context.strip():
        sections.insert(2, "## Mémoire de session")
        sections.insert(3, memory_context.strip())
    return "\n\n".join(sections)
