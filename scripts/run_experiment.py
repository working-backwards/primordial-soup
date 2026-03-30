#!/usr/bin/env python
"""Run an experiment and produce a run bundle.

This is the bundle-producing experiment entry point, separate from
baseline_governance_campaign.py (which is for console-output analysis).
The evaluator is for optimization (summarize and discard); this script
is for reporting (collect and preserve).

Runs all three governance archetypes across all three environment
families with multiple seeds, collects full RunResults and WorldStates,
and produces a complete run bundle with Parquet tables, figures, HTML
report, and validation.

Usage:
    python scripts/run_experiment.py
    python scripts/run_experiment.py --seeds 3
    python scripts/run_experiment.py --output-dir results/
    python scripts/run_experiment.py --families balanced_incumbent --presets balanced

Design reference: docs/implementation/reporting_package_specification.md §Step 8
"""

from __future__ import annotations

import argparse
import logging
import time
from pathlib import Path

from primordial_soup.config import (
    ReportingConfig,
    SimulationConfiguration,
)
from primordial_soup.presets import (
    EnvironmentFamilyName,
    make_aggressive_stop_loss_governance_config,
    make_balanced_governance_config,
    make_environment_spec,
    make_patient_moonshot_governance_config,
)
from primordial_soup.run_bundle import (
    ExperimentalConditionRecord,
    ExperimentalConditionSpec,
    ExperimentSpec,
    SeedRunRecord,
    create_run_bundle,
    extract_initiative_final_states,
)
from primordial_soup.runner import run_single_regime
from primordial_soup.workbench import make_policy

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
)
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
    "aggressive_stop_loss": "Aggressive Stop-Loss",
    "patient_moonshot": "Patient Moonshot",
}

FAMILY_LABELS: dict[str, str] = {
    "balanced_incumbent": "Balanced Incumbent",
    "short_cycle_throughput": "Short Cycle Throughput",
    "discovery_heavy": "Discovery Heavy",
}

GOVERNANCE_FACTORIES = {
    "balanced": make_balanced_governance_config,
    "aggressive_stop_loss": make_aggressive_stop_loss_governance_config,
    "patient_moonshot": make_patient_moonshot_governance_config,
}


# ============================================================================
# Main
# ============================================================================


def run_experiment(
    families: tuple[EnvironmentFamilyName, ...],
    presets: tuple[str, ...],
    seeds: tuple[int, ...],
    output_dir: Path,
) -> Path:
    """Run the experiment and produce a run bundle.

    Args:
        families: Environment family names to evaluate.
        presets: Governance preset names to evaluate.
        seeds: World seeds for Monte Carlo replications.
        output_dir: Parent directory for the run bundle.

    Returns:
        Path to the created run-bundle directory.
    """
    total_runs = len(families) * len(presets) * len(seeds)
    logger.info(
        "Starting experiment: %d families x %d presets x %d seeds = %d runs",
        len(families),
        len(presets),
        len(seeds),
        total_runs,
    )
    experiment_start = time.time()

    # Bundle runs force both event logs and per-tick logs.
    # Per plan §Step 8: both are required for bundle generation.
    reporting = ReportingConfig(
        record_manifest=True,
        record_per_tick_logs=True,
        record_event_log=True,
    )

    condition_records: list[ExperimentalConditionRecord] = []
    run_count = 0

    for family in families:
        env_spec = make_environment_spec(family)

        for preset in presets:
            condition_id = f"{family}__{preset}"
            logger.info("Condition: %s", condition_id)

            # Build governance config from preset.
            gov_factory = GOVERNANCE_FACTORIES[preset]
            governance = gov_factory(
                exec_attention_budget=env_spec.model.exec_attention_budget,
                default_initial_quality_belief=env_spec.model.default_initial_quality_belief,
            )

            # Build policy.
            policy = make_policy(governance)

            # Run all seeds for this condition.
            seed_run_records: list[SeedRunRecord] = []
            representative_config = None

            for seed in seeds:
                run_count += 1
                logger.info(
                    "  Run %d/%d: seed=%d, policy=%s",
                    run_count,
                    total_runs,
                    seed,
                    preset,
                )

                sim_config = SimulationConfiguration(
                    world_seed=seed,
                    time=env_spec.time,
                    teams=env_spec.teams,
                    model=env_spec.model,
                    governance=governance,
                    reporting=reporting,
                    initiative_generator=env_spec.initiative_generator,
                )
                representative_config = sim_config

                # Run the simulation — collect both RunResult and WorldState.
                run_result, world_state = run_single_regime(sim_config, policy)

                # Extract per-initiative final states for the reporting tables.
                final_states = extract_initiative_final_states(world_state)

                seed_run_records.append(
                    SeedRunRecord(
                        world_seed=seed,
                        run_result=run_result,
                        initiative_final_states=final_states,
                        initiative_configs=run_result.manifest.resolved_initiatives,
                    )
                )

            assert representative_config is not None

            # Build condition spec.
            condition_spec = ExperimentalConditionSpec(
                experimental_condition_id=condition_id,
                environmental_conditions_id=family,
                environmental_conditions_name=FAMILY_LABELS.get(family, family),
                governance_architecture_id="default",
                governance_architecture_name="Default",
                operating_policy_id=preset,
                operating_policy_name=PRESET_LABELS.get(preset, preset),
                governance_regime_label=PRESET_LABELS.get(preset, preset),
            )

            condition_records.append(
                ExperimentalConditionRecord(
                    condition_spec=condition_spec,
                    seed_run_records=tuple(seed_run_records),
                    simulation_config=representative_config,
                )
            )

    # Build experiment spec.
    experiment_spec = ExperimentSpec(
        experiment_name="baseline_governance_comparison",
        title="Baseline Governance Comparison",
        description=(
            f"{len(presets)} governance regimes across {len(families)} "
            f"environmental conditions with {len(seeds)} shared seeds."
        ),
        world_seeds=seeds,
        condition_records=tuple(condition_records),
        script_name="scripts/run_experiment.py",
        study_phase="evaluation",
    )

    # Create the run bundle.
    logger.info("Creating run bundle...")
    bundle_path = create_run_bundle(experiment_spec, output_dir)

    elapsed = time.time() - experiment_start
    logger.info(
        "Experiment complete: %d runs in %.1fs. Bundle: %s",
        total_runs,
        elapsed,
        bundle_path,
    )

    return bundle_path


def main() -> None:
    """Parse arguments and run the experiment."""
    parser = argparse.ArgumentParser(
        description="Run a governance comparison experiment and produce a run bundle.",
    )
    parser.add_argument(
        "--seeds",
        type=int,
        default=7,
        help="Number of Monte Carlo seeds (default: 7)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="results",
        help="Output directory for the run bundle (default: results/)",
    )
    parser.add_argument(
        "--families",
        nargs="+",
        default=list(FAMILIES),
        help="Environment families to include (default: all three)",
    )
    parser.add_argument(
        "--presets",
        nargs="+",
        default=list(PRESETS),
        help="Governance presets to include (default: all three)",
    )
    parser.add_argument(
        "--seed-start",
        type=int,
        default=42,
        help="First seed value (default: 42)",
    )

    args = parser.parse_args()
    seeds = tuple(range(args.seed_start, args.seed_start + args.seeds))
    output_dir = Path(args.output_dir)

    bundle_path = run_experiment(
        families=tuple(args.families),
        presets=tuple(args.presets),
        seeds=seeds,
        output_dir=output_dir,
    )

    print(f"\nRun bundle created: {bundle_path}")


if __name__ == "__main__":
    main()
