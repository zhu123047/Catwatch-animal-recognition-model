"""Shared image preprocessing helpers."""

from __future__ import annotations

from io import BytesIO


def open_rgb_image(image_bytes: bytes):
    from PIL import Image

    image = Image.open(BytesIO(image_bytes))
    return image.convert("RGB")

