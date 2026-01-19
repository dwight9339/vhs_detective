"""Legacy entry point that now delegates into the packaged CLI."""
from __future__ import annotations

from vhs_detective.cli.app import run_cli


def main() -> int:
    return run_cli()


if __name__ == "__main__":
    raise SystemExit(main())
