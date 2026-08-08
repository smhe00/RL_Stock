"""Wait for the matching ChatGPT reviewer handoff on origin/main.

Usage:
    python scripts/wait_for_reviewer.py G4_EVAL_FIX_001

The script uses `git fetch` only while waiting, so it does not modify the local
working tree. When a terminal reviewer state for the expected handoff appears,
it exits and Claude should run `git pull --ff-only`, then read the referenced
reviewer response.
"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

INTERVAL_SECONDS = 60
TERMINAL_STATES = {"REVIEW_COMPLETE", "REVISIONS_REQUIRED", "BLOCKED"}
REMOTE_STATE_PATH = "docs/reviewer_state/CHATGPT_REVIEW.yaml"


def run(*args: str) -> str:
    return subprocess.check_output(args, text=True, stderr=subprocess.STDOUT).strip()


def parse_simple_yaml(text: str) -> dict[str, str]:
    """Parse only top-level scalar keys needed by this helper."""
    out: dict[str, str] = {}
    for raw in text.splitlines():
        if not raw or raw.startswith(" ") or raw.lstrip().startswith("#") or ":" not in raw:
            continue
        key, value = raw.split(":", 1)
        out[key.strip()] = value.strip().strip('"\'')
    return out


def read_remote_state() -> dict[str, str] | None:
    try:
        text = run("git", "show", f"origin/main:{REMOTE_STATE_PATH}")
    except subprocess.CalledProcessError:
        return None
    return parse_simple_yaml(text)


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: python scripts/wait_for_reviewer.py <handoff_id>")
        return 2

    expected = sys.argv[1]
    print(f"Waiting for reviewer handoff: {expected}")
    print(f"Polling origin/main every {INTERVAL_SECONDS}s via git fetch.")

    while True:
        try:
            run("git", "fetch", "origin", "main")
            state = read_remote_state()
            now = time.strftime("%Y-%m-%d %H:%M:%S")
            if state is None:
                print(now, "reviewer state not found")
            else:
                got_id = state.get("handoff_id", "")
                got_state = state.get("state", "")
                print(now, f"handoff_id={got_id} state={got_state}")
                if got_id == expected and got_state in TERMINAL_STATES:
                    print("Reviewer handoff is ready.")
                    print("Next: ensure worktree clean, then `git pull --ff-only`.")
                    return 0
        except KeyboardInterrupt:
            print("Interrupted.")
            return 130
        except Exception as exc:  # noqa: BLE001
            print(time.strftime("%Y-%m-%d %H:%M:%S"), "poll error:", exc)

        time.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    raise SystemExit(main())
