"""Configuration presets and named environment families.

This module provides factory functions that construct complete
SimulationConfiguration instances for each of the three canonical
governance archetypes:

    - **Balanced** (make_balanced_config): The canonical reference
      baseline. Moderate stop thresholds, equal attention allocation,
      all four stop rules active. Per experiments.md §Named anchor
      archetypes.

    - **Aggressive Stop-Loss** (make_aggressive_stop_loss_config):
      Tight stop thresholds, lower patience windows, and rapid
      redeployment after negative signals. Per experiments.md §Named
      anchor archetypes.

    - **Patient Moonshot** (make_patient_moonshot_config): Confidence-
      decline stopping disabled, longer patience windows, higher
      tolerance for execution overrun. Holds longer on high-potential
      initiatives. Per experiments.md §Named anchor archetypes.

Environment families:
    The canonical study evaluates governance regimes across a small set
    of **named environment families** representing plausibly different
    organizational worlds. Each family defines a distinct initiative pool
    composition (initiative mix, right-tail incidence, and duration
    structure) while sharing the same TimeConfig, WorkforceConfig, and
    ModelConfig.

    - **balanced_incumbent** (default): Mid-case major-win environment
      with multi-year right-tail durations. The canonical baseline.
    - **short_cycle_throughput**: Mature, quick-win-heavy world with
      lower right-tail representation and shorter right-tail durations.
    - **discovery_heavy**: Strong-builder / favorable-domain world with
      more right-tail initiatives and longer exploratory durations.

    Families are defined and frozen before the comparative governance
    campaign begins, so governance findings can be interpreted as holding
    within, across, or conditional on those environments rather than as
    artifacts of one hand-tuned generator configuration.

    Key right-tail parameters were calibrated in March 2026 after a
    structural collapse finding (zero major wins across all archetypes).
    The calibration used triangulation from multiple independent evidence
    sources: incumbent new-business-building research, internal venture
    and exploratory-innovation evidence, and parametric analysis of Beta
    distributions against the threshold rule. These sources consistently
    indicate that company-level breakthrough outcomes are rare among
    completed exploratory initiatives, supporting calibration of
    major-win incidence in the low-single-digit range (0.3–4%). The
    same evidence supports treating right-tail initiatives as multi-year
    efforts. See docs/design/calibration_note.md for the full evidence
    chain and parameter derivation.

Historical note:
    The 2026-03-12 validation campaign used a repaired single-baseline
    configuration to reactivate right-tail major-win dynamics after an
    earlier zero-major-win failure. That repaired configuration is no
    longer the canonical baseline. The canonical study now uses named
    environment families validated for:
        (1) no pool exhaustion,
        (2) non-zero major-win mechanism activation, and
        (3) plausible right-tail duration structure.

Design posture:
    - Pool exhaustion is a configuration error, not a regime result.
    - Major wins are rare strategic events tracked separately from
      ordinary realized value.
    - Right-tail durations are calibrated as multi-year exploratory
      efforts, not as quick-win variants.

Design references:
    - docs/design/experiments.md (archetype descriptions, sweep design)
    - docs/design/sourcing_and_generation.md (attribute ranges)
    - docs/design/governance.md (stop rules, attention semantics)
    - docs/design/generator_validity_memo.md (calibration evidence)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Literal

from primordial_soup.config import (
    FrontierSpec,
    GovernanceConfig,
    InitiativeGeneratorConfig,
    InitiativeTypeSpec,
    ModelConfig,
    PortfolioMixTargets,
    ReportingConfig,
    SimulationConfiguration,
    TimeConfig,
    WorkforceConfig,
)
from primordial_soup.types import (
    BetaDistribution,
    LogNormalDistribution,
    RampShape,
)

if TYPE_CHECKING:
    from primordial_soup.campaign import EnvironmentSpec, WorkforceArchitectureSpec

logger = logging.getLogger(__name__)


# ===========================================================================
# Environment family selector
# ===========================================================================
#
# Named environment families represent plausibly different organizational
# worlds. They differ in initiative mix, right-tail incidence, and duration
# structure but share the same TimeConfig, WorkforceConfig, and ModelConfig.
# Families are defined and frozen before the comparative governance campaign
# begins.

EnvironmentFamilyName = Literal[
    "balanced_incumbent",
    "short_cycle_throughput",
    "discovery_heavy",
]

# All families share the same total pool size. Pool exhaustion is a
# configuration error, not a regime result.
_FAMILY_POOL_SIZE: int = 200


# ===========================================================================
# Baseline environment configuration (shared across all families)
# ===========================================================================
#
# Shared environment across all archetypes. Per experiments.md: the
# canonical governance study holds the environment configuration fixed
# and varies governance regime × world_seed.


def make_baseline_time_config() -> TimeConfig:
    """Build the shared baseline TimeConfig.

    Horizon of 313 ticks (weeks). One tick represents one calendar
    week; 313 weeks ≈ 6 years, a reasonable long-term planning horizon
    for large incumbent firms. This gives patient governance regimes
    enough window to observe completions of initiatives drawn from the
    upper end of the right-tail duration range, even when those
    initiatives are assigned mid-run.
    """
    return TimeConfig(
        tick_horizon=313,
        tick_label="week",
    )


def make_baseline_workforce_config() -> WorkforceConfig:
    """Build the shared baseline WorkforceConfig.

    210 total labor across 24 teams of mixed sizes. 10 small squads (5),
    12 medium teams (10), and 2 large program teams (20). This creates
    genuine governance trade-offs in team assignment: small teams handle
    quick-wins and enablers efficiently, medium teams can staff flywheels,
    and only the large teams can handle the biggest right-tail bets.

    The 10/12/2 split is calibrated so that size-5 teams have enough
    matching work (quick-wins + small enablers) without exhausting
    their pool too early and sitting idle. The 12 size-10 teams are the
    primary workforce for flywheels (required_team_size 8-10).
    """
    return WorkforceConfig(
        team_count=24,
        team_size=(
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
        ),
        ramp_period=4,
        ramp_multiplier_shape=RampShape.LINEAR,
    )


def make_baseline_model_config() -> ModelConfig:
    """Build the shared baseline ModelConfig.

    World-evolution parameters that control signal generation, learning,
    capability dynamics, and attention curve shape. These are environment
    parameters, not governance decisions.

    exec_attention_budget is set conservatively high (40.0) so that
    attention-feasibility violations are negligible under any governance
    archetype. Per experiments.md §Canonical experiment posture on budget
    binding: realized attention should be determined by governance policy,
    not by engine-side rejection/clamping.
    """
    return ModelConfig(
        # --- Attention budget: conservatively high ---
        # With 24 teams, even if all 24 initiatives get attention_max = 1.0,
        # the sum is 24.0. Setting budget to 30.0 gives headroom.
        exec_attention_budget=30.0,
        # --- Observation noise ---
        base_signal_st_dev_default=0.15,
        # dependency_noise_exponent (alpha_d): moderate amplification
        dependency_noise_exponent=1.0,
        # Initial quality belief: c_0 = 0.5 (uninformative prior)
        default_initial_quality_belief=0.5,
        # reference_ceiling: median of right-tail observable ceilings.
        # Right-tail ceilings drawn LogNormal(4.0, 0.5) → median ~55.
        # Use 50 as a round central value.
        reference_ceiling=50.0,
        # --- Attention curve g(a) ---
        # a_min: attention floor below which g(a) = g_min
        attention_noise_threshold=0.15,
        # k_low: penalty exponent below a_min
        low_attention_penalty_slope=2.0,
        # k: gain exponent above a_min
        attention_curve_exponent=0.5,
        # g_min: floor of g(a)
        min_attention_noise_modifier=0.3,
        # g_max: uncapped
        max_attention_noise_modifier=None,
        # --- Learning rates ---
        learning_rate=0.1,  # eta
        dependency_learning_scale=None,  # canonical formula L(d) = 1 - d
        # --- Execution signal ---
        execution_signal_st_dev=0.15,  # sigma_exec
        execution_learning_rate=0.1,  # eta_exec
        # --- Portfolio capability ---
        max_portfolio_capability=3.0,  # C_max
        capability_decay=0.005,  # slow decay toward 1.0
    )


def make_initiative_generator_config(
    family: EnvironmentFamilyName = "balanced_incumbent",
) -> InitiativeGeneratorConfig:
    """Build an InitiativeGeneratorConfig for a named environment family.

    Environment families are the canonical mechanism for representing
    plausibly different organizational worlds in the study. They are
    grounded by independent empirical calibration where available and
    frozen before the comparative governance campaign begins.

    Historical note:
        The 2026-03-12 validation campaign used a repaired single-baseline
        configuration to reactivate right-tail major-win dynamics after an
        earlier zero-major-win failure. That repaired configuration is no
        longer the canonical baseline. The canonical study now uses named
        environment families validated for:
            (1) no pool exhaustion,
            (2) non-zero major-win mechanism activation, and
            (3) plausible right-tail duration structure.

    Current family design posture:
        - Pool exhaustion is a configuration error, not a regime result.
        - Major wins are rare strategic events tracked separately from
          ordinary realized value.
        - Right-tail durations are calibrated as multi-year exploratory
          efforts, not as quick-win variants.

    Family differences:
        Only the right-tail type spec and type counts change across
        families. Flywheel, enabler, and quick-win type parameters
        (quality distributions, durations, residual rates, etc.) remain
        identical across all three families, ensuring family differences
        are interpretable as differences in right-tail opportunity
        structure and initiative mix.

    Args:
        family: Named environment family. Defaults to "balanced_incumbent".

    Returns:
        InitiativeGeneratorConfig for the specified family.
    """
    # --- Right-tail type spec (family-specific) ---
    right_tail_spec = _make_right_tail_spec(family)

    # --- Non-right-tail counts ---
    # Total pool is always _FAMILY_POOL_SIZE (200). Flywheel and enabler
    # counts vary by family; quick-win count adjusts to fill the remainder.
    #
    # Family-specific pool composition. Balanced_incumbent has a large
    # flywheel base reflecting an established compounding-value portfolio.
    # Short_cycle_throughput has fewer flywheels (more quick wins).
    # Discovery_heavy has the fewest flywheels (more right-tail bets).
    if family == "balanced_incumbent":
        flywheel_count = 70
        enabler_count = 30
    elif family == "short_cycle_throughput":
        flywheel_count = 50
        enabler_count = 30
    elif family == "discovery_heavy":
        flywheel_count = 40
        enabler_count = 30
    else:
        flywheel_count = 40
        enabler_count = 30
    quick_win_count = _FAMILY_POOL_SIZE - right_tail_spec.count - flywheel_count - enabler_count

    # --- Flywheel type spec (shared across families) ---
    # High mean, low variance quality. Long duration. Residual on
    # completion with moderate rate and slow decay (persistent value).
    flywheel_spec = InitiativeTypeSpec(
        generation_tag="flywheel",
        count=flywheel_count,
        # Beta with high mean, low variance: alpha=6, beta=2 → mean≈0.75
        quality_distribution=BetaDistribution(alpha=6.0, beta=2.0),
        base_signal_st_dev_range=(0.05, 0.15),
        dependency_level_range=(0.1, 0.4),
        # Required team size: 8–10 people. Size-10 teams can handle all
        # flywheels; size-5 teams cannot.
        required_team_size_range=(8, 10),
        # Duration: 25–45 ticks (6–10 months).
        true_duration_range=(25, 45),
        # Planned duration: slight overestimate of true duration range
        planned_duration_range=(30, 55),
        residual_enabled=True,
        residual_activation_state="completed",
        # Moderate-to-high residual rate; persistent flywheel momentum
        residual_rate_range=(0.5, 2.0),
        # Low but positive exponential decay
        residual_decay_range=(0.005, 0.02),
        # Screening signal: moderate noise. Flywheels have established
        # business models so intake screening is informative but not
        # precise — some flywheels look good on paper but underperform,
        # and vice versa. sigma_screen=0.15 means initial beliefs are
        # correlated with true quality but with meaningful uncertainty.
        screening_signal_st_dev=0.15,
        # Dynamic frontier: slow declining quality as the flywheel
        # landscape is consumed. Per dynamic_opportunity_frontier.md §1:
        # degradation_rate=0.01 means alpha drops ~1% per resolved initiative.
        # replenishment_threshold=3 keeps a buffer of unassigned initiatives
        # per family so freed teams of any size can find feasible work
        # (avoids artificial idleness from team-size mismatches).
        frontier=FrontierSpec(
            frontier_degradation_rate=0.01,
            frontier_quality_floor=0.1,
            replenishment_threshold=3,
        ),
    )

    # --- Enabler type spec (shared across families) ---
    # Moderate quality. Moderate duration. Capability contribution on
    # completion. No residual channel.
    enabler_spec = InitiativeTypeSpec(
        generation_tag="enabler",
        count=enabler_count,
        # Beta moderate mean: alpha=4, beta=4 → mean=0.5
        quality_distribution=BetaDistribution(alpha=4.0, beta=4.0),
        base_signal_st_dev_range=(0.05, 0.20),
        dependency_level_range=(0.0, 0.2),
        # Required team size: 5–8 people. Any size-5+ team can handle
        # enablers.
        required_team_size_range=(5, 8),
        # Duration: 10–30 ticks (sourcing_and_generation.md)
        true_duration_range=(10, 30),
        planned_duration_range=(12, 35),
        # Capability contribution: positive scale drawn uniformly
        capability_contribution_scale_range=(0.1, 0.5),
        # Screening signal: moderate noise. Enabler value (capability
        # contribution) is somewhat assessable through technical review
        # but the quality of the enabling work is uncertain until
        # underway. sigma_screen=0.20 — slightly noisier than flywheels.
        screening_signal_st_dev=0.20,
        # Dynamic frontier: very conservative declining quality.
        # Enablers are a broad but finite landscape of capability-building
        # opportunities. Per dynamic_opportunity_frontier.md §3:
        # degradation_rate=0.005 provides mild quality degradation if
        # the enabler pool is exhausted.
        frontier=FrontierSpec(
            frontier_degradation_rate=0.005,
            frontier_quality_floor=0.1,
            replenishment_threshold=3,
        ),
    )

    # --- Quick-win type spec (shared across families) ---
    # Moderate-to-high quality, low variance. Short duration.
    # Completion-lump-dominant: the primary value channel is a one-time
    # lump realized at completion. A small residual tail is permitted
    # but must not dominate the value profile.
    #
    # Per comprehensive_design_to_align_study_model_and_authoring_v2.md:
    # quick wins are completion-lump-dominant with at most a small
    # residual tail, not residual-dominant.
    quick_win_spec = InitiativeTypeSpec(
        generation_tag="quick_win",
        count=quick_win_count,
        # Beta moderate-to-high mean, low variance: alpha=5, beta=3 → mean≈0.625
        quality_distribution=BetaDistribution(alpha=5.0, beta=3.0),
        base_signal_st_dev_range=(0.05, 0.15),
        dependency_level_range=(0.0, 0.2),
        # Required team size: fixed at 5. Any team can handle quick wins.
        required_team_size=5,
        # Duration: 3–10 ticks (sourcing_and_generation.md)
        true_duration_range=(3, 10),
        planned_duration_range=(4, 12),
        # Primary value channel: completion lump. Realized once at completion.
        completion_lump_enabled=True,
        completion_lump_value_range=(1.0, 5.0),
        # Small residual tail (not the dominant value channel).
        # Rate is deliberately low relative to the lump; high decay
        # ensures the tail is bounded and secondary.
        residual_enabled=True,
        residual_activation_state="completed",
        residual_rate_range=(0.01, 0.10),
        residual_decay_range=(0.10, 0.30),
        # Screening signal: low noise. Quick wins are short, well-scoped
        # projects whose feasibility and value are relatively easy to
        # assess before committing a team. sigma_screen=0.10 means
        # intake screening is quite informative.
        screening_signal_st_dev=0.10,
        # Dynamic frontier: faster declining quality than flywheel since
        # quick wins are a shallower opportunity landscape.
        # Per dynamic_opportunity_frontier.md §1: degradation_rate=0.02.
        frontier=FrontierSpec(
            frontier_degradation_rate=0.02,
            frontier_quality_floor=0.1,
            replenishment_threshold=3,
        ),
    )

    return InitiativeGeneratorConfig(
        type_specs=(
            flywheel_spec,
            right_tail_spec,
            enabler_spec,
            quick_win_spec,
        ),
    )


def _make_right_tail_spec(family: EnvironmentFamilyName) -> InitiativeTypeSpec:
    """Build the right-tail InitiativeTypeSpec for a named environment family.

    Each family defines a distinct right-tail opportunity structure:
    quality distribution, major-win threshold, duration range, and
    count. These are the only type-level parameters that vary across
    families; all other initiative types use shared parameters.

    Right-tail calibration notes:
        Key parameters were narrowed using triangulation from multiple
        independent evidence sources: incumbent new-business-building
        research, internal venture and exploratory-innovation evidence,
        and industry analogues with measurable long-shot hit rates.
        Across those lenses, company-level breakthrough outcomes appear
        rare but non-zero among completed exploratory initiatives,
        supporting a low-single-digit conditional major-win range.
        The same evidence supports treating right-tail initiatives as
        multi-year efforts to stable resolution, which justifies
        materially longer duration settings than the earlier repaired
        validation baseline (which used true_duration_range 20–80).

    Args:
        family: Named environment family.

    Returns:
        InitiativeTypeSpec for the right-tail type in the specified family.

    Raises:
        ValueError: If the family name is not recognized.
    """
    # Shared right-tail attributes (identical across all families):
    #   generation_tag="right_tail"
    #   base_signal_st_dev_range=(0.20, 0.40)
    #   dependency_level_range=(0.2, 0.6)
    #   major_win_event_enabled=True
    #   observable_ceiling_distribution=LogNormal(mean=4.0, st_dev=0.5)
    #       → median ≈ 55, with some draws in the hundreds.
    #
    # Family-specific attributes: count, quality_distribution,
    # q_major_win_threshold, true_duration_range, planned_duration_range.

    # Observable ceiling (TAM) distribution shared by all families.
    _ceiling_dist = LogNormalDistribution(mean=4.0, st_dev=0.5)

    if family == "balanced_incumbent":
        # Mid-case major-win environment. Multi-year right-tail durations.
        # Beta(0.8, 2.0): mean ≈ 0.286, right-skewed with ~3% tail
        # above threshold 0.80. Calibrated from Project 3 parametric
        # analysis cross-referenced with Project 1 incumbent breakthrough
        # incidence evidence (0.3–4%, midpoint ~1.5%).
        # Per calibration_note.md §1.3.
        #
        # Durations 104–182 ticks (2.0–3.5 years) represent multi-year
        # exploratory efforts that can complete within the 313-tick
        # (6 year) horizon under patient governance.
        # Per calibration_note.md §1.4.
        return InitiativeTypeSpec(
            generation_tag="right_tail",
            count=20,
            quality_distribution=BetaDistribution(alpha=0.8, beta=2.0),
            base_signal_st_dev_range=(0.20, 0.40),
            dependency_level_range=(0.2, 0.6),
            # Required team size: 5–15 people. Right-tail bets span a
            # wide range of organizational commitment.
            required_team_size_range=(5, 15),
            true_duration_range=(104, 182),
            planned_duration_range=(125, 220),
            major_win_event_enabled=True,
            q_major_win_threshold=0.80,
            observable_ceiling_distribution=_ceiling_dist,
            # Screening signal: high noise. Right-tail initiatives are
            # exploratory moonshots whose true quality is inherently hard
            # to assess at intake. sigma_screen=0.30 means initial beliefs
            # are weakly correlated with true quality — governance gets a
            # rough signal but cannot reliably rank right-tail candidates.
            screening_signal_st_dev=0.30,
            # Prize-preserving refresh: stopped right-tail initiatives
            # make their ceiling available for re-attempt with fresh quality.
            # No general declining frontier (rate=0); no per-attempt
            # degradation by default (study hypothesis parameter).
            frontier=FrontierSpec(
                frontier_degradation_rate=0.0,
                frontier_quality_floor=0.1,
                replenishment_threshold=3,
                right_tail_refresh_quality_degradation=0.0,
            ),
        )

    if family == "short_cycle_throughput":
        # Mature, quick-win-heavy world. Lower right-tail representation
        # and shorter right-tail durations. Fewer right-tail initiatives
        # (24) are offset by more quick wins (106).
        # Beta(0.6, 2.5): mean ≈ 0.194, right-skewed with ~1% tail
        # above threshold 0.80. Scarcer major wins than balanced,
        # consistent with a mature environment where breakthrough
        # opportunities are rarer.
        # Per calibration_note.md §1.3.
        #
        # Durations 80–156 ticks (1.5–3.0 years) represent shorter-cycle
        # exploratory efforts in a mature operational world.
        # Per calibration_note.md §1.4.
        return InitiativeTypeSpec(
            generation_tag="right_tail",
            count=16,
            quality_distribution=BetaDistribution(alpha=0.6, beta=2.5),
            base_signal_st_dev_range=(0.20, 0.40),
            dependency_level_range=(0.2, 0.6),
            # Required team size: 5–15 people. Right-tail bets span a
            # wide range of organizational commitment.
            required_team_size_range=(5, 15),
            true_duration_range=(80, 156),
            planned_duration_range=(96, 187),
            major_win_event_enabled=True,
            q_major_win_threshold=0.80,
            observable_ceiling_distribution=_ceiling_dist,
            # Screening signal: high noise, same as balanced_incumbent.
            screening_signal_st_dev=0.30,
            frontier=FrontierSpec(
                frontier_degradation_rate=0.0,
                frontier_quality_floor=0.1,
                replenishment_threshold=3,
                right_tail_refresh_quality_degradation=0.0,
            ),
        )

    if family == "discovery_heavy":
        # Strong-builder / favorable-domain world. More right-tail
        # representation (56) offset by fewer quick wins (74).
        # Beta(1.2, 1.8): mean ≈ 0.400, less skewed with ~5–8% tail
        # above threshold 0.80. Richer major-win environment where
        # patient governance has more opportunities to discover
        # breakthroughs.
        # Per calibration_note.md §1.3.
        #
        # Durations 130–260 ticks (2.5–5.0 years) represent longer
        # exploratory efforts in a discovery-rich environment. The
        # upper range approaches the 313-tick horizon, requiring
        # genuine governance patience for completion.
        # Per calibration_note.md §1.4.
        return InitiativeTypeSpec(
            generation_tag="right_tail",
            count=56,
            quality_distribution=BetaDistribution(alpha=1.2, beta=1.8),
            base_signal_st_dev_range=(0.20, 0.40),
            dependency_level_range=(0.2, 0.6),
            # Required team size: 5–15 people. Right-tail bets span a
            # wide range of organizational commitment.
            required_team_size_range=(5, 15),
            true_duration_range=(130, 260),
            planned_duration_range=(156, 312),
            major_win_event_enabled=True,
            q_major_win_threshold=0.80,
            observable_ceiling_distribution=_ceiling_dist,
            # Screening signal: high noise, same as balanced_incumbent.
            screening_signal_st_dev=0.30,
            frontier=FrontierSpec(
                frontier_degradation_rate=0.0,
                frontier_quality_floor=0.1,
                replenishment_threshold=3,
                right_tail_refresh_quality_degradation=0.0,
            ),
        )

    raise ValueError(
        f"Unknown environment family: {family!r}. "
        f"Valid families: balanced_incumbent, short_cycle_throughput, discovery_heavy."
    )


def make_baseline_initiative_generator_config() -> InitiativeGeneratorConfig:
    """Build the balanced_incumbent InitiativeGeneratorConfig.

    Backward-compatible wrapper. Equivalent to:
        make_initiative_generator_config("balanced_incumbent")
    """
    return make_initiative_generator_config("balanced_incumbent")


def make_baseline_reporting_config() -> ReportingConfig:
    """Build the shared baseline ReportingConfig.

    All output channels enabled for canonical experiments.
    """
    return ReportingConfig(
        record_manifest=True,
        record_per_tick_logs=True,
        record_event_log=True,
    )


# ===========================================================================
# Step 7b — Balanced preset factory
# ===========================================================================


def make_balanced_governance_config(
    *,
    exec_attention_budget: float,
    default_initial_quality_belief: float,
) -> GovernanceConfig:
    """Build the Balanced archetype GovernanceConfig.

    Moderate stop thresholds and broadly even attention distribution.
    Exercises all four stop rules (confidence decline, TAM adequacy,
    stagnation, execution overrun) without strongly biasing toward
    either early stopping or extreme patience.

    All portfolio-risk parameters set explicitly, even when None.

    Per experiments.md §Named anchor archetypes: "Balanced".

    Args:
        exec_attention_budget: Read-only copy from ModelConfig.
        default_initial_quality_belief: Read-only copy from ModelConfig.

    Returns:
        GovernanceConfig for the Balanced archetype.
    """
    return GovernanceConfig(
        policy_id="balanced",
        exec_attention_budget=exec_attention_budget,
        default_initial_quality_belief=default_initial_quality_belief,
        # --- Stop thresholds: moderate ---
        # Confidence decline: stop if quality_belief_t < 0.3
        # (well below initial 0.5, but not negligible)
        confidence_decline_threshold=0.3,
        # TAM adequacy: stop if quality_belief_t stays below 30% of
        # initial belief for base_tam_patience_window reviewed ticks
        tam_threshold_ratio=0.6,
        # TAM patience: 10 consecutive reviews below TAM ratio
        base_tam_patience_window=10,
        # --- Stagnation: moderate window ---
        # 15 staffed ticks of stagnation before stopping
        stagnation_window_staffed_ticks=15,
        # Belief change < 0.02 is considered stagnant
        stagnation_belief_change_threshold=0.02,
        # --- Attention: moderate bounds ---
        # Floor ensures meaningful signal on every initiative receiving
        # attention. No cap — even attention across active initiatives.
        attention_min=0.15,
        attention_max=None,
        # --- Execution overrun: moderate ---
        # Stop if execution_belief_t < 0.4
        exec_overrun_threshold=0.4,
        # --- Portfolio-risk controls: all explicitly None ---
        # Per plan Step 7b: set ALL portfolio-risk parameters
        # explicitly, even when the baseline value is None.
        low_quality_belief_threshold=None,
        max_low_quality_belief_labor_share=None,
        max_single_initiative_labor_share=None,
        # --- Portfolio mix targets: moderate diversification ---
        # Balanced governance allocates labor roughly in proportion to
        # the initiative mix, with a 10% right-tail cap reflecting
        # a conservative posture toward speculative bets.
        portfolio_mix_targets=PortfolioMixTargets(
            bucket_targets=(
                ("flywheel", 0.40),
                ("right_tail", 0.10),
                ("enabler", 0.15),
                ("quick_win", 0.35),
            ),
            tolerance=0.10,
        ),
    )


def make_balanced_config(
    world_seed: int,
    family: EnvironmentFamilyName = "balanced_incumbent",
) -> SimulationConfiguration:
    """Build a complete SimulationConfiguration for the Balanced archetype.

    Combines the environment for the specified family (TimeConfig,
    WorkforceConfig, ModelConfig, InitiativeGeneratorConfig) with the
    Balanced GovernanceConfig. This is the canonical reference baseline.

    The paired policy is BalancedPolicy().

    Per experiments.md: the recommended starting point for implementation
    validation and the study's reference baseline.

    Args:
        world_seed: Seed for deterministic world generation.
        family: Named environment family. Defaults to "balanced_incumbent".

    Returns:
        Complete SimulationConfiguration for one Balanced run.
    """
    model = make_baseline_model_config()
    return SimulationConfiguration(
        world_seed=world_seed,
        time=make_baseline_time_config(),
        teams=make_baseline_workforce_config(),
        model=model,
        governance=make_balanced_governance_config(
            exec_attention_budget=model.exec_attention_budget,
            default_initial_quality_belief=model.default_initial_quality_belief,
        ),
        reporting=make_baseline_reporting_config(),
        initiative_generator=make_initiative_generator_config(family),
    )


# ===========================================================================
# Step 7d — Aggressive Stop-Loss preset factory
# ===========================================================================


def make_aggressive_stop_loss_governance_config(
    *,
    exec_attention_budget: float,
    default_initial_quality_belief: float,
) -> GovernanceConfig:
    """Build the Aggressive Stop-Loss archetype GovernanceConfig.

    Tight stop thresholds, shorter patience windows, lower tolerance for
    execution overrun. Stops earlier and more aggressively than Balanced.
    Favors rapid redeployment of freed teams.

    Per experiments.md §Named anchor archetypes: "Aggressive stop-loss".

    Args:
        exec_attention_budget: Read-only copy from ModelConfig.
        default_initial_quality_belief: Read-only copy from ModelConfig.

    Returns:
        GovernanceConfig for the Aggressive Stop-Loss archetype.
    """
    return GovernanceConfig(
        policy_id="aggressive_stop_loss",
        exec_attention_budget=exec_attention_budget,
        default_initial_quality_belief=default_initial_quality_belief,
        # --- Stop thresholds: tight ---
        # Confidence decline: stop at higher threshold (less tolerant
        # of belief drops from 0.5 initial).
        confidence_decline_threshold=0.4,
        # TAM adequacy: stop if belief stays below 70% of initial for
        # a short patience window.
        tam_threshold_ratio=0.7,
        # TAM patience: only 5 consecutive reviews (half of Balanced)
        base_tam_patience_window=5,
        # --- Stagnation: shorter window ---
        # 8 staffed ticks (about half of Balanced)
        stagnation_window_staffed_ticks=8,
        stagnation_belief_change_threshold=0.02,
        # --- Attention: moderate bounds (same as Balanced) ---
        # Attention allocation breadth is a sweep dimension, not an
        # archetype distinction (per experiments.md).
        attention_min=0.15,
        attention_max=None,
        # --- Execution overrun: tight ---
        # Stop if execution_belief_t < 0.5 (stricter than Balanced 0.4)
        exec_overrun_threshold=0.5,
        # --- Portfolio-risk controls: all explicitly None ---
        low_quality_belief_threshold=None,
        max_low_quality_belief_labor_share=None,
        max_single_initiative_labor_share=None,
        # --- Portfolio mix targets: throughput-maximizing ---
        # Aggressive governance minimizes right-tail allocation (5%)
        # and maximizes quick-win throughput (50%).
        portfolio_mix_targets=PortfolioMixTargets(
            bucket_targets=(
                ("flywheel", 0.35),
                ("right_tail", 0.05),
                ("enabler", 0.10),
                ("quick_win", 0.50),
            ),
            tolerance=0.10,
        ),
    )


def make_aggressive_stop_loss_config(
    world_seed: int,
    family: EnvironmentFamilyName = "balanced_incumbent",
) -> SimulationConfiguration:
    """Build a complete SimulationConfiguration for Aggressive Stop-Loss.

    Same shared environment components as Balanced (TimeConfig,
    WorkforceConfig, ModelConfig), different GovernanceConfig.
    Initiative pool varies by environment family.
    The paired policy is AggressiveStopLossPolicy().

    Args:
        world_seed: Seed for deterministic world generation.
        family: Named environment family. Defaults to "balanced_incumbent".

    Returns:
        Complete SimulationConfiguration for one Aggressive run.
    """
    model = make_baseline_model_config()
    return SimulationConfiguration(
        world_seed=world_seed,
        time=make_baseline_time_config(),
        teams=make_baseline_workforce_config(),
        model=model,
        governance=make_aggressive_stop_loss_governance_config(
            exec_attention_budget=model.exec_attention_budget,
            default_initial_quality_belief=model.default_initial_quality_belief,
        ),
        reporting=make_baseline_reporting_config(),
        initiative_generator=make_initiative_generator_config(family),
    )


# ===========================================================================
# Step 7d — Patient Moonshot preset factory
# ===========================================================================


def make_patient_moonshot_governance_config(
    *,
    exec_attention_budget: float,
    default_initial_quality_belief: float,
) -> GovernanceConfig:
    """Build the Patient Moonshot archetype GovernanceConfig.

    Confidence-decline stopping disabled. Longer patience windows.
    Higher execution-overrun tolerance. Holds longer on high-potential
    initiatives, preserving candidates that may eventually surface
    major wins.

    Per experiments.md §Named anchor archetypes: "Patient moonshot".

    Args:
        exec_attention_budget: Read-only copy from ModelConfig.
        default_initial_quality_belief: Read-only copy from ModelConfig.

    Returns:
        GovernanceConfig for the Patient Moonshot archetype.
    """
    return GovernanceConfig(
        policy_id="patient_moonshot",
        exec_attention_budget=exec_attention_budget,
        default_initial_quality_belief=default_initial_quality_belief,
        # --- Stop thresholds: patient but not paralyzed ---
        # Confidence decline: very low threshold (0.08) so only truly
        # hopeless initiatives are stopped. This prevents the paralysis
        # observed when confidence_decline_threshold=None caused zero
        # completions across all seeds (issue #18). The threshold is
        # well below Balanced (0.2) to preserve the patient philosophy.
        confidence_decline_threshold=0.08,
        # TAM adequacy: lower ratio (more tolerant), longer patience.
        tam_threshold_ratio=0.4,
        # TAM patience: 15 consecutive reviews (50% more than Balanced 10).
        # Reduced from 20 which contributed to paralysis.
        base_tam_patience_window=15,
        # --- Stagnation: moderately longer window ---
        # 20 staffed ticks (vs Balanced 15). Reduced from 25 which
        # was too long — initiatives stagnated without being stopped.
        stagnation_window_staffed_ticks=20,
        # Slightly more tolerant epsilon
        stagnation_belief_change_threshold=0.015,
        # --- Attention: moderate bounds (same as Balanced) ---
        # Attention allocation breadth is a sweep dimension, not an
        # archetype distinction (per experiments.md).
        attention_min=0.15,
        attention_max=None,
        # --- Execution overrun: moderately tolerant ---
        # Stop if execution_belief_t < 0.35 (between Balanced 0.4
        # and the previous 0.3 which was too tolerant).
        exec_overrun_threshold=0.35,
        # --- Portfolio-risk controls: all explicitly None ---
        low_quality_belief_threshold=None,
        max_low_quality_belief_labor_share=None,
        max_single_initiative_labor_share=None,
        # --- Portfolio mix targets: exploration-heavy ---
        # Patient governance allocates 25% to right-tail speculative
        # bets — willing to make large bets on breakthrough potential.
        # Higher tolerance (15%) reflects flexible allocation.
        portfolio_mix_targets=PortfolioMixTargets(
            bucket_targets=(
                ("flywheel", 0.25),
                ("right_tail", 0.25),
                ("enabler", 0.15),
                ("quick_win", 0.35),
            ),
            tolerance=0.15,
        ),
    )


def make_patient_moonshot_config(
    world_seed: int,
    family: EnvironmentFamilyName = "balanced_incumbent",
) -> SimulationConfiguration:
    """Build a complete SimulationConfiguration for Patient Moonshot.

    Same shared environment components as Balanced (TimeConfig,
    WorkforceConfig, ModelConfig), different GovernanceConfig.
    Initiative pool varies by environment family.
    The paired policy is PatientMoonshotPolicy().

    Args:
        world_seed: Seed for deterministic world generation.
        family: Named environment family. Defaults to "balanced_incumbent".

    Returns:
        Complete SimulationConfiguration for one Patient Moonshot run.
    """
    model = make_baseline_model_config()
    return SimulationConfiguration(
        world_seed=world_seed,
        time=make_baseline_time_config(),
        teams=make_baseline_workforce_config(),
        model=model,
        governance=make_patient_moonshot_governance_config(
            exec_attention_budget=model.exec_attention_budget,
            default_initial_quality_belief=model.default_initial_quality_belief,
        ),
        reporting=make_baseline_reporting_config(),
        initiative_generator=make_initiative_generator_config(family),
    )


# ===========================================================================
# EnvironmentSpec factories
# ===========================================================================


def make_environment_spec(
    family: EnvironmentFamilyName = "balanced_incumbent",
) -> EnvironmentSpec:
    """Build an EnvironmentSpec for a named environment family.

    Combines the shared environment components (TimeConfig,
    WorkforceConfig, ModelConfig) with the family-specific
    InitiativeGeneratorConfig into a single EnvironmentSpec.

    The import of EnvironmentSpec is deferred to avoid a circular
    import (campaign.py imports from presets.py for archetype factories).

    Args:
        family: Named environment family. Defaults to "balanced_incumbent".

    Returns:
        EnvironmentSpec for the specified family.
    """
    # Deferred import to avoid circular dependency:
    # campaign.py imports presets.py for archetype governance configs,
    # so presets.py cannot import campaign.py at module level.
    from primordial_soup.campaign import EnvironmentSpec

    return EnvironmentSpec(
        time=make_baseline_time_config(),
        teams=make_baseline_workforce_config(),
        model=make_baseline_model_config(),
        initiative_generator=make_initiative_generator_config(family),
    )


def make_baseline_environment_spec() -> EnvironmentSpec:
    """Build the balanced_incumbent EnvironmentSpec.

    Backward-compatible wrapper. Equivalent to:
        make_environment_spec("balanced_incumbent")
    """
    return make_environment_spec("balanced_incumbent")


# ===========================================================================
# WorkforceArchitectureSpec factories
# ===========================================================================


def make_baseline_workforce_architecture_spec() -> WorkforceArchitectureSpec:
    """Build the baseline workforce architecture spec.

    220 total labor across 30 teams of mixed sizes, ramp period of
    4 ticks with linear ramp shape. This represents the canonical
    governance architecture choice for the baseline study.

    The existing make_baseline_workforce_config() remains as the
    primary factory for the resolved representation. This spec
    makes the architecture/environment distinction explicit for
    experiment-design purposes: total_labor_endowment is the
    environmental given, while team_count and ramp are governance
    architecture choices.

    Per docs/design/team_and_resources.md and the three-layer model
    described in docs/design/governance.md.
    """
    # Deferred import to avoid circular dependency:
    # campaign.py imports presets.py for archetype governance configs,
    # so presets.py cannot import campaign.py at module level.
    from primordial_soup.campaign import WorkforceArchitectureSpec

    return WorkforceArchitectureSpec(
        total_labor_endowment=210,
        team_count=24,
        ramp_period=4,
        ramp_multiplier_shape=RampShape.LINEAR,
    )


# ===========================================================================
# Model 0 — Simplified "VW Beetle" configuration
# ===========================================================================
#
# Model 0 is a radically simplified configuration that isolates the
# portfolio selection decision: which initiatives to start, given
# limited team capacity. All other complexity layers (residual value,
# major wins, capability, attention effects, team ramp, dependency
# friction, dynamic frontier, screening signals) are disabled via
# parameter settings — no engine code is removed.
#
# The three Model 0 governance archetypes differ ONLY in portfolio
# mix targets — what fraction of teams they allocate to each initiative
# type. All use BalancedPolicy since the differentiation is in the
# config, not the policy logic.
#
# Design reference: results/model0_plan.md


def make_model0_time_config() -> TimeConfig:
    """Build the Model 0 TimeConfig.

    Horizon of 100 ticks (weeks), approximately 2 years. Shorter than
    the full model's 313 weeks. Long enough that most initiatives can
    complete; short enough that right-tail investments started late may
    not finish before horizon, creating a genuine governance tension
    between safe short-term bets and risky long-term investments.
    """
    return TimeConfig(
        tick_horizon=100,
        tick_label="week",
    )


def make_model0_workforce_config() -> WorkforceConfig:
    """Build the Model 0 WorkforceConfig.

    10 uniform teams of size 5 (50 total labor). Uniform team sizes
    eliminate the team-size matching artifact that causes 25-36% idle
    in the full model. Every team can work on every initiative.

    Ramp period is 1 tick (effectively instant), disabling the ramp
    penalty. Teams are immediately productive after assignment.
    """
    return WorkforceConfig(
        team_count=10,
        team_size=5,
        ramp_period=1,
        ramp_multiplier_shape=RampShape.LINEAR,
    )


def make_model0_model_config() -> ModelConfig:
    """Build the Model 0 ModelConfig.

    All complexity layers disabled via parameter settings:

    - exec_attention_budget=0: no executive attention allocated.
      Per governance.md §Zero-budget special case.
    - Attention noise modifier g(a) = 1.0 everywhere: attention has
      no effect on signal quality even if allocated.
    - dependency_noise_exponent=0: no dependency-based noise.
    - max_portfolio_capability=3.0: capability mechanism active.
      Enabler completions increase C_t, improving signal quality.
    - capability_decay=0.005: slow decay toward 1.0.

    What remains active:
    - base_signal_st_dev_default=0.15: signals are noisy (learning
      is not instant).
    - learning_rate=0.1: beliefs update via EMA toward true quality.
    - execution_signal_st_dev=0.15 and execution_learning_rate=0.1:
      execution beliefs update, but execution overrun stopping is
      disabled in the governance config.
    """
    return ModelConfig(
        # No executive attention allocated.
        exec_attention_budget=0.0,
        # --- Signal noise: active but simple ---
        base_signal_st_dev_default=0.15,
        # No dependency noise amplification.
        dependency_noise_exponent=0.0,
        # Uninformative prior: all initiatives start at belief 0.5.
        default_initial_quality_belief=0.5,
        # Reference ceiling: irrelevant with no TAM/bounded-prize
        # initiatives, but must be > 0 for validation.
        reference_ceiling=50.0,
        # --- Attention curve g(a): flat at 1.0 (attention has no effect) ---
        attention_noise_threshold=0.15,
        low_attention_penalty_slope=0.0,
        attention_curve_exponent=0.5,
        min_attention_noise_modifier=1.0,
        max_attention_noise_modifier=1.0,
        # --- Learning: active ---
        learning_rate=0.1,
        dependency_learning_scale=None,  # canonical formula, but d=0 so L(d)=1
        # --- Execution signal: active but overrun stopping disabled ---
        execution_signal_st_dev=0.15,
        execution_learning_rate=0.1,
        # --- Portfolio capability: active ---
        # Enabler completions increase C_t, improving signal quality
        # for all initiatives. This is one of the three success
        # dimensions (value, major wins, organizational learning).
        max_portfolio_capability=3.0,
        capability_decay=0.005,  # slow decay toward 1.0
    )


def make_model0_initiative_generator_config() -> InitiativeGeneratorConfig:
    """Build the Model 0 InitiativeGeneratorConfig.

    50 initiatives across 4 types, each producing a different kind of
    outcome. No frontier, no screening signals, no dependency.

    The four types represent the core portfolio selection tradeoff:
    - quick_win: immediate certain value (completion lump only)
    - flywheel: ongoing compounding value (residual after completion)
    - enabler: organizational capability (C_t improvement)
    - right_tail: transformational discoveries (major wins)

    The types differ in risk/return/duration profile:
    - quick_win (15): low value (1-3), short (3-8 wk), high quality
    - flywheel (15): moderate-high value (3-8), moderate (15-30 wk)
    - enabler (10): moderate value (2-5), moderate (8-20 wk)
    - right_tail (10): wide value range (1-20), long (30-60 wk),
      low mean quality, high signal noise — the speculative bet

    All initiatives require team_size=5 (matching the uniform teams)
    so team-size matching is never a constraint.
    """
    # --- Quick-win: safe, short, low value ---
    quick_win_spec = InitiativeTypeSpec(
        generation_tag="quick_win",
        count=40,
        # High mean quality: Beta(5,3) → mean ≈ 0.63
        quality_distribution=BetaDistribution(alpha=5.0, beta=3.0),
        base_signal_st_dev_range=(0.05, 0.15),
        dependency_level_range=(0.0, 0.0),
        required_team_size=5,
        true_duration_range=(3, 8),
        planned_duration_range=(4, 10),
        # Completion lump is the only value channel.
        completion_lump_enabled=True,
        completion_lump_value_range=(1.0, 3.0),
        # All other channels disabled.
        residual_enabled=False,
        major_win_event_enabled=False,
    )

    # --- Flywheel: reliable, moderate duration, compounding value ---
    # Flywheels are the compounding-value type. Their defining
    # characteristic is ongoing residual value after completion —
    # the "flywheel" that keeps spinning. Small completion lump
    # but persistent residual stream. This makes them strategically
    # different from quick wins (immediate lump, no tail).
    flywheel_spec = InitiativeTypeSpec(
        generation_tag="flywheel",
        count=40,
        # High mean quality: Beta(6,2) → mean ≈ 0.75
        quality_distribution=BetaDistribution(alpha=6.0, beta=2.0),
        base_signal_st_dev_range=(0.05, 0.15),
        dependency_level_range=(0.0, 0.0),
        required_team_size=5,
        true_duration_range=(15, 30),
        planned_duration_range=(18, 35),
        # Small lump on completion — the upfront value is modest.
        completion_lump_enabled=True,
        completion_lump_value_range=(1.0, 3.0),
        # Residual: ongoing compounding value after completion.
        # Moderate rate with slow decay — the flywheel persists.
        residual_enabled=True,
        residual_activation_state="completed",
        residual_rate_range=(0.5, 2.0),
        residual_decay_range=(0.005, 0.02),
        major_win_event_enabled=False,
    )

    # --- Enabler: moderate quality, moderate duration and value ---
    # Enablers contribute to organizational capability (C_t) on
    # completion, improving signal quality for all initiatives.
    enabler_spec = InitiativeTypeSpec(
        generation_tag="enabler",
        count=25,
        # Moderate quality: Beta(4,4) → mean = 0.50
        quality_distribution=BetaDistribution(alpha=4.0, beta=4.0),
        base_signal_st_dev_range=(0.05, 0.20),
        dependency_level_range=(0.0, 0.0),
        required_team_size=5,
        true_duration_range=(8, 20),
        planned_duration_range=(10, 25),
        completion_lump_enabled=True,
        completion_lump_value_range=(2.0, 5.0),
        # Capability contribution: enabler completions increase C_t.
        capability_contribution_scale_range=(0.1, 0.5),
        residual_enabled=False,
        major_win_event_enabled=False,
    )

    # --- Right-tail: speculative, long, high-variance value ---
    # Right-tail initiatives can surface major wins — transformational
    # discoveries that represent qualitatively different outcomes.
    # Major wins are tracked as a count, one of the three success
    # dimensions alongside value and organizational learning.
    right_tail_spec = InitiativeTypeSpec(
        generation_tag="right_tail",
        count=25,
        # Low mean, right-skewed: Beta(0.8,2) → mean ≈ 0.29
        # Most are low quality, but occasional draws above 0.7
        # produce the high end of the value range.
        quality_distribution=BetaDistribution(alpha=0.8, beta=2.0),
        base_signal_st_dev_range=(0.20, 0.35),
        dependency_level_range=(0.0, 0.0),
        required_team_size=5,
        # Long duration: 30-60 weeks. Some will not complete
        # within the 100-tick horizon if started after tick 40-70.
        true_duration_range=(30, 60),
        planned_duration_range=(35, 70),
        # Wide value range: most produce 1-5, but occasional
        # high-quality draws produce up to 20. This creates the
        # genuine safe-vs-speculative governance tradeoff.
        completion_lump_enabled=True,
        completion_lump_value_range=(1.0, 20.0),
        residual_enabled=False,
        # Major-win tracking: q >= 0.80 at completion is a
        # transformational discovery. Same threshold as full model.
        major_win_event_enabled=True,
        q_major_win_threshold=0.80,
    )

    return InitiativeGeneratorConfig(
        type_specs=(
            flywheel_spec,
            right_tail_spec,
            enabler_spec,
            quick_win_spec,
        ),
    )


def _make_model0_governance_config(
    *,
    policy_label: str,
    portfolio_mix_targets: PortfolioMixTargets,
) -> GovernanceConfig:
    """Build a Model 0 GovernanceConfig with the given mix targets.

    All stop rules are effectively disabled. The governance decision
    is purely about initiative selection via portfolio_mix_targets.

    Args:
        policy_label: Descriptive label for this archetype (used as
            policy_id for reporting, not for policy class dispatch).
        portfolio_mix_targets: The portfolio selection strategy that
            differentiates this archetype.
    """
    return GovernanceConfig(
        # All Model 0 archetypes use BalancedPolicy (policy_id="balanced"
        # for policy dispatch). The policy_label is for display only.
        policy_id="balanced",
        exec_attention_budget=0.0,
        default_initial_quality_belief=0.5,
        # --- All stop rules disabled ---
        confidence_decline_threshold=None,
        tam_threshold_ratio=0.6,
        base_tam_patience_window=999,
        stagnation_window_staffed_ticks=999,
        stagnation_belief_change_threshold=0.02,
        # --- Attention: zero budget, zero floor ---
        attention_min=0.0,
        attention_max=None,
        # --- Execution overrun: disabled ---
        exec_overrun_threshold=None,
        # --- Portfolio risk controls: all off ---
        low_quality_belief_threshold=None,
        max_low_quality_belief_labor_share=None,
        max_single_initiative_labor_share=None,
        # --- Portfolio selection: the primary governance lever ---
        portfolio_mix_targets=portfolio_mix_targets,
    )


def make_model0_throughput_governance_config() -> GovernanceConfig:
    """Build the Model 0 Throughput-Focused GovernanceConfig.

    Prioritizes safe, short-duration initiatives. Heavy quick-win
    allocation (60%) with moderate flywheel (30%), minimal investment
    in speculative or enabling work.
    """
    return _make_model0_governance_config(
        policy_label="throughput",
        portfolio_mix_targets=PortfolioMixTargets(
            bucket_targets=(
                ("flywheel", 0.30),
                ("right_tail", 0.05),
                ("enabler", 0.05),
                ("quick_win", 0.60),
            ),
            tolerance=0.05,
        ),
    )


def make_model0_balanced_governance_config() -> GovernanceConfig:
    """Build the Model 0 Balanced GovernanceConfig.

    Even allocation across initiative types. The reference baseline.
    """
    return _make_model0_governance_config(
        policy_label="balanced",
        portfolio_mix_targets=PortfolioMixTargets(
            bucket_targets=(
                ("flywheel", 0.35),
                ("right_tail", 0.15),
                ("enabler", 0.15),
                ("quick_win", 0.35),
            ),
            tolerance=0.10,
        ),
    )


def make_model0_exploration_governance_config() -> GovernanceConfig:
    """Build the Model 0 Exploration-Focused GovernanceConfig.

    Prioritizes long-horizon speculative investments. Heavy right-tail
    allocation (40%) with moderate enabler support (20%). Willing to
    sacrifice short-term throughput for potential high-value outcomes.
    """
    return _make_model0_governance_config(
        policy_label="exploration",
        portfolio_mix_targets=PortfolioMixTargets(
            bucket_targets=(
                ("flywheel", 0.25),
                ("right_tail", 0.40),
                ("enabler", 0.20),
                ("quick_win", 0.15),
            ),
            tolerance=0.05,
        ),
    )


def make_model0_throughput_config(world_seed: int) -> SimulationConfiguration:
    """Build a complete Model 0 Throughput-Focused SimulationConfiguration.

    Args:
        world_seed: Seed for deterministic world generation.

    Returns:
        Complete SimulationConfiguration for one Model 0 Throughput run.
    """
    return SimulationConfiguration(
        world_seed=world_seed,
        time=make_model0_time_config(),
        teams=make_model0_workforce_config(),
        model=make_model0_model_config(),
        governance=make_model0_throughput_governance_config(),
        reporting=make_baseline_reporting_config(),
        initiative_generator=make_model0_initiative_generator_config(),
    )


def make_model0_balanced_config(world_seed: int) -> SimulationConfiguration:
    """Build a complete Model 0 Balanced SimulationConfiguration.

    Args:
        world_seed: Seed for deterministic world generation.

    Returns:
        Complete SimulationConfiguration for one Model 0 Balanced run.
    """
    return SimulationConfiguration(
        world_seed=world_seed,
        time=make_model0_time_config(),
        teams=make_model0_workforce_config(),
        model=make_model0_model_config(),
        governance=make_model0_balanced_governance_config(),
        reporting=make_baseline_reporting_config(),
        initiative_generator=make_model0_initiative_generator_config(),
    )


def make_model0_exploration_config(world_seed: int) -> SimulationConfiguration:
    """Build a complete Model 0 Exploration-Focused SimulationConfiguration.

    Args:
        world_seed: Seed for deterministic world generation.

    Returns:
        Complete SimulationConfiguration for one Model 0 Exploration run.
    """
    return SimulationConfiguration(
        world_seed=world_seed,
        time=make_model0_time_config(),
        teams=make_model0_workforce_config(),
        model=make_model0_model_config(),
        governance=make_model0_exploration_governance_config(),
        reporting=make_baseline_reporting_config(),
        initiative_generator=make_model0_initiative_generator_config(),
    )
