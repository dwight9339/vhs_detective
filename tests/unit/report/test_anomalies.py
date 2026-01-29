import json
from pathlib import Path

import pytest

from vhs_detective.models.anomaly import AnalysisResult, Evidence, Region
from vhs_detective.models.core import FrameStats
from vhs_detective.report.anomalies import write_analysis_json, write_anomalies


def _frame(time: float) -> FrameStats:
    return FrameStats(pts_time=time, kv={})


def _sample_region() -> Region:
    return Region(
        kind='video.freeze_frame',
        start_time=2.0,
        end_time=3.0,
        score=0.5,
        evidence=[Evidence(source='video', metric='YDIFF', value=0.01, pts_time=2.5)],
    )


def test_write_analysis_json_captures_metadata(tmp_path: Path) -> None:
    analysis = AnalysisResult(
        regions=[_sample_region()],
        video_frames=[_frame(0.0)],
        audio_frames=[_frame(0.0)],
        ctl_pulses=[],
        video_lock_time=1.234,
    )
    path = tmp_path / 'analysis.json'

    write_analysis_json(path, analysis, base_name='demo')

    payload = json.loads(path.read_text())
    assert payload['source'] == 'demo'
    assert payload['video_lock_time'] == pytest.approx(1.234)
    assert payload['counts']['regions'] == 1
    assert payload['regions'][0]['kind'] == 'video.freeze_frame'
    assert payload['regions'][0]['evidence'][0]['metric'] == 'YDIFF'


def test_write_anomalies_serializes_regions(tmp_path: Path) -> None:
    path = tmp_path / 'regions.json'
    write_anomalies(path, [_sample_region()])

    payload = json.loads(path.read_text())
    assert len(payload['regions']) == 1
    region = payload['regions'][0]
    assert region['duration'] == pytest.approx(1.0)
