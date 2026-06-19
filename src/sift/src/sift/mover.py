from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from classifier import FileClassifier
from config import SiftConfig
from filesystem import process_entry
from models import Bucket, FileAction, RunReport, RunStatistics
from scanner import scan_files


@dataclass(slots=True)
class RunOptions:
    move: bool = False
    dry_run: bool = False
    remove_empty_dirs: bool = False
    overwrite: bool = False
    skip_existing: bool = False
    verbose: bool = False
    report_path: Path | None = None
    command: list[str] | None = None


def destination_for(output: Path, bucket: Bucket, relative_path: Path) -> Path:
    return output / bucket.value / relative_path


def run_sift(
    source: Path,
    output: Path,
    *,
    config: SiftConfig,
    options: RunOptions,
) -> RunReport:
    classifier = FileClassifier(config)
    stats = RunStatistics()
    actions: list[FileAction] = []
    action_limit = 25

    exclude = output if output.is_relative_to(source) else None

    for entry in scan_files(source, exclude=exclude):
        classification = classifier.classify(entry)
        stats.add(
            classification.bucket,
            entry.relative_path,
            entry.size,
            classification.extension,
        )

        destination = destination_for(
            output, classification.bucket, entry.relative_path
        )

        action_name = (
            "dry-run" if options.dry_run else ("move" if options.move else "copy")
        )
        action = FileAction(
            source=entry.source_path,
            destination=destination,
            bucket=classification.bucket,
            relative_path=entry.relative_path,
            extension=classification.extension,
            size=entry.size,
            action=action_name,
        )
        if len(actions) < action_limit:
            actions.append(action)

        if options.verbose:
            print(
                f"{action_name.upper():<8} {classification.bucket.value}: {entry.relative_path.as_posix()}"
            )

        if options.dry_run:
            continue

        process_entry(
            entry.source_path,
            destination,
            move=options.move,
            overwrite=options.overwrite,
            skip_existing=options.skip_existing,
        )

    report = RunReport(
        source=str(source),
        output=str(output),
        move=options.move,
        dry_run=options.dry_run,
        remove_empty_dirs=options.remove_empty_dirs,
        overwrite=options.overwrite,
        skip_existing=options.skip_existing,
        historical_extensions=sorted(config.historical_extensions),
        statistics=stats,
        actions=actions,
        created_at=_utc_now_iso(),
        command=options.command or [],
        notes=[],
    )
    return report


def _utc_now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()
