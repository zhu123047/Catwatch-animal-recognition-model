from datetime import datetime

import pytest

from epic3_api.classifier import DemoSpeciesClassifier
from epic3_api.classifier import build_classifier
from epic3_api.db import SPECIES_CONTEXT_SQL, SUBURB_SQL
from epic3_api.schemas import Prediction, SpeciesInsight


def test_demo_classifier_is_deterministic():
    classifier = DemoSpeciesClassifier()

    first = classifier.classify_image(b"fake-image-bytes", top_k=3)
    second = classifier.classify_image(b"fake-image-bytes", top_k=3)

    assert first == second
    assert len(first) == 3
    assert first[0].confidence > first[1].confidence
    assert first[0].source == "demo"


def test_auto_classifier_falls_back_to_demo_when_ml_dependencies_are_unavailable(monkeypatch):
    from epic3_api.ml import imagenet_classifier

    def fail_to_load():
        raise RuntimeError("torch unavailable")

    monkeypatch.setattr(imagenet_classifier, "ImageNetClassifier", fail_to_load)
    classifier = build_classifier(
        model_path="/path/that/does/not/exist.pt",
        labels_path="/path/that/does/not/exist.json",
        backend="auto",
    )

    assert classifier.mode == "demo"


def test_db_queries_are_read_only_selects():
    combined_sql = f"{SUBURB_SQL}\n{SPECIES_CONTEXT_SQL}".lower()

    assert "select" in combined_sql
    assert "insert " not in combined_sql
    assert "update " not in combined_sql
    assert "delete " not in combined_sql
    assert "drop " not in combined_sql
    assert "create " not in combined_sql
    assert "alter " not in combined_sql


def test_identify_endpoint_uses_mocked_dependencies(monkeypatch):
    pytest.importorskip("fastapi")
    monkeypatch.setenv("EPIC3_CLASSIFIER_BACKEND", "demo")
    from fastapi.testclient import TestClient

    from epic3_api.main import app

    class FakeClassifier:
        mode = "test"

        def classify_image(self, image_bytes, top_k=3):
            assert image_bytes == b"image-bytes"
            assert top_k == 2
            return [
                Prediction(
                    scientific_name="Platycercus elegans",
                    common_name="Crimson Rosella",
                    confidence=0.91,
                    source="test",
                )
            ]

    class FakeRepository:
        def get_species_insights(self, postcode, predictions):
            assert postcode == "3029"
            return [
                SpeciesInsight(
                    prediction=predictions[0],
                    conservation_status="Not listed",
                    local_sighting_count=4,
                    lga_sighting_count=7,
                    victoria_sighting_count=20,
                    latest_local_cached_at=datetime(2026, 1, 1),
                    suburb_name="Tarneit",
                    lga_name="Wyndham",
                )
            ]

    original_classifier = app.state.classifier
    original_repository = app.state.repository
    app.state.classifier = FakeClassifier()
    app.state.repository = FakeRepository()
    try:
        response = TestClient(app).post(
            "/api/epic3/identify",
            data={"postcode": "3029", "top_k": "2"},
            files={"image": ("photo.jpg", b"image-bytes", "image/jpeg")},
        )
    finally:
        app.state.classifier = original_classifier
        app.state.repository = original_repository

    assert response.status_code == 200
    payload = response.json()
    assert payload["postcode"] == "3029"
    assert payload["classifier_mode"] == "test"
    assert payload["predictions"][0]["scientific_name"] == "Platycercus elegans"
    assert payload["species_insights"][0]["local_sighting_count"] == 4
    assert payload["warnings"] == []

