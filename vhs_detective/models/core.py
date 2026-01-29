"""Shared data structures used across the pipeline."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional


@dataclass
class FrameStats:
    """Numeric metadata emitted by FFmpeg for a single frame/window."""

    pts_time: float
    kv: Dict[str, float]


@dataclass
class CTLPulse:
    """Single CTL pulse observation.

    Historically CTL pulses were represented just by a timestamp (`t`) and an
    optional duration (`dt`).  As we start parsing raw logic captures we also
    track which logic level was considered the pulse, plus the run-length
    metadata derived from the original sample stream.
    """

    t: float
    dt: Optional[float]
    idx: int
    level: int = 0
    start_sample: Optional[int] = None
    sample_count: Optional[int] = None
    sample_rate_hz: Optional[int] = None

    @property
    def start_time(self) -> float:
        """Alias for code that expects `t` to hold the pulse start time."""

        return self.t

    @property
    def duration(self) -> Optional[float]:
        """Alias for `dt` (kept for clarity in the new parser context)."""

        return self.dt

    @property
    def end_time(self) -> Optional[float]:
        """Convenience accessor for downstream detectors."""

        if self.dt is None:
            return None
        return self.t + self.dt


@dataclass
class Inputs:
    """All files discovered for a single base-name."""

    base: str
    video: Path
    ctl_csv: Optional[Path]
    video_stats: Path
    audio_stats: Optional[Path]


@dataclass(frozen=True)
class DetectionToggles:
    """Toggle individual detector families on/off."""

    video: bool = True
    audio: bool = True
    ctl: bool = True
