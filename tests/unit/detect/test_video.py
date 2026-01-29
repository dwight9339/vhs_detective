"""Tests for video detection heuristics."""
from __future__ import annotations

import pytest

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


def test_detect_video_bright_regions_flags_whiteout() -> None:
    frames = [
        _frame(0.0, YAVG=150.0),
        _frame(0.1, YAVG=245.0),
        _frame(0.2, YAVG=246.0),
        _frame(0.3, YAVG=200.0),
    ]

    regions = video.detect_video_bright_regions(frames, yavg_threshold=240.0, min_duration=0.15)

    assert len(regions) == 1
    assert regions[0].kind == 'video.bright_luma'


def test_detect_video_freeze_regions_uses_low_diff() -> None:
    frames = [
        _frame(0.0, YDIFF=0.5),
        _frame(0.1, YDIFF=0.01),
        _frame(0.2, YDIFF=0.02),
        _frame(0.3, YDIFF=0.03),
        _frame(0.4, YDIFF=0.6),
    ]

    regions = video.detect_video_freeze_regions(frames, diff_threshold=0.05, min_duration=0.2)

    assert len(regions) == 1
    assert regions[0].kind == 'video.freeze_frame'


def test_detect_video_dropframe_gaps_spots_large_pts_jump() -> None:
    frames = [
        _frame(0.0, YAVG=10.0),
        _frame(0.04, YAVG=9.0),
        _frame(1.0, YAVG=8.0),
        _frame(1.04, YAVG=9.0),
    ]

    regions = video.detect_video_dropframe_gaps(frames, gap_threshold=0.5)
    assert len(regions) == 1
    assert regions[0].kind == 'video.dropframe_gap'
    assert regions[0].score == 0.96


def test_detect_video_chroma_dropouts_when_u_v_flatline() -> None:
    frames = [
        _frame(0.0, UAVG=140.0, VAVG=120.0),
        _frame(0.1, UAVG=129.0, VAVG=130.0),
        _frame(0.2, UAVG=127.5, VAVG=128.5),
        _frame(0.3, UAVG=140.0, VAVG=125.0),
    ]

    regions = video.detect_video_chroma_dropouts(frames, deviation_threshold=3.0, min_duration=0.15)
    assert len(regions) == 1
    assert regions[0].kind == 'video.chroma_dropout'


def test_detect_video_noise_spikes_when_ydrange_surges() -> None:
    frames = [
        _frame(0.0, YDRANGE=10.0),
        _frame(0.1, YDRANGE=60.0),
        _frame(0.2, YDRANGE=65.0),
        _frame(0.3, YDRANGE=20.0),
    ]

    regions = video.detect_video_noise_spikes(frames, ydrange_threshold=50.0, min_duration=0.15)
    assert len(regions) == 1
    assert regions[0].kind == 'video.noise_spike'


def _lavfi_frame(time: float, **metrics: float) -> FrameStats:
    prefixed = {f'lavfi.signalstats.{key}': value for key, value in metrics.items()}
    return FrameStats(pts_time=time, kv=prefixed)


def test_estimate_video_lock_time_returns_first_color_run() -> None:
    frames = []
    t = 0.0
    step = 1 / 30.0
    for _ in range(10):
        frames.append(
            _lavfi_frame(
                t,
                SATAVG=0.0,
                YLOW=16.0,
                YHIGH=16.0,
                YDIF=0.0,
                UAVG=128.0,
                VAVG=128.0,
            )
        )
        t += step
    for _ in range(10):
        frames.append(
            _lavfi_frame(
                t,
                SATAVG=8.0,
                YLOW=10.0,
                YHIGH=200.0,
                YDIF=25.0,
                UAVG=150.0,
                VAVG=110.0,
            )
        )
        t += step

    lock_time = video.estimate_video_lock_time(frames)

    assert lock_time is not None
    assert lock_time == pytest.approx(frames[10].pts_time)


def test_estimate_video_lock_time_detects_luma_after_blank() -> None:
    frames = []
    step = 1 / 30.0
    t = 0.0
    # 12 blank frames (~0.4s)
    for _ in range(12):
        frames.append(
            _lavfi_frame(
                t,
                SATAVG=0.0,
                YLOW=16.0,
                YHIGH=16.0,
                YDIF=0.0,
                UAVG=128.0,
                VAVG=128.0,
            )
        )
        t += step
    # Monochrome content with range + motion but zero saturation
    for _ in range(4):
        frames.append(
            _lavfi_frame(
                t,
                SATAVG=0.0,
                YLOW=20.0,
                YHIGH=70.0,
                YDIF=15.0,
            )
        )
        t += step

    lock_time = video.estimate_video_lock_time(frames)

    assert lock_time is not None
    assert lock_time == pytest.approx(frames[12].pts_time)
