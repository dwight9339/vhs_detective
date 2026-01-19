# VHS Detective

VHS Detective is a Python toolchain for **forensic analysis of VHS captures**. It ingests lossless captures (typically FFV1-in-MKV), runs FFmpeg-based probes, and turns those metrics into explainable anomaly reports.

## Features

- Generate and parse **per-frame video signal metrics** with `signalstats`.
- Generate and parse **time-windowed audio metrics** with `astats`.
- Optionally ingest **CTL pulse CSVs** and correlate control-track pulses with video time.
- Detect and categorize **anomalous regions** (dropouts, edits, tracking issues, silence/spikes, etc.).
- Export structured results for downstream review tooling.

> **Philosophy:** explainable heuristics first-every flagged region should trace back to metrics and thresholds.

## Status

Active development. Early milestones focus on:

- File discovery by base-name.
- Stats generation (video + audio).
- Parsing metrics into stable data models.
- First-pass anomaly detection (placeholders today).

Timeline/review UI work will follow after the core pipeline stabilizes.

## Requirements

- Python 3.10+ (3.11+ recommended).
- FFmpeg + FFprobe available on `PATH` (any recent build works).
- Optional: CTL pulse CSVs from your capture workflow.

## Quickstart

1. Place capture artifacts in a single directory (the working directory):

   - Required: `<base>.mkv`
   - Optional inputs: `<base>_ctl.csv`
   - Derived if missing: `<base>_video_stats.txt`, `<base>_audio_stats.txt`

2. Run the CLI:

   ```bash
   # Entry point shim maintained for convenience
   python analyze_tape.py hurricanes_of_the_1980s

   # Equivalent package invocation
   python -m vhs_detective.cli.app hurricanes_of_the_1980s
   ```

   Missing stats files will be generated automatically via FFmpeg.
   If the working directory contains exactly one `.mkv`, the CLI infers the base name automatically; when multiple captures are present, pass the desired base explicitly.

## What stats are generated?

### Video stats (`signalstats`)

The CLI runs a filtergraph equivalent to:

- `signalstats`
- `metadata=print:file=...`

Results include per-frame luma/chroma and noise measurements.

### Audio stats (`astats`)

Audio metrics rely on:

- `asetnsamples` (~1 s window) to control cadence.
- `astats=metadata=1:reset=1:measure_overall=RMS_level+Peak_level`.
- `ametadata=print:file=...` to emit text logs.

We focus on a small, useful subset of measures to avoid multi-gigabyte logs.

## Project Layout

```
vhs_detective/
    cli/            # argparse entry points
    config/         # typed config models
    ctl/            # CTL CSV ingest + normalization
    detect/         # placeholder detection heuristics
    ffmpeg/         # ffmpeg/ffprobe wrappers
    fs/             # discovery + derived artifact helpers
    models/         # shared dataclasses
    report/         # anomaly exporters
    stats/          # metadata parsing + helpers
tests/
    fixtures/       # lightweight text fixtures
    unit/           # pytest suites (see conftest.py)
```

`AGENTS.md` documents architectural conventions, code ownership, and the contribution workflow in more detail.

## Cross-platform notes

The project targets Windows and Linux:

- Ensure `ffmpeg` and `ffprobe` live on the `PATH`.
- Prefer relative paths when telling FFmpeg where to write logs (`metadata=print:file=...`).
- Inputs without audio are tolerated-audio stats generation simply skips.

## Outputs

Expected outputs will evolve, but the intent is:

- `*_anomalies.json`: anomaly regions with labels, confidence, and supporting evidence.
- Optional debug artifacts under `*_debug/`.

Derived artifacts should never be checked into git.

## Development

### Environment setup

```bash
python -m venv .venv
.venv\Scripts\activate        # or source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install pytest  # dev dependency for now
```

### Running tests

```bash
python -m pytest
```

`tests/conftest.py` adds the repo root to `sys.path`, so no editable install is required.

### Repo conventions

- Keep the pipeline modular: discover -> ensure stats -> parse -> detect -> export.
- Shared state travels via dataclasses, not ad-hoc dicts.
- Use `logging` inside package code; reserve `print` for the CLI.
- Add/extend pytest coverage for parsers/detectors alongside code changes.

See **AGENTS.md** for architectural decisions and the current backlog.

## License

This project is licensed under the [MIT License](./LICENSE).
