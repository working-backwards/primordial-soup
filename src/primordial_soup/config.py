"""Simulation configuration and validation.

This module defines the complete configuration contract for a simulation
run. SimulationConfiguration is the single authoritative input. It is
declarative, frozen, and opaque to the engine.

Configuration validation is the responsibility of the construction site
(runner, preset builder, sweep generator), not the simulator. The
validate_configuration function is provided for that purpose.

See interfaces.md for the canonical field definitions and validation rules.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from primordial_soup.types import (
    DistributionSpec,
    RampShape,
    ValueChannels,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Canonical initiative bucket definitions
# ---------------------------------------------------------------------------

# The four canonical initiative buckets used for portfolio mix targets.
# These names match the generation_tag vocabulary, but at runtime the
# policy classifies initiatives using observable attributes only
# (observable_ceiling, capability_contribution_scale, planned_duration_ticks).
# See governance.py classify_initiative_bucket() for the classification rules.
CANONICAL_BUCKET_NAMES: frozenset[str] = frozenset(
    {
        "flywheel",
        "right_tail",
        "enabler",
        "quick_win",
    }
)


@dataclass(frozen=True)
class PortfolioMixTargets:
    """Desired labor-share distribution across initiative buckets.

    This is a governance-architecture input: a structural preference
    for how active labor should be distributed across categories of
    work, fixed before the run begins and varied across runs as
    experimental treatments.

    Bucket names use the canonical set defined in CANONICAL_BUCKET_NAMES:
    flywheel, right_tail, enabler, quick_win. These match the
    generation_tag vocabulary. At runtime, the policy classifies
    initiatives using InitiativeObservation.generation_tag via
    classify_initiative_bucket() in governance.py.

    The policy consumes these targets as soft preferences during team
    assignment. The engine does not know they exist.

    Per portfolio_allocation_targets_proposal.md and governance.md
    §Selection and portfolio management semantics.

    Attributes:
        bucket_targets: Ordered pairs of (bucket_name, target_labor_share).
            All values must be non-negative. Must sum to 1.0 (within
            tolerance). Stored as tuple-of-tuples for immutability and
            hashability.
        tolerance: Acceptable drift from target before the policy should
            bias selection toward under-target buckets. Global, not
            per-bucket. Must be in [0, 1].
    """

    bucket_targets: tuple[tuple[str, float], ...]
    tolerance: float = 0.10

    @property
    def targets_dict(self) -> dict[str, float]:
        """Return bucket targets as a dict for O(1) lookup by bucket name."""
        return dict(self.bucket_targets)


# ---------------------------------------------------------------------------
# Sub-configurations
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TimeConfig:
    """Temporal structure of the run. Per interfaces.md."""

    tick_horizon: int
    tick_label: str = "week"


@dataclass(frozen=True)
class WorkforceConfig:
    """Realized workforce structure consumed by the simulator.

    This is the resolved representation — concrete team count, sizes,
    and ramp parameters. The simulator reads these fields directly.
    How this workforce was generated (from an architecture spec, a
    preset, or direct construction) is not visible here.

    Per interfaces.md WorkforceConfig.
    """

    team_count: int
    team_size: int | tuple[int, ...]
    ramp_period: int
    ramp_multiplier_shape: RampShape = RampShape.LINEAR

    @property
    def total_labor_endowment(self) -> int:
        """Total labor units across all teams.

        This is an environmental quantity — the aggregate productive
        capacity available to the organization. The simulator consumes
        the realized team decomposition; this property makes the
        aggregate explicit for reporting and builder-layer logic.
        """
        if isinstance(self.team_size, int):
            return self.team_count * self.team_size
        return sum(self.team_size)


@dataclass(frozen=True)
class ModelConfig:
    """Parameters governing world-state evolution.

    These are not governance decision thresholds. They control how the
    simulated world evolves, generates observations, and detects state
    transitions. Per interfaces.md ModelConfig.
    """

    # Total executive attention budget per tick (sum of all initiative
    # attention allocations must not exceed this).
    exec_attention_budget: float

    # --- Observation noise parameters ---

    # Default base noise std for quality signal observations.
    # Per-initiative base_signal_st_dev may override this.
    # sigma_base in the design docs.
    base_signal_st_dev_default: float

    # Linear scale factor for dependency-adjusted noise:
    #   effective_signal_st_dev_t = base_signal_st_dev * (1 + alpha_d * d)
    # where d = dependency_level and alpha_d = this parameter.
    # Per core_simulator.md authoritative formula.
    # NOTE: The field name "dependency_noise_exponent" is a legacy misnomer —
    # alpha_d is used as a linear scale factor, not an exponent. Renaming
    # deferred to avoid churn across config construction sites and test fixtures.
    # alpha_d in the design docs.
    dependency_noise_exponent: float

    # Default initial quality belief assigned to new initiatives (in [0, 1]).
    # Per-initiative initial_quality_belief may override this.
    default_initial_quality_belief: float

    # Scaling reference for TAM patience window calculation:
    #   effective_T_tam = ceil(T_tam * observable_ceiling / reference_ceiling)
    reference_ceiling: float

    # --- Attention curve g(a) parameters — per core_simulator.md ---
    # The attention curve maps executive_attention_t to a gain multiplier
    # g(a) that scales the learning rate. Below attention_noise_threshold,
    # g = min_attention_noise_modifier.

    # Attention level below which g(a) = min_attention_noise_modifier (floor region).
    # a_min in the design docs.
    attention_noise_threshold: float
    # Curve exponent in the low-attention region (a < attention_noise_threshold).
    # k_low in the design docs.
    low_attention_penalty_slope: float
    # Curve exponent in the high-attention region (a >= attention_noise_threshold).
    # k in the design docs.
    attention_curve_exponent: float
    # Minimum attention gain (floor of g(a) curve).
    # g_min in the design docs.
    min_attention_noise_modifier: float
    # Maximum attention gain (cap on g(a)), None = uncapped.
    # g_max in the design docs.
    max_attention_noise_modifier: float | None

    # --- Learning ---

    # Base learning rate for belief updates (eta in design docs).
    learning_rate: float
    # Optional override for dependency-adjusted learning scale L(d).
    # None means use canonical formula: L(d) = 1 - d.
    dependency_learning_scale: float | None

    # --- Execution signal — per core_simulator.md ---

    # Noise std for execution progress signal observations.
    # sigma_exec in the design docs.
    execution_signal_st_dev: float
    # Learning rate for execution belief (execution_belief_t) updates.
    # eta_exec in the design docs.
    execution_learning_rate: float

    # --- Portfolio capability — per core_simulator.md ---

    # Upper bound on portfolio capability scalar C_t (must be >= 1.0).
    # C_max in the design docs.
    max_portfolio_capability: float
    # Per-tick decay rate for capability (capability moves toward 1.0).
    capability_decay: float


@dataclass(frozen=True)
class GovernanceConfig:
    """Immutable decision parameters supplied to the governance policy.

    This dataclass contains two conceptually distinct groups of
    parameters, reflecting the study's three-layer model (see
    governance.md §Governance architecture vs. operating policy):

    **Operating-policy parameters** — per-tick decision thresholds and
    bounds that govern how the policy makes stop/continue, attention,
    and assignment decisions. These are the recurring levers that the
    policy exercises within its chosen governance architecture
    (confidence_decline_threshold through exec_overrun_threshold,
    plus attention_min and attention_max).

    **Architecture-level constraints** — structural portfolio guardrails
    set before the run begins (low_quality_belief_threshold,
    max_low_quality_belief_labor_share, max_single_initiative_labor_share).
    These are governance architecture choices, not per-tick operating
    parameters. They are surfaced through GovernanceConfig for backward
    compatibility so the policy can read them without a separate config
    object. They are not engine-enforced; the policy decides whether
    and how to honor them. A Phase 2 refactor may nest these into a
    separate dataclass.

    The policy reads all fields but cannot change them. Counters and
    rolling windows required by these thresholds live in engine-owned
    initiative state, not in hidden mutable policy memory.
    Per interfaces.md GovernanceConfig.
    """

    # Identifies which governance archetype is active (e.g., "balanced").
    policy_id: str
    # Read-only copies from ModelConfig so the policy doesn't need
    # access to the full model configuration.
    exec_attention_budget: float
    default_initial_quality_belief: float

    # ---------------------------------------------------------------
    # Operating-policy parameters (per-tick decision logic)
    # ---------------------------------------------------------------

    # --- Stop decision thresholds ---

    # Confidence threshold: stop if quality belief drops below this.
    # None = confidence-decline stopping disabled.
    # theta_stop in the design docs.
    confidence_decline_threshold: float | None
    # TAM adequacy ratio: stop if quality belief stays below this fraction
    # of initial belief for base_tam_patience_window consecutive reviewed ticks.
    # theta_tam_ratio in the design docs.
    tam_threshold_ratio: float
    # TAM patience window: number of consecutive reviews below
    # tam_threshold_ratio before triggering a TAM stop (must be int).
    # T_tam in the design docs.
    base_tam_patience_window: int

    # --- Stagnation detection ---

    # Sliding window width (in staffed ticks) for stagnation detection.
    # W_stag in the design docs.
    stagnation_window_staffed_ticks: int
    # Minimum belief change over stagnation window; below this the
    # initiative is considered stagnant.
    # epsilon_stag in the design docs.
    stagnation_belief_change_threshold: float

    # --- Attention allocation bounds ---

    # Minimum attention level when attention is allocated (in (0, 1]).
    # If attention is allocated at all, it must be >= this value.
    attention_min: float
    # Maximum attention level per initiative. None = no cap.
    attention_max: float | None

    # --- Execution overrun ---

    # Execution belief threshold: stop if execution belief drops below this.
    # None = execution-overrun stopping disabled.
    exec_overrun_threshold: float | None

    # ---------------------------------------------------------------
    # Architecture-level constraints (governance architecture guardrails)
    #
    # These are structural portfolio guardrails set before the run
    # begins. In the three-layer model they belong to governance
    # architecture, not operating policy. They are surfaced here so the
    # policy can read them without a separate config object. The engine
    # does not enforce them; the policy decides whether and how to honor
    # them. Per governance.md §Governance architecture vs. operating
    # policy and interfaces.md GovernanceConfig portfolio-risk section.
    # ---------------------------------------------------------------

    # Strategic belief level below which an initiative is considered
    # low-confidence for portfolio exposure purposes.
    # None = no low-quality threshold applied.
    low_quality_belief_threshold: float | None = None

    # Maximum share of active labor that may be allocated to initiatives
    # whose quality_belief_t is below low_quality_belief_threshold.
    # None = no labor-share cap on low-confidence work.
    max_low_quality_belief_labor_share: float | None = None

    # Maximum share of active labor that may be allocated to any single
    # initiative. None = no concentration cap.
    max_single_initiative_labor_share: float | None = None

    # Portfolio mix targets: desired labor-share distribution across
    # canonical initiative buckets. The policy may use these as soft
    # preferences during team assignment to bias selection toward
    # under-target buckets. None = no mix targets configured.
    # Per portfolio_allocation_targets_proposal.md §5.
    portfolio_mix_targets: PortfolioMixTargets | None = None


@dataclass(frozen=True)
class ReportingConfig:
    """Output behavior configuration. Must not affect simulation mechanics."""

    record_manifest: bool = True
    record_per_tick_logs: bool = True
    record_event_log: bool = True
    label_groupings: tuple[str, ...] | None = None


# ---------------------------------------------------------------------------
# Resolved initiative configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ResolvedInitiativeConfig:
    """Complete immutable configuration for a single initiative.

    All fields are set at generation time and never changed by the engine.
    This is the resolved form — no type-based branching, no unresolved
    generator parameters. Per initiative_model.md immutable attributes.
    """

    # Required fields (no defaults)
    initiative_id: str
    latent_quality: float  # q in the design docs
    dependency_level: float  # d in the design docs
    base_signal_st_dev: float  # sigma_base in the design docs
    value_channels: ValueChannels

    # Fields with defaults
    created_tick: int = 0
    required_team_size: int = 1
    true_duration_ticks: int | None = None
    observable_ceiling: float | None = None
    generation_tag: str | None = None
    initial_quality_belief: float | None = None  # None → use ModelConfig default
    planned_duration_ticks: int | None = None
    initial_execution_belief: float = 1.0  # c_exec_0 in the design docs
    capability_contribution_scale: float = 0.0

    # Staffing intensity response parameter. Controls how much additional
    # staffing above required_team_size accelerates learning. The staffing
    # multiplier applied to the learning rate is:
    #
    #   staffing_multiplier = 1.0 + staffing_response_scale
    #                             * (1.0 - required_team_size / assigned_team_size)
    #
    # When staffing_response_scale == 0.0 (the default), the multiplier is
    # always exactly 1.0 regardless of team size, preserving full backward
    # compatibility with existing configurations. When positive, larger
    # assigned teams above the minimum threshold produce faster learning
    # with diminishing returns, saturating toward 1.0 + staffing_response_scale.
    #
    # This is a study parameter expressing a modeled hypothesis about how
    # strongly learning responds to additional staffing — not an empirical
    # truth the simulator asserts about the world. Different study setups
    # may choose different values to test whether staffing intensity matters.
    #
    # Per opportunity_staffing_intensity_design_for_claude_v2.md.
    staffing_response_scale: float = 0.0

    # Prize descriptor ID for right-tail frontier re-attempts. When a
    # right-tail initiative is materialized from an available prize
    # descriptor, this field links it back to the original prize. None
    # for initial pool initiatives and non-right-tail frontier draws.
    # Per dynamic_opportunity_frontier.md §2 (prize lifecycle).
    prize_id: str | None = None

    # Prize attempt count at the time this initiative was materialized.
    # Preserved on the config so it survives the prize being removed from
    # the available set while the attempt is in flight. Used to compute
    # the correct incremented attempt_count when the initiative stops and
    # the prize returns to the available set.
    # Per dynamic_opportunity_frontier.md §2 (prize-preserving refresh).
    prize_attempt_count: int = 0


# ---------------------------------------------------------------------------
# Frontier configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FrontierSpec:
    """Per-family frontier parameters controlling dynamic quality degradation.

    When attached to an InitiativeTypeSpec, enables runner-side inter-tick
    frontier materialization for that family. When the unassigned pool for
    a family falls below its replenishment threshold, the runner draws new
    initiatives from a quality distribution whose alpha parameter is
    scaled down based on how many initiatives of that family have been
    resolved (completed or stopped).

    Functional form (per dynamic_opportunity_frontier.md §1):
        effective_alpha = base_alpha * max(frontier_quality_floor,
                                          1.0 - frontier_degradation_rate * n_resolved)

    When frontier is None on an InitiativeTypeSpec, that family uses
    fixed-pool semantics: the initial pool is the complete pool and no
    new initiatives are generated during the run.

    When frontier is set with frontier_degradation_rate == 0.0, the
    family uses non-degrading dynamic mode: replenishment is active
    but quality does not degrade. This is distinct from fixed-pool mode.

    Attributes:
        frontier_degradation_rate: Per-resolved-initiative reduction in
            the quality distribution's alpha multiplier. 0.0 means no
            degradation (non-degrading dynamic mode).
        frontier_quality_floor: Minimum multiplier on alpha. Prevents
            the Beta distribution from collapsing. Must be > 0.
        replenishment_threshold: Target buffer size for the unassigned
            pool per family. When the unassigned count for this family
            falls to or below this value, the runner materializes enough
            initiatives to bring the count back up to the threshold.

            The buffer exists because mixed-size teams and variable
            required_team_size create feasibility mismatches: a single
            unassigned initiative requiring team_size 12 cannot be
            started by a free team of size 5, causing artificial
            idleness. A buffer of several initiatives per family
            ensures team-size diversity in the pool so freed teams can
            find feasible work.

            A threshold of 0 recovers compact-pool behavior: materialize
            only when the pool is completely empty, generate exactly one.
            Per dynamic_opportunity_frontier.md §1.
    """

    frontier_degradation_rate: float = 0.0
    frontier_quality_floor: float = 0.1
    replenishment_threshold: int = 3

    # Per-attempt quality degradation for right-tail prize refresh.
    # When > 0, each failed attempt on a specific prize shifts the
    # quality alpha downward by this amount, modeling learning about
    # the difficulty of a particular opportunity space. Only meaningful
    # for right-tail families using prize-preserving refresh.
    # Default: 0.0 (no degradation — fresh draw from same distribution).
    # Per dynamic_opportunity_frontier.md §2.
    right_tail_refresh_quality_degradation: float = 0.0


# ---------------------------------------------------------------------------
# Initiative generator configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class InitiativeTypeSpec:
    """Per-type generation parameters for the initiative pool generator.

    Each spec describes one initiative type (e.g., flywheel, right-tail)
    with its distribution parameters and value channel templates.
    Per sourcing_and_generation.md canonical attribute ranges.
    """

    generation_tag: str
    count: int
    quality_distribution: DistributionSpec
    base_signal_st_dev_range: tuple[float, float]
    dependency_level_range: tuple[float, float]

    true_duration_range: tuple[int, int] | None = None
    planned_duration_range: tuple[int, int] | None = None
    required_team_size: int = 1
    # Range for required team size. When provided, a uniform integer
    # draw from [low, high] is assigned to each generated initiative as
    # its required_team_size, overriding the fixed required_team_size
    # field above. When None, the fixed required_team_size is used for
    # all initiatives of this type.
    #
    # This enables per-family team size variation: small exploratory
    # probes (e.g. 5 people) vs. large ambitious programs (e.g. 15
    # people). The governance trade-off is between staffing one large
    # initiative or several small ones within a portfolio labor cap.
    required_team_size_range: tuple[int, int] | None = None
    initial_execution_belief: float = 1.0

    # Value channel templates
    completion_lump_enabled: bool = False
    completion_lump_value_range: tuple[float, float] | None = None
    residual_enabled: bool = False
    residual_activation_state: str = "completed"
    residual_rate_range: tuple[float, float] | None = None
    residual_decay_range: tuple[float, float] | None = None
    major_win_event_enabled: bool = False
    q_major_win_threshold: float = 0.7
    observable_ceiling_distribution: DistributionSpec | None = None
    capability_contribution_scale_range: tuple[float, float] | None = None

    # Staffing intensity response scale range. When provided, a uniform
    # draw from this range is assigned to each generated initiative as
    # its staffing_response_scale. When None, generated initiatives get
    # the default staffing_response_scale of 0.0 (no staffing intensity
    # effect), preserving backward compatibility.
    #
    # Different initiative categories may use different ranges to express
    # study hypotheses about how each type of work responds to additional
    # staffing. For example, right-tail research may benefit more from
    # extra staffing than quick wins that saturate quickly.
    #
    # Per opportunity_staffing_intensity_design_for_claude_v2.md.
    staffing_response_scale_range: tuple[float, float] | None = None

    # Screening signal standard deviation (sigma_screen). Controls the
    # accuracy of the ex ante intake screening process that sets each
    # initiative's initial_quality_belief at generation time.
    #
    # When not None, the generator draws:
    #     screening_signal = clamp(q + Normal(0, sigma_screen), 0, 1)
    #     initial_quality_belief = screening_signal
    #
    # High sigma_screen = poor screening (beliefs weakly correlated with
    # true quality). Low sigma_screen = good screening (beliefs close to
    # true quality). This models the organization's intake evaluation
    # process: business cases, feasibility studies, strategic fit
    # assessments.
    #
    # When None, the generator sets initial_quality_belief = None and the
    # runner uses ModelConfig.default_initial_quality_belief (0.5 — the
    # uninformative prior). This preserves the pre-screening behavior.
    #
    # Per post_expert_review_plan.md Step 3.
    screening_signal_st_dev: float | None = None

    # Dynamic frontier specification. When set, enables runner-side
    # inter-tick frontier materialization for this family: the runner
    # generates new initiatives from a degraded quality distribution
    # when the family's unassigned pool is depleted. When None, the
    # family uses fixed-pool semantics (no dynamic materialization).
    # Per dynamic_opportunity_frontier.md.
    frontier: FrontierSpec | None = None


@dataclass(frozen=True)
class InitiativeGeneratorConfig:
    """Configuration for stochastic initiative pool generation.

    The runner resolves this into a concrete list of
    ResolvedInitiativeConfig using world_seed before simulation start.
    All resolved parameters are recorded in the manifest.
    Per sourcing_and_generation.md generator contract.
    """

    type_specs: tuple[InitiativeTypeSpec, ...]


# ---------------------------------------------------------------------------
# Top-level configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SimulationConfiguration:
    """Complete declarative specification of a simulation run.

    This is the single authoritative input contract. It is frozen and
    opaque to the engine. The simulator receives it, reads from it,
    and never modifies it.

    Exactly one of initiatives or initiative_generator must be provided.
    Per interfaces.md SimulationConfiguration.
    """

    world_seed: int
    time: TimeConfig
    teams: WorkforceConfig
    model: ModelConfig
    governance: GovernanceConfig
    reporting: ReportingConfig

    initiatives: tuple[ResolvedInitiativeConfig, ...] | None = None
    initiative_generator: InitiativeGeneratorConfig | None = None


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def validate_configuration(config: SimulationConfiguration) -> None:
    """Validate a SimulationConfiguration against interfaces.md rules.

    Collects all violations into a list and raises a single ValueError
    with all messages (rather than failing on the first error). This
    lets the caller fix all issues at once.

    Non-blocking advisory warnings are emitted via logging after
    validation passes.

    Raises:
        ValueError: if any validation rule is violated.
    """
    errors: list[str] = []

    # --- Initiative source: exactly one of initiatives or generator ---
    has_initiatives = config.initiatives is not None
    has_generator = config.initiative_generator is not None
    if has_initiatives == has_generator:
        errors.append(
            "Exactly one of 'initiatives' or 'initiative_generator' must be provided, "
            f"got {'both' if has_initiatives else 'neither'}."
        )

    # --- TimeConfig: horizon must define a meaningful simulation ---
    if config.time.tick_horizon <= 0:
        errors.append(f"tick_horizon must be > 0, got {config.time.tick_horizon}.")

    # --- WorkforceConfig: must have at least one team ---
    if config.teams.team_count <= 0:
        errors.append(f"team_count must be > 0, got {config.teams.team_count}.")

    # --- WorkforceConfig: tuple team_size length must match team_count ---
    # When team_size is a tuple (per-team sizes), the number of entries
    # must equal team_count so each team has a defined size.
    if (
        isinstance(config.teams.team_size, tuple)
        and len(config.teams.team_size) != config.teams.team_count
    ):
        errors.append(
            f"team_size tuple length ({len(config.teams.team_size)}) "
            f"must match team_count ({config.teams.team_count})."
        )

    # --- ModelConfig: world-evolution parameter bounds ---
    # These constraints ensure the attention curve, learning, and
    # capability update equations produce valid outputs.
    model = config.model
    if not (0.0 <= model.attention_noise_threshold <= 1.0):
        errors.append(
            f"attention_noise_threshold must be in [0, 1], got {model.attention_noise_threshold}."
        )
    if model.low_attention_penalty_slope < 0:
        errors.append(
            f"low_attention_penalty_slope must be >= 0, got {model.low_attention_penalty_slope}."
        )
    if model.reference_ceiling <= 0:
        errors.append(f"reference_ceiling must be > 0, got {model.reference_ceiling}.")
    if model.max_attention_noise_modifier is not None and not (
        0 <= model.min_attention_noise_modifier <= model.max_attention_noise_modifier
    ):
        errors.append(
            f"min_attention_noise_modifier must be <= max_attention_noise_modifier "
            f"when max is set, got min={model.min_attention_noise_modifier}, "
            f"max={model.max_attention_noise_modifier}."
        )
    if model.max_portfolio_capability < 1.0:
        errors.append(
            f"max_portfolio_capability must be >= 1.0, got {model.max_portfolio_capability}."
        )
    if model.capability_decay < 0:
        errors.append(f"capability_decay must be >= 0, got {model.capability_decay}.")
    if not (0 <= model.default_initial_quality_belief <= 1):
        errors.append(
            "default_initial_quality_belief must be in [0, 1], "
            f"got {model.default_initial_quality_belief}."
        )
    if model.execution_signal_st_dev < 0:
        errors.append(
            f"execution_signal_st_dev must be >= 0, got {model.execution_signal_st_dev}."
        )
    if not (0 < model.execution_learning_rate <= 1):
        errors.append(
            f"execution_learning_rate must be in (0, 1], got {model.execution_learning_rate}."
        )

    # --- GovernanceConfig: decision-threshold bounds ---
    # These constraints ensure governance primitives receive valid
    # parameters for stop evaluation, stagnation detection, and
    # attention allocation.
    governance = config.governance
    if not isinstance(governance.base_tam_patience_window, int):
        errors.append(
            f"base_tam_patience_window must be int, "
            f"got {type(governance.base_tam_patience_window).__name__}. "
            "YAML parsers may silently coerce '5' to float 5.0; "
            "use explicit int casting when loading YAML configs."
        )
    if governance.stagnation_window_staffed_ticks < 1:
        errors.append(
            f"stagnation_window_staffed_ticks must be >= 1, "
            f"got {governance.stagnation_window_staffed_ticks}."
        )
    if governance.stagnation_belief_change_threshold < 0:
        errors.append(
            f"stagnation_belief_change_threshold must be >= 0, "
            f"got {governance.stagnation_belief_change_threshold}."
        )
    # attention_min must be in (0, 1] when exec_attention_budget > 0.
    # When exec_attention_budget == 0.0, attention_min = 0.0 is valid because
    # no attention is allocated and the attention_min floor is irrelevant.
    # Per governance.md §Zero-budget special case and interfaces.md validation rules.
    if model.exec_attention_budget == 0.0:
        if not (0 <= governance.attention_min <= 1):
            errors.append(
                f"attention_min must be in [0, 1] when exec_attention_budget is 0, "
                f"got {governance.attention_min}."
            )
    elif not (0 < governance.attention_min <= 1):
        errors.append(f"attention_min must be in (0, 1], got {governance.attention_min}.")
    if governance.attention_max is not None:
        if not (0 <= governance.attention_max <= 1):
            errors.append(f"attention_max must be in [0, 1], got {governance.attention_max}.")
        if governance.attention_min > governance.attention_max:
            errors.append(
                f"attention_min must be <= attention_max, "
                f"got min={governance.attention_min}, max={governance.attention_max}."
            )

    # --- Per-initiative validation (when explicit initiatives provided) ---
    if config.initiatives is not None:
        for initiative in config.initiatives:
            _validate_initiative(initiative, errors)

    if errors:
        raise ValueError(
            "Configuration validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
        )

    # --- Warnings (non-blocking advisory conditions) ---
    # If confidence_decline_threshold >= initial belief, most initiatives
    # will trigger confidence-decline stops before other rules have a
    # chance to act.
    if (
        governance.confidence_decline_threshold is not None
        and governance.confidence_decline_threshold >= model.default_initial_quality_belief
    ):
        logger.warning(
            "confidence_decline_threshold (%.3f) >= "
            "default_initial_quality_belief (%.3f): "
            "non-TAM stagnation path may be dominated by confidence decline.",
            governance.confidence_decline_threshold,
            model.default_initial_quality_belief,
        )


def _validate_initiative(initiative: ResolvedInitiativeConfig, errors: list[str]) -> None:
    """Validate a single ResolvedInitiativeConfig.

    Checks per-initiative constraints from interfaces.md: duration
    consistency, value channel requirements, and capability
    contribution prerequisites. Appends violation messages to the
    shared errors list.
    """
    prefix = f"Initiative '{initiative.initiative_id}'"

    # --- Attribute bounds (per initiative_model.md) ---
    if not (0.0 <= initiative.latent_quality <= 1.0):
        errors.append(
            f"{prefix}: latent_quality must be in [0, 1], got {initiative.latent_quality}."
        )
    if not (0.0 <= initiative.dependency_level <= 1.0):
        errors.append(
            f"{prefix}: dependency_level must be in [0, 1], got {initiative.dependency_level}."
        )
    if initiative.base_signal_st_dev < 0:
        errors.append(
            f"{prefix}: base_signal_st_dev must be >= 0, got {initiative.base_signal_st_dev}."
        )
    if initiative.staffing_response_scale < 0:
        errors.append(
            f"{prefix}: staffing_response_scale must be >= 0, "
            f"got {initiative.staffing_response_scale}."
        )

    # --- Duration consistency ---
    if initiative.planned_duration_ticks is not None and initiative.planned_duration_ticks <= 0:
        errors.append(f"{prefix}: planned_duration_ticks must be > 0.")

    if initiative.true_duration_ticks is not None and initiative.true_duration_ticks <= 0:
        errors.append(f"{prefix}: true_duration_ticks must be > 0.")

    # true_duration is the latent completion target; it only makes
    # sense relative to a planned duration that governance can see.
    if initiative.true_duration_ticks is not None and initiative.planned_duration_ticks is None:
        errors.append(
            f"{prefix}: true_duration_ticks requires planned_duration_ticks to also be set."
        )

    # --- Execution belief initial value ---
    if initiative.initial_execution_belief is not None and not (
        0 < initiative.initial_execution_belief <= 1
    ):
        errors.append(
            f"{prefix}: initial_execution_belief must be in (0, 1], "
            f"got {initiative.initial_execution_belief}."
        )

    # --- Capability contribution ---
    if initiative.capability_contribution_scale < 0:
        errors.append(
            f"{prefix}: capability_contribution_scale must be >= 0, "
            f"got {initiative.capability_contribution_scale}."
        )

    # Capability contribution is realized at completion, so the
    # engine needs to know when completion occurs.
    if initiative.capability_contribution_scale > 0 and initiative.true_duration_ticks is None:
        errors.append(f"{prefix}: capability_contribution_scale > 0 requires true_duration_ticks.")

    # --- Completion lump channel ---
    completion_lump = initiative.value_channels.completion_lump
    if completion_lump.enabled and completion_lump.realized_value is None:
        errors.append(
            f"{prefix}: completion_lump is enabled but realized_value is absent. "
            "The engine must not silently default to zero."
        )
    if (
        completion_lump.enabled
        and completion_lump.realized_value is not None
        and completion_lump.realized_value < 0
    ):
        errors.append(f"{prefix}: completion_lump.realized_value must be >= 0.")
    if completion_lump.enabled and initiative.true_duration_ticks is None:
        errors.append(
            f"{prefix}: completion_lump is enabled but true_duration_ticks is not set. "
            "Completion lump can only be realized at the completion transition."
        )

    # --- Residual channel ---
    residual = initiative.value_channels.residual
    if residual.enabled and residual.residual_decay < 0:
        errors.append(f"{prefix}: residual_decay must be >= 0.")
    if residual.enabled and residual.activation_state != "completed":
        errors.append(
            f"{prefix}: residual.activation_state must be 'completed', "
            f"got '{residual.activation_state}'."
        )

    # Residual with activation_state="completed" needs a defined
    # completion point (true_duration_ticks) so the engine knows
    # when to activate the channel.
    if (
        residual.enabled
        and residual.activation_state == "completed"
        and initiative.true_duration_ticks is None
    ):
        errors.append(
            f"{prefix}: residual with activation_state='completed' requires true_duration_ticks."
        )
