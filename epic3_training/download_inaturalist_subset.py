"""Download a small, license-aware iNaturalist subset for EPIC 3 training.

This script intentionally caps species count, images per species, and total
download size so it does not compete with Docker/PostgreSQL storage.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import time
from typing import Any

import requests
from tqdm import tqdm


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TARGETS = PROJECT_ROOT / "epic3_training" / "species_targets.json"
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "epic3" / "images"
DEFAULT_METADATA = PROJECT_ROOT / "data" / "epic3" / "raw" / "observations.jsonl"
INAT_OBSERVATIONS_URL = "https://api.inaturalist.org/v1/observations"
VICTORIA_PLACE_ID = 7830
LICENSES = "cc0,cc-by,cc-by-sa"


def slugify(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    return value.strip("_")


def load_targets(path: Path, limit: int) -> list[dict[str, str]]:
    targets = json.loads(path.read_text(encoding="utf-8"))
    return targets[:limit]


def query_observations(
    taxon_name: str,
    per_page: int,
    page: int,
) -> list[dict[str, Any]]:
    params = {
        "taxon_name": taxon_name,
        "place_id": VICTORIA_PLACE_ID,
        "quality_grade": "research",
        "photos": "true",
        "license": LICENSES,
        "photo_license": LICENSES,
        "per_page": per_page,
        "page": page,
        "order": "desc",
        "order_by": "observed_on",
    }
    response = requests.get(INAT_OBSERVATIONS_URL, params=params, timeout=30)
    response.raise_for_status()
    return response.json().get("results", [])


def best_photo_url(observation: dict[str, Any]) -> str | None:
    photos = observation.get("photos") or []
    if not photos:
        return None
    url = photos[0].get("url")
    if not url:
        return None
    return url.replace("square.", "medium.")


def download_image(url: str, destination: Path, max_bytes: int) -> int:
    with requests.get(url, stream=True, timeout=45) as response:
        response.raise_for_status()
        total = 0
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("wb") as file_obj:
            for chunk in response.iter_content(chunk_size=65536):
                if not chunk:
                    continue
                total += len(chunk)
                if total > max_bytes:
                    destination.unlink(missing_ok=True)
                    raise ValueError(f"Image exceeds per-file limit: {url}")
                file_obj.write(chunk)
    return total


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--targets", type=Path, default=DEFAULT_TARGETS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--metadata", type=Path, default=DEFAULT_METADATA)
    parser.add_argument("--max-species", type=int, default=5)
    parser.add_argument("--images-per-species", type=int, default=80)
    parser.add_argument("--max-total-mb", type=int, default=2048)
    parser.add_argument("--max-image-mb", type=int, default=8)
    parser.add_argument("--sleep", type=float, default=0.3)
    args = parser.parse_args()

    targets = load_targets(args.targets, args.max_species)
    max_total_bytes = args.max_total_mb * 1024 * 1024
    max_image_bytes = args.max_image_mb * 1024 * 1024
    total_bytes = 0
    downloaded = 0

    args.output.mkdir(parents=True, exist_ok=True)
    args.metadata.parent.mkdir(parents=True, exist_ok=True)

    with args.metadata.open("a", encoding="utf-8") as metadata_file:
        for target in targets:
            class_dir = args.output / slugify(target["scientific_name"])
            class_dir.mkdir(parents=True, exist_ok=True)
            existing = list(class_dir.glob("*.jpg"))
            if len(existing) >= args.images_per_species:
                continue

            species_count = len(existing)
            page = 1
            per_page = 200
            progress = tqdm(
                total=args.images_per_species,
                initial=species_count,
                desc=target["scientific_name"],
                unit="img",
            )
            while species_count < args.images_per_species:
                observations = query_observations(
                    target["taxon_name"],
                    per_page=per_page,
                    page=page,
                )
                if not observations:
                    break

                for observation in observations:
                    if species_count >= args.images_per_species:
                        break
                    if total_bytes >= max_total_bytes:
                        print("Reached total download limit; stopping.")
                        progress.close()
                        return

                    url = best_photo_url(observation)
                    if not url:
                        continue

                    destination = class_dir / f"{observation['id']}.jpg"
                    if destination.exists():
                        continue

                    try:
                        size = download_image(url, destination, max_image_bytes)
                    except Exception as exc:
                        print(f"Skipping {url}: {exc}")
                        continue

                    metadata_file.write(
                        json.dumps(
                            {
                                "observation_id": observation["id"],
                                "scientific_name": target["scientific_name"],
                                "common_name": target.get("common_name"),
                                "image_path": str(destination),
                                "photo_url": url,
                                "license_code": observation.get("license_code"),
                            },
                            ensure_ascii=True,
                        )
                        + "\n"
                    )
                    metadata_file.flush()
                    total_bytes += size
                    downloaded += 1
                    species_count += 1
                    progress.update(1)
                    time.sleep(args.sleep)

                page += 1
                if species_count >= args.images_per_species:
                    break
            progress.close()

    print(f"Downloaded {downloaded} images, {total_bytes / (1024 * 1024):.1f} MB.")


if __name__ == "__main__":
    main()

