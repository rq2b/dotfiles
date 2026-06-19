from __future__ import annotations

import csv
from dataclasses import asdict
from pathlib import Path

from config import INDEX_FILE, JOBS_DIR, TRANSACTIONS_DIR
from models import JobRecord, TransactionItem, TransactionMetadata, TransactionState
from utils import atomic_write_json, atomic_write_text, read_json


def transaction_dir(transaction_id: str) -> Path:
    return TRANSACTIONS_DIR / transaction_id


def metadata_file(transaction_id: str) -> Path:
    return transaction_dir(transaction_id) / "metadata.json"


def state_file(transaction_id: str) -> Path:
    return transaction_dir(transaction_id) / "state.json"


def job_file(transaction_id: str) -> Path:
    return JOBS_DIR / f"{transaction_id}.json"


def write_metadata(metadata: TransactionMetadata) -> None:
    atomic_write_json(metadata_file(metadata.id), asdict(metadata))


def write_state(transaction_id: str, state: TransactionState) -> None:
    atomic_write_json(state_file(transaction_id), asdict(state))


def write_job(job: JobRecord) -> None:
    atomic_write_json(job_file(job.transaction_id), asdict(job))


def read_metadata(transaction_id: str) -> TransactionMetadata:
    data = read_json(metadata_file(transaction_id))
    return TransactionMetadata(
        id=data["id"],
        label=data["label"],
        device=data["device"],
        created_unix=data["created_unix"],
        created_iso=data["created_iso"],
        action=data["action"],
        status=data["status"],
        original_paths=list(data["original_paths"]),
        stored_path=data["stored_path"],
        size_bytes=data["size_bytes"],
        file_count=data["file_count"],
        directory_count=data["directory_count"],
        items=[
            TransactionItem(
                original_path=item["original_path"],
                stored_relpath=item["stored_relpath"],
                kind=item.get("kind", "file"),
            )
            for item in data.get("items", [])
        ],
        checksum=data.get("checksum"),
        tags=list(data.get("tags", [])),
        notes=data.get("notes"),
        extra=dict(data.get("extra", {})),
        tombstone=bool(data.get("tombstone", False)),
        version=data.get("version")
    )


def read_state(transaction_id: str) -> TransactionState:
    data = read_json(state_file(transaction_id))
    return TransactionState(
        state=data["state"],
        started_unix=data.get("started_unix"),
        completed_unix=data.get("completed_unix"),
        purged_unix=data.get("purged_unix"),
        restored_unix=data.get("restored_unix"),
        error=data.get("error"),
        detail=dict(data.get("detail", {})),
    )


def read_job(transaction_id: str) -> JobRecord:
    data = read_json(job_file(transaction_id))
    return JobRecord(
        transaction_id=data["transaction_id"],
        pid=data.get("pid"),
        status=data["status"],
        started_unix=data["started_unix"],
        updated_unix=data.get("updated_unix"),
        error=data.get("error"),
        detail=dict(data.get("detail", {})),
    )


def _transaction_sort_key(directory: Path) -> tuple[int, str]:
    try:
        ts = int(directory.name.split("_", 1)[0])
    except Exception:
        ts = 0
    return (ts, directory.name)


def rebuild_index() -> None:
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    rows: list[list[str]] = [
        [
            "id",
            "state",
            "label",
            "device",
            "created_iso",
            "stored_path",
            "original_paths",
        ]
    ]

    if TRANSACTIONS_DIR.exists():
        for transaction_dir_path in sorted(
            (p for p in TRANSACTIONS_DIR.iterdir() if p.is_dir()),
            key=_transaction_sort_key,
        ):
            tid = transaction_dir_path.name
            meta_path = transaction_dir_path / "metadata.json"
            state_path = transaction_dir_path / "state.json"

            if meta_path.exists():
                try:
                    meta = read_json(meta_path)
                except Exception:
                    meta = {}
            else:
                meta = {}

            if state_path.exists():
                try:
                    state = read_json(state_path)
                    state_name = state.get("state", "unknown")
                    detail = dict(state.get("detail", {}))
                except Exception:
                    state_name = "unknown"
                    detail = {}
            else:
                state_name = meta.get("status", "unknown")
                detail = {}

            label = meta.get("label") or detail.get("label", "")
            device = meta.get("device") or detail.get("device", "")
            created_iso = meta.get("created_iso") or detail.get("created_iso", "")
            stored_path = meta.get("stored_path") or detail.get("stored_path", "")
            original_paths = meta.get("original_paths") or detail.get(
                "original_paths", []
            )

            rows.append(
                [
                    tid,
                    str(state_name),
                    str(label),
                    str(device),
                    str(created_iso),
                    str(stored_path),
                    " | ".join(map(str, original_paths)),
                ]
            )

    lines = ["\t".join(row) for row in rows]
    atomic_write_text(INDEX_FILE, "\n".join(lines) + "\n")


def read_index_rows() -> list[dict[str, str]]:
    if not INDEX_FILE.exists():
        return []
    with INDEX_FILE.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        return [dict(row) for row in reader]


def create_running_state(
    started_unix: int, *, detail: dict | None = None
) -> TransactionState:
    return TransactionState(
        state="running", started_unix=started_unix, detail=dict(detail or {})
    )


def create_complete_state(
    started_unix: int | None, completed_unix: int, *, detail: dict | None = None
) -> TransactionState:
    return TransactionState(
        state="complete",
        started_unix=started_unix,
        completed_unix=completed_unix,
        detail=dict(detail or {}),
    )


def create_purged_state(
    previous: TransactionState | None, purged_unix: int
) -> TransactionState:
    return TransactionState(
        state="purged",
        started_unix=previous.started_unix if previous else None,
        completed_unix=previous.completed_unix if previous else None,
        purged_unix=purged_unix,
        restored_unix=previous.restored_unix if previous else None,
        error=previous.error if previous else None,
        detail=dict(previous.detail) if previous else {},
    )


def create_restored_state(
    previous: TransactionState | None, restored_unix: int
) -> TransactionState:
    return TransactionState(
        state="restored",
        started_unix=previous.started_unix if previous else None,
        completed_unix=previous.completed_unix if previous else None,
        purged_unix=previous.purged_unix if previous else None,
        restored_unix=restored_unix,
        error=previous.error if previous else None,
        detail=dict(previous.detail) if previous else {},
    )
