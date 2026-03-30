"""Thin evaluator wrapper for optimization readiness.

This module provides a stable interface between the simulator and any
future optimizer (SimOpt or otherwise). It does not implement optimization
logic. It locks in the interface contract: given a governance parameter
vector, a set of seeds, and an environment specification, produce a
multi-dimensional response bundle that can be consumed by any downstream
scalarization, multi-objective, or constraint-based optimizer.

Design contract
---------------

- The evaluator calls existing run-resolution and runner machinery.
  It does not reimplement any simulator logic.
- The response is multi-dimensional by default. Scalarization (weighting
  cumulative_value vs. major_win_count vs. terminal_capability, etc.)
  is deliberately a separate downstream decision, not baked into this
  interface.
- The evaluator is deterministic for the same (params, seeds,
  environment_spec) triple. Reproducibility is inherited from the
  runner's CRN discipline.
- The evaluator is stateless. Each call is independent.

Relationship to SimOpt
----------------------

When a SimOpt Problem class is eventually built, it wraps this evaluator:

    class PrimordialSoupProblem(Problem):
        def replicate(self, solution, rng_list):
            # Map solution vector → GovernanceParams
            # Map SimOpt RNG → world_seed
            # Call evaluate_policy(...)
            # Map ObjectiveResult → SimOpt responses

The evaluator is the stable contract between these layers.

Usage example::

    from primordial_soup.evaluator import (
        GovernanceParams,
        ObjectiveResult,
        evaluate_policy,
    )
    from primordial_soup.presets import make_environment_spec

    params = GovernanceParams(
        policy_preset="balanced",
        ramp_period=4,
        team_count=8,
        total_labor_endowment=8,
    )
    env = make_environment_spec("balanced_incumbent")
    result = evaluate_policy(params, seeds=(42, 43, 44), environment_spec=env)
    print(result.mean_cumulative_value)
    print(result.per_seed_results)

Design references:
    - docs/implementation/simopt_notes.md
    - docs/design/state_definition_and_markov_property.md
    - docs/implementation/2026-03-16 Implementation Plan.md (Stage 6)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from primordial_soup.config import (
    GovernanceConfig,
    PortfolioMixTargets,
    ReportingConfig,
    SimulationConfiguration,
    WorkforceConfig,
)
from primordial_soup.presets import (
    make_aggressive_stop_loss_governance_config,
    make_balanced_governance_config,
    make_patient_moonshot_governance_config,
)
from primordial_soup.runner import run_single_regime
from primordial_soup.types import RampShape
from primordial_soup.workbench import make_policy, summarize_run_result

if TYPE_CHECKING:
    from primordial_soup.campaign import EnvironmentSpec

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Input: governance parameter vector
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GovernanceParams:
    """Governance parameter vector for the evaluator.

    Captures all governance-layer inputs that an optimizer might vary:
    the policy preset (operating policy), workforce architecture, and
    optional portfolio guardrails. Environmental conditions are held
    fixed and supplied separately via the environment_spec argument.

    This is the optimizer-facing input surface. It does not duplicate
    every field on GovernanceConfig — it exposes only the parameters
    that are meaningful to vary in an optimization context.

    Attributes:
        policy_preset: Named operating policy preset. One of "balanced",
            "aggressive_stop_loss", "patient_moonshot".
        team_count: Number of parallel work units.
        total_labor_endowment: Total labor units.
        team_sizes: Per-team sizes. None = equal-sized teams.
        ramp_period: Team switching-cost ramp duration in ticks.
        ramp_shape: Ramp multiplier curve shape.
        portfolio_mix_targets: Optional portfolio labor-share targets.
        low_quality_belief_threshold: Portfolio guardrail threshold.
        max_low_quality_belief_labor_share: Portfolio labor cap.
        max_single_initiative_labor_share: Concentration cap.
    """

    policy_preset: str = "balanced"

    # Workforce architecture.
    # Defaults match the canonical baseline: 24 mixed-size teams
    # (10×5 + 12×10 + 2×20 = 210 total labor). See presets.py
    # make_baseline_workforce_config() for rationale.
    team_count: int = 24
    total_labor_endowment: int = 210
    team_sizes: tuple[int, ...] | None = (
        5,
        5,
        5,
        5,
        5,
        5,
        5,
        5,
        5,
        5,
        10,
        10,
        10,
        10,
        10,
        10,
        10,
        10,
        10,
        10,
        10,
        10,
        20,
        20,
    )
    ramp_period: int = 4
    ramp_shape: RampShape = RampShape.LINEAR

    # Portfolio guardrails (None = not set).
    portfolio_mix_targets: PortfolioMixTargets | None = None
    low_quality_belief_threshold: float | None = None
    max_low_quality_belief_labor_share: float | None = None
    max_single_initiative_labor_share: float | None = None


# ---------------------------------------------------------------------------
# Output: multi-dimensional response bundle
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SeedResult:
    """Response from a single seed replication.

    Contains the full summary dict from summarize_run_result() plus
    named fields for the most commonly consumed objective dimensions.
    The summary dict provides access to all metrics without requiring
    the evaluator to anticipate every downstream use.

    Attributes:
        seed: World seed for this replication.
        cumulative_value: Total portfolio value realized over the run.
        major_win_count: Number of major-win discovery events.
        terminal_capability: Portfolio capability scalar at final tick.
        free_value_per_tick: Terminal aggregate residual rate.
        idle_team_tick_fraction: Fraction of available team-ticks idle.
        ramp_labor_fraction: Fraction of team-ticks spent in ramp.
        summary: Full summary dict from summarize_run_result().
    """

    seed: int
    cumulative_value: float
    major_win_count: int
    terminal_capability: float
    free_value_per_tick: float
    idle_team_tick_fraction: float
    ramp_labor_fraction: float
    summary: dict[str, Any]


@dataclass(frozen=True)
class ObjectiveResult:
    """Multi-dimensional response bundle from the evaluator.

    Contains per-seed results and cross-seed aggregates. The aggregates
    are simple means — any more sophisticated aggregation (medians,
    percentiles, risk measures) belongs in the optimizer or analysis
    layer, not here.

    Attributes:
        per_seed_results: One SeedResult per seed, in seed order.
        n_seeds: Number of seeds evaluated.
        mean_cumulative_value: Mean of cumulative_value across seeds.
        mean_major_win_count: Mean of major_win_count across seeds.
        mean_terminal_capability: Mean of terminal_capability across seeds.
        mean_free_value_per_tick: Mean of free_value_per_tick across seeds.
        mean_idle_fraction: Mean of idle_team_tick_fraction across seeds.
        mean_ramp_labor_fraction: Mean of ramp_labor_fraction across seeds.
        total_major_wins: Sum of major_win_count across all seeds.
    """

    per_seed_results: tuple[SeedResult, ...]
    n_seeds: int
    mean_cumulative_value: float
    mean_major_win_count: float
    mean_terminal_capability: float
    mean_free_value_per_tick: float
    mean_idle_fraction: float
    mean_ramp_labor_fraction: float
    total_major_wins: int


# ---------------------------------------------------------------------------
# Core evaluator function
# ---------------------------------------------------------------------------


def evaluate_policy(
    params: GovernanceParams,
    seeds: tuple[int, ...],
    environment_spec: EnvironmentSpec,
    *,
    reporting: ReportingConfig | None = None,
) -> ObjectiveResult:
    """Evaluate a governance parameter vector across multiple seeds.

    This is the primary evaluator entry point. It resolves the governance
    parameters into concrete config types, runs one simulation per seed
    using existing runner machinery, and assembles a multi-dimensional
    response bundle.

    The evaluator is stateless and deterministic for the same inputs.
    Each call is independent — no state is carried between calls.

    Args:
        params: Governance parameter vector to evaluate.
        seeds: World seeds for initiative pool generation. Each seed
            produces one independent replication.
        environment_spec: Environment specification (initiative pool,
            time, model). Held fixed across seeds and across optimizer
            iterations. Produced by make_environment_spec() or the
            workbench.
        reporting: Optional reporting config override. Defaults to
            minimal reporting (manifest + events, no per-tick logs)
            for performance.

    Returns:
        ObjectiveResult with per-seed and aggregate responses.

    Raises:
        ValueError: If params.policy_preset is not recognized, or if
            workforce parameters are inconsistent.
    """
    if not seeds:
        raise ValueError("seeds must not be empty.")

    # --- Resolve governance config from preset ---
    governance = _resolve_governance(params, environment_spec.model)

    # --- Resolve workforce ---
    workforce = _resolve_workforce(params)

    # --- Reporting config: default to lightweight for optimizer use ---
    if reporting is None:
        reporting = ReportingConfig(
            record_manifest=True,
            record_per_tick_logs=False,
            record_event_log=True,
        )

    # --- Instantiate the policy ---
    policy = make_policy(governance)

    # --- Run one replication per seed ---
    seed_results: list[SeedResult] = []
    for seed in seeds:
        sim_config = SimulationConfiguration(
            world_seed=seed,
            time=environment_spec.time,
            teams=workforce,
            model=environment_spec.model,
            governance=governance,
            reporting=reporting,
            initiative_generator=environment_spec.initiative_generator,
        )

        run_result, _ = run_single_regime(sim_config, policy)
        summary = summarize_run_result(run_result)

        seed_results.append(
            SeedResult(
                seed=seed,
                cumulative_value=summary["cumulative_value"],
                major_win_count=summary["major_win_count"],
                terminal_capability=summary["productivity_at_end"],
                free_value_per_tick=summary["free_value_per_tick"],
                idle_team_tick_fraction=summary["idle_team_tick_fraction"],
                ramp_labor_fraction=summary["ramp_labor_fraction"],
                summary=summary,
            )
        )

    # --- Aggregate across seeds ---
    n = len(seed_results)
    return ObjectiveResult(
        per_seed_results=tuple(seed_results),
        n_seeds=n,
        mean_cumulative_value=sum(r.cumulative_value for r in seed_results) / n,
        mean_major_win_count=sum(r.major_win_count for r in seed_results) / n,
        mean_terminal_capability=sum(r.terminal_capability for r in seed_results) / n,
        mean_free_value_per_tick=sum(r.free_value_per_tick for r in seed_results) / n,
        mean_idle_fraction=sum(r.idle_team_tick_fraction for r in seed_results) / n,
        mean_ramp_labor_fraction=sum(r.ramp_labor_fraction for r in seed_results) / n,
        total_major_wins=sum(r.major_win_count for r in seed_results),
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _resolve_governance(
    params: GovernanceParams,
    model: Any,
) -> GovernanceConfig:
    """Resolve GovernanceParams into a GovernanceConfig.

    Uses the preset factory functions to build the base config, then
    applies portfolio guardrails from the params.

    Args:
        params: Governance parameter vector.
        model: ModelConfig from the environment spec.

    Returns:
        Fully resolved GovernanceConfig.

    Raises:
        ValueError: If the policy preset is not recognized.
    """
    import dataclasses

    kwargs = {
        "exec_attention_budget": model.exec_attention_budget,
        "default_initial_quality_belief": model.default_initial_quality_belief,
    }

    preset = params.policy_preset
    if preset == "balanced":
        base = make_balanced_governance_config(**kwargs)
    elif preset == "aggressive_stop_loss":
        base = make_aggressive_stop_loss_governance_config(**kwargs)
    elif preset == "patient_moonshot":
        base = make_patient_moonshot_governance_config(**kwargs)
    else:
        raise ValueError(
            f"Unknown policy preset: {preset!r}. "
            f"Valid presets: balanced, aggressive_stop_loss, patient_moonshot."
        )

    # Apply portfolio guardrails from params.
    return dataclasses.replace(
        base,
        low_quality_belief_threshold=params.low_quality_belief_threshold,
        max_low_quality_belief_labor_share=params.max_low_quality_belief_labor_share,
        max_single_initiative_labor_share=params.max_single_initiative_labor_share,
        portfolio_mix_targets=params.portfolio_mix_targets,
    )


def _resolve_workforce(params: GovernanceParams) -> WorkforceConfig:
    """Resolve GovernanceParams into a WorkforceConfig.

    Args:
        params: Governance parameter vector.

    Returns:
        Resolved WorkforceConfig.

    Raises:
        ValueError: If team sizes are inconsistent.
    """
    if params.team_sizes is not None:
        if len(params.team_sizes) != params.team_count:
            raise ValueError(
                f"team_sizes length ({len(params.team_sizes)}) must match "
                f"team_count ({params.team_count})."
            )
        if sum(params.team_sizes) != params.total_labor_endowment:
            raise ValueError(
                f"team_sizes sum ({sum(params.team_sizes)}) must equal "
                f"total_labor_endowment ({params.total_labor_endowment})."
            )
        team_size: int | tuple[int, ...] = params.team_sizes
    else:
        if params.total_labor_endowment % params.team_count != 0:
            raise ValueError(
                f"total_labor_endowment ({params.total_labor_endowment}) must be "
                f"divisible by team_count ({params.team_count}) when team_sizes "
                f"is not specified."
            )
        team_size = params.total_labor_endowment // params.team_count

    return WorkforceConfig(
        team_count=params.team_count,
        team_size=team_size,
        ramp_period=params.ramp_period,
        ramp_multiplier_shape=params.ramp_shape,
    )
