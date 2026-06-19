from __future__ import annotations

import os
import sys
from pathlib import Path

try:
    DEVICE = os.environ["DEVICE"]
except KeyError as exc:  # pragma: no cover - startup failure path
    print(
        "ERROR: DEVICE environment variable is not set.\n\n"
        "Example:\n\n"
        "    DEVICE=samsung-hd502hj-500gb trash remove Downloads",
        file=sys.stderr,
    )
    raise SystemExit(1) from exc

TRASH_ROOT = Path("/mnt/offsite/deletions")
TRANSACTIONS_DIR = TRASH_ROOT / "transactions"
JOBS_DIR = TRASH_ROOT / "jobs"
LOGS_DIR = TRASH_ROOT / "logs"
INDEX_FILE = TRASH_ROOT / "index.tsv"

MAX_LABEL_LENGTH = 64
DEFAULT_ASYNC = True

JSON_INDENT = 2
