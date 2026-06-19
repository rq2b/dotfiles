from __future__ import annotations

from pathlib import Path

from config import SiftConfig
from models import Bucket
from utils import normalize_extension_candidates


def classify_extension(path: Path, config: SiftConfig) -> tuple[Bucket, str | None]:
    """
    Determine the target bucket for a file based on extension.
    """
    candidates = normalize_extension_candidates(path)
    if not candidates:
        return Bucket.UNKNOWN, None

    for candidate in candidates:
        if candidate in config.historical_extensions:
            return Bucket.HISTORICAL, candidate

    return Bucket.RESIDUAL, candidates[0]
