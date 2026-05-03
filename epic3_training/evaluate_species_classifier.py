"""Evaluate the exported EPIC 3 fine-tuned species classifier."""

from __future__ import annotations

import argparse
from pathlib import Path

import torch
from torch.utils.data import DataLoader
from torchvision import datasets
from torchvision.models import EfficientNet_B0_Weights, efficientnet_b0


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_IMAGES = PROJECT_ROOT / "data" / "epic3" / "images"
DEFAULT_MODEL = PROJECT_ROOT / "models" / "epic3" / "species_classifier.pt"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--images", type=Path, default=DEFAULT_IMAGES)
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--batch-size", type=int, default=8)
    args = parser.parse_args()

    weights = EfficientNet_B0_Weights.DEFAULT
    dataset = datasets.ImageFolder(args.images, transform=weights.transforms())
    loader = DataLoader(dataset, batch_size=args.batch_size, shuffle=False, num_workers=0)

    model = efficientnet_b0(weights=None)
    in_features = model.classifier[1].in_features
    model.classifier[1] = torch.nn.Linear(in_features, len(dataset.classes))
    checkpoint = torch.load(args.model, map_location="cpu")
    model.load_state_dict(checkpoint.get("model_state_dict", checkpoint))
    model.eval()

    correct_top1 = 0
    correct_top3 = 0
    total = 0
    per_class = {
        class_name: {"total": 0, "top1": 0, "top3": 0}
        for class_name in dataset.classes
    }
    with torch.no_grad():
        for images, labels in loader:
            outputs = model(images)
            top3 = outputs.topk(k=min(3, len(dataset.classes)), dim=1).indices
            correct_top1 += (top3[:, 0] == labels).sum().item()
            correct_top3 += (top3 == labels.unsqueeze(1)).any(dim=1).sum().item()
            total += labels.size(0)
            for expected, predictions in zip(labels.tolist(), top3.tolist()):
                class_name = dataset.classes[expected]
                per_class[class_name]["total"] += 1
                if predictions[0] == expected:
                    per_class[class_name]["top1"] += 1
                if expected in predictions:
                    per_class[class_name]["top3"] += 1

    print(f"samples={total}")
    print(f"top1_accuracy={correct_top1 / total:.4f}")
    print(f"top3_accuracy={correct_top3 / total:.4f}")
    for class_name, metrics in per_class.items():
        class_total = metrics["total"]
        if not class_total:
            continue
        top1 = metrics["top1"] / class_total
        top3 = metrics["top3"] / class_total
        print(f"{class_name}: top1={top1:.4f} top3={top3:.4f} samples={class_total}")


if __name__ == "__main__":
    main()

