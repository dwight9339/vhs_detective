"""Tests for CTL detection heuristics."""
from __future__ import annotations

from typing import List

import pytest

from vhs_detective.detect import ctl
from vhs_detective.models.core import CTLPulse


def _pulse(time: float, idx: int) -> CTLPulse:
    return CTLPulse(t=time, dt=0.02, idx=idx)


def _times(*values: float) -> List[CTLPulse]:
    return [_pulse(time, idx=i) for i, time in enumerate(values)]


def test_detect_ctl_outliers_flags_long_gap() -> None:
    step = 1 / 30.0
    pulses = _times(
        0.0,
        step,
        step * 2,
        step * 3 + 0.12,  # intentional dropout
        step * 4 + 0.12,
    )

    regions = ctl.detect_ctl_outliers(pulses, gap_ratio=1.4, min_gap_duration=0.05)

    assert any(region.kind == 'ctl.gap' for region in regions)
    gap = next(region for region in regions if region.kind == 'ctl.gap')
    assert gap.start_time == pytest.approx(pulses[2].start_time)
    assert gap.end_time == pytest.approx(pulses[3].start_time)
    assert gap.score > 0


def test_detect_ctl_outliers_flags_short_interval() -> None:
    step = 1 / 30.0
    pulses = _times(
        0.0,
        step,
        step * 2,
        step * 2 + 0.01,  # double pulse
        step * 3 + 0.01,
    )

    regions = ctl.detect_ctl_outliers(pulses, short_ratio=0.5)

    assert any(region.kind == 'ctl.short_interval' for region in regions)
    short = next(region for region in regions if region.kind == 'ctl.short_interval')
    assert short.score > 0


def test_detect_ctl_outliers_groups_jitter_run() -> None:
    step = 1 / 30.0
    pulses = _times(
        0.0,
        step,
        step * 2,
        step * 3,
        step * 4 + 0.004,
        step * 5 + 0.008,
        step * 6 + 0.012,
        step * 7 + 0.016,
        step * 8 + 0.05,
    )

    regions = ctl.detect_ctl_outliers(pulses, jitter_threshold=0.002, min_jitter_intervals=3)

    assert any(region.kind == 'ctl.jitter_run' for region in regions)
    jitter = next(region for region in regions if region.kind == 'ctl.jitter_run')
    assert jitter.end_time > jitter.start_time
    assert jitter.score > 0


def test_detect_ctl_outliers_flags_trailing_gap() -> None:
    step = 1 / 30.0
    pulses = _times(0.0, step, step * 2, step * 3)

    regions = ctl.detect_ctl_outliers(
        pulses,
        timeline_start=0.0,
        timeline_end=step * 3 + 2.0,
        lead_tail_gap_threshold=0.5,
    )

    kinds = {region.kind for region in regions}
    assert 'ctl.gap.trailing' in kinds


def test_detect_ctl_outliers_detects_mode_shift() -> None:
    base = 1 / 30.0
    pulses = [0.0]
    t = 0.0
    for _ in range(120):
        t += base
        pulses.append(t)
    for _ in range(90):
        t += base * 3.0
        pulses.append(t)
    for _ in range(60):
        t += base
        pulses.append(t)

    ctl_pulses = _times(*pulses)

    regions = ctl.detect_ctl_outliers(ctl_pulses, mode_window=30, min_mode_duration=1.0)

    assert any(region.kind == 'ctl.mode_shift.slow' for region in regions)
