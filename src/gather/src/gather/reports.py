from __future__ import annotations

import csv
import json
from dataclasses import asdict
from pathlib import Path
from typing import Iterable

from models import CopyFailure, ManifestEntry, SelectedEntry


def write_duplicate_groups_csv(
    path: Path, selected: dict[str, SelectedEntry], counts: dict[str, int]
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["sha256", "count", "chosen_path"])
        for sha256 in sorted(selected):
            count = counts.get(sha256, 0)
            if count <= 1:
                continue
            chosen = selected[sha256]
            writer.writerow(
                [
                    sha256,
                    count,
                    chosen.entry.dataset + "/" + chosen.entry.relative_path.as_posix(),
                ]
            )


def write_skipped_duplicates_csv(
    path: Path, rows: Iterable[tuple[str, str, str]]
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["sha256", "path", "reason"])
        for row in rows:
            writer.writerow(row)


def write_extensions_csv(path: Path, rows: Iterable[tuple[str, int, int]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["Extension", "Count", "Size"])
        for row in rows:
            writer.writerow(row)


def write_report_json(path: Path, report: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
