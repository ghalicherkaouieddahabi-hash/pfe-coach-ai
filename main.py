"""Point d'entrée FastAPI — Coach-PFE."""

import logging
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from models.request_models import ErrorResponse
from routes.analyze_route import router as analyze_router
from routes.export_route import router as export_router

_PROJECT_ROOT = Path(__file__).resolve().parent
load_dotenv(_PROJECT_ROOT / ".env", override=False)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("coach_pfe")


def _log_gemini_config() -> None:
    from services.gemini_service import iter_gemini_model_chain

    key_ok = bool(os.getenv("GEMINI_API_KEY", "").strip())
    logger.info(
        "Gemini — clé : %s | modèles : %s",
        "ok" if key_ok else "MANQUANTE",
        " → ".join(iter_gemini_model_chain()),
    )


_log_gemini_config()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Coach-PFE API",
        description="Assistant IA de rédaction académique pour les PFE (Gemini + RAG).",
        version="1.0.0",
    )

    @app.exception_handler(RequestValidationError)
    async def validation_error(_request: Request, exc: RequestValidationError) -> JSONResponse:
        body = ErrorResponse(
            success=False,
            error="Requête invalide : champ 'topic' requis.",
            detail=str(exc.errors()),
        ).model_dump()
        return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content=body)

    @app.exception_handler(HTTPException)
    async def http_error(_request: Request, exc: HTTPException) -> JSONResponse:
        if isinstance(exc.detail, dict):
            return JSONResponse(status_code=exc.status_code, content=exc.detail)
        return JSONResponse(
            status_code=exc.status_code,
            content=ErrorResponse(success=False, error=str(exc.detail)).model_dump(),
        )

    @app.get("/", tags=["Health"])
    def health() -> dict[str, Any]:
        from services.gemini_service import get_effective_gemini_model, iter_gemini_model_chain

        return {
            "service": "Coach-PFE",
            "status": "ok",
            "docs": "/docs",
            "ui": "/ui/",
            "gemini_api_key_configured": bool(os.getenv("GEMINI_API_KEY", "").strip()),
            "gemini_model": get_effective_gemini_model(),
            "gemini_model_chain": iter_gemini_model_chain(),
        }

    app.include_router(analyze_router)
    app.include_router(export_router)
    app.mount(
        "/ui",
        StaticFiles(directory=str(_PROJECT_ROOT / "static"), html=True),
        name="ui",
    )
    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "8000")),
        reload=True,
    )
