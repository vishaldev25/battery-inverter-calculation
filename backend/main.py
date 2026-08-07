"""
Backend Application Entrypoint
Mounts the calculation router (Feature 08), configures environment-driven
CORS, standardizes unhandled error responses, and manages the MongoDB
connection lifecycle (Feature 10).

Run locally with:
    fastapi dev backend/main.py
or:
    uvicorn backend.main:app --reload

Environment variables (see .env / .env.example):
    ALLOWED_ORIGINS   Comma-separated list of allowed CORS origins.
                       Defaults to local Vite dev origins if unset.
    MONGODB_URI       MongoDB Atlas connection string.
    DATABASE_NAME     Target database name.
"""

import logging
#logging.basicConfig(level=logging.INFO)
import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.db.client import connect_to_mongo, close_mongo_connection
from backend.projects.router import router as calculation_router

load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env")
logger = logging.getLogger("backend")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: connect to MongoDB and verify with a ping before accepting traffic.
    await connect_to_mongo()
    yield
    # Shutdown: close the connection cleanly.
    await close_mongo_connection()


app = FastAPI(
    title="Battery & Inverter Sizing API",
    description=(
        "Standards-based (IEEE 485 / IEEE 1013 / NEC) battery bank and "
        "inverter sizing calculation engine for electrical professionals."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# CORS — environment-driven, never hardcoded.
# ---------------------------------------------------------------------------
_DEFAULT_DEV_ORIGINS = "http://localhost:5173,http://127.0.0.1:5173"

_raw_origins = os.environ.get("ALLOWED_ORIGINS", _DEFAULT_DEV_ORIGINS)
ALLOWED_ORIGINS = [origin.strip() for origin in _raw_origins.split(",") if origin.strip()]

if not ALLOWED_ORIGINS:
    logger.warning(
        "ALLOWED_ORIGINS resolved to an empty list — falling back to local dev origins."
    )
    ALLOWED_ORIGINS = _DEFAULT_DEV_ORIGINS.split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Standard response envelope for UNHANDLED errors only.
# ---------------------------------------------------------------------------

def _error_envelope(code: int, message: str) -> dict:
    return {
        "success": False,
        "error": {"code": code, "message": message},
        "data": None,
    }


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=_error_envelope(exc.status_code, exc.detail),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    messages = [
        f"{'.'.join(str(loc) for loc in err['loc'])}: {err['msg']}"
        for err in exc.errors()
    ]
    combined_message = "; ".join(messages) if messages else "Invalid request payload."

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=_error_envelope(status.HTTP_422_UNPROCESSABLE_ENTITY, combined_message),
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception while processing request: %s", request.url)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=_error_envelope(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "An unexpected error occurred. Please try again.",
        ),
    )


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(calculation_router)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
@app.get("/health", status_code=status.HTTP_200_OK, tags=["Health"])
async def health_check() -> dict:
    return {"status": "ok"}