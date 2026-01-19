"""Placeholder anomaly reporting helpers."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Sequence


def write_anomalies(path: Path, regions: Sequence[dict]) -> None:
    """Persist placeholder anomaly data for downstream tooling."""

    payload = {'regions': list(regions)}
    path.write_text(json.dumps(payload, indent=2), encoding='utf-8')
