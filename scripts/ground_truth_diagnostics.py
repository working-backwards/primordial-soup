#!/usr/bin/env python
"""Ground-truth diagnostic metrics across archetypes and families.

Runs all 3 archetypes × 3 families × N seeds and computes all five
ground-truth diagnostic metrics for each cell. Reports comparison
tables showing how governance regimes differ in their treatment of
major-win-eligible initiatives.

The five metrics:
  1. False-stop rate on eventual major wins
  2. Survival curve to revelation (summary statistics)
  3. Belief-at-stop distribution for major-win-eligible
  4. Attention-conditioned false negatives
  5. Hazard of stop by staffed tick

Usage:
    python scripts/ground_truth_diagnostics.py
    python scripts/ground_truth_diagnostics.py --seeds 10
    python scripts/ground_truth_diagnostics.py --families balanced_incumbent

Per plan §A.2.3.
"""

from __future__ import annotations

import argparse
import logging
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from primordial_soup.config import ReportingConfig, SimulationConfiguration
from primordial_soup.diagnostics import (
    compute_belief_at_stop,
    compute_false_stop_rate,
)
from primordial_soup.policy import (
    AggressiveStopLossPolicy,
    BalancedPolicy,
    GovernancePolicy,
    PatientMoonshotPolicy,
)
from primordial_soup.presets import (
    EnvironmentFamilyName,
    make_aggressive_stop_loss_config,
    make_balanced_config,
    make_patient_moonshot_config,
)
from primordial_soup.runner import run_single_regime

if TYPE_CHECKING:
    from primordial_soup.reporting import RunResult

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


# ============================================================================
# Configuration
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

# Archetype definitions: (id, label, config_factory, policy_factory).
ARCHETYPES: tuple[tuple[str, str, type, type], ...] = (
    ("balanced", "Balanced", type(None), type(None)),  # Placeholder, replaced below
    ("aggressive", "Aggressive", type(None), type(None)),
    ("patient", "Patient", type(None), type(None)),
)


def _make_config_and_policy(
    archetype: str,
    seed: int,
    family: EnvironmentFamilyName,
) -> tuple[SimulationConfiguration, GovernancePolicy]:
    """Build config and policy for an archetype × family × seed."""
    # Override reporting to include event logs (needed for diagnostics).
    import dataclasses

    if archetype == "balanced":
        config = make_balanced_config(seed, family)
        policy: GovernancePolicy = BalancedPolicy()
    elif archetype == "aggressive":
        config = make_aggressive_stop_loss_config(seed, family)
        policy = AggressiveStopLossPolicy()
    elif archetype == "patient":
        config = make_patient_moonshot_config(seed, family)
        policy = PatientMoonshotPolicy()
    else:
        raise ValueError(f"Unknown archetype: {archetype!r}")

    # Ensure event logs are recorded (needed for diagnostics).
    config = dataclasses.replace(
        config,
        reporting=ReportingConfig(
            record_manifest=True,
            record_per_tick_logs=False,
            record_event_log=True,
        ),
    )
    return config, policy


ARCHETYPE_IDS = ("balanced", "aggressive", "patient")
ARCHETYPE_LABELS: dict[str, str] = {
    "balanced": "Balanced",
    "aggressive": "Aggressive",
    "patient": "Patient",
}


# ============================================================================
# Per-cell diagnostic aggregation
# ============================================================================


@dataclass
class CellDiagnostics:
    """Aggregated diagnostics across seeds for one archetype × family cell."""

    # Metric 1: False-stop rate.
    false_stop_rates: list[float | None] = field(default_factory=list)
    total_eligible: list[int] = field(default_factory=list)
    total_stopped_eligible: list[int] = field(default_factory=list)
    total_completed_eligible: list[int] = field(default_factory=list)

    # Metric 2: Survival curve summary.
    # We store median survival staffed tick per seed.
    rt_stop_tick_lists: list[list[int]] = field(default_factory=list)

    # Metric 3: Belief-at-stop.
    all_beliefs: list[float] = field(default_factory=list)

    # Metric 5: Stop hazard.
    all_stop_ticks: list[int] = field(default_factory=list)

    # Counts.
    major_win_counts: list[int] = field(default_factory=list)
    rt_completion_counts: list[int] = field(default_factory=list)
    rt_stop_counts: list[int] = field(default_factory=list)


def aggregate_seed_diagnostics(
    result: RunResult,
    cell: CellDiagnostics,
) -> None:
    """Compute all diagnostics for one seed and append to the cell aggregator."""
    # Metric 1: False-stop rate.
    fsr = compute_false_stop_rate(result)
    cell.false_stop_rates.append(fsr.false_stop_rate)
    cell.total_eligible.append(fsr.total_major_win_eligible)
    cell.total_stopped_eligible.append(fsr.stopped_major_win_eligible)
    cell.total_completed_eligible.append(fsr.completed_major_win_eligible)

    # Metric 2: Survival curve — collect stop ticks for RT initiatives.
    seed_stop_ticks: list[int] = []
    if result.stop_event_log is not None:
        from primordial_soup.diagnostics import build_config_map, is_right_tail

        config_map = build_config_map(result)
        for event in result.stop_event_log:
            cfg = config_map.get(event.initiative_id)
            if cfg is not None and is_right_tail(cfg):
                seed_stop_ticks.append(event.staffed_ticks)
    cell.rt_stop_tick_lists.append(seed_stop_ticks)

    # Metric 3: Belief-at-stop.
    bas = compute_belief_at_stop(result)
    cell.all_beliefs.extend(bas.beliefs)

    # Metric 5: Stop hazard — collect all RT stop staffed ticks.
    cell.all_stop_ticks.extend(seed_stop_ticks)

    # Counts.
    cell.major_win_counts.append(result.major_win_profile.major_win_count)
    cell.rt_completion_counts.append(
        result.exploration_cost_profile.completed_initiative_count_by_label.get("right_tail", 0)
    )
    cell.rt_stop_counts.append(
        result.exploration_cost_profile.stopped_initiative_count_by_label.get("right_tail", 0)
    )


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


def _safe_mean(values: list[float | None]) -> float | None:
    """Mean of non-None values, or None if all are None."""
    valid = [v for v in values if v is not None]
    return sum(valid) / len(valid) if valid else None


def _fmt_rate(rate: float | None) -> str:
    """Format a rate as percentage or '--'."""
    if rate is None:
        return "--"
    return f"{rate * 100:.1f}%"


def _fmt_float(val: float | None, precision: int = 2) -> str:
    """Format a float or '--'."""
    if val is None:
        return "--"
    return f"{val:.{precision}f}"


# ============================================================================
# Report printing
# ============================================================================


def print_overview_table(
    results: dict[tuple[str, str], CellDiagnostics],
    families: tuple[EnvironmentFamilyName, ...],
    n_seeds: int,
) -> None:
    """Print the overview table: counts and false-stop rates."""
    _print_section("Overview: RT outcomes and false-stop rate (mean across seeds)")

    header = (
        f"{'Family':>14s}  {'Policy':>12s}  "
        f"{'MW/run':>6s}  {'RTComp':>6s}  {'RTStop':>6s}  "
        f"{'Eligible':>8s}  {'StopElig':>8s}  {'FSR':>6s}"
    )
    print(header)
    print("-" * len(header))

    for family in families:
        for arch in ARCHETYPE_IDS:
            cell = results[(family, arch)]
            n = n_seeds
            mean_mw = sum(cell.major_win_counts) / n
            mean_rtc = sum(cell.rt_completion_counts) / n
            mean_rts = sum(cell.rt_stop_counts) / n
            mean_elig = sum(cell.total_eligible) / n
            mean_stop_elig = sum(cell.total_stopped_eligible) / n
            mean_fsr = _safe_mean(cell.false_stop_rates)

            print(
                f"{FAMILY_LABELS[family]:>14s}  {ARCHETYPE_LABELS[arch]:>12s}  "
                f"{mean_mw:>6.2f}  {mean_rtc:>6.1f}  {mean_rts:>6.1f}  "
                f"{mean_elig:>8.1f}  {mean_stop_elig:>8.1f}  {_fmt_rate(mean_fsr):>6s}"
            )
        if family != families[-1]:
            print()


def print_belief_at_stop_table(
    results: dict[tuple[str, str], CellDiagnostics],
    families: tuple[EnvironmentFamilyName, ...],
) -> None:
    """Print belief-at-stop distribution for eligible stops."""
    _print_section("Belief-at-stop for major-win-eligible (pooled across seeds)")

    header = (
        f"{'Family':>14s}  {'Policy':>12s}  "
        f"{'Count':>5s}  {'Mean':>6s}  {'Min':>6s}  {'Max':>6s}"
    )
    print(header)
    print("-" * len(header))

    for family in families:
        for arch in ARCHETYPE_IDS:
            cell = results[(family, arch)]
            beliefs = cell.all_beliefs
            count = len(beliefs)
            mean_b = sum(beliefs) / count if count > 0 else None
            min_b = min(beliefs) if count > 0 else None
            max_b = max(beliefs) if count > 0 else None

            print(
                f"{FAMILY_LABELS[family]:>14s}  {ARCHETYPE_LABELS[arch]:>12s}  "
                f"{count:>5d}  {_fmt_float(mean_b):>6s}  "
                f"{_fmt_float(min_b):>6s}  {_fmt_float(max_b):>6s}"
            )
        if family != families[-1]:
            print()


def print_stop_hazard_table(
    results: dict[tuple[str, str], CellDiagnostics],
    families: tuple[EnvironmentFamilyName, ...],
) -> None:
    """Print stop hazard by staffed-tick bin (pooled across seeds)."""
    _print_section("RT stop hazard by staffed-tick bin (pooled across seeds)")

    bin_width = 20
    max_tick = 200
    n_bins = max_tick // bin_width

    # Print bin headers.
    bin_labels = [f"{i * bin_width}-{(i + 1) * bin_width - 1}" for i in range(n_bins)]
    header = f"{'Family':>14s}  {'Policy':>12s}  " + "  ".join(f"{bl:>7s}" for bl in bin_labels)
    print(header)
    print("-" * len(header))

    for family in families:
        for arch in ARCHETYPE_IDS:
            cell = results[(family, arch)]
            stop_ticks = cell.all_stop_ticks
            total = len(stop_ticks)

            # Bin the stops.
            bin_counts = [0] * n_bins
            for t in stop_ticks:
                idx = min(t // bin_width, n_bins - 1)
                bin_counts[idx] += 1

            parts = []
            for c in bin_counts:
                pct = c / total * 100 if total > 0 else 0
                parts.append(f"{pct:>6.1f}%")

            print(
                f"{FAMILY_LABELS[family]:>14s}  {ARCHETYPE_LABELS[arch]:>12s}  " + "  ".join(parts)
            )
        if family != families[-1]:
            print()


def print_metric_guide() -> None:
    """Print interpretation guidance for the metrics."""
    _print_section("Metric Guide")
    print()
    print("  MW/run:     Mean major wins surfaced per run (higher = more discovery)")
    print("  RTComp:     Mean right-tail completions per run")
    print("  RTStop:     Mean right-tail stops per run")
    print("  Eligible:   Mean major-win-eligible initiatives in pool")
    print("  StopElig:   Mean eligible initiatives stopped (false stops)")
    print("  FSR:        False-stop rate = StopElig / Eligible")
    print("              High FSR = governance kills potential breakthroughs")
    print()
    print("  Belief-at-stop: quality_belief_t when eligible initiatives are stopped")
    print("    Low mean belief: stops are rational responses to declining signals")
    print("    High mean belief: stops are premature (information failure)")
    print()
    print("  Stop hazard: fraction of RT stops in each staffed-tick bin")
    print("    Early clustering: stops before beliefs have time to mature")
    print("    Spread across bins: stops are information-driven")
    print()


# ============================================================================
# Main
# ============================================================================


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ground-truth diagnostic metrics.",
    )
    parser.add_argument(
        "--seeds",
        type=int,
        default=7,
        help="Number of seeds per cell (default: 7).",
    )
    parser.add_argument(
        "--families",
        type=str,
        nargs="+",
        default=None,
        help="Environment families (default: all three).",
    )
    args = parser.parse_args()

    n_seeds: int = args.seeds
    families: tuple[EnvironmentFamilyName, ...] = (
        tuple(args.families) if args.families else FAMILIES
    )
    seeds = tuple(range(42, 42 + n_seeds))
    total_runs = len(ARCHETYPE_IDS) * len(families) * n_seeds

    _print_header("Ground-Truth Diagnostic Metrics")
    print(f"  Archetypes: {[ARCHETYPE_LABELS[a] for a in ARCHETYPE_IDS]}")
    print(f"  Families:   {[FAMILY_LABELS[f] for f in families]}")
    print(f"  Seeds:      {list(seeds)} ({n_seeds} per cell)")
    print(f"  Total runs: {total_runs}")
    print()

    t0 = time.time()

    # --- Run all cells ---
    results: dict[tuple[str, str], CellDiagnostics] = {}
    for family in families:
        for arch in ARCHETYPE_IDS:
            label = f"{FAMILY_LABELS[family]} / {ARCHETYPE_LABELS[arch]}"
            print(f"  Running {label} ({n_seeds} seeds)...", end="", flush=True)
            cell_t0 = time.time()

            cell = CellDiagnostics()
            for seed in seeds:
                config, policy = _make_config_and_policy(arch, seed, family)
                run_result, _ = run_single_regime(config, policy)
                aggregate_seed_diagnostics(run_result, cell)

            results[(family, arch)] = cell
            cell_elapsed = time.time() - cell_t0
            print(f" {cell_elapsed:.1f}s")

    elapsed = time.time() - t0

    # --- Print results ---
    _print_header("Diagnostic Results")
    print_overview_table(results, families, n_seeds)
    print_belief_at_stop_table(results, families)
    print_stop_hazard_table(results, families)
    print_metric_guide()

    print(f"  Total elapsed: {elapsed:.0f}s ({total_runs} runs)")
    print()


if __name__ == "__main__":
    main()
