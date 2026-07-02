"""MP4 encoding command construction."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .blender import frame_number_width


@dataclass(frozen=True, slots=True)
class EncodePlan:
    """Information required to encode a rendered frame sequence."""

    png_dir: Path
    output_file: Path
    start_frame: int
    end_frame: int
    fps: float

    @property
    def pattern(self) -> str:
        width = frame_number_width(self.start_frame, self.end_frame)
        return str(self.png_dir / f"%0{width}d.png")


def build_ffmpeg_command(ffmpeg_executable: str, plan: EncodePlan) -> list[str]:
    """Build the NVENC-based ffmpeg command."""

    return [
        ffmpeg_executable,
        "-y",
        "-framerate",
        f"{plan.fps:.6f}".rstrip("0").rstrip("."),
        "-start_number",
        str(plan.start_frame),
        "-i",
        plan.pattern,
        "-c:v",
        "h264_nvenc",
        "-preset",
        "p5",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        str(plan.output_file),
    ]
