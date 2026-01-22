"""Tests for audio detection heuristics."""
from __future__ import annotations

from vhs_detective.detect import audio
from vhs_detective.models.core import FrameStats


def _frame(time: float, **metrics: float) -> FrameStats:
    return FrameStats(pts_time=time, kv=metrics)


def test_detect_audio_silence_regions_flags_low_rms_span() -> None:
    frames = [
        _frame(0.0, RMS_level=-40.0),
        _frame(0.5, RMS_level=-55.0),
        _frame(1.0, RMS_level=-58.0),
        _frame(1.5, RMS_level=-56.0),
        _frame(2.0, RMS_level=-42.0),
    ]

    regions = audio.detect_audio_silence_regions(frames, rms_threshold=-50.0, min_duration=1.0)

    assert len(regions) == 1
    region = regions[0]
    assert region.kind == 'audio.low_rms'
    assert region.start_time == 0.5
    assert region.end_time == 2.0
    assert region.score > 0
    assert region.evidence[0].metric == 'RMS_level'
