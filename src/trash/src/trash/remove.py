from __future__ import annotations

from pathlib import Path

from config import DEVICE, TRANSACTIONS_DIR
from filesystem import (
    move_paths_into_transaction,
    scan_paths_stats,
    validate_non_overlapping_paths,
)
from labels import auto_label, normalize_label
from metadata import (
    create_complete_state,
    create_running_state,
    rebuild_index,
    transaction_dir,
    write_metadata,
    write_state,
)
from models import TransactionMetadata
from utils import human_size, now_iso, now_unix, prompt_for_label


def create_transaction_id(label: str, created_unix: int) -> str:
    tid = f"{created_unix}_{label}"
    candidate = tid
    while transaction_dir(candidate).exists():
        created_unix += 1
        candidate = f"{created_unix}_{label}"
    return candidate


def resolve_label(paths: list[Path], explicit_label: str | None) -> str:
    if explicit_label is not None:
        label = normalize_label(explicit_label)
        if label:
            return label
    label = auto_label(paths)
    if label:
        return label
    return prompt_for_label()


def perform_remove(
    paths: list[Path],
    *,
    explicit_label: str | None,
    dry_run: bool,
    sync: bool,
) -> TransactionMetadata:
    if not paths:
        raise ValueError("No paths supplied.")

    validate_non_overlapping_paths(paths)

    created_unix = now_unix()
    created_iso = now_iso()
    label = resolve_label(paths, explicit_label)
    transaction_id = create_transaction_id(label, created_unix)
    transaction_path = transaction_dir(transaction_id)

    stats = scan_paths_stats(paths)
    stored_path = str(transaction_path)
    original_paths = [str(path) for path in paths]

    if dry_run:
        return TransactionMetadata(
            id=transaction_id,
            label=label,
            device=DEVICE,
            created_unix=created_unix,
            created_iso=created_iso,
            action="move",
            status="dry-run",
            original_paths=original_paths,
            stored_path=stored_path,
            size_bytes=stats.size_bytes,
            file_count=stats.file_count,
            directory_count=stats.directory_count,
            items=[],
            extra={
                "dry_run": True,
                "estimated_size_human": human_size(stats.size_bytes),
            },
        )

    TRANSACTIONS_DIR.mkdir(parents=True, exist_ok=True)
    transaction_path.mkdir(parents=True, exist_ok=True)
    (transaction_path / "contents").mkdir(parents=True, exist_ok=True)

    detail = {
        "label": label,
        "original_paths": original_paths,
        "size_bytes": stats.size_bytes,
        "file_count": stats.file_count,
        "directory_count": stats.directory_count,
        "stored_path": stored_path,
        "device": DEVICE,
        "created_iso": created_iso,
    }
    write_state(transaction_id, create_running_state(created_unix, detail=detail))

    items = move_paths_into_transaction(paths, transaction_path)

    if sync:
        final_metadata = TransactionMetadata(
            id=transaction_id,
            label=label,
            device=DEVICE,
            created_unix=created_unix,
            created_iso=created_iso,
            action="move",
            status="complete",
            original_paths=original_paths,
            stored_path=stored_path,
            size_bytes=stats.size_bytes,
            file_count=stats.file_count,
            directory_count=stats.directory_count,
            items=items,
        )
        write_metadata(final_metadata)
        write_state(
            transaction_id,
            create_complete_state(created_unix, now_unix(), detail=detail),
        )
        rebuild_index()
        return final_metadata

    return TransactionMetadata(
        id=transaction_id,
        label=label,
        device=DEVICE,
        created_unix=created_unix,
        created_iso=created_iso,
        action="move",
        status="running",
        original_paths=original_paths,
        stored_path=stored_path,
        size_bytes=stats.size_bytes,
        file_count=stats.file_count,
        directory_count=stats.directory_count,
        items=items,
    )
