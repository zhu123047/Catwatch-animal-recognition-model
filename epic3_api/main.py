"""FastAPI entry point for the EPIC 3 image identification MVP."""

from __future__ import annotations

import re

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from .classifier import build_classifier
from .config import load_settings
from .db import DatabaseConfig, ReadOnlySpeciesRepository
from .schemas import HealthResponse, IdentifyResponse, SpeciesInsight


POSTCODE_RE = re.compile(r"^\d{4}$")

settings = load_settings()
classifier = build_classifier(
    settings.model_path,
    settings.labels_path,
    settings.classifier_backend,
)
repository = ReadOnlySpeciesRepository(DatabaseConfig(settings.pg_dsn))

app = FastAPI(
    title="EPIC 3 Species Identification API",
    version="0.1.0",
    description="MVP API for image-based species identification and local sightings.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)
app.state.classifier = classifier
app.state.repository = repository
app.state.settings = settings


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        classifier_mode=app.state.classifier.mode,
        database=app.state.settings.pg_database,
    )


@app.post("/api/epic3/identify", response_model=IdentifyResponse)
async def identify_species(
    postcode: str = Form(...),
    image: UploadFile = File(...),
    top_k: int | None = Form(None),
) -> IdentifyResponse:
    postcode = postcode.strip()
    if not POSTCODE_RE.match(postcode):
        raise HTTPException(status_code=400, detail="postcode must be a 4 digit value.")

    if image.content_type and not image.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Uploaded file must be an image.")

    image_bytes = await image.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Uploaded image is empty.")

    if len(image_bytes) > app.state.settings.max_upload_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"Uploaded image exceeds {app.state.settings.max_upload_mb} MB.",
        )

    requested_top_k = top_k or app.state.settings.default_top_k
    try:
        predictions = app.state.classifier.classify_image(image_bytes, requested_top_k)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    warnings: list[str] = []
    try:
        insights = app.state.repository.get_species_insights(postcode, predictions)
    except Exception as exc:  # pragma: no cover - depends on local database state.
        warnings.append(f"Database lookup unavailable: {exc}")
        insights = [
            SpeciesInsight(prediction=prediction) for prediction in predictions
        ]

    return IdentifyResponse(
        postcode=postcode,
        filename=image.filename or "upload",
        classifier_mode=app.state.classifier.mode,
        predictions=predictions,
        species_insights=insights,
        warnings=warnings,
    )

