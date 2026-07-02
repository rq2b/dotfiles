"""Job path handling and filesystem layout."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from .exceptions import RenderJobLayoutError


JOB_NAME_PATTERN = re.compile(r"^[^/\\\0]+$")  # noqa: W605


@dataclass(frozen=True, slots=True)
class JobPaths:
    """All paths associated with a render job."""

    root_dir: Path
    job_name: str
    job_dir: Path
    logs_dir: Path
    render_dir: Path
    png_dir: Path
    src_dir: Path

    @property
    def blend_files(self) -> list[Path]:
        return sorted(self.src_dir.glob("*.blend"))

    @property
    def session_name(self) -> str:
        return f"render_{self.job_name}"


def normalize_job_name(raw_name: str) -> str:
    """Validate and normalize a job name.

    Trailing slashes are ignored. The result must remain a single path component.
    """

    name = raw_name.strip()
    while name.endswith(("/", "\\")):
        name = name[:-1]
    if not name:
        raise RenderJobLayoutError("Job name cannot be empty.")
    if name in {".", ".."}:
        raise RenderJobLayoutError(f"Invalid job name: {raw_name!r}")
    if not JOB_NAME_PATTERN.match(name):
        raise RenderJobLayoutError(
            f"Job name must be a single path component, not a path: {raw_name!r}"
        )
    if Path(name).name != name:
        raise RenderJobLayoutError(
            f"Job name must not contain path separators or parent directories: {raw_name!r}"
        )
    return name


def build_job_paths(root_dir: Path, job_name: str) -> JobPaths:
    job_dir = root_dir / job_name
    return JobPaths(
        root_dir=root_dir,
        job_name=job_name,
        job_dir=job_dir,
        logs_dir=job_dir / "logs",
        render_dir=job_dir / "render",
        png_dir=job_dir / "render" / "png",
        src_dir=job_dir / "src",
    )


def ensure_job_layout(paths: JobPaths) -> None:
    """Create the standard directory layout if it does not already exist."""

    paths.root_dir.mkdir(parents=True, exist_ok=True)
    paths.job_dir.mkdir(parents=True, exist_ok=True)
    for directory in (paths.logs_dir, paths.render_dir, paths.png_dir, paths.src_dir):
        directory.mkdir(parents=True, exist_ok=True)


def discover_blend_file(paths: JobPaths) -> Path:
    """Find the single .blend file in the job's src directory."""

    blend_files = paths.blend_files
    if not blend_files:
        raise RenderJobLayoutError(
            f"No .blend file found in {paths.src_dir}. "
            "Place exactly one Blender source file in src/."
        )
    if len(blend_files) > 1:
        names = ", ".join(item.name for item in blend_files)
        raise RenderJobLayoutError(
            f"Multiple .blend files found in {paths.src_dir}: {names}. "
            "Keep exactly one source file in src/."
        )
    return blend_files[0]


_FRAME_RE = re.compile(r"^(?P<frame>\d+)\.png$", re.IGNORECASE)


def scan_existing_frames(png_dir: Path) -> list[int]:
    frames: list[int] = []
    if not png_dir.exists():
        return frames
    for item in png_dir.iterdir():
        if not item.is_file():
            continue
        match = _FRAME_RE.match(item.name)
        if not match:
            continue
        frames.append(int(match.group("frame")))
    return sorted(set(frames))


def highest_existing_frame(png_dir: Path) -> int | None:
    frames = scan_existing_frames(png_dir)
    return frames[-1] if frames else None
