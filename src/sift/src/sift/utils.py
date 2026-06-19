from __future__ import annotations

from pathlib import Path
from typing import Iterable, Iterator


def human_bytes(value: int) -> str:
    units = ["B", "KiB", "MiB", "GiB", "TiB", "PiB"]
    size = float(value)
    unit = units[0]
    for candidate in units[1:]:
        if size < 1024.0:
            break
        size /= 1024.0
        unit = candidate
    if unit == "B":
        return f"{int(size)} {unit}"
    return f"{size:.1f} {unit}"


def normalize_extension_candidates(path: Path) -> list[str]:
    suffixes = [suffix.lower() for suffix in path.suffixes]
    if not suffixes:
        return []
    candidates: list[str] = []
    for start in range(len(suffixes)):
        candidate = "".join(suffixes[start:])
        if candidate not in candidates:
            candidates.append(candidate)
    return candidates


def iter_non_empty_lines(values: Iterable[str]) -> Iterator[str]:
    for value in values:
        cleaned = value.strip()
        if cleaned:
            yield cleaned


def relative_display_path(path: Path) -> str:
    return path.as_posix()
