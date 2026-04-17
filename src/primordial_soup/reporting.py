"""Output schemas and aggregation for simulation runs.

This module defines the canonical output surface of the Primordial Soup
study. It provides frozen dataclasses for per-tick records, run manifests,
and run results, plus aggregation functions that compute a RunResult from
collected per-tick data and events.

The reporting layer is the evidentiary substrate for analysis: it records
what happened during a simulation run in precise, observational language
without evaluative judgment.

Design reference: docs/design/review_and_reporting.md (authoritative output
schema), docs/design/interfaces.md (RunManifest, ReportingConfig).

Compact symbol → descriptive name mapping for this module:
    c_t         → quality_belief_t
    q           → latent_quality
    C_t         → portfolio_capability_t (capability_C_t in PortfolioTickRecord)
    σ_eff       → effective_sigma_t
    c_exec_t    → execution_belief_t
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from primordial_soup.config import ResolvedInitiativeConfig, SimulationConfiguration
    from primordial_soup.events import (
        AttentionFeasibilityViolationEvent,
        CompletionEvent,
        MajorWinEvent,
        ReassignmentEvent,
        StopEvent,
    )
    from primordial_soup.state import WorldState

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Per-tick record types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PerInitiativeTickRecord:
    """Per-initiative state snapshot for one tick.

    Emitted when record_per_tick_logs is True. Contains both
    governance-observable fields (quality_belief_t, execution_belief_t)
    and post-hoc fields (latent_quality) for analysis.

    exec_attention_a_t is the realized attention applied after engine
    validation, not merely the submitted policy request. An initiative
    omitted from the policy's SetExecAttention actions records 0.0.

    Per review_and_reporting.md PerInitiativeTickRecord schema.
    """

    tick: int
    initiative_id: str
    lifecycle_state: str
    quality_belief_t: float
    latent_quality: float  # post-hoc only; not observable during run
    exec_attention_a_t: float
    effective_sigma_t: float
    execution_belief_t: float | None
    is_ramping: bool
    ramp_multiplier: float | None  # None if not ramping


@dataclass(frozen=True)
class PortfolioTickRecord:
    """Portfolio-level aggregates for one tick.

    Emitted alongside PerInitiativeTickRecord when record_per_tick_logs
    is True. capability_C_t is required for RQ4 capability-investment
    analysis.

    Per review_and_reporting.md PortfolioTickRecord schema.
    """

    tick: int
    capability_C_t: float  # portfolio_capability_t at this tick
    active_initiative_count: int
    idle_team_count: int
    total_exec_attention_allocated: float  # portfolio sum of all attention


# ---------------------------------------------------------------------------
# Value-by-channel breakdown
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ValueByChannel:
    """Channel-separated value breakdown for a run.

    Per review_and_reporting.md value_by_channel schema.
    """

    completion_lump_value: float
    residual_value: float
    # Residual value disaggregated by generation label.
    # Keys are generation tags (e.g. "flywheel", "right_tail").
    residual_value_by_label: dict[str, float]


# ---------------------------------------------------------------------------
# Major-win profile
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MajorWinProfile:
    """Summary of major-win discovery events in a run.

    Per review_and_reporting.md major_win_profile schema.
    """

    major_win_count: int
    # Ticks from initiative creation to major-win event, one per event.
    time_to_major_win: tuple[int, ...]
    # Count of major wins disaggregated by generation label.
    major_win_count_by_label: dict[str, int]
    # Total labor invested in right-tail initiatives / major_win_count.
    # None if no major wins occurred.
    labor_per_major_win: float | None


# ---------------------------------------------------------------------------
# Belief accuracy
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BeliefAccuracy:
    """Aggregate belief accuracy metrics over all per-tick records.

    Computed from the full set of PerInitiativeTickRecord rows.
    Per review_and_reporting.md aggregate_belief_accuracy schema.
    """

    mean_absolute_belief_error: float
    mean_squared_belief_error: float


# ---------------------------------------------------------------------------
# Idle capacity profile
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class IdleCapacityProfile:
    """Idle capacity metrics for a run.

    Per review_and_reporting.md idle_capacity_profile schema.
    """

    cumulative_idle_team_ticks: int
    # Fraction of total available team-ticks that were idle.
    idle_team_tick_fraction: float
    # First tick at which all remaining unassigned initiatives were below
    # policy's activation threshold and at least one team was idle.
    # None if this condition never occurred.
    pool_exhaustion_tick: int | None


# ---------------------------------------------------------------------------
# Exploration cost profile
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ExplorationCostProfile:
    """Investment profile for stopped and completed initiatives.

    Per review_and_reporting.md exploration_cost_profile schema.
    Uses observational language — no evaluative terms.
    """

    # Stopped initiative investment.
    cumulative_labor_in_stopped_initiatives: float
    cumulative_attention_in_stopped_initiatives: float
    stopped_initiative_count_by_label: dict[str, int]
    # Per review_and_reporting.md: labor and attention broken down by
    # generation label, for RQ4/RQ5 investment-by-family analysis.
    cumulative_labor_in_stopped_by_label: dict[str, float]
    cumulative_attention_in_stopped_by_label: dict[str, float]
    # Distribution of true latent quality among stopped initiatives.
    latent_quality_distribution_of_stopped: tuple[float, ...]

    # Completed initiative investment.
    cumulative_labor_in_completed_initiatives: float
    cumulative_attention_in_completed_initiatives: float
    completed_initiative_count_by_label: dict[str, int]
    # Per review_and_reporting.md: labor and attention broken down by
    # generation label, for RQ4/RQ5 investment-by-family analysis.
    cumulative_labor_in_completed_by_label: dict[str, float]
    cumulative_attention_in_completed_by_label: dict[str, float]


# ---------------------------------------------------------------------------
# Reassignment profile
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ReassignmentProfile:
    """Summary of team reassignment activity in a run.

    Per review_and_reporting.md reassignment_profile schema.
    """

    reassignment_event_count: int
    # Full event log, included when record_event_log is True.
    reassignment_event_log: tuple[ReassignmentEvent, ...] | None


# ---------------------------------------------------------------------------
# Family timing profile
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FamilyTimingProfile:
    """Per-family timing metrics for governance pacing analysis.

    Reports when completions and stops occurred by initiative family,
    enabling analysis of governance pacing as a core study question.
    Timing often matters as much as totals for understanding governance
    quality — a regime that completes the same number of enablers but
    much later has a structurally different capability trajectory.

    Per implementation plan Step 5.2.
    """

    # Time-to-first-completion by family. The tick of the first
    # completion event for each generation_tag. None if no completions.
    first_completion_tick_by_family: dict[str, int | None]

    # Mean completion tick by family. Average completed_tick for
    # completed initiatives of each generation_tag. None if no completions.
    mean_completion_tick_by_family: dict[str, float | None]

    # Full completion tick distributions by family. For downstream
    # analysis (e.g. histograms, percentiles).
    completion_ticks_by_family: dict[str, tuple[int, ...]]

    # Peak capability tick: the tick at which portfolio_capability_t
    # reached its maximum value during the run.
    peak_capability_tick: int

    # First right-tail stop tick: the tick of the first right-tail
    # stop event. Counterpart of first-completion for a family where
    # stops are the dominant governance action. None if no right-tail stops.
    first_right_tail_stop_tick: int | None


# ---------------------------------------------------------------------------
# Right-tail false-stop profile
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RightTailFalseStopProfile:
    """Right-tail false-stop metrics for a run.

    Tracks how many right-tail initiatives were major-win-eligible,
    how many of those eligible were stopped, and the resulting
    false-stop rate. Also records the belief at stop for stopped
    eligible initiatives, enabling downstream belief-at-stop
    distribution analysis.

    Per reporting_package_specification.md §Source fields and computation:
    - is_major_win_eligible: cfg.value_channels.major_win_event.enabled
      AND cfg.value_channels.major_win_event.is_major_win
    - right_tail_false_stop_rate: stopped_eligible / eligible
      (None when eligible == 0)
    - belief_at_stop: StopEvent.quality_belief_t

    All counts are restricted to initiatives with
    generation_tag == "right_tail".
    """

    # Count of right-tail initiatives where major_win_event.enabled
    # is True AND major_win_event.is_major_win is True.
    right_tail_eligible_count: int

    # Of the eligible set, how many were stopped.
    right_tail_stopped_eligible_count: int

    # Right-tail initiatives that completed (any, not just eligible).
    right_tail_completions: int

    # Right-tail initiatives that were stopped (any, not just eligible).
    right_tail_stops: int

    # stopped_eligible_count / eligible_count. None when eligible == 0.
    right_tail_false_stop_rate: float | None

    # quality_belief_t from StopEvent for each stopped eligible
    # initiative, in stable initiative_id order. Enables downstream
    # belief-at-stop distribution analysis.
    belief_at_stop_for_stopped_eligible: tuple[float, ...]


# ---------------------------------------------------------------------------
# Frontier summary
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FrontierSummary:
    """Per-family frontier state at end of run.

    Reports the frontier exhaustion state for each initiative family,
    enabling assessment of whether the opportunity supply was adequate
    for the study design.

    Per implementation plan Step 5.1 (frontier state by family).
    """

    # Per-family frontier state: (generation_tag, n_resolved,
    # n_frontier_draws, effective_alpha_multiplier).
    family_frontier_states: dict[str, dict[str, float | int]]


# ---------------------------------------------------------------------------
# Run manifest
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RunManifest:
    """Provenance artifact for exact replay of a simulation run.

    Contains all information needed to reproduce the run: seed,
    resolved configuration, resolved initiative list, and engine
    version identifier.

    Per interfaces.md RunManifest schema.
    """

    policy_id: str
    world_seed: int
    is_replay: bool
    resolved_configuration: SimulationConfiguration
    resolved_initiatives: tuple[ResolvedInitiativeConfig, ...]
    engine_version: str

    @property
    def flat_governance_params(self) -> dict[str, object]:
        """Flat dict of governance parameters for sweep analysis.

        Returns governance config fields as simple key-value pairs
        suitable for DataFrame construction and parameter filtering.
        Per review_and_reporting.md: full GovernanceConfig parameter
        values as a flat metadata record.
        """
        gov = self.resolved_configuration.governance
        return {
            "policy_id": gov.policy_id,
            "exec_attention_budget": gov.exec_attention_budget,
            "default_initial_quality_belief": gov.default_initial_quality_belief,
            "confidence_decline_threshold": gov.confidence_decline_threshold,
            "tam_threshold_ratio": gov.tam_threshold_ratio,
            "base_tam_patience_window": gov.base_tam_patience_window,
            "stagnation_window_staffed_ticks": gov.stagnation_window_staffed_ticks,
            "stagnation_belief_change_threshold": gov.stagnation_belief_change_threshold,
            "attention_min": gov.attention_min,
            "attention_max": gov.attention_max,
            "exec_overrun_threshold": gov.exec_overrun_threshold,
            "low_quality_belief_threshold": gov.low_quality_belief_threshold,
            "max_low_quality_belief_labor_share": gov.max_low_quality_belief_labor_share,
            "max_single_initiative_labor_share": gov.max_single_initiative_labor_share,
        }

    @property
    def flat_environment_params(self) -> dict[str, object]:
        """Flat dict of environment/model parameters for sweep analysis.

        Returns model config fields as simple key-value pairs suitable
        for DataFrame construction and parameter filtering. Per
        review_and_reporting.md: full environmental configuration as
        a flat metadata record.
        """
        model = self.resolved_configuration.model
        teams = self.resolved_configuration.teams
        return {
            "tick_horizon": model.tick_horizon,
            "learning_rate": model.learning_rate,
            "base_signal_noise": model.base_signal_noise,
            "dependency_noise_exponent": model.dependency_noise_exponent,
            "attention_noise_coefficient": model.attention_noise_coefficient,
            "attention_curve_shape": model.attention_curve_shape,
            "reference_ceiling": model.reference_ceiling,
            "capability_growth_rate": model.capability_growth_rate,
            "capability_max": model.capability_max,
            "residual_base_rate": model.residual_base_rate,
            "residual_growth_rate": model.residual_growth_rate,
            "execution_learning_rate": model.execution_learning_rate,
            "ramp_period": teams.ramp_period,
            "ramp_multiplier_shape": teams.ramp_multiplier_shape,
        }


# ---------------------------------------------------------------------------
# RunResult — the complete output of a single simulation run
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RunResult:
    """Complete output of a single simulation run.

    Assembles all primary outputs from review_and_reporting.md into
    a single frozen record. Event logs and per-tick logs are
    conditional on ReportingConfig flags.

    Per review_and_reporting.md primary outputs schema.
    """

    # --- Primary value outputs ---
    cumulative_value_total: float
    value_by_channel: ValueByChannel

    # --- Major-win profile ---
    major_win_profile: MajorWinProfile

    # --- Belief accuracy ---
    belief_accuracy: BeliefAccuracy

    # --- Terminal state ---
    terminal_capability_t: float  # C_t at the final tick
    # Peak portfolio_capability_t reached at any tick during the run.
    # Complements terminal_capability_t, which may be lower due to capability decay.
    max_portfolio_capability_t: float
    terminal_aggregate_residual_rate: float  # sum of residual rates at final tick

    # --- Idle capacity ---
    idle_capacity_profile: IdleCapacityProfile

    # --- Baseline work value ---
    # Cumulative value accrued by teams when idle/on baseline over
    # the run. Runner-side accounting only; the engine does not
    # consume this field. Per governance.md "Baseline work semantics".
    cumulative_baseline_value: float

    # --- Exploration cost ---
    exploration_cost_profile: ExplorationCostProfile

    # --- Right-tail false-stop ---
    right_tail_false_stop_profile: RightTailFalseStopProfile

    # --- Reassignment ---
    reassignment_profile: ReassignmentProfile

    # --- Cumulative ramp labor ---
    cumulative_ramp_labor: float

    # --- Ramp labor fraction ---
    # Fraction of total team-ticks spent in ramp (switching cost).
    ramp_labor_fraction: float

    # --- Value by initiative family ---
    # Cumulative value (lump + residual) decomposed by generation_tag.
    value_by_family: dict[str, float]

    # --- Family timing ---
    family_timing: FamilyTimingProfile

    # --- Frontier summary ---
    frontier_summary: FrontierSummary | None

    # --- Attention feasibility violations ---
    # Count of ticks where attention allocation violated constraints.
    # Per governance.md §Budget and feasibility constraints.
    attention_feasibility_violation_count: int

    # --- Conditional event logs (when record_event_log is True) ---
    major_win_event_log: tuple[MajorWinEvent, ...] | None
    stop_event_log: tuple[StopEvent, ...] | None

    # --- Conditional per-tick logs (when record_per_tick_logs is True) ---
    per_initiative_tick_records: tuple[PerInitiativeTickRecord, ...] | None
    portfolio_tick_records: tuple[PortfolioTickRecord, ...] | None

    # --- Manifest ---
    manifest: RunManifest


# ---------------------------------------------------------------------------
# Mutable collector used during the tick loop
# ---------------------------------------------------------------------------


@dataclass
class RunCollector:
    """Mutable accumulator used by the runner during the tick loop.

    Not frozen — the runner mutates this as it processes ticks. After
    the loop completes, the runner calls assemble_run_result() to
    produce the immutable RunResult.

    This is an internal type not exposed to callers.
    """

    # Cumulative value accumulators (channel-separated).
    cumulative_lump_value: float = 0.0
    cumulative_residual_value: float = 0.0

    # Event logs.
    completion_events: list[CompletionEvent] = field(default_factory=list)
    major_win_events: list[MajorWinEvent] = field(default_factory=list)
    stop_events: list[StopEvent] = field(default_factory=list)
    reassignment_events: list[ReassignmentEvent] = field(default_factory=list)
    attention_feasibility_violation_events: list[AttentionFeasibilityViolationEvent] = field(
        default_factory=list
    )

    # Per-tick records (populated when record_per_tick_logs is True).
    per_initiative_tick_records: list[PerInitiativeTickRecord] = field(default_factory=list)
    portfolio_tick_records: list[PortfolioTickRecord] = field(default_factory=list)

    # Idle capacity tracking.
    cumulative_idle_team_ticks: int = 0
    pool_exhaustion_tick: int | None = None

    # Baseline work value accrual (runner-side accounting).
    # Each tick, idle teams accrue `config.model.baseline_value_per_tick`
    # per team. This represents productive non-portfolio activity
    # (maintenance, operational improvements, customer support, etc.).
    # Per governance.md "Baseline work semantics". When
    # baseline_value_per_tick is 0 (default), this stays 0 for the run.
    cumulative_baseline_value: float = 0.0

    # Ramp labor tracking (team-ticks during ramp).
    cumulative_ramp_labor: float = 0.0

    # Peak portfolio_capability_t reached at any tick during the run.
    # Default is 1.0 because that is the initial portfolio_capability value.
    max_portfolio_capability_t: float = 1.0

    # Tick at which peak portfolio_capability_t was first reached.
    # Tracks when the organization's learning environment was at its best.
    # Default is 0 (initial tick); updated alongside max_portfolio_capability_t.
    peak_capability_tick: int = 0


# ---------------------------------------------------------------------------
# Aggregation functions
# ---------------------------------------------------------------------------


def compute_belief_accuracy(
    records: list[PerInitiativeTickRecord],
) -> BeliefAccuracy:
    """Compute aggregate belief accuracy from per-tick records.

    Calculates mean absolute error and mean squared error between
    quality_belief_t and latent_quality over all emitted records.

    Per review_and_reporting.md aggregate_belief_accuracy definition:
        MAE = mean(|quality_belief_t - latent_quality|)
        MSE = mean((quality_belief_t - latent_quality)^2)

    Args:
        records: All PerInitiativeTickRecord rows from the run.

    Returns:
        BeliefAccuracy with MAE and MSE. Returns zeros if no records.
    """
    if not records:
        return BeliefAccuracy(
            mean_absolute_belief_error=0.0,
            mean_squared_belief_error=0.0,
        )

    total_absolute_error = 0.0
    total_squared_error = 0.0
    count = len(records)

    for record in records:
        error = record.quality_belief_t - record.latent_quality
        total_absolute_error += abs(error)
        total_squared_error += error * error

    return BeliefAccuracy(
        mean_absolute_belief_error=total_absolute_error / count,
        mean_squared_belief_error=total_squared_error / count,
    )


def compute_value_by_channel(
    cumulative_lump_value: float,
    cumulative_residual_value: float,
    stop_events: list[StopEvent],
    completion_events: list[CompletionEvent],
    initiative_configs: tuple[ResolvedInitiativeConfig, ...],
    residual_value_by_initiative: dict[str, float],
) -> ValueByChannel:
    """Compute channel-separated value breakdown.

    residual_value_by_initiative maps initiative_id to the total
    residual value that initiative produced over the run. This is
    disaggregated by generation_tag to produce residual_value_by_label.

    Args:
        cumulative_lump_value: Total completion-lump value over the run.
        cumulative_residual_value: Total residual value over the run.
        stop_events: All stop events (not used directly but kept for
            interface consistency).
        completion_events: All completion events (not used directly).
        initiative_configs: Resolved configs for label lookup.
        residual_value_by_initiative: Map of initiative_id to total
            residual value produced by that initiative.

    Returns:
        ValueByChannel with lump, residual, and residual-by-label.
    """
    # Build config lookup for generation_tag.
    config_map = {cfg.initiative_id: cfg for cfg in initiative_configs}

    # Disaggregate residual value by generation label.
    residual_by_label: dict[str, float] = {}
    for init_id, residual_val in residual_value_by_initiative.items():
        cfg = config_map.get(init_id)
        label = cfg.generation_tag if cfg is not None and cfg.generation_tag else "unknown"
        residual_by_label[label] = residual_by_label.get(label, 0.0) + residual_val

    return ValueByChannel(
        completion_lump_value=cumulative_lump_value,
        residual_value=cumulative_residual_value,
        residual_value_by_label=residual_by_label,
    )


def compute_major_win_profile(
    major_win_events: list[MajorWinEvent],
    initiative_configs: tuple[ResolvedInitiativeConfig, ...],
    total_right_tail_labor: float,
) -> MajorWinProfile:
    """Compute major-win profile from collected events.

    Per review_and_reporting.md major_win_profile schema:
    - major_win_count: total surfaced major wins
    - time_to_major_win: ticks from creation to major-win event
    - major_win_count_by_label: disaggregated by generation tag
    - labor_per_major_win: total right-tail labor / major_win_count

    Args:
        major_win_events: All MajorWinEvent records from the run.
        initiative_configs: Resolved configs for label and creation-tick lookup.
        total_right_tail_labor: Total labor invested in right-tail initiatives.

    Returns:
        MajorWinProfile summarizing major-win outcomes.
    """
    config_map = {cfg.initiative_id: cfg for cfg in initiative_configs}
    count = len(major_win_events)

    # Time-to-major-win: ticks from created_tick to the major-win tick.
    times: list[int] = []
    count_by_label: dict[str, int] = {}

    for event in major_win_events:
        cfg = config_map.get(event.initiative_id)
        created_tick = cfg.created_tick if cfg is not None else 0
        times.append(event.tick - created_tick)

        label = cfg.generation_tag if cfg is not None and cfg.generation_tag else "unknown"
        count_by_label[label] = count_by_label.get(label, 0) + 1

    labor_per_mw: float | None = None
    if count > 0:
        labor_per_mw = total_right_tail_labor / count

    return MajorWinProfile(
        major_win_count=count,
        time_to_major_win=tuple(times),
        major_win_count_by_label=count_by_label,
        labor_per_major_win=labor_per_mw,
    )


def compute_idle_capacity_profile(
    cumulative_idle_team_ticks: int,
    total_team_ticks: int,
    pool_exhaustion_tick: int | None,
) -> IdleCapacityProfile:
    """Compute idle capacity profile for the run.

    Per review_and_reporting.md idle_capacity_profile schema.

    Args:
        cumulative_idle_team_ticks: Total team-ticks with no assignment.
        total_team_ticks: Total available team-ticks (team_count * horizon).
        pool_exhaustion_tick: First tick where pool exhaustion occurred.

    Returns:
        IdleCapacityProfile with aggregate and fractional idle metrics.
    """
    fraction = 0.0
    if total_team_ticks > 0:
        fraction = cumulative_idle_team_ticks / total_team_ticks

    return IdleCapacityProfile(
        cumulative_idle_team_ticks=cumulative_idle_team_ticks,
        idle_team_tick_fraction=fraction,
        pool_exhaustion_tick=pool_exhaustion_tick,
    )


def compute_exploration_cost_profile(
    stop_events: list[StopEvent],
    completion_events: list[CompletionEvent],
    initiative_configs: tuple[ResolvedInitiativeConfig, ...],
    cumulative_labor_by_initiative: dict[str, float],
    cumulative_attention_by_initiative: dict[str, float],
) -> ExplorationCostProfile:
    """Compute exploration cost profile from events and initiative state.

    Per review_and_reporting.md exploration_cost_profile schema.
    Uses neutral observational language — no evaluative terms.

    Args:
        stop_events: All StopEvent records from the run.
        completion_events: All CompletionEvent records from the run.
        initiative_configs: Resolved configs for label and latent quality lookup.
        cumulative_labor_by_initiative: Map of initiative_id to total labor.
        cumulative_attention_by_initiative: Map of initiative_id to total attention.

    Returns:
        ExplorationCostProfile with stopped and completed investment breakdowns.
    """
    config_map = {cfg.initiative_id: cfg for cfg in initiative_configs}

    # --- Stopped initiatives ---
    stopped_labor = 0.0
    stopped_attention = 0.0
    stopped_count_by_label: dict[str, int] = {}
    stopped_labor_by_label: dict[str, float] = {}
    stopped_attention_by_label: dict[str, float] = {}
    stopped_qualities: list[float] = []

    for event in stop_events:
        init_labor = cumulative_labor_by_initiative.get(event.initiative_id, 0.0)
        init_attention = cumulative_attention_by_initiative.get(event.initiative_id, 0.0)
        stopped_labor += init_labor
        stopped_attention += init_attention
        cfg = config_map.get(event.initiative_id)
        label = cfg.generation_tag if cfg is not None and cfg.generation_tag else "unknown"
        stopped_count_by_label[label] = stopped_count_by_label.get(label, 0) + 1
        stopped_labor_by_label[label] = stopped_labor_by_label.get(label, 0.0) + init_labor
        stopped_attention_by_label[label] = (
            stopped_attention_by_label.get(label, 0.0) + init_attention
        )
        stopped_qualities.append(event.latent_quality)

    # --- Completed initiatives ---
    completed_labor = 0.0
    completed_attention = 0.0
    completed_count_by_label: dict[str, int] = {}
    completed_labor_by_label: dict[str, float] = {}
    completed_attention_by_label: dict[str, float] = {}

    for comp_event in completion_events:
        comp_init_labor = cumulative_labor_by_initiative.get(comp_event.initiative_id, 0.0)
        comp_init_attention = cumulative_attention_by_initiative.get(comp_event.initiative_id, 0.0)
        completed_labor += comp_init_labor
        completed_attention += comp_init_attention
        comp_cfg = config_map.get(comp_event.initiative_id)
        comp_label = (
            comp_cfg.generation_tag
            if comp_cfg is not None and comp_cfg.generation_tag
            else "unknown"
        )
        completed_count_by_label[comp_label] = completed_count_by_label.get(comp_label, 0) + 1
        completed_labor_by_label[comp_label] = (
            completed_labor_by_label.get(comp_label, 0.0) + comp_init_labor
        )
        completed_attention_by_label[comp_label] = (
            completed_attention_by_label.get(comp_label, 0.0) + comp_init_attention
        )

    return ExplorationCostProfile(
        cumulative_labor_in_stopped_initiatives=stopped_labor,
        cumulative_attention_in_stopped_initiatives=stopped_attention,
        stopped_initiative_count_by_label=stopped_count_by_label,
        cumulative_labor_in_stopped_by_label=stopped_labor_by_label,
        cumulative_attention_in_stopped_by_label=stopped_attention_by_label,
        latent_quality_distribution_of_stopped=tuple(stopped_qualities),
        cumulative_labor_in_completed_initiatives=completed_labor,
        cumulative_attention_in_completed_initiatives=completed_attention,
        completed_initiative_count_by_label=completed_count_by_label,
        cumulative_labor_in_completed_by_label=completed_labor_by_label,
        cumulative_attention_in_completed_by_label=completed_attention_by_label,
    )


def compute_terminal_aggregate_residual_rate(
    initiative_configs: tuple[ResolvedInitiativeConfig, ...],
    residual_activated_ids: set[str],
    final_tick: int,
    residual_activation_ticks: dict[str, int],
) -> float:
    """Compute the sum of residual rates at the final tick.

    For each residual-activated initiative, compute the decayed residual
    rate at the final tick using the canonical decay law:
        residual_rate_t = residual_rate * exp(-residual_decay * τ_residual)
    where τ_residual = final_tick - residual_activation_tick.

    Per review_and_reporting.md terminal_aggregate_residual_rate definition.

    Args:
        initiative_configs: Resolved configs with residual channel params.
        residual_activated_ids: Set of initiative ids with activated residual.
        final_tick: The last tick of the simulation run.
        residual_activation_ticks: Map of initiative_id to activation tick.

    Returns:
        Sum of residual rates at the final tick across all activated initiatives.
    """
    import math

    config_map = {cfg.initiative_id: cfg for cfg in initiative_configs}
    total_rate = 0.0

    for init_id in sorted(residual_activated_ids):
        cfg = config_map.get(init_id)
        if cfg is None:
            continue
        activation_tick = residual_activation_ticks.get(init_id)
        if activation_tick is None:
            continue

        ticks_since_activation = final_tick - activation_tick
        rate = cfg.value_channels.residual.residual_rate * math.exp(
            -cfg.value_channels.residual.residual_decay * ticks_since_activation
        )
        total_rate += max(rate, 0.0)

    return total_rate


def compute_value_by_family(
    initiative_configs: tuple[ResolvedInitiativeConfig, ...],
    final_world_state: WorldState,
) -> dict[str, float]:
    """Compute cumulative value (lump + residual) decomposed by generation_tag.

    Aggregates per-initiative cumulative_value_realized (which includes both
    lump and residual channels) by generation_tag. This provides the
    family-level value decomposition that the conductor needs to understand
    which initiative families are driving total value.

    Per implementation plan Step 5.1 (value by initiative family).

    Args:
        initiative_configs: Resolved configs for generation_tag lookup.
        final_world_state: Final world state with per-initiative value accumulators.

    Returns:
        Dict mapping generation_tag to cumulative value.
    """
    config_map = {cfg.initiative_id: cfg for cfg in initiative_configs}
    value_by_family: dict[str, float] = {}
    for init_state in final_world_state.initiative_states:
        cfg = config_map.get(init_state.initiative_id)
        label = cfg.generation_tag if cfg is not None and cfg.generation_tag else "unknown"
        value_by_family[label] = (
            value_by_family.get(label, 0.0) + init_state.cumulative_value_realized
        )
    return value_by_family


def compute_family_timing_profile(
    completion_events: list[CompletionEvent],
    stop_events: list[StopEvent],
    initiative_configs: tuple[ResolvedInitiativeConfig, ...],
    peak_capability_tick: int,
) -> FamilyTimingProfile:
    """Compute per-family timing metrics from events.

    Per implementation plan Step 5.2. Generalizes timing analysis to all
    four canonical families because governance pacing is a core study
    question and timing often matters as much as totals.

    Args:
        completion_events: All completion events from the run.
        stop_events: All stop events from the run.
        initiative_configs: Resolved configs for generation_tag lookup.
        peak_capability_tick: Tick at which peak capability was reached.

    Returns:
        FamilyTimingProfile with per-family timing metrics.
    """
    config_map = {cfg.initiative_id: cfg for cfg in initiative_configs}

    # Collect completion ticks by family.
    completion_ticks_by_family: dict[str, list[int]] = {}
    for event in completion_events:
        cfg = config_map.get(event.initiative_id)
        label = cfg.generation_tag if cfg is not None and cfg.generation_tag else "unknown"
        completion_ticks_by_family.setdefault(label, []).append(event.tick)

    # First completion tick and mean completion tick by family.
    # Include all four canonical families even if no completions occurred.
    canonical_families = ["flywheel", "right_tail", "enabler", "quick_win"]
    first_completion: dict[str, int | None] = {}
    mean_completion: dict[str, float | None] = {}
    frozen_ticks: dict[str, tuple[int, ...]] = {}

    for family in canonical_families:
        ticks = completion_ticks_by_family.get(family, [])
        if ticks:
            first_completion[family] = min(ticks)
            mean_completion[family] = sum(ticks) / len(ticks)
            frozen_ticks[family] = tuple(sorted(ticks))
        else:
            first_completion[family] = None
            mean_completion[family] = None
            frozen_ticks[family] = ()

    # Include any non-canonical families that appeared in events.
    for label, ticks in completion_ticks_by_family.items():
        if label not in frozen_ticks:
            first_completion[label] = min(ticks) if ticks else None
            mean_completion[label] = sum(ticks) / len(ticks) if ticks else None
            frozen_ticks[label] = tuple(sorted(ticks))

    # First right-tail stop tick.
    first_rt_stop: int | None = None
    for event in stop_events:
        cfg = config_map.get(event.initiative_id)
        if (
            cfg is not None
            and cfg.generation_tag == "right_tail"
            and (first_rt_stop is None or event.tick < first_rt_stop)
        ):
            first_rt_stop = event.tick

    return FamilyTimingProfile(
        first_completion_tick_by_family=first_completion,
        mean_completion_tick_by_family=mean_completion,
        completion_ticks_by_family=frozen_ticks,
        peak_capability_tick=peak_capability_tick,
        first_right_tail_stop_tick=first_rt_stop,
    )


def compute_frontier_summary(
    final_world_state: WorldState,
) -> FrontierSummary | None:
    """Compute frontier state summary from the final world state.

    Per implementation plan Step 5.1 (frontier state by family).

    Args:
        final_world_state: Final world state with frontier state.

    Returns:
        FrontierSummary with per-family frontier state, or None if
        no frontier state is tracked (fixed-pool runs).
    """
    if not final_world_state.frontier_state_by_family:
        return None

    family_states: dict[str, dict[str, float | int]] = {}
    for tag, frontier_state in final_world_state.frontier_state_by_family:
        family_states[tag] = {
            "n_resolved": frontier_state.n_resolved,
            "n_frontier_draws": frontier_state.n_frontier_draws,
            "effective_alpha_multiplier": frontier_state.effective_alpha_multiplier,
        }

    return FrontierSummary(family_frontier_states=family_states)


def compute_right_tail_false_stop_profile(
    stop_events: list[StopEvent],
    completion_events: list[CompletionEvent],
    initiative_configs: tuple[ResolvedInitiativeConfig, ...],
) -> RightTailFalseStopProfile:
    """Compute right-tail false-stop metrics from events and configs.

    Per reporting_package_specification.md §Source fields and computation:
    - An initiative is major-win-eligible if and only if
      cfg.value_channels.major_win_event.enabled is True AND
      cfg.value_channels.major_win_event.is_major_win is True.
    - Only initiatives with generation_tag == "right_tail" are counted.
    - right_tail_false_stop_rate = stopped_eligible / eligible,
      None when eligible == 0.
    - belief_at_stop is StopEvent.quality_belief_t for stopped eligible
      initiatives, in stable initiative_id order.

    Args:
        stop_events: All StopEvent records from the run.
        completion_events: All CompletionEvent records from the run.
        initiative_configs: Resolved initiative configs.

    Returns:
        RightTailFalseStopProfile with false-stop metrics.
    """
    config_map = {cfg.initiative_id: cfg for cfg in initiative_configs}

    # Identify right-tail initiatives that are major-win-eligible.
    eligible_ids: set[str] = set()
    for cfg in initiative_configs:
        if (
            cfg.generation_tag == "right_tail"
            and cfg.value_channels.major_win_event.enabled
            and cfg.value_channels.major_win_event.is_major_win
        ):
            eligible_ids.add(cfg.initiative_id)

    # Count right-tail completions and stops (any right-tail, not just eligible).
    stopped_rt_ids: set[str] = set()
    for event in stop_events:
        cfg = config_map.get(event.initiative_id)
        if cfg is not None and cfg.generation_tag == "right_tail":
            stopped_rt_ids.add(event.initiative_id)

    completed_rt_ids: set[str] = set()
    for event in completion_events:
        cfg = config_map.get(event.initiative_id)
        if cfg is not None and cfg.generation_tag == "right_tail":
            completed_rt_ids.add(event.initiative_id)

    # Stopped eligible: intersection of eligible and stopped right-tail.
    stopped_eligible_ids = eligible_ids & stopped_rt_ids

    # Collect belief_at_stop for stopped eligible, in stable id order.
    # Build a lookup from initiative_id to StopEvent.quality_belief_t.
    stop_belief_by_id: dict[str, float] = {}
    for event in stop_events:
        if event.initiative_id in stopped_eligible_ids:
            stop_belief_by_id[event.initiative_id] = event.quality_belief_t

    belief_at_stop_values = tuple(
        stop_belief_by_id[init_id] for init_id in sorted(stopped_eligible_ids)
    )

    # Compute false-stop rate.
    eligible_count = len(eligible_ids)
    stopped_eligible_count = len(stopped_eligible_ids)
    false_stop_rate: float | None = None
    if eligible_count > 0:
        false_stop_rate = stopped_eligible_count / eligible_count

    return RightTailFalseStopProfile(
        right_tail_eligible_count=eligible_count,
        right_tail_stopped_eligible_count=stopped_eligible_count,
        right_tail_completions=len(completed_rt_ids),
        right_tail_stops=len(stopped_rt_ids),
        right_tail_false_stop_rate=false_stop_rate,
        belief_at_stop_for_stopped_eligible=belief_at_stop_values,
    )


def assemble_run_result(
    collector: RunCollector,
    config: SimulationConfiguration,
    initiative_configs: tuple[ResolvedInitiativeConfig, ...],
    final_world_state: WorldState,
    manifest: RunManifest,
) -> RunResult:
    """Assemble a RunResult from collected per-tick data and events.

    This is the final aggregation step called by the runner after the
    tick loop completes. It computes all derived metrics from the
    raw collected data.

    Args:
        collector: The mutable RunCollector with all collected data.
        config: The simulation configuration (for reporting flags).
        initiative_configs: Resolved initiative configs.
        final_world_state: The WorldState at the end of the simulation.
        manifest: The RunManifest for provenance.

    Returns:
        An immutable RunResult with all primary outputs.
    """
    reporting = config.reporting

    # --- Build initiative-level lookups from final world state ---
    cumulative_labor_by_init: dict[str, float] = {}
    cumulative_attention_by_init: dict[str, float] = {}
    residual_value_by_init: dict[str, float] = {}
    residual_activated_ids: set[str] = set()
    residual_activation_ticks: dict[str, int] = {}

    for init_state in final_world_state.initiative_states:
        cumulative_labor_by_init[init_state.initiative_id] = init_state.cumulative_labor_invested
        cumulative_attention_by_init[init_state.initiative_id] = (
            init_state.cumulative_attention_invested
        )
        residual_value_by_init[init_state.initiative_id] = (
            init_state.cumulative_residual_value_realized
        )
        if init_state.residual_activated:
            residual_activated_ids.add(init_state.initiative_id)
            if init_state.residual_activation_tick is not None:
                residual_activation_ticks[init_state.initiative_id] = (
                    init_state.residual_activation_tick
                )

    # --- Cumulative value ---
    cumulative_value_total = collector.cumulative_lump_value + collector.cumulative_residual_value

    # --- Value by channel ---
    value_by_channel = compute_value_by_channel(
        cumulative_lump_value=collector.cumulative_lump_value,
        cumulative_residual_value=collector.cumulative_residual_value,
        stop_events=collector.stop_events,
        completion_events=collector.completion_events,
        initiative_configs=initiative_configs,
        residual_value_by_initiative=residual_value_by_init,
    )

    # --- Major-win profile ---
    # Compute total labor in right-tail initiatives.
    total_right_tail_labor = 0.0
    for cfg in initiative_configs:
        if cfg.generation_tag == "right_tail":
            total_right_tail_labor += cumulative_labor_by_init.get(cfg.initiative_id, 0.0)

    major_win_profile = compute_major_win_profile(
        major_win_events=collector.major_win_events,
        initiative_configs=initiative_configs,
        total_right_tail_labor=total_right_tail_labor,
    )

    # --- Belief accuracy ---
    belief_accuracy = compute_belief_accuracy(collector.per_initiative_tick_records)

    # --- Terminal state ---
    terminal_capability_t = final_world_state.portfolio_capability
    max_portfolio_capability_t = collector.max_portfolio_capability_t

    # The final tick index is final_world_state.tick - 1 because step_world
    # advances the tick counter.  But for residual rate computation we use
    # the last tick that was actually simulated.
    final_tick = final_world_state.tick - 1
    terminal_residual_rate = compute_terminal_aggregate_residual_rate(
        initiative_configs=initiative_configs,
        residual_activated_ids=residual_activated_ids,
        final_tick=final_tick,
        residual_activation_ticks=residual_activation_ticks,
    )

    # --- Idle capacity ---
    total_team_ticks = config.teams.team_count * config.time.tick_horizon
    idle_capacity = compute_idle_capacity_profile(
        cumulative_idle_team_ticks=collector.cumulative_idle_team_ticks,
        total_team_ticks=total_team_ticks,
        pool_exhaustion_tick=collector.pool_exhaustion_tick,
    )

    # --- Exploration cost ---
    exploration_cost = compute_exploration_cost_profile(
        stop_events=collector.stop_events,
        completion_events=collector.completion_events,
        initiative_configs=initiative_configs,
        cumulative_labor_by_initiative=cumulative_labor_by_init,
        cumulative_attention_by_initiative=cumulative_attention_by_init,
    )

    # --- Right-tail false-stop profile ---
    right_tail_false_stop = compute_right_tail_false_stop_profile(
        stop_events=collector.stop_events,
        completion_events=collector.completion_events,
        initiative_configs=initiative_configs,
    )

    # --- Reassignment ---
    reassignment_profile = ReassignmentProfile(
        reassignment_event_count=len(collector.reassignment_events),
        reassignment_event_log=(
            tuple(collector.reassignment_events) if reporting.record_event_log else None
        ),
    )

    # --- Ramp labor fraction ---
    ramp_labor_fraction = 0.0
    if total_team_ticks > 0:
        ramp_labor_fraction = collector.cumulative_ramp_labor / total_team_ticks

    # --- Value by initiative family ---
    value_by_family = compute_value_by_family(
        initiative_configs=initiative_configs,
        final_world_state=final_world_state,
    )

    # --- Family timing ---
    family_timing = compute_family_timing_profile(
        completion_events=collector.completion_events,
        stop_events=collector.stop_events,
        initiative_configs=initiative_configs,
        peak_capability_tick=collector.peak_capability_tick,
    )

    # --- Frontier summary ---
    frontier_summary = compute_frontier_summary(
        final_world_state=final_world_state,
    )

    # --- Conditional event logs ---
    major_win_log: tuple[MajorWinEvent, ...] | None = None
    stop_log: tuple[StopEvent, ...] | None = None
    if reporting.record_event_log:
        major_win_log = tuple(collector.major_win_events)
        stop_log = tuple(collector.stop_events)

    # --- Conditional per-tick logs ---
    per_init_records: tuple[PerInitiativeTickRecord, ...] | None = None
    portfolio_records: tuple[PortfolioTickRecord, ...] | None = None
    if reporting.record_per_tick_logs:
        per_init_records = tuple(collector.per_initiative_tick_records)
        portfolio_records = tuple(collector.portfolio_tick_records)

    return RunResult(
        cumulative_value_total=cumulative_value_total,
        value_by_channel=value_by_channel,
        major_win_profile=major_win_profile,
        belief_accuracy=belief_accuracy,
        terminal_capability_t=terminal_capability_t,
        max_portfolio_capability_t=max_portfolio_capability_t,
        terminal_aggregate_residual_rate=terminal_residual_rate,
        idle_capacity_profile=idle_capacity,
        cumulative_baseline_value=collector.cumulative_baseline_value,
        exploration_cost_profile=exploration_cost,
        right_tail_false_stop_profile=right_tail_false_stop,
        reassignment_profile=reassignment_profile,
        cumulative_ramp_labor=collector.cumulative_ramp_labor,
        ramp_labor_fraction=ramp_labor_fraction,
        value_by_family=value_by_family,
        family_timing=family_timing,
        frontier_summary=frontier_summary,
        attention_feasibility_violation_count=len(
            collector.attention_feasibility_violation_events
        ),
        major_win_event_log=major_win_log,
        stop_event_log=stop_log,
        per_initiative_tick_records=per_init_records,
        portfolio_tick_records=portfolio_records,
        manifest=manifest,
    )
