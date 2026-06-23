from __future__ import annotations

import argparse
import shutil
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from config import GatherConfig
from dedupe import SourceRanker
from logging_utils import GatherLogger
from models import CopyFailure, ManifestEntry, SelectedEntry
from parser import discover_manifest_files, iter_manifest_entries
from reports import (
    write_duplicate_groups_csv,
    write_extensions_csv,
    write_report_json,
    write_skipped_duplicates_csv,
)
from state import GatherState, load_state, save_state


@dataclass(slots=True)
class MediaRunResult:
    datasets_scanned: list[str]
    manifests_scanned: list[str]
    files_selected: int
    unique_hashes: int
    duplicates_skipped: int
    photo_count: int
    video_count: int
    total_size: int
    bytes_copied: int
    extension_breakdown: dict[str, tuple[int, int]]
    copy_failures: list[dict[str, str]]


def classify_extension(path: Path) -> str:
    return path.suffix.casefold()


def is_media_extension(
    extension: str,
    photo_extensions: frozenset[str],
    video_extensions: frozenset[str],
) -> bool:
    return extension.casefold() in photo_extensions or extension.casefold() in video_extensions


def media_kind(
    extension: str,
    photo_extensions: frozenset[str],
    video_extensions: frozenset[str],
) -> str | None:
    normalized = extension.casefold()
    if normalized in photo_extensions:
        return "photo"
    if normalized in video_extensions:
        return "video"
    return None


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def source_path_for_entry(config: GatherConfig, entry: ManifestEntry) -> Path:
    return config.source_root / entry.dataset / "import" / entry.relative_path


def destination_path_for_entry(config: GatherConfig, entry: ManifestEntry) -> Path:
    return config.destination_root / entry.dataset / entry.relative_path


def populate_selected_sizes(selected: dict[str, SelectedEntry]) -> None:
    for item in selected.values():
        try:
            item.size_bytes = item.source_path.stat().st_size
        except OSError:
            item.size_bytes = 0


def _load_resume_state(config: GatherConfig, logger: GatherLogger) -> GatherState | None:
    if config.dry_run:
        logger.log("[resume] dry-run; state disabled")
        return None

    try:
        state = load_state(config.state_file)
    except Exception as exc:
        logger.log(
            f"[resume] could not load state file {config.state_file}: {exc}; starting fresh"
        )
        return GatherState(
            completed_hashes=set(),
            files_completed=0,
            bytes_copied=0,
        )

    logger.log(
        f"[resume] loaded {len(state.completed_hashes):,} completed hashes"
    )
    return state


def perform_copy(
    selected: dict[str, SelectedEntry],
    config: GatherConfig,
    logger: GatherLogger,
) -> tuple[int, int, list[CopyFailure]]:
    bytes_copied = 0
    files_copied = 0
    failures: list[CopyFailure] = []

    state = _load_resume_state(config, logger)

    total = len(selected)

    for index, sha256 in enumerate(sorted(selected), start=1):
        item = selected[sha256]

        if state is not None and sha256 in state.completed_hashes:
            continue

        if not config.dry_run:
            try:
                if item.destination_path.exists():
                    destination_size = item.destination_path.stat().st_size
                    if item.size_bytes == 0 or destination_size == item.size_bytes:
                        if state is not None:
                            state.completed_hashes.add(sha256)
                            state.files_completed += 1
                            if state.files_completed % 1000 == 0:
                                save_state(config.state_file, state)
                                logger.log(f"[state] saved {state.files_completed:,}")
                        continue
            except OSError:
                pass

        if not item.source_path.exists():
            failures.append(
                CopyFailure(
                    entry=item.entry,
                    source_path=item.source_path,
                    destination_path=item.destination_path,
                    reason="missing-source-file",
                )
            )
            continue

        try:
            if item.size_bytes == 0:
                item.size_bytes = item.source_path.stat().st_size

            if not config.dry_run:
                ensure_parent(item.destination_path)
                shutil.copy2(item.source_path, item.destination_path)

                if state is not None:
                    state.completed_hashes.add(sha256)
                    state.files_completed += 1
                    state.bytes_copied += item.size_bytes
                    if state.files_completed % 1000 == 0:
                        save_state(config.state_file, state)
                        logger.log(f"[state] saved {state.files_completed:,}")

                files_copied += 1
                bytes_copied += item.size_bytes

            if index % 1000 == 0:
                logger.log(
                    f"[copy] {index:,}/{total:,} "
                    f"({index / total:.1%})"
                )

        except OSError as exc:
            failures.append(
                CopyFailure(
                    entry=item.entry,
                    source_path=item.source_path,
                    destination_path=item.destination_path,
                    reason=f"copy-error:{exc.__class__.__name__}",
                )
            )

    if state is not None:
        save_state(config.state_file, state)

    return files_copied, bytes_copied, failures


def build_extension_stats(
    selected: dict[str, SelectedEntry],
    photo_extensions: frozenset[str],
    video_extensions: frozenset[str],
) -> tuple[dict[str, tuple[int, int]], int, int]:
    stats: dict[str, tuple[int, int]] = defaultdict(lambda: (0, 0))
    photo_count = 0
    video_count = 0

    for sha256 in sorted(selected):
        item = selected[sha256]
        ext = classify_extension(item.entry.relative_path)
        kind = media_kind(ext, photo_extensions, video_extensions)

        if kind == "photo":
            photo_count += 1
        elif kind == "video":
            video_count += 1

        size_bytes = item.size_bytes
        if size_bytes == 0 and item.source_path.exists():
            try:
                size_bytes = item.source_path.stat().st_size
                item.size_bytes = size_bytes
            except OSError:
                size_bytes = 0

        count, size = stats[ext]
        stats[ext] = (count + 1, size + size_bytes)

    return dict(stats), photo_count, video_count


def run_media(config: GatherConfig, logger: GatherLogger) -> MediaRunResult:
    ranker = SourceRanker(config.preference)

    selected: dict[str, SelectedEntry] = {}
    counts: dict[str, int] = {}
    datasets: set[str] = set()
    manifests: list[str] = []
    media_entries: list[ManifestEntry] = []

    logger.log("[discover] locating manifests")
    entries_processed = 0

    for manifest_path in discover_manifest_files(config.source_root, config.manifest_name):
        manifests.append(str(manifest_path))

        dataset_name = manifest_path.parent.parent.name
        logger.log(f"[manifest] dataset={dataset_name}")

        for entry in iter_manifest_entries(manifest_path, config.source_root):
            extension = classify_extension(entry.relative_path)
            if not is_media_extension(extension, config.photo_extensions, config.video_extensions):
                continue

            media_entries.append(entry)
            datasets.add(entry.dataset)
            counts[entry.sha256] = counts.get(entry.sha256, 0) + 1

            selected_item = selected.get(entry.sha256)
            source_path = source_path_for_entry(config, entry)
            destination_path = destination_path_for_entry(config, entry)
            score = ranker.score(entry)

            if selected_item is None or score < selected_item.score:
                selected[entry.sha256] = SelectedEntry(
                    entry=entry,
                    source_path=source_path,
                    destination_path=destination_path,
                    score=score,
                )

            entries_processed += 1
            if entries_processed % 100_000 == 0:
                logger.log(
                    f"[index] entries={entries_processed:,} "
                    f"unique={len(selected):,} "
                    f"duplicates={entries_processed - len(selected):,}"
                )

    populate_selected_sizes(selected)

    files_selected, bytes_copied, failures = perform_copy(selected, config, logger)

    extension_breakdown, photo_count, video_count = build_extension_stats(
        selected,
        config.photo_extensions,
        config.video_extensions,
    )
    total_size = sum(item.size_bytes for item in selected.values())
    skipped_count = sum(count - 1 for count in counts.values() if count > 1)

    report_dir = config.effective_report_dir
    report_dir.mkdir(parents=True, exist_ok=True)

    write_duplicate_groups_csv(report_dir / "duplicate-groups.csv", selected, counts)

    def skipped_rows() -> Iterator[tuple[str, str, str]]:
        for entry in media_entries:
            chosen = selected.get(entry.sha256)
            if chosen is None:
                continue

            current_path = entry.dataset + "/" + entry.relative_path.as_posix()
            chosen_path = chosen.entry.dataset + "/" + chosen.entry.relative_path.as_posix()
            if current_path == chosen_path:
                continue

            if ranker.score(entry) > chosen.score:
                reason = ranker.reason_for_loser(entry, chosen.entry)
            else:
                reason = "duplicate"

            yield (entry.sha256, current_path, reason)

    write_skipped_duplicates_csv(report_dir / "skipped-duplicates.csv", skipped_rows())
    write_extensions_csv(
        report_dir / "extensions.csv",
        (
            (ext, count, size)
            for ext, (count, size) in sorted(
                extension_breakdown.items(),
                key=lambda item: (-item[1][1], item[0]),
            )
        ),
    )
    write_report_json(
        report_dir / "gather-report.json",
        {
            "datasets_scanned": sorted(datasets),
            "manifests_scanned": manifests,
            "files_selected": len(selected),
            "unique_hashes": len(selected),
            "duplicates_skipped": skipped_count,
            "photo_count": photo_count,
            "video_count": video_count,
            "total_size": total_size,
            "bytes_copied": bytes_copied,
            "extension_breakdown": {
                ext: {"count": count, "size": size}
                for ext, (count, size) in sorted(extension_breakdown.items())
            },
            "dry_run": config.dry_run,
            "copy_failures": [
                {
                    "dataset": failure.entry.dataset,
                    "sha256": failure.entry.sha256,
                    "source_path": str(failure.source_path),
                    "destination_path": str(failure.destination_path),
                    "reason": failure.reason,
                }
                for failure in failures
            ],
        },
    )

    return MediaRunResult(
        datasets_scanned=sorted(datasets),
        manifests_scanned=manifests,
        files_selected=len(selected),
        unique_hashes=len(selected),
        duplicates_skipped=skipped_count,
        photo_count=photo_count,
        video_count=video_count,
        total_size=total_size,
        bytes_copied=bytes_copied,
        extension_breakdown=extension_breakdown,
        copy_failures=[
            {
                "dataset": failure.entry.dataset,
                "sha256": failure.entry.sha256,
                "source_path": str(failure.source_path),
                "destination_path": str(failure.destination_path),
                "reason": failure.reason,
            }
            for failure in failures
        ],
    )


def print_media_summary(result: MediaRunResult, logger: GatherLogger) -> None:
    logger.log(f"Files Selected: {result.files_selected}")
    logger.log(f"Unique Hashes: {result.unique_hashes}")
    logger.log(f"Duplicate Copies Skipped: {result.duplicates_skipped}")
    logger.log("")
    logger.log(f"Photo Count: {result.photo_count}")
    logger.log(f"Video Count: {result.video_count}")
    logger.log("")
    logger.log(f"Total Size: {result.total_size}")
    logger.log(f"Bytes Copied: {result.bytes_copied}")

    if result.copy_failures:
        logger.log("")
        logger.log("Copy Failures:")
        for failure in result.copy_failures:
            logger.log(f"- {failure['reason']}: {failure['source_path']}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="gather")
    subparsers = parser.add_subparsers(dest="command", required=True)

    media_parser = subparsers.add_parser("media", help="Extract manifest-indexed media")
    media_parser.add_argument("source_root", type=Path)
    media_parser.add_argument("destination_root", type=Path)
    media_parser.add_argument("--dry-run", action="store_true")
    media_parser.add_argument("--manifest-name", default="70-sha256-manifest.txt")
    media_parser.add_argument("--report-dir", type=Path, default=None)
    media_parser.add_argument("--backup-term", action="append", default=None)
    media_parser.add_argument("--import-term", action="append", default=None)
    media_parser.add_argument("--snapshot-term", action="append", default=None)
    media_parser.add_argument("--photo-ext", action="append", default=None)
    media_parser.add_argument("--video-ext", action="append", default=None)
    media_parser.add_argument("--log-file", type=Path, default=None)
    media_parser.set_defaults(func=handle_media)
    return parser


def _merge_extensions(
    defaults: frozenset[str],
    additions: list[str] | None,
) -> frozenset[str]:
    if not additions:
        return defaults

    merged = {
        ext.casefold() if ext.startswith(".") else f".{ext.casefold()}"
        for ext in additions
    }
    return frozenset(defaults | merged)


def handle_media(args: argparse.Namespace) -> int:
    from config import DedupePreference

    photo_extensions = _merge_extensions(
        frozenset(
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
        ),
        args.photo_ext,
    )
    video_extensions = _merge_extensions(
        frozenset(
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
        ),
        args.video_ext,
    )
    preference = DedupePreference(
        backup_terms=tuple(args.backup_term or ["backup", "backups"]),
        import_terms=tuple(args.import_term or ["import", "imports"]),
        snapshot_terms=tuple(args.snapshot_term or ["snapshot", "snapshots"]),
    )
    config = GatherConfig(
        source_root=args.source_root,
        destination_root=args.destination_root,
        manifest_name=args.manifest_name,
        photo_extensions=photo_extensions,
        video_extensions=video_extensions,
        preference=preference,
        dry_run=args.dry_run,
        report_dir=args.report_dir,
        log_file=args.log_file,
    )

    logger = GatherLogger(config.log_file)
    try:
        result = run_media(config, logger)
        print_media_summary(result, logger)
    finally:
        logger.close()

    return 0


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
