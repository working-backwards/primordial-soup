#!/usr/bin/env python
"""Calibration sanity check — analytical and empirical validation.

Reports, for each environment family:
  1. Expected major-win-eligible initiatives in the initial pool
     (count × P(q >= threshold) from the Beta distribution).
  2. Expected right-tail completions by horizon (given duration range
     vs. 313-tick horizon).
  3. Probability of at least one surfaced major win per run under
     baseline governance (binomial from eligibility × completion rate).
  4. Empirical validation: run a few seeds per archetype and report
     observed major-win counts, completion counts, and value.

This checks for generator collapse without targeting a preferred
outcome. If expected eligibles per pool ≈ 0, the calibration is
still structurally broken regardless of governance.

Usage:
    python scripts/calibration_sanity_check.py
    python scripts/calibration_sanity_check.py --seeds 20
    python scripts/calibration_sanity_check.py --empirical
"""

from __future__ import annotations

import argparse
import logging
import math
import time

from primordial_soup.evaluator import GovernanceParams, evaluate_policy
from primordial_soup.presets import (
    EnvironmentFamilyName,
    make_environment_spec,
    make_initiative_generator_config,
)
from primordial_soup.types import BetaDistribution

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


# ============================================================================
# Constants
# ============================================================================

FAMILIES: tuple[EnvironmentFamilyName, ...] = (
    "balanced_incumbent",
    "short_cycle_throughput",
    "discovery_heavy",
)

FAMILY_LABELS: dict[str, str] = {
    "balanced_incumbent": "Balanced Inc.",
    "short_cycle_throughput": "Short Cycle",
    "discovery_heavy": "Discovery",
}

PRESETS: tuple[str, ...] = ("balanced", "aggressive_stop_loss", "patient_moonshot")

PRESET_LABELS: dict[str, str] = {
    "balanced": "Balanced",
    "aggressive_stop_loss": "Aggressive",
    "patient_moonshot": "Patient",
}

TICK_HORIZON = 313


# ============================================================================
# Analytical functions
# ============================================================================


def beta_sf(x: float, alpha: float, beta_param: float) -> float:
    """Compute P(X >= x) for a Beta(alpha, beta) distribution.

    Uses the regularized incomplete beta function via math.lgamma
    and numerical integration (simple trapezoidal rule with fine grid).
    Good enough for calibration-check accuracy.

    Args:
        x: Threshold value in [0, 1].
        alpha: Beta distribution alpha parameter.
        beta_param: Beta distribution beta parameter.

    Returns:
        Probability that a Beta(alpha, beta) draw exceeds x.
    """
    if x <= 0.0:
        return 1.0
    if x >= 1.0:
        return 0.0

    # Numerical integration via trapezoidal rule on [x, 1].
    # Use enough points for 3-digit accuracy.
    n_points = 10000
    step = (1.0 - x) / n_points

    # Log of the Beta normalization constant B(alpha, beta).
    log_beta_norm = math.lgamma(alpha) + math.lgamma(beta_param) - math.lgamma(alpha + beta_param)

    total = 0.0
    for i in range(n_points + 1):
        t = x + i * step
        # Clamp to avoid log(0).
        t = max(t, 1e-15)
        t = min(t, 1.0 - 1e-15)
        log_pdf = (
            (alpha - 1.0) * math.log(t) + (beta_param - 1.0) * math.log(1.0 - t) - log_beta_norm
        )
        pdf = math.exp(log_pdf)
        # Trapezoidal weight: half at endpoints.
        weight = 0.5 if (i == 0 or i == n_points) else 1.0
        total += weight * pdf * step

    return total


def expected_completions_by_horizon(
    duration_range: tuple[int, int],
    horizon: int,
) -> float:
    """Expected fraction of initiatives that can complete within horizon.

    Assumes true_duration_ticks is uniformly distributed in
    [low, high]. An initiative can complete if its duration <= horizon.
    This is an upper bound — it assumes the initiative is assigned
    from tick 0 and never stopped.

    Args:
        duration_range: (low, high) for true_duration_ticks.
        horizon: Total simulation ticks.

    Returns:
        Fraction of draws whose duration <= horizon.
    """
    low, high = duration_range
    if high <= horizon:
        # All initiatives can complete within the horizon.
        return 1.0
    if low > horizon:
        # No initiatives can complete.
        return 0.0
    # Linear interpolation: fraction with duration <= horizon.
    return (horizon - low) / (high - low)


# ============================================================================
# Printing helpers
# ============================================================================


def _print_header(title: str, width: int = 78) -> None:
    print()
    print("=" * width)
    print(f"  {title}")
    print("=" * width)


def _print_section(title: str, width: int = 78) -> None:
    print()
    print(f"  {title}")
    print("-" * width)


# ============================================================================
# Analytical report
# ============================================================================


def print_analytical_report() -> None:
    """Print analytical calibration check for all families."""
    _print_header("Calibration Sanity Check — Analytical")

    for family in FAMILIES:
        gen_config = make_initiative_generator_config(family)
        # Find the right-tail spec.
        rt_spec = next(s for s in gen_config.type_specs if s.generation_tag == "right_tail")

        # Extract Beta distribution parameters.
        quality_dist = rt_spec.quality_distribution
        assert isinstance(quality_dist, BetaDistribution)
        alpha = quality_dist.alpha
        beta_param = quality_dist.beta
        threshold = rt_spec.q_major_win_threshold
        rt_count = rt_spec.count
        duration_range = rt_spec.true_duration_range
        assert duration_range is not None

        # P(q >= threshold)
        p_eligible = beta_sf(threshold, alpha, beta_param)

        # Expected eligible in initial pool.
        expected_eligible = rt_count * p_eligible

        # Expected completion fraction (upper bound, assumes tick-0 assignment).
        completion_fraction = expected_completions_by_horizon(duration_range, TICK_HORIZON)

        # P(at least one surfaced major win per run) — binomial.
        # Surfaced = eligible AND completed.
        # Upper bound: assumes all eligible are assigned and worked.
        p_surfaced_per_initiative = p_eligible * completion_fraction
        p_at_least_one = 1.0 - (1.0 - p_surfaced_per_initiative) ** rt_count

        _print_section(f"Family: {FAMILY_LABELS[family]} ({family})")
        print(f"  Right-tail count:           {rt_count}")
        print(f"  Quality distribution:       Beta({alpha}, {beta_param})")
        print(f"  Major-win threshold:        {threshold}")
        print(f"  P(q >= {threshold}):              {p_eligible:.4f} ({p_eligible * 100:.2f}%)")
        print(f"  Expected eligible in pool:  {expected_eligible:.2f}")
        print()
        print(f"  Duration range:             {duration_range}")
        print(f"  Horizon:                    {TICK_HORIZON} ticks")
        print(
            f"  Completion fraction (UB):   "
            f"{completion_fraction:.3f} ({completion_fraction * 100:.1f}%)"
        )
        print()
        print(f"  P(surfaced per initiative): {p_surfaced_per_initiative:.5f}")
        print(f"  P(>=1 surfaced per run):    {p_at_least_one:.4f} ({p_at_least_one * 100:.1f}%)")

        # Assessment.
        print()
        if expected_eligible < 0.01:
            print("  ** WARNING: Generator collapse — expected eligibles ≈ 0. **")
            print("     The calibration is structurally broken for this family.")
        elif expected_eligible < 0.5:
            print("  ** CAUTION: Very few expected eligibles. Major wins will be")
            print("     extremely rare. Check if this is the intended design. **")
        else:
            print(f"  OK: ~{expected_eligible:.1f} eligible initiatives per pool.")
            print("      Major wins are rare but structurally possible.")


# ============================================================================
# Empirical validation
# ============================================================================


def print_empirical_report(seed_count: int) -> None:
    """Run a small campaign and report observed outcomes."""
    _print_header("Calibration Sanity Check — Empirical")

    seeds = tuple(range(42, 42 + seed_count))
    total_runs = len(PRESETS) * len(FAMILIES) * seed_count
    print(f"  Seeds: {list(seeds)} ({seed_count} per cell)")
    print(f"  Total runs: {total_runs}")

    t0 = time.time()

    # Run all cells.
    results: dict[tuple[str, str], dict] = {}
    for family in FAMILIES:
        env = make_environment_spec(family)
        for preset in PRESETS:
            label = f"{FAMILY_LABELS[family]} / {PRESET_LABELS[preset]}"
            print(f"  Running {label}...", end="", flush=True)
            cell_t0 = time.time()

            params = GovernanceParams(policy_preset=preset)
            result = evaluate_policy(params, seeds=seeds, environment_spec=env)

            # Extract per-seed detail.
            rt_completed = []
            rt_stopped = []
            for sr in result.per_seed_results:
                rt_completed.append(sr.summary.get("completed_by_label", {}).get("right_tail", 0))
                rt_stopped.append(sr.summary.get("stopped_by_label", {}).get("right_tail", 0))

            results[(family, preset)] = {
                "total_major_wins": result.total_major_wins,
                "mean_major_wins": result.mean_major_win_count,
                "mean_value": result.mean_cumulative_value,
                "mean_rt_completed": sum(rt_completed) / len(rt_completed),
                "mean_rt_stopped": sum(rt_stopped) / len(rt_stopped),
                "idle_fraction": result.mean_idle_fraction,
                "pool_exhaustion_count": sum(
                    1
                    for sr in result.per_seed_results
                    if sr.summary.get("pool_exhaustion_tick") is not None
                ),
            }

            cell_elapsed = time.time() - cell_t0
            print(f" {cell_elapsed:.1f}s")

    elapsed = time.time() - t0

    # Print results table.
    _print_section("Empirical results (mean across seeds)")

    header = (
        f"{'Family':>14s}  {'Policy':>12s}  "
        f"{'MajWins':>7s}  {'RTComp':>7s}  {'RTStop':>7s}  "
        f"{'Value':>8s}  {'Idle%':>6s}  {'Exhaust':>7s}"
    )
    print(header)
    print("-" * len(header))

    for family in FAMILIES:
        for preset in PRESETS:
            r = results[(family, preset)]
            print(
                f"{FAMILY_LABELS[family]:>14s}  {PRESET_LABELS[preset]:>12s}  "
                f"{r['mean_major_wins']:>7.2f}  {r['mean_rt_completed']:>7.1f}  "
                f"{r['mean_rt_stopped']:>7.1f}  {r['mean_value']:>8.1f}  "
                f"{r['idle_fraction']:>6.1%}  {r['pool_exhaustion_count']:>7d}"
            )
        if family != FAMILIES[-1]:
            print()

    # Acceptance criteria check.
    _print_section("Acceptance criteria")

    all_ok = True
    for family in FAMILIES:
        family_label = FAMILY_LABELS[family]

        # Check pool exhaustion.
        for preset in PRESETS:
            r = results[(family, preset)]
            if r["pool_exhaustion_count"] > 0:
                print(
                    f"  FAIL: {family_label}/{PRESET_LABELS[preset]}: "
                    f"{r['pool_exhaustion_count']} pool exhaustion(s)"
                )
                all_ok = False

        # Check RT completion rate > 0 under at least one archetype.
        any_rt_completed = any(results[(family, p)]["mean_rt_completed"] > 0 for p in PRESETS)
        if not any_rt_completed:
            print(f"  FAIL: {family_label}: zero right-tail completions " f"under all archetypes")
            all_ok = False
        else:
            print(f"  OK:   {family_label}: right-tail completions observed")

        # Check total major wins across the family.
        total_mw = sum(results[(family, p)]["total_major_wins"] for p in PRESETS)
        if total_mw > 0:
            print(f"  OK:   {family_label}: {total_mw} total major wins")
        else:
            print(
                f"  NOTE: {family_label}: zero major wins (may be " f"acceptable with few seeds)"
            )

    if all_ok:
        print()
        print("  All acceptance criteria passed.")
    else:
        print()
        print("  ** Some criteria failed — check output above. **")

    print(f"\n  Total elapsed: {elapsed:.0f}s ({total_runs} runs)")


# ============================================================================
# Main
# ============================================================================


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Calibration sanity check — analytical and empirical.",
    )
    parser.add_argument(
        "--seeds",
        type=int,
        default=7,
        help="Number of seeds for empirical validation (default: 7).",
    )
    parser.add_argument(
        "--empirical",
        action="store_true",
        default=False,
        help="Run empirical validation (simulation runs). Default: analytical only.",
    )
    args = parser.parse_args()

    print_analytical_report()

    if args.empirical:
        print_empirical_report(args.seeds)
    else:
        print()
        print("  Use --empirical to also run simulation validation.")
        print()


if __name__ == "__main__":
    main()
