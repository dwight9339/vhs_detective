"""Parsing helpers for FFmpeg metadata output."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Optional

from ..models.core import FrameStats

_VIDEO_META_RE = re.compile(r"(?P<key>[A-Za-z0-9_.:-]+)=(?P<val>.+)$")


def parse_metadata_print_file(path: Path) -> List[FrameStats]:
    frames: List[FrameStats] = []
    cur_pts: Optional[float] = None
    cur_kv: Dict[str, float] = {}

    def flush() -> None:
        nonlocal cur_pts, cur_kv
        if cur_pts is not None and cur_kv:
            frames.append(FrameStats(cur_pts, dict(cur_kv)))
        cur_pts = None
        cur_kv = {}

    with path.open('r', encoding='utf-8', errors='replace') as handle:
        for raw in handle:
            line = raw.strip()
            if not line:
                continue
            if 'pts_time:' in line:
                match = re.search(r"pts_time:(-?\d+(?:\.\d+)?)", line)
                if match:
                    flush()
                    cur_pts = float(match.group(1))
                continue
            m = _VIDEO_META_RE.match(line)
            if not m:
                continue
            key = m.group('key')
            val = m.group('val').strip()
            try:
                cur_kv[key] = float(val)
            except ValueError:
                continue
    flush()
    return frames
