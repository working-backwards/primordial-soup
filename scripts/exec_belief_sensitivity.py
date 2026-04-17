#!/usr/bin/env python
"""Execution-belief initialization bias sensitivity analysis.

Tests whether the default initial_execution_belief of 1.0 (which produces
systematic downward drift for on-plan initiatives) materially affects
outcomes. Runs the baseline with three different initial values and
breaks down results by initiative family.

Usage:
    python scripts/exec_belief_sensitivity.py
    python scripts/exec_belief_sensitivity.py --seeds 10
    python scripts/exec_belief_sensitivity.py --family discovery_heavy

Three possible outcomes:
    (a) Bias is negligible across all families and RQs.
    (b) Bias is material across the board.
    (c) Bias is material for some families but not others.

Stage 2, Step 2.3 of the implementation plan
(docs/implementation/2026-03-16 Implementation Plan.md).
"""

from __future__ import annotations

import argparse
import logging
import time
from dataclasses import replace
from typing import Any

from primordial_soup.config import (
    InitiativeGeneratorConfig,
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

# Three initial execution belief values to test.
EXEC_BELIEF_VALUES: tuple[float, ...] = (1.0, 0.9, 0.8)

TICK_HORIZON: int = 313


# ============================================================================
# Helpers
# ============================================================================


def _make_generator(
    family: EnvironmentFamilyName,
    initial_exec_belief: float,
) -> InitiativeGeneratorConfig:
    """Build initiative generator with a specific initial_execution_belief.

    Modifies all type specs to use the specified initial value.

    Args:
        family: Environment family name.
        initial_exec_belief: Initial execution belief to set on all type specs.

    Returns:
        InitiativeGeneratorConfig with modified initial_execution_belief.
    """
    base_gen = make_initiative_generator_config(family)

    modified_specs = tuple(
        replace(spec, initial_execution_belief=initial_exec_belief) for spec in base_gen.type_specs
    )
    return InitiativeGeneratorConfig(type_specs=modified_specs)


def _make_config(
    seed: int,
    initial_exec_belief: float,
    family: EnvironmentFamilyName,
) -> SimulationConfiguration:
    """Build a SimulationConfiguration with a specific initial execution belief.

    Args:
        seed: World seed.
        initial_exec_belief: Initial execution belief for all initiatives.
        family: Environment family name.

    Returns:
        Complete SimulationConfiguration.
    """
    model = make_baseline_model_config()
    governance = make_balanced_governance_config(
        exec_attention_budget=model.exec_attention_budget,
        default_initial_quality_belief=model.default_initial_quality_belief,
    )

    return SimulationConfiguration(
        world_seed=seed,
        time=TimeConfig(tick_horizon=TICK_HORIZON, tick_label="week"),
        teams=WorkforceConfig(
            team_count=8,
            team_size=1,
            ramp_period=4,
            ramp_multiplier_shape=RampShape.LINEAR,
        ),
        model=model,
        governance=governance,
        reporting=ReportingConfig(
            record_manifest=True,
            record_per_tick_logs=False,
            record_event_log=True,
        ),
        initiative_generator=_make_generator(family, initial_exec_belief),
    )


def _run_scenario(
    initial_exec_belief: float,
    seeds: list[int],
    family: EnvironmentFamilyName,
) -> list[dict[str, Any]]:
    """Run all seeds for one exec-belief value and return summaries.

    Args:
        initial_exec_belief: Initial execution belief value.
        seeds: List of world seeds.
        family: Environment family name.

    Returns:
        List of summary dictionaries, one per seed.
    """
    policy = BalancedPolicy()
    summaries = []
    for seed in seeds:
        logger.info("  exec_belief=%.1f -- seed %d", initial_exec_belief, seed)
        config = _make_config(seed, initial_exec_belief, family)
        result, _ = run_single_regime(config, policy)
        summary = summarize_run_result(result)
        summaries.append(summary)
    return summaries


def _print_aggregate(label: str, summaries: list[dict[str, Any]]) -> None:
    """Print aggregate metrics for one exec-belief value."""
    n = len(summaries)
    avg_val = sum(s["cumulative_value"] for s in summaries) / n
    avg_lump = sum(s["lump_value"] for s in summaries) / n
    avg_resid = sum(s["residual_value"] for s in summaries) / n
    avg_idle = sum(s["idle_team_tick_fraction"] for s in summaries) / n
    total_wins = sum(s["major_win_count"] for s in summaries)
    avg_completed = sum(s["initiatives_completed"] for s in summaries) / n
    avg_stopped = sum(s["initiatives_stopped"] for s in summaries) / n

    print(f"  {label}")
    print(f"    Avg value:       {avg_val:8.2f}  (lump {avg_lump:.2f} + resid {avg_resid:.2f})")
    print(f"    Idle %:          {avg_idle:8.2%}")
    print(f"    Major wins:      {total_wins}")
    print(f"    Avg completed:   {avg_completed:8.1f}")
    print(f"    Avg stopped:     {avg_stopped:8.1f}")


def _print_family_breakdown(
    label: str,
    summaries: list[dict[str, Any]],
) -> None:
    """Print per-family completed/stopped breakdown.

    The per-family breakdown is the key diagnostic: the exec-belief
    bias is expected to be concentrated in long-duration families
    (right-tail, enabler, flywheel) and nearly irrelevant for
    short-duration ones (quick-win).
    """
    n = len(summaries)

    # Aggregate completed and stopped by family across seeds.
    families = ["flywheel", "right_tail", "enabler", "quick_win"]

    print(f"  {label} — per-family breakdown:")
    for family_tag in families:
        avg_completed = sum(s["completed_by_label"].get(family_tag, 0) for s in summaries) / n
        avg_stopped = sum(s["stopped_by_label"].get(family_tag, 0) for s in summaries) / n
        print(
            f"    {family_tag:15s}  "
            f"completed = {avg_completed:5.1f}  "
            f"stopped = {avg_stopped:5.1f}"
        )


# ============================================================================
# Main
# ============================================================================


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Execution-belief initialization bias sensitivity analysis.",
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
    print("Execution-Belief Initialization Bias Sensitivity")
    print("=" * 70)
    print(f"  Environment family: {family}")
    print(f"  Initial exec-belief values: {EXEC_BELIEF_VALUES}")
    print(f"  Seeds: {seeds}")
    print("  Policy: Balanced (baseline)")
    print(f"  Horizon: {TICK_HORIZON} ticks")
    print()
    print("  The default initial_execution_belief is 1.0. Because execution")
    print("  signals are noisy and many initiatives complete on schedule,")
    print("  execution belief drifts systematically downward. This may cause")
    print("  false exec-overrun stops, especially for long-duration families.")
    print()

    t0 = time.time()

    # Run all three exec-belief values.
    all_results: dict[float, list[dict[str, Any]]] = {}
    for belief_val in EXEC_BELIEF_VALUES:
        all_results[belief_val] = _run_scenario(belief_val, seeds, family)

    # --- Print per-value aggregates ---
    print()
    for belief_val in EXEC_BELIEF_VALUES:
        _print_aggregate(
            f"initial_execution_belief = {belief_val}",
            all_results[belief_val],
        )
        print()

    # --- Per-family breakdown ---
    print("-" * 70)
    print("  Per-family completed/stopped breakdown")
    print("-" * 70)
    print()
    for belief_val in EXEC_BELIEF_VALUES:
        _print_family_breakdown(
            f"initial_execution_belief = {belief_val}",
            all_results[belief_val],
        )
        print()

    # --- Delta table vs. baseline (1.0) ---
    baseline_val = 1.0
    if baseline_val in all_results:
        print("-" * 70)
        print(f"  Value delta vs. baseline (exec_belief={baseline_val}):")
        print("-" * 70)

        n = len(seeds)
        baseline_avg = sum(s["cumulative_value"] for s in all_results[baseline_val]) / n

        for belief_val in EXEC_BELIEF_VALUES:
            val_avg = sum(s["cumulative_value"] for s in all_results[belief_val]) / n
            delta = val_avg - baseline_avg
            pct = (delta / baseline_avg * 100) if baseline_avg != 0 else 0
            print(f"    exec_belief = {belief_val}:  {delta:+8.2f}  ({pct:+.1f}%)")
        print()

    # --- Stop-count delta by family ---
    print("-" * 70)
    print(f"  Stop-count delta by family vs. baseline (exec_belief={baseline_val}):")
    print("-" * 70)

    families = ["flywheel", "right_tail", "enabler", "quick_win"]
    n = len(seeds)
    for belief_val in EXEC_BELIEF_VALUES:
        if belief_val == baseline_val:
            continue
        print(f"    exec_belief = {belief_val}:")
        for family_tag in families:
            baseline_stops = (
                sum(s["stopped_by_label"].get(family_tag, 0) for s in all_results[baseline_val])
                / n
            )
            treatment_stops = (
                sum(s["stopped_by_label"].get(family_tag, 0) for s in all_results[belief_val]) / n
            )
            delta_stops = treatment_stops - baseline_stops
            print(
                f"      {family_tag:15s}  "
                f"stops: {baseline_stops:.1f} -> {treatment_stops:.1f}  "
                f"({delta_stops:+.1f})"
            )
        print()

    # --- Outcome classification ---
    print("=" * 70)
    print("  ASSESSMENT GUIDANCE")
    print("=" * 70)
    print()
    print("  Compare the results above against these criteria:")
    print()
    print("  (a) Bias is negligible: value and stop-count deltas are small")
    print("      (<2% value change) across all families and belief values.")
    print("      Proceed without correction.")
    print()
    print("  (b) Bias is material across the board: value changes are large")
    print("      (>5%) for all families. Flag for mechanical correction")
    print("      before RQ8 findings are treated as substantive.")
    print()
    print("  (c) Bias is material for some families: stop-count changes are")
    print("      concentrated in long-duration families (right-tail, enabler,")
    print("      flywheel) but negligible for quick-win. Narrow RQ8 claims")
    print("      or add a mandatory sensitivity bracket.")
    print()

    elapsed = time.time() - t0
    print(f"Elapsed: {elapsed:.0f}s")
    print()


if __name__ == "__main__":
    main()
