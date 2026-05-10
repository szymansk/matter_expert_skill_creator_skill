"""CLI entry point for the docs-to-skill builder."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from builder.integration.cost_estimator import estimate_build_cost
from builder.phases import Phase


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="docs-to-skill",
        description="Build an expert skill from a directory of documents.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    # estimate
    est = sub.add_parser("estimate", help="Print pre-build cost estimate.")
    est.add_argument("--input", type=Path, required=True)
    est.add_argument("--url", action="append", default=[],
                     help="URL to include (may be passed multiple times)")

    # build
    build = sub.add_parser("build", help="Run the full builder pipeline.")
    build.add_argument("--input", type=Path, required=True)
    build.add_argument("--url", action="append", default=[])
    build.add_argument("--run-dir", type=Path, required=True)
    build.add_argument("--plugin-root", type=Path, required=True)
    build.add_argument("--name", required=True)
    build.add_argument("--version", default="0.1.0")
    build.add_argument("--description", default="Generated expert skill.")
    build.add_argument("--author", default="docs-to-skill")
    build.add_argument("--replay-from", choices=[p.value for p in Phase],
                       default=None)
    build.add_argument("--yes", action="store_true",
                       help="Skip cost confirmation prompt.")

    args = parser.parse_args(argv)

    if args.cmd == "estimate":
        estimate = estimate_build_cost(
            input_dir=args.input, url_list=list(args.url),
        )
        print(estimate.format())
        return 0

    if args.cmd == "build":
        # Show cost estimate and confirm unless --yes.
        estimate = estimate_build_cost(
            input_dir=args.input, url_list=list(args.url),
        )
        print(estimate.format())
        if not args.yes:
            reply = input("\nProceed? [Y/n] ").strip().lower()
            if reply and reply not in ("y", "yes"):
                print("Aborted.")
                return 1

        run_id = args.run_dir.name
        from builder.integration.anthropic_agent import AnthropicAgent
        from builder.integration.builder import (
            BuilderOrchestrator, BuildConfig,
        )
        from builder.integration.http_fetcher import UrllibFetcher

        config = BuildConfig(
            run_id=run_id,
            input_dir=args.input,
            url_list=list(args.url),
            run_dir=args.run_dir,
            plugin_root=args.plugin_root,
            plugin_name=args.name,
            plugin_version=args.version,
            plugin_description=args.description,
            author=args.author,
            replay_from=Phase(args.replay_from) if args.replay_from else None,
        )
        builder = BuilderOrchestrator(
            agent=AnthropicAgent(), fetcher=UrllibFetcher(),
        )
        pipeline = builder.build(config=config)
        print(f"\nDone. Plugin written to {args.plugin_root}.")
        actual = pipeline.state.cost_tracker.get("actual_so_far_usd", 0.0)
        print(f"Actual cost: ${actual:.2f}")
        return 0

    return 2


if __name__ == "__main__":
    sys.exit(main())
