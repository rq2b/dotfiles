from __future__ import annotations

from pathlib import Path
from typing import Iterator

from models import ManifestEntry


def discover_manifest_files(
    source_root: Path,
    manifest_name: str,
) -> Iterator[Path]:
    for dataset_dir in source_root.iterdir():
        if not dataset_dir.is_dir():
            continue

        manifest = dataset_dir / "meta" / manifest_name

        if manifest.is_file():
            yield manifest


def dataset_name_from_manifest(manifest_path: Path, source_root: Path) -> str:
    relative = manifest_path.relative_to(source_root)
    if len(relative.parts) < 2:
        raise ValueError(
            f"Manifest path is not inside a dataset/meta layout: {manifest_path}"
        )
    return relative.parts[0]


def iter_manifest_entries(
    manifest_path: Path, source_root: Path
) -> Iterator[ManifestEntry]:
    dataset = dataset_name_from_manifest(manifest_path, source_root)
    with manifest_path.open("r", encoding="utf-8", errors="strict") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith("#"):
                continue
            parts = line.split(maxsplit=1)
            if len(parts) != 2:
                raise ValueError(
                    f"Invalid manifest line {manifest_path}:{line_number}: {line!r}"
                )
            sha256, raw_path = parts
            rel_text = raw_path.strip()
            if rel_text.startswith("./"):
                rel_text = rel_text[2:]
            rel_path = Path(rel_text)
            yield ManifestEntry(sha256=sha256, dataset=dataset, relative_path=rel_path)
