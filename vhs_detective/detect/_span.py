"""Shared helpers for span-based detectors."""
from __future__ import annotations

from statistics import median
from typing import Callable, Iterable, List, Sequence, Tuple

from ..models.anomaly import Evidence, Region
from ..models.core import FrameStats

MetricSpan = List[Tuple[FrameStats, float]]


def detect_span_regions(
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
    """Convert qualifying metric spans into anomaly regions."""

    regions: List[Region] = []
    for span in iter_metric_spans(frames, metric=metric, predicate=predicate):
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


def iter_metric_spans(
    frames: Sequence[FrameStats],
    *,
    metric: str,
    predicate: Callable[[float], bool],
) -> Iterable[MetricSpan]:
    """Yield contiguous spans where `predicate(frame[metric])` holds true."""

    current: MetricSpan = []
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


def estimate_frame_step(frames: Sequence[FrameStats], *, fallback: float) -> float:
    """Estimate the frame/window spacing from pts deltas."""

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


def min_by_value(span: Sequence[Tuple[FrameStats, float]]) -> Tuple[FrameStats, float]:
    """Return the (frame, value) tuple with the lowest metric value."""

    return min(span, key=lambda item: item[1])
