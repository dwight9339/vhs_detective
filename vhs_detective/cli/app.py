"""Command-line entry points for VHS Detective."""
from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Sequence

from ..config.schema import AnalysisConfig
from ..ctl.parser import load_ctl_csv_guess
from ..ffmpeg.commands import which_or_die
from ..fs.discovery import discover_inputs, ensure_stats
from ..stats.audio import parse_audio_stats
from ..stats.video import parse_video_stats

_VIDEO_EXTENSIONS = ('.mkv',)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description='Tape analysis: video + audio + optional CTL stats',
    )
    parser.add_argument(
        'base',
        nargs='?',
        help='Common base-name (defaults to the lone *.mkv file in the working directory)',
    )
    parser.add_argument(
        '--workdir',
        type=Path,
        default=None,
        help='Override working directory (defaults to current directory)',
    )
    parser.add_argument(
        '--log-level',
        default='INFO',
        help='Logging level (DEBUG, INFO, WARNING, ...)',
    )
    return parser


def run_cli(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    logging.basicConfig(level=getattr(logging, str(args.log_level).upper(), logging.INFO))
    logger = logging.getLogger(__name__)

    workdir = args.workdir or Path.cwd()
    base = args.base or _auto_detect_base(workdir)

    ffmpeg_exe = which_or_die('ffmpeg')
    ffprobe_exe = which_or_die('ffprobe')

    cfg = AnalysisConfig(base=base, working_dir=workdir)
    logger.debug('Analysis config: %s', cfg)

    inputs = discover_inputs(cfg.base, cfg.working_dir)
    inputs = ensure_stats(inputs, ffmpeg_exe, ffprobe_exe)

    logger.info('Parsing video stats...')
    video_frames = parse_video_stats(inputs.video_stats)
    logger.info('Parsed "%s" (%d frames)', inputs.video_stats.name, len(video_frames))

    audio_frames = None
    if inputs.audio_stats and inputs.audio_stats.exists():
        logger.info('Parsing audio stats...')
        audio_frames = parse_audio_stats(inputs.audio_stats)
        logger.info('Parsed "%s" (%d windows)', inputs.audio_stats.name, len(audio_frames))

    ctl_pulses = None
    if inputs.ctl_csv:
        logger.info('Loading CTL CSV...')
        ctl_pulses = load_ctl_csv_guess(inputs.ctl_csv)
        logger.info('Loaded %d CTL pulses', len(ctl_pulses))

    _log_next_steps(
        logger,
        video_frames_count=len(video_frames),
        audio_frames_count=len(audio_frames or []),
        ctl_count=len(ctl_pulses or []),
    )
    return 0


def _log_next_steps(
    logger: logging.Logger,
    *,
    video_frames_count: int,
    audio_frames_count: int,
    ctl_count: int,
) -> None:
    logger.info('Stats ingestion complete. Detection + UI are next.')
    logger.info('Video frames: %d | Audio windows: %d | CTL pulses: %d', video_frames_count, audio_frames_count, ctl_count)


def _auto_detect_base(workdir: Path) -> str:
    candidates = sorted(
        path.name
        for path in workdir.iterdir()
        if path.is_file() and path.suffix.lower() in _VIDEO_EXTENSIONS
    )
    if not candidates:
        raise SystemExit(
            f"No video file with extensions {', '.join(_VIDEO_EXTENSIONS)} found in {workdir}. "
            'Specify BASE explicitly.'
        )
    if len(candidates) > 1:
        raise SystemExit(
            "Multiple video files found ({files}). Specify BASE explicitly.".format(
                files=', '.join(candidates)
            )
        )
    return Path(candidates[0]).stem
