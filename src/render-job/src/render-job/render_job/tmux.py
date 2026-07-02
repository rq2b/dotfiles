"""Tmux integration and launch script generation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shlex
import subprocess
from textwrap import dedent

from .blender import build_blender_command
from .encoding import EncodePlan, build_ffmpeg_command
from .job import scan_existing_frames


@dataclass(frozen=True, slots=True)
class LaunchScriptContext:
    """Data needed to write the tmux launch script."""

    log_file: Path
    blend_file: Path
    png_dir: Path
    blender_executable: str
    ffmpeg_executable: str | None
    start_frame: int
    end_frame: int
    fps: float
    skip_encoding: bool
    output_file: Path
    job_name: str


def session_exists(tmux_executable: str, session_name: str) -> bool:
    result = subprocess.run(
        [tmux_executable, "has-session", "-t", session_name],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def _shell_array(values: list[str]) -> str:
    return "(" + " ".join(shlex.quote(value) for value in values) + ")"


def write_launch_script(script_path: Path, context: LaunchScriptContext) -> None:
    blender_cmd = build_blender_command(
        context.blender_executable,
        context.blend_file,
        context.png_dir,
        context.start_frame,
        context.end_frame,
    )

    ffmpeg_cmd: list[str] | None = None
    encode_output = context.output_file

    if not context.skip_encoding:
        if context.ffmpeg_executable is None:
            raise ValueError("ffmpeg executable is required when encoding is enabled")

        frames = scan_existing_frames(context.png_dir)

        if not frames:
            raise ValueError(f"No PNG frames found in {context.png_dir}.")

        encode_start = frames[0]
        encode_end = frames[-1]

        encode_output = (
            context.output_file.parent / f"{encode_start:04d}-{encode_end:04d}.mp4"
        )

        encode_plan = EncodePlan(
            png_dir=context.png_dir,
            output_file=encode_output,
            start_frame=encode_start,
            end_frame=encode_end,
            fps=context.fps,
        )

        ffmpeg_cmd = build_ffmpeg_command(
            context.ffmpeg_executable,
            encode_plan,
        )

    template = dedent("""\
        #!/usr/bin/env bash
        set -euo pipefail

        LOG_FILE=__LOG_FILE__
        JOB_NAME=__JOB_NAME__
        START_FRAME=__START_FRAME__
        END_FRAME=__END_FRAME__
        SKIP_ENCODING=__SKIP_ENCODING__

        BLENDER_CMD=__BLENDER_CMD__
        __FFMPEG_CMD_LINE__

        exec > >(tee -a "$LOG_FILE") 2>&1

        echo "Started: $(date '+%Y-%m-%d %H:%M:%S')"
        echo "Job: $JOB_NAME"
        echo "Log file: $LOG_FILE"
        echo "Planned output: __PLANNED_OUTPUT__"
        echo "Frame range: $START_FRAME-$END_FRAME"
        echo "Blender command:"
        printf ' %q' "${BLENDER_CMD[@]}"
        echo

        render_started_at=$(date +%s)
        if "${BLENDER_CMD[@]}"; then
            render_status=0
        else
            render_status=$?
        fi

        if [[ "$render_status" -ne 0 ]]; then
            echo "Render failed with exit code $render_status"
            exit "$render_status"
        fi

        render_finished_at=$(date +%s)
        render_elapsed=$((render_finished_at - render_started_at))
        rendered_frames=$((END_FRAME - START_FRAME + 1))
        if [[ "$rendered_frames" -gt 0 ]]; then
            average_frame_time=$(awk -v elapsed="$render_elapsed" -v frames="$rendered_frames" 'BEGIN { printf "%.2f", elapsed / frames }')
        else
            average_frame_time="0.00"
        fi

        echo "Render attempt complete"
        echo "Frames rendered: $rendered_frames"
        echo "Elapsed time: ${render_elapsed}s"
        echo "Average frame time: ${average_frame_time}s"

        __POST_RENDER_BLOCK__
        """)

    if ffmpeg_cmd is None:
        post_render_block = "\n".join(
            [
                'echo "Encoding skipped by request."',
                "exit 0",
            ]
        )
        ffmpeg_cmd_line = ""
    else:
        post_render_block = "\n".join(
            [
                'echo "Encoding command:"',
                "printf ' %q' \"${FFMPEG_CMD[@]}\"",
                "echo",
                "",
                'if "${FFMPEG_CMD[@]}"; then',
                "    encode_status=0",
                "else",
                "    encode_status=$?",
                "fi",
                "",
                'if [[ "$encode_status" -ne 0 ]]; then',
                '    echo "Encoding failed with exit code $encode_status"',
                '    exit "$encode_status"',
                "fi",
                "",
                f'echo "Encoding complete: {encode_output}"',
            ]
        )
        ffmpeg_cmd_line = f"FFMPEG_CMD={_shell_array(ffmpeg_cmd)}"

    script = (
        template.replace("__LOG_FILE__", shlex.quote(str(context.log_file)))
        .replace("__JOB_NAME__", shlex.quote(context.job_name))
        .replace("__START_FRAME__", str(context.start_frame))
        .replace("__END_FRAME__", str(context.end_frame))
        .replace("__SKIP_ENCODING__", "1" if context.skip_encoding else "0")
        .replace("__BLENDER_CMD__", _shell_array(blender_cmd))
        .replace("__FFMPEG_CMD_LINE__", ffmpeg_cmd_line)
        .replace("__PLANNED_OUTPUT__", str(encode_output))
        .replace("__POST_RENDER_BLOCK__", post_render_block)
    )

    script_path.write_text(script, encoding="utf-8")
    script_path.chmod(0o755)


def launch_tmux_session(
    tmux_executable: str, session_name: str, script_path: Path
) -> None:
    subprocess.run(
        [
            tmux_executable,
            "new-session",
            "-d",
            "-s",
            session_name,
            "--",
            "bash",
            str(script_path),
        ],
        check=True,
    )
