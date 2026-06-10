#!/usr/bin/env python
"""Model 4 governance comparison campaign.

Runs three stop/intake-posture governance archetypes on the Model 4
configuration and produces a self-contained run bundle.

Model 4 is the fifth rung of the model ladder (per
docs/implementation/2026-06-10 Repo Improvement Plan.md): Model 3
plus executive attention in the two-parameter form
g(a) = c1 * exp(-c2 * a) (core_simulator.md; expert review). The
attention budget becomes positive (5.0 across 10 teams, equal share
~0.5) and buys signal clarity: g(0.5) ~= 0.61 vs Model 3's neutral
g = 1.0. Stop/intake posture configs are unchanged, so the M4-vs-M3
paired diff isolates the attention mechanism.

Usage:
    python scripts/model4_campaign.py
    python scripts/model4_campaign.py --seeds 5
"""

from __future__ import annotations

import argparse
import logging
import time
from pathlib import Path

from primordial_soup.presets import (
    make_model4_aggressive_config,
    make_model4_balanced_config,
    make_model4_patient_config,
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
# SimulationConfiguration with Model 4 parameters baked in.
ARCHETYPES = [
    ("balanced", "Balanced", make_model4_balanced_config),
    ("aggressive", "Aggressive", make_model4_aggressive_config),
    ("patient", "Patient", make_model4_patient_config),
]

# Default seed count. Model 4 runs are small (130 initiatives,
# 160 ticks, 10 teams) so 30 seeds is cheap and gives the lever
# sweeps and regime comparisons real statistical footing.
DEFAULT_SEED_COUNT = 30

# Seeds are consecutive from this base so cross-archetype runs pair
# by world_seed for CRN comparisons (compare_bundles.py).
SEED_BASE = 42


# ============================================================================
# Main
# ============================================================================


def run_model4_campaign(
    seeds: tuple[int, ...],
    output_dir: Path,
) -> Path:
    """Run the Model 4 three-archetype campaign and write a run bundle.

    Args:
        seeds: World seeds; each archetype runs every seed (CRN pairing).
        output_dir: Directory under which the bundle is created.

    Returns:
        Path to the created run bundle directory.
    """
    total_runs = len(ARCHETYPES) * len(seeds)
    logger.info(
        "Model 4 campaign: %d archetypes x %d seeds = %d runs",
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

            config = factory(seed)
            representative_config = config

            policy = make_policy(config.governance)
            run_result, world_state = run_single_regime(config, policy)

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

        # Single shared environment ("model4"); conditions vary only by
        # stop/intake posture. Mix targets are identical by design.
        condition_spec = ExperimentalConditionSpec(
            experimental_condition_id=f"model4__{label}",
            environmental_conditions_id="model4",
            environmental_conditions_name="Model 4",
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

    experiment_spec = ExperimentSpec(
        experiment_name="model4_governance_comparison",
        title="Model 4 Governance Comparison",
        description=(
            "Three stop/intake-posture archetypes (Balanced, Aggressive, "
            "Patient) on the Model 4 configuration: Model 3 plus executive "
            "attention as a signal-clarity lever (two-parameter curve, "
            "equal allocation). Posture configs unchanged; the paired "
            "diff isolates the attention mechanism."
        ),
        world_seeds=seeds,
        condition_records=tuple(condition_records),
        script_name="scripts/model4_campaign.py",
        study_phase="evaluation",
        baseline_condition_id="model4__balanced",
    )

    bundle_path = create_run_bundle(experiment_spec, output_dir)
    elapsed = time.time() - campaign_start
    logger.info("Campaign complete in %.1fs. Bundle: %s", elapsed, bundle_path)
    return bundle_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--seeds",
        type=int,
        default=DEFAULT_SEED_COUNT,
        help=f"Number of world seeds to run (default {DEFAULT_SEED_COUNT})",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("results"),
        help="Directory under which the run bundle is created",
    )
    args = parser.parse_args()

    seeds = tuple(range(SEED_BASE, SEED_BASE + args.seeds))
    bundle_path = run_model4_campaign(seeds, args.output_dir)
    print(f"Run bundle written to {bundle_path}")


if __name__ == "__main__":
    main()
