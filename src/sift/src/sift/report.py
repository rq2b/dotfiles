from __future__ import annotations

from typing import Iterable

from models import FileAction, RunReport, RunStatistics
from stats import format_extension_report, format_run_summary


def render_actions(actions: Iterable[FileAction], *, limit: int = 25) -> str:
    lines: list[str] = []
    for idx, action in enumerate(actions):
        if idx >= limit:
            lines.append("...")
            break
        lines.append(
            f"{action.action.upper():<8} {action.bucket.value}: {action.relative_path.as_posix()}"
        )
    return "\n".join(lines)


def render_dry_run_report(stats: RunStatistics) -> str:
    parts = [
        "Dry run summary",
        "",
        format_run_summary(stats),
        "",
        "Extension report",
        format_extension_report(stats),
    ]
    return "\n".join(parts)


def render_completion_report(report: RunReport) -> str:
    parts = [
        "Run complete",
        "",
        format_run_summary(report.statistics),
        "",
        "Extension report",
        format_extension_report(report.statistics),
    ]
    if report.actions:
        parts.extend(["", "Examples", render_actions(report.actions, limit=20)])
    if report.notes:
        parts.extend(["", "Notes", *report.notes])
    return "\n".join(parts)
