"""Command-line entry points for VHS Detective."""
from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import List, Sequence, Set

from ..analyzer.pipeline import run_analysis
from ..config.schema import AnalysisConfig, CTLConfig
from ..ctl import parser as ctl_parser
from ..ffmpeg.commands import which_or_die
from ..fs.discovery import discover_inputs, ensure_stats
from ..models.core import CTLPulse, DetectionToggles
from ..report.anomalies import write_analysis_json
from ..report.summary import write_text_summary
from ..stats.audio import parse_audio_stats
from ..stats.video import parse_video_stats

_VIDEO_EXTENSIONS = ('.mkv',)
_DETECTION_TARGETS = ('video', 'audio', 'ctl')


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
    parser.add_argument(
        '--detect',
        dest='detect_targets',
        action='append',
        metavar='TARGETS',
        help=(
            'Restrict detector families (video, audio, ctl). '
            'Provide multiple --detect flags or comma-separated values; defaults to all.'
        ),
    )
    parser.add_argument(
        '--video-lock-time',
        type=_parse_lock_time,
        default=None,
        help='Manually specify the video lock start time (seconds or HH:MM:SS.mmm).',
    )
    parser.add_argument(
        '--ctl-sample-rate',
        type=int,
        default=None,
        help='Override CTL raw capture sample rate in Hz (fallback when metadata missing)',
    )
    parser.add_argument(
        '--ctl-min-pulse-samples',
        type=int,
        default=5,
        help='Minimum run length (samples) to treat as a CTL pulse (glitch filter).',
    )
    parser.add_argument(
        '--ctl-pulse-level',
        type=int,
        choices=(0, 1),
        default=0,
        help='Logic level that represents the CTL pulse (0 = low-going, 1 = high).',
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

    detect_cfg = _build_detection_toggles(args.detect_targets)
    ctl_cfg = CTLConfig(
        sample_rate_hz=args.ctl_sample_rate,
        min_pulse_samples=args.ctl_min_pulse_samples,
        pulse_level=args.ctl_pulse_level,
    )
    cfg = AnalysisConfig(
        base=base,
        working_dir=workdir,
        detection=detect_cfg,
        video_lock_time_override=args.video_lock_time,
        ctl=ctl_cfg,
    )
    logger.debug('Analysis config: %s', cfg)
    logger.info(
        'Detectors enabled | video=%s audio=%s ctl=%s',
        'ON' if cfg.detection.video else 'OFF',
        'ON' if cfg.detection.audio else 'OFF',
        'ON' if cfg.detection.ctl else 'OFF',
    )

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
        ctl_pulses = _ingest_ctl_capture(inputs.ctl_csv, logger, cfg.ctl)

    analysis = run_analysis(
        video_frames=video_frames,
        audio_frames=audio_frames,
        ctl_pulses=ctl_pulses,
        video_lock_time_override=cfg.video_lock_time_override,
        detection=cfg.detection,
    )
    logger.info('Detected %d anomaly region(s)', len(analysis.regions))
    _log_next_steps(
        logger,
        video_frames_count=len(video_frames),
        audio_frames_count=len(audio_frames or []),
        ctl_count=len(ctl_pulses or []),
    )
    has_ctl_data = bool(ctl_pulses)
    should_estimate_lock = cfg.detection.video or cfg.detection.ctl or has_ctl_data
    if cfg.video_lock_time_override is not None:
        logger.info('Video lock override provided: %.3f s', cfg.video_lock_time_override)
    elif not should_estimate_lock:
        logger.info('Video lock estimation skipped (video/CTL detectors disabled and no CTL capture).')
    elif analysis.video_lock_time is not None:
        logger.info('Video lock detected at %.3f s', analysis.video_lock_time)
    else:
        logger.info('Video lock time could not be determined from the stats.')

    summary_path = cfg.working_dir / f"{cfg.base}_analysis.txt"
    write_text_summary(summary_path, analysis, base_name=cfg.base)
    logger.info('Wrote analysis summary to %s', summary_path.name)

    json_path = cfg.working_dir / f"{cfg.base}_analysis.json"
    write_analysis_json(json_path, analysis, base_name=cfg.base)
    logger.info('Wrote analysis JSON to %s', json_path.name)

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


def _ingest_ctl_capture(path: Path, logger: logging.Logger, ctl_cfg: CTLConfig) -> List[CTLPulse]:
    """Load CTL pulses from whichever capture format is present."""

    logger.info('Loading CTL capture from %s', path.name)
    fmt = ctl_parser.sniff_ctl_format(path)
    if fmt == ctl_parser.RAW_CAPTURE:
        metadata = ctl_parser.load_raw_ctl_metadata(path)
        sample_rate_hz = (
            metadata.sample_rate_hz
            if metadata and metadata.sample_rate_hz
            else ctl_cfg.sample_rate_hz
            if ctl_cfg.sample_rate_hz is not None
            else ctl_parser.DEFAULT_SAMPLE_RATE_HZ
        )
        if metadata:
            logger.info(
                'Detected raw logic capture (%s) | sample rate %.2f MHz (metadata)',
                path.name,
                sample_rate_hz / 1_000_000,
            )
        else:
            logger.info(
                'Detected raw logic capture (%s) | sample rate %.2f MHz (%s)',
                path.name,
                sample_rate_hz / 1_000_000,
                'CLI override' if ctl_cfg.sample_rate_hz else 'package default',
            )
        pulses = ctl_parser.load_raw_ctl_pulses(
            path,
            sample_rate_hz=sample_rate_hz,
            pulse_level=ctl_cfg.pulse_level,
            min_pulse_samples=ctl_cfg.min_pulse_samples,
        )
    else:
        logger.info('Detected aggregate CTL CSV (columns).')
        pulses = ctl_parser.load_ctl_csv_guess(path)
    logger.info('Loaded %d CTL pulses', len(pulses))
    return pulses


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


def _build_detection_toggles(raw_targets: Sequence[str] | None) -> DetectionToggles:
    if not raw_targets:
        return DetectionToggles()
    selected: Set[str] = set()
    for chunk in raw_targets:
        for value in chunk.split(','):
            normalized = value.strip().lower()
            if not normalized:
                continue
            if normalized not in _DETECTION_TARGETS:
                choices = ', '.join(_DETECTION_TARGETS)
                raise SystemExit(f"Unknown detection target '{value}'. Choose from: {choices}.")
            selected.add(normalized)
    if not selected:
        raise SystemExit('At least one detection target must be specified when using --detect.')
    return DetectionToggles(
        video='video' in selected,
        audio='audio' in selected,
        ctl='ctl' in selected,
    )


def _parse_lock_time(value: str) -> float:
    stripped = value.strip()
    if not stripped:
        raise argparse.ArgumentTypeError('Video lock time must be non-empty.')
    try:
        return float(stripped)
    except ValueError:
        pass

    sign = -1.0 if stripped.startswith('-') else 1.0
    work = stripped[1:] if sign < 0 else stripped
    parts = work.split(':')
    if len(parts) not in (2, 3):
        raise argparse.ArgumentTypeError(
            f"Invalid time format '{value}'. Use seconds or HH:MM:SS.mmm."
        )
    try:
        seconds = float(parts[-1])
        minutes = int(parts[-2])
        hours = int(parts[-3]) if len(parts) == 3 else 0
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"Invalid numeric component in '{value}'."
        ) from exc
    total = hours * 3600 + minutes * 60 + seconds
    return sign * total
