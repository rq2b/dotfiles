from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Sequence

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import DEVICE, TRASH_ROOT, TRANSACTIONS_DIR, JOBS_DIR, LOGS_DIR
from filesystem import ensure_storage_dirs, scan_paths_stats, item_kind
from jobs import create_job, get_job, spawn_metadata_worker, update_job
from metadata import (
    create_complete_state,
    read_index_rows,
    read_metadata,
    read_state,
    rebuild_index,
    transaction_dir,
    write_metadata,
    write_state,
)
from models import TransactionItem, TransactionMetadata
from remove import perform_remove
from delete import perform_delete
from restore import perform_restore
from purge import perform_purge
from utils import human_size, now_iso, now_unix

SUMMARY_FIELDS = [
    "id",
    "state",
    "action",
    "label",
    "device",
    "created_iso",
    "size_human",
    "file_count",
    "directory_count",
    "original_paths",
    "stored_path",
    "tombstone",
    "restored",
    "purged",
]


def ensure_layout() -> None:
    ensure_storage_dirs(TRASH_ROOT, TRANSACTIONS_DIR, JOBS_DIR, LOGS_DIR)


def print_error(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)


def format_summary(metadata, state) -> str:

    fields = [
        ("Transaction", metadata.id),
        ("Status", state.state.upper()),
        ("Action", metadata.action.upper()),
        ("Label", metadata.label),
        ("Device", metadata.device),
        ("Created", metadata.created_iso),
        ("Size", human_size(metadata.size_bytes)),
        ("Files", f"{metadata.file_count:,}"),
        ("Directories", f"{metadata.directory_count:,}"),
        ("Stored At", metadata.stored_path),
        ("Tombstone", "Yes" if metadata.tombstone else "No"),
        (
            "Restored",
            "Yes" if state.restored_unix is not None else "No",
        ),
        (
            "Purged",
            "Yes" if state.purged_unix is not None else "No",
        ),
    ]

    width = max(len(name) for name, _ in fields)

    lines = [f"{name:<{width + 2}} :  {value}" for name, value in fields]

    lines.append("Original Paths")

    for path in metadata.original_paths:
        lines.append(f"  {path}")

    return "\n".join(lines)


def format_transaction_summary(metadata: TransactionMetadata) -> str:
    lines = [
        "Transaction:",
        f"  {metadata.id}",
        "",
        "Device:",
        f"  {metadata.device}",
        "",
        "Label:",
        f"  {metadata.label}",
        "",
        "Original Paths:",
    ]
    for path in metadata.original_paths:
        lines.append(f"  {path}")
    lines.extend(
        [
            "",
            "Files:",
            f"  {metadata.file_count}",
            "",
            "Directories:",
            f"  {metadata.directory_count}",
            "",
            "Size:",
            f"  {human_size(metadata.size_bytes)}",
            "",
            "Stored At:",
            f"  {metadata.stored_path}",
        ]
    )
    return "\n".join(lines)


def format_dry_run(metadata: TransactionMetadata) -> str:
    lines = [
        "Transaction:",
        f"  {metadata.id}",
        "",
        "Device:",
        f"  {metadata.device}",
        "",
        "Label:",
        f"  {metadata.label}",
        "",
        "Original Paths:",
    ]
    for path in metadata.original_paths:
        lines.append(f"  {path}")
    lines.extend(
        [
            "",
            "Files:",
            f"  {metadata.file_count}",
            "",
            "Directories:",
            f"  {metadata.directory_count}",
            "",
            "Size:",
            f"  {human_size(metadata.size_bytes)}",
            "",
            "Stored At:",
            f"  {metadata.stored_path}",
            "",
            "Changes:",
            "  none (dry run)",
        ]
    )
    return "\n".join(lines)


def cmd_summary(args: argparse.Namespace) -> int:

    if args.preview:

        print("""
SUMMARY FIELDS

  id
  state
  action
  label
  device
  created_iso
  size_human
  file_count
  directory_count
  original_paths
  stored_path
  tombstone
  restored
  purged
""".strip())

        return 0

    try:
        metadata = read_metadata(args.transaction_id)
        state = read_state(args.transaction_id)

    except Exception as exc:
        print_error(str(exc))
        return 1

    print(format_summary(metadata, state))
    return 0


def cmd_remove(args: argparse.Namespace) -> int:
    try:
        paths = [Path(path) for path in args.paths]
        metadata = perform_remove(
            paths, explicit_label=args.label, dry_run=args.dry_run, sync=args.sync
        )
    except Exception as exc:
        print_error(str(exc))
        return 1

    if args.dry_run:
        print(format_dry_run(metadata))
        return 0

    if args.sync:
        print(format_transaction_summary(metadata))
        print()
        print("Status:")
        print("  complete")
        return 0

    try:
        pid = spawn_metadata_worker(metadata.id)
        create_job(
            metadata.id, pid, status="running", detail={"mode": "metadata-worker"}
        )
    except Exception as exc:
        print_error(f"Failed to start metadata worker: {exc}")
        return 1

    print(f"Transaction:\n  {metadata.id}\n")
    print("Status:")
    print("  metadata generation running")
    return 0


def cmd_delete(args: argparse.Namespace) -> int:
    if not args.confirm and not args.dry_run:
        print_error("delete is irreversible.\n\n" "Use --confirm to continue.")
        return 1

    try:
        metadata = perform_delete(
            [Path(path) for path in args.paths],
            explicit_label=args.label,
            dry_run=args.dry_run,
        )
    except Exception as exc:
        print_error(str(exc))
        return 1

    if args.dry_run:
        print(format_dry_run(metadata))
        return 0

    print(format_transaction_summary(metadata))
    print()
    print("Status:")
    print("  complete")
    return 0


def cmd_restore(args: argparse.Namespace) -> int:
    try:
        perform_restore(args.transaction_id, overwrite=args.overwrite)
    except Exception as exc:
        print_error(str(exc))
        return 1

    print(f"Transaction:\n  {args.transaction_id}\n")
    print("Status:")
    print("  restored")
    return 0


def cmd_purge(args: argparse.Namespace) -> int:
    try:
        perform_purge(args.transaction_id)
    except Exception as exc:
        print_error(str(exc))
        return 1

    print(f"Transaction:\n  {args.transaction_id}\n")
    print("Status:")
    print("  purged")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    rebuild_index()
    rows = read_index_rows()
    print("ID                               STATE")
    if not rows:
        return 0

    print()
    for row in rows:
        print(f"{row.get('id',''):<32} {str(row.get('state','')).upper()}")
    return 0


def cmd_info(args: argparse.Namespace) -> int:
    try:
        metadata = read_metadata(args.transaction_id)
        state = read_state(args.transaction_id)
    except Exception as exc:
        print_error(str(exc))
        return 1

    print("Metadata:")
    print(json.dumps(asdict(metadata), ensure_ascii=False, indent=2, default=str))
    print()
    print("State:")
    print(json.dumps(asdict(state), ensure_ascii=False, indent=2, default=str))
    return 0


def _build_items_from_state_detail(
    transaction_id: str, detail: dict[str, object]
) -> list[TransactionItem]:
    tdir = transaction_dir(transaction_id)
    contents = tdir / "contents"
    items: list[TransactionItem] = []
    for original in map(str, detail.get("original_paths", [])):
        original_path = Path(original)
        stored = (
            contents / Path(*original_path.parts[1:])
            if original_path.is_absolute()
            else contents / original_path
        )
        items.append(
            TransactionItem(
                original_path=original,
                stored_relpath=str(stored.relative_to(contents)),
                kind=item_kind(stored),
            )
        )
    return items


def worker_metadata(transaction_id: str) -> int:
    try:
        tdir = transaction_dir(transaction_id)
        if not tdir.exists():
            raise FileNotFoundError(f"Transaction not found: {transaction_id}")

        state = read_state(transaction_id)
        detail = dict(state.detail)
        if not detail:
            raise RuntimeError("Missing transaction detail in state.json.")

        original_paths = [str(p) for p in detail.get("original_paths", [])]
        if not original_paths:
            raise RuntimeError("Missing original_paths in state detail.")

        size_bytes = int(detail.get("size_bytes", 0))
        file_count = int(detail.get("file_count", 0))
        directory_count = int(detail.get("directory_count", 0))
        stored_path = str(detail.get("stored_path", str(tdir)))
        label = str(detail.get("label", tdir.name.split("_", 1)[-1]))

        items = _build_items_from_state_detail(transaction_id, detail)

        final = TransactionMetadata(
            id=transaction_id,
            label=label,
            device=DEVICE,
            created_unix=state.started_unix or now_unix(),
            created_iso=str(detail.get("created_iso", now_iso())),
            action="move",
            status="complete",
            original_paths=original_paths,
            stored_path=stored_path,
            size_bytes=size_bytes,
            file_count=file_count,
            directory_count=directory_count,
            items=items,
        )
        write_metadata(final)
        write_state(
            transaction_id,
            create_complete_state(state.started_unix, now_unix(), detail=detail),
        )
        rebuild_index()
        job = get_job(transaction_id)
        if job is not None:
            update_job(job, status="complete")
        return 0
    except Exception as exc:
        try:
            from models import TransactionState

            job = get_job(transaction_id)
            if job is not None:
                update_job(job, status="error", error=str(exc))
            tdir = transaction_dir(transaction_id)
            if tdir.exists():
                previous = read_state(transaction_id)
                write_state(
                    transaction_id,
                    TransactionState(
                        state="error",
                        started_unix=previous.started_unix,
                        error=str(exc),
                        detail={"worker": "metadata"},
                    ),
                )
                rebuild_index()
        except Exception:
            pass
        return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="trash", description="Archival-grade deletion staging utility."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    remove_p = sub.add_parser("remove", help="Move paths into a deletion transaction.")
    remove_p.add_argument("paths", nargs="+", help="Paths to stage for deletion.")
    remove_p.add_argument("--label", help="Override the transaction label.")
    remove_p.add_argument(
        "--sync", action="store_true", help="Wait for metadata generation."
    )
    remove_p.add_argument(
        "--dry-run",
        action="store_true",
        help="Show the full transaction that would be created.",
    )
    remove_p.set_defaults(func=cmd_remove)

    delete_p = sub.add_parser(
        "delete",
        help="Permanently delete paths and create a tombstone record.",
    )

    delete_p.add_argument(
        "paths",
        nargs="+",
    )

    delete_p.add_argument(
        "--label",
    )

    delete_p.add_argument(
        "--dry-run",
        action="store_true",
    )

    delete_p.add_argument(
        "--confirm",
        action="store_true",
    )

    delete_p.set_defaults(func=cmd_delete)

    restore_p = sub.add_parser(
        "restore", help="Restore a transaction to its original locations."
    )
    restore_p.add_argument("transaction_id", help="Transaction identifier.")
    restore_p.add_argument(
        "--overwrite", action="store_true", help="Allow replacing existing targets."
    )
    restore_p.set_defaults(func=cmd_restore)

    purge_p = sub.add_parser("purge", help="Permanently remove transaction contents.")
    purge_p.add_argument("transaction_id", help="Transaction identifier.")
    purge_p.set_defaults(func=cmd_purge)

    list_p = sub.add_parser("list", help="List transactions.")
    list_p.set_defaults(func=cmd_list)

    info_p = sub.add_parser("info", help="Show full transaction information.")
    info_p.add_argument("transaction_id", help="Transaction identifier.")
    info_p.set_defaults(func=cmd_info)

    summary_p = sub.add_parser(
        "summary",
        help="Show a human-readable transaction summary.",
    )

    summary_p.add_argument(
        "transaction_id",
        nargs="?",
    )

    summary_p.add_argument(
        "--preview",
        action="store_true",
    )

    summary_p.set_defaults(func=cmd_summary)

    worker_p = sub.add_parser("_worker", help=argparse.SUPPRESS)
    worker_p.add_argument("worker_kind", choices=["metadata"])
    worker_p.add_argument("transaction_id")
    worker_p.set_defaults(func=lambda args: worker_metadata(args.transaction_id))

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    ensure_layout()
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except KeyboardInterrupt:
        print_error("Interrupted.")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
