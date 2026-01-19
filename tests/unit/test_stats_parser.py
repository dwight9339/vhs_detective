from pathlib import Path

from vhs_detective.stats.parsers import parse_metadata_print_file


def test_parse_metadata_print_file_fixture() -> None:
    fixture = Path(__file__).resolve().parents[1] / 'fixtures' / 'sample_signalstats.txt'
    frames = parse_metadata_print_file(fixture)
    assert len(frames) == 2
    assert frames[0].pts_time == 0.0
    assert frames[0].kv['YAVG'] == 12.5
    assert 'key' not in frames[1].kv
    assert frames[1].kv['XMIN'] == 0.5
