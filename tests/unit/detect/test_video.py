"""Tests for video detection heuristics."""
from __future__ import annotations

from vhs_detective.detect import video
from vhs_detective.models.core import FrameStats


def _frame(time: float, **metrics: float) -> FrameStats:
    return FrameStats(pts_time=time, kv=metrics)


def test_detect_video_dark_regions_finds_low_luma_span() -> None:
    frames = [
        _frame(0.0, YAVG=20.0),
        _frame(0.1, YAVG=5.0),
        _frame(0.2, YAVG=4.0),
        _frame(0.3, YAVG=4.5),
        _frame(0.4, YAVG=9.0),
    ]

    regions = video.detect_video_dark_regions(frames, yavg_threshold=6.0, min_duration=0.25)

    assert len(regions) == 1
    region = regions[0]
    assert region.kind == 'video.dark_luma'
    assert region.start_time == 0.1
    assert region.end_time == 0.4
    assert region.score > 0
    assert region.evidence[0].metric == 'YAVG'
