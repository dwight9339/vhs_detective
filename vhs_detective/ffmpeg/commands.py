"""Helpers that wrap FFmpeg/FFprobe invocations."""
from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)


def which_or_die(name: str) -> str:
    path = shutil.which(name)
    if not path:
        raise RuntimeError(f"Required executable not found in PATH: {name}")
    return path


def ffprobe_duration_seconds(ffprobe_exe: str, video_path: Path) -> Optional[float]:
    """Return the container duration using ffprobe."""

    cmd = [
        ffprobe_exe,
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(video_path),
    ]
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT)
    except Exception as exc:  # pragma: no cover - passthrough
        logger.debug("ffprobe duration failed", exc_info=exc)
        return None
    text = out.decode("utf-8", "replace").strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _ffmpeg_null_device() -> str:
    return "NUL" if os.name == "nt" else os.devnull


def run_ffmpeg_with_progress(cmd: List[str], duration_s: Optional[float], label: str) -> None:
    """Run FFmpeg with -progress and keep a single-line progress indicator."""

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )

    last_line = ""
    out_time_ms: Optional[int] = None
    try:
        assert proc.stdout is not None
        for line in proc.stdout:
            line = line.strip()
            if not line:
                continue
            last_line = line
            if line.startswith("out_time_ms="):
                try:
                    out_time_ms = int(line.split("=", 1)[1])
                except ValueError:
                    continue
            elif line.startswith("progress=") and line.endswith("end"):
                break

            if out_time_ms is not None:
                msg = _render_progress(duration_s, out_time_ms)
                if msg:
                    sys.stdout.write(f"\r{label}: {msg}   ")
                    sys.stdout.flush()

        rc = proc.wait()
        sys.stdout.write("\r" + " " * 80 + "\r")
        sys.stdout.flush()
        if rc != 0:
            stderr = proc.stderr.read() if proc.stderr else ""
            raise RuntimeError(
                f"FFmpeg failed (rc={rc}). Last progress line: {last_line}\n{stderr}"
            )
    finally:
        if proc.stdout:
            proc.stdout.close()
        if proc.stderr:
            proc.stderr.close()


def _render_progress(duration_s: Optional[float], out_time_ms: Optional[int]) -> str:
    if out_time_ms is None:
        return ""
    t = out_time_ms / 1_000_000.0
    if duration_s and duration_s > 0:
        pct = max(0.0, min(100.0, (t / duration_s) * 100.0))
        return f"{t:8.1f}s / {duration_s:8.1f}s  ({pct:6.2f}%)"
    return f"{t:8.1f}s"


def ffprobe_audio_sample_rate(ffprobe_exe: str, video_path: Path) -> Optional[int]:
    """Return the first audio stream sample rate, or None."""

    cmd = [
        ffprobe_exe,
        "-v",
        "error",
        "-select_streams",
        "a:0",
        "-show_entries",
        "stream=sample_rate",
        "-of",
        "json",
        str(video_path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        return None
    try:
        data = json.loads(proc.stdout)
    except Exception:  # pragma: no cover - unexpected JSON
        return None
    streams = data.get("streams") or []
    if not streams:
        return None
    sr = streams[0].get("sample_rate")
    try:
        return int(sr)
    except (TypeError, ValueError):
        return None


def generate_video_stats(ffmpeg_exe: str, ffprobe_exe: str, video_path: Path, out_stats: Path) -> None:
    duration_s = ffprobe_duration_seconds(ffprobe_exe, video_path)
    devnull = _ffmpeg_null_device()
    out_file_for_filter = out_stats.name if os.name == "nt" else str(out_stats)
    cmd = [
        ffmpeg_exe,
        "-hide_banner",
        "-nostats",
        "-i",
        str(video_path),
        "-an",
        "-vf",
        f"signalstats,metadata=print:file={out_file_for_filter}",
        "-f",
        "null",
        devnull,
        "-progress",
        "pipe:1",
    ]
    run_ffmpeg_with_progress(cmd, duration_s, label="Video stats")


def generate_audio_stats(ffmpeg_exe: str, ffprobe_exe: str, video_path: Path, out_stats: Path) -> None:
    duration_s = ffprobe_duration_seconds(ffprobe_exe, video_path)
    devnull = _ffmpeg_null_device()
    sample_rate = ffprobe_audio_sample_rate(ffprobe_exe, video_path)
    if not sample_rate:
        logger.info("No audio stream found; skipping audio stats.")
        return
    window_samples = sample_rate
    out_file_for_filter = out_stats.name if os.name == "nt" else str(out_stats)
    afilter = (
        f"asetnsamples=n={window_samples}:p=1,"
        f"astats=metadata=1:reset=1:measure_perchannel=none:measure_overall=RMS_level+Peak_level,"
        f"ametadata=print:file={out_file_for_filter}"
    )
    cmd = [
        ffmpeg_exe,
        "-hide_banner",
        "-nostats",
        "-nostdin",
        "-y",
        "-i",
        str(video_path),
        "-vn",
        "-map",
        "0:a:0?",
        "-af",
        afilter,
        "-f",
        "null",
        devnull,
        "-progress",
        "pipe:1",
    ]
    run_ffmpeg_with_progress(cmd, duration_s, label="Audio stats")
