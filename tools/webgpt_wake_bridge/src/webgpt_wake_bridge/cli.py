from __future__ import annotations

import argparse
from pathlib import Path

from . import __version__
from .bootstrap import write_initial_config
from .bridge import RemoteMarkerWatcher, configure_logging
from .browser import CdpFetchSender, NoopLifecycleDiagnostic
from .config import BridgeConfig, load_config, validate_cdp_endpoint
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
    if MARKER_ORDER != list(MARKER_OWNERS):
        raise BridgeError("marker order/owner schema mismatch")
    if BRIDGE_OWNED_MARKERS != {"trigger_fetch_sent.json"}:
        raise BridgeError("bridge ownership schema changed unexpectedly")
    validate_cdp_endpoint(config.cdp_endpoint)
    print("webgpt-bridge check: PASS (no browser action, no git mutation)")
    print(f"  repo: {config.repo_root}")
    print(f"  marker_root: {config.marker_root.as_posix()}")
    print(f"  runtime: {config.runtime_dir}")


def main() -> int:
    parser = argparse.ArgumentParser(prog="webgpt-bridge")
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="create a local project config outside the consumer repo by default")
    p_init.add_argument("--repo", type=Path, required=True)
    p_init.add_argument("--config-path", type=Path)
    p_init.add_argument("--runtime-dir", type=Path)
    p_init.add_argument("--remote", default="origin")
    p_init.add_argument("--branch", default="main")
    p_init.add_argument("--marker-root", default="docs/web_bridge")

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
        if args.command == "init":
            path = write_initial_config(
                args.repo,
                config_path=args.config_path,
                runtime_dir=args.runtime_dir,
                remote=args.remote,
                branch=args.branch,
                marker_root=args.marker_root,
            )
            print(f"local config created: {path}")
            print("NEXT: edit target_conversation_url, keep the config untracked, then run `webgpt-bridge check`.")
            return 0

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
            print(f"explicit retry cleared uncertain/failed attempt: {cleared}")
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
