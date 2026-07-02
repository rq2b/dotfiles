from pathlib import Path
import tempfile

from render_job.job import normalize_job_name, build_job_paths, scan_existing_frames
from render_job.blender import frame_number_width
from render_job.encoding import EncodePlan, build_ffmpeg_command
from render_job.progress import build_preflight_summary


def test_normalize_job_name_strips_trailing_slash():
    assert normalize_job_name("01-right-to-left/") == "01-right-to-left"


def test_scan_existing_frames():
    with tempfile.TemporaryDirectory() as d:
        p = Path(d)
        (p / "0001.png").write_text("x")
        (p / "0010.png").write_text("x")
        (p / "ignore.txt").write_text("x")
        assert scan_existing_frames(p) == [1, 10]


def test_frame_number_width():
    assert frame_number_width(0, 9) == 4
    assert frame_number_width(350, 1000) == 4
    assert frame_number_width(12345, 2) == 5


def test_build_ffmpeg_command():
    plan = EncodePlan(
        png_dir=Path("/job/render/png"),
        output_file=Path("/job/render/0001-0009.mp4"),
        start_frame=1,
        end_frame=9,
        fps=24,
    )
    cmd = build_ffmpeg_command("ffmpeg", plan)
    assert cmd[0] == "ffmpeg"
    assert cmd[cmd.index("-c:v") + 1] == "h264_nvenc"
    assert cmd[-1].endswith("0001-0009.mp4")


def test_preflight_summary():
    with tempfile.TemporaryDirectory() as d:
        p = Path(d)
        (p / "0000.png").write_text("x")
        (p / "0001.png").write_text("x")
        summary = build_preflight_summary("job", p, 2, 10)
        assert summary.existing_png_count == 2
        assert summary.frames_to_render == 9
