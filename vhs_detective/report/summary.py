"""Text-based analysis summary writer."""
from __future__ import annotations

from pathlib import Path
from typing import Iterable

from ..models.anomaly import AnalysisResult, Evidence, Region


def write_text_summary(path: Path, analysis: AnalysisResult, *, base_name: str) -> None:
    """Write a human-readable summary containing lock info + ordered anomalies."""

    lines: list[str] = []
    lines.append('VHS Detective Analysis Summary')
    lines.append(f'Source: {base_name}')
    lock_line = _format_lock_time(analysis.video_lock_time)
    lines.append(lock_line)
    lines.append(
        'Counts: video_frames={video} | audio_windows={audio} | ctl_pulses={ctl}'.format(
            video=len(analysis.video_frames),
            audio=len(analysis.audio_frames or []),
            ctl=len(analysis.ctl_pulses or []),
        )
    )
    lines.append('')
    lines.append('Anomalies (sorted by start time):')
    if not analysis.regions:
        lines.append('  (none detected)')
    else:
        for idx, region in enumerate(analysis.regions, start=1):
            lines.extend(_format_region_lines(idx, region))
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')


def _format_lock_time(lock_time: float | None) -> str:
    if lock_time is None:
        return 'Video lock time: unknown'
    return f'Video lock time: {lock_time:.3f}s'


def _format_region_lines(index: int, region: Region) -> Iterable[str]:
    duration = max(0.0, region.end_time - region.start_time)
    score = f'{region.score:.2f}' if region.score is not None else 'n/a'
    header = (
        f'  {index}. [{region.start_time:8.3f}s - {region.end_time:8.3f}s | '
        f'duration {duration:6.3f}s] {region.kind} (score={score})'
    )
    lines = [header]
    if region.evidence:
        ev = region.evidence[0]
        lines.append(
            f'      evidence: {ev.source}.{ev.metric}={ev.value:.3f} @ {ev.pts_time:.3f}s'
        )
    return lines
