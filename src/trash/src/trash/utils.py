from __future__ import annotations

import json
import os
import re
import tempfile
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator

from config import JSON_INDENT, MAX_LABEL_LENGTH

_ALLOWED_LABEL_RE = re.compile(r"[\w\-.]+", re.UNICODE)
_SEP_RE = re.compile(r"[-\s_]+", re.UNICODE)


def utc_now() -> datetime:
    return datetime.now(timezone.utc).astimezone()


def now_unix() -> int:
    return int(utc_now().timestamp())


def now_iso() -> str:
    return utc_now().isoformat(timespec="seconds")


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def atomic_write_text(path: Path, text: str, *, encoding: str = "utf-8") -> None:
    ensure_parent(path)
    with tempfile.NamedTemporaryFile(
        "w", delete=False, dir=str(path.parent), encoding=encoding, newline=""
    ) as tmp:
        tmp.write(text)
        tmp_path = Path(tmp.name)
    os.replace(tmp_path, path)


def _json_default(obj: Any) -> Any:
    if is_dataclass(obj):
        return asdict(obj)  # pyright: ignore[reportArgumentType]
    if isinstance(obj, Path):
        return str(obj)
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def atomic_write_json(path: Path, data: Any) -> None:
    text = json.dumps(
        data,
        ensure_ascii=False,
        indent=JSON_INDENT,
        sort_keys=True,
        default=_json_default,
    )
    atomic_write_text(path, text)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def human_size(num_bytes: int) -> str:
    units = ["B", "KiB", "MiB", "GiB", "TiB", "PiB"]
    value = float(num_bytes)
    for unit in units:
        if abs(value) < 1024.0 or unit == units[-1]:
            if unit == "B":
                return f"{int(value)} B"
            return f"{value:.1f} {unit}"
        value /= 1024.0
    return f"{num_bytes} B"


def flatten_paths(paths: Iterable[Path]) -> list[Path]:
    return [Path(p) for p in paths]


def path_to_label_fragment(path: Path) -> str:
    name = path.name or path.anchor or str(path)
    if name in {"", ".", "/"}:
        name = "unnamed"
    return sanitize_label(name)


def sanitize_label(value: str, *, max_length: int = MAX_LABEL_LENGTH) -> str:
    value = value.strip().lower()
    value = value.replace("$", "")
    value = value.replace("\\", "/")
    value = value.replace("/", "-")
    value = _SEP_RE.sub("-", value)
    pieces: list[str] = []
    for char in value:
        if char.isalnum() or char in {"-", "."}:
            pieces.append(char)
        elif char in {" ", "_"}:
            pieces.append("-")
        # discard unsafe filesystem characters but keep readable unicode
    normalized = "".join(pieces)
    normalized = re.sub(r"[-.]{2,}", lambda m: m.group(0)[0], normalized)
    normalized = normalized.strip("-.")
    normalized = re.sub(r"-{2,}", "-", normalized)
    if len(normalized) > max_length:
        normalized = normalized[:max_length].rstrip("-.")
    return normalized


def generate_label_from_paths(paths: Iterable[Path]) -> str:
    fragments = [path_to_label_fragment(path) for path in paths]
    fragments = [fragment for fragment in fragments if fragment]
    if not fragments:
        return ""
    label = "-".join(fragments)
    label = sanitize_label(label)
    return label


def prompt_for_label() -> str:
    if not os.isatty(0):
        raise RuntimeError(
            "Cannot prompt for a label because stdin is not interactive."
        )
    while True:
        try:
            response = input(
                "Unable to generate label automatically.\n\nPlease provide a label: "
            ).strip()
        except EOFError:
            response = ""
        if response:
            label = sanitize_label(response)
            if label:
                return label
            print("Label is unusable after sanitization. Try again.")
            continue
        return "unnamed"


def iter_path_ancestors(path: Path) -> Iterator[Path]:
    current = path
    while True:
        yield current
        if current.parent == current:
            break
        current = current.parent


def format_key_value_block(mapping: dict[str, Any]) -> str:
    lines: list[str] = []
    for key, value in mapping.items():
        if isinstance(value, list):
            rendered = ", ".join(map(str, value))
        else:
            rendered = str(value)
        lines.append(f"{key}: {rendered}")
    return "\n".join(lines)


def unique_preserve_order(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result
