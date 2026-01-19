## Purpose
This file keeps VHS Detective work aligned as we expand a one-file prototype into a modular toolchain. Treat it as the project's ground truth for architecture, coding standards, and task ownership.

## Architectural North Star
- **Package-first**: move logic from `analyze_tape.py` into a `vhs_detective/` package with submodules for CLI, data models, ingest, parsers, detection, evidence fusion, and outputs.
- **Explicit pipeline**: each stage (discover -> ensure assets -> parse -> detect -> export) should be its own module with typed inputs/outputs.
- **Configuration surface**: centralize CLI parsing + config defaults (env, `.toml`, CLI flags) so stages can stay pure.
- **Extensibility hooks**: design detection/export layers as registries so new heuristics or sinks can be added without editing core flow.
- **Testing focus areas**: parser fixtures, detection heuristics, and regression harnesses for FFmpeg command construction.

## Target Layout
```
vhs_detective/
    __init__.py
    cli/app.py                # argparse + config loading
    config/schema.py          # dataclasses for CLI/config inputs
    fs/discovery.py           # locate source + derived artifacts
    ffmpeg/commands.py        # helpers for invoking ffmpeg/ffprobe
    stats/video.py            # signalstats generation + parsing
    stats/audio.py            # astats generation + parsing
    ctl/parser.py             # CTL CSV ingestion + normalization
    detect/                    # heuristic modules
        baseline.py
        ctl.py
    report/anomalies.py       # write JSON + future exporters
    models/core.py            # shared dataclasses (FrameMetrics, Region, Evidence, etc.)
tests/
    unit/...                  # pytest preferred
    fixtures/...              # tiny textual fixtures, not binaries
scripts/
    demo_pipeline.py          # dogfood end-to-end orchestration
```

## Agent Roles & Expectations
- **Core Maintainer**: keeps architecture cohesive. Owns package layout decisions, dependency management, and CI rules.
- **Capture Integrator**: focuses on ingest paths-file discovery, FFmpeg command generation, CTL parsing, and sample data fixtures.
- **Signal Analyst**: owns metrics parsing + anomaly heuristics. Supplies explainable rules, confidence scoring, and documentation.
- **UX/Exporter**: designs anomaly JSON schema, debug artifacts, and the eventual review UI contract.

Agents coordinate through small RFC-style PR descriptions referencing this file. Any structural deviation needs Core Maintainer buy-in.

## Coding Standards
- Python 3.11+, strict type hints, `mypy` clean (enable `--strict` once feasible).
- Shared dataclasses live in `models/`; avoid ad-hoc dicts crossing module boundaries.
- `logging` over `print` in package code; CLI handles pretty output.
- Minimum dependencies; prefer stdlib and `numpy`/`pydantic` only if justified via benchmarks or ergonomics.
- Commands shell out via helper functions (`ffmpeg.run_signalstats(...)`) to keep subprocess usage centralized and mockable.
- Provide docstrings for modules + public functions; add short comments only when logic isn't obvious.

## Workflow Rules
1. Start by updating/consulting `AGENTS.md` whenever you begin a new stream of work.
2. Create or update unit tests alongside code changes; never ship parser/detector changes without fixtures.
3. Keep `analyze_tape.py` as the thin CLI wrapper until the full package exists; gradually migrate features behind feature flags.
4. Derived artifacts (stats, debug exports) stay out of git-respect `.gitignore`.
5. Prefer small, incremental PRs that take one stage closer to the target layout.

## Near-Term Backlog
1. Define anomaly data models (`models/anomaly.py`) + JSON writer that replaces placeholders in `report`.
2. Harden CTL ingestion (column mapping, validation, drift fitting) and expose detector-ready helpers.
3. Implement baseline video/audio detection heuristics with pytest coverage + fixtures.
4. Introduce configuration loading (env vars / optional TOML) feeding `AnalysisConfig`.
5. Draft CONTRIBUTING.md and set up CI (lint + pytest on Windows + Linux).
