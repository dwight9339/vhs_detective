"""CTL CSV ingestion utilities."""
from __future__ import annotations

import csv
from pathlib import Path
from typing import List

from ..models.core import CTLPulse


def load_ctl_csv_guess(path: Path) -> List[CTLPulse]:
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
