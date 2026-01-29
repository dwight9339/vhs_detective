"""Video-focused detection helpers."""
from __future__ import annotations

from typing import Dict, List, Optional, Sequence

from ..models.anomaly import Evidence, Region
from ..models.core import FrameStats
from . import _span

_METRIC_ALIASES: Dict[str, str] = {
    'YDIFF': 'YDIF',
    'UDIFF': 'UDIF',
    'VDIFF': 'VDIF',
}


def _metric(frame: FrameStats, key: str) -> Optional[float]:
    """Return the requested metric, accepting either bare or lavfi-prefixed keys."""

    if key in frame.kv:
        return frame.kv[key]
    alias = _METRIC_ALIASES.get(key)
    if alias and alias in frame.kv:
        return frame.kv[alias]
    prefixed = f'lavfi.signalstats.{key}'
    if prefixed in frame.kv:
        return frame.kv[prefixed]
    if alias:
        prefixed_alias = f'lavfi.signalstats.{alias}'
        if prefixed_alias in frame.kv:
            return frame.kv[prefixed_alias]
    return None


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
        value_getter=lambda frame: _metric(frame, 'YAVG'),
        predicate=lambda value: value <= yavg_threshold,
        min_duration=min_duration,
        source='video',
        kind='video.dark_luma',
        frame_step=frame_step,
        score_fn=lambda v: max(0.0, yavg_threshold - v),
        extreme_selector=_span.min_by_value,
    )


def detect_video_bright_regions(
    frames: Sequence[FrameStats],
    *,
    yavg_threshold: float = 235.0,
    min_duration: float = 0.25,
) -> List[Region]:
    """Detect spans where luma saturates near white."""

    if not frames:
        return []
    frame_step = _span.estimate_frame_step(frames, fallback=1 / 30.0)
    return _span.detect_span_regions(
        frames=frames,
        metric='YAVG',
        value_getter=lambda frame: _metric(frame, 'YAVG'),
        predicate=lambda value: value >= yavg_threshold,
        min_duration=min_duration,
        source='video',
        kind='video.bright_luma',
        frame_step=frame_step,
        score_fn=lambda v: max(0.0, v - yavg_threshold),
        extreme_selector=_span.max_by_value,
    )


def detect_video_freeze_regions(
    frames: Sequence[FrameStats],
    *,
    diff_threshold: float = 0.15,
    min_duration: float = 0.5,
) -> List[Region]:
    """Detect spans where per-frame pixel deltas remain near zero (frozen frame)."""

    if not frames:
        return []
    frame_step = _span.estimate_frame_step(frames, fallback=1 / 30.0)
    return _span.detect_span_regions(
        frames=frames,
        metric='YDIFF',
        value_getter=lambda frame: _metric(frame, 'YDIFF'),
        predicate=lambda value: value <= diff_threshold,
        min_duration=min_duration,
        source='video',
        kind='video.freeze_frame',
        frame_step=frame_step,
        score_fn=lambda v: max(0.0, diff_threshold - v),
        extreme_selector=_span.min_by_value,
    )


def detect_video_dropframe_gaps(
    frames: Sequence[FrameStats],
    *,
    gap_threshold: float = 0.25,
) -> List[Region]:
    """Detect unusually large pts_time gaps that imply dropped frames."""

    regions: List[Region] = []
    if len(frames) < 2:
        return regions
    for prev, cur in zip(frames, frames[1:]):
        delta = cur.pts_time - prev.pts_time
        if delta < gap_threshold:
            continue
        start = prev.pts_time
        end = cur.pts_time
        evidence = [
            Evidence(
                source='video',
                metric='pts_gap',
                value=delta,
                pts_time=cur.pts_time,
            )
        ]
        regions.append(
            Region(
                kind='video.dropframe_gap',
                start_time=start,
                end_time=end,
                score=delta,
                evidence=evidence,
            )
        )
    return regions


def detect_video_chroma_dropouts(
    frames: Sequence[FrameStats],
    *,
    deviation_threshold: float = 6.0,
    min_duration: float = 0.3,
) -> List[Region]:
    """Detect spans where chroma collapses toward neutral, suggesting color loss."""

    if not frames:
        return []

    def chroma_dev(frame: FrameStats) -> Optional[float]:
        u = _metric(frame, 'UAVG')
        v = _metric(frame, 'VAVG')
        if u is None or v is None:
            return None
        return max(abs(u - 128.0), abs(v - 128.0))

    frame_step = _span.estimate_frame_step(frames, fallback=1 / 30.0)
    return _span.detect_span_regions(
        frames=frames,
        metric='chroma_dev',
        value_getter=chroma_dev,
        predicate=lambda value: value <= deviation_threshold,
        min_duration=min_duration,
        source='video',
        kind='video.chroma_dropout',
        frame_step=frame_step,
        score_fn=lambda v: max(0.0, deviation_threshold - v),
        extreme_selector=_span.min_by_value,
    )


def detect_video_noise_spikes(
    frames: Sequence[FrameStats],
    *,
    ydrange_threshold: float = 40.0,
    min_duration: float = 0.15,
) -> List[Region]:
    """Detect spans where luma noise/range jumps sharply."""

    if not frames:
        return []
    frame_step = _span.estimate_frame_step(frames, fallback=1 / 30.0)
    return _span.detect_span_regions(
        frames=frames,
        metric='YDRANGE',
        value_getter=lambda frame: _metric(frame, 'YDRANGE'),
        predicate=lambda value: value >= ydrange_threshold,
        min_duration=min_duration,
        source='video',
        kind='video.noise_spike',
        frame_step=frame_step,
        score_fn=lambda v: max(0.0, v - ydrange_threshold),
        extreme_selector=_span.max_by_value,
    )


def estimate_video_lock_time(
    frames: Sequence[FrameStats],
    *,
    min_color_duration: float = 0.25,
    min_luma_duration: float = 0.1,
    min_blank_duration: float = 0.2,
    chroma_sat_threshold: float = 5.0,
    chroma_dev_threshold: float = 4.0,
    signal_range_threshold: float = 20.0,
    blank_range_threshold: float = 2.0,
    blank_sat_threshold: float = 0.5,
    min_luma_activity: float = 5.0,
) -> Optional[float]:
    """Estimate when usable video first appears in the stats sequence.

    The heuristic looks for two cues:
      * A sustained span where chroma metrics rise above the noise floor.
      * A transition from a long flat/blank region into frames that show luma range
        and per-frame differences (covers monochrome-but-legible material).

    Returns the pts_time of the first qualifying frame or None if the input is empty.
    """

    if not frames:
        return None

    frame_step = _span.estimate_frame_step(frames, fallback=1 / 30.0)
    blank_duration = 0.0
    post_blank_active = False
    luma_candidate_start: Optional[float] = None
    luma_candidate_duration = 0.0

    color_candidate_start: Optional[float] = None
    color_candidate_duration = 0.0

    for frame in frames:
        sat = _metric(frame, 'SATAVG') or 0.0
        u = _metric(frame, 'UAVG')
        v = _metric(frame, 'VAVG')
        y_high = _metric(frame, 'YHIGH')
        y_low = _metric(frame, 'YLOW')
        ydiff = _metric(frame, 'YDIFF') or 0.0
        y_range = (y_high - y_low) if (y_high is not None and y_low is not None) else None

        is_blank = (sat <= blank_sat_threshold) and (y_range is None or y_range <= blank_range_threshold)
        if is_blank:
            blank_duration += frame_step
            post_blank_active = False
            luma_candidate_start = None
            luma_candidate_duration = 0.0
            color_candidate_start = None if sat < chroma_sat_threshold else color_candidate_start
            continue

        if blank_duration >= min_blank_duration and not post_blank_active:
            post_blank_active = True
        if not is_blank:
            blank_duration = 0.0

        if post_blank_active:
            qualifies = (
                y_range is not None
                and y_range >= signal_range_threshold
                and ydiff >= min_luma_activity
            )
            if qualifies:
                if luma_candidate_start is None:
                    luma_candidate_start = frame.pts_time
                    luma_candidate_duration = frame_step
                else:
                    luma_candidate_duration = frame.pts_time - luma_candidate_start + frame_step
                if luma_candidate_duration >= min_luma_duration:
                    return luma_candidate_start
            else:
                luma_candidate_start = None
                luma_candidate_duration = 0.0
                post_blank_active = False

        color_dev = max(abs(u - 128.0), abs(v - 128.0)) if (u is not None and v is not None) else 0.0
        has_chroma = (sat >= chroma_sat_threshold) or (color_dev >= chroma_dev_threshold)
        if has_chroma:
            if color_candidate_start is None:
                color_candidate_start = frame.pts_time
                color_candidate_duration = frame_step
            else:
                color_candidate_duration = frame.pts_time - color_candidate_start + frame_step
            if color_candidate_duration >= min_color_duration:
                return color_candidate_start
        else:
            color_candidate_start = None
            color_candidate_duration = 0.0

    return frames[0].pts_time
