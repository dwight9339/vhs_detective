"""Data structures describing detected anomaly regions."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Sequence

from .core import CTLPulse, FrameStats


@dataclass(frozen=True)
class Evidence:
    """Single metric sample supporting an anomaly decision."""

    source: str
    metric: str
    value: float
    pts_time: float


@dataclass(frozen=True)
class Region:
    """An anomalous span across the tape timeline."""

    kind: str
    start_time: float
    end_time: float
    score: Optional[float]
    evidence: List[Evidence] = field(default_factory=list)


@dataclass
class AnalysisResult:
    """Top-level output from the analysis pipeline."""

    regions: List[Region]
    video_frames: Sequence[FrameStats]
    audio_frames: Optional[Sequence[FrameStats]] = None
    ctl_pulses: Optional[Sequence[CTLPulse]] = None
    video_lock_time: Optional[float] = None
