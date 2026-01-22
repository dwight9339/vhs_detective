"""Tests for CTL parser helpers."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from vhs_detective.ctl import parser


FIXTURE_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "ctl"


def test_sniff_ctl_format_detects_raw_logic() -> None:
    fixture = FIXTURE_DIR / "hurricanes_field_sample.csv"
    detected = parser.sniff_ctl_format(fixture)
    assert detected == parser.RAW_CAPTURE


def test_stream_raw_ctl_pulses_extracts_low_runs() -> None:
    fixture = FIXTURE_DIR / "hurricanes_field_sample.csv"

    pulses = list(
        parser.stream_raw_ctl_pulses(
            fixture,
            sample_rate_hz=100_000_000,
            pulse_level=0,
            min_pulse_samples=1,
        )
    )

    assert len(pulses) == 19
    first = pulses[0]
    assert first.level == 0
    assert first.idx == 0
    assert first.start_sample == 116
    assert first.sample_count == 26
    assert first.t == pytest.approx(116 / 100_000_000)
    assert first.dt == pytest.approx(26 / 100_000_000)

    last = pulses[-1]
    assert last.start_sample == 59894
    assert last.sample_count == 21


def test_stream_raw_ctl_pulses_respects_glitch_filter(tmp_path: Path) -> None:
    capture = tmp_path / "glitch.csv"
    capture.write_text(
        "\n".join(
            [
                "logic",
                "1",
                "1",
                "1",
                "0",  # glitch (1 sample)
                "1",
                "1",
                "0",
                "0",
                "0",  # real pulse (3 samples)
                "1",
            ]
        ),
        encoding="utf-8",
    )

    pulses = list(
        parser.stream_raw_ctl_pulses(
            capture,
            sample_rate_hz=1,
            pulse_level=0,
            min_pulse_samples=2,
        )
    )

    assert len(pulses) == 1
    pulse = pulses[0]
    assert pulse.start_sample == 6
    assert pulse.sample_count == 3
    assert pulse.t == pytest.approx(6)
    assert pulse.dt == pytest.approx(3)


def test_load_any_ctl_pulses_uses_metadata_sample_rate(tmp_path: Path) -> None:
    fixture = FIXTURE_DIR / "hurricanes_field_sample.csv"
    meta_target = tmp_path / "capture.csv"
    meta_target.write_text(fixture.read_text(encoding="utf-8"), encoding="utf-8")
    meta = {
        "sample_rate_hz": 200,
    }
    (tmp_path / "capture_meta.json").write_text(
        json.dumps(meta),
        encoding="utf-8",
    )

    pulses = parser.load_any_ctl_pulses(
        meta_target,
        default_sample_rate_hz=50,
        pulse_level=0,
        min_pulse_samples=1,
    )

    assert pulses[0].dt == pytest.approx(pulses[0].sample_count / 200)


def test_sniff_ctl_format_handles_aggregate(tmp_path: Path) -> None:
    aggregate = tmp_path / "agg.csv"
    aggregate.write_text("time,dt\n0.0,0.1\n0.1,0.1\n", encoding="utf-8")
    detected = parser.sniff_ctl_format(aggregate)
    assert detected == parser.AGGREGATE_CSV
