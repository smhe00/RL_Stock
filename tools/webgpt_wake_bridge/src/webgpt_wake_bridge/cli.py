"""CLI entry point for the standalone package staging tree.

Behavioral commands will be enabled as accepted V1 modules are extracted. Until
then this command is intentionally non-operational so the embedded accepted V1
cannot be shadowed accidentally.
"""
from __future__ import annotations

import argparse

from . import __version__


def main() -> int:
    parser = argparse.ArgumentParser(prog="webgpt-bridge")
    parser.add_argument("--version", action="store_true")
    args = parser.parse_args()
    if args.version:
        print(__version__)
        return 0
    parser.error(
        "standalone package is STAGING; use the accepted embedded V1 until extraction acceptance completes"
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
