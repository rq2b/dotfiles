#!/usr/bin/env python3
"""
monkeytype.py — Summarise Monkeytype CSV exports by test type.

Drop in ~/bin (or anywhere on $PATH), chmod +x, then run:
    monkeytype.py                  # auto-finds newest CSV in ~/Downloads
    monkeytype.py my.csv           # explicit path
    monkeytype.py --runs 3         # last 3 batches only
    monkeytype.py --add-override   # interactively record a result that
                                   # Monkeytype refused to save
"""

import argparse
import glob
import os
import secrets
import sys
from collections import OrderedDict
from datetime import datetime

import pandas as pd


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
    return parser.parse_args()


# ---------------------------------------------------------------------------
# CSV auto-discovery
# ---------------------------------------------------------------------------

def find_latest_csv() -> str:
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
    print(f"Auto-selected: {newest}\n")
    return newest


# ---------------------------------------------------------------------------
# Override — interactive entry
# ---------------------------------------------------------------------------

def _ask(prompt: str, default: str = "", validator=None) -> str:
    """Prompt, use default on bare Enter, re-prompt if validator fails."""
    while True:
        suffix = f" (default: {default}): " if default != "" else ": "
        raw    = input(prompt + suffix).strip()
        value  = raw if raw != "" else default
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
    overrides.csv.  All fields not asked are hardcoded to standard
    custom-test defaults so the row parses identically to real exports.
    """
    now    = datetime.now()
    active = {k: v for k, v in FIXED_TESTS.items() if k > 0}

    print()
    print("─" * 52)
    print("  Add override — values from your Monkeytype screenshot")
    print("─" * 52)

    # ── metrics ─────────────────────────────────────────────────────────────
    wpm         = _ask_float("wpm")
    acc         = _ask_float("accuracy")
    raw_wpm     = _ask_float("raw wpm")
    consistency = _ask_float("consistency")
    duration    = _ask_float("time (seconds)")

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
    year   = _ask_int("year",   default=str(now.year))
    month  = _ask_int("month",  default=str(now.month),  choices=list(range(1,  13)))
    day    = _ask_int("day",    default=str(now.day),    choices=list(range(1,  32)))
    hour   = _ask_int("hour",   default=str(now.hour),   choices=list(range(0,  24)))
    minute = _ask_int("minute", default=str(now.minute), choices=list(range(0,  60)))

    try:
        dt = datetime(year, month, day, hour, minute, 0)
    except ValueError as e:
        sys.exit(f"Invalid date: {e}")

    timestamp_ms = int(dt.timestamp() * 1000)

    # ── assemble row ─────────────────────────────────────────────────────────
    # charStats: "correct;incorrect;extra;missed"
    # Screenshots only show the total count (e.g. 252/0/0/0).
    # We fill incorrect/extra/missed as 0; they don't affect test identification.
    row = {
        "_id":                   _fake_id(),
        "isPb":                  False,
        "wpm":                   wpm,
        "acc":                   acc,
        "rawWpm":                raw_wpm,
        "consistency":           consistency,
        "charStats":             f"{chars};0;0;0",
        "mode":                  "custom",
        "mode2":                 "custom",
        "quoteLength":           -1,
        "restartCount":          0,
        "testDuration":          duration,
        "afkDuration":           0,
        "incompleteTestSeconds": 0.0,
        "punctuation":           False,
        "numbers":               False,
        "language":              "english",
        "funbox":                float("nan"),
        "difficulty":            "normal",
        "lazyMode":              False,
        "blindMode":             False,
        "bailedOut":             False,
        "tags":                  float("nan"),
        "timestamp":             timestamp_ms,
    }

    # ── write ────────────────────────────────────────────────────────────────
    new_df      = pd.DataFrame([row], columns=CSV_COLUMNS)
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
    ts_max = pd.to_numeric(df["timestamp"], errors="coerce").max()
    if pd.isna(ts_max):
        sys.exit("Could not parse the timestamp column.")
    unit   = "ms" if ts_max > 10_000_000_000 else "s"
    df["dt"] = pd.to_datetime(df["timestamp"], unit=unit, errors="coerce")
    df = df.dropna(subset=["dt"]).sort_values("dt").reset_index(drop=True)

    cs = df["charStats"].astype(str).str.split(";", expand=True).astype(int)
    cs.columns        = ["correct", "incorrect", "extra", "missed"]
    df["correct"]     = cs["correct"]
    df["incorrect"]   = cs["incorrect"]
    df["extra"]       = cs["extra"]
    df["missed"]      = cs["missed"]
    df["total_chars"] = cs.sum(axis=1)
    df["errors"]      = cs["incorrect"] + cs["missed"]

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


def load_data(csv_path: str) -> pd.DataFrame:
    """Load main CSV, merge overrides if present, parse, return combined df."""
    df = pd.read_csv(csv_path)

    required = {"timestamp", "charStats", "wpm", "rawWpm",
                "acc", "consistency", "testDuration", "isPb"}
    missing  = required - set(df.columns)
    if missing:
        sys.exit(f"CSV is missing required columns: {', '.join(sorted(missing))}")

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
                    df = pd.concat([df, overrides], ignore_index=True)
                    print(f"Merged {len(overrides)} override row(s) "
                          f"from {OVERRIDE_PATH}")
        except Exception as exc:
            print(f"  ⚠  Could not read overrides.csv: {exc}", file=sys.stderr)

    return _parse_df(df)


# ---------------------------------------------------------------------------
# Batch segmentation
# ---------------------------------------------------------------------------

def build_batches(df: pd.DataFrame, gap_hours: float) -> pd.DataFrame:
    gap        = pd.Timedelta(hours=gap_hours)
    df         = df.copy()
    df["delta"]    = df["dt"].diff()
    df["batch_id"] = (df["delta"].isna() | (df["delta"] > gap)).cumsum()
    batch_names    = (
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
    df["test_type"]        = "other"
    df["test_name"]        = None
    df["test_key"]         = None
    df["attempt_in_batch"] = 0
    df["sort_order"]       = 0

    fixed_order = {total: idx for idx, total in enumerate(_ACTIVE_FIXED)}

    for batch_id, batch_idx in df.groupby("batch_id").groups.items():
        idx   = list(batch_idx)
        batch = df.loc[idx].sort_values("dt")

        fixed_mask = batch["total_chars"].apply(_is_fixed)
        for row_idx in batch[fixed_mask].index:
            total = int(df.at[row_idx, "total_chars"])
            name  = _ACTIVE_FIXED[total]
            df.at[row_idx, "test_type"]  = "fixed"
            df.at[row_idx, "test_name"]  = name
            df.at[row_idx, "test_key"]   = f"fixed:{total}:{name}"
            df.at[row_idx, "sort_order"] = fixed_order[total]

        drill_rows = batch[
            (~fixed_mask)
            & batch["testDuration"].between(25, 35, inclusive="both")
        ].sort_values("dt")

        for pos, row_idx in enumerate(drill_rows.index):
            cycle     = pos // drill_cycle_size + 1
            slot      = pos % drill_cycle_size
            base_name = DRILL_SEQUENCE[slot]
            name      = base_name if cycle == 1 else f"{base_name} #{cycle}"
            df.at[row_idx, "test_type"]  = "drill"
            df.at[row_idx, "test_name"]  = name
            df.at[row_idx, "test_key"]   = f"drill:{slot}:{cycle}:{base_name}"
            df.at[row_idx, "sort_order"] = (
                100 + (cycle - 1) * drill_cycle_size + slot
            )

        unknown = batch[df.loc[idx, "test_name"].isna()]
        for row_idx in unknown.index:
            total    = int(df.at[row_idx, "total_chars"])
            dur      = df.at[row_idx, "testDuration"]
            dur_text = "na" if pd.isna(dur) else f"{dur:.2f}"
            name     = f"unknown_{total}_{dur_text}"
            df.at[row_idx, "test_type"]  = "other"
            df.at[row_idx, "test_name"]  = name
            df.at[row_idx, "test_key"]   = f"other:{total}:{dur_text}"
            df.at[row_idx, "sort_order"] = 1000 + total

        df.loc[batch.index, "attempt_in_batch"] = range(1, len(batch) + 1)

    return df


# ---------------------------------------------------------------------------
# Display
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
            test_type   = ("test_type",    "first"),
            sort_order  = ("sort_order",   "min"),
            samples     = ("test_name",    "size"),
            total_chars = ("total_chars",  "first"),
            correct     = ("correct",      "mean"),
            errors      = ("errors",       "mean"),
            dur_avg     = ("testDuration", "mean"),
            wpm         = ("wpm",          "mean"),
            rawWpm      = ("rawWpm",       "mean"),
            acc         = ("acc",          "mean"),
            consistency = ("consistency",  "mean"),
            pb_count    = ("pb",           lambda s: (s == "*").sum()),
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
            best_wpm         = ("wpm",         "max"),
            best_acc         = ("acc",         "max"),
            best_consistency = ("consistency", "max"),
            runs             = ("wpm",         "count"),
            pb_flags         = ("pb",          lambda s: (s == "*").sum()),
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

    csv_path = args.csv or find_latest_csv()
    df       = load_data(csv_path)
    df       = build_batches(df, args.gap_hours)
    df       = assign_test_names(df, args.drill_cycle_size)

    all_batches: list[str] = df["batch"].drop_duplicates().tolist()
    batches = all_batches[-args.runs:]

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
