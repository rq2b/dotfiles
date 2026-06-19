from __future__ import annotations

import os
from pathlib import Path
from typing import Iterator

from models import FileEntry


def scan_files(source: Path, *, exclude: Path | None = None) -> Iterator[FileEntry]:
    """
    Stream files under source without loading them all into memory.
    """
    source = source.resolve()
    exclude_resolved = exclude.resolve() if exclude is not None else None

    for root, dirnames, filenames in os.walk(source, topdown=True):
        root_path = Path(root)
        if exclude_resolved is not None:
            filtered_dirs: list[str] = []
            for dirname in dirnames:
                candidate = (root_path / dirname).resolve()
                if (
                    candidate == exclude_resolved
                    or exclude_resolved in candidate.parents
                ):
                    continue
                filtered_dirs.append(dirname)
            dirnames[:] = filtered_dirs

        for filename in filenames:
            file_path = root_path / filename
            if file_path.is_symlink():
                size = file_path.lstat().st_size
            else:
                size = file_path.stat().st_size
            relative = file_path.relative_to(source)
            yield FileEntry(source_path=file_path, relative_path=relative, size=size)
