"""File discovery helpers."""
from __future__ import annotations

import logging
from pathlib import Path

from ..ffmpeg.commands import generate_audio_stats, generate_video_stats
from ..models.core import Inputs

logger = logging.getLogger(__name__)


def discover_inputs(base: str, cwd: Path) -> Inputs:
    video = cwd / f"{base}.mkv"
    if not video.exists():
        raise FileNotFoundError(f"Missing required video file: {video.name}")
    ctl_candidate = cwd / f"{base}_ctl.csv"
    ctl_csv = ctl_candidate if ctl_candidate.exists() else None
    video_stats = cwd / f"{base}_video_stats.txt"
    audio_stats = cwd / f"{base}_audio_stats.txt"
    audio_stats = audio_stats if audio_stats.exists() else None
    return Inputs(
        base=base,
        video=video,
        ctl_csv=ctl_csv,
        video_stats=video_stats,
        audio_stats=audio_stats,
    )


def ensure_stats(inputs: Inputs, ffmpeg_exe: str, ffprobe_exe: str) -> Inputs:
    if not inputs.video_stats.exists():
        logger.info("Generating video stats: %s", inputs.video_stats.name)
        generate_video_stats(ffmpeg_exe, ffprobe_exe, inputs.video, inputs.video_stats)
    else:
        logger.info("Found video stats: %s", inputs.video_stats.name)
    if inputs.audio_stats is None:
        target = inputs.video_stats.with_name(f"{inputs.base}_audio_stats.txt")
        if not target.exists():
            logger.info("Generating audio stats: %s", target.name)
            generate_audio_stats(ffmpeg_exe, ffprobe_exe, inputs.video, target)
        if target.exists():
            inputs.audio_stats = target
    else:
        logger.info("Found audio stats: %s", inputs.audio_stats.name)
    return inputs
