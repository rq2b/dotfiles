from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class Bucket(str, Enum):
    HISTORICAL = "historical-artifacts"
    RESIDUAL = "residual"
    UNKNOWN = "unknown"


@dataclass(slots=True)
class FileEntry:
    source_path: Path
    relative_path: Path
    size: int


@dataclass(slots=True)
class ClassificationResult:
    entry: FileEntry
    bucket: Bucket
    extension: str | None


@dataclass(slots=True)
class BucketStats:
    files: int = 0
    size: int = 0
    examples: list[str] = field(default_factory=list)

    def add(self, relative_path: Path, size: int, *, example_limit: int = 5) -> None:
        self.files += 1
        self.size += size
        if len(self.examples) < example_limit:
            self.examples.append(relative_path.as_posix())


@dataclass(slots=True)
class ExtensionStat:
    extension: str
    files: int = 0
    size: int = 0

    def add(self, size: int) -> None:
        self.files += 1
        self.size += size


@dataclass(slots=True)
class RunStatistics:
    historical: BucketStats = field(default_factory=BucketStats)
    residual: BucketStats = field(default_factory=BucketStats)
    unknown: BucketStats = field(default_factory=BucketStats)
    extension_stats: dict[str, ExtensionStat] = field(default_factory=dict)

    def bucket_stats(self, bucket: Bucket) -> BucketStats:
        if bucket is Bucket.HISTORICAL:
            return self.historical
        if bucket is Bucket.RESIDUAL:
            return self.residual
        return self.unknown

    def add(
        self, bucket: Bucket, relative_path: Path, size: int, extension: str | None
    ) -> None:
        self.bucket_stats(bucket).add(relative_path, size)
        key = extension if extension else "<none>"
        stat = self.extension_stats.get(key)
        if stat is None:
            stat = ExtensionStat(extension=key)
            self.extension_stats[key] = stat
        stat.add(size)

    def totals(self) -> dict[str, tuple[int, int]]:
        return {
            "historical": (self.historical.files, self.historical.size),
            "residual": (self.residual.files, self.residual.size),
            "unknown": (self.unknown.files, self.unknown.size),
        }


@dataclass(slots=True)
class FileAction:
    source: Path
    destination: Path
    bucket: Bucket
    relative_path: Path
    extension: str | None
    size: int
    action: str  # copy | move | skip | dry-run


@dataclass(slots=True)
class RunReport:
    source: str
    output: str
    move: bool
    dry_run: bool
    remove_empty_dirs: bool
    overwrite: bool
    skip_existing: bool
    historical_extensions: list[str]
    statistics: RunStatistics
    actions: list[FileAction]
    created_at: str
    command: list[str]
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "output": self.output,
            "move": self.move,
            "dry_run": self.dry_run,
            "remove_empty_dirs": self.remove_empty_dirs,
            "overwrite": self.overwrite,
            "skip_existing": self.skip_existing,
            "historical_extensions": self.historical_extensions,
            "statistics": {
                "historical": {
                    "files": self.statistics.historical.files,
                    "size": self.statistics.historical.size,
                    "examples": self.statistics.historical.examples,
                },
                "residual": {
                    "files": self.statistics.residual.files,
                    "size": self.statistics.residual.size,
                    "examples": self.statistics.residual.examples,
                },
                "unknown": {
                    "files": self.statistics.unknown.files,
                    "size": self.statistics.unknown.size,
                    "examples": self.statistics.unknown.examples,
                },
                "extension_stats": {
                    key: {"files": stat.files, "size": stat.size}
                    for key, stat in sorted(self.statistics.extension_stats.items())
                },
            },
            "actions": [
                {
                    "source": str(action.source),
                    "destination": str(action.destination),
                    "bucket": action.bucket.value,
                    "relative_path": action.relative_path.as_posix(),
                    "extension": action.extension,
                    "size": action.size,
                    "action": action.action,
                }
                for action in self.actions
            ],
            "created_at": self.created_at,
            "command": self.command,
            "notes": self.notes,
        }
