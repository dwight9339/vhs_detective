"""Video-focused detection helpers."""
from __future__ import annotations

from typing import List, Sequence

from ..models.anomaly import Region
from ..models.core import FrameStats
from . import _span


def detect_video_dark_regions(
    frames: Sequence[FrameStats],
    *,
    yavg_threshold: float = 6.0,
    min_duration: float = 0.25,
) -> List[Region]:
    """Detect spans where the average luma drops very low."""

    if not frames:
        return []
    frame_step = _span.estimate_frame_step(frames, fallback=1 / 30.0)
    return _span.detect_span_regions(
        frames=frames,
        metric='YAVG',
        predicate=lambda value: value <= yavg_threshold,
        min_duration=min_duration,
        source='video',
        kind='video.dark_luma',
        frame_step=frame_step,
        score_fn=lambda v: max(0.0, yavg_threshold - v),
        extreme_selector=_span.min_by_value,
    )
