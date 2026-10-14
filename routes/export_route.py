"""Téléchargement des exports PDF / DOCX."""

import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from services.export_service import resolve_export_path

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Export"])


@router.get("/exports/{job_id}/{filename}", summary="Télécharger PDF ou DOCX")
def download_export(job_id: str, filename: str) -> FileResponse:
    path = resolve_export_path(job_id, filename)
    if path is None:
        raise HTTPException(status_code=404, detail="Fichier introuvable.")
    media = (
        "application/pdf"
        if path.suffix.lower() == ".pdf"
        else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    logger.info("Export : %s", path.name)
    return FileResponse(path, media_type=media, filename=path.name)
