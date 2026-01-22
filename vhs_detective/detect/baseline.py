"""Baseline heuristics for video/audio derived metrics."""
from __future__ import annotations

from dataclasses import dataclass
from statistics import median
from typing import Callable, Iterable, List, Sequence, Tuple

from ..models.anomaly import Evidence, Region
from ..models.core import FrameStats


def detect_video_dark_regions(
    frames: Sequence[FrameStats],
    *,
    yavg_threshold: float = 6.0,
    min_duration: float = 0.25,
) -> List[Region]:
    """Detect spans where the average luma drops very low."""

    if not frames:
        return []
    frame_step = _estimate_frame_step(frames, fallback=1 / 30.0)
    return _detect_span_regions(
        frames=frames,
        metric='YAVG',
        predicate=lambda value: value <= yavg_threshold,
        min_duration=min_duration,
        source='video',
        kind='video.dark_luma',
        frame_step=frame_step,
        score_fn=lambda v: max(0.0, yavg_threshold - v),
        extreme_selector=_min_by_value,
    )


def detect_audio_silence_regions(
    frames: Sequence[FrameStats],
    *,
    rms_threshold: float = -50.0,
    min_duration: float = 1.0,
) -> List[Region]:
    """Detect spans where overall RMS level stays very low."""

    if not frames:
        return []
    frame_step = _estimate_frame_step(frames, fallback=1.0)
    return _detect_span_regions(
        frames=frames,
        metric='RMS_level',
        predicate=lambda value: value <= rms_threshold,
        min_duration=min_duration,
        source='audio',
        kind='audio.low_rms',
        frame_step=frame_step,
        score_fn=lambda v: max(0.0, rms_threshold - v),
        extreme_selector=_min_by_value,
    )


def _detect_span_regions(
    *,
    frames: Sequence[FrameStats],
    metric: str,
    predicate: Callable[[float], bool],
    min_duration: float,
    source: str,
    kind: str,
    frame_step: float,
    score_fn: Callable[[float], float],
    extreme_selector: Callable[[Sequence[Tuple[FrameStats, float]]], Tuple[FrameStats, float]],
) -> List[Region]:
    regions: List[Region] = []
    for span in _iter_metric_spans(frames, metric=metric, predicate=predicate):
        start_time = span[0][0].pts_time
        end_time = span[-1][0].pts_time + frame_step
        if end_time <= start_time:
            end_time = start_time + frame_step
        if (end_time - start_time) < min_duration:
            continue
        pivot_frame, pivot_value = extreme_selector(span)
        evidence = [
            Evidence(
                source=source,
                metric=metric,
                value=pivot_value,
                pts_time=pivot_frame.pts_time,
            )
        ]
        regions.append(
            Region(
                kind=kind,
                start_time=start_time,
                end_time=end_time,
                score=score_fn(pivot_value),
                evidence=evidence,
            )
        )
    return regions


def _iter_metric_spans(
    frames: Sequence[FrameStats],
    *,
    metric: str,
    predicate: Callable[[float], bool],
) -> Iterable[List[Tuple[FrameStats, float]]]:
    current: List[Tuple[FrameStats, float]] = []
    for frame in frames:
        value = frame.kv.get(metric)
        if value is None or not predicate(value):
            if current:
                yield current
                current = []
            continue
        current.append((frame, value))
    if current:
        yield current


def _estimate_frame_step(frames: Sequence[FrameStats], *, fallback: float) -> float:
    if len(frames) < 2:
        return fallback
    deltas = [
        max(0.0, frames[i + 1].pts_time - frames[i].pts_time)
        for i in range(len(frames) - 1)
    ]
    filtered = [delta for delta in deltas if delta > 0]
    if not filtered:
        return fallback
    return median(filtered)


def _min_by_value(span: Sequence[Tuple[FrameStats, float]]) -> Tuple[FrameStats, float]:
    return min(span, key=lambda item: item[1])
