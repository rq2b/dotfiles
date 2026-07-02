"""Blender metadata queries and render command construction."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import subprocess
from typing import Sequence

from .exceptions import RenderJobConfigurationError


@dataclass(frozen=True, slots=True)
class SceneInfo:
    """Basic render metadata extracted from Blender."""

    frame_start: int
    frame_end: int
    fps: int
    fps_base: float

    @property
    def fps_effective(self) -> float:
        base = self.fps_base if self.fps_base else 1.0
        return self.fps / base


def _parse_json_from_output(output: str) -> dict[str, object]:
    for line in reversed(output.splitlines()):
        line = line.strip()
        if not line:
            continue
        if line.startswith("{") and line.endswith("}"):
            return json.loads(line)
    raise RenderJobConfigurationError(
        "Failed to parse Blender metadata output. "
        "The Blender query did not return JSON as expected."
    )


def query_scene_info(blender_executable: str, blend_file: Path) -> SceneInfo:
    """Read the active scene's frame range and FPS from Blender."""

    expr = (
        "import bpy, json; "
        "s=bpy.context.scene; "
        "print(json.dumps({"
        "'frame_start': int(s.frame_start), "
        "'frame_end': int(s.frame_end), "
        "'fps': int(s.render.fps), "
        "'fps_base': float(s.render.fps_base), "
        "}))"
    )
    result = subprocess.run(
        [blender_executable, "--background", str(blend_file), "--python-expr", expr],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = _parse_json_from_output(result.stdout)
    try:
        return SceneInfo(
            frame_start=int(payload["frame_start"]),
            frame_end=int(payload["frame_end"]),
            fps=int(payload["fps"]),
            fps_base=float(payload["fps_base"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise RenderJobConfigurationError(
            f"Unexpected Blender metadata payload: {payload!r}"
        ) from exc


def format_frame_number(frame: int, width: int) -> str:
    return f"{frame:0{width}d}"


def frame_number_width(*frame_numbers: int) -> int:
    return max(4, max(len(str(number)) for number in frame_numbers if number is not None))


def build_blender_command(
    blender_executable: str,
    blend_file: Path,
    png_dir: Path,
    start_frame: int,
    end_frame: int,
) -> list[str]:
    """Build the Blender background-mode render command."""

    width = frame_number_width(start_frame, end_frame)
    output_base = png_dir / ("#" * width)
    return [
        blender_executable,
        "--background",
        str(blend_file),
        "-o",
        str(output_base),
        "-F",
        "PNG",
        "-s",
        str(start_frame),
        "-e",
        str(end_frame),
        "-a",
    ]


def build_blender_query_command(blender_executable: str, blend_file: Path) -> list[str]:
    """Return the command used to query Blender metadata.

    Useful for testing and documentation.
    """

    expr = (
        "import bpy, json; "
        "s=bpy.context.scene; "
        "print(json.dumps({"
        "'frame_start': int(s.frame_start), "
        "'frame_end': int(s.frame_end), "
        "'fps': int(s.render.fps), "
        "'fps_base': float(s.render.fps_base), "
        "}))"
    )
    return [blender_executable, "--background", str(blend_file), "--python-expr", expr]
