#!/usr/bin/env python
"""Staffing intensity study: robustness, channel isolation, and sensitivity.

Three study steps in one script:

    Study 1 — Robustness: more seeds to check whether the value lift
              from staffing intensity is stable across stochastic draws.

    Study 2 — Channel isolation: enable staffing intensity on only one
              initiative family at a time to identify which family drives
              the gain.

    Study 3 — Sensitivity: test conservative, moderate, and aggressive
              scale ranges to check whether the hypothesized effect sizes
              are too strong.

Usage:
    python scripts/staffing_intensity_study.py              # all three studies
    python scripts/staffing_intensity_study.py --study 1    # robustness only
    python scripts/staffing_intensity_study.py --study 2    # isolation only
    python scripts/staffing_intensity_study.py --study 3    # sensitivity only

Estimated runtime: ~8-10 minutes for all three studies on a modern machine.
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
# Shared configuration
# ============================================================================

# Team decomposition: 100 people, 12 teams.
TEAM_SIZES: tuple[int, ...] = (
    10,
    10,
    10,
    10,  # 4 teams of 10  (40 people)
    4,
    4,
    4,
    4,
    4,  # 5 teams of 4   (20 people)
    15,
    15,  # 2 teams of 15  (30 people)
    10,  # 1 team of 10   (10 people)
)

TICK_HORIZON: int = 313

# The "moderate" scale ranges (same as test_staffing_intensity.py).
MODERATE_SCALES: dict[str, tuple[float, float]] = {
    "right_tail": (0.8, 2.0),
    "enabler": (0.5, 1.5),
    "flywheel": (0.3, 0.8),
    "quick_win": (0.0, 0.2),
}


# ============================================================================
# Helpers
# ============================================================================


def _make_workforce() -> WorkforceConfig:
    return WorkforceConfig(
        team_count=len(TEAM_SIZES),
        team_size=TEAM_SIZES,
        ramp_period=4,
        ramp_multiplier_shape=RampShape.LINEAR,
    )


def _make_generator(
    scales: dict[str, tuple[float, float]] | None,
) -> InitiativeGeneratorConfig:
    """Build initiative generator with optional per-family staffing scales.

    Args:
        scales: Map from generation_tag to (lo, hi) staffing_response_scale
                range. None means all scales are 0.0 (baseline).
    """
    base_gen = make_initiative_generator_config("balanced_incumbent")
    if scales is None:
        return base_gen

    modified = []
    for spec in base_gen.type_specs:
        scale_range = scales.get(spec.generation_tag)
        if scale_range is not None:
            spec = replace(spec, staffing_response_scale_range=scale_range)
        modified.append(spec)
    return InitiativeGeneratorConfig(type_specs=tuple(modified))


def _make_config(
    seed: int,
    scales: dict[str, tuple[float, float]] | None,
) -> SimulationConfiguration:
    model = make_baseline_model_config()
    governance = make_balanced_governance_config(
        exec_attention_budget=model.exec_attention_budget,
        default_initial_quality_belief=model.default_initial_quality_belief,
    )
    return SimulationConfiguration(
        world_seed=seed,
        time=TimeConfig(tick_horizon=TICK_HORIZON, tick_label="week"),
        teams=_make_workforce(),
        model=model,
        governance=governance,
        reporting=ReportingConfig(
            record_manifest=True,
            record_per_tick_logs=False,
            record_event_log=True,
        ),
        initiative_generator=_make_generator(scales),
    )


def _run_scenario(
    label: str,
    scales: dict[str, tuple[float, float]] | None,
    seeds: list[int],
) -> list[dict[str, Any]]:
    """Run all seeds for one scenario and return summary dicts."""
    policy = BalancedPolicy()
    summaries = []
    for seed in seeds:
        logger.info("  %s -- seed %d", label, seed)
        config = _make_config(seed, scales)
        result, _ = run_single_regime(config, policy)
        summary = summarize_run_result(result)
        summary["residual_by_label"] = {
            k: round(v, 2) for k, v in result.value_by_channel.residual_value_by_label.items()
        }
        summaries.append(summary)
    return summaries


def _print_aggregate(label: str, summaries: list[dict[str, Any]]) -> None:
    """Print aggregate metrics for one scenario."""
    n = len(summaries)
    avg_val = sum(s["cumulative_value"] for s in summaries) / n
    avg_lump = sum(s["lump_value"] for s in summaries) / n
    avg_resid = sum(s["residual_value"] for s in summaries) / n
    avg_idle = sum(s["idle_team_tick_fraction"] for s in summaries) / n
    total_wins = sum(s["major_win_count"] for s in summaries)
    avg_free = sum(s["free_value_per_tick"] for s in summaries) / n
    avg_peak = sum(s["peak_productivity"] for s in summaries) / n
    avg_end = sum(s["productivity_at_end"] for s in summaries) / n

    print(f"  {label}")
    print(f"    Avg value:       {avg_val:8.2f}  (lump {avg_lump:.2f} + resid {avg_resid:.2f})")
    print(f"    Free val/tick:   {avg_free:8.4f}")
    print(f"    Peak / end prod: {avg_peak:.4f} / {avg_end:.4f}")
    print(f"    Idle %:          {avg_idle:8.2%}")
    print(f"    Major wins:      {total_wins}")


def _delta_line(label: str, baseline: list[dict], treatment: list[dict]) -> None:
    """Print a one-line delta."""
    n = len(baseline)
    base_avg = sum(s["cumulative_value"] for s in baseline) / n
    treat_avg = sum(s["cumulative_value"] for s in treatment) / n
    delta = treat_avg - base_avg
    pct = (delta / base_avg * 100) if base_avg != 0 else 0
    print(f"  {label:30s}  {delta:+8.2f}  ({pct:+.1f}%)")


# ============================================================================
# Study 1: Robustness (more seeds)
# ============================================================================


def study_1_robustness() -> None:
    seeds = list(range(42, 52))  # 10 seeds

    print()
    print("=" * 65)
    print(f"STUDY 1: Robustness ({len(seeds)} seeds)")
    print("=" * 65)
    print()
    print("  Question: Is the value lift from staffing intensity stable")
    print("  across stochastic draws, or driven by a few lucky seeds?")
    print()

    baseline = _run_scenario("Baseline", None, seeds)
    intensity = _run_scenario("Full intensity", MODERATE_SCALES, seeds)

    print()
    _print_aggregate("Baseline (scale=0)", baseline)
    print()
    _print_aggregate("Full intensity", intensity)
    print()

    # Per-seed comparison.
    print("  Per-seed value (baseline -> intensity):")
    lifts = []
    for b, t in zip(baseline, intensity, strict=True):
        delta = t["cumulative_value"] - b["cumulative_value"]
        lifts.append(delta)
        print(
            f"    seed {b['world_seed']}: "
            f"{b['cumulative_value']:8.2f} -> {t['cumulative_value']:8.2f}  "
            f"({delta:+.2f})"
        )

    # Summary statistics on the lift.
    avg_lift = sum(lifts) / len(lifts)
    min_lift = min(lifts)
    max_lift = max(lifts)
    positive_count = sum(1 for v in lifts if v > 0)
    print()
    print(f"  Lift: avg={avg_lift:+.2f}  min={min_lift:+.2f}  max={max_lift:+.2f}")
    print(f"  Positive in {positive_count}/{len(lifts)} seeds")
    print()


# ============================================================================
# Study 2: Channel isolation
# ============================================================================


def study_2_isolation() -> None:
    seeds = list(range(42, 49))  # 7 seeds

    print()
    print("=" * 65)
    print(f"STUDY 2: Channel isolation ({len(seeds)} seeds)")
    print("=" * 65)
    print()
    print("  Question: Which initiative family is driving the value lift?")
    print("  Method: Enable staffing intensity on only one family at a time.")
    print()

    baseline = _run_scenario("Baseline", None, seeds)

    # One variant per family: only that family gets staffing intensity.
    variants: dict[str, list[dict]] = {}
    for family_tag in ["flywheel", "right_tail", "enabler", "quick_win"]:
        # Build scales with only this family active.
        isolated_scales = {family_tag: MODERATE_SCALES[family_tag]}
        label = f"Only {family_tag}"
        variants[family_tag] = _run_scenario(label, isolated_scales, seeds)

    # Also run all-on for reference.
    all_on = _run_scenario("All families", MODERATE_SCALES, seeds)

    print()
    _print_aggregate("Baseline (scale=0)", baseline)
    print()
    for tag, summaries in variants.items():
        _print_aggregate(f"Only {tag}", summaries)
        print()
    _print_aggregate("All families", all_on)
    print()

    # Delta table.
    print("  Value lift vs. baseline:")
    for tag, summaries in variants.items():
        _delta_line(f"Only {tag}", baseline, summaries)
    _delta_line("All families combined", baseline, all_on)
    print()

    # Additivity check: do individual lifts sum to the combined lift?
    individual_sum = 0.0
    n = len(seeds)
    for _tag, variant_summaries in variants.items():
        individual_sum += (
            sum(s["cumulative_value"] for s in variant_summaries) / n
            - sum(s["cumulative_value"] for s in baseline) / n
        )
    combined_lift = (
        sum(s["cumulative_value"] for s in all_on) / n
        - sum(s["cumulative_value"] for s in baseline) / n
    )
    print(f"  Sum of individual lifts: {individual_sum:+.2f}")
    print(f"  Combined lift:           {combined_lift:+.2f}")
    if abs(individual_sum) > 0:
        interaction = combined_lift - individual_sum
        print(f"  Interaction effect:      {interaction:+.2f}")
    print()


# ============================================================================
# Study 3: Sensitivity
# ============================================================================


def _scale_ranges(
    base: dict[str, tuple[float, float]],
    factor: float,
) -> dict[str, tuple[float, float]]:
    """Multiply all scale ranges by a factor."""
    return {tag: (lo * factor, hi * factor) for tag, (lo, hi) in base.items()}


def study_3_sensitivity() -> None:
    seeds = list(range(42, 49))  # 7 seeds

    # Three intensity levels.
    conservative = _scale_ranges(MODERATE_SCALES, 0.5)
    moderate = MODERATE_SCALES
    aggressive = _scale_ranges(MODERATE_SCALES, 1.5)

    print()
    print("=" * 65)
    print(f"STUDY 3: Sensitivity ({len(seeds)} seeds)")
    print("=" * 65)
    print()
    print("  Question: Are the hypothesized scale ranges too strong?")
    print("  Method: Test 0.5x, 1.0x, and 1.5x the moderate ranges.")
    print()
    print("  Scale ranges:")
    for label_name, scales in [
        ("Conservative (0.5x)", conservative),
        ("Moderate (1.0x)", moderate),
        ("Aggressive (1.5x)", aggressive),
    ]:
        print(f"    {label_name}:")
        for tag, (lo, hi) in scales.items():
            print(f"      {tag:20s}  [{lo:.2f}, {hi:.2f}]")
    print()

    baseline = _run_scenario("Baseline", None, seeds)
    results_conservative = _run_scenario("Conservative", conservative, seeds)
    results_moderate = _run_scenario("Moderate", moderate, seeds)
    results_aggressive = _run_scenario("Aggressive", aggressive, seeds)

    print()
    _print_aggregate("Baseline (scale=0)", baseline)
    print()
    _print_aggregate("Conservative (0.5x)", results_conservative)
    print()
    _print_aggregate("Moderate (1.0x)", results_moderate)
    print()
    _print_aggregate("Aggressive (1.5x)", results_aggressive)
    print()

    # Delta table.
    print("  Value lift vs. baseline:")
    _delta_line("Conservative (0.5x)", baseline, results_conservative)
    _delta_line("Moderate (1.0x)", baseline, results_moderate)
    _delta_line("Aggressive (1.5x)", baseline, results_aggressive)
    print()

    # Is the lift roughly proportional to scale, or does it plateau?
    n = len(seeds)
    lifts = []
    for label_name, results in [
        ("0.5x", results_conservative),
        ("1.0x", results_moderate),
        ("1.5x", results_aggressive),
    ]:
        lift = (
            sum(s["cumulative_value"] for s in results) / n
            - sum(s["cumulative_value"] for s in baseline) / n
        )
        lifts.append((label_name, lift))

    if lifts[0][1] > 0 and lifts[1][1] > 0:
        ratio_mod_to_con = lifts[1][1] / lifts[0][1]
        ratio_agg_to_mod = lifts[2][1] / lifts[1][1]
        print("  Lift ratios (checking for diminishing returns at study level):")
        print(f"    Moderate / Conservative:  {ratio_mod_to_con:.2f}x")
        print(f"    Aggressive / Moderate:    {ratio_agg_to_mod:.2f}x")
        print("    (If these ratios are declining, the effect is saturating)")
    print()


# ============================================================================
# Main
# ============================================================================


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Staffing intensity study: robustness, isolation, sensitivity.",
    )
    parser.add_argument(
        "--study",
        type=int,
        choices=[1, 2, 3],
        default=None,
        help="Run only one study (1=robustness, 2=isolation, 3=sensitivity). "
        "Default: run all three.",
    )
    args = parser.parse_args()

    total_labor = sum(TEAM_SIZES)
    print()
    print("=" * 65)
    print("Staffing Intensity Study")
    print("=" * 65)
    print(f"  Teams: {len(TEAM_SIZES)} teams, {total_labor} total labor")
    print(f"  Horizon: {TICK_HORIZON} ticks, balanced_incumbent, Balanced policy")
    print()

    t0 = time.time()

    if args.study is None or args.study == 1:
        study_1_robustness()
    if args.study is None or args.study == 2:
        study_2_isolation()
    if args.study is None or args.study == 3:
        study_3_sensitivity()

    elapsed = time.time() - t0
    print(f"Total elapsed: {elapsed:.0f}s")
    print()


if __name__ == "__main__":
    main()
