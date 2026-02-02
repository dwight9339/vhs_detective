"""CTL-focused detection helpers."""
from __future__ import annotations

from statistics import median
from typing import Deque, List, Sequence, Tuple

from ..models.anomaly import Evidence, Region
from ..models.core import CTLPulse


def detect_ctl_outliers(
    pulses: Sequence[CTLPulse],
    *,
    gap_ratio: float = 1.5,
    min_gap_duration: float = 0.25,
    short_ratio: float = 0.65,
    jitter_threshold: float = 0.0015,
    min_jitter_intervals: int = 3,
    timeline_start: float | None = None,
    timeline_end: float | None = None,
    lead_tail_gap_threshold: float = 0.75,
    mode_window: int = 90,
    mode_ratio_slow: float = 1.65,
    mode_ratio_fast: float = 0.75,
    mode_hysteresis: float = 0.15,
    min_mode_duration: float = 2.5,
) -> List[Region]:
    """Detect CTL timing anomalies (gaps, early pulses, jittery runs, mode shifts)."""

    if len(pulses) < 2:
        return _edge_gap_regions(pulses, timeline_start, timeline_end, lead_tail_gap_threshold)

    intervals: List[Tuple[float, CTLPulse, CTLPulse]] = []
    for prev, cur in zip(pulses, pulses[1:]):
        delta = cur.start_time - prev.start_time
        intervals.append((delta, prev, cur))

    positive = [delta for delta, _, _ in intervals if delta > 0]
    baseline = median(positive) if positive else (intervals[0][0] or 1 / 30.0)
    regions: List[Region] = []

    regions.extend(_edge_gap_regions(pulses, timeline_start, timeline_end, lead_tail_gap_threshold))

    jitter_state = _JitterState(min_jitter_intervals=min_jitter_intervals)

    gap_run = _GapRun(min_duration=min_gap_duration)

    mode_state = _ModeShiftState(
        mode_window=mode_window,
        ratio_slow=mode_ratio_slow,
        ratio_fast=mode_ratio_fast,
        hysteresis=mode_hysteresis,
        min_duration=min_mode_duration,
    )

    for delta, prev, cur in intervals:
        deviation = abs(delta - baseline)
        evidence = [
            Evidence(
                source='ctl',
                metric='interval',
                value=delta,
                pts_time=cur.start_time,
            ),
            Evidence(
                source='ctl',
                metric='expected_interval',
                value=baseline,
                pts_time=prev.start_time,
            ),
        ]
        ratio = (delta / baseline) if baseline > 0 else 1.0
        mode_region = mode_state.observe(ratio=ratio, start=prev.start_time, end=cur.start_time, evidence=evidence)
        if mode_region:
            regions.append(mode_region)

        if (baseline > 0 and delta >= baseline * gap_ratio) or delta >= min_gap_duration:
            regions.extend(gap_run.add(prev.start_time, cur.start_time, delta - baseline, evidence))
            jitter_state.flush(regions)
            continue
        else:
            regions.extend(gap_run.flush())

        if baseline > 0 and delta <= baseline * short_ratio:
            regions.append(
                Region(
                    kind='ctl.short_interval',
                    start_time=prev.start_time,
                    end_time=cur.start_time,
                    score=baseline - delta,
                    evidence=evidence,
                )
            )
            jitter_state.flush(regions)
            continue

        if deviation >= jitter_threshold:
            jitter_state.extend(prev.start_time, cur.start_time, deviation, evidence)
        else:
            jitter_state.flush(regions)

    regions.extend(gap_run.flush())
    jitter_state.flush(regions)
    tail_region = mode_state.finish(final_time=pulses[-1].start_time)
    if tail_region:
        regions.append(tail_region)
    return regions


def _edge_gap_regions(
    pulses: Sequence[CTLPulse],
    timeline_start: float | None,
    timeline_end: float | None,
    threshold: float,
) -> List[Region]:
    regions: List[Region] = []
    if not pulses:
        return regions
    if timeline_start is not None:
        lead_gap = pulses[0].start_time - timeline_start
        if lead_gap >= threshold:
            regions.append(
                Region(
                    kind='ctl.gap.leading',
                    start_time=timeline_start,
                    end_time=pulses[0].start_time,
                    score=lead_gap,
                    evidence=[],
                )
            )
    if timeline_end is not None:
        tail_gap = timeline_end - pulses[-1].start_time
        if tail_gap >= threshold:
            regions.append(
                Region(
                    kind='ctl.gap.trailing',
                    start_time=pulses[-1].start_time,
                    end_time=timeline_end,
                    score=tail_gap,
                    evidence=[],
                )
            )
    return regions


class _JitterState:
    def __init__(self, *, min_jitter_intervals: int) -> None:
        self.min_jitter_intervals = min_jitter_intervals
        self.start: float | None = None
        self.end: float | None = None
        self.evidence: List[Evidence] = []
        self.count = 0
        self.max_deviation = 0.0

    def extend(self, start: float, end: float, deviation: float, evidence: List[Evidence]) -> None:
        if self.start is None:
            self.start = start
        self.end = end
        self.evidence.extend(evidence)
        self.count += 1
        self.max_deviation = max(self.max_deviation, deviation)

    def flush(self, regions: List[Region]) -> None:
        if self.start is not None and self.end is not None and self.count >= self.min_jitter_intervals:
            regions.append(
                Region(
                    kind='ctl.jitter_run',
                    start_time=self.start,
                    end_time=self.end,
                    score=self.max_deviation,
                    evidence=list(self.evidence),
                )
            )
        self.start = None
        self.end = None
        self.evidence = []
        self.count = 0
        self.max_deviation = 0.0


class _GapRun:
    def __init__(self, *, min_duration: float) -> None:
        self.min_duration = min_duration
        self.start: float | None = None
        self.end: float | None = None
        self.score = 0.0
        self.evidence: List[Evidence] = []

    def add(self, start: float, end: float, score: float, evidence: List[Evidence]) -> List[Region]:
        if self.start is None:
            self.start = start
        self.end = end
        self.score = max(self.score, score)
        self.evidence.extend(evidence)
        return []

    def flush(self) -> List[Region]:
        if self.start is None or self.end is None:
            self._reset()
            return []
        duration = self.end - self.start
        if duration < self.min_duration:
            self._reset()
            return []
        region = Region(
            kind='ctl.gap',
            start_time=self.start,
            end_time=self.end,
            score=self.score if self.score > 0 else duration,
            evidence=list(self.evidence),
        )
        self._reset()
        return [region]

    def _reset(self) -> None:
        self.start = None
        self.end = None
        self.score = 0.0
        self.evidence = []


class _ModeShiftState:
    def __init__(
        self,
        *,
        mode_window: int,
        ratio_slow: float,
        ratio_fast: float,
        hysteresis: float,
        min_duration: float,
    ) -> None:
        from collections import deque

        self.window: Deque[float] = deque(maxlen=max(5, mode_window))
        self.ratio_slow = ratio_slow
        self.ratio_fast = ratio_fast
        self.hysteresis = hysteresis
        self.min_duration = min_duration
        self.active_kind: str | None = None
        self.active_start: float | None = None
        self.last_avg: float | None = None

    def observe(
        self,
        *,
        ratio: float,
        start: float,
        end: float,
        evidence: List[Evidence],
    ) -> Region | None:
        self.window.append(ratio)
        avg_ratio = sum(self.window) / len(self.window)
        self.last_avg = avg_ratio

        if self.active_kind is None:
            if avg_ratio >= self.ratio_slow:
                self.active_kind = 'ctl.mode_shift.slow'
                self.active_start = start
            elif avg_ratio <= self.ratio_fast:
                self.active_kind = 'ctl.mode_shift.fast'
                self.active_start = start
            return None

        if self.active_kind == 'ctl.mode_shift.slow':
            if avg_ratio <= self.ratio_slow - self.hysteresis:
                return self._finish(end_time=end, avg=avg_ratio)
        elif self.active_kind == 'ctl.mode_shift.fast':
            if avg_ratio >= self.ratio_fast + self.hysteresis:
                return self._finish(end_time=end, avg=avg_ratio)
        return None

    def finish(self, *, final_time: float) -> Region | None:
        if self.active_kind and self.active_start is not None:
            return self._finish(end_time=final_time, avg=self.last_avg or 0.0)
        return None

    def _finish(self, *, end_time: float, avg: float) -> Region | None:
        if self.active_start is None:
            self.active_kind = None
            return None
        duration = end_time - self.active_start
        if duration < self.min_duration:
            self.active_kind = None
            self.active_start = None
            return None
        region = Region(
            kind=self.active_kind or 'ctl.mode_shift',
            start_time=self.active_start,
            end_time=end_time,
            score=avg,
            evidence=[],
        )
        self.active_kind = None
        self.active_start = None
        return region
