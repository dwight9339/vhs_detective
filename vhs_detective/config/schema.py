"""Configuration dataclasses for VHS Detective."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from ..models.core import DetectionToggles


@dataclass(frozen=True)
class CTLConfig:
    """Controls how CTL captures are parsed."""

    sample_rate_hz: Optional[int] = None
    min_pulse_samples: int = 5
    pulse_level: int = 0


@dataclass(frozen=True)
class AnalysisConfig:
    """High-level knobs for an analysis run."""

    base: str
    working_dir: Path
    detection: DetectionToggles = field(default_factory=DetectionToggles)
    video_lock_time_override: Optional[float] = None
    ctl: CTLConfig = field(default_factory=CTLConfig)
