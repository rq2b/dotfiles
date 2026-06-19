from __future__ import annotations

import os
import shutil
from pathlib import Path


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _copy_symlink(source: Path, destination: Path, *, overwrite: bool) -> None:
    if destination.exists() or destination.is_symlink():
        if not overwrite:
            raise FileExistsError(str(destination))
        if destination.is_dir() and not destination.is_symlink():
            raise IsADirectoryError(str(destination))
        destination.unlink()
    ensure_parent(destination)
    target = os.readlink(source)
    os.symlink(target, destination)


def copy_entry(
    source: Path, destination: Path, *, overwrite: bool, skip_existing: bool
) -> str:
    if destination.exists() or destination.is_symlink():
        if skip_existing:
            return "skip"
        if not overwrite:
            raise FileExistsError(str(destination))
        if destination.is_dir() and not destination.is_symlink():
            raise IsADirectoryError(str(destination))
        if destination.is_symlink() or destination.is_file():
            destination.unlink()
        elif destination.exists():
            shutil.rmtree(destination)

    ensure_parent(destination)
    if source.is_symlink():
        _copy_symlink(source, destination, overwrite=overwrite)
    else:
        shutil.copy2(source, destination)
    return "copy"


def move_entry(
    source: Path, destination: Path, *, overwrite: bool, skip_existing: bool
) -> str:
    if destination.exists() or destination.is_symlink():
        if skip_existing:
            return "skip"
        if not overwrite:
            raise FileExistsError(str(destination))
        if destination.is_dir() and not destination.is_symlink():
            shutil.rmtree(destination)
        else:
            destination.unlink()

    ensure_parent(destination)
    shutil.move(str(source), str(destination))
    return "move"


def process_entry(
    source: Path,
    destination: Path,
    *,
    move: bool,
    overwrite: bool,
    skip_existing: bool,
) -> str:
    if move:
        return move_entry(
            source, destination, overwrite=overwrite, skip_existing=skip_existing
        )
    return copy_entry(
        source, destination, overwrite=overwrite, skip_existing=skip_existing
    )


def remove_empty_dirs(path: Path) -> int:
    """
    Remove truly empty directories under path, bottom-up.
    Returns the number of directories removed.
    """
    removed = 0
    for root, dirnames, filenames in os.walk(path, topdown=False):
        root_path = Path(root)
        if filenames:
            continue
        if any((root_path / dirname).exists() for dirname in dirnames):
            continue
        try:
            root_path.rmdir()
        except OSError:
            continue
        else:
            removed += 1
    return removed
