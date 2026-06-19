from __future__ import annotations

from pathlib import Path

from metadata import read_metadata, read_state, transaction_dir


def load_transaction_paths(transaction_id: str) -> tuple[Path, Path]:
    tdir = transaction_dir(transaction_id)
    return tdir / "metadata.json", tdir / "state.json"


def transaction_exists(transaction_id: str) -> bool:
    return transaction_dir(transaction_id).exists()
