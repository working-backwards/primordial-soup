"""Run a single simulation with a chosen governance archetype.

Usage:
    python scripts/run_single.py

The script presents the three canonical governance archetypes and asks
you to pick one. It then runs a 200-tick simulation and prints key
output metrics.
"""

from __future__ import annotations

import logging

from primordial_soup.policy import (
    AggressiveStopLossPolicy,
    BalancedPolicy,
    GovernancePolicy,
    PatientMoonshotPolicy,
)
from primordial_soup.presets import (
    make_aggressive_stop_loss_config,
    make_balanced_config,
    make_patient_moonshot_config,
)
from primordial_soup.runner import run_single_regime

# Configure logging so you can see progress.
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

# --- Archetype menu ---
# Each entry: (label, description, config_factory, policy_instance)
ARCHETYPES: list[tuple[str, str, type, GovernancePolicy]] = [
    (
        "Balanced",
        "Moderate stop thresholds, all four stop rules active, even attention.",
        make_balanced_config,
        BalancedPolicy(),
    ),
    (
        "Aggressive Stop-Loss",
        "Tighter thresholds, shorter patience, rapid redeployment.",
        make_aggressive_stop_loss_config,
        AggressiveStopLossPolicy(),
    ),
    (
        "Patient Moonshot",
        "Confidence-decline disabled, longer patience, holds high-potential work.",
        make_patient_moonshot_config,
        PatientMoonshotPolicy(),
    ),
]

print()
print("Governance Archetypes")
print("-" * 50)
for i, (label, description, _, _) in enumerate(ARCHETYPES, start=1):
    print(f"  {i}. {label}")
    print(f"     {description}")
print()

# Prompt for selection.
while True:
    choice = input(f"Pick an archetype [1-{len(ARCHETYPES)}]: ").strip()
    if choice.isdigit() and 1 <= int(choice) <= len(ARCHETYPES):
        break
    print(f"  Please enter a number between 1 and {len(ARCHETYPES)}.")

selected_index = int(choice) - 1
label, _, config_factory, policy = ARCHETYPES[selected_index]

# The world_seed controls all stochasticity — same seed, same results.
world_seed = 42
config = config_factory(world_seed=world_seed)

print()
print(f"Running {label} archetype (seed={world_seed}) ...")

# Run the simulation (200 ticks by default).
result, _ = run_single_regime(config, policy)

# Print key outputs.
print()
print("=" * 50)
print(f"{label} — Single Run Complete")
print("=" * 50)

# --- Value realized during the run ---
print(f"Cumulative value:          {result.cumulative_value_total:.2f}")
print(f"  Lump-sum value:          {result.value_by_channel.completion_lump_value:.2f}")
print(f"  Residual value:          {result.value_by_channel.residual_value:.2f}")
print("  Residual by type:        ", end="")
print({k: round(v, 2) for k, v in result.value_by_channel.residual_value_by_label.items()})

# --- Organizational momentum at horizon ---
# Free value/tick: value earned each tick from completed flywheel and
# quick-win residual streams, without deploying any additional labor.
print(f"Free value/tick:            {result.terminal_aggregate_residual_rate:.4f}")
# Productivity multiplier: enabler completions raise this above 1.0,
# making every team-tick more effective. Peak vs terminal shows decay.
print(f"Peak productivity:          {result.max_portfolio_capability_t:.4f}")
print(f"Productivity at end:        {result.terminal_capability_t:.4f}")

# --- Discovery ---
# Major wins: count only; the study does not estimate right-tail value.
print(f"Major wins discovered:      {result.major_win_profile.major_win_count}")

# --- Governance quality ---
# Quality estimation error: how accurately governance estimated true
# initiative quality (lower is better).
print(f"Quality est. error:         {result.belief_accuracy.mean_absolute_belief_error:.4f}")
print(f"Idle team-tick %:           {result.idle_capacity_profile.idle_team_tick_fraction:.2%}")
print(f"Pool exhaustion tick:       {result.idle_capacity_profile.pool_exhaustion_tick}")

# --- Initiative outcomes by type ---
print()
completed_by_label = dict(result.exploration_cost_profile.completed_initiative_count_by_label)
print("Completed by type: ", completed_by_label)
labor_in_completed = result.exploration_cost_profile.cumulative_labor_in_completed_initiatives
print(f"  Total labor:     {labor_in_completed:.0f}")
stopped_by_label = dict(result.exploration_cost_profile.stopped_initiative_count_by_label)
print("Stopped by type:   ", stopped_by_label)
