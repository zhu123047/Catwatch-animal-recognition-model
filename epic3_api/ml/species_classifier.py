"""Fine-tuned Australian species classifier."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from epic3_api.schemas import Prediction

from .preprocess import open_rgb_image


@dataclass(frozen=True)
class SpeciesLabel:
    """Human-readable metadata for one classifier output class."""

    scientific_name: str
    common_name: str | None = None


class FineTunedSpeciesClassifier:
    """Loads a locally fine-tuned EfficientNet model exported by training scripts."""

    mode = "species_finetuned"

    def __init__(self, model_path: str, labels_path: str) -> None:
        # Import torch lazily so the API can still start with other backends
        # when the ML dependencies are not installed.
        try:
            import torch
            from torchvision.models import EfficientNet_B0_Weights, efficientnet_b0
        except ImportError as exc:
            raise RuntimeError(
                "Fine-tuned classifier requires torch, torchvision, and pillow. "
                "Install requirements-epic3.txt first."
            ) from exc

        self.model_path = Path(model_path)
        self.labels_path = Path(labels_path)
        if not self.model_path.exists():
            raise FileNotFoundError(f"Model file not found: {self.model_path}")
        if not self.labels_path.exists():
            raise FileNotFoundError(f"Labels file not found: {self.labels_path}")

        # Reuse the same ImageNet preprocessing that was used during fine-tuning.
        self._torch = torch
        self._weights = EfficientNet_B0_Weights.DEFAULT
        self._preprocess = self._weights.transforms()
        self._labels = self._load_labels(self.labels_path)

        # Build the EfficientNet-B0 architecture and replace the classifier head
        # with the number of Australian species labels in labels.json.
        self._model = efficientnet_b0(weights=None)
        in_features = self._model.classifier[1].in_features
        self._model.classifier[1] = torch.nn.Linear(in_features, len(self._labels))

        # Training scripts may save either a plain state dict or a checkpoint dict.
        checkpoint = torch.load(self.model_path, map_location="cpu")
        state_dict = checkpoint.get("model_state_dict", checkpoint)
        self._model.load_state_dict(state_dict)
        self._model.eval()

    def classify_image(self, image_bytes: bytes, top_k: int = 3) -> list[Prediction]:
        if not image_bytes:
            raise ValueError("Uploaded image is empty.")
        if top_k < 1:
            raise ValueError("top_k must be at least 1.")

        image = open_rgb_image(image_bytes)
        batch = self._preprocess(image).unsqueeze(0)

        # Run CPU inference without gradients, then convert logits to probabilities.
        with self._torch.no_grad():
            probabilities = self._model(batch).softmax(dim=1)[0]
            scores, indices = self._torch.topk(
                probabilities, k=min(top_k, len(self._labels))
            )

        predictions: list[Prediction] = []
        for score, index in zip(scores.tolist(), indices.tolist()):
            label = self._labels[index]
            predictions.append(
                Prediction(
                    scientific_name=label.scientific_name,
                    common_name=label.common_name,
                    confidence=round(float(score), 4),
                    source=self.mode,
                )
            )
        return predictions

    @staticmethod
    def _load_labels(labels_path: Path) -> list[SpeciesLabel]:
        """Load labels exported alongside the fine-tuned model."""

        raw = json.loads(labels_path.read_text(encoding="utf-8"))
        labels: list[SpeciesLabel] = []
        for item in raw:
            if isinstance(item, str):
                labels.append(SpeciesLabel(scientific_name=item))
            else:
                labels.append(
                    SpeciesLabel(
                        scientific_name=str(item["scientific_name"]),
                        common_name=item.get("common_name"),
                    )
                )
        if not labels:
            raise ValueError("Labels file must contain at least one class.")
        return labels

