#!/usr/bin/env python
"""Model 2 governance comparison campaign.

Runs three stop/intake-posture governance archetypes on the Model 2
configuration and produces a self-contained run bundle with report,
Parquet tables, and figures.

Model 2 is the third rung of the model ladder (per
docs/implementation/2026-06-10 Repo Improvement Plan.md): Model 1
plus the revelation lag (design decision 27 — information arrives in
lumps, purchased by sustained investment). For a per-type fraction of
each initiative's true build time, strategic quality signals are
drawn but discarded: belief stays flat while cost accrues. Pools and
governance configs are otherwise identical to Model 1, so the
M2-vs-M1 paired diff (compare_bundles.py) isolates the revelation
mechanism alone.

Lag fractions: quick_win 0.0, flywheel 0.35, enabler 0.35,
right_tail 0.50.

Usage:
    python scripts/model2_campaign.py
    python scripts/model2_campaign.py --seeds 5
    python scripts/model2_campaign.py --output-dir results/
"""

from __future__ import annotations

import argparse
import logging
import time
from pathlib import Path

from primordial_soup.presets import (
    make_model2_aggressive_config,
    make_model2_balanced_config,
    make_model2_patient_config,
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
# SimulationConfiguration with Model 2 parameters baked in.
ARCHETYPES = [
    ("balanced", "Balanced", make_model2_balanced_config),
    ("aggressive", "Aggressive", make_model2_aggressive_config),
    ("patient", "Patient", make_model2_patient_config),
]

# Default seed count. Model 2 runs are small (130 initiatives,
# 160 ticks, 10 teams) so 30 seeds is cheap and gives the lever
# sweeps and regime comparisons real statistical footing.
DEFAULT_SEED_COUNT = 30

# Seeds are consecutive from this base so cross-archetype runs pair
# by world_seed for CRN comparisons (compare_bundles.py).
SEED_BASE = 42


# ============================================================================
# Main
# ============================================================================


def run_model2_campaign(
    seeds: tuple[int, ...],
    output_dir: Path,
) -> Path:
    """Run the Model 2 three-archetype campaign and write a run bundle.

    Args:
        seeds: World seeds; each archetype runs every seed (CRN pairing).
        output_dir: Directory under which the bundle is created.

    Returns:
        Path to the created run bundle directory.
    """
    total_runs = len(ARCHETYPES) * len(seeds)
    logger.info(
        "Model 2 campaign: %d archetypes x %d seeds = %d runs",
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

        # Single shared environment ("model2"); conditions vary only by
        # stop/intake posture. Mix targets are identical by design.
        condition_spec = ExperimentalConditionSpec(
            experimental_condition_id=f"model2__{label}",
            environmental_conditions_id="model2",
            environmental_conditions_name="Model 2",
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
        experiment_name="model2_governance_comparison",
        title="Model 2 Governance Comparison",
        description=(
            "Three stop/intake-posture archetypes (Balanced, Aggressive, "
            "Patient) on the Model 2 configuration: Model 1 plus the "
            "revelation lag (signals dark for a per-type fraction of the "
            "build). Pools and governance identical to Model 1, so the "
            "paired M2-vs-M1 diff isolates the revelation mechanism."
        ),
        world_seeds=seeds,
        condition_records=tuple(condition_records),
        script_name="scripts/model2_campaign.py",
        study_phase="evaluation",
        baseline_condition_id="model2__balanced",
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
    bundle_path = run_model2_campaign(seeds, args.output_dir)
    print(f"Run bundle written to {bundle_path}")


if __name__ == "__main__":
    main()
