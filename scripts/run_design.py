#!/usr/bin/env python
"""Run a simulation from a YAML run design file.

Usage
-----
    python scripts/run_design.py path/to/my_run.yaml
    python scripts/run_design.py path/to/my_run.yaml --dry-run

Options
-------
    --dry-run       Validate and print the resolved design summary, then exit
                    without running. Use this to check your config before
                    committing to a potentially long run.

    --no-confirm    Skip the interactive confirmation prompt. Useful in
                    non-interactive environments (CI, batch jobs).

    --output-dir PATH
                    Directory for result output files. Default: results/

Examples
--------
    # Check your config first:
    python scripts/run_design.py templates/run_design_template.yaml --dry-run

    # Run the canonical balanced baseline:
    python scripts/run_design.py templates/presets/balanced_incumbent_balanced.yaml

    # Run without confirmation (e.g. in a batch script):
    python scripts/run_design.py my_run.yaml --no-confirm --output-dir /data/runs

YAML file format
----------------
    See templates/run_design_template.yaml for a fully documented template.
    See templates/presets/ for nine ready-to-use preset combinations.
"""

from __future__ import annotations

import argparse
import dataclasses
import logging
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("run_design")


# ---------------------------------------------------------------------------
# YAML loading
# ---------------------------------------------------------------------------


def _load_yaml(path: Path) -> dict:
    try:
        import yaml  # type: ignore[import]
    except ImportError:
        logger.error("PyYAML is not installed. Install it with:  pip install pyyaml")
        sys.exit(1)
    with path.open() as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        logger.error("YAML file did not produce a mapping at the top level: %s", path)
        sys.exit(1)
    return data


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run a Primordial Soup simulation from a YAML run design file.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("yaml_file", type=Path, help="Path to the run design YAML file.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and print the resolved summary, then exit without running.",
    )
    parser.add_argument(
        "--no-confirm",
        action="store_true",
        help="Skip the interactive confirmation prompt.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("results"),
        metavar="PATH",
        help="Directory for result output files (default: results/).",
    )
    args = parser.parse_args()

    yaml_path: Path = args.yaml_file.resolve()
    if not yaml_path.exists():
        logger.error("File not found: %s", yaml_path)
        sys.exit(1)

    # ── Parse ─────────────────────────────────────────────────────────────
    from primordial_soup.workbench import (
        RunDesignSpec,
        build_experiment_spec_from_design,
        make_policy,
        resolve_run_design,
        summarize_run_result,
        validate_run_design,
    )

    logger.info("Loading run design from %s", yaml_path)
    data = _load_yaml(yaml_path)

    try:
        spec = RunDesignSpec.from_dict(data)
    except (KeyError, TypeError, ValueError) as exc:
        logger.error("Failed to parse YAML file: %s", exc)
        sys.exit(1)

    # ── Validate ──────────────────────────────────────────────────────────
    logger.info("Validating run design '%s'...", spec.name)
    try:
        validate_run_design(spec)
    except ValueError as exc:
        logger.error("Validation failed:\n%s", exc)
        sys.exit(1)
    logger.info("Validation passed.")

    # ── Resolve and inspect ────────────────────────────────────────────────
    resolved = resolve_run_design(spec)
    summary_text = resolved.summary()
    print()
    # Handle Windows consoles that cannot render Unicode box-drawing characters.
    try:
        print(summary_text)
    except UnicodeEncodeError:
        print(summary_text.encode("ascii", errors="replace").decode("ascii"))
    print()

    if args.dry_run:
        logger.info("--dry-run: exiting without running.")
        sys.exit(0)

    # ── Confirm ───────────────────────────────────────────────────────────
    n_runs = len(resolved.simulation_configs)
    if not args.no_confirm:
        try:
            answer = (
                input(f"Run {n_runs} simulation{'s' if n_runs != 1 else ''}? [y/N] ")
                .strip()
                .lower()
            )
        except (EOFError, KeyboardInterrupt):
            print()
            logger.info("Aborted.")
            sys.exit(0)
        if answer not in ("y", "yes"):
            logger.info("Aborted.")
            sys.exit(0)

    # ── Execute ───────────────────────────────────────────────────────────
    from primordial_soup.config import ReportingConfig
    from primordial_soup.run_bundle import create_run_bundle
    from primordial_soup.runner import run_single_regime

    logger.info(
        "Starting %d run%s for design '%s'...",
        n_runs,
        "s" if n_runs != 1 else "",
        spec.name,
    )

    output_dir: Path = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    # Enable full logging so trajectory figures can be generated from the
    # run bundle. The YAML design may not have requested per-tick logs, but
    # the bundle format needs them for post-hoc analysis and plotting.
    full_reporting = ReportingConfig(
        record_manifest=True,
        record_per_tick_logs=True,
        record_event_log=True,
    )

    summaries: list[dict] = []
    seed_results: list[tuple] = []  # (RunResult, WorldState) pairs

    for i, sim_config in enumerate(resolved.simulation_configs):
        logger.info(
            "  Run %d/%d — seed=%d, policy=%s",
            i + 1,
            n_runs,
            sim_config.world_seed,
            resolved.governance.policy_id,
        )

        # Replace reporting config to enable per-tick logging, regardless
        # of what the original config specified. This ensures the run
        # bundle has enough data for trajectory figures.
        sim_config_with_logging = dataclasses.replace(
            sim_config,
            reporting=full_reporting,
        )

        policy = make_policy(resolved.governance)
        run_result, final_state = run_single_regime(sim_config_with_logging, policy)

        seed_results.append((run_result, final_state))
        summary = summarize_run_result(run_result)
        summaries.append(summary)
        logger.info("  Run %d/%d complete.", i + 1, n_runs)

    # Build ExperimentSpec and create run bundle. The bridge function maps
    # the YAML-layer ResolvedRunDesign into the reporting-layer
    # ExperimentSpec, and create_run_bundle writes the timestamped bundle
    # directory with Parquet tables, figures, and provenance metadata.
    experiment_spec = build_experiment_spec_from_design(
        resolved,
        tuple(seed_results),
    )
    bundle_path = create_run_bundle(experiment_spec, output_dir)

    # ── Print results (console feedback) ──────────────────────────────────
    # The bundle contains all data, but the console summary is still useful
    # for interactive feedback during development and calibration runs.
    print()
    print("=" * 60)
    print(f"Complete: {n_runs} run{'s' if n_runs != 1 else ''} for '{spec.name}'")
    print("=" * 60)
    print()

    # Value across all runs.
    values = [s["cumulative_value"] for s in summaries]
    print("Value across all runs:")
    print(f"  Min:    {min(values):.2f}")
    print(f"  Max:    {max(values):.2f}")
    print(f"  Mean:   {sum(values) / len(values):.2f}")
    print()

    # Metric guide.
    print("-" * 60)
    print("Metric guide:")
    print("  Cumulative value      Total value realized during the run")
    print("  Idle team-tick %      Fraction of team-ticks with no assignment")
    print("  Major wins            Right-tail breakthroughs discovered (count")
    print("                        only; value is not estimated)")
    print("  Free value/tick       Value earned each tick from completed")
    print("                        flywheel and quick-win residual streams,")
    print("                        without deploying any additional labor")
    print("  Peak productivity     Highest org-wide productivity multiplier")
    print("                        reached (from enabler completions); 1.0")
    print("                        is baseline")
    print("  Productivity at end   Productivity multiplier at the final tick;")
    print("                        lower than peak because capability decays")
    print("                        between enabler completions")
    print("  Quality est. error    How accurately governance estimated true")
    print("                        initiative quality (lower is better)")
    print("-" * 60)
    print()

    # Aggregate summary.
    n = len(summaries)
    avg_value = sum(s["cumulative_value"] for s in summaries) / n
    avg_idle = sum(s["idle_team_tick_fraction"] for s in summaries) / n
    total_wins = sum(s["major_win_count"] for s in summaries)
    exhaustions = [s["pool_exhaustion_tick"] for s in summaries]
    avg_free = sum(s["free_value_per_tick"] for s in summaries) / n
    avg_peak = sum(s["peak_productivity"] for s in summaries) / n
    avg_end = sum(s["productivity_at_end"] for s in summaries) / n
    avg_err = sum(s["quality_est_error"] for s in summaries) / n

    preset_label = spec.policy.preset.replace("_", " ").title()
    print(f"{preset_label} ({spec.environment.family}):")
    print(f"  Avg cumulative value:  {avg_value:.2f}")
    print(f"  Avg idle team-tick %:  {avg_idle:.2%}")
    print(f"  Total major wins:      {total_wins}")
    print(f"  Pool exhaustion:       {exhaustions}")
    print(f"  Avg free value/tick:   {avg_free:.4f}")
    print(f"  Avg peak productivity: {avg_peak:.4f}")
    print(f"  Avg productivity@end:  {avg_end:.4f}")
    print(f"  Avg quality est. err:  {avg_err:.4f}")
    print()

    print(f"Run bundle written to {bundle_path}")


if __name__ == "__main__":
    main()
