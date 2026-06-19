from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from config import JOBS_DIR
from metadata import read_job, write_job
from models import JobRecord
from utils import now_unix


def spawn_metadata_worker(transaction_id: str) -> int:
    script = Path(__file__).with_name("main.py")
    command = [sys.executable, str(script), "_worker", "metadata", transaction_id]
    creationflags = 0
    kwargs: dict[str, object] = {
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "stdin": subprocess.DEVNULL,
        "start_new_session": True,
        "cwd": str(Path(__file__).resolve().parent),
    }
    if os.name == "nt":
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS  # type: ignore[attr-defined]
        kwargs["creationflags"] = creationflags

    proc = subprocess.Popen(command, **kwargs)  # type: ignore[arg-type]
    return int(proc.pid or 0)


def create_job(
    transaction_id: str,
    pid: int | None,
    status: str = "running",
    *,
    detail: dict | None = None,
) -> JobRecord:
    record = JobRecord(
        transaction_id=transaction_id,
        pid=pid,
        status=status,
        started_unix=now_unix(),
        updated_unix=None,
        error=None,
        detail=dict(detail or {}),
    )
    write_job(record)
    return record


def update_job(
    record: JobRecord,
    *,
    status: str | None = None,
    error: str | None = None,
    detail: dict | None = None,
) -> JobRecord:
    updated = JobRecord(
        transaction_id=record.transaction_id,
        pid=record.pid,
        status=status or record.status,
        started_unix=record.started_unix,
        updated_unix=now_unix(),
        error=error,
        detail=dict(detail or record.detail),
    )
    write_job(updated)
    return updated


def get_job(transaction_id: str) -> JobRecord | None:
    path = JOBS_DIR / f"{transaction_id}.json"
    if not path.exists():
        return None
    return read_job(transaction_id)
