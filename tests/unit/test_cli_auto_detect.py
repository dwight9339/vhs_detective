import argparse
import pytest
from pathlib import Path

from vhs_detective.cli.app import (
    _auto_detect_base,
    _build_detection_toggles,
    _parse_lock_time,
)
from vhs_detective.models.core import DetectionToggles


def test_auto_detect_single_video(tmp_path: Path) -> None:
    video = tmp_path / 'example.mkv'
    video.touch()

    assert _auto_detect_base(tmp_path) == 'example'


def test_auto_detect_requires_base_when_multiple(tmp_path: Path) -> None:
    (tmp_path / 'a.mkv').touch()
    (tmp_path / 'b.mkv').touch()

    with pytest.raises(SystemExit) as exc:
        _auto_detect_base(tmp_path)
    assert 'Multiple video files' in str(exc.value)


def test_auto_detect_requires_base_when_none(tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as exc:
        _auto_detect_base(tmp_path)
    assert 'No video file' in str(exc.value)


def test_build_detection_toggles_defaults_to_all() -> None:
    toggles = _build_detection_toggles(None)
    assert toggles == DetectionToggles()


def test_build_detection_toggles_supports_subset() -> None:
    toggles = _build_detection_toggles(['ctl'])
    assert toggles.video is False
    assert toggles.audio is False
    assert toggles.ctl is True


def test_build_detection_toggles_parses_comma_separated_values() -> None:
    toggles = _build_detection_toggles(['video,audio'])
    assert toggles.video is True
    assert toggles.audio is True
    assert toggles.ctl is False


def test_build_detection_toggles_rejects_unknown_targets() -> None:
    with pytest.raises(SystemExit):
        _build_detection_toggles(['unknown'])


def test_parse_lock_time_accepts_seconds() -> None:
    assert _parse_lock_time('12.5') == pytest.approx(12.5)


def test_parse_lock_time_accepts_hms() -> None:
    assert _parse_lock_time('00:00:02.369') == pytest.approx(2.369)
    assert _parse_lock_time('01:02:03.5') == pytest.approx((1 * 3600) + (2 * 60) + 3.5)


def test_parse_lock_time_accepts_mm_ss() -> None:
    assert _parse_lock_time('5:30') == pytest.approx(330.0)


def test_parse_lock_time_rejects_invalid() -> None:
    with pytest.raises(argparse.ArgumentTypeError):
        _parse_lock_time('bad')
    with pytest.raises(argparse.ArgumentTypeError):
        _parse_lock_time('1:2:3:4')
