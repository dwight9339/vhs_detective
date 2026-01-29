"""Anomaly reporting helpers."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Sequence

from ..models.anomaly import AnalysisResult, Evidence, Region


def write_anomalies(path: Path, regions: Sequence[Region]) -> None:
    """Persist anomaly region data to JSON."""

    payload = {'regions': [_region_to_dict(region) for region in regions]}
    _write_json(path, payload)


def write_analysis_json(path: Path, analysis: AnalysisResult, *, base_name: str) -> None:
    """Emit the full analysis payload, including lock time + counts."""

    payload = {
        'source': base_name,
        'video_lock_time': analysis.video_lock_time,
        'counts': {
            'video_frames': len(analysis.video_frames),
            'audio_windows': len(analysis.audio_frames or []),
            'ctl_pulses': len(analysis.ctl_pulses or []),
            'regions': len(analysis.regions),
        },
        'regions': [_region_to_dict(region) for region in analysis.regions],
    }
    _write_json(path, payload)


def _region_to_dict(region: Region) -> Dict[str, object]:
    return {
        'kind': region.kind,
        'start_time': region.start_time,
        'end_time': region.end_time,
        'duration': max(0.0, region.end_time - region.start_time),
        'score': region.score,
        'evidence': [_evidence_to_dict(ev) for ev in region.evidence],
    }


def _evidence_to_dict(ev: Evidence) -> Dict[str, object]:
    return {
        'source': ev.source,
        'metric': ev.metric,
        'value': ev.value,
        'pts_time': ev.pts_time,
    }


def _write_json(path: Path, payload: Dict[str, object]) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding='utf-8')
