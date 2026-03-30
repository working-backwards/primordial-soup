#!/usr/bin/env python
"""Fragility mapping — 3D governance parameter grid sweep.

Maps where major-win discovery collapses across the governance parameter
space. Sweeps confidence_decline_threshold x attention_min x
exec_overrun_threshold while holding other parameters at Balanced
defaults. All three environment families are swept.

This is diagnostic cartography, not policy recommendation. The output
describes the policy surface — it does not evaluate or recommend
governance parameters.

Grid dimensions:
  - confidence_decline_threshold: 7 values (0.15 to 0.45)
  - attention_min: 5 values (0.05 to 0.40)
  - exec_overrun_threshold: 5 values (0.20 to 0.60)
  - Total: 175 points x N seeds x 3 families

Response variables per grid point (averaged across seeds):
  Primary:   surfaced major-win count
  Companion: false-stop rate, right-tail completion rate
  Context:   mean cumulative value, mean terminal capability,
             mean idle fraction

Output:
  - 2D response slices at Balanced-default cross-sections
  - Gradient computation on primary and companion surfaces
  - Cliff identification per family
  - Cross-family comparison
  - Optional CSV export

Usage:
    python scripts/fragility_mapping.py
    python scripts/fragility_mapping.py --seeds 3 --csv fragility.csv
    python scripts/fragility_mapping.py --families balanced_incumbent
    python scripts/fragility_mapping.py --seeds 3  # Quick test

Per plan section B.1.
"""

from __future__ import annotations

import argparse
import csv
import dataclasses
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path

from primordial_soup.config import (
    ReportingConfig,
    SimulationConfiguration,
)
from primordial_soup.diagnostics import compute_false_stop_rate
from primordial_soup.policy import BalancedPolicy, GovernancePolicy
from primordial_soup.presets import (
    EnvironmentFamilyName,
    make_balanced_config,
)
from primordial_soup.runner import run_single_regime

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


# ============================================================================
# Grid configuration
# ============================================================================

# confidence_decline_threshold: 7 values from 0.15 to 0.45.
# Lower = more patient (stops only at very low belief).
# Higher = more aggressive (stops at higher belief).
CONFIDENCE_DECLINE_VALUES: tuple[float, ...] = (
    0.15,
    0.20,
    0.25,
    0.30,
    0.35,
    0.40,
    0.45,
)

# attention_min: 5 values from 0.05 to 0.40.
# Lower = shallower attention floor.
# Higher = deeper minimum attention per initiative.
ATTENTION_MIN_VALUES: tuple[float, ...] = (
    0.05,
    0.10,
    0.15,
    0.25,
    0.40,
)

# exec_overrun_threshold: 5 values from 0.20 to 0.60.
# Lower = more tolerant of execution overrun.
# Higher = stops sooner on execution problems.
EXEC_OVERRUN_VALUES: tuple[float, ...] = (
    0.20,
    0.30,
    0.40,
    0.50,
    0.60,
)

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

# Balanced-default cross-section values for 2D slices.
# These are the Balanced archetype defaults from presets.py.
BALANCED_CDT = 0.30  # confidence_decline_threshold
BALANCED_AMIN = 0.15  # attention_min
BALANCED_EOT = 0.40  # exec_overrun_threshold


# ============================================================================
# Data structures
# ============================================================================


@dataclass(frozen=True)
class GridPoint:
    """A single point in the 3D parameter grid."""

    confidence_decline_threshold: float
    attention_min: float
    exec_overrun_threshold: float


@dataclass
class GridPointResult:
    """Aggregated results for one grid point across seeds."""

    point: GridPoint
    family: str

    # Seed-level accumulators.
    major_win_counts: list[int] = field(default_factory=list)
    false_stop_rates: list[float | None] = field(default_factory=list)
    rt_completion_counts: list[int] = field(default_factory=list)
    cumulative_values: list[float] = field(default_factory=list)
    terminal_capabilities: list[float] = field(default_factory=list)
    idle_fractions: list[float] = field(default_factory=list)

    @property
    def n_seeds(self) -> int:
        return len(self.major_win_counts)

    @property
    def mean_major_wins(self) -> float:
        return sum(self.major_win_counts) / self.n_seeds if self.n_seeds > 0 else 0.0

    @property
    def mean_false_stop_rate(self) -> float | None:
        valid = [r for r in self.false_stop_rates if r is not None]
        return sum(valid) / len(valid) if valid else None

    @property
    def mean_rt_completions(self) -> float:
        return sum(self.rt_completion_counts) / self.n_seeds if self.n_seeds > 0 else 0.0

    @property
    def mean_value(self) -> float:
        return sum(self.cumulative_values) / self.n_seeds if self.n_seeds > 0 else 0.0

    @property
    def mean_capability(self) -> float:
        return sum(self.terminal_capabilities) / self.n_seeds if self.n_seeds > 0 else 0.0

    @property
    def mean_idle(self) -> float:
        return sum(self.idle_fractions) / self.n_seeds if self.n_seeds > 0 else 0.0


# ============================================================================
# Grid execution
# ============================================================================


def make_grid_config(
    point: GridPoint,
    seed: int,
    family: EnvironmentFamilyName,
) -> SimulationConfiguration:
    """Build a SimulationConfiguration for one grid point.

    Starts from the Balanced archetype and overrides the three swept
    parameters. All other parameters are held at Balanced defaults.

    Args:
        point: The grid point parameters.
        seed: World seed.
        family: Environment family.

    Returns:
        SimulationConfiguration for this grid point.
    """
    # Start from Balanced config.
    base = make_balanced_config(seed, family)

    # Override the three swept governance parameters.
    new_governance = dataclasses.replace(
        base.governance,
        confidence_decline_threshold=point.confidence_decline_threshold,
        attention_min=point.attention_min,
        exec_overrun_threshold=point.exec_overrun_threshold,
    )

    # Use lightweight reporting (no per-tick logs, but event logs needed
    # for false-stop rate computation).
    new_reporting = ReportingConfig(
        record_manifest=True,
        record_per_tick_logs=False,
        record_event_log=True,
    )

    return dataclasses.replace(
        base,
        governance=new_governance,
        reporting=new_reporting,
    )


def run_grid_point(
    point: GridPoint,
    seeds: tuple[int, ...],
    family: EnvironmentFamilyName,
) -> GridPointResult:
    """Run all seeds for one grid point and aggregate results.

    Args:
        point: The grid point parameters.
        seeds: World seeds to evaluate.
        family: Environment family.

    Returns:
        GridPointResult with aggregated metrics.
    """
    gpr = GridPointResult(point=point, family=family)
    policy: GovernancePolicy = BalancedPolicy()

    for seed in seeds:
        config = make_grid_config(point, seed, family)
        result, _ = run_single_regime(config, policy)

        # Primary: major-win count.
        gpr.major_win_counts.append(result.major_win_profile.major_win_count)

        # Companion: false-stop rate.
        fsr = compute_false_stop_rate(result)
        gpr.false_stop_rates.append(fsr.false_stop_rate)

        # Companion: RT completion count.
        rt_comp = result.exploration_cost_profile.completed_initiative_count_by_label.get(
            "right_tail", 0
        )
        gpr.rt_completion_counts.append(rt_comp)

        # Context metrics.
        gpr.cumulative_values.append(result.cumulative_value_total)
        gpr.terminal_capabilities.append(result.terminal_capability_t)
        gpr.idle_fractions.append(result.idle_capacity_profile.idle_team_tick_fraction)

    return gpr


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


def _fmt_rate(rate: float | None) -> str:
    if rate is None:
        return "  --"
    return f"{rate * 100:4.0f}%"


# ============================================================================
# 2D slice printing
# ============================================================================


def print_2d_slice_cdt_vs_eot(
    results: dict[tuple[str, GridPoint], GridPointResult],
    family: str,
    attention_min_value: float,
) -> None:
    """Print 2D slice: confidence_decline_threshold vs exec_overrun_threshold.

    Holds attention_min fixed at the given value.
    """
    _print_section(
        f"{FAMILY_LABELS[family]}: Major wins | "
        f"CDT vs EOT (attn_min={attention_min_value:.2f})"
    )

    # Header row: exec_overrun_threshold values.
    header = f"{'CDT':>6s}  " + "  ".join(f"{eot:>6.2f}" for eot in EXEC_OVERRUN_VALUES)
    print(f"  {header}")
    print(f"  {'-' * len(header)}")

    for cdt in CONFIDENCE_DECLINE_VALUES:
        parts = []
        for eot in EXEC_OVERRUN_VALUES:
            point = GridPoint(cdt, attention_min_value, eot)
            gpr = results.get((family, point))
            if gpr is not None:
                parts.append(f"{gpr.mean_major_wins:>6.2f}")
            else:
                parts.append(f"{'--':>6s}")
        print(f"  {cdt:>6.2f}  {'  '.join(parts)}")


def print_2d_slice_cdt_vs_amin(
    results: dict[tuple[str, GridPoint], GridPointResult],
    family: str,
    exec_overrun_value: float,
) -> None:
    """Print 2D slice: confidence_decline_threshold vs attention_min.

    Holds exec_overrun_threshold fixed.
    """
    _print_section(
        f"{FAMILY_LABELS[family]}: Major wins | " f"CDT vs Attn_min (EOT={exec_overrun_value:.2f})"
    )

    header = f"{'CDT':>6s}  " + "  ".join(f"{amin:>6.2f}" for amin in ATTENTION_MIN_VALUES)
    print(f"  {header}")
    print(f"  {'-' * len(header)}")

    for cdt in CONFIDENCE_DECLINE_VALUES:
        parts = []
        for amin in ATTENTION_MIN_VALUES:
            point = GridPoint(cdt, amin, exec_overrun_value)
            gpr = results.get((family, point))
            if gpr is not None:
                parts.append(f"{gpr.mean_major_wins:>6.2f}")
            else:
                parts.append(f"{'--':>6s}")
        print(f"  {cdt:>6.2f}  {'  '.join(parts)}")


def print_fsr_slice_cdt_vs_eot(
    results: dict[tuple[str, GridPoint], GridPointResult],
    family: str,
    attention_min_value: float,
) -> None:
    """Print 2D FSR slice: confidence_decline_threshold vs exec_overrun."""
    _print_section(
        f"{FAMILY_LABELS[family]}: False-stop rate | "
        f"CDT vs EOT (attn_min={attention_min_value:.2f})"
    )

    header = f"{'CDT':>6s}  " + "  ".join(f"{eot:>6.2f}" for eot in EXEC_OVERRUN_VALUES)
    print(f"  {header}")
    print(f"  {'-' * len(header)}")

    for cdt in CONFIDENCE_DECLINE_VALUES:
        parts = []
        for eot in EXEC_OVERRUN_VALUES:
            point = GridPoint(cdt, attention_min_value, eot)
            gpr = results.get((family, point))
            if gpr is not None:
                parts.append(f"{_fmt_rate(gpr.mean_false_stop_rate):>6s}")
            else:
                parts.append(f"{'--':>6s}")
        print(f"  {cdt:>6.2f}  {'  '.join(parts)}")


# ============================================================================
# Gradient and cliff detection
# ============================================================================


def compute_gradient_along_cdt(
    results: dict[tuple[str, GridPoint], GridPointResult],
    family: str,
    attention_min_value: float,
    exec_overrun_value: float,
) -> list[tuple[float, float, float]]:
    """Compute gradient of major-win count along CDT axis.

    Returns list of (cdt_midpoint, delta_major_wins, delta_cdt) tuples.
    """
    gradients: list[tuple[float, float, float]] = []
    for i in range(1, len(CONFIDENCE_DECLINE_VALUES)):
        cdt_lo = CONFIDENCE_DECLINE_VALUES[i - 1]
        cdt_hi = CONFIDENCE_DECLINE_VALUES[i]
        point_lo = GridPoint(cdt_lo, attention_min_value, exec_overrun_value)
        point_hi = GridPoint(cdt_hi, attention_min_value, exec_overrun_value)
        gpr_lo = results.get((family, point_lo))
        gpr_hi = results.get((family, point_hi))
        if gpr_lo is not None and gpr_hi is not None:
            delta_mw = gpr_hi.mean_major_wins - gpr_lo.mean_major_wins
            delta_cdt = cdt_hi - cdt_lo
            midpoint = (cdt_lo + cdt_hi) / 2
            gradients.append((midpoint, delta_mw, delta_cdt))
    return gradients


def print_gradient_analysis(
    results: dict[tuple[str, GridPoint], GridPointResult],
    families: tuple[EnvironmentFamilyName, ...],
) -> None:
    """Print gradient analysis along CDT axis at Balanced cross-section."""
    _print_section("Gradient: major wins along CDT axis (Balanced cross-section)")

    for family in families:
        gradients = compute_gradient_along_cdt(results, family, BALANCED_AMIN, BALANCED_EOT)
        print(f"\n  {FAMILY_LABELS[family]}:")
        print(f"    {'CDT mid':>8s}  {'dMW':>8s}  {'dMW/dCDT':>10s}  {'Cliff?':>8s}")
        for mid, delta_mw, delta_cdt in gradients:
            rate = delta_mw / delta_cdt if delta_cdt != 0 else 0
            # A cliff is a large negative gradient (major wins drop sharply
            # as CDT increases = governance gets more aggressive).
            is_cliff = "  ***" if rate < -5.0 else ""
            print(f"    {mid:>8.3f}  {delta_mw:>+8.2f}  {rate:>+10.1f}{is_cliff}")


# ============================================================================
# Cross-family comparison
# ============================================================================


def print_cross_family_comparison(
    results: dict[tuple[str, GridPoint], GridPointResult],
    families: tuple[EnvironmentFamilyName, ...],
) -> None:
    """Print cross-family comparison at key grid points."""
    _print_section("Cross-family comparison at key grid points")

    key_points = [
        ("Most patient", GridPoint(0.15, 0.05, 0.20)),
        ("Balanced default", GridPoint(BALANCED_CDT, BALANCED_AMIN, BALANCED_EOT)),
        ("Most aggressive", GridPoint(0.45, 0.40, 0.60)),
    ]

    header = f"  {'Point':>20s}  " + "  ".join(f"{FAMILY_LABELS[f]:>14s}" for f in families)
    print(header)
    print(f"  {'-' * (len(header) - 2)}")

    for label, point in key_points:
        parts = []
        for family in families:
            gpr = results.get((family, point))
            if gpr is not None:
                mw = gpr.mean_major_wins
                fsr = gpr.mean_false_stop_rate
                parts.append(f"MW={mw:.1f} FSR={_fmt_rate(fsr)}")
            else:
                parts.append(f"{'--':>14s}")
        print(f"  {label:>20s}  " + "  ".join(f"{p:>14s}" for p in parts))


# ============================================================================
# CSV export
# ============================================================================


def export_csv(
    results: dict[tuple[str, GridPoint], GridPointResult],
    path: Path,
) -> None:
    """Export all grid point results to CSV."""
    rows = sorted(results.values(), key=lambda r: (r.family, r.point))

    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "family",
                "confidence_decline_threshold",
                "attention_min",
                "exec_overrun_threshold",
                "n_seeds",
                "mean_major_wins",
                "mean_false_stop_rate",
                "mean_rt_completions",
                "mean_cumulative_value",
                "mean_terminal_capability",
                "mean_idle_fraction",
            ]
        )
        for gpr in rows:
            writer.writerow(
                [
                    gpr.family,
                    gpr.point.confidence_decline_threshold,
                    gpr.point.attention_min,
                    gpr.point.exec_overrun_threshold,
                    gpr.n_seeds,
                    f"{gpr.mean_major_wins:.4f}",
                    f"{gpr.mean_false_stop_rate:.4f}"
                    if gpr.mean_false_stop_rate is not None
                    else "",
                    f"{gpr.mean_rt_completions:.4f}",
                    f"{gpr.mean_value:.4f}",
                    f"{gpr.mean_capability:.4f}",
                    f"{gpr.mean_idle:.4f}",
                ]
            )
    print(f"\n  CSV exported to: {path}")


# ============================================================================
# Main
# ============================================================================


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fragility mapping: 3D governance parameter grid sweep.",
    )
    parser.add_argument(
        "--seeds",
        type=int,
        default=7,
        help="Number of seeds per grid point (default: 7).",
    )
    parser.add_argument(
        "--families",
        type=str,
        nargs="+",
        default=None,
        help="Environment families (default: all three).",
    )
    parser.add_argument(
        "--csv",
        type=str,
        default=None,
        help="Export results to CSV file.",
    )
    args = parser.parse_args()

    n_seeds: int = args.seeds
    families: tuple[EnvironmentFamilyName, ...] = (
        tuple(args.families) if args.families else FAMILIES
    )
    seeds = tuple(range(42, 42 + n_seeds))

    n_grid_points = (
        len(CONFIDENCE_DECLINE_VALUES) * len(ATTENTION_MIN_VALUES) * len(EXEC_OVERRUN_VALUES)
    )
    total_runs = n_grid_points * n_seeds * len(families)

    _print_header("Fragility Mapping: 3D Governance Parameter Sweep")
    print(
        f"  Grid: {len(CONFIDENCE_DECLINE_VALUES)} CDT x "
        f"{len(ATTENTION_MIN_VALUES)} attn_min x "
        f"{len(EXEC_OVERRUN_VALUES)} EOT = {n_grid_points} points"
    )
    print(f"  Families:   {[FAMILY_LABELS[f] for f in families]}")
    print(f"  Seeds:      {n_seeds} per point")
    print(f"  Total runs: {total_runs}")
    print()

    t0 = time.time()

    # --- Build and run grid ---
    results: dict[tuple[str, GridPoint], GridPointResult] = {}
    run_count = 0

    for family in families:
        family_t0 = time.time()
        print(f"  Family: {FAMILY_LABELS[family]}")

        for cdt in CONFIDENCE_DECLINE_VALUES:
            for amin in ATTENTION_MIN_VALUES:
                for eot in EXEC_OVERRUN_VALUES:
                    point = GridPoint(cdt, amin, eot)
                    gpr = run_grid_point(point, seeds, family)
                    results[(family, point)] = gpr
                    run_count += n_seeds

            # Progress update per CDT row.
            pct = run_count / total_runs * 100
            elapsed = time.time() - t0
            print(
                f"    CDT={cdt:.2f} done  "
                f"({run_count}/{total_runs} runs, {pct:.0f}%, "
                f"{elapsed:.0f}s elapsed)",
                flush=True,
            )

        family_elapsed = time.time() - family_t0
        print(f"    Family complete in {family_elapsed:.0f}s")

    total_elapsed = time.time() - t0

    # --- Print results ---
    _print_header("Results")

    # 2D slices at Balanced-default cross-sections.
    for family in families:
        # Major wins: CDT vs EOT at default attn_min.
        print_2d_slice_cdt_vs_eot(results, family, BALANCED_AMIN)
        # Major wins: CDT vs attn_min at default EOT.
        print_2d_slice_cdt_vs_amin(results, family, BALANCED_EOT)
        # False-stop rate: CDT vs EOT at default attn_min.
        print_fsr_slice_cdt_vs_eot(results, family, BALANCED_AMIN)

    # Gradient analysis.
    print_gradient_analysis(results, families)

    # Cross-family comparison.
    print_cross_family_comparison(results, families)

    # CSV export. Write under results/ per CLAUDE.md Script Output Conventions.
    if args.csv:
        from script_utils import create_results_dir

        csv_path = Path(args.csv)
        if csv_path.parent == Path("."):
            # Bare filename — place it in a timestamped results dir.
            output_dir = create_results_dir("fragility")
            csv_path = output_dir / csv_path.name
        export_csv(results, csv_path)

    # Summary.
    _print_section("Summary")
    print(f"  Total runs: {total_runs}")
    print(f"  Total elapsed: {total_elapsed:.0f}s")
    print(f"  Mean time per run: {total_elapsed / total_runs:.2f}s")
    print()


if __name__ == "__main__":
    main()
