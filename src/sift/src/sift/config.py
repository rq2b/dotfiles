from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

DEFAULT_HISTORICAL_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".jpg",
        ".jpeg",
        ".png",
        ".webp",
        ".gif",
        ".bmp",
        ".tif",
        ".tiff",
        ".psd",
        ".xcf",
        ".ai",
        ".cdr",
        ".svg",
        ".doc",
        ".docx",
        ".odt",
        ".rtf",
        ".txt",
        ".md",
        ".pdf",
        ".xls",
        ".xlsx",
        ".ods",
        ".ppt",
        ".pptx",
        ".csv",
        ".json",
        ".xml",
        ".db",
        ".sqlite",
        ".sqlite3",
        ".html",
        ".css",
        ".js",
        ".php",
        ".zip",
        ".7z",
        ".rar",
        ".tar",
        ".tar.gz",
        ".tar.zst",
    }
)


def _normalize_extension(value: str) -> str:
    ext = value.strip().lower()
    if not ext:
        raise ValueError("empty extension is not allowed")
    if not ext.startswith("."):
        ext = f".{ext}"
    return ext


def load_extensions_file(path: Path) -> frozenset[str]:
    """
    Load a newline-delimited extension list.

    Lines beginning with # are comments.
    """
    values: set[str] = set()
    text = path.read_text(encoding="utf-8")
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        values.add(_normalize_extension(line))
    return frozenset(values)


@dataclass(slots=True)
class SiftConfig:
    historical_extensions: frozenset[str] = field(
        default_factory=lambda: DEFAULT_HISTORICAL_EXTENSIONS
    )
    example_limit: int = 5

    @classmethod
    def from_iterable(
        cls,
        *,
        extensions: Iterable[str] | None = None,
        extensions_file: Path | None = None,
    ) -> "SiftConfig":
        hist = set(DEFAULT_HISTORICAL_EXTENSIONS)
        if extensions_file is not None:
            hist.update(load_extensions_file(extensions_file))
        if extensions is not None:
            for value in extensions:
                hist.add(_normalize_extension(value))
        return cls(historical_extensions=frozenset(hist))
