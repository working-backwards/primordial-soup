"""Campaign specification and governance sweep generation.

This module defines the experiment-definition layer for the Primordial
Soup study. It sits outside the core simulator: the simulator only sees
SimulationConfiguration and GovernancePolicy. This module produces those
as output from higher-level campaign abstractions.

Three levels of experimental control:

    Level 1 — Initiative instances: stochastic draws from the initiative
        generator, varied by world_seed. Not controlled here.
    Level 2 — Governance parameters: the governance design space. This
        module generates GovernanceConfig instances via Latin Hypercube
        Sampling (LHS) and includes fixed archetype anchor points.
    Level 3 — Environment configurations: different opportunity
        environments. EnvironmentSpec encapsulates one environment.
        Environment sweeps are a future concern.

Key design decisions:
    - LHS uses NumPy for design-time randomness, seeded by design_seed.
      This is experiment-construction randomness, NOT simulation-time
      stochasticity. Simulation-time RNG uses MRG32k3a via noise.py.
      The design_seed is recorded in the campaign manifest for
      reproducibility.
    - Disabled governance rules (confidence_decline_threshold=None,
      exec_overrun_threshold=None) are separate design points or
      campaign families, NOT encoded in the LHS. Every LHS point has
      all 8 governance parameters active (float values within bounds).
    - The canonical sweep dimension for attention breadth is
      attention_min (sampled directly) plus a nonnegative attention_span
      (sampled directly). attention_max is derived:
          attention_max = min(attention_min + attention_span, 1.0)
      This guarantees attention_min <= attention_max by construction
      (per experiments.md).
    - Portfolio-risk parameters are NOT in the baseline LHS. They are
      set to None in every generated GovernanceConfig.
    - The three named archetypes (Balanced, Aggressive Stop-Loss,
      Patient Moonshot) are appended as fixed supplemental design
      points, not LHS draws.

Design references:
    - docs/design/experiments.md (sweep design, LHS spec, sample sizes)
    - docs/implementation/open_implementation_issues.md Issue 7 (RNG)
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

from primordial_soup.config import (
    GovernanceConfig,
    ReportingConfig,
    SimulationConfiguration,
    WorkforceConfig,
)
from primordial_soup.presets import (
    make_aggressive_stop_loss_governance_config,
    make_balanced_governance_config,
    make_patient_moonshot_governance_config,
)
from primordial_soup.types import RampShape

if TYPE_CHECKING:
    from primordial_soup.config import (
        InitiativeGeneratorConfig,
        ModelConfig,
        TimeConfig,
    )
    from primordial_soup.policy import GovernancePolicy
    from primordial_soup.reporting import RunResult

# A PolicyFactory maps a GovernanceConfig to the appropriate
# GovernancePolicy implementation. This allows the campaign runner to
# remain decoupled from specific policy class imports.
PolicyFactory = Callable[["GovernanceConfig"], "GovernancePolicy"]

logger = logging.getLogger(__name__)


# ===========================================================================
# Step 7f — Campaign specification types
# ===========================================================================


@dataclass(frozen=True)
class EnvironmentSpec:
    """A complete environment configuration for a campaign.

    Encapsulates the four baseline component configs that define one
    Level 3 environment (opportunity structure). The baseline environment
    from Phase 7 Milestone 1 is the first EnvironmentSpec instance.

    The simulator sees these as fields of SimulationConfiguration.
    EnvironmentSpec groups them for experiment-definition convenience.
    """

    time: TimeConfig
    teams: WorkforceConfig
    model: ModelConfig
    initiative_generator: InitiativeGeneratorConfig


@dataclass(frozen=True)
class WorkforceArchitectureSpec:
    """Governance architecture specification for workforce structure.

    Describes the executive's structural workforce design choice:
    how to decompose a given total labor endowment into discrete
    teams. Resolved into a concrete WorkforceConfig before simulation
    start. The simulator never sees this type.

    This is the workforce analogue of InitiativeGeneratorConfig: an
    upstream specification that is resolved into a realized
    representation (WorkforceConfig) before the engine runs. The
    simulator consumes the realized workforce and does not know or
    care how it was generated.

    total_labor_endowment is the environmental given — the aggregate
    productive capacity. team_count and team_sizes describe the
    governance architecture — how that capacity is decomposed into
    discrete work units.

    In the current study framing, ramp parameters are treated as
    properties of the chosen team structure rather than environmental
    givens. This is a modeling choice, not an empirical law.

    Per docs/design/team_and_resources.md and the three-layer model
    described in docs/design/governance.md.
    """

    total_labor_endowment: int
    team_count: int
    # If None, teams are equal-sized (total_labor_endowment // team_count).
    # If provided, must have length == team_count and sum to
    # total_labor_endowment.
    team_sizes: tuple[int, ...] | None = None
    ramp_period: int = 4
    ramp_multiplier_shape: RampShape = RampShape.LINEAR

    def resolve(self) -> WorkforceConfig:
        """Produce a concrete WorkforceConfig from this architecture spec.

        Resolves the architecture specification into the realized
        workforce representation that the simulator consumes. This is
        analogous to how InitiativeGeneratorConfig is resolved into
        concrete ResolvedInitiativeConfig instances before simulation
        start.

        Returns:
            WorkforceConfig with concrete team count, sizes, and ramp
            parameters.

        Raises:
            ValueError: If team_sizes is provided but has wrong length
                or does not sum to total_labor_endowment, or if
                total_labor_endowment is not exactly divisible by
                team_count when team_sizes is omitted.
        """
        if self.team_sizes is not None:
            if len(self.team_sizes) != self.team_count:
                raise ValueError(
                    f"team_sizes length ({len(self.team_sizes)}) must "
                    f"match team_count ({self.team_count})."
                )
            if sum(self.team_sizes) != self.total_labor_endowment:
                raise ValueError(
                    f"team_sizes sum ({sum(self.team_sizes)}) must "
                    f"equal total_labor_endowment "
                    f"({self.total_labor_endowment})."
                )
            return WorkforceConfig(
                team_count=self.team_count,
                team_size=self.team_sizes,
                ramp_period=self.ramp_period,
                ramp_multiplier_shape=self.ramp_multiplier_shape,
            )
        # Equal-sized teams: require exact divisibility so the resolved
        # workforce has exactly the declared total labor endowment.
        if self.total_labor_endowment % self.team_count != 0:
            raise ValueError(
                f"total_labor_endowment ({self.total_labor_endowment}) must "
                f"be exactly divisible by team_count ({self.team_count}) "
                f"when team_sizes is not provided."
            )
        team_size = self.total_labor_endowment // self.team_count
        return WorkforceConfig(
            team_count=self.team_count,
            team_size=team_size,
            ramp_period=self.ramp_period,
            ramp_multiplier_shape=self.ramp_multiplier_shape,
        )


@dataclass(frozen=True)
class LhsParameterBounds:
    """Bounds for the 8-dimensional LHS governance parameter space.

    Each field is a (lower, upper) tuple defining the sampling range
    for that parameter. The LHS generator samples uniformly within
    these bounds (after stratification).

    The 8 LHS dimensions:
        1. confidence_decline_threshold — float in bounds
        2. tam_threshold_ratio — float in bounds
        3. base_tam_patience_window — int (rounded after sampling)
        4. stagnation_window_staffed_ticks — int (rounded after sampling)
        5. stagnation_belief_change_threshold — float in bounds
        6. attention_min — float in bounds
        7. attention_span — float >= 0 in bounds; attention_max is derived
           as min(attention_min + attention_span, 1.0)
        8. exec_overrun_threshold — float in bounds

    In the baseline LHS, all parameters are active (no None values).
    Disabled-rule variants are separate design points.
    """

    # Per experiments.md: all bounds are inclusive [lower, upper].
    confidence_decline_threshold: tuple[float, float]
    tam_threshold_ratio: tuple[float, float]
    base_tam_patience_window: tuple[int, int]
    stagnation_window_staffed_ticks: tuple[int, int]
    stagnation_belief_change_threshold: tuple[float, float]
    attention_min: tuple[float, float]
    # attention_span >= 0; attention_max = attention_min + attention_span.
    # The canonical sweep dimension is attention_min plus derived
    # attention_span — attention_max is constructed, not sampled.
    attention_span: tuple[float, float]
    exec_overrun_threshold: tuple[float, float]


@dataclass(frozen=True)
class GovernanceSweepSpec:
    """Specification for generating governance configurations via LHS.

    Describes how to generate governance configurations for a campaign:
    the LHS parameter bounds, sample count, design seed for LHS
    reproducibility, and fixed archetype anchor points.

    Per experiments.md: minimum LHS sample size is 10 × dimensionality
    (8 params → 80 minimum, 200 recommended for robustness).

    The three named archetypes are always included as fixed supplemental
    points appended after the LHS draws. They are not part of the LHS
    sample itself.

    Portfolio-risk parameters are not in the LHS. They are set to None
    in every generated GovernanceConfig.
    """

    # LHS parameter bounds for the 8-dimensional governance space.
    parameter_bounds: LhsParameterBounds

    # Number of LHS sample points to draw. Per experiments.md:
    # minimum 10 × dimensionality = 80, recommended 200.
    lhs_sample_count: int

    # Seed for LHS design-time randomness (NumPy RNG). Recorded in
    # the campaign manifest for provenance. This is NOT the simulation
    # world_seed — it controls only the experimental design layout.
    design_seed: int

    # Whether to append the three named archetype configs as fixed
    # supplemental points after the LHS draws.
    include_archetype_anchors: bool = True


@dataclass(frozen=True)
class CampaignSpec:
    """Complete experiment definition for a campaign.

    Combines one EnvironmentSpec with one GovernanceSweepSpec and a set
    of world_seed values. Each (governance_config, world_seed) pair is
    one simulation run.

    Total runs = len(governance_configs) × len(world_seeds).

    Per experiments.md: for regime comparisons, use paired runs sharing
    the same set of world_seed values across all regimes so that outcome
    differences reflect governance differences.
    """

    # Campaign-level metadata.
    campaign_id: str
    description: str

    # Environment (Level 3) — held fixed across the campaign.
    environment: EnvironmentSpec

    # Governance sweep specification.
    governance_sweep: GovernanceSweepSpec

    # World seeds for replication. Each governance config is run against
    # every world_seed in this tuple.
    world_seeds: tuple[int, ...]


# ===========================================================================
# Step 7g — LHS governance sweep generator
# ===========================================================================

# Number of LHS dimensions in the baseline governance sweep.
_LHS_DIMENSIONS: int = 8

# Dimension indices for referencing columns in the LHS sample matrix.
# These must match the order used in _scale_lhs_to_governance_configs.
_DIM_CONFIDENCE_DECLINE = 0
_DIM_TAM_THRESHOLD_RATIO = 1
_DIM_BASE_TAM_PATIENCE_WINDOW = 2
_DIM_STAGNATION_WINDOW = 3
_DIM_STAGNATION_EPSILON = 4
_DIM_ATTENTION_MIN = 5
_DIM_ATTENTION_SPAN = 6
_DIM_EXEC_OVERRUN = 7


def generate_lhs_unit_sample(
    sample_count: int,
    dimensions: int,
    rng: np.random.Generator,
) -> np.ndarray:
    """Generate a Latin Hypercube Sample on the unit hypercube [0, 1]^D.

    Algorithm (no scipy dependency):
        1. Divide [0, 1] into sample_count equal strata per dimension.
        2. Draw one uniform sample within each stratum per dimension.
        3. Randomly permute each column independently.

    This produces a sample_count × dimensions array where each column
    is a permutation of stratified samples — the defining property of
    Latin Hypercube Sampling.

    Args:
        sample_count: Number of sample points (N).
        dimensions: Number of dimensions (D).
        rng: NumPy random Generator seeded with design_seed.

    Returns:
        np.ndarray of shape (sample_count, dimensions) with values
        in [0, 1].
    """
    # Step 1–2: For each dimension, draw one uniform sample within each
    # stratum. Stratum i covers [i/N, (i+1)/N]. A uniform draw within
    # stratum i is: (i + U) / N where U ~ Uniform(0, 1).
    #
    # We generate a (N, D) array of uniform draws and offset them by
    # their stratum index.
    strata_indices = np.arange(sample_count)  # [0, 1, ..., N-1]
    uniform_draws = rng.uniform(size=(sample_count, dimensions))

    # result[i, j] = (strata_indices[i] + uniform_draws[i, j]) / N
    # Broadcasting: strata_indices is (N,), needs to be (N, 1).
    result = (strata_indices[:, np.newaxis] + uniform_draws) / sample_count

    # Step 3: Randomly permute each column independently.
    for dim in range(dimensions):
        rng.shuffle(result[:, dim])

    return result


def generate_governance_configs(
    sweep_spec: GovernanceSweepSpec,
    environment: EnvironmentSpec,
) -> tuple[GovernanceConfig, ...]:
    """Generate governance configurations from a GovernanceSweepSpec.

    Produces LHS-sampled GovernanceConfig instances plus (optionally)
    the three named archetype configs as fixed supplemental points.

    The LHS samples over 8 dimensions:
        1. confidence_decline_threshold (float)
        2. tam_threshold_ratio (float)
        3. base_tam_patience_window (int, rounded)
        4. stagnation_window_staffed_ticks (int, rounded)
        5. stagnation_belief_change_threshold (float)
        6. attention_min (float)
        7. attention_span (float >= 0, derives attention_max)
        8. exec_overrun_threshold (float)

    Integer parameters are rounded to nearest int after continuous
    LHS sampling. attention_max = min(attention_min + attention_span, 1.0),
    guaranteeing feasibility by construction.

    All portfolio-risk parameters are set to None in every config.

    Args:
        sweep_spec: The governance sweep specification.
        environment: The environment spec (needed for ModelConfig fields
            that GovernanceConfig mirrors: exec_attention_budget and
            default_initial_quality_belief).

    Returns:
        Tuple of GovernanceConfig instances: LHS samples first, then
        archetype anchors (if include_archetype_anchors is True).
    """
    bounds = sweep_spec.parameter_bounds

    # --- Validate sweep spec ---
    if sweep_spec.lhs_sample_count < 1:
        raise ValueError(f"lhs_sample_count must be >= 1, got {sweep_spec.lhs_sample_count}.")
    minimum_recommended = 10 * _LHS_DIMENSIONS  # 80
    if sweep_spec.lhs_sample_count < minimum_recommended:
        logger.warning(
            "lhs_sample_count (%d) is below the recommended minimum of "
            "10 × dimensionality = %d. Results may underrepresent the "
            "governance parameter space.",
            sweep_spec.lhs_sample_count,
            minimum_recommended,
        )

    # --- Generate LHS unit sample ---
    # NumPy RNG seeded with design_seed. This is design-time randomness,
    # not simulation-time stochasticity. The design_seed is recorded in
    # the campaign manifest for reproducibility.
    rng = np.random.default_rng(sweep_spec.design_seed)
    unit_sample = generate_lhs_unit_sample(
        sample_count=sweep_spec.lhs_sample_count,
        dimensions=_LHS_DIMENSIONS,
        rng=rng,
    )

    # --- Scale unit sample to parameter bounds and build configs ---
    lhs_configs = _scale_lhs_to_governance_configs(
        unit_sample=unit_sample,
        bounds=bounds,
        exec_attention_budget=environment.model.exec_attention_budget,
        default_initial_quality_belief=environment.model.default_initial_quality_belief,
    )

    # --- Append archetype anchor points ---
    configs: list[GovernanceConfig] = list(lhs_configs)
    if sweep_spec.include_archetype_anchors:
        archetype_configs = _make_archetype_anchor_configs(
            exec_attention_budget=environment.model.exec_attention_budget,
            default_initial_quality_belief=environment.model.default_initial_quality_belief,
        )
        configs.extend(archetype_configs)

    logger.info(
        "Generated %d governance configs: %d LHS samples + %d archetype anchors.",
        len(configs),
        sweep_spec.lhs_sample_count,
        len(configs) - sweep_spec.lhs_sample_count,
    )

    return tuple(configs)


def _scale_lhs_to_governance_configs(
    unit_sample: np.ndarray,
    bounds: LhsParameterBounds,
    exec_attention_budget: float,
    default_initial_quality_belief: float,
) -> list[GovernanceConfig]:
    """Scale a [0,1]^D LHS sample to governance parameter bounds.

    For each row in the unit_sample matrix, maps the unit values to
    parameter values within the specified bounds:
        param = lower + unit_value * (upper - lower)

    Integer parameters (base_tam_patience_window,
    stagnation_window_staffed_ticks) are rounded to nearest int after
    continuous scaling, then clamped to the original bounds.

    attention_max is derived from attention_min + attention_span,
    capped at 1.0. This is the canonical construction that guarantees
    attention_min <= attention_max by construction.

    All portfolio-risk parameters are set to None.

    Args:
        unit_sample: np.ndarray of shape (N, 8) with values in [0, 1].
        bounds: LhsParameterBounds defining ranges for each dimension.
        exec_attention_budget: From ModelConfig (mirrored in GovernanceConfig).
        default_initial_quality_belief: From ModelConfig (mirrored).

    Returns:
        List of N GovernanceConfig instances.
    """
    configs: list[GovernanceConfig] = []

    for row_index in range(unit_sample.shape[0]):
        row = unit_sample[row_index]

        # --- Scale each dimension ---
        # Continuous parameters: lower + u * (upper - lower)
        confidence_decline = bounds.confidence_decline_threshold[0] + row[
            _DIM_CONFIDENCE_DECLINE
        ] * (bounds.confidence_decline_threshold[1] - bounds.confidence_decline_threshold[0])
        tam_threshold = bounds.tam_threshold_ratio[0] + row[_DIM_TAM_THRESHOLD_RATIO] * (
            bounds.tam_threshold_ratio[1] - bounds.tam_threshold_ratio[0]
        )
        stag_bounds = bounds.stagnation_belief_change_threshold
        stagnation_eps = stag_bounds[0] + row[_DIM_STAGNATION_EPSILON] * (
            stag_bounds[1] - stag_bounds[0]
        )
        att_min = bounds.attention_min[0] + row[_DIM_ATTENTION_MIN] * (
            bounds.attention_min[1] - bounds.attention_min[0]
        )
        att_span = bounds.attention_span[0] + row[_DIM_ATTENTION_SPAN] * (
            bounds.attention_span[1] - bounds.attention_span[0]
        )
        exec_overrun = bounds.exec_overrun_threshold[0] + row[_DIM_EXEC_OVERRUN] * (
            bounds.exec_overrun_threshold[1] - bounds.exec_overrun_threshold[0]
        )

        # Integer parameters: continuous scale then round, clamp to bounds.
        tam_patience_raw = bounds.base_tam_patience_window[0] + row[
            _DIM_BASE_TAM_PATIENCE_WINDOW
        ] * (bounds.base_tam_patience_window[1] - bounds.base_tam_patience_window[0])
        tam_patience = int(
            max(
                bounds.base_tam_patience_window[0],
                min(bounds.base_tam_patience_window[1], round(tam_patience_raw)),
            )
        )

        stagnation_window_raw = bounds.stagnation_window_staffed_ticks[0] + row[
            _DIM_STAGNATION_WINDOW
        ] * (bounds.stagnation_window_staffed_ticks[1] - bounds.stagnation_window_staffed_ticks[0])
        stagnation_window = int(
            max(
                bounds.stagnation_window_staffed_ticks[0],
                min(
                    bounds.stagnation_window_staffed_ticks[1],
                    round(stagnation_window_raw),
                ),
            )
        )

        # Derive attention_max from attention_min + attention_span,
        # capped at 1.0. This is the canonical construction per
        # experiments.md §Parameter sweep design.
        attention_max = min(att_min + att_span, 1.0)

        # Build GovernanceConfig with a descriptive policy_id indicating
        # this is an LHS-generated sweep point, not a named archetype.
        configs.append(
            GovernanceConfig(
                policy_id=f"lhs_sweep_{row_index:04d}",
                exec_attention_budget=exec_attention_budget,
                default_initial_quality_belief=default_initial_quality_belief,
                confidence_decline_threshold=float(confidence_decline),
                tam_threshold_ratio=float(tam_threshold),
                base_tam_patience_window=tam_patience,
                stagnation_window_staffed_ticks=stagnation_window,
                stagnation_belief_change_threshold=float(stagnation_eps),
                attention_min=float(att_min),
                attention_max=float(attention_max),
                exec_overrun_threshold=float(exec_overrun),
                # Portfolio-risk parameters NOT in baseline LHS.
                # Set explicitly to None per experiments.md §Parameter
                # sweep design (experiments.md §Parameter sweep design).
                low_quality_belief_threshold=None,
                max_low_quality_belief_labor_share=None,
                max_single_initiative_labor_share=None,
            )
        )

    return configs


def _make_archetype_anchor_configs(
    exec_attention_budget: float,
    default_initial_quality_belief: float,
) -> list[GovernanceConfig]:
    """Build the three named archetype configs as fixed anchor points.

    These are appended to the LHS sample as supplemental design points.
    They use the same parameter values as the preset factories in
    presets.py.

    Per experiments.md: the three named archetypes are fixed supplemental
    design points, not random draws and not constrained LHS cells.

    Args:
        exec_attention_budget: From ModelConfig.
        default_initial_quality_belief: From ModelConfig.

    Returns:
        List of 3 GovernanceConfig instances (Balanced, Aggressive, Patient).
    """
    return [
        make_balanced_governance_config(
            exec_attention_budget=exec_attention_budget,
            default_initial_quality_belief=default_initial_quality_belief,
        ),
        make_aggressive_stop_loss_governance_config(
            exec_attention_budget=exec_attention_budget,
            default_initial_quality_belief=default_initial_quality_belief,
        ),
        make_patient_moonshot_governance_config(
            exec_attention_budget=exec_attention_budget,
            default_initial_quality_belief=default_initial_quality_belief,
        ),
    ]


# ===========================================================================
# Convenience: default parameter bounds
# ===========================================================================


def make_default_parameter_bounds() -> LhsParameterBounds:
    """Build default LHS parameter bounds for the baseline governance sweep.

    These bounds define reasonable ranges for the 8-dimensional
    governance parameter space. They are chosen to cover the space
    between and beyond the three named archetypes, ensuring the LHS
    explores governance postures from aggressive to patient.

    Returns:
        LhsParameterBounds with canonical default ranges.
    """
    return LhsParameterBounds(
        # confidence_decline_threshold: from very aggressive (0.1) to
        # barely-below-initial (0.45). Initial belief is 0.5.
        confidence_decline_threshold=(0.1, 0.45),
        # tam_threshold_ratio: from tolerant (0.3) to demanding (0.9).
        tam_threshold_ratio=(0.3, 0.9),
        # base_tam_patience_window: from impatient (3) to very patient (30).
        base_tam_patience_window=(3, 30),
        # stagnation_window_staffed_ticks: from tight (5) to generous (40).
        stagnation_window_staffed_ticks=(5, 40),
        # stagnation_belief_change_threshold: from tight detection (0.005) to loose (0.05).
        stagnation_belief_change_threshold=(0.005, 0.05),
        # attention_min: from low floor (0.05) to high floor (0.4).
        attention_min=(0.05, 0.4),
        # attention_span: from zero span (attention_max = attention_min,
        # i.e. all initiatives get the same attention) to wide span (0.6).
        # attention_max = attention_min + attention_span, capped at 1.0.
        attention_span=(0.0, 0.6),
        # exec_overrun_threshold: from tolerant (0.2) to strict (0.6).
        exec_overrun_threshold=(0.2, 0.6),
    )


# ===========================================================================
# Step 7i — Campaign runner
# ===========================================================================


@dataclass(frozen=True)
class CampaignResult:
    """Result bundle from running a complete campaign.

    Contains all individual RunResults plus the campaign specification
    and generated governance configs for provenance.
    """

    campaign_spec: CampaignSpec
    governance_configs: tuple[GovernanceConfig, ...]
    run_results: tuple[RunResult, ...]
    # Total number of runs executed.
    total_runs: int


def run_campaign(
    campaign_spec: CampaignSpec,
    policy_factory: PolicyFactory,
) -> CampaignResult:
    """Execute all runs in a campaign sequentially.

    Generates governance configs from the sweep spec, then runs every
    (governance_config, world_seed) pair. Sequential execution — no
    parallelism. Parallel execution is a future enhancement.

    The policy_factory callable receives a GovernanceConfig and returns
    the appropriate GovernancePolicy implementation. This decouples
    campaign execution from specific policy class imports.

    Args:
        campaign_spec: Complete campaign definition.
        policy_factory: Callable that maps GovernanceConfig → GovernancePolicy.

    Returns:
        CampaignResult with all RunResults and provenance.
    """
    from primordial_soup.runner import run_single_regime

    # --- Generate governance configs ---
    governance_configs = generate_governance_configs(
        sweep_spec=campaign_spec.governance_sweep,
        environment=campaign_spec.environment,
    )

    # --- Run all (governance_config, world_seed) pairs ---
    results: list[RunResult] = []
    total_runs = len(governance_configs) * len(campaign_spec.world_seeds)

    logger.info(
        "Starting campaign '%s': %d governance configs × %d world seeds = %d total runs.",
        campaign_spec.campaign_id,
        len(governance_configs),
        len(campaign_spec.world_seeds),
        total_runs,
    )

    run_number = 0
    for _config_index, gov_config in enumerate(governance_configs):
        policy = policy_factory(gov_config)

        for seed in campaign_spec.world_seeds:
            run_number += 1

            # Build SimulationConfiguration from environment + governance.
            sim_config = SimulationConfiguration(
                world_seed=seed,
                time=campaign_spec.environment.time,
                teams=campaign_spec.environment.teams,
                model=campaign_spec.environment.model,
                governance=gov_config,
                reporting=ReportingConfig(
                    record_manifest=True,
                    record_per_tick_logs=True,
                    record_event_log=True,
                ),
                initiative_generator=campaign_spec.environment.initiative_generator,
            )

            logger.info(
                "Campaign '%s' run %d/%d: policy=%s, seed=%d.",
                campaign_spec.campaign_id,
                run_number,
                total_runs,
                gov_config.policy_id,
                seed,
            )

            result, _ = run_single_regime(sim_config, policy)
            results.append(result)

    logger.info(
        "Campaign '%s' complete: %d runs executed.",
        campaign_spec.campaign_id,
        total_runs,
    )

    return CampaignResult(
        campaign_spec=campaign_spec,
        governance_configs=governance_configs,
        run_results=tuple(results),
        total_runs=total_runs,
    )
