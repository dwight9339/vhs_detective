"""Video stats helpers."""
from __future__ import annotations

from pathlib import Path
from typing import List

from ..models.core import FrameStats
from .parsers import parse_metadata_print_file


def parse_video_stats(path: Path) -> List[FrameStats]:
    return parse_metadata_print_file(path)
