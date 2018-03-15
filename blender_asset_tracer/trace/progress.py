"""Callback class definition for BAT Tracer progress reporting.

Mostly used to forward events to pack.progress.Callback.
"""
import pathlib


class Callback:
    """BAT Tracer progress reporting."""

    def trace_blendfile(self, filename: pathlib.Path) -> None:
        """Called for every blendfile opened when tracing dependencies."""
