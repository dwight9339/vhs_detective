import pytest

from vhs_detective.analyzer.pipeline import run_analysis
from vhs_detective.models.core import CTLPulse, DetectionToggles, FrameStats


def _frame(time: float, **kv: float) -> FrameStats:
    return FrameStats(pts_time=time, kv=dict(kv))


def _lavfi_frame(time: float, **metrics: float) -> FrameStats:
    prefixed = {f'lavfi.signalstats.{key}': value for key, value in metrics.items()}
    return FrameStats(pts_time=time, kv=prefixed)


def _pulse(time: float, *, dt: float = 0.02, idx: int = 0) -> CTLPulse:
    return CTLPulse(t=time, dt=dt, idx=idx)


def test_run_analysis_combines_sources() -> None:
    video = [
        _frame(0.0, YAVG=10),
        _frame(0.04, YAVG=2),
        _frame(0.08, YAVG=1),
        _frame(0.12, YAVG=1),
        _frame(0.16, YAVG=1),
        _frame(0.20, YAVG=1),
        _frame(0.24, YAVG=1),
        _frame(0.28, YAVG=1),
        _frame(0.32, YAVG=10),
    ]
    audio = [
        _frame(0.0, RMS_level=-60),
        _frame(1.0, RMS_level=-55),
        _frame(2.0, RMS_level=-10),
    ]

    result = run_analysis(video_frames=video, audio_frames=audio)
    assert len(result.regions) >= 1
    kinds = {region.kind for region in result.regions}
    assert 'video.dark_luma' in kinds


def test_run_analysis_aligns_ctl_pulses_to_video_start() -> None:
    video = []
    step = 1 / 30.0
    t = 0.0
    for _ in range(6):
        video.append(
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
        video.append(
            _lavfi_frame(
                t,
                SATAVG=8.0,
                YLOW=20.0,
                YHIGH=200.0,
                YDIF=25.0,
                UAVG=150.0,
                VAVG=110.0,
            )
        )
        t += step
    ctl = [
        _pulse(0.05, idx=0),
        _pulse(0.083, idx=1),
    ]

    result = run_analysis(video_frames=video, ctl_pulses=ctl)

    assert result.ctl_pulses is not None
    lock_time = video[6].pts_time
    assert result.video_lock_time == pytest.approx(lock_time)
    assert result.ctl_pulses[0].t == pytest.approx(lock_time)
    expected_delta = lock_time - 0.05
    assert result.ctl_pulses[1].t == pytest.approx(0.083 + expected_delta)


def test_run_analysis_skips_video_detectors_when_disabled() -> None:
    video = [
        _frame(0.0, YAVG=1),
        _frame(0.04, YAVG=1),
        _frame(0.08, YAVG=1),
        _frame(0.12, YAVG=50),
    ]

    result = run_analysis(
        video_frames=video,
        detection=DetectionToggles(video=False, audio=False, ctl=False),
    )

    assert result.regions == []


def test_run_analysis_skips_lock_estimation_when_video_and_ctl_disabled() -> None:
    video = [
        _frame(0.0, YAVG=10),
        _frame(0.04, YAVG=20),
    ]

    result = run_analysis(
        video_frames=video,
        detection=DetectionToggles(video=False, audio=True, ctl=False),
    )

    assert result.video_lock_time is None


def test_run_analysis_aligns_ctl_with_video_detectors_off() -> None:
    video = []
    step = 1 / 30.0
    t = 0.0
    for _ in range(6):
        video.append(
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
        video.append(
            _lavfi_frame(
                t,
                SATAVG=9.0,
                YLOW=20.0,
                YHIGH=200.0,
                YDIF=30.0,
                UAVG=150.0,
                VAVG=110.0,
            )
        )
        t += step
    ctl = [
        _pulse(0.05, idx=0),
        _pulse(0.083, idx=1),
    ]

    result = run_analysis(
        video_frames=video,
        ctl_pulses=ctl,
        detection=DetectionToggles(video=False, audio=False, ctl=True),
    )

    assert result.ctl_pulses is not None
    lock_time = video[6].pts_time
    assert result.video_lock_time == pytest.approx(lock_time)
    assert result.ctl_pulses[0].t == pytest.approx(lock_time)


def test_run_analysis_aligns_ctl_even_when_ctl_detection_disabled() -> None:
    video = []
    step = 1 / 30.0
    t = 0.0
    for _ in range(6):
        video.append(
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
    for _ in range(8):
        video.append(
            _lavfi_frame(
                t,
                SATAVG=9.0,
                YLOW=20.0,
                YHIGH=200.0,
                YDIF=30.0,
                UAVG=150.0,
                VAVG=110.0,
            )
        )
        t += step
    ctl = [_pulse(0.05, idx=0)]

    result = run_analysis(
        video_frames=video,
        ctl_pulses=ctl,
        detection=DetectionToggles(video=False, audio=False, ctl=False),
    )

    assert result.ctl_pulses is not None
    lock_time = video[6].pts_time
    assert result.video_lock_time == pytest.approx(lock_time)
    assert result.ctl_pulses[0].t == pytest.approx(lock_time)


def test_run_analysis_honors_manual_lock_override() -> None:
    manual_lock = 5.0
    video = [
        _frame(10.0, YAVG=50),
        _frame(10.04, YAVG=60),
    ]
    ctl = [_pulse(0.0, idx=0)]

    result = run_analysis(
        video_frames=video,
        ctl_pulses=ctl,
        video_lock_time_override=manual_lock,
    )

    assert result.video_lock_time == pytest.approx(manual_lock)
    assert result.ctl_pulses is not None
    assert result.ctl_pulses[0].t == pytest.approx(manual_lock)
