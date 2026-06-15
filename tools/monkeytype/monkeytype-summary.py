#!/usr/bin/env python3
"""
monkeytype.py — Summarise Monkeytype CSV exports by test type.

Drop in ~/bin (or anywhere on $PATH), chmod +x, then run:
    monkeytype.py                  # auto-finds newest CSV in ~/Downloads
    monkeytype.py my.csv           # explicit path
    monkeytype.py --runs 3         # last 3 batches only
    monkeytype.py --add-override   # interactively record a result that
                                   # Monkeytype refused to save
    monkeytype.py --json           # emit machine-readable JSON
"""

import argparse
import glob
import json
import math
import os
import secrets
import sys
from collections import OrderedDict
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd


SCRIPT_VERSION = "2.0-json"
SCHEMA_VERSION = "2.0"

# ---------------------------------------------------------------------------
# Test catalogue
#
# Keys are TOTAL char counts (correct + incorrect + extra + missed),
# i.e. the sum of all four semicolon-separated fields in charStats.
# Using total rather than just correct chars fixes REGEX recognition:
# a REGEX run with one error gives charStats "90;1;0;0", so correct=90
# which is ambiguous with other short tests, but total=91 is unique.
#
# v2 entries are placeholders (key=-1 … -4) until you measure the real
# char counts after running the new snippets in Monkeytype.  Update the
# keys to the actual totals then; the names stay the same.
# ---------------------------------------------------------------------------
FIXED_TESTS: OrderedDict[int, str] = OrderedDict([
    (393,  "bash"),
    (543,  "C"),
    (628,  "Cpp"),
    (383,  "Python"),
    (400,  "CS"),
    # (85,   "VIM"),
    # (91,   "REGEX"),
    # (131,  "linux"),
    # (110,  "symbols"),
    (177,   "VIM-v2"),
    (304,   "REGEX-v2"),
    (482,   "linux-v2"),
    (334,   "symbols-v2"),
    (476,   "git-l1-1"),
    (499,   "git-l1-2"),
])

# Sequence that names 30-second drill slots within a batch, in order.
DRILL_SEQUENCE: list[str] = [
    "left",
    "right",
    "both",
    "operators",
    "punctuation+numbers",
    "raw",
]

# ---------------------------------------------------------------------------
# Calibration / warmup exclusions
#
# These rows stay in the raw data, but are ignored by summaries, PB tables,
# trends, and JSON export.
# ---------------------------------------------------------------------------

# Optional: remove whole early batches if the first day(s) were setup noise.
IGNORED_BATCHES: set[str] = {
    # "2026-05-12 21:45",
    # "2026-05-13 05:59",
}

# Skip the first N occurrences of a named test across the whole dataset.
# Start small: right=1 removes the first anomalous right-hand calibration run.
CALIBRATION_SKIP_FIRST: dict[str, int] = {
    "right": 1,
    # "left": 1,
    # "both": 1,
    # "operators": 1,
    # "punctuation+numbers": 1,
    # "raw": 1,
}

# Columns shown in the raw-attempts table.
RAW_COLS = [
    "batch",
    "attempt_in_batch",
    "test_name",
    "total_chars",
    "correct",
    "errors",
    "testDuration",
    "wpm",
    "rawWpm",
    "acc",
    "consistency",
    "pb",
    "analysis_included"
]

SEP = "=" * 70

# Where manual overrides live.  Auto-excluded from CSV auto-discovery.
OVERRIDE_PATH = os.path.expanduser("~/Downloads/overrides.csv")

# Full column order matching a real Monkeytype export row.
CSV_COLUMNS = [
    "_id", "isPb", "wpm", "acc", "rawWpm", "consistency",
    "charStats", "mode", "mode2", "quoteLength", "restartCount",
    "testDuration", "afkDuration", "incompleteTestSeconds",
    "punctuation", "numbers", "language", "funbox", "difficulty",
    "lazyMode", "blindMode", "bailedOut", "tags", "timestamp",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_missing(value: Any) -> bool:
    try:
        return bool(pd.isna(value))
    except Exception:
        return False


def _json_scalar(value: Any, ndigits: int = 2) -> Any:
    """Convert pandas / numpy scalars into JSON-safe Python types."""
    if value is None:
        return None
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, (bool,)):
        return value
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (int,)):
        return value
    if isinstance(value, (np.floating, float)):
        if math.isnan(float(value)):
            return None
        return round(float(value), ndigits)
    if _is_missing(value):
        return None
    return value


def _jsonify(value: Any, ndigits: int = 2) -> Any:
    if isinstance(value, dict):
        return {str(k): _jsonify(v, ndigits=ndigits) for k, v in value.items()}
    if isinstance(value, list):
        return [_jsonify(v, ndigits=ndigits) for v in value]
    if isinstance(value, tuple):
        return [_jsonify(v, ndigits=ndigits) for v in value]
    return _json_scalar(value, ndigits=ndigits)


def _round_series(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    out = df.copy()
    for col in cols:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce").round(2)
    return out


def _round_value(value: Any, ndigits: int = 2) -> Any:
    if _is_missing(value):
        return None
    if isinstance(value, (np.integer, int, bool, np.bool_)):
        return int(value) if not isinstance(value, (bool, np.bool_)) else bool(value)
    if isinstance(value, (np.floating, float)):
        return round(float(value), ndigits)
    return value


def _iso_or_none(value: Any) -> str | None:
    if _is_missing(value):
        return None
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _num_or_none(value: Any, ndigits: int = 2) -> float | int | None:
    if _is_missing(value):
        return None
    if isinstance(value, (np.integer, int)) and not isinstance(value, bool):
        return int(value)
    if isinstance(value, (np.floating, float)):
        return round(float(value), ndigits)
    try:
        return round(float(value), ndigits)
    except Exception:
        return None


def _source_breakdown(df: pd.DataFrame) -> dict[str, int]:
    counts = df["source"].value_counts(dropna=False).to_dict() if "source" in df else {}
    return {str(k): int(v) for k, v in counts.items()}


def _weighted_mean(values: pd.Series, weights: pd.Series) -> float | None:
    values = pd.to_numeric(values, errors="coerce")
    weights = pd.to_numeric(weights, errors="coerce")
    mask = values.notna() & weights.notna()
    if not mask.any():
        return None
    total = weights[mask].sum()
    if total == 0:
        return None
    return float((values[mask] * weights[mask]).sum() / total)


def _safe_max(records: list[dict[str, Any]], key: str) -> dict[str, Any] | None:
    best = None
    best_val = None
    for record in records:
        val = record.get(key)
        if val is None:
            continue
        if best is None or val > best_val:
            best = record
            best_val = val
    return best

def apply_analysis_filters(df: pd.DataFrame) -> pd.DataFrame:
    """
    Mark warmup / calibration rows so they can be excluded from analysis
    without deleting the raw history.
    """
    out = df.copy()
    out["analysis_included"] = True

    if IGNORED_BATCHES:
        out.loc[out["batch"].isin(IGNORED_BATCHES), "analysis_included"] = False

    if CALIBRATION_SKIP_FIRST:
        ordered = out.sort_values(["dt", "batch_id", "attempt_in_batch"])
        for test_name, skip_n in CALIBRATION_SKIP_FIRST.items():
            if skip_n <= 0:
                continue
            drop_idx = ordered.index[ordered["test_name"] == test_name].tolist()[:skip_n]
            out.loc[drop_idx, "analysis_included"] = False

    return out


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Summarise Monkeytype CSV exports by test type.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "csv",
        nargs="?",
        help=(
            "Path to Monkeytype CSV export. "
            "If omitted the newest *.csv in ~/Downloads is used."
        ),
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=999,
        help="How many of the most recent batches to include.",
    )
    parser.add_argument(
        "--gap-hours",
        type=float,
        default=2.0,
        help="Silence gap (hours) that starts a new batch / session.",
    )
    parser.add_argument(
        "--drill-cycle-size",
        type=int,
        default=len(DRILL_SEQUENCE),
        help="How many 30-second drill slots form one full cycle.",
    )
    parser.add_argument(
        "--no-changes",
        action="store_true",
        help="Skip the batch-to-batch change tables (shorter output).",
    )
    parser.add_argument(
        "--add-override",
        action="store_true",
        help=(
            "Interactively record a result Monkeytype refused to save "
            "and append it to ~/Downloads/overrides.csv."
        ),
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON instead of the terminal report.",
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# CSV auto-discovery
# ---------------------------------------------------------------------------

def find_latest_csv(quiet: bool = False) -> str:
    """Return the newest .csv in ~/Downloads (excluding overrides.csv)."""
    downloads = os.path.expanduser("~/Downloads")
    candidates = glob.glob(os.path.join(downloads, "*.csv"))
    candidates = [
        c for c in candidates
        if os.path.abspath(c) != os.path.abspath(OVERRIDE_PATH)
    ]
    if not candidates:
        sys.exit(
            f"No .csv files found in {downloads}.\n"
            "Export your results from monkeytype.com and try again, "
            "or pass a path explicitly."
        )
    newest = max(candidates, key=os.path.getmtime)
    if not quiet:
        print(f"Auto-selected: {newest}\n")
    return newest


# ---------------------------------------------------------------------------
# Override — interactive entry
# ---------------------------------------------------------------------------

def _ask(prompt: str, default: str = "", validator=None) -> str:
    """Prompt, use default on bare Enter, re-prompt if validator fails."""
    while True:
        suffix = f" (default: {default}): " if default != "" else ": "
        raw = input(prompt + suffix).strip()
        value = raw if raw != "" else default
        if validator is None or validator(value):
            return value


def _ask_float(prompt: str, default: str = "") -> float:
    def v(s):
        try:
            float(s)
            return True
        except ValueError:
            print(f"  ✗  Please enter a number (got {s!r}).")
            return False
    return float(_ask(prompt, default, v))


def _ask_int(prompt: str, default: str = "",
             choices: list[int] | None = None) -> int:
    def v(s):
        try:
            n = int(s)
        except ValueError:
            print(f"  ✗  Please enter a whole number (got {s!r}).")
            return False
        if choices is not None and n not in choices:
            print(f"  ✗  Must be one of {choices}.")
            return False
        return True
    return int(_ask(prompt, default, v))


def _fake_id() -> str:
    """24-char hex string that looks like a Monkeytype _id."""
    return secrets.token_hex(12)


def add_override() -> None:
    """
    Collect one unsaved test result interactively and append it to
    overrides.csv. All fields not asked are hardcoded to standard
    custom-test defaults so the row parses identically to real exports.
    """
    now = datetime.now()
    active = {k: v for k, v in FIXED_TESTS.items() if k > 0}

    print()
    print("─" * 52)
    print("  Add override — values from your Monkeytype screenshot")
    print("─" * 52)

    # ── metrics ─────────────────────────────────────────────────────────────
    wpm = _ask_float("wpm")
    acc = _ask_float("accuracy")
    raw_wpm = _ask_float("raw wpm")
    consistency = _ask_float("consistency")
    duration = _ask_float("time (seconds)")

    # ── char count with hint table ───────────────────────────────────────────
    print()
    print("  Known tests and their character counts:")
    for total, name in sorted(active.items()):
        print(f"    {name:<14}  {total} chars")
    print()

    valid_totals = set(active.keys())

    def char_validator(s: str) -> bool:
        try:
            n = int(s)
        except ValueError:
            print(f"  ✗  Please enter a whole number (got {s!r}).")
            return False
        if n not in valid_totals:
            print(
                f"  ✗  {n} is not in the known test table.\n"
                f"     Valid counts: {sorted(valid_totals)}\n"
                f"     Add it to FIXED_TESTS in the script first."
            )
            return False
        return True

    chars = int(_ask("characters typed", validator=char_validator))

    # ── date / time ─────────────────────────────────────────────────────────
    print()
    year = _ask_int("year", default=str(now.year))
    month = _ask_int("month", default=str(now.month), choices=list(range(1, 13)))
    day = _ask_int("day", default=str(now.day), choices=list(range(1, 32)))
    hour = _ask_int("hour", default=str(now.hour), choices=list(range(0, 24)))
    minute = _ask_int("minute", default=str(now.minute), choices=list(range(0, 60)))

    try:
        dt = datetime(year, month, day, hour, minute, 0)
    except ValueError as e:
        sys.exit(f"Invalid date: {e}")

    timestamp_ms = int(dt.timestamp() * 1000)

    # ── assemble row ────────────────────────────────────────────────────────
    # charStats: "correct;incorrect;extra;missed"
    # Screenshots only show the total count (e.g. 252/0/0/0).
    # We fill incorrect/extra/missed as 0; they don't affect test identification.
    row = {
        "_id": _fake_id(),
        "isPb": False,
        "wpm": wpm,
        "acc": acc,
        "rawWpm": raw_wpm,
        "consistency": consistency,
        "charStats": f"{chars};0;0;0",
        "mode": "custom",
        "mode2": "custom",
        "quoteLength": -1,
        "restartCount": 0,
        "testDuration": duration,
        "afkDuration": 0,
        "incompleteTestSeconds": 0.0,
        "punctuation": False,
        "numbers": False,
        "language": "english",
        "funbox": float("nan"),
        "difficulty": "normal",
        "lazyMode": False,
        "blindMode": False,
        "bailedOut": False,
        "tags": float("nan"),
        "timestamp": timestamp_ms,
    }

    # ── write ────────────────────────────────────────────────────────────────
    new_df = pd.DataFrame([row], columns=CSV_COLUMNS)
    file_exists = os.path.isfile(OVERRIDE_PATH)
    new_df.to_csv(
        OVERRIDE_PATH,
        mode="a" if file_exists else "w",
        header=not file_exists,
        index=False,
    )

    test_name = active.get(chars, f"unknown ({chars} chars)")
    print()
    print(f"  ✓  {test_name}  |  {wpm} wpm  {acc}% acc  {consistency}% consistency")
    print(f"     Saved to {OVERRIDE_PATH}")
    print()


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def _parse_df(df: pd.DataFrame) -> pd.DataFrame:
    """Post-load parsing shared by the main CSV and overrides."""
    df = df.copy()
    ts_max = pd.to_numeric(df["timestamp"], errors="coerce").max()
    if pd.isna(ts_max):
        sys.exit("Could not parse the timestamp column.")
    unit = "ms" if ts_max > 10_000_000_000 else "s"
    df["dt"] = pd.to_datetime(df["timestamp"], unit=unit, errors="coerce")
    df = df.dropna(subset=["dt"]).sort_values("dt").reset_index(drop=True)

    cs = df["charStats"].astype(str).str.split(";", expand=True).astype(int)
    cs.columns = ["correct", "incorrect", "extra", "missed"]
    df["correct"] = cs["correct"]
    df["incorrect"] = cs["incorrect"]
    df["extra"] = cs["extra"]
    df["missed"] = cs["missed"]
    df["total_chars"] = cs["correct"]
    df["errors"] = cs["incorrect"] + cs["missed"]

    for col in ("wpm", "rawWpm", "acc", "consistency", "testDuration"):
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df["pb"] = (
        df["isPb"]
        .astype(str)
        .str.lower()
        .map({"true": "*", "false": ""})
        .fillna("")
    )
    return df


def load_data(csv_path: str, quiet: bool = False) -> tuple[pd.DataFrame, int]:
    """Load main CSV, merge overrides if present, parse, and return combined df."""
    df = pd.read_csv(csv_path)
    df["source"] = "monkeytype"

    required = {"timestamp", "charStats", "wpm", "rawWpm",
                "acc", "consistency", "testDuration", "isPb"}
    missing = required - set(df.columns)
    if missing:
        sys.exit(f"CSV is missing required columns: {', '.join(sorted(missing))}")

    override_count = 0
    if os.path.isfile(OVERRIDE_PATH):
        try:
            overrides = pd.read_csv(OVERRIDE_PATH)
            if not overrides.empty:
                missing_ov = required - set(overrides.columns)
                if missing_ov:
                    print(
                        f"  ⚠  overrides.csv is missing columns "
                        f"{sorted(missing_ov)} — skipping.",
                        file=sys.stderr,
                    )
                else:
                    overrides = overrides.copy()
                    overrides["source"] = "override"
                    override_count = len(overrides)
                    df = pd.concat([df, overrides], ignore_index=True)
                    if not quiet:
                        print(f"Merged {len(overrides)} override row(s) "
                              f"from {OVERRIDE_PATH}")
        except Exception as exc:
            print(f"  ⚠  Could not read overrides.csv: {exc}", file=sys.stderr)

    return _parse_df(df), override_count


# ---------------------------------------------------------------------------
# Batch segmentation
# ---------------------------------------------------------------------------

def build_batches(df: pd.DataFrame, gap_hours: float) -> pd.DataFrame:
    gap = pd.Timedelta(hours=gap_hours)
    df = df.copy()
    df["delta"] = df["dt"].diff()
    df["batch_id"] = (df["delta"].isna() | (df["delta"] > gap)).cumsum()
    batch_names = (
        df.groupby("batch_id")["dt"]
        .min()
        .dt.strftime("%Y-%m-%d %H:%M")
    )
    df["batch"] = df["batch_id"].map(batch_names)
    return df


# ---------------------------------------------------------------------------
# Test-name assignment
# ---------------------------------------------------------------------------

_ACTIVE_FIXED: dict[int, str] = {k: v for k, v in FIXED_TESTS.items() if k > 0}


def _is_fixed(total: int) -> bool:
    return total in _ACTIVE_FIXED


def assign_test_names(df: pd.DataFrame, drill_cycle_size: int) -> pd.DataFrame:
    df = df.copy()
    df["test_type"] = "other"
    df["test_name"] = None
    df["test_key"] = None
    df["attempt_in_batch"] = 0
    df["sort_order"] = 0

    fixed_order = {total: idx for idx, total in enumerate(_ACTIVE_FIXED)}

    for batch_id, batch_idx in df.groupby("batch_id").groups.items():
        idx = list(batch_idx)
        batch = df.loc[idx].sort_values("dt")

        fixed_mask = batch["total_chars"].apply(_is_fixed)
        for row_idx in batch[fixed_mask].index:
            total = int(df.at[row_idx, "total_chars"])
            name = _ACTIVE_FIXED[total]
            df.at[row_idx, "test_type"] = "fixed"
            df.at[row_idx, "test_name"] = name
            df.at[row_idx, "test_key"] = f"fixed:{total}:{name}"
            df.at[row_idx, "sort_order"] = fixed_order[total]

        drill_rows = batch[
            (~fixed_mask)
            & batch["testDuration"].between(25, 35, inclusive="both")
        ].sort_values("dt")

        for pos, row_idx in enumerate(drill_rows.index):
            cycle = pos // drill_cycle_size + 1
            slot = pos % drill_cycle_size
            base_name = DRILL_SEQUENCE[slot]
            name = base_name if cycle == 1 else f"{base_name} #{cycle}"
            df.at[row_idx, "test_type"] = "drill"
            df.at[row_idx, "test_name"] = name
            df.at[row_idx, "test_key"] = f"drill:{slot}:{cycle}:{base_name}"
            df.at[row_idx, "sort_order"] = 100 + (cycle - 1) * drill_cycle_size + slot

        unknown = batch[df.loc[idx, "test_name"].isna()]
        for row_idx in unknown.index:
            total = int(df.at[row_idx, "total_chars"])
            dur = df.at[row_idx, "testDuration"]
            dur_text = "na" if pd.isna(dur) else f"{dur:.2f}"
            name = f"unknown_{total}_{dur_text}"
            df.at[row_idx, "test_type"] = "other"
            df.at[row_idx, "test_name"] = name
            df.at[row_idx, "test_key"] = f"other:{total}:{dur_text}"
            df.at[row_idx, "sort_order"] = 1000 + total

        df.loc[batch.index, "attempt_in_batch"] = range(1, len(batch) + 1)

    return df


# ---------------------------------------------------------------------------
# JSON export construction
# ---------------------------------------------------------------------------

def _make_attempt_record(row: pd.Series) -> dict[str, Any]:
    return {
        "attempt_id": _json_scalar(row.get("_id")),
        "source": _json_scalar(row.get("source")),
        "session_id": _json_scalar(row.get("batch_id")),
        "session_label": _json_scalar(row.get("batch")),
        "session_started_at": _iso_or_none(row.get("batch_start")),
        "session_datetime": _iso_or_none(row.get("dt")),
        "attempt_in_session": _json_scalar(row.get("attempt_in_batch")),
        "test_type": _json_scalar(row.get("test_type")),
        "test_name": _json_scalar(row.get("test_name")),
        "test_key": _json_scalar(row.get("test_key")),
        "sort_order": _json_scalar(row.get("sort_order")),
        "mode": _json_scalar(row.get("mode")),
        "mode2": _json_scalar(row.get("mode2")),
        "test_duration": _num_or_none(row.get("testDuration")),
        "wpm": _num_or_none(row.get("wpm")),
        "raw_wpm": _num_or_none(row.get("rawWpm")),
        "acc": _num_or_none(row.get("acc")),
        "consistency": _num_or_none(row.get("consistency")),
        "is_pb": bool(row.get("isPb")) if not _is_missing(row.get("isPb")) else None,
        "pb_flag": _json_scalar(row.get("pb")),
        "total_chars": _json_scalar(row.get("total_chars")),
        "correct": _json_scalar(row.get("correct")),
        "incorrect": _json_scalar(row.get("incorrect")),
        "extra": _json_scalar(row.get("extra")),
        "missed": _json_scalar(row.get("missed")),
        "errors": _json_scalar(row.get("errors")),
        "char_stats": _json_scalar(row.get("charStats")),
        "punctuation": bool(row.get("punctuation")) if not _is_missing(row.get("punctuation")) else None,
        "numbers": bool(row.get("numbers")) if not _is_missing(row.get("numbers")) else None,
        "language": _json_scalar(row.get("language")),
        "difficulty": _json_scalar(row.get("difficulty")),
        "lazy_mode": bool(row.get("lazyMode")) if not _is_missing(row.get("lazyMode")) else None,
        "blind_mode": bool(row.get("blindMode")) if not _is_missing(row.get("blindMode")) else None,
        "bailed_out": bool(row.get("bailedOut")) if not _is_missing(row.get("bailedOut")) else None,
        "quote_length": _json_scalar(row.get("quoteLength")),
        "restart_count": _json_scalar(row.get("restartCount")),
        "afk_duration": _num_or_none(row.get("afkDuration")),
        "incomplete_test_seconds": _num_or_none(row.get("incompleteTestSeconds")),
        "timestamp_ms": _json_scalar(row.get("timestamp")),
    }


def _compute_session_summary(session_rows: pd.DataFrame) -> dict[str, Any]:
    named = session_rows[session_rows["test_name"].notna()].copy()
    if named.empty:
        return {
            "named_test_count": 0,
            "drill_count": int((session_rows["test_type"] == "drill").sum()),
            "attempt_count": int(len(session_rows)),
            "source_breakdown": _source_breakdown(session_rows),
        }

    return {
        "named_test_count": int((session_rows["test_type"] != "drill").sum()),
        "drill_count": int((session_rows["test_type"] == "drill").sum()),
        "attempt_count": int(len(session_rows)),
        "source_breakdown": _source_breakdown(session_rows),
        "wpm_mean": _num_or_none(named["wpm"].mean()),
        "raw_wpm_mean": _num_or_none(named["rawWpm"].mean()),
        "acc_mean": _num_or_none(named["acc"].mean()),
        "consistency_mean": _num_or_none(named["consistency"].mean()),
    }


def _build_test_entry(record: dict[str, Any], previous: dict[str, Any] | None = None) -> dict[str, Any]:
    entry = {
        "session_id": record["session_id"],
        "session_label": record["session_label"],
        "session_datetime": record["session_datetime"],
        "session_started_at": record["session_started_at"],
        "attempt_in_session": record["attempt_in_session"],
        "test_key": record["test_key"],
        "test_type": record["test_type"],
        "source": record["source"],
        "wpm": record["wpm"],
        "raw_wpm": record["raw_wpm"],
        "acc": record["acc"],
        "consistency": record["consistency"],
        "test_duration": record["test_duration"],
        "total_chars": record["total_chars"],
        "correct": record["correct"],
        "errors": record["errors"],
        "pb_flag": record["pb_flag"],
        "timestamp_ms": record["timestamp_ms"],
    }
    if previous is None:
        entry.update({
            "wpm_delta": None,
            "raw_wpm_delta": None,
            "acc_delta": None,
            "consistency_delta": None,
            "test_duration_delta": None,
        })
    else:
        entry.update({
            "wpm_delta": _num_or_none(record["wpm"] - previous["wpm"]) if record["wpm"] is not None and previous["wpm"] is not None else None,
            "raw_wpm_delta": _num_or_none(record["raw_wpm"] - previous["raw_wpm"]) if record["raw_wpm"] is not None and previous["raw_wpm"] is not None else None,
            "acc_delta": _num_or_none(record["acc"] - previous["acc"]) if record["acc"] is not None and previous["acc"] is not None else None,
            "consistency_delta": _num_or_none(record["consistency"] - previous["consistency"]) if record["consistency"] is not None and previous["consistency"] is not None else None,
            "test_duration_delta": _num_or_none(record["test_duration"] - previous["test_duration"]) if record["test_duration"] is not None and previous["test_duration"] is not None else None,
        })
    return entry


def _build_trend(history: list[dict[str, Any]]) -> dict[str, Any]:
    wpm_values = [h["wpm"] for h in history if h.get("wpm") is not None]
    if not wpm_values:
        return {
            "latest_wpm": None,
            "best_wpm": None,
            "last_3_avg_wpm": None,
            "last_5_avg_wpm": None,
            "improvement_since_first": None,
        }

    latest = wpm_values[-1]
    first = wpm_values[0]
    last_3 = wpm_values[-3:]
    last_5 = wpm_values[-5:]
    return {
        "latest_wpm": _num_or_none(latest),
        "best_wpm": _num_or_none(max(wpm_values)),
        "last_3_avg_wpm": _num_or_none(sum(last_3) / len(last_3)),
        "last_5_avg_wpm": _num_or_none(sum(last_5) / len(last_5)),
        "improvement_since_first": _num_or_none(latest - first),
    }


def _build_personal_best(history: list[dict[str, Any]]) -> dict[str, Any] | None:
    valid = [h for h in history if h.get("wpm") is not None]
    if not valid:
        return None
    best = max(valid, key=lambda h: (h["wpm"], h.get("acc") or -1, h.get("consistency") or -1))
    return {
        "wpm": _num_or_none(best.get("wpm")),
        "acc": _num_or_none(best.get("acc")),
        "consistency": _num_or_none(best.get("consistency")),
        "achieved_in_session": best.get("session_label"),
        "achieved_at": best.get("session_datetime"),
        "test_key": best.get("test_key"),
        "source": best.get("source"),
        "timestamp_ms": best.get("timestamp_ms"),
    }



def build_json_export(
    df: pd.DataFrame,
    batches: list[str],
    csv_path: str,
    override_path: str,
    override_count: int,
    gap_hours: float,
    drill_cycle_size: int,
) -> dict[str, Any]:
    selected = df[df["batch"].isin(batches)].copy()

    # Build one canonical record per attempt, in chronological order.
    selected_sorted = selected.sort_values(["dt", "batch_id", "attempt_in_batch"]).copy()
    record_map: dict[int, dict[str, Any]] = {}
    test_history: dict[str, dict[str, Any]] = {}
    previous_global: dict[str, dict[str, Any]] = {}

    for row_idx, row in selected_sorted.iterrows():
        record = _make_attempt_record(row)
        record_map[int(row_idx)] = record

        history_key = record["test_name"] or record["test_key"] or "unknown"
        history_root = test_history.setdefault(
            history_key,
            {
                "test_name": record["test_name"],
                "test_key": record["test_key"],
                "test_type": record["test_type"],
                "history": [],
                "personal_best": None,
                "trend": None,
                "source_breakdown": {},
            },
        )
        prev = previous_global.get(history_key)
        history_entry = _build_test_entry(record, previous=prev)
        history_root["history"].append(history_entry)
        previous_global[history_key] = record

    sessions: list[dict[str, Any]] = []
    for batch_id, batch_df in selected.groupby("batch_id", sort=True):
        batch_df = batch_df.sort_values("dt").copy()
        session_label = batch_df["batch"].iloc[0]
        session_start = batch_df["dt"].min()
        session_end = batch_df["dt"].max()
        session_obj = {
            "session_id": _json_scalar(batch_id),
            "batch_label": session_label,
            "batch_started_at": _iso_or_none(session_start),
            "batch_ended_at": _iso_or_none(session_end),
            "attempt_count": int(len(batch_df)),
            "summary": _compute_session_summary(batch_df),
            "tests": {},
            "drills": [],
            "attempts": [],
        }
        for row_idx, row in batch_df.iterrows():
            record = record_map[int(row_idx)]
            session_obj["attempts"].append(record)
            if record["test_type"] == "drill":
                session_obj["drills"].append(record)
            elif record["test_name"]:
                session_obj["tests"][record["test_name"]] = record
        sessions.append(_jsonify(session_obj))

    batch_summary_rows = [_jsonify(row) for row in _build_batch_summary_rows(selected)]

    for payload in test_history.values():
        history = payload["history"]
        payload["personal_best"] = _build_personal_best(history)
        payload["trend"] = _build_trend(history)
        payload["source_breakdown"] = _source_breakdown(
            pd.DataFrame(history) if history else pd.DataFrame(columns=["source"])
        )
        payload["history"] = [_jsonify(item) for item in history]

    meta = {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "script_version": SCRIPT_VERSION,
        "schema_version": SCHEMA_VERSION,
        "csv_path": csv_path,
        "override_path": override_path,
        "override_count": int(override_count),
        "gap_hours": _num_or_none(gap_hours),
        "drill_cycle_size": int(drill_cycle_size),
        "total_rows": int(len(df)),
        "selected_rows": int(len(selected)),
        "selected_session_count": int(len(sessions)),
        "all_session_count": int(df["batch_id"].nunique()),
        "selected_batches": list(batches),
        "selected_batch_count": int(len(batches)),
        "total_tests_tracked": int(len(test_history)),
    }

    return {
        "meta": meta,
        "sessions": sessions,
        "batch_summary": batch_summary_rows,
        "test_history": _jsonify(test_history),
    }


def _build_batch_summary_rows(batch_df: pd.DataFrame) -> list[dict[str, Any]]:
    summary = (
        batch_df.groupby(["batch", "test_name"], as_index=False)
        .agg(
            session_id=("batch_id", "first"),
            session_started_at=("dt", "min"),
            session_ended_at=("dt", "max"),
            test_type=("test_type", "first"),
            test_key=("test_key", "first"),
            sort_order=("sort_order", "min"),
            samples=("test_name", "size"),
            total_chars=("total_chars", "first"),
            correct=("correct", "mean"),
            errors=("errors", "mean"),
            dur_avg=("testDuration", "mean"),
            wpm=("wpm", "mean"),
            rawWpm=("rawWpm", "mean"),
            acc=("acc", "mean"),
            consistency=("consistency", "mean"),
            pb_count=("pb", lambda s: (s == "*").sum()),
            source_breakdown=("source", lambda s: _source_breakdown(pd.DataFrame({"source": s}))),
        )
        .sort_values(["batch", "sort_order", "test_name"])
        .reset_index(drop=True)
    )

    rows: list[dict[str, Any]] = []
    for _, row in summary.iterrows():
        rows.append({
            "session_id": _json_scalar(row["session_id"]),
            "batch_label": _json_scalar(row["batch"]),
            "session_started_at": _iso_or_none(row["session_started_at"]),
            "session_ended_at": _iso_or_none(row["session_ended_at"]),
            "test_name": _json_scalar(row["test_name"]),
            "test_type": _json_scalar(row["test_type"]),
            "test_key": _json_scalar(row["test_key"]),
            "sort_order": _json_scalar(row["sort_order"]),
            "samples": _json_scalar(row["samples"]),
            "total_chars": _json_scalar(row["total_chars"]),
            "correct": _num_or_none(row["correct"]),
            "errors": _num_or_none(row["errors"]),
            "dur_avg": _num_or_none(row["dur_avg"]),
            "wpm": _num_or_none(row["wpm"]),
            "raw_wpm": _num_or_none(row["rawWpm"]),
            "acc": _num_or_none(row["acc"]),
            "consistency": _num_or_none(row["consistency"]),
            "pb_count": _json_scalar(row["pb_count"]),
            "source_breakdown": _jsonify(row["source_breakdown"]),
        })
    return rows


# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------

def _sep(label: str = "") -> None:
    print()
    print(SEP)
    if label:
        print(label)
        print(SEP)


def print_raw_attempts(df: pd.DataFrame, batches: list[str]) -> None:
    _sep("RAW ATTEMPTS")
    view = (
        df[df["batch"].isin(batches)][RAW_COLS]
        .copy()
        .round({"testDuration": 2, "wpm": 2, "rawWpm": 2,
                "acc": 2, "consistency": 2})
    )
    print(view.to_string(index=False))


def summarize_batches(df: pd.DataFrame, batches: list[str]) -> pd.DataFrame:
    return (
        df[df["batch"].isin(batches)]
        .groupby(["batch", "test_name"], as_index=False)
        .agg(
            test_type=("test_type", "first"),
            test_key=("test_key", "first"),
            sort_order=("sort_order", "min"),
            samples=("test_name", "size"),
            total_chars=("total_chars", "first"),
            correct=("correct", "mean"),
            errors=("errors", "mean"),
            dur_avg=("testDuration", "mean"),
            wpm=("wpm", "mean"),
            rawWpm=("rawWpm", "mean"),
            acc=("acc", "mean"),
            consistency=("consistency", "mean"),
            pb_count=("pb", lambda s: (s == "*").sum()),
        )
        .sort_values(["batch", "sort_order", "test_name"])
        .reset_index(drop=True)
    )


def print_summary(summary: pd.DataFrame, show_changes: bool) -> None:
    _sep("BATCH SUMMARY")
    display_cols = [
        "batch", "test_name", "test_type", "sort_order",
        "samples", "total_chars", "dur_avg",
        "wpm", "rawWpm", "acc", "consistency", "pb_count",
    ]
    print(summary[display_cols].round(2).to_string(index=False))

    if not show_changes:
        return

    _sep("BATCH-TO-BATCH CHANGES")
    for test_name, grp in summary.groupby("test_name", sort=False):
        grp = grp.sort_values("batch").reset_index(drop=True)
        if len(grp) < 2:
            continue
        print()
        print(test_name.upper())
        show = ["batch", "samples", "total_chars", "wpm", "rawWpm",
                "acc", "consistency"]
        print(grp[show].round(2).to_string(index=False))
        diffs = grp.copy()
        for col in ("wpm", "rawWpm", "acc", "consistency"):
            diffs[col] = diffs[col].diff()
        print("changes vs previous batch:")
        print(
            diffs[["batch", "wpm", "rawWpm", "acc", "consistency"]]
            .round(2).to_string(index=False)
        )


def print_pb_summary(df: pd.DataFrame, batches: list[str]) -> None:
    fixed = df[
        (df["batch"].isin(batches)) & (df["test_type"] == "fixed")
    ].copy()
    if fixed.empty:
        return
    best = (
        fixed.groupby("test_name", as_index=False)
        .agg(
            best_wpm=("wpm", "max"),
            best_acc=("acc", "max"),
            best_consistency=("consistency", "max"),
            runs=("wpm", "count"),
            pb_flags=("pb", lambda s: (s == "*").sum()),
        )
        .sort_values("best_wpm", ascending=False)
    )
    _sep("PERSONAL BESTS  (fixed tests, within selected batches)")
    print(best.round(2).to_string(index=False))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    args = parse_args()

    if args.add_override:
        add_override()
        return

    csv_path = args.csv or find_latest_csv(quiet=args.json)
    df, override_count = load_data(csv_path, quiet=args.json)
    
    df = build_batches(df, args.gap_hours)
    df = assign_test_names(df, args.drill_cycle_size)
    df = apply_analysis_filters(df)

    analysis_df = df[df["analysis_included"]].copy()

    all_batches: list[str] = df["batch"].drop_duplicates().tolist()
    batches = all_batches[-args.runs:]

    if args.json:
        export = build_json_export(
            df=analysis_df,
            batches=batches,
            csv_path=csv_path,
            override_path=OVERRIDE_PATH,
            override_count=override_count,
            gap_hours=args.gap_hours,
            drill_cycle_size=args.drill_cycle_size,
        )
        print(json.dumps(export, indent=2, ensure_ascii=False))
        return

    print()
    print("Batches:")
    for b in batches:
        print(f"  {b}")

    pending = {k: v for k, v in FIXED_TESTS.items() if k <= 0}
    if pending:
        print()
        print("Pending v2 tests (update char counts in FIXED_TESTS once measured):")
        for k, name in pending.items():
            print(f"  {name:<15}  placeholder key={k}")

    print_raw_attempts(df, batches)
    summary = summarize_batches(df, batches)
    print_summary(summary, show_changes=not args.no_changes)
    print_pb_summary(df, batches)


if __name__ == "__main__":
    main()
