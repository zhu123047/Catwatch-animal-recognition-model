"""Pydantic response models for the EPIC 3 API."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class Prediction(BaseModel):
    scientific_name: str
    common_name: Optional[str] = None
    confidence: float = Field(ge=0.0, le=1.0)
    source: str = "demo"


class SpeciesInsight(BaseModel):
    prediction: Prediction
    conservation_status: Optional[str] = None
    local_sighting_count: int = 0
    lga_sighting_count: int = 0
    victoria_sighting_count: int = 0
    latest_local_cached_at: Optional[datetime] = None
    latest_victoria_cached_at: Optional[datetime] = None
    suburb_name: Optional[str] = None
    lga_name: Optional[str] = None


class IdentifyResponse(BaseModel):
    postcode: str
    filename: str
    classifier_mode: str
    predictions: list[Prediction]
    species_insights: list[SpeciesInsight]
    warnings: list[str] = Field(default_factory=list)


class HealthResponse(BaseModel):
    status: str
    classifier_mode: str
    database: str

