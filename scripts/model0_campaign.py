#!/usr/bin/env python
"""Model 0 governance comparison campaign.

Runs three selection-focused governance archetypes on the simplified
Model 0 configuration and produces a self-contained run bundle with
HTML report, Parquet tables, and figures.

Model 0 isolates the portfolio selection decision: which initiatives
to start, given limited team capacity.

Complexity layers disabled: residual value, attention effects, team
ramp, dependency, dynamic frontier, screening signals.

Active mechanics: completion lump value, major-win discovery (right-tail),
organizational capability (enabler completions), EMA belief learning.

The three archetypes differ ONLY in portfolio mix targets:
  - Throughput: 60% quick-win, 30% flywheel, 5% enabler, 5% right-tail
  - Balanced:   35% quick-win, 35% flywheel, 15% enabler, 15% right-tail
  - Exploration: 15% quick-win, 25% flywheel, 20% enabler, 40% right-tail

Usage:
    python scripts/model0_campaign.py
    python scripts/model0_campaign.py --seeds 3
    python scripts/model0_campaign.py --seeds 10
    python scripts/model0_campaign.py --output-dir results/
"""

from __future__ import annotations

import argparse
import logging
import time
from pathlib import Path

from primordial_soup.presets import (
    make_model0_balanced_config,
    make_model0_exploration_config,
    make_model0_throughput_config,
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

# Archetype definitions: (label, display_name, config_factory).
# Each factory takes a world_seed and returns a complete
# SimulationConfiguration with Model 0 parameters baked in.
ARCHETYPES = [
    ("throughput", "Throughput", make_model0_throughput_config),
    ("balanced", "Balanced", make_model0_balanced_config),
    ("exploration", "Exploration", make_model0_exploration_config),
]


# ============================================================================
# Main
# ============================================================================


def run_model0_campaign(
    seeds: tuple[int, ...],
    output_dir: Path,
) -> Path:
    """Run the Model 0 campaign and produce a run bundle.

    Iterates over the three Model 0 archetypes, runs each across the
    given seeds, collects full RunResult + WorldState per seed, and
    passes the assembled ExperimentSpec to create_run_bundle() for
    table/figure/report generation.

    Args:
        seeds: World seeds for Monte Carlo replications.
        output_dir: Parent directory for the run bundle.

    Returns:
        Path to the created run-bundle directory.
    """
    total_runs = len(ARCHETYPES) * len(seeds)
    logger.info(
        "Starting Model 0 campaign: %d archetypes x %d seeds = %d runs",
        len(ARCHETYPES),
        len(seeds),
        total_runs,
    )
    campaign_start = time.time()

    condition_records: list[ExperimentalConditionRecord] = []
    run_count = 0

    for label, display, factory in ARCHETYPES:
        logger.info("Archetype: %s", display)

        seed_run_records: list[SeedRunRecord] = []
        representative_config = None

        for seed in seeds:
            run_count += 1
            logger.info(
                "  Run %d/%d: seed=%d, archetype=%s",
                run_count,
                total_runs,
                seed,
                label,
            )

            # Build the complete config from the Model 0 factory.
            # The factory returns a SimulationConfiguration with all
            # Model 0 parameters baked in, including reporting config
            # with all logging channels enabled.
            config = factory(seed)
            representative_config = config

            # Build the governance policy and run the simulation.
            policy = make_policy(config.governance)
            run_result, world_state = run_single_regime(config, policy)

            # Collect the seed run record for the bundle pipeline.
            seed_run_records.append(
                SeedRunRecord(
                    world_seed=seed,
                    run_result=run_result,
                    initiative_final_states=extract_initiative_final_states(
                        world_state,
                    ),
                    initiative_configs=run_result.manifest.resolved_initiatives,
                )
            )

        assert representative_config is not None

        # Build condition spec. Model 0 has a single environment — the
        # condition varies only by governance archetype (mix targets).
        condition_spec = ExperimentalConditionSpec(
            experimental_condition_id=f"model0__{label}",
            environmental_conditions_id="model0",
            environmental_conditions_name="Model 0",
            governance_architecture_id="default",
            governance_architecture_name="Default",
            operating_policy_id=label,
            operating_policy_name=display,
            governance_regime_label=display,
        )

        condition_records.append(
            ExperimentalConditionRecord(
                condition_spec=condition_spec,
                seed_run_records=tuple(seed_run_records),
                simulation_config=representative_config,
            )
        )

    # Build the experiment spec.
    experiment_spec = ExperimentSpec(
        experiment_name="model0_governance_comparison",
        title="Model 0 Governance Comparison",
        description=(
            "3 selection-focused governance archetypes on the simplified "
            f"Model 0 configuration with {len(seeds)} shared seeds. "
            "Complexity layers disabled: residual, attention, ramp, "
            "dependency, frontier, screening. Active: lump value, "
            "major-win discovery, capability, EMA belief learning."
        ),
        world_seeds=seeds,
        condition_records=tuple(condition_records),
        script_name="scripts/model0_campaign.py",
        study_phase="evaluation",
        baseline_condition_id="model0__balanced",
    )

    # Create the run bundle — generates Parquet tables, figures, and
    # the HTML report under output_dir/<timestamped_bundle_id>/.
    logger.info("Creating run bundle...")
    bundle_path = create_run_bundle(experiment_spec, output_dir)

    elapsed = time.time() - campaign_start
    logger.info(
        "Model 0 campaign complete: %d runs in %.1fs. Bundle: %s",
        total_runs,
        elapsed,
        bundle_path,
    )

    return bundle_path


def main() -> None:
    """Parse arguments and run the Model 0 campaign."""
    parser = argparse.ArgumentParser(
        description="Model 0 governance comparison campaign.",
    )
    parser.add_argument(
        "--seeds",
        type=int,
        default=5,
        help="Number of seeds per archetype (default: 5).",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="results",
        help="Output directory for the run bundle (default: results/).",
    )
    parser.add_argument(
        "--seed-start",
        type=int,
        default=42,
        help="First seed value (default: 42).",
    )
    args = parser.parse_args()

    seeds = tuple(range(args.seed_start, args.seed_start + args.seeds))
    output_dir = Path(args.output_dir)

    bundle_path = run_model0_campaign(seeds=seeds, output_dir=output_dir)

    print(f"\nRun bundle created: {bundle_path}")
    print(f"Open report: {bundle_path / 'report' / 'index.html'}")


if __name__ == "__main__":
    main()
