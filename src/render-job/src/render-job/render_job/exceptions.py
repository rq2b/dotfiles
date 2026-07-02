"""Custom exceptions for render-job."""

from __future__ import annotations


class RenderJobError(Exception):
    """Base class for user-facing render-job failures."""


class RenderJobConfigurationError(RenderJobError):
    """Raised when configuration or external tools are invalid."""


class RenderJobLayoutError(RenderJobError):
    """Raised when the job directory layout is incomplete or invalid."""
