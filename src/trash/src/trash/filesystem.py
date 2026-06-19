from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from models import TransactionItem
from utils import unique_preserve_order


@dataclass(slots=True)
class PathStats:
    size_bytes: int = 0
    file_count: int = 0
    directory_count: int = 0


def ensure_storage_dirs(*dirs: Path) -> None:
    for directory in dirs:
        directory.mkdir(parents=True, exist_ok=True)


def is_absolute_within_root(path: Path) -> bool:
    return path.is_absolute()


def normalize_input_path(raw: str | Path) -> Path:
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = path.resolve(strict=False)
    return path


def path_is_ancestor(parent: Path, child: Path) -> bool:
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def validate_non_overlapping_paths(paths: list[Path]) -> None:
    unique = [Path(p) for p in unique_preserve_order([str(p) for p in paths])]
    normalized = [Path(p) for p in unique]
    for i, first in enumerate(normalized):
        for j, second in enumerate(normalized):
            if i == j:
                continue
            if path_is_ancestor(first, second):
                raise ValueError(
                    f"Paths overlap: {first} is an ancestor of {second}. "
                    "Remove overlapping paths in separate transactions."
                )


def transaction_contents_path(transaction_dir: Path, original_path: Path) -> Path:
    if original_path.is_absolute():
        rel = (
            Path(*original_path.parts[1:])
            if len(original_path.parts) > 1
            else Path(original_path.name)
        )
    else:
        rel = original_path
    if str(rel) == "":
        rel = Path("unnamed")
    return transaction_dir / "contents" / rel


def scan_path_stats(path: Path) -> PathStats:
    stats = PathStats()
    if not path.exists() and not path.is_symlink():
        raise FileNotFoundError(str(path))

    def add_file(file_path: Path) -> None:
        nonlocal stats
        try:
            st = file_path.lstat()
        except FileNotFoundError:
            return
        stats.size_bytes += st.st_size
        stats.file_count += 1

    if path.is_symlink():
        add_file(path)
        return stats

    if path.is_file():
        add_file(path)
        return stats

    if path.is_dir():
        stats.directory_count += 1
        for root, dirs, files in os.walk(path, followlinks=False):
            stats.directory_count += len(dirs)
            for filename in files:
                add_file(Path(root) / filename)
        return stats

    add_file(path)
    return stats


def scan_paths_stats(paths: list[Path]) -> PathStats:
    total = PathStats()
    seen: set[tuple[int, int]] = set()

    for path in paths:
        if not path.exists() and not path.is_symlink():
            raise FileNotFoundError(str(path))
        st = path.lstat() if path.exists() or path.is_symlink() else None
        key = (st.st_dev, st.st_ino) if st is not None else None

        if key is not None and key in seen:
            continue
        if key is not None:
            seen.add(key)

        stats = scan_path_stats(path)
        total.size_bytes += stats.size_bytes
        total.file_count += stats.file_count
        total.directory_count += stats.directory_count

    return total


def item_kind(path: Path) -> str:
    if path.is_symlink():
        return "symlink"
    if path.is_dir():
        return "directory"
    if path.is_file():
        return "file"
    return "other"


def move_paths_into_transaction(
    paths: list[Path], transaction_dir: Path
) -> list[TransactionItem]:
    items: list[TransactionItem] = []
    contents_dir = transaction_dir / "contents"
    contents_dir.mkdir(parents=True, exist_ok=True)

    for path in paths:
        target = transaction_contents_path(transaction_dir, path)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(path), str(target))
        items.append(
            TransactionItem(
                original_path=str(path),
                stored_relpath=str(target.relative_to(contents_dir)),
                kind=item_kind(target),
            )
        )
    return items


def restore_items_from_transaction(
    transaction_dir: Path, items: list[TransactionItem], *, overwrite: bool
) -> None:
    contents_dir = transaction_dir / "contents"
    for item in sorted(items, key=lambda it: len(Path(it.original_path).parts)):
        source = contents_dir / Path(item.stored_relpath)
        destination = Path(item.original_path)

        if not source.exists() and not source.is_symlink():
            raise FileNotFoundError(f"Missing transaction content: {source}")

        if destination.exists() or destination.is_symlink():
            if not overwrite:
                raise FileExistsError(f"Restore target already exists: {destination}")
            remove_path(destination)

        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(destination))


def remove_path(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink(missing_ok=True)
        return
    if path.is_dir():
        shutil.rmtree(path)
        return
    if path.exists():
        path.unlink(missing_ok=True)
