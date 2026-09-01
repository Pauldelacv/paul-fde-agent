"""``pfa`` — the command-line entry point.

Built on argparse from the standard library. See docs/adr/0004-cli-framework.md
for why no CLI dependency was taken.
"""

from __future__ import annotations

import argparse
import json
import sys

import yaml

from . import __version__
from .config import load_config
from .doctor import FAIL, PASS, SKIP, WARN, run_all, to_json, worst_status
from .errors import PfaError
from .hermes import AUTONOMY_LEVELS, DEFAULT_AUTONOMY, render_config, write_config
from .observability import log_dir
from .router import route
from .runner import run_task

_COLORS = {PASS: "\033[32m", WARN: "\033[33m", FAIL: "\033[31m", SKIP: "\033[90m"}
_RESET = "\033[0m"


def _paint(status: str) -> str:
    if not sys.stdout.isatty():
        return status
    return f"{_COLORS.get(status, '')}{status}{_RESET}"


# --- commands --------------------------------------------------------------


def cmd_route(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    decision = route(args.text, config, task=args.task)
    if args.json:
        print(
            json.dumps(
                {
                    "task": decision.task,
                    "basis": decision.basis,
                    "matched_keyword": decision.matched_keyword,
                    "provider": decision.provider.name,
                    "model": decision.model,
                    "model_ref": decision.model_ref,
                    "local": decision.provider.is_local,
                },
                indent=2,
            )
        )
    else:
        print(decision.explain())
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    result = run_task(
        args.text,
        config,
        task=args.task,
        skills=args.skill,
        dry_run=args.dry_run,
        timeout=args.timeout,
    )

    if args.json:
        print(json.dumps(result.record.to_dict(), indent=2))
        return 0 if result.ok else 1

    if not args.quiet:
        print(f"[pfa] {result.decision.explain()}", file=sys.stderr)
    if args.dry_run:
        print("[pfa] dry run — no model was invoked.", file=sys.stderr)
        return 0

    if result.stdout:
        print(result.stdout, end="" if result.stdout.endswith("\n") else "\n")
    if not result.ok:
        print(f"[pfa] run failed: {result.record.error}", file=sys.stderr)
        return result.record.exit_code or 1
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    checks = run_all(args.config)
    if args.json:
        print(to_json(checks))
    else:
        width = max(len(c.name) for c in checks)
        print("Paul FDE Agent — environment check\n")
        for check in checks:
            print(f"  [{_paint(check.status):>4}] {check.name:<{width}}  {check.detail}")
            if check.remedy:
                print(f"         {'':<{width}}  -> {check.remedy}")
        print()
    status = worst_status(checks)
    if status == FAIL:
        print("Result: FAIL — resolve the items above before running tasks.", file=sys.stderr)
        return 2
    if status == WARN:
        print("Result: WARN — usable, but review the warnings above.", file=sys.stderr)
        return 1
    print("Result: PASS")
    return 0


def cmd_config(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    print(f"policy: {config.source_path}  (version {config.version})\n")
    print("providers:")
    for name, provider in sorted(config.providers.items()):
        tier = "local" if provider.is_local else "cloud"
        print(f"  {name:<8} {tier:<6} {provider.base_url}")
        print(
            f"           default model: {provider.default_model}   key env: ${provider.api_key_env}"
        )
    print("\nroutes:")
    for task, selected in config.routes.items():
        provider = config.provider_for(selected.provider)
        model = selected.model or provider.default_model
        marker = " (default)" if task == config.default_task else ""
        print(f"  {task:<14} -> {selected.provider}/{model}{marker}")
        if selected.description:
            print(f"  {'':<14}    {selected.description}")
    print(f"\nclassification rules: {len(config.rules)} (first match wins)")
    print(f"log directory: {log_dir()}")
    return 0


def cmd_hermes_config(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    if args.write:
        path = write_config(config, autonomy=args.autonomy, terminal=args.terminal)
        print(f"Wrote {path} (autonomy: {args.autonomy}, terminal: {args.terminal})")
        print(
            "Secrets are referenced as ${VAR}; put their values in "
            f"{path.parent / '.env'} with mode 600."
        )
        return 0
    document = render_config(config, autonomy=args.autonomy, terminal=args.terminal)
    print(yaml.safe_dump(document, sort_keys=False, default_flow_style=False))
    return 0


def cmd_autonomy(args: argparse.Namespace) -> int:
    print("Autonomy levels (enforced by the Hermes approval system):\n")
    for level in sorted(AUTONOMY_LEVELS.values(), key=lambda item: item.number):
        default = "  <- default" if level.name == DEFAULT_AUTONOMY else ""
        print(f"  LEVEL {level.number}  {level.name.upper():<9}{default}")
        print(f"           {level.summary}")
        print(
            f"           approvals.mode={level.approvals_mode}  "
            f"unattended={level.unattended_mode}  cron={level.cron_mode}\n"
        )
    return 0


def cmd_logs(args: argparse.Namespace) -> int:
    directory = log_dir()
    files = sorted(directory.glob("runs-*.jsonl")) if directory.is_dir() else []
    if not files:
        print(f"No run logs in {directory}.")
        return 0

    records = []
    for path in files[-args.days :]:
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

    records = records[-args.limit :]
    if args.json:
        print(json.dumps(records, indent=2))
        return 0

    print(f"{'TIME':<20} {'TASK':<14} {'MODEL':<34} {'MS':>7}  STATUS")
    for record in records:
        print(
            f"{record.get('timestamp', '')[:19]:<20} "
            f"{record.get('task', ''):<14} "
            f"{record.get('provider', '')}/{record.get('model', ''):<26} "
            f"{record.get('duration_ms', 0):>7}  {record.get('status', '')}"
        )
    total = sum(r.get("estimated_cost_usd") or 0.0 for r in records)
    print(f"\n{len(records)} runs shown. Estimated cloud cost: ${total:.4f}")
    return 0


# --- parser ----------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pfa",
        description="Paul FDE Agent — route Forward Deployed Engineering tasks "
        "to the right model and run them on the Hermes runtime.",
    )
    parser.add_argument("--version", action="version", version=f"pfa {__version__}")
    parser.add_argument(
        "--config",
        metavar="PATH",
        help="Routing policy path (default: config/routing.yaml, or $PFA_CONFIG).",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    run = subparsers.add_parser("run", help="Route a task and execute it via Hermes.")
    run.add_argument("text", help="The task, in plain language.")
    run.add_argument("--task", help="Force a task category, bypassing classification.")
    run.add_argument(
        "--skill", action="append", default=[], help="Preload a Hermes skill (repeatable)."
    )
    run.add_argument("--dry-run", action="store_true", help="Route and log, but invoke no model.")
    run.add_argument("--timeout", type=int, default=None, help="Seconds before aborting.")
    run.add_argument("--json", action="store_true", help="Emit the run record as JSON.")
    run.add_argument("--quiet", action="store_true", help="Suppress the routing banner.")
    run.set_defaults(func=cmd_run)

    route_cmd = subparsers.add_parser(
        "route", help="Show the routing decision for a task without running it."
    )
    route_cmd.add_argument("text")
    route_cmd.add_argument("--task")
    route_cmd.add_argument("--json", action="store_true")
    route_cmd.set_defaults(func=cmd_route)

    doctor = subparsers.add_parser("doctor", help="Check the environment end to end.")
    doctor.add_argument("--json", action="store_true")
    doctor.set_defaults(func=cmd_doctor)

    config_cmd = subparsers.add_parser("config", help="Show the resolved routing policy.")
    config_cmd.set_defaults(func=cmd_config)

    hermes_cmd = subparsers.add_parser(
        "hermes-config", help="Render the Hermes config.yaml from the routing policy."
    )
    hermes_cmd.add_argument(
        "--write", action="store_true", help="Write to $HERMES_HOME/config.yaml instead of stdout."
    )
    hermes_cmd.add_argument("--autonomy", choices=sorted(AUTONOMY_LEVELS), default=DEFAULT_AUTONOMY)
    hermes_cmd.add_argument(
        "--terminal",
        default="local",
        choices=["local", "docker", "ssh", "modal", "daytona", "singularity"],
        help="Hermes terminal backend (the command isolation boundary).",
    )
    hermes_cmd.set_defaults(func=cmd_hermes_config)

    autonomy = subparsers.add_parser("autonomy", help="Describe the four autonomy levels.")
    autonomy.set_defaults(func=cmd_autonomy)

    logs = subparsers.add_parser("logs", help="Show recent structured run records.")
    logs.add_argument("--limit", type=int, default=20)
    logs.add_argument("--days", type=int, default=7, help="How many daily log files to read.")
    logs.add_argument("--json", action="store_true")
    logs.set_defaults(func=cmd_logs)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except PfaError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("\ninterrupted", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
