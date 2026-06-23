from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True, frozen=True)
class ManifestEntry:
    sha256: str
    dataset: str
    relative_path: Path


@dataclass(slots=True)
class SelectedEntry:
    entry: ManifestEntry
    source_path: Path
    destination_path: Path
    score: tuple[int, int, int, int, int, str]
    size_bytes: int = 0


@dataclass(slots=True)
class CopyFailure:
    entry: ManifestEntry
    source_path: Path
    destination_path: Path
    reason: str
