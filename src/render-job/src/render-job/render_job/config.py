"""Runtime configuration handling."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import shutil

from .exceptions import RenderJobConfigurationError


DEFAULT_BLENDER_ROOT = Path("/home/staging/blender")


@dataclass(frozen=True, slots=True)
class ToolPaths:
    """Resolved external tool paths."""

    blender: str
    tmux: str


@dataclass(frozen=True, slots=True)
class AppConfig:
    """Resolved runtime configuration."""

    root_dir: Path
    tools: ToolPaths


def resolve_tool(name: str, env_var: str) -> str:
    """Resolve a tool path from an environment variable or PATH."""

    value = os.environ.get(env_var)
    if value:
        return value
    resolved = shutil.which(name)
    if not resolved:
        raise RenderJobConfigurationError(
            f"Required tool '{name}' was not found on PATH. "
            f"Set {env_var} or install {name}."
        )
    return resolved


def resolve_ffmpeg() -> str:
    """Resolve ffmpeg when encoding is enabled."""

    return resolve_tool("ffmpeg", "FFMPEG_EXECUTABLE")


def load_config() -> AppConfig:
    """Load configuration from environment and system PATH."""

    root_dir = Path(os.environ.get("BLENDER_ROOT", str(DEFAULT_BLENDER_ROOT))).expanduser()
    tools = ToolPaths(
        blender=resolve_tool("blender", "BLENDER_EXECUTABLE"),
        tmux=resolve_tool("tmux", "TMUX_EXECUTABLE"),
    )
    return AppConfig(root_dir=root_dir, tools=tools)
