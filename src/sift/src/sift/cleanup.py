from __future__ import annotations

from pathlib import Path

from filesystem import remove_empty_dirs


def cleanup_empty_directories(source: Path) -> int:
    return remove_empty_dirs(source)
