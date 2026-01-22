"""CTL CSV ingestion utilities."""
from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, List, Optional, TextIO

from ..models.core import CTLPulse

DEFAULT_SAMPLE_RATE_HZ = 100_000_000
_RAW_HEADERS = {"logic", "level"}
RAW_CAPTURE = "raw_logic_capture"
AGGREGATE_CSV = "aggregate_csv"


@dataclass
class RawCtlMetadata:
    """Optional metadata that accompanies a raw logic capture."""

    sample_rate_hz: int
    start_sample: Optional[int] = None
    samples: Optional[int] = None
    start_time_s: Optional[float] = None
    duration_s: Optional[float] = None
    description: Optional[str] = None


def load_ctl_csv_guess(path: Path) -> List[CTLPulse]:
    """Fallback parser for already-aggregated CTL CSV exports."""

    pulses: List[CTLPulse] = []
    with path.open('r', encoding='utf-8', errors='replace', newline='') as handle:
        reader = csv.reader(handle)
        header = next(reader, None)
        if header is None:
            return pulses
        header_lower = [h.strip().lower() for h in header]
        t_col = None
        dt_col = None
        for idx, name in enumerate(header_lower):
            if name in {'t', 'time', 'timestamp', 'seconds'}:
                t_col = idx
            if name in {'dt', 'delta', 'period'}:
                dt_col = idx
        if t_col is None:
            t_col = 0
        last_t = None
        pulse_idx = 0
        for row in reader:
            if not row:
                continue
            try:
                t = float(row[t_col])
            except Exception:
                continue
            if dt_col is not None:
                try:
                    dt = float(row[dt_col])
                except Exception:
                    dt = None
            else:
                dt = t - last_t if last_t is not None else None
            pulses.append(CTLPulse(t=t, dt=dt, idx=pulse_idx))
            last_t = t
            pulse_idx += 1
    return pulses


def load_raw_ctl_pulses(
    path: Path,
    *,
    sample_rate_hz: int = DEFAULT_SAMPLE_RATE_HZ,
    pulse_level: int = 0,
    min_pulse_samples: int = 1,
    max_samples: Optional[int] = None,
) -> List[CTLPulse]:
    """Materialize all pulses from a raw logic CSV."""

    return list(
        stream_raw_ctl_pulses(
            path,
            sample_rate_hz=sample_rate_hz,
            pulse_level=pulse_level,
            min_pulse_samples=min_pulse_samples,
            max_samples=max_samples,
        )
    )


def load_any_ctl_pulses(
    path: Path,
    *,
    default_sample_rate_hz: int = DEFAULT_SAMPLE_RATE_HZ,
    pulse_level: int = 0,
    min_pulse_samples: int = 1,
    max_samples: Optional[int] = None,
) -> List[CTLPulse]:
    """Load pulses from either a raw capture or an aggregate CSV."""

    fmt = sniff_ctl_format(path)
    if fmt == RAW_CAPTURE:
        meta = load_raw_ctl_metadata(path)
        sample_rate = meta.sample_rate_hz if meta else default_sample_rate_hz
        return load_raw_ctl_pulses(
            path,
            sample_rate_hz=sample_rate,
            pulse_level=pulse_level,
            min_pulse_samples=min_pulse_samples,
            max_samples=max_samples,
        )

    return load_ctl_csv_guess(path)


def stream_raw_ctl_pulses(
    path: Path,
    *,
    sample_rate_hz: int = DEFAULT_SAMPLE_RATE_HZ,
    pulse_level: int = 0,
    min_pulse_samples: int = 1,
    max_samples: Optional[int] = None,
) -> Iterator[CTLPulse]:
    """Stream CTLPulse objects from a raw logic CSV (e.g. 100 MHz captures)."""

    if min_pulse_samples < 1:
        raise ValueError("min_pulse_samples must be >= 1")

    with path.open('r', encoding='utf-8', errors='replace', newline='') as handle:
        yield from _stream_raw_ctl_pulses_from_handle(
            handle,
            sample_rate_hz=sample_rate_hz,
            pulse_level=pulse_level,
            min_pulse_samples=min_pulse_samples,
            max_samples=max_samples,
        )


def _stream_raw_ctl_pulses_from_handle(
    handle: TextIO,
    *,
    sample_rate_hz: int,
    pulse_level: int,
    min_pulse_samples: int,
    max_samples: Optional[int],
) -> Iterator[CTLPulse]:
    sample_iter = _iter_logic_samples(handle, max_samples=max_samples)
    run_level = None
    run_length = 0
    run_start = 0
    pulse_idx = 0

    for level in sample_iter:
        if run_level is None:
            run_level = level
            run_length = 1
            continue

        if level == run_level:
            run_length += 1
            continue

        maybe_pulse = _build_pulse(
            idx=pulse_idx,
            run_level=run_level,
            run_start=run_start,
            run_length=run_length,
            sample_rate_hz=sample_rate_hz,
            pulse_level=pulse_level,
            min_pulse_samples=min_pulse_samples,
        )
        if maybe_pulse is not None:
            pulse_idx += 1
            yield maybe_pulse

        run_start += run_length
        run_level = level
        run_length = 1

    if run_level is None:
        return

    maybe_pulse = _build_pulse(
        idx=pulse_idx,
        run_level=run_level,
        run_start=run_start,
        run_length=run_length,
        sample_rate_hz=sample_rate_hz,
        pulse_level=pulse_level,
        min_pulse_samples=min_pulse_samples,
    )
    if maybe_pulse is not None:
        yield maybe_pulse


def sniff_ctl_format(path: Path) -> str:
    """Return RAW_CAPTURE or AGGREGATE_CSV based on the file header."""

    header, first_value = _peek_header_and_first_value(path)
    header_lower = header.strip().lower()
    first_value = first_value.strip()
    if header_lower in _RAW_HEADERS and not first_value:
        return RAW_CAPTURE
    if header_lower in _RAW_HEADERS and first_value in {"0", "1"} and "," not in first_value:
        return RAW_CAPTURE
    if header_lower in _RAW_HEADERS and "," not in header_lower:
        return RAW_CAPTURE
    return AGGREGATE_CSV


def load_raw_ctl_metadata(path: Path) -> Optional[RawCtlMetadata]:
    """Load adjoining *_meta.json metadata if present."""

    meta_path = _derive_meta_path(path)
    if not meta_path.exists():
        return None
    try:
        data = json.loads(meta_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:  # pragma: no cover - once metadata exists tests guard
        raise ValueError(f"Failed to parse CTL metadata at {meta_path}: {exc}") from exc

    sample_rate = data.get("sample_rate_hz")
    if sample_rate is None:
        raise ValueError(f"Metadata at {meta_path} missing 'sample_rate_hz'")
    return RawCtlMetadata(
        sample_rate_hz=int(sample_rate),
        start_sample=data.get("start_sample"),
        samples=data.get("samples"),
        start_time_s=data.get("start_time_s"),
        duration_s=data.get("duration_s"),
        description=data.get("description"),
    )


def _derive_meta_path(path: Path) -> Path:
    return path.with_name(f"{path.stem}_meta.json")


def _peek_header_and_first_value(path: Path) -> tuple[str, str]:
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        header = handle.readline()
        first_value = ""
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            first_value = stripped
            break
    return header, first_value


def _iter_logic_samples(handle: TextIO, *, max_samples: Optional[int]) -> Iterator[int]:
    """Yield logic levels (0/1) from a raw capture while skipping the header."""

    header_consumed = False
    samples = 0
    for line_no, raw_line in enumerate(handle, start=1):
        cell = raw_line.strip()
        if not cell:
            continue
        try:
            level = int(cell)
        except ValueError:
            if not header_consumed:
                header_consumed = True
                continue
            raise ValueError(f"Unexpected token {cell!r} on line {line_no}") from None

        if level not in (0, 1):
            raise ValueError(f"Logic levels must be 0 or 1; saw {level!r} on line {line_no}")

        header_consumed = True
        yield level
        samples += 1
        if max_samples is not None and samples >= max_samples:
            break


def _build_pulse(
    *,
    idx: int,
    run_level: int,
    run_start: int,
    run_length: int,
    sample_rate_hz: int,
    pulse_level: int,
    min_pulse_samples: int,
) -> Optional[CTLPulse]:
    if run_level != pulse_level or run_length < min_pulse_samples:
        return None

    start_time = run_start / sample_rate_hz
    duration = run_length / sample_rate_hz
    return CTLPulse(
        t=start_time,
        dt=duration,
        idx=idx,
        level=run_level,
        start_sample=run_start,
        sample_count=run_length,
        sample_rate_hz=sample_rate_hz,
    )
