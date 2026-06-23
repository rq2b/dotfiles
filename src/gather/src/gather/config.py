from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_PHOTO_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".jpg",
        ".jpeg",
        ".heic",
        ".tif",
        ".tiff",
        ".cr2",
        ".cr3",
        ".nef",
        ".arw",
        ".dng",
    }
)

DEFAULT_VIDEO_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".mov",
        ".mp4",
        ".mkv",
        ".avi",
        ".mts",
        ".m2ts",
        ".3gp",
        ".wmv",
    }
)


@dataclass(slots=True)
class DedupePreference:
    backup_terms: tuple[str, ...] = ("backup", "backups")
    import_terms: tuple[str, ...] = ("import", "imports")
    snapshot_terms: tuple[str, ...] = ("snapshot", "snapshots")


@dataclass(slots=True)
class GatherConfig:
    source_root: Path
    destination_root: Path
    manifest_name: str = "70-sha256-manifest.txt"
    photo_extensions: frozenset[str] = field(
        default_factory=lambda: DEFAULT_PHOTO_EXTENSIONS
    )
    video_extensions: frozenset[str] = field(
        default_factory=lambda: DEFAULT_VIDEO_EXTENSIONS
    )
    preference: DedupePreference = field(default_factory=DedupePreference)
    dry_run: bool = False
    report_dir: Path | None = None
    state_dir_name: str = ".gather"
    log_file: Path | None = None

    @property
    def effective_report_dir(self) -> Path:
        return self.report_dir if self.report_dir is not None else self.destination_root

    @property
    def state_dir(self) -> Path:
        return self.destination_root / self.state_dir_name

    @property
    def state_file(self) -> Path:
        return self.state_dir / "state.json"
