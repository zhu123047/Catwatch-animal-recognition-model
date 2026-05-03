"""Fine-tune an EfficientNet classifier for the EPIC 3 species subset."""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path

from sklearn.model_selection import train_test_split
import torch
from torch import nn
from torch.utils.data import DataLoader, Subset, WeightedRandomSampler
from torchvision import datasets, transforms
from torchvision.models import EfficientNet_B0_Weights, efficientnet_b0
from tqdm import tqdm


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_IMAGES = PROJECT_ROOT / "data" / "epic3" / "images"
DEFAULT_MODEL = PROJECT_ROOT / "models" / "epic3" / "species_classifier.pt"
DEFAULT_LABELS = PROJECT_ROOT / "models" / "epic3" / "labels.json"
DEFAULT_TARGETS = PROJECT_ROOT / "epic3_training" / "species_targets.json"


def load_label_metadata(targets_path: Path) -> dict[str, dict[str, str]]:
    targets = json.loads(targets_path.read_text(encoding="utf-8"))
    return {
        target["scientific_name"].lower().replace(" ", "_"): target
        for target in targets
    }


def export_labels(dataset: datasets.ImageFolder, targets_path: Path, output: Path) -> None:
    metadata = load_label_metadata(targets_path)
    labels = []
    for class_name in dataset.classes:
        target = metadata.get(class_name, {})
        labels.append(
            {
                "scientific_name": target.get(
                    "scientific_name", class_name.replace("_", " ")
                ),
                "common_name": target.get("common_name"),
            }
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(labels, indent=2), encoding="utf-8")


def stratified_split(dataset: datasets.ImageFolder, val_ratio: float) -> tuple[list[int], list[int]]:
    indices = list(range(len(dataset)))
    labels = [dataset.targets[index] for index in indices]
    train_indices, val_indices = train_test_split(
        indices,
        test_size=val_ratio,
        random_state=42,
        stratify=labels,
    )
    return train_indices, val_indices


def build_transforms(weights: EfficientNet_B0_Weights) -> tuple[transforms.Compose, object]:
    mean = weights.transforms().mean
    std = weights.transforms().std
    train_transform = transforms.Compose(
        [
            transforms.Resize((256, 256)),
            transforms.RandomResizedCrop(224, scale=(0.65, 1.0)),
            transforms.RandomHorizontalFlip(),
            transforms.RandomRotation(20),
            transforms.ColorJitter(
                brightness=0.25,
                contrast=0.25,
                saturation=0.25,
                hue=0.03,
            ),
            transforms.ToTensor(),
            transforms.Normalize(mean=mean, std=std),
        ]
    )
    return train_transform, weights.transforms()


def class_weights_for_targets(
    labels: list[int],
    num_classes: int,
    target_class_ids: set[int],
    target_boost: float,
) -> torch.Tensor:
    counts = Counter(labels)
    weights = []
    for class_id in range(num_classes):
        base_weight = 1.0 / max(counts[class_id], 1)
        if class_id in target_class_ids:
            base_weight *= target_boost
        weights.append(base_weight)
    total = sum(weights)
    return torch.tensor([weight * num_classes / total for weight in weights], dtype=torch.float32)


def weighted_sampler(
    labels: list[int],
    class_weights: torch.Tensor,
) -> WeightedRandomSampler:
    sample_weights = [float(class_weights[label]) for label in labels]
    return WeightedRandomSampler(
        weights=sample_weights,
        num_samples=len(sample_weights),
        replacement=True,
    )


def set_trainable_layers(model: nn.Module, unfreeze_blocks: int) -> None:
    for parameter in model.features.parameters():
        parameter.requires_grad = False

    if unfreeze_blocks > 0:
        for block in list(model.features.children())[-unfreeze_blocks:]:
            for parameter in block.parameters():
                parameter.requires_grad = True


def evaluate(
    model: nn.Module,
    loader: DataLoader,
    device: torch.device,
    class_names: list[str],
) -> dict[str, object]:
    model.eval()
    correct = 0
    per_class_correct = {class_name: 0 for class_name in class_names}
    per_class_total = {class_name: 0 for class_name in class_names}
    total = 0
    with torch.no_grad():
        for images, labels in loader:
            images = images.to(device)
            labels = labels.to(device)
            outputs = model(images)
            predicted = outputs.argmax(dim=1)
            correct += (predicted == labels).sum().item()
            total += labels.size(0)
            for expected, actual in zip(labels.cpu().tolist(), predicted.cpu().tolist()):
                class_name = class_names[expected]
                per_class_total[class_name] += 1
                if expected == actual:
                    per_class_correct[class_name] += 1

    per_class_accuracy = {
        class_name: (
            per_class_correct[class_name] / per_class_total[class_name]
            if per_class_total[class_name]
            else 0.0
        )
        for class_name in class_names
    }
    return {
        "accuracy": correct / total if total else 0.0,
        "per_class_accuracy": per_class_accuracy,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--images", type=Path, default=DEFAULT_IMAGES)
    parser.add_argument("--model-output", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--labels-output", type=Path, default=DEFAULT_LABELS)
    parser.add_argument("--targets", type=Path, default=DEFAULT_TARGETS)
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--head-epochs", type=int, default=2)
    parser.add_argument("--unfreeze-blocks", type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--learning-rate", type=float, default=1e-4)
    parser.add_argument("--fine-tune-learning-rate", type=float, default=2e-5)
    parser.add_argument("--val-ratio", type=float, default=0.2)
    parser.add_argument(
        "--target-class",
        action="append",
        default=["gymnorhina_tibicen", "trichoglossus_moluccanus"],
        help="Class folder name to emphasize. Can be passed multiple times.",
    )
    parser.add_argument("--target-boost", type=float, default=1.8)
    args = parser.parse_args()

    weights = EfficientNet_B0_Weights.DEFAULT
    train_transform, val_transform = build_transforms(weights)
    train_dataset = datasets.ImageFolder(args.images, transform=train_transform)
    val_dataset = datasets.ImageFolder(args.images, transform=val_transform)
    if len(train_dataset.classes) < 2:
        raise ValueError("Training requires at least two species folders.")

    train_indices, val_indices = stratified_split(train_dataset, args.val_ratio)
    train_labels = [train_dataset.targets[index] for index in train_indices]
    target_class_ids = {
        train_dataset.class_to_idx[class_name]
        for class_name in args.target_class
        if class_name in train_dataset.class_to_idx
    }
    class_weights = class_weights_for_targets(
        train_labels,
        len(train_dataset.classes),
        target_class_ids,
        args.target_boost,
    )
    sampler = weighted_sampler(train_labels, class_weights)
    train_loader = DataLoader(
        Subset(train_dataset, train_indices),
        batch_size=args.batch_size,
        sampler=sampler,
        num_workers=0,
    )
    val_loader = DataLoader(
        Subset(val_dataset, val_indices),
        batch_size=args.batch_size,
        shuffle=False,
        num_workers=0,
    )

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = efficientnet_b0(weights=weights)
    set_trainable_layers(model, unfreeze_blocks=0)
    in_features = model.classifier[1].in_features
    model.classifier[1] = nn.Linear(in_features, len(train_dataset.classes))
    model = model.to(device)

    criterion = nn.CrossEntropyLoss(weight=class_weights.to(device))
    optimizer = torch.optim.Adam(
        (parameter for parameter in model.parameters() if parameter.requires_grad),
        lr=args.learning_rate,
    )

    best_accuracy = 0.0
    args.model_output.parent.mkdir(parents=True, exist_ok=True)
    for epoch in range(args.epochs):
        if epoch == args.head_epochs:
            set_trainable_layers(model, unfreeze_blocks=args.unfreeze_blocks)
            model = model.to(device)
            optimizer = torch.optim.Adam(
                (parameter for parameter in model.parameters() if parameter.requires_grad),
                lr=args.fine_tune_learning_rate,
            )

        model.train()
        progress = tqdm(train_loader, desc=f"epoch {epoch + 1}/{args.epochs}")
        for images, labels in progress:
            images = images.to(device)
            labels = labels.to(device)
            optimizer.zero_grad()
            loss = criterion(model(images), labels)
            loss.backward()
            optimizer.step()
            progress.set_postfix(loss=f"{loss.item():.4f}")

        metrics = evaluate(model, val_loader, device, train_dataset.classes)
        accuracy = float(metrics["accuracy"])
        print(f"validation_accuracy={accuracy:.4f}")
        for class_name, class_accuracy in metrics["per_class_accuracy"].items():
            if class_name in set(args.target_class):
                print(f"validation_{class_name}_accuracy={class_accuracy:.4f}")
        if accuracy >= best_accuracy:
            best_accuracy = accuracy
            torch.save(
                {
                    "model_state_dict": model.cpu().state_dict(),
                    "classes": train_dataset.classes,
                    "validation_accuracy": best_accuracy,
                    "target_classes": args.target_class,
                },
                args.model_output,
            )
            model = model.to(device)

    export_labels(train_dataset, args.targets, args.labels_output)
    print(f"Saved model to {args.model_output}")
    print(f"Saved labels to {args.labels_output}")


if __name__ == "__main__":
    main()

