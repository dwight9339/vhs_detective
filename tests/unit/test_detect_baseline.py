from vhs_detective.detect import baseline
from vhs_detective.models.core import FrameStats


def _frame(time: float, **kv: float) -> FrameStats:
    return FrameStats(pts_time=time, kv=dict(kv))


def test_detect_video_dark_regions_filters_by_duration() -> None:
    frames = [
        _frame(0.0, YAVG=10),
        _frame(0.04, YAVG=3),
        _frame(0.08, YAVG=2),
        _frame(0.12, YAVG=7),
    ]
    regions = baseline.detect_video_dark_regions(
        frames,
        yavg_threshold=4,
        min_duration=0.05,
    )
    assert len(regions) == 1
    region = regions[0]
    assert region.kind == 'video.dark_luma'
    assert region.start_time == 0.04
    assert region.end_time > region.start_time
    assert region.evidence[0].metric == 'YAVG'


def test_detect_audio_silence_regions_handles_low_rms() -> None:
    frames = [
        _frame(0.0, RMS_level=-20),
        _frame(1.0, RMS_level=-55),
        _frame(2.0, RMS_level=-60),
        _frame(3.0, RMS_level=-18),
    ]
    regions = baseline.detect_audio_silence_regions(
        frames,
        rms_threshold=-45,
        min_duration=1.0,
    )
    assert len(regions) == 1
    assert regions[0].kind == 'audio.low_rms'
    assert regions[0].evidence[0].metric == 'RMS_level'
