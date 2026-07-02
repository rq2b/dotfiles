"""Command-line entry point for render-job."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import argparse
import subprocess
import sys

from .blender import query_scene_info
from .config import load_config, resolve_ffmpeg
from .exceptions import RenderJobError, RenderJobLayoutError
from .job import (
    JobPaths,
    build_job_paths,
    discover_blend_file,
    ensure_job_layout,
    normalize_job_name,
    scan_existing_frames,
)
from .progress import build_preflight_summary
from .tmux import (
    LaunchScriptContext,
    launch_tmux_session,
    session_exists,
    write_launch_script,
)


@dataclass(frozen=True, slots=True)
class CliOptions:
    job_name: str
    start_frame: int | None
    end_frame: int | None
    skip_encoding: bool


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="render-job",
        description="Launch, resume, and encode Blender render jobs.",
    )
    parser.add_argument("job_name", help="Job directory name under BLENDER_ROOT")
    parser.add_argument(
        "--start-frame",
        type=int,
        default=None,
        help="Override the computed start frame.",
    )
    parser.add_argument(
        "--end-frame",
        type=int,
        default=None,
        help="Override the computed end frame.",
    )
    parser.add_argument(
        "--skip-encoding",
        action="store_true",
        help="Render PNG frames but skip the MP4 encoding step.",
    )
    return parser


def parse_args(argv: list[str] | None = None) -> CliOptions:
    namespace = build_parser().parse_args(argv)
    return CliOptions(
        job_name=namespace.job_name,
        start_frame=namespace.start_frame,
        end_frame=namespace.end_frame,
        skip_encoding=namespace.skip_encoding,
    )


def prompt_create_job(job_dir: Path) -> bool:
    response = input(
        f"Job directory {job_dir} does not exist. Create it? [y/N] "
    ).strip().lower()
    return response in {"y", "yes"}


def current_timestamp() -> str:
    return datetime.now().astimezone().strftime("%Y-%m-%d_%H-%M-%S")


def resolve_frames(
    job_paths: JobPaths,
    scene_info,
    options: CliOptions,
) -> tuple[int, int]:
    existing_frames = scan_existing_frames(job_paths.png_dir)
    existing_set = set(existing_frames)

    resume_floor = scene_info.frame_start
    while resume_floor in existing_set:
        resume_floor += 1

    if options.start_frame is not None:
        requested_start = options.start_frame
    else:
        requested_start = scene_info.frame_start

    start_frame = min(requested_start, resume_floor)
    while start_frame in existing_set:
        start_frame += 1

    if options.end_frame is not None:
        end_frame = options.end_frame
    else:
        end_frame = scene_info.frame_end

    if start_frame > end_frame:
        raise RenderJobLayoutError(
            f"Invalid frame range: start frame {start_frame} is after end frame {end_frame}."
        )

    return start_frame, end_frame


def build_output_file(job_paths: JobPaths, encode_start_frame: int, encode_end_frame: int) -> Path:
    width = max(4, len(str(encode_start_frame)), len(str(encode_end_frame)))
    return (
        job_paths.render_dir
        / f"{encode_start_frame:0{width}d}-{encode_end_frame:0{width}d}.mp4"
    )


def main(argv: list[str] | None = None) -> int:
    try:
        options = parse_args(argv)
        config = load_config()
        job_name = normalize_job_name(options.job_name)
        job_paths = build_job_paths(config.root_dir, job_name)
        config.root_dir.mkdir(parents=True, exist_ok=True)

        if not job_paths.job_dir.exists():
            if prompt_create_job(job_paths.job_dir):
                ensure_job_layout(job_paths)
                print(f"Created job layout at {job_paths.job_dir}")
                return 0
            print("Job creation declined.")
            return 1

        ensure_job_layout(job_paths)
        blend_file = discover_blend_file(job_paths)
        scene_info = query_scene_info(config.tools.blender, blend_file)
        start_frame, end_frame = resolve_frames(job_paths, scene_info, options)
        existing_frames = scan_existing_frames(job_paths.png_dir)
        encode_start_frame = min(existing_frames[0], start_frame) if existing_frames else start_frame
        output_file = build_output_file(job_paths, encode_start_frame, end_frame)

        ffmpeg_executable = None if options.skip_encoding else resolve_ffmpeg()

        timestamp = current_timestamp()
        log_file = job_paths.logs_dir / f"render_{timestamp}.log"
        script_file = job_paths.logs_dir / f"render_{timestamp}.sh"
        session_name = job_paths.session_name

        if session_exists(config.tools.tmux, session_name):
            raise RenderJobLayoutError(
                f"tmux session {session_name!r} already exists. "
                f"Attach with: tmux attach -t {session_name}"
            )

        summary = build_preflight_summary(job_name, job_paths.png_dir, start_frame, end_frame)
        print(summary.format())
        print(f"Blend file: {blend_file}")
        print(f"Session name: {session_name}")
        print(f"Log file: {log_file}")
        print(f"Output file: {output_file}")

        script_context = LaunchScriptContext(
            log_file=log_file,
            blend_file=blend_file,
            png_dir=job_paths.png_dir,
            blender_executable=config.tools.blender,
            ffmpeg_executable=ffmpeg_executable,
            start_frame=start_frame,
            end_frame=end_frame,
            fps=scene_info.fps_effective,
            skip_encoding=options.skip_encoding,
            output_file=output_file,
            encode_start_frame=encode_start_frame,
            job_name=job_name,
        )
        write_launch_script(script_file, script_context)
        launch_tmux_session(config.tools.tmux, session_name, script_file)

        print(f"Render launched in tmux session: {session_name}")
        print(f"Attach with: tmux attach -t {session_name}")
        return 0
    except RenderJobError as exc:
        print(f"render-job: {exc}", file=sys.stderr)
        return 1
    except subprocess.CalledProcessError as exc:
        print(
            f"render-job: external command failed with exit code {exc.returncode}",
            file=sys.stderr,
        )
        return 1
    except FileNotFoundError as exc:
        print(f"render-job: missing executable or file: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
