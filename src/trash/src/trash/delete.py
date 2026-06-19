from __future__ import annotations

from pathlib import Path

from config import DEVICE, TRANSACTIONS_DIR
from filesystem import (
    remove_path,
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
from remove import create_transaction_id, resolve_label
from utils import now_iso, now_unix


def perform_delete(
    paths: list[Path],
    *,
    explicit_label: str | None,
    dry_run: bool,
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
            action="delete",
            status="dry-run",
            original_paths=original_paths,
            stored_path=stored_path,
            size_bytes=stats.size_bytes,
            file_count=stats.file_count,
            directory_count=stats.directory_count,
            tombstone=True,
        )

    TRANSACTIONS_DIR.mkdir(parents=True, exist_ok=True)
    transaction_path.mkdir(parents=True, exist_ok=True)

    detail = {
        "label": label,
        "original_paths": original_paths,
        "size_bytes": stats.size_bytes,
        "file_count": stats.file_count,
        "directory_count": stats.directory_count,
        "stored_path": stored_path,
        "device": DEVICE,
        "created_iso": created_iso,
        "transaction_type": "tombstone",
    }

    write_state(
        transaction_id,
        create_running_state(
            created_unix,
            detail=detail,
        ),
    )

    for path in paths:
        remove_path(path)

    metadata = TransactionMetadata(
        id=transaction_id,
        label=label,
        device=DEVICE,
        created_unix=created_unix,
        created_iso=created_iso,
        action="delete",
        status="complete",
        original_paths=original_paths,
        stored_path=stored_path,
        size_bytes=stats.size_bytes,
        file_count=stats.file_count,
        directory_count=stats.directory_count,
        tombstone=True,
    )

    write_metadata(metadata)

    write_state(
        transaction_id,
        create_complete_state(
            created_unix,
            now_unix(),
            detail=detail,
        ),
    )

    rebuild_index()

    return metadata
