"""Analysis pipeline that orchestrates detectors across data sources."""
from __future__ import annotations

from typing import List, Optional, Sequence

from ..detect import audio as audio_detect
from ..detect import video as video_detect
from ..models.anomaly import AnalysisResult, Region
from ..models.core import CTLPulse, FrameStats


def run_analysis(
    *,
    video_frames: Sequence[FrameStats],
    audio_frames: Optional[Sequence[FrameStats]] = None,
    ctl_pulses: Optional[Sequence[CTLPulse]] = None,
) -> AnalysisResult:
    """Run all detectors across available data sources."""

    regions: List[Region] = []
    regions.extend(video_detect.detect_video_dark_regions(video_frames))
    if audio_frames:
        regions.extend(audio_detect.detect_audio_silence_regions(audio_frames))

    # Future: add CTL + fusion detectors here
    regions.sort(key=lambda region: region.start_time)

    return AnalysisResult(
        regions=regions,
        video_frames=video_frames,
        audio_frames=audio_frames,
        ctl_pulses=ctl_pulses,
    )
