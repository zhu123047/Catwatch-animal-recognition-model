"""Torchvision ImageNet fallback classifier."""

from __future__ import annotations

from epic3_api.schemas import Prediction

from .preprocess import open_rgb_image


class ImageNetClassifier:
    """Real image classifier using torchvision's ImageNet-pretrained weights."""

    mode = "imagenet"

    def __init__(self) -> None:
        try:
            import torch
            from torchvision.models import EfficientNet_B0_Weights, efficientnet_b0
        except ImportError as exc:
            raise RuntimeError(
                "ImageNet classifier requires torch, torchvision, and pillow. "
                "Install requirements-epic3.txt first."
            ) from exc

        self._torch = torch
        self._weights = EfficientNet_B0_Weights.DEFAULT
        self._model = efficientnet_b0(weights=self._weights)
        self._model.eval()
        self._preprocess = self._weights.transforms()
        self._categories: list[str] = self._weights.meta["categories"]

    def classify_image(self, image_bytes: bytes, top_k: int = 3) -> list[Prediction]:
        if not image_bytes:
            raise ValueError("Uploaded image is empty.")
        if top_k < 1:
            raise ValueError("top_k must be at least 1.")

        image = open_rgb_image(image_bytes)
        batch = self._preprocess(image).unsqueeze(0)

        with self._torch.no_grad():
            probabilities = self._model(batch).softmax(dim=1)[0]
            scores, indices = self._torch.topk(
                probabilities, k=min(top_k, len(self._categories))
            )

        predictions: list[Prediction] = []
        for score, index in zip(scores.tolist(), indices.tolist()):
            label = self._categories[index]
            predictions.append(
                Prediction(
                    scientific_name=label,
                    common_name=label,
                    confidence=round(float(score), 4),
                    source=self.mode,
                )
            )
        return predictions

