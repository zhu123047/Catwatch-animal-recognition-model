"""Image classification adapters for EPIC 3."""

from __future__ import annotations

from dataclasses import dataclass
import csv
import hashlib
import json
from pathlib import Path
from typing import Protocol

from .schemas import Prediction


DEFAULT_LABELS = [
    {
        "scientific_name": "Platycercus elegans",
        "common_name": "Crimson Rosella",
    },
    {
        "scientific_name": "Trichosurus vulpecula",
        "common_name": "Common Brushtail Possum",
    },
    {
        "scientific_name": "Trichoglossus moluccanus",
        "common_name": "Rainbow Lorikeet",
    },
    {
        "scientific_name": "Gymnorhina tibicen",
        "common_name": "Australian Magpie",
    },
    {
        "scientific_name": "Anas superciliosa",
        "common_name": "Pacific Black Duck",
    },
]


@dataclass(frozen=True)
class Label:
    scientific_name: str
    common_name: str | None = None


class SpeciesClassifier(Protocol):
    mode: str

    def classify_image(self, image_bytes: bytes, top_k: int = 3) -> list[Prediction]:
        ...


class DemoSpeciesClassifier:
    """Deterministic classifier used until a trained local model is available."""

    mode = "demo"

    def __init__(self, labels_path: str | None = None) -> None:
        self.labels = self._load_labels(labels_path)

    def classify_image(self, image_bytes: bytes, top_k: int = 3) -> list[Prediction]:
        if not image_bytes:
            raise ValueError("Uploaded image is empty.")
        if top_k < 1:
            raise ValueError("top_k must be at least 1.")

        digest = hashlib.sha256(image_bytes).digest()
        offset = digest[0] % len(self.labels)
        ordered = self.labels[offset:] + self.labels[:offset]
        limited = ordered[: min(top_k, len(ordered))]

        predictions: list[Prediction] = []
        for index, label in enumerate(limited):
            confidence = max(0.15, 0.86 - (index * 0.17))
            predictions.append(
                Prediction(
                    scientific_name=label.scientific_name,
                    common_name=label.common_name,
                    confidence=round(confidence, 2),
                    source=self.mode,
                )
            )
        return predictions

    def _load_labels(self, labels_path: str | None) -> list[Label]:
        if not labels_path:
            return [Label(**label) for label in DEFAULT_LABELS]

        path = Path(labels_path)
        if not path.exists():
            raise FileNotFoundError(f"Labels file not found: {path}")

        if path.suffix.lower() == ".json":
            raw = json.loads(path.read_text(encoding="utf-8"))
            return [self._label_from_object(item) for item in raw]

        if path.suffix.lower() == ".csv":
            with path.open(newline="", encoding="utf-8") as file_obj:
                reader = csv.DictReader(file_obj)
                return [
                    Label(
                        scientific_name=row["scientific_name"],
                        common_name=row.get("common_name") or None,
                    )
                    for row in reader
                ]

        raise ValueError("Labels file must be JSON or CSV.")

    @staticmethod
    def _label_from_object(item: object) -> Label:
        if isinstance(item, str):
            return Label(scientific_name=item)
        if isinstance(item, dict):
            return Label(
                scientific_name=str(item["scientific_name"]),
                common_name=item.get("common_name"),
            )
        raise ValueError("Each label must be a string or object.")


def build_classifier(
    model_path: str | None,
    labels_path: str | None,
    backend: str = "auto",
) -> SpeciesClassifier:
    normalized_backend = backend.lower().strip()
    demo_labels_path = labels_path if labels_path and Path(labels_path).exists() else None

    if normalized_backend == "demo":
        return DemoSpeciesClassifier(labels_path=demo_labels_path)

    if normalized_backend in {"species", "species_finetuned"}:
        from .ml.species_classifier import FineTunedSpeciesClassifier

        if not model_path or not labels_path:
            raise ValueError("EPIC3_MODEL_PATH and EPIC3_LABELS_PATH are required.")
        return FineTunedSpeciesClassifier(model_path, labels_path)

    if normalized_backend == "imagenet":
        from .ml.imagenet_classifier import ImageNetClassifier

        return ImageNetClassifier()

    if normalized_backend != "auto":
        raise ValueError(
            "EPIC3_CLASSIFIER_BACKEND must be auto, species_finetuned, imagenet, or demo."
        )

    if model_path and labels_path and Path(model_path).exists() and Path(labels_path).exists():
        try:
            from .ml.species_classifier import FineTunedSpeciesClassifier

            return FineTunedSpeciesClassifier(model_path, labels_path)
        except Exception:
            # Keep the API available; ImageNet remains a real vision model fallback.
            pass

    try:
        from .ml.imagenet_classifier import ImageNetClassifier

        return ImageNetClassifier()
    except Exception:
        # Last-resort fallback for environments where ML dependencies are not installed.
        pass

    return DemoSpeciesClassifier(labels_path=demo_labels_path)

