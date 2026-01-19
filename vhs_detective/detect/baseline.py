"""Placeholder baseline detection heuristics."""
from __future__ import annotations

from typing import List

from ..models.core import FrameStats


def detect_from_video(frames: List[FrameStats]) -> List[dict]:
    """Return empty detections for now to keep the pipeline pluggable."""

    return []
