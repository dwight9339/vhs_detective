from pathlib import Path

from vhs_detective.models.anomaly import AnalysisResult, Evidence, Region
from vhs_detective.models.core import FrameStats
from vhs_detective.report.summary import write_text_summary


def _frame(time: float) -> FrameStats:
    return FrameStats(pts_time=time, kv={})


def test_write_text_summary_lists_anomalies(tmp_path: Path) -> None:
    region = Region(
        kind='video.dark_luma',
        start_time=1.0,
        end_time=2.0,
        score=3.14,
        evidence=[Evidence(source='video', metric='YAVG', value=2.0, pts_time=1.5)],
    )
    analysis = AnalysisResult(
        regions=[region],
        video_frames=[_frame(0.0)],
        video_lock_time=0.75,
    )

    summary_path = tmp_path / 'summary.txt'
    write_text_summary(summary_path, analysis, base_name='example')

    text = summary_path.read_text()
    assert 'Video lock time: 0.750s' in text
    assert 'video.dark_luma' in text
    assert '1.000s -' in text
    assert 'evidence' in text


def test_write_text_summary_handles_no_anomalies(tmp_path: Path) -> None:
    analysis = AnalysisResult(
        regions=[],
        video_frames=[_frame(0.0)],
        video_lock_time=None,
    )
    summary_path = tmp_path / 'summary.txt'
    write_text_summary(summary_path, analysis, base_name='empty')

    text = summary_path.read_text()
    assert 'Video lock time: unknown' in text
    assert '(none detected)' in text
