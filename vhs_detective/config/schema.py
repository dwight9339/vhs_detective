"""Configuration dataclasses for VHS Detective."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AnalysisConfig:
    """High-level knobs for an analysis run."""

    base: str
    working_dir: Path
