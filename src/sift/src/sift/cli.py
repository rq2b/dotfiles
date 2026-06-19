from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from cleanup import cleanup_empty_directories
from config import SiftConfig
from mover import RunOptions, run_sift
from report import render_completion_report, render_dry_run_report
from stats import format_saved_report, load_report, save_report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sift", description="Archive triage and historical artifact extraction"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser(
        "run", help="Classify files into historical-artifacts, residual, and unknown"
    )
    run_parser.add_argument("source", type=Path)
    run_parser.add_argument("output", type=Path)
    run_parser.add_argument(
        "--move", action="store_true", help="Move files instead of copying them"
    )
    run_parser.add_argument(
        "--dry-run", action="store_true", help="Do not modify the filesystem"
    )
    run_parser.add_argument(
        "--remove-empty-dirs",
        action="store_true",
        help="Remove empty source directories after move",
    )
    run_parser.add_argument(
        "--overwrite", action="store_true", help="Overwrite existing destination files"
    )
    run_parser.add_argument(
        "--skip-existing", action="store_true", help="Skip existing destination files"
    )
    run_parser.add_argument(
        "--verbose", action="store_true", help="Print per-file actions"
    )
    run_parser.add_argument(
        "--report-path", type=Path, help="Where to write the JSON report"
    )
    run_parser.add_argument(
        "--extensions-file", type=Path, help="Plain-text extension list file"
    )
    run_parser.add_argument(
        "--extension",
        dest="extensions",
        action="append",
        default=[],
        help="Add a historical extension override",
    )

    ext_parser = subparsers.add_parser(
        "extensions", help="Show configured historical extensions"
    )
    ext_parser.add_argument(
        "--extensions-file", type=Path, help="Plain-text extension list file"
    )
    ext_parser.add_argument(
        "--extension",
        dest="extensions",
        action="append",
        default=[],
        help="Add a historical extension override",
    )

    stats_parser = subparsers.add_parser(
        "stats", help="Display a saved sift JSON report"
    )
    stats_parser.add_argument("report_path", type=Path)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "run":
        return _run(args, parser)
    if args.command == "extensions":
        return _extensions(args)
    if args.command == "stats":
        return _stats(args)
    parser.error("unknown command")
    return 2


def _run(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    source = args.source.resolve()
    output = args.output.resolve()

    if not source.exists():
        raise FileNotFoundError(source)
    if not source.is_dir():
        raise NotADirectoryError(source)
    if output == source:
        raise ValueError("output must be different from source")

    if not args.dry_run:
        output.mkdir(parents=True, exist_ok=True)

    config = SiftConfig.from_iterable(
        extensions=args.extensions,
        extensions_file=args.extensions_file,
    )

    options = RunOptions(
        move=bool(args.move),
        dry_run=bool(args.dry_run),
        remove_empty_dirs=bool(args.remove_empty_dirs),
        overwrite=bool(args.overwrite),
        skip_existing=bool(args.skip_existing),
        verbose=bool(args.verbose),
        report_path=args.report_path,
        command=[parser.prog, "run", str(source), str(output)],
    )

    report = run_sift(source, output, config=config, options=options)

    if options.remove_empty_dirs and options.move and not options.dry_run:
        removed = cleanup_empty_directories(source)
        report.notes.append(f"Removed {removed} empty directories from source.")

    report_path = args.report_path or (output / "sift-report.json")
    if not options.dry_run:
        save_report(report, report_path)
        print(f"Saved report: {report_path}")
        print(render_completion_report(report))
    else:
        print(render_dry_run_report(report.statistics))

    return 0


def _extensions(args: argparse.Namespace) -> int:
    config = SiftConfig.from_iterable(
        extensions=args.extensions,
        extensions_file=args.extensions_file,
    )
    print("Historical extensions")
    for ext in sorted(config.historical_extensions):
        print(ext)
    print("")
    print(
        "Unknown files: extensionless files such as README, LICENSE, Makefile, hosts, passwd"
    )
    print("Residual files: any file whose extension is not in the historical set")
    return 0


def _stats(args: argparse.Namespace) -> int:
    report = load_report(args.report_path)
    print(format_saved_report(report))
    return 0
