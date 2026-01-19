import pytest
from pathlib import Path

from vhs_detective.cli.app import _auto_detect_base


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
