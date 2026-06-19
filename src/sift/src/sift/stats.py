from __future__ import annotations

from pathlib import Path
from typing import Any

from models import RunReport, RunStatistics
from utils import human_bytes


def format_run_summary(stats: RunStatistics) -> str:
    lines = [
        "Historical",
        f"  Files: {stats.historical.files:,}",
        f"  Size: {human_bytes(stats.historical.size)}",
    ]
    if stats.historical.examples:
        lines.append(f"  Examples: {', '.join(stats.historical.examples)}")
    lines.extend(
        [
            "",
            "Residual",
            f"  Files: {stats.residual.files:,}",
            f"  Size: {human_bytes(stats.residual.size)}",
        ]
    )
    if stats.residual.examples:
        lines.append(f"  Examples: {', '.join(stats.residual.examples)}")
    lines.extend(
        [
            "",
            "Unknown",
            f"  Files: {stats.unknown.files:,}",
            f"  Size: {human_bytes(stats.unknown.size)}",
        ]
    )
    if stats.unknown.examples:
        lines.append(f"  Examples: {', '.join(stats.unknown.examples)}")
    return "\n".join(lines)


def format_extension_report(stats: RunStatistics) -> str:
    lines = ["Extension      Count      Size"]
    rows = sorted(
        stats.extension_stats.values(), key=lambda item: (-item.files, item.extension)
    )
    for item in rows:
        lines.append(
            f"{item.extension:<13} {item.files:>8,}  {human_bytes(item.size):>10}"
        )
    return "\n".join(lines)


def save_report(report: RunReport, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_to_json(report.to_dict()), encoding="utf-8")


def load_report(path: Path) -> dict[str, Any]:
    import json

    return json.loads(path.read_text(encoding="utf-8"))


def format_saved_report(report: dict[str, Any]) -> str:
    stats = report["statistics"]
    lines = [
        f"Source: {report['source']}",
        f"Output: {report['output']}",
        f"Created at: {report['created_at']}",
        "",
        "Historical",
        f"  Files: {stats['historical']['files']:,}",
        f"  Size: {human_bytes(stats['historical']['size'])}",
    ]
    if stats["historical"].get("examples"):
        lines.append(f"  Examples: {', '.join(stats['historical']['examples'])}")
    lines.extend(
        [
            "",
            "Residual",
            f"  Files: {stats['residual']['files']:,}",
            f"  Size: {human_bytes(stats['residual']['size'])}",
        ]
    )
    if stats["residual"].get("examples"):
        lines.append(f"  Examples: {', '.join(stats['residual']['examples'])}")
    lines.extend(
        [
            "",
            "Unknown",
            f"  Files: {stats['unknown']['files']:,}",
            f"  Size: {human_bytes(stats['unknown']['size'])}",
        ]
    )
    if stats["unknown"].get("examples"):
        lines.append(f"  Examples: {', '.join(stats['unknown']['examples'])}")
    lines.extend(
        [
            "",
            "Extensions",
            "Extension      Count      Size",
        ]
    )
    extension_stats = stats.get("extension_stats", {})
    for key, item in sorted(
        extension_stats.items(), key=lambda pair: (-pair[1]["files"], pair[0])
    ):
        lines.append(f"{key:<13} {item['files']:>8,}  {human_bytes(item['size']):>10}")
    return "\n".join(lines)


def _to_json(data: dict[str, Any]) -> str:
    import json

    return json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True)
