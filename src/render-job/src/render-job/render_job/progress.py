"""Progress summary helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import math

from .job import scan_existing_frames


@dataclass(frozen=True, slots=True)
class RenderPlanSummary:
    """Preflight progress summary for a planned render."""

    job_name: str
    start_frame: int
    end_frame: int
    existing_png_count: int
    existing_highest_frame: int | None

    @property
    def frames_to_render(self) -> int:
        return max(0, self.end_frame - self.start_frame + 1)

    def format(self) -> str:
        highest = (
            str(self.existing_highest_frame).zfill(4)
            if self.existing_highest_frame is not None
            else "none"
        )
        return (
            f"Job: {self.job_name}\n"
            f"Resume point: {self.start_frame}\n"
            f"End frame: {self.end_frame}\n"
            f"Existing PNGs: {self.existing_png_count} (highest: {highest})\n"
            f"Frames to render this run: {self.frames_to_render}"
        )


@dataclass(frozen=True, slots=True)
class AttemptSummary:
    """Summary of a render attempt inside the tmux session."""

    job_name: str
    start_frame: int
    end_frame: int
    elapsed_seconds: int

    @property
    def frames_rendered(self) -> int:
        return max(0, self.end_frame - self.start_frame + 1)

    @property
    def average_frame_seconds(self) -> float:
        if self.frames_rendered == 0:
            return 0.0
        return self.elapsed_seconds / self.frames_rendered

    def format(self) -> str:
        avg = f"{self.average_frame_seconds:.2f}"
        return (
            f"Render attempt complete\n"
            f"Job: {self.job_name}\n"
            f"Frames rendered: {self.frames_rendered}\n"
            f"Elapsed time: {self.elapsed_seconds}s\n"
            f"Average frame time: {avg}s"
        )


def build_preflight_summary(job_name: str, png_dir: Path, start_frame: int, end_frame: int) -> RenderPlanSummary:
    existing = scan_existing_frames(png_dir)
    return RenderPlanSummary(
        job_name=job_name,
        start_frame=start_frame,
        end_frame=end_frame,
        existing_png_count=len(existing),
        existing_highest_frame=existing[-1] if existing else None,
    )
