from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class TransactionItem:
    original_path: str
    stored_relpath: str
    kind: str  # "file" | "directory" | "symlink" | "other"


@dataclass(slots=True)
class TransactionMetadata:
    id: str
    label: str
    device: str
    created_unix: int
    created_iso: str
    action: str
    status: str
    original_paths: list[str]
    stored_path: str
    size_bytes: int
    file_count: int
    directory_count: int
    items: list[TransactionItem] = field(default_factory=list)
    checksum: str | None = None
    tags: list[str] = field(default_factory=list)
    notes: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)
    tombstone: bool = False
    version: str = "v2"

@dataclass(slots=True)
class TransactionState:
    state: str
    started_unix: int | None = None
    completed_unix: int | None = None
    purged_unix: int | None = None
    restored_unix: int | None = None
    error: str | None = None
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class JobRecord:
    transaction_id: str
    pid: int | None
    status: str
    started_unix: int
    updated_unix: int | None = None
    error: str | None = None
    detail: dict[str, Any] = field(default_factory=dict)
