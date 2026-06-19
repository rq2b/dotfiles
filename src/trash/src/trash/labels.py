from __future__ import annotations

from pathlib import Path

from config import MAX_LABEL_LENGTH
from utils import generate_label_from_paths, sanitize_label


def auto_label(paths: list[Path]) -> str:
    return generate_label_from_paths(paths)


def normalize_label(label: str) -> str:
    return sanitize_label(label, max_length=MAX_LABEL_LENGTH)
