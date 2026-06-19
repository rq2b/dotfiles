from __future__ import annotations

from filesystem import restore_items_from_transaction
from metadata import (
    create_restored_state,
    read_metadata,
    read_state,
    rebuild_index,
    transaction_dir,
    write_state,
)
from utils import now_unix


def perform_restore(transaction_id: str, *, overwrite: bool) -> None:
    tdir = transaction_dir(transaction_id)
    metadata = read_metadata(transaction_id)

    if metadata.tombstone:
        raise RuntimeError(
            "Transaction is a tombstone and cannot be restored."
        )

    previous = read_state(transaction_id)

    restore_items_from_transaction(tdir, metadata.items, overwrite=overwrite)

    write_state(transaction_id, create_restored_state(previous, now_unix()))
    rebuild_index()
