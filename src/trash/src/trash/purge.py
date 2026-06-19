from __future__ import annotations

from filesystem import remove_path
from metadata import (
    create_purged_state,
    read_state,
    rebuild_index,
    transaction_dir,
    write_state,
)
from utils import now_unix


def perform_purge(transaction_id: str) -> None:
    tdir = transaction_dir(transaction_id)
    contents = tdir / "contents"
    previous = read_state(transaction_id)

    if contents.exists():
        for child in sorted(contents.iterdir(), key=lambda p: p.name):
            remove_path(child)

    write_state(transaction_id, create_purged_state(previous, now_unix()))
    rebuild_index()
