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
    """Single CTL pulse observation."""

    t: float
    dt: Optional[float]
    idx: int


@dataclass
class Inputs:
    """All files discovered for a single base-name."""

    base: str
    video: Path
    ctl_csv: Optional[Path]
    video_stats: Path
    audio_stats: Optional[Path]
