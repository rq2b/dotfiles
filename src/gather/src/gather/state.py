from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, UTC
from pathlib import Path


@dataclass(slots=True)
class GatherState:
    completed_hashes: set[str]
    files_completed: int
    bytes_copied: int


def load_state(path: Path) -> GatherState:
    if not path.exists():
        return GatherState(
            completed_hashes=set(),
            files_completed=0,
            bytes_copied=0,
        )

    data = json.loads(path.read_text(encoding="utf-8"))

    return GatherState(
        completed_hashes=set(data["completed_hashes"]),
        files_completed=data["files_completed"],
        bytes_copied=data["bytes_copied"],
    )


def save_state(
    path: Path,
    state: GatherState,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "version": 1,
        "updated_at": datetime.now(UTC).isoformat(),
        "files_completed": state.files_completed,
        "bytes_copied": state.bytes_copied,
        "completed_hashes": sorted(state.completed_hashes),
    }

    path.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
