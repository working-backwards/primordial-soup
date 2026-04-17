#!/usr/bin/env python
"""Right-tail abundance study: how opportunity supply affects governance outcomes.

Varies right-tail initiative count and frontier settings across runs to test
how the richness of the right-tail opportunity landscape affects governance
outcomes under different policy postures. Uses shared seeds for paired
comparison across treatments.

Study design:
    - Treatment axis: right-tail prize count (varying from scarce to abundant).
    - Policy comparison: all three archetypes (balanced, aggressive, patient).
    - Frontier-aware: uses Stage 3 prize-preserving refresh semantics, so
      stopped right-tail initiatives make their ceiling available for re-attempt.
    - Quick-win count adjusts automatically to maintain total pool size.

Key questions this study helps answer:
    - Does patient governance benefit disproportionately from richer right-tail
      supply? (More prizes = more chances to discover major wins.)
    - Does aggressive governance perform better or worse when right-tail
      opportunities are scarce? (Fewer prizes may make early stopping more
      costly if stopped prizes are consumed.)
    - Is there a threshold of right-tail abundance below which patient
      governance cannot outperform aggressive governance on total value?

Usage:
    python scripts/right_tail_abundance_study.py
    python scripts/right_tail_abundance_study.py --seeds 10
    python scripts/right_tail_abundance_study.py --family discovery_heavy
    python scripts/right_tail_abundance_study.py --refresh-degradation 0.05

Stage 4, Step 4.2 of the implementation plan
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
from primordial_soup.policy import (
    AggressiveStopLossPolicy,
    BalancedPolicy,
    GovernancePolicy,
    PatientMoonshotPolicy,
)
from primordial_soup.presets import (
    EnvironmentFamilyName,
    make_aggressive_stop_loss_governance_config,
    make_balanced_governance_config,
    make_baseline_model_config,
    make_patient_moonshot_governance_config,
)
from primordial_soup.runner import run_single_regime
from primordial_soup.types import RampShape
from primordial_soup.workbench import (
    EnvironmentConditionsSpec,
    summarize_run_result,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


# ============================================================================
# Configuration
# ============================================================================

# Right-tail count treatments. These represent different levels of
# right-tail opportunity richness. The total pool size (200) stays constant;
# quick-win count adjusts to fill the remainder.
# balanced_incumbent default: 40 right-tail.
RIGHT_TAIL_COUNTS: tuple[int, ...] = (15, 25, 40, 60, 80)

TICK_HORIZON: int = 313

# Policy archetypes to compare.
ARCHETYPES: list[tuple[str, Any, GovernancePolicy]] = [
    ("balanced", make_balanced_governance_config, BalancedPolicy()),
    ("aggressive", make_aggressive_stop_loss_governance_config, AggressiveStopLossPolicy()),
    ("patient", make_patient_moonshot_governance_config, PatientMoonshotPolicy()),
]


# ============================================================================
# Helpers
# ============================================================================


def _make_config(
    seed: int,
    right_tail_count: int,
    governance_factory: Any,
    family: EnvironmentFamilyName,
    refresh_degradation: float,
) -> SimulationConfiguration:
    """Build a SimulationConfiguration with a specific right-tail count.

    Uses the EnvironmentConditionsSpec override mechanism to adjust
    the right-tail count and (optionally) refresh degradation.

    Args:
        seed: World seed.
        right_tail_count: Number of right-tail initiatives in the pool.
        governance_factory: Factory function for the governance config.
        family: Environment family name.
        refresh_degradation: Right-tail refresh quality degradation.

    Returns:
        Complete SimulationConfiguration.
    """
    model = make_baseline_model_config()
    governance = governance_factory(
        exec_attention_budget=model.exec_attention_budget,
        default_initial_quality_belief=model.default_initial_quality_belief,
    )

    # Use EnvironmentConditionsSpec to apply overrides to the family preset.
    env_spec = EnvironmentConditionsSpec(
        family=family,
        right_tail_prize_count=right_tail_count,
        right_tail_refresh_degradation=(
            refresh_degradation if refresh_degradation > 0.0 else None
        ),
    )
    env_base = env_spec.resolve_environment_base()

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
        initiative_generator=env_base.initiative_generator,
    )


def _run_treatment(
    right_tail_count: int,
    governance_factory: Any,
    policy: GovernancePolicy,
    seeds: list[int],
    family: EnvironmentFamilyName,
    refresh_degradation: float,
) -> list[dict[str, Any]]:
    """Run all seeds for one treatment and return summaries.

    Args:
        right_tail_count: Number of right-tail initiatives.
        governance_factory: Factory for governance config.
        policy: Policy instance to use.
        seeds: List of world seeds.
        family: Environment family name.
        refresh_degradation: Right-tail refresh quality degradation.

    Returns:
        List of summary dicts, one per seed.
    """
    summaries = []
    for seed in seeds:
        logger.info("    rt_count=%d, seed=%d", right_tail_count, seed)
        config = _make_config(
            seed, right_tail_count, governance_factory, family, refresh_degradation
        )
        result, _ = run_single_regime(config, policy)
        summary = summarize_run_result(result)
        summaries.append(summary)
    return summaries


def _print_results_table(
    all_results: dict[tuple[int, str], list[dict[str, Any]]],
    seeds: list[int],
) -> None:
    """Print a comparison table of results across treatments and archetypes.

    Columns: right-tail count, archetype, avg value, avg completed,
    avg stopped, major wins, idle %.
    """
    n = len(seeds)
    print()
    header = (
        f"{'RT Count':>10s}  {'Policy':>12s}  "
        f"{'Avg Value':>10s}  {'Completed':>10s}  {'Stopped':>10s}  "
        f"{'Wins':>5s}  {'Idle%':>6s}"
    )
    print(header)
    print("-" * len(header))

    for (rt_count, archetype_label), summaries in sorted(all_results.items()):
        avg_val = sum(s["cumulative_value"] for s in summaries) / n
        avg_completed = sum(s["initiatives_completed"] for s in summaries) / n
        avg_stopped = sum(s["initiatives_stopped"] for s in summaries) / n
        total_wins = sum(s["major_win_count"] for s in summaries)
        avg_idle = sum(s["idle_team_tick_fraction"] for s in summaries) / n
        print(
            f"{rt_count:>10d}  {archetype_label:>12s}  "
            f"{avg_val:>10.2f}  {avg_completed:>10.1f}  {avg_stopped:>10.1f}  "
            f"{total_wins:>5d}  {avg_idle:>6.2%}"
        )


def _print_value_by_family(
    all_results: dict[tuple[int, str], list[dict[str, Any]]],
    seeds: list[int],
) -> None:
    """Print per-family completed/stopped breakdown."""
    n = len(seeds)
    families = ["flywheel", "right_tail", "enabler", "quick_win"]

    print()
    print("Per-family completed/stopped breakdown:")
    print()

    for (rt_count, archetype_label), summaries in sorted(all_results.items()):
        print(f"  RT count={rt_count}, policy={archetype_label}:")
        for family_tag in families:
            avg_completed = sum(s["completed_by_label"].get(family_tag, 0) for s in summaries) / n
            avg_stopped = sum(s["stopped_by_label"].get(family_tag, 0) for s in summaries) / n
            print(
                f"    {family_tag:15s}  "
                f"completed={avg_completed:5.1f}  "
                f"stopped={avg_stopped:5.1f}"
            )
        print()


# ============================================================================
# Main
# ============================================================================


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Right-tail abundance study: how opportunity supply "
        "affects governance outcomes.",
    )
    parser.add_argument(
        "--seeds",
        type=int,
        default=5,
        help="Number of seeds (default: 5).",
    )
    parser.add_argument(
        "--family",
        type=str,
        default="balanced_incumbent",
        help="Environment family (default: balanced_incumbent).",
    )
    parser.add_argument(
        "--refresh-degradation",
        type=float,
        default=0.0,
        help="Right-tail refresh quality degradation (default: 0.0).",
    )
    parser.add_argument(
        "--rt-counts",
        type=int,
        nargs="+",
        default=None,
        help="Right-tail counts to test (default: 15 25 40 60 80).",
    )
    args = parser.parse_args()

    seed_count: int = args.seeds
    family: EnvironmentFamilyName = args.family
    refresh_degradation: float = args.refresh_degradation
    rt_counts = tuple(args.rt_counts) if args.rt_counts else RIGHT_TAIL_COUNTS
    seeds = list(range(42, 42 + seed_count))

    print()
    print("=" * 72)
    print("Right-Tail Abundance Study")
    print("=" * 72)
    print(f"  Environment family: {family}")
    print(f"  Right-tail counts:  {list(rt_counts)}")
    print(f"  Policies:           {[label for label, _, _ in ARCHETYPES]}")
    print(f"  Seeds:              {seeds}")
    print(f"  Horizon:            {TICK_HORIZON} ticks")
    print(f"  Refresh degradation: {refresh_degradation}")
    print()
    print("  This study varies right-tail initiative count across runs to")
    print("  test how right-tail opportunity supply affects governance")
    print("  outcomes. Quick-win count adjusts to maintain total pool=200.")
    print()

    t0 = time.time()

    # Run all treatments.
    all_results: dict[tuple[int, str], list[dict[str, Any]]] = {}
    for rt_count in rt_counts:
        print(f"  Right-tail count = {rt_count}:")
        for archetype_label, governance_factory, policy in ARCHETYPES:
            print(f"    Policy: {archetype_label}")
            summaries = _run_treatment(
                rt_count, governance_factory, policy, seeds, family, refresh_degradation
            )
            all_results[(rt_count, archetype_label)] = summaries

    # --- Results ---
    print()
    print("=" * 72)
    print("Results")
    print("=" * 72)

    _print_results_table(all_results, seeds)
    _print_value_by_family(all_results, seeds)

    # --- Patient vs. aggressive value delta by right-tail count ---
    print("-" * 72)
    print("  Patient vs. Aggressive value delta by right-tail count:")
    print("-" * 72)
    n = len(seeds)
    for rt_count in rt_counts:
        patient_key = (rt_count, "patient")
        aggressive_key = (rt_count, "aggressive")
        if patient_key in all_results and aggressive_key in all_results:
            patient_avg = sum(s["cumulative_value"] for s in all_results[patient_key]) / n
            aggressive_avg = sum(s["cumulative_value"] for s in all_results[aggressive_key]) / n
            delta = patient_avg - aggressive_avg
            pct = (delta / aggressive_avg * 100) if aggressive_avg != 0 else 0
            print(
                f"    RT count={rt_count:3d}: "
                f"patient={patient_avg:8.2f}  aggressive={aggressive_avg:8.2f}  "
                f"delta={delta:+8.2f} ({pct:+.1f}%)"
            )
    print()

    # --- Interpretation guidance ---
    print("=" * 72)
    print("  INTERPRETATION GUIDANCE")
    print("=" * 72)
    print()
    print("  Look for:")
    print("  (1) Does patient governance gain disproportionately from richer")
    print("      right-tail supply? (Larger patient-vs-aggressive delta at")
    print("      higher RT counts.)")
    print()
    print("  (2) Is there a threshold below which patient governance cannot")
    print("      outperform aggressive governance on total value?")
    print()
    print("  (3) How do major-win counts scale with right-tail abundance?")
    print("      (If wins don't increase, the additional supply may not be")
    print("      productive.)")
    print()
    print("  (4) Does idle capacity increase at high RT counts? (More")
    print("      right-tail initiatives are longer-duration, which may")
    print("      affect team utilization.)")
    print()

    elapsed = time.time() - t0
    print(f"Elapsed: {elapsed:.0f}s")
    print()


if __name__ == "__main__":
    main()
