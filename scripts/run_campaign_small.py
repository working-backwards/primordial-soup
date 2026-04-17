"""Run a small validation campaign (23 configs x 3 seeds = 69 runs).

Usage:
    python scripts/run_campaign_small.py

This script demonstrates how to define and run a campaign — the core
experimental tool of the Primordial Soup study. A campaign generates
governance configurations via Latin Hypercube Sampling (LHS), adds
the three named archetype anchor points, then runs every configuration
against multiple world seeds.

The results are printed as a summary and saved as a timestamped JSON
file under results/ (e.g. results/campaign_2026_03_12_14_30_05.json).
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from primordial_soup.campaign import (
    CampaignSpec,
    GovernanceSweepSpec,
    make_default_parameter_bounds,
    run_campaign,
)
from primordial_soup.manifest import campaign_result_to_dict
from primordial_soup.policy import (
    AggressiveStopLossPolicy,
    BalancedPolicy,
    GovernancePolicy,
    PatientMoonshotPolicy,
)
from primordial_soup.presets import make_baseline_environment_spec

if TYPE_CHECKING:
    from primordial_soup.config import GovernanceConfig

# Configure logging so you can see per-run progress.
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


def policy_factory(gov_config: GovernanceConfig) -> GovernancePolicy:
    """Map a GovernanceConfig to the appropriate policy implementation.

    LHS sweep points use BalancedPolicy as a generic policy — the
    governance CONFIG parameters vary across sweep points, but the
    policy LOGIC (how those parameters are applied) is shared.
    The three named archetypes get their own policy classes.
    """
    policy_map: dict[str, GovernancePolicy] = {
        "balanced": BalancedPolicy(),
        "aggressive_stop_loss": AggressiveStopLossPolicy(),
        "patient_moonshot": PatientMoonshotPolicy(),
    }
    return policy_map.get(gov_config.policy_id, BalancedPolicy())


# ---------------------------------------------------------------------------
# Build the campaign spec
# ---------------------------------------------------------------------------

# The baseline environment: 313-tick horizon, 8 teams, 200 initiatives.
environment = make_baseline_environment_spec()

# Governance sweep: 20 LHS sample points + 3 archetype anchors = 23 configs.
# (The recommended minimum for production is 80+ LHS points; 20 is fine
# for a quick validation run.)
sweep = GovernanceSweepSpec(
    parameter_bounds=make_default_parameter_bounds(),
    lhs_sample_count=20,
    design_seed=2024,
    include_archetype_anchors=True,
)

# Three world seeds for replication.
# Total runs = 23 configs x 3 seeds = 69 runs.
campaign_spec = CampaignSpec(
    campaign_id="getting_started_validation",
    description="Small validation campaign for the getting-started guide.",
    environment=environment,
    governance_sweep=sweep,
    world_seeds=(42, 123, 999),
)

# ---------------------------------------------------------------------------
# Run the campaign
# ---------------------------------------------------------------------------

print(f"Running campaign: {campaign_spec.campaign_id}")
print(f"  LHS sample points: {sweep.lhs_sample_count}")
print("  Archetype anchors: 3")
print(f"  World seeds:       {len(campaign_spec.world_seeds)}")
print(f"  Total runs:        {(sweep.lhs_sample_count + 3) * len(campaign_spec.world_seeds)}")
print()

result = run_campaign(campaign_spec, policy_factory)

# ---------------------------------------------------------------------------
# Print summary
# ---------------------------------------------------------------------------

print()
print("=" * 60)
print(f"Campaign complete: {result.total_runs} runs")
print("=" * 60)
print()

# Summary statistics across all runs.
values = [rr.cumulative_value_total for rr in result.run_results]
print("Value across all runs:")
print(f"  Min:    {min(values):.2f}")
print(f"  Max:    {max(values):.2f}")
print(f"  Mean:   {sum(values) / len(values):.2f}")
print()

# Metric legend — printed once so readers know what each line means.
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

# Per-archetype breakdown. The last 3 governance configs are the
# archetypes (Balanced, Aggressive, Patient), each run against all
# world seeds.
archetype_names = ["Balanced", "Aggressive Stop-Loss", "Patient Moonshot"]
num_seeds = len(campaign_spec.world_seeds)
num_archetypes = 3
archetype_runs = result.run_results[-(num_archetypes * num_seeds) :]

for i, name in enumerate(archetype_names):
    runs = archetype_runs[i * num_seeds : (i + 1) * num_seeds]
    n = len(runs)
    avg_value = sum(rr.cumulative_value_total for rr in runs) / n
    avg_idle = sum(rr.idle_capacity_profile.idle_team_tick_fraction for rr in runs) / n
    total_wins = sum(rr.major_win_profile.major_win_count for rr in runs)
    exhaustions = [rr.idle_capacity_profile.pool_exhaustion_tick for rr in runs]
    avg_max_cap = sum(rr.max_portfolio_capability_t for rr in runs) / n
    avg_term_cap = sum(rr.terminal_capability_t for rr in runs) / n
    avg_residual_rate = sum(rr.terminal_aggregate_residual_rate for rr in runs) / n
    avg_belief_mae = sum(rr.belief_accuracy.mean_absolute_belief_error for rr in runs) / n
    print(f"{name}:")
    print(f"  Avg cumulative value:  {avg_value:.2f}")
    print(f"  Avg idle team-tick %:  {avg_idle:.2%}")
    print(f"  Total major wins:      {total_wins}")
    print(f"  Pool exhaustion:       {exhaustions}")
    print(f"  Avg free value/tick:   {avg_residual_rate:.4f}")
    print(f"  Avg peak productivity: {avg_max_cap:.4f}")
    print(f"  Avg productivity@end:  {avg_term_cap:.4f}")
    print(f"  Avg quality est. err:  {avg_belief_mae:.4f}")
    print()

# ---------------------------------------------------------------------------
# Save results to JSON
# ---------------------------------------------------------------------------

# All script output goes under results/ per CLAUDE.md. No ad-hoc
# top-level output directories.
output_dir = Path("results")
output_dir.mkdir(exist_ok=True)

# Timestamped filename so successive runs don't overwrite each other.
timestamp = datetime.now(tz=UTC).strftime("%Y_%m_%d_%H_%M_%S")
output_path = output_dir / f"campaign_{timestamp}.json"

data = campaign_result_to_dict(result)
with output_path.open("w", encoding="utf-8") as f:
    json.dump(data, f, indent=2)

print(f"Full results written to {output_path}")
