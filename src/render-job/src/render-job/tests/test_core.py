
from __future__ import annotations

import tempfile
from pathlib import Path
from types import SimpleNamespace
import unittest

from render_job.cli import CliOptions, build_output_file, resolve_frames
from render_job.job import build_job_paths, ensure_job_layout
from render_job.tmux import LaunchScriptContext, write_launch_script


class ResolveFramesTests(unittest.TestCase):
    def test_resolve_frames_repairs_missing_frame_before_user_override(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            job_paths = build_job_paths(root, "demo")
            ensure_job_layout(job_paths)

            for frame in (0, 1, 3):
                (job_paths.png_dir / f"{frame:04d}.png").write_text("x", encoding="utf-8")

            scene_info = SimpleNamespace(frame_start=0, frame_end=10)
            options = CliOptions(
                job_name="demo",
                start_frame=4,
                end_frame=10,
                skip_encoding=False,
            )

            start_frame, end_frame = resolve_frames(job_paths, scene_info, options)

            self.assertEqual(start_frame, 2)
            self.assertEqual(end_frame, 10)

    def test_build_output_file_uses_encode_start_and_end(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            job_paths = build_job_paths(root, "demo")
            ensure_job_layout(job_paths)

            output = build_output_file(job_paths, 0, 10)
            self.assertEqual(output.name, "0000-0010.mp4")


class TmuxScriptTests(unittest.TestCase):
    def test_write_launch_script_uses_render_and_encode_ranges_separately(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            script_path = root / "render.sh"
            context = LaunchScriptContext(
                log_file=root / "render.log",
                blend_file=root / "scene.blend",
                png_dir=root / "png",
                blender_executable="/usr/bin/blender",
                ffmpeg_executable="/usr/bin/ffmpeg",
                start_frame=2,
                end_frame=10,
                fps=60.0,
                skip_encoding=False,
                output_file=root / "0000-0010.mp4",
                encode_start_frame=0,
                job_name="demo",
            )

            context.png_dir.mkdir(parents=True, exist_ok=True)
            write_launch_script(script_path, context)

            script = script_path.read_text(encoding="utf-8")
            self.assertIn("-s 2", script)
            self.assertIn("-e 10", script)
            self.assertIn("-start_number 0", script)
            self.assertIn("0000-0010.mp4", script)


if __name__ == "__main__":
    unittest.main()
