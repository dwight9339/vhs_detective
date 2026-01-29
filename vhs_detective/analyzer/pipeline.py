"""Analysis pipeline that orchestrates detectors across data sources."""
from __future__ import annotations

from typing import List, Optional, Sequence

from ..detect import audio as audio_detect
from ..detect import video as video_detect
from ..models.anomaly import AnalysisResult, Region
from ..models.core import CTLPulse, DetectionToggles, FrameStats


def run_analysis(
    *,
    video_frames: Sequence[FrameStats],
    audio_frames: Optional[Sequence[FrameStats]] = None,
    ctl_pulses: Optional[Sequence[CTLPulse]] = None,
    video_lock_time_override: Optional[float] = None,
    detection: Optional[DetectionToggles] = None,
) -> AnalysisResult:
    """Run all detectors across available data sources."""

    toggles = detection or DetectionToggles()
    has_ctl_data = bool(ctl_pulses)
    should_estimate_lock = toggles.video or toggles.ctl or has_ctl_data
    if video_lock_time_override is not None:
        lock_time = video_lock_time_override
    elif should_estimate_lock:
        lock_time = video_detect.estimate_video_lock_time(video_frames)
    else:
        lock_time = None

    if ctl_pulses:
        _align_ctl_to_video(video_frames, ctl_pulses, lock_time=lock_time)

    regions: List[Region] = []
    if toggles.video:
        regions.extend(video_detect.detect_video_dark_regions(video_frames))
        regions.extend(video_detect.detect_video_bright_regions(video_frames))
        regions.extend(video_detect.detect_video_freeze_regions(video_frames))
        regions.extend(video_detect.detect_video_dropframe_gaps(video_frames))
        regions.extend(video_detect.detect_video_chroma_dropouts(video_frames))
        regions.extend(video_detect.detect_video_noise_spikes(video_frames))
    if toggles.audio and audio_frames:
        regions.extend(audio_detect.detect_audio_silence_regions(audio_frames))

    # Future: add CTL + fusion detectors here
    regions.sort(key=lambda region: region.start_time)

    return AnalysisResult(
        regions=regions,
        video_frames=video_frames,
        audio_frames=audio_frames,
        ctl_pulses=ctl_pulses,
        video_lock_time=lock_time,
    )


def _align_ctl_to_video(
    video_frames: Sequence[FrameStats],
    ctl_pulses: Optional[Sequence[CTLPulse]],
    *,
    lock_time: Optional[float],
) -> None:
    """Shift CTL pulse timestamps so the first pulse lines up with video start.

    Field captures often begin slightly before/after FFmpeg stats logging.
    We now estimate the first usable video timestamp (color burst or the first
    luma-rich frame after a blank run) and anchor the CTL pulses to that point.
    """

    if not video_frames or not ctl_pulses:
        return

    anchor_pts = lock_time if lock_time is not None else video_frames[0].pts_time
    first_ctl_start = ctl_pulses[0].start_time
    offset = anchor_pts - first_ctl_start
    if offset == 0.0:
        return
    for pulse in ctl_pulses:
        pulse.t += offset
