"""Validate environment families against the three governance archetypes.

Usage:
    python scripts/validate_environment_families.py

Runs each named environment family against the three governance archetypes
for a small seed panel. Prints a compact summary table showing key metrics
that confirm whether the family mechanisms are firing correctly:
    - Pool not exhausted
    - Right-tail major wins are non-zero but rare
    - Idle capacity is reasonable

This is a validation tool, not an optimization tool. Families are intended
to be defined, validated, then frozen before the comparative campaign.
"""

from __future__ import annotations

import logging
import sys
import time
from collections.abc import Callable
from typing import TYPE_CHECKING

from primordial_soup.config import SimulationConfiguration
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

# Type alias for archetype config factory callables.
# Each factory takes (world_seed, family) and returns SimulationConfiguration.
ConfigFactory = Callable[..., SimulationConfiguration]

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Small seed panel for quick validation. Three seeds give enough spread
# to detect systematic failures without consuming excessive wall time.
SEED_PANEL: tuple[int, ...] = (42, 123, 999)

# Environment families to validate (all three canonical families).
FAMILIES: tuple[EnvironmentFamilyName, ...] = (
    "balanced_incumbent",
    "short_cycle_throughput",
    "discovery_heavy",
)

# Archetype definitions: (display_name, config_factory, policy_instance).
# Config factories accept (world_seed, family) and return a
# SimulationConfiguration. Policies are stateless protocol implementors.
ARCHETYPES: tuple[tuple[str, ConfigFactory, GovernancePolicy], ...] = (
    ("Balanced", make_balanced_config, BalancedPolicy()),
    ("Aggressive Stop-Loss", make_aggressive_stop_loss_config, AggressiveStopLossPolicy()),
    ("Patient Moonshot", make_patient_moonshot_config, PatientMoonshotPolicy()),
)

# Configure logging: INFO for progress messages, WARNING for library noise.
logging.basicConfig(
    level=logging.WARNING,
    format="%(levelname)s %(name)s: %(message)s",
    stream=sys.stderr,
)
# The runner logs at INFO; keep it at WARNING to avoid flooding the console
# during a multi-run validation. Promote to INFO for debugging.
logging.getLogger("primordial_soup.runner").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Per-cell result container
# ---------------------------------------------------------------------------


class CellResult:
    """Aggregated metrics for one (family, archetype) cell across seeds.

    Stores per-seed RunResult references and computes cross-seed
    summary statistics on demand.
    """

    def __init__(self, results: list[RunResult]) -> None:
        self.results = results

    @property
    def seed_count(self) -> int:
        return len(self.results)

    # --- Pool exhaustion ---

    def exhaustion_ticks(self) -> list[int | None]:
        """Pool exhaustion tick for each seed (None if no exhaustion)."""
        return [r.idle_capacity_profile.pool_exhaustion_tick for r in self.results]

    def any_exhausted(self) -> bool:
        """True if any seed experienced pool exhaustion."""
        return any(t is not None for t in self.exhaustion_ticks())

    def exhaustion_summary(self) -> str:
        """Compact string: 'no' if none exhausted, else comma-separated ticks."""
        ticks = self.exhaustion_ticks()
        if not self.any_exhausted():
            return "no"
        return ", ".join(str(t) if t is not None else "no" for t in ticks)

    # --- Right-tail completions ---

    def right_tail_completions(self) -> list[int]:
        """Count of completed right-tail initiatives per seed."""
        return [
            r.exploration_cost_profile.completed_initiative_count_by_label.get("right_tail", 0)
            for r in self.results
        ]

    def total_right_tail_completions(self) -> int:
        return sum(self.right_tail_completions())

    # --- Major wins ---

    def major_win_counts(self) -> list[int]:
        """Major-win count per seed."""
        return [r.major_win_profile.major_win_count for r in self.results]

    def total_major_wins(self) -> int:
        return sum(self.major_win_counts())

    # --- Conditional major-win rate ---

    def conditional_major_win_rate(self) -> float | None:
        """Major wins / right-tail completions, or None if no completions."""
        completions = self.total_right_tail_completions()
        if completions == 0:
            return None
        return self.total_major_wins() / completions

    def conditional_major_win_rate_str(self) -> str:
        """Formatted percentage or 'N/A'."""
        rate = self.conditional_major_win_rate()
        if rate is None:
            return "N/A"
        return f"{rate:.1%}"

    # --- Terminal capability (average across seeds) ---

    def mean_terminal_capability(self) -> float:
        return sum(r.terminal_capability_t for r in self.results) / self.seed_count

    # --- Idle fraction (average across seeds) ---

    def mean_idle_fraction(self) -> float:
        return (
            sum(r.idle_capacity_profile.idle_team_tick_fraction for r in self.results)
            / self.seed_count
        )


# ---------------------------------------------------------------------------
# Main validation logic
# ---------------------------------------------------------------------------


def run_validation() -> dict[tuple[str, str], CellResult]:
    """Run all (family, archetype, seed) combinations and return results.

    Returns:
        Dict mapping (family_name, archetype_name) to CellResult.
    """
    all_cells: dict[tuple[str, str], CellResult] = {}
    total_runs = len(FAMILIES) * len(ARCHETYPES) * len(SEED_PANEL)
    run_index = 0

    for family in FAMILIES:
        for archetype_name, config_factory, policy in ARCHETYPES:
            seed_results: list[RunResult] = []

            for seed in SEED_PANEL:
                run_index += 1
                print(
                    f"  [{run_index}/{total_runs}] {family} x {archetype_name} (seed={seed}) ...",
                    flush=True,
                )

                # Build configuration for this (family, archetype, seed).
                config = config_factory(world_seed=seed, family=family)

                # Run the simulation.
                result, _ = run_single_regime(config, policy)
                seed_results.append(result)

            all_cells[(family, archetype_name)] = CellResult(seed_results)

    return all_cells


def print_summary_table(cells: dict[tuple[str, str], CellResult]) -> None:
    """Print a compact summary table to stdout.

    Columns:
        Family | Archetype | Exhausted? | RT Compl | RT Wins | MW Rate | Capability | Idle %
    """
    # Column headers and widths.
    headers = [
        ("Family", 24),
        ("Archetype", 22),
        ("Exhausted?", 12),
        ("RT Compl", 10),
        ("RT Wins", 9),
        ("MW Rate", 9),
        ("Capability", 12),
        ("Idle %", 8),
    ]

    # Print header row.
    header_line = "  ".join(h.ljust(w) for h, w in headers)
    print(header_line)
    print("-" * len(header_line))

    # Print data rows.
    for family in FAMILIES:
        for archetype_name, _, _ in ARCHETYPES:
            cell = cells[(family, archetype_name)]

            row_values = [
                family.ljust(24),
                archetype_name.ljust(22),
                cell.exhaustion_summary().ljust(12),
                str(cell.total_right_tail_completions()).ljust(10),
                str(cell.total_major_wins()).ljust(9),
                cell.conditional_major_win_rate_str().ljust(9),
                f"{cell.mean_terminal_capability():.4f}".ljust(12),
                f"{cell.mean_idle_fraction():.1%}".ljust(8),
            ]
            print("  ".join(row_values))

        # Blank line between families for readability.
        print()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Run the full environment family validation."""
    print()
    print("=" * 78)
    print("  Environment Family Validation")
    print("  Families: " + ", ".join(FAMILIES))
    print("  Archetypes: " + ", ".join(name for name, _, _ in ARCHETYPES))
    print(f"  Seeds: {SEED_PANEL}")
    print(
        f"  Total runs: "
        f"{len(FAMILIES)} families x {len(ARCHETYPES)} archetypes x "
        f"{len(SEED_PANEL)} seeds = "
        f"{len(FAMILIES) * len(ARCHETYPES) * len(SEED_PANEL)}"
    )
    print("=" * 78)
    print()

    start_time = time.monotonic()
    cells = run_validation()
    elapsed = time.monotonic() - start_time

    print()
    print("=" * 78)
    print("  Summary Table")
    print("=" * 78)
    print()
    print_summary_table(cells)

    # --- Validation notes ---
    print("-" * 78)
    print("Column guide:")
    print("  Exhausted?   Pool exhaustion ticks per seed ('no' = none)")
    print("  RT Compl     Right-tail completions (summed across seeds)")
    print("  RT Wins      Right-tail major wins (summed across seeds)")
    print("  MW Rate      Major wins / right-tail completions (conditional)")
    print("  Capability   Terminal portfolio capability (mean across seeds)")
    print("  Idle %       Idle team-tick fraction (mean across seeds)")
    print()
    print(
        "Acceptance target: 0.5% <= observed_completed_conditional_major_win_rate "
        "<= 5% for balanced_incumbent"
    )
    print()
    print(f"Completed in {elapsed:.1f}s.")


if __name__ == "__main__":
    main()
