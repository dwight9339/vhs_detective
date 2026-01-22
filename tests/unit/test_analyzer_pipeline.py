from vhs_detective.analyzer.pipeline import run_analysis
from vhs_detective.models.core import FrameStats


def _frame(time: float, **kv: float) -> FrameStats:
    return FrameStats(pts_time=time, kv=dict(kv))


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
