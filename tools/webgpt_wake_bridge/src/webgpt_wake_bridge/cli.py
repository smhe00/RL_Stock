from __future__ import annotations

import argparse
from pathlib import Path

from . import __version__
from .bridge import RemoteMarkerWatcher, configure_logging
from .browser import CdpFetchSender, NoopLifecycleDiagnostic
from .config import BridgeConfig, load_config
from .errors import BridgeError
from .finalize import finalize_handoff
from .markers import BRIDGE_OWNED_MARKERS, MARKER_ORDER, MARKER_OWNERS
from .transport_git import GitTransport


def _runtime(config: BridgeConfig) -> tuple[RemoteMarkerWatcher, object]:
    logger = configure_logging(config)
    sender = CdpFetchSender(
        config.cdp_endpoint,
        config.target_conversation_url or "",
        config.chrome_profile_path,
        playwright_module=config.playwright_module,
    )
    transport = GitTransport(
        config.repo_root,
        config.runtime_dir,
        config.marker_root,
        config.remote,
        config.branch,
    )
    return RemoteMarkerWatcher(config, transport, sender, logger), logger


def _check(config: BridgeConfig) -> None:
    if set(MARKER_ORDER) != set(MARKER_OWNERS):
        raise BridgeError("marker order/owner schema mismatch")
    if BRIDGE_OWNED_MARKERS != {"trigger_fetch_sent.json"}:
        raise BridgeError("bridge ownership schema changed unexpectedly")
    if not config.cdp_endpoint.lower().startswith("http://127.0.0.1"):
        raise BridgeError("CDP endpoint must be localhost only")
    print("webgpt-bridge check: PASS (no browser action, no git mutation)")


def main() -> int:
    parser = argparse.ArgumentParser(prog="webgpt-bridge")
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)

    for name in ("check", "once", "daemon", "noop"):
        p = sub.add_parser(name)
        p.add_argument("--config", type=Path, required=True)
    sub.choices["noop"].add_argument("--hold-seconds", type=float, default=30.0)

    p_retry = sub.add_parser("retry")
    p_retry.add_argument("--config", type=Path, required=True)
    p_retry.add_argument("--handoff", required=True)

    p_reconcile = sub.add_parser("reconcile")
    p_reconcile.add_argument("--config", type=Path, required=True)
    p_reconcile.add_argument("--handoff", required=True)

    p_finalize = sub.add_parser("finalize")
    p_finalize.add_argument("--config", type=Path, required=True)
    p_finalize.add_argument("--handoff", required=True)
    p_finalize.add_argument("--code-commit", required=True)
    p_finalize.add_argument("--expect-head", default="")

    args = parser.parse_args()
    try:
        require_url = args.command in {"once", "daemon", "noop"}
        config = load_config(args.config.resolve(), require_url=require_url)
        if args.command == "check":
            _check(config)
            return 0
        if args.command == "finalize":
            path = finalize_handoff(config, args.handoff, args.code_commit, args.expect_head)
            print(f"doorbell created: {path}")
            print("commit and push this marker as the FINAL push of the review-requesting handoff")
            return 0
        watcher, _logger = _runtime(config)
        if args.command == "once":
            outcomes = watcher.scan_once()
            print("\n".join(outcomes) if outcomes else "no eligible handoff")
            return 0
        if args.command == "daemon":
            watcher.run_forever()
            return 0
        if args.command == "retry":
            cleared = watcher.clear_failure(args.handoff)
            print(f"retry failure cleared: {cleared}")
            return 0 if cleared else 1
        if args.command == "reconcile":
            result = watcher.reconcile_missing_trigger(args.handoff)
            print(f"reconcile: {result}")
            return 0 if result in {"RECONCILE_PUBLISHED", "ALREADY_PUBLISHED"} else 1
        if args.command == "noop":
            result = NoopLifecycleDiagnostic(
                config.cdp_endpoint,
                config.target_conversation_url or "",
                args.hold_seconds,
                config.playwright_module,
            ).run()
            print(f"noop lifecycle: PASS target={result['after']['url']}")
            return 0
    except BridgeError as exc:
        print(f"webgpt-bridge error: {exc}")
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
