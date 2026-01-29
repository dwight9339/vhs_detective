"""Audio-focused detection helpers."""
from __future__ import annotations

from typing import List, Sequence

from ..models.anomaly import Region
from ..models.core import FrameStats
from . import _span


def detect_audio_silence_regions(
    frames: Sequence[FrameStats],
    *,
    rms_threshold: float = -50.0,
    min_duration: float = 1.0,
) -> List[Region]:
    """Detect spans where overall RMS level stays very low."""

    if not frames:
        return []
    frame_step = _span.estimate_frame_step(frames, fallback=1.0)
    return _span.detect_span_regions(
        frames=frames,
        metric='RMS_level',
        value_getter=lambda frame: frame.kv.get('RMS_level'),
        predicate=lambda value: value <= rms_threshold,
        min_duration=min_duration,
        source='audio',
        kind='audio.low_rms',
        frame_step=frame_step,
        score_fn=lambda v: max(0.0, rms_threshold - v),
        extreme_selector=_span.min_by_value,
    )
