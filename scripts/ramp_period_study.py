#!/usr/bin/env python
"""Ramp period study: how reassignment cost affects governance outcomes.

Runs the same environment + policy across multiple ramp-period values to
measure how switching cost affects outcomes. Uses shared seeds for paired
comparison.

Usage:
    python scripts/ramp_period_study.py
    python scripts/ramp_period_study.py --seeds 10
    python scripts/ramp_period_study.py --family discovery_heavy

Stage 2, Step 2.2 of the implementation plan
(docs/implementation/2026-03-16 Implementation Plan.md).
"""

from __future__ import annotations

import argparse
import logging
import time
from typing import Any

from primordial_soup.config import (
    ReportingConfig,
    SimulationConfiguration,
    TimeConfig,
    WorkforceConfig,
)
from primordial_soup.policy import BalancedPolicy
from primordial_soup.presets import (
    EnvironmentFamilyName,
    make_balanced_governance_config,
    make_baseline_model_config,
    make_initiative_generator_config,
)
from primordial_soup.runner import run_single_regime
from primordial_soup.types import RampShape
from primordial_soup.workbench import summarize_run_result

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


# ============================================================================
# Configuration
# ============================================================================

# Ramp values to sweep: from near-instant to substantial switching cost.
RAMP_VALUES: tuple[int, ...] = (1, 2, 4, 8, 12)

TICK_HORIZON: int = 313


# ============================================================================
# Helpers
# ============================================================================


def _make_config(
    seed: int,
    ramp_period: int,
    family: EnvironmentFamilyName,
) -> SimulationConfiguration:
    """Build a SimulationConfiguration with a specific ramp period.

    Uses the baseline 8-team workforce with the specified ramp period.
    All other parameters are baseline defaults.

    Args:
        seed: World seed for this run.
        ramp_period: Number of ticks for team ramp-up after reassignment.
        family: Environment family name.

    Returns:
        Complete SimulationConfiguration ready for run_single_regime().
    """
    model = make_baseline_model_config()
    governance = make_balanced_governance_config(
        exec_attention_budget=model.exec_attention_budget,
        default_initial_quality_belief=model.default_initial_quality_belief,
    )

    # Baseline workforce: 8 teams of size 1, but with the specified ramp.
    workforce = WorkforceConfig(
        team_count=8,
        team_size=1,
        ramp_period=ramp_period,
        ramp_multiplier_shape=RampShape.LINEAR,
    )

    return SimulationConfiguration(
        world_seed=seed,
        time=TimeConfig(tick_horizon=TICK_HORIZON, tick_label="week"),
        teams=workforce,
        model=model,
        governance=governance,
        reporting=ReportingConfig(
            record_manifest=True,
            record_per_tick_logs=False,
            record_event_log=True,
        ),
        initiative_generator=make_initiative_generator_config(family),
    )


def _run_ramp_scenario(
    ramp_period: int,
    seeds: list[int],
    family: EnvironmentFamilyName,
) -> list[dict[str, Any]]:
    """Run all seeds for one ramp value and return summary dicts.

    Args:
        ramp_period: Ramp period in ticks.
        seeds: List of world seeds.
        family: Environment family name.

    Returns:
        List of summary dictionaries, one per seed.
    """
    policy = BalancedPolicy()
    summaries = []
    for seed in seeds:
        logger.info("  ramp=%d -- seed %d", ramp_period, seed)
        config = _make_config(seed, ramp_period, family)
        result, _ = run_single_regime(config, policy)
        summary = summarize_run_result(result)
        # Add reassignment count for mechanism analysis.
        summary["reassignment_count"] = result.reassignment_profile.reassignment_event_count
        summary["ramp_labor_cost"] = result.cumulative_ramp_labor
        summaries.append(summary)
    return summaries


def _print_aggregate(label: str, summaries: list[dict[str, Any]]) -> None:
    """Print aggregate metrics for one ramp value."""
    n = len(summaries)
    avg_val = sum(s["cumulative_value"] for s in summaries) / n
    avg_lump = sum(s["lump_value"] for s in summaries) / n
    avg_resid = sum(s["residual_value"] for s in summaries) / n
    avg_idle = sum(s["idle_team_tick_fraction"] for s in summaries) / n
    total_wins = sum(s["major_win_count"] for s in summaries)
    avg_free = sum(s["free_value_per_tick"] for s in summaries) / n
    avg_reassign = sum(s["reassignment_count"] for s in summaries) / n
    avg_ramp_labor = sum(s["ramp_labor_cost"] for s in summaries) / n
    avg_completed = sum(s["initiatives_completed"] for s in summaries) / n
    avg_stopped = sum(s["initiatives_stopped"] for s in summaries) / n

    print(f"  {label}")
    print(f"    Avg value:       {avg_val:8.2f}  (lump {avg_lump:.2f} + resid {avg_resid:.2f})")
    print(f"    Free val/tick:   {avg_free:8.4f}")
    print(f"    Idle %:          {avg_idle:8.2%}")
    print(f"    Major wins:      {total_wins}")
    print(f"    Avg reassign:    {avg_reassign:8.1f}")
    print(f"    Avg ramp labor:  {avg_ramp_labor:8.1f}")
    print(f"    Avg completed:   {avg_completed:8.1f}")
    print(f"    Avg stopped:     {avg_stopped:8.1f}")


# ============================================================================
# Main
# ============================================================================


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ramp period study: reassignment cost effects.",
    )
    parser.add_argument(
        "--seeds",
        type=int,
        default=7,
        help="Number of seeds (default: 7).",
    )
    parser.add_argument(
        "--family",
        type=str,
        default="balanced_incumbent",
        help="Environment family (default: balanced_incumbent).",
    )
    args = parser.parse_args()

    seed_count: int = args.seeds
    family: EnvironmentFamilyName = args.family
    seeds = list(range(42, 42 + seed_count))

    print()
    print("=" * 70)
    print("Ramp Period Study")
    print("=" * 70)
    print(f"  Environment family: {family}")
    print(f"  Ramp values: {RAMP_VALUES}")
    print(f"  Seeds: {seeds}")
    print("  Policy: Balanced (baseline)")
    print(f"  Horizon: {TICK_HORIZON} ticks")
    print()

    t0 = time.time()

    # Run all ramp values.
    all_results: dict[int, list[dict[str, Any]]] = {}
    for ramp in RAMP_VALUES:
        all_results[ramp] = _run_ramp_scenario(ramp, seeds, family)

    # --- Print per-ramp aggregates ---
    print()
    for ramp in RAMP_VALUES:
        _print_aggregate(f"Ramp = {ramp:2d} ticks", all_results[ramp])
        print()

    # --- Delta table vs. baseline (ramp=4, the current default) ---
    baseline_ramp = 4
    if baseline_ramp in all_results:
        print("-" * 70)
        print(f"  Value delta vs. baseline (ramp={baseline_ramp}):")
        print("-" * 70)

        n = len(seeds)
        baseline_avg = sum(s["cumulative_value"] for s in all_results[baseline_ramp]) / n

        for ramp in RAMP_VALUES:
            ramp_avg = sum(s["cumulative_value"] for s in all_results[ramp]) / n
            delta = ramp_avg - baseline_avg
            pct = (delta / baseline_avg * 100) if baseline_avg != 0 else 0
            print(f"    Ramp = {ramp:2d}:  {delta:+8.2f}  ({pct:+.1f}%)")
        print()

    # --- Reassignment count trend ---
    print("-" * 70)
    print("  Reassignment and ramp-labor trends:")
    print("-" * 70)
    n = len(seeds)
    for ramp in RAMP_VALUES:
        avg_reassign = sum(s["reassignment_count"] for s in all_results[ramp]) / n
        avg_ramp_labor = sum(s["ramp_labor_cost"] for s in all_results[ramp]) / n
        print(
            f"    Ramp = {ramp:2d}:  "
            f"reassignments = {avg_reassign:.1f}  "
            f"ramp labor = {avg_ramp_labor:.1f}"
        )
    print()

    # --- Interpretation guidance ---
    print("-" * 70)
    print("  Interpretation:")
    print("-" * 70)
    print()
    print("  If value is roughly flat across ramp values, reassignment cost")
    print("  is not a material driver of outcomes under this policy/environment.")
    print("  If value drops sharply at higher ramp values, switching cost is")
    print("  penalizing the policy's reallocation behavior — relevant to RQ6.")
    print("  If reassignment count drops at high ramp, the policy may be")
    print("  implicitly becoming more patient (fewer stops) because the cost")
    print("  of switching is too high.")
    print()

    elapsed = time.time() - t0
    print(f"Elapsed: {elapsed:.0f}s")
    print()


if __name__ == "__main__":
    main()
