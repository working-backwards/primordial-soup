#!/usr/bin/env python
"""Baseline governance comparison campaign.

Runs all three governance archetypes across all three environment families
with multiple seeds. This is the canonical study — the one everything else
is compared against.

Design: 3 archetypes × 3 families × 7 seeds = 63 runs.

Usage:
    python scripts/baseline_governance_campaign.py
    python scripts/baseline_governance_campaign.py --seeds 5
    python scripts/baseline_governance_campaign.py --seeds 10
    python scripts/baseline_governance_campaign.py --families balanced_incumbent discovery_heavy

RQ1-RQ2 of the implementation plan.
"""

from __future__ import annotations

import argparse
import logging
import time

from primordial_soup.evaluator import GovernanceParams, ObjectiveResult, evaluate_policy
from primordial_soup.presets import EnvironmentFamilyName, make_environment_spec

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ============================================================================
# Configuration
# ============================================================================

PRESETS: tuple[str, ...] = ("balanced", "aggressive_stop_loss", "patient_moonshot")

FAMILIES: tuple[EnvironmentFamilyName, ...] = (
    "balanced_incumbent",
    "short_cycle_throughput",
    "discovery_heavy",
)

PRESET_LABELS: dict[str, str] = {
    "balanced": "Balanced",
    "aggressive_stop_loss": "Aggressive",
    "patient_moonshot": "Patient",
}

FAMILY_LABELS: dict[str, str] = {
    "balanced_incumbent": "Balanced Inc.",
    "short_cycle_throughput": "Short Cycle",
    "discovery_heavy": "Discovery",
}


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


def _print_overview_table(
    results: dict[tuple[str, str], ObjectiveResult],
    families: tuple[EnvironmentFamilyName, ...],
) -> None:
    """Print the main comparison table: one row per archetype × family."""
    _print_section("Overview: aggregate metrics (mean across seeds)")

    header = (
        f"{'Environment':>14s}  {'Regime':>12s}  "
        f"{'TotalVal':>8s}  {'Lump':>7s}  {'Resid':>7s}  "
        f"{'Wins':>5s}  {'Learn':>5s}  "
        f"{'Val/wk':>7s}  {'Idle%':>6s}  {'Ramp%':>6s}"
    )
    print(header)
    print("-" * len(header))

    for family in families:
        for preset in PRESETS:
            r = results[(family, preset)]
            n = r.n_seeds
            mean_lump = sum(sr.summary["lump_value"] for sr in r.per_seed_results) / n
            mean_resid = sum(sr.summary["residual_value"] for sr in r.per_seed_results) / n

            print(
                f"{FAMILY_LABELS[family]:>14s}  {PRESET_LABELS[preset]:>12s}  "
                f"{r.mean_cumulative_value:>8.1f}  {mean_lump:>7.1f}  {mean_resid:>7.1f}  "
                f"{r.total_major_wins:>5d}  {r.mean_terminal_capability:>5.2f}  "
                f"{r.mean_free_value_per_tick:>7.3f}  "
                f"{r.mean_idle_fraction:>6.1%}  {r.mean_ramp_labor_fraction:>6.1%}"
            )
        if family != families[-1]:
            print()


def _print_value_by_family_table(
    results: dict[tuple[str, str], ObjectiveResult],
    families: tuple[EnvironmentFamilyName, ...],
) -> None:
    """Print value decomposition by initiative family."""
    _print_section("Value by initiative family (mean across seeds)")

    families_init = ["flywheel", "right_tail", "enabler", "quick_win"]

    for family in families:
        print(f"\n  Environment: {FAMILY_LABELS[family]}")
        header = f"    {'Policy':>12s}  " + "  ".join(f"{f:>12s}" for f in families_init)
        print(header)

        for preset in PRESETS:
            r = results[(family, preset)]
            n = r.n_seeds
            mean_by_fam: dict[str, float] = {}
            for fi in families_init:
                mean_by_fam[fi] = (
                    sum(sr.summary["value_by_family"].get(fi, 0.0) for sr in r.per_seed_results)
                    / n
                )

            parts = "  ".join(f"{mean_by_fam[fi]:>12.1f}" for fi in families_init)
            print(f"    {PRESET_LABELS[preset]:>12s}  {parts}")


def _print_completion_table(
    results: dict[tuple[str, str], ObjectiveResult],
    families: tuple[EnvironmentFamilyName, ...],
) -> None:
    """Print completed/stopped counts by initiative family."""
    _print_section("Initiative outcomes by family (mean across seeds)")

    families_init = ["flywheel", "right_tail", "enabler", "quick_win"]

    for family in families:
        print(f"\n  Environment: {FAMILY_LABELS[family]}")

        for preset in PRESETS:
            r = results[(family, preset)]
            n = r.n_seeds
            print(f"    {PRESET_LABELS[preset]}:")
            for fi in families_init:
                avg_comp = (
                    sum(sr.summary["completed_by_label"].get(fi, 0) for sr in r.per_seed_results)
                    / n
                )
                avg_stop = (
                    sum(sr.summary["stopped_by_label"].get(fi, 0) for sr in r.per_seed_results) / n
                )
                print(f"      {fi:>12s}:  completed={avg_comp:5.1f}  stopped={avg_stop:5.1f}")
            print()


def _print_timing_table(
    results: dict[tuple[str, str], ObjectiveResult],
    families: tuple[EnvironmentFamilyName, ...],
) -> None:
    """Print family timing metrics."""
    _print_section("Timing: first completion tick by family (mean across seeds)")

    families_init = ["flywheel", "right_tail", "enabler", "quick_win"]

    for family in families:
        print(f"\n  Environment: {FAMILY_LABELS[family]}")
        header = (
            f"    {'Policy':>12s}  "
            + "  ".join(f"{f:>12s}" for f in families_init)
            + f"  {'PeakCap':>8s}  {'1stRTStop':>9s}"
        )
        print(header)

        for preset in PRESETS:
            r = results[(family, preset)]
            n = r.n_seeds

            parts = []
            for fi in families_init:
                ticks = [
                    sr.summary["first_completion_tick_by_family"].get(fi)
                    for sr in r.per_seed_results
                ]
                valid = [t for t in ticks if t is not None]
                if valid:
                    parts.append(f"{sum(valid) / len(valid):>12.0f}")
                else:
                    parts.append(f"{'--':>12s}")

            # Peak capability tick.
            mean_peak = sum(sr.summary["peak_capability_tick"] for sr in r.per_seed_results) / n

            # First right-tail stop.
            rt_stops = [sr.summary["first_right_tail_stop_tick"] for sr in r.per_seed_results]
            valid_rt = [t for t in rt_stops if t is not None]
            rt_str = f"{sum(valid_rt) / len(valid_rt):>9.0f}" if valid_rt else f"{'--':>9s}"

            print(
                f"    {PRESET_LABELS[preset]:>12s}  "
                f"{'  '.join(parts)}  {mean_peak:>8.0f}  {rt_str}"
            )


def _print_frontier_table(
    results: dict[tuple[str, str], ObjectiveResult],
    families: tuple[EnvironmentFamilyName, ...],
) -> None:
    """Print frontier exhaustion state at end of run."""
    _print_section("Frontier state at end of run (mean across seeds)")

    families_init = ["flywheel", "right_tail", "enabler", "quick_win"]

    for family in families:
        print(f"\n  Environment: {FAMILY_LABELS[family]}")

        for preset in PRESETS:
            r = results[(family, preset)]
            print(f"    {PRESET_LABELS[preset]}:")

            for fi in families_init:
                resolved_vals = []
                draws_vals = []
                alpha_vals = []
                for sr in r.per_seed_results:
                    fs = sr.summary.get("frontier_state_by_family", {})
                    if fi in fs:
                        resolved_vals.append(fs[fi]["n_resolved"])
                        draws_vals.append(fs[fi]["n_frontier_draws"])
                        alpha_vals.append(fs[fi]["effective_alpha_multiplier"])

                if resolved_vals:
                    avg_res = sum(resolved_vals) / len(resolved_vals)
                    avg_draws = sum(draws_vals) / len(draws_vals)
                    avg_alpha = sum(alpha_vals) / len(alpha_vals)
                    print(
                        f"      {fi:>12s}:  resolved={avg_res:5.1f}  "
                        f"draws={avg_draws:5.1f}  alpha={avg_alpha:.3f}"
                    )
            print()


def _print_diagnostic_summary(
    results: dict[tuple[str, str], ObjectiveResult],
    families: tuple[EnvironmentFamilyName, ...],
) -> None:
    """Print per-archetype diagnostic summary for calibration work.

    Shows what each governance regime actually did: completions,
    stops by rule, stop timing, and governance parameters. This is
    the equivalent of a portfolio review — "here is what we invested
    in, here is what we stopped and why, here is what finished."
    """
    families_init = ["flywheel", "right_tail", "enabler", "quick_win"]

    for family in families:
        _print_section(f"Diagnostic: {FAMILY_LABELS[family]}")

        for preset in PRESETS:
            r = results[(family, preset)]
            n = r.n_seeds
            print(f"\n    {PRESET_LABELS[preset]} regime:")

            # --- Initiative outcomes by family ---
            total_comp = 0.0
            total_stop = 0.0
            for fi in families_init:
                avg_comp = (
                    sum(sr.summary["completed_by_label"].get(fi, 0) for sr in r.per_seed_results)
                    / n
                )
                avg_stop = (
                    sum(sr.summary["stopped_by_label"].get(fi, 0) for sr in r.per_seed_results) / n
                )
                total_comp += avg_comp
                total_stop += avg_stop
                print(f"      {fi:>12s}:  completed={avg_comp:5.1f}  stopped={avg_stop:5.1f}")
            print(f"      {'TOTAL':>12s}:  completed={total_comp:5.1f}  stopped={total_stop:5.1f}")

            # --- Stop rule breakdown ---
            stop_rules: dict[str, int] = {}
            for sr in r.per_seed_results:
                for rule, count in sr.summary.get("stop_rule_counts", {}).items():
                    stop_rules[rule] = stop_rules.get(rule, 0) + count
            if stop_rules:
                print("      Stop reasons (total across seeds):")
                for rule in sorted(stop_rules.keys()):
                    print(f"        {rule}: {stop_rules[rule]}")

            # --- Value decomposition ---
            mean_lump = sum(sr.summary["lump_value"] for sr in r.per_seed_results) / n
            mean_resid = sum(sr.summary["residual_value"] for sr in r.per_seed_results) / n
            print(
                f"      Value: total={r.mean_cumulative_value:.1f}  "
                f"lump={mean_lump:.1f}  residual={mean_resid:.1f}  "
                f"capability={r.mean_terminal_capability:.2f}x"
            )
            print(
                f"      Efficiency: idle={r.mean_idle_fraction:.1%}  "
                f"ramp={r.mean_ramp_labor_fraction:.1%}  "
                f"wins={r.total_major_wins}"
            )
        print()


def _print_policy_delta_table(
    results: dict[tuple[str, str], ObjectiveResult],
    families: tuple[EnvironmentFamilyName, ...],
) -> None:
    """Print value deltas relative to Balanced baseline."""
    _print_section("Value delta vs. Balanced baseline")

    for family in families:
        baseline = results[(family, "balanced")].mean_cumulative_value
        print(f"  {FAMILY_LABELS[family]}:")
        for preset in PRESETS:
            val = results[(family, preset)].mean_cumulative_value
            delta = val - baseline
            pct = (delta / baseline * 100) if baseline != 0 else 0
            wins = results[(family, preset)].total_major_wins
            base_wins = results[(family, "balanced")].total_major_wins
            print(
                f"    {PRESET_LABELS[preset]:>12s}:  "
                f"value={val:8.1f}  delta={delta:+8.1f} ({pct:+.1f}%)  "
                f"wins={wins} (baseline={base_wins})"
            )
        print()


# ============================================================================
# Main
# ============================================================================


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Baseline governance comparison campaign.",
    )
    parser.add_argument(
        "--seeds",
        type=int,
        default=7,
        help="Number of seeds per archetype×family (default: 7).",
    )
    parser.add_argument(
        "--families",
        type=str,
        nargs="+",
        default=None,
        help="Environment families to test (default: all three).",
    )
    args = parser.parse_args()

    seed_count: int = args.seeds
    families: tuple[EnvironmentFamilyName, ...] = (
        tuple(args.families) if args.families else FAMILIES
    )
    seeds = tuple(range(42, 42 + seed_count))
    total_runs = len(PRESETS) * len(families) * seed_count

    _print_header("Baseline Governance Comparison Campaign")
    print(f"  Archetypes: {[PRESET_LABELS[p] for p in PRESETS]}")
    print(f"  Families:   {[FAMILY_LABELS[f] for f in families]}")
    print(f"  Seeds:      {list(seeds)} ({seed_count} per cell)")
    print(f"  Total runs: {total_runs}")
    print()

    t0 = time.time()

    # --- Run all cells ---
    results: dict[tuple[str, str], ObjectiveResult] = {}
    for family in families:
        env = make_environment_spec(family)
        for preset in PRESETS:
            label = f"{FAMILY_LABELS[family]} / {PRESET_LABELS[preset]}"
            print(f"  Running {label} ({seed_count} seeds)...", end="", flush=True)
            cell_t0 = time.time()

            params = GovernanceParams(policy_preset=preset)
            result = evaluate_policy(params, seeds=seeds, environment_spec=env)
            results[(family, preset)] = result

            cell_elapsed = time.time() - cell_t0
            print(f" {cell_elapsed:.1f}s")

    elapsed = time.time() - t0

    # --- Results ---
    _print_header("Results")
    _print_overview_table(results, families)
    _print_value_by_family_table(results, families)
    _print_completion_table(results, families)
    _print_timing_table(results, families)
    _print_frontier_table(results, families)
    _print_policy_delta_table(results, families)

    # --- Per-archetype diagnostic summary (#20) ---
    _print_header("Per-Archetype Diagnostic Summary")
    _print_diagnostic_summary(results, families)

    # --- Metric guide (#17) ---
    _print_header("Metric Guide")
    print()
    print("  TotalVal  Total cumulative value (lump + residual). Higher is better.")
    print("  Lump      One-time value realized at initiative completion.")
    print("  Resid     Ongoing compounding value from completed initiatives.")
    print("  Wins      Major-win discoveries surfaced (high-value right-tail events).")
    print("  Learn     Organizational learning capability multiplier (1.0 = baseline).")
    print("            Higher means better signal clarity for future decisions.")
    print("  Val/wk    Value generated per week of simulation. Higher is better.")
    print("  Idle%     Fraction of total capacity sitting idle (teams with no initiative).")
    print("            Lower is better — idle teams are wasted capacity.")
    print("  Ramp%     Fraction of total capacity spent on team ramp-up after reassignment.")
    print("            Higher means more switching cost from frequent reassignments.")
    print()

    # --- Interpretation guidance ---
    _print_header("Interpretation Guide")
    print()
    print("  Key questions to answer from this campaign:")
    print()
    print("  RQ1: Does attention allocation breadth matter?")
    print("    Compare Idle% across archetypes. If all archetypes have")
    print("      similar Idle%, attention is not the differentiator.")
    print()
    print("  RQ2: When does aggressive stopping help vs. hurt?")
    print("    Compare Aggressive vs. Balanced value delta across environments.")
    print("      Does the advantage hold in all environments?")
    print()
    print("  Look for:")
    print("    - Which regime wins on total value? Is it consistent across environments?")
    print("    - Where do major wins appear? Does Patient generate more?")
    print("    - How does value decomposition differ? (flywheel vs. quick-win vs. right-tail)")
    print("    - Does Aggressive complete more quick-wins but fewer flywheels?")
    print("    - Does Patient build more capability but waste labor on stalled initiatives?")
    print("    - How do frontier exhaustion patterns differ across regimes?")
    print()

    print(f"  Total elapsed: {elapsed:.0f}s ({total_runs} runs)")
    print()


if __name__ == "__main__":
    main()
