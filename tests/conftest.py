"""Shared test fixtures and factory functions for Primordial Soup tests.

Prefer factory functions that build valid test objects with sensible
defaults over large shared fixtures. Per CLAUDE.md testing rules.
"""

from __future__ import annotations

from primordial_soup.config import (
    GovernanceConfig,
    ModelConfig,
    ReportingConfig,
    ResolvedInitiativeConfig,
    SimulationConfiguration,
    TimeConfig,
    WorkforceConfig,
)
from primordial_soup.observation import (
    GovernanceObservation,
    InitiativeObservation,
    PortfolioSummary,
    TeamObservation,
)
from primordial_soup.types import (
    CompletionLumpChannel,
    MajorWinEventChannel,
    RampShape,
    ResidualChannel,
    ValueChannels,
)


def make_value_channels(
    *,
    lump_enabled: bool = False,
    lump_value: float | None = None,
    residual_enabled: bool = False,
    residual_rate: float = 0.0,
    residual_decay: float = 0.0,
    major_win_enabled: bool = False,
    is_major_win: bool = False,
) -> ValueChannels:
    """Build a ValueChannels with sensible defaults."""
    return ValueChannels(
        completion_lump=CompletionLumpChannel(enabled=lump_enabled, realized_value=lump_value),
        residual=ResidualChannel(
            enabled=residual_enabled,
            residual_rate=residual_rate,
            residual_decay=residual_decay,
        ),
        major_win_event=MajorWinEventChannel(enabled=major_win_enabled, is_major_win=is_major_win),
    )


def make_initiative(
    *,
    initiative_id: str = "init-1",
    latent_quality: float = 0.6,
    dependency_level: float = 0.2,
    base_signal_st_dev: float = 0.1,
    value_channels: ValueChannels | None = None,
    true_duration_ticks: int | None = None,
    planned_duration_ticks: int | None = None,
    observable_ceiling: float | None = None,
    capability_contribution_scale: float = 0.0,
    generation_tag: str | None = None,
    staffing_response_scale: float = 0.0,
) -> ResolvedInitiativeConfig:
    """Build a valid ResolvedInitiativeConfig with sensible defaults."""
    if value_channels is None:
        value_channels = make_value_channels()
    return ResolvedInitiativeConfig(
        initiative_id=initiative_id,
        latent_quality=latent_quality,
        dependency_level=dependency_level,
        base_signal_st_dev=base_signal_st_dev,
        value_channels=value_channels,
        true_duration_ticks=true_duration_ticks,
        planned_duration_ticks=planned_duration_ticks,
        observable_ceiling=observable_ceiling,
        capability_contribution_scale=capability_contribution_scale,
        generation_tag=generation_tag,
        staffing_response_scale=staffing_response_scale,
    )


def make_model_config(**overrides: object) -> ModelConfig:
    """Build a valid ModelConfig with sensible defaults."""
    defaults = dict(
        exec_attention_budget=1.0,
        base_signal_st_dev_default=0.15,
        dependency_noise_exponent=1.0,
        default_initial_quality_belief=0.5,
        reference_ceiling=100.0,
        attention_noise_threshold=0.1,
        low_attention_penalty_slope=2.0,
        attention_curve_exponent=3.0,
        min_attention_noise_modifier=0.3,
        max_attention_noise_modifier=None,
        learning_rate=0.1,
        dependency_learning_scale=None,
        execution_signal_st_dev=0.15,
        execution_learning_rate=0.1,
        max_portfolio_capability=3.0,
        capability_decay=0.01,
    )
    defaults.update(overrides)
    return ModelConfig(**defaults)  # type: ignore[arg-type]


def make_governance_config(**overrides: object) -> GovernanceConfig:
    """Build a valid GovernanceConfig with sensible defaults."""
    defaults = dict(
        policy_id="balanced",
        exec_attention_budget=1.0,
        default_initial_quality_belief=0.5,
        confidence_decline_threshold=0.3,
        tam_threshold_ratio=0.3,
        base_tam_patience_window=5,
        stagnation_window_staffed_ticks=10,
        stagnation_belief_change_threshold=0.02,
        attention_min=0.1,
        attention_max=None,
        exec_overrun_threshold=0.5,
        low_quality_belief_threshold=None,
        max_low_quality_belief_labor_share=None,
        max_single_initiative_labor_share=None,
    )
    defaults.update(overrides)
    return GovernanceConfig(**defaults)  # type: ignore[arg-type]


_USE_DEFAULT = object()


def make_simulation_config(
    *,
    initiatives: tuple[ResolvedInitiativeConfig, ...] | None | object = _USE_DEFAULT,
    **overrides: object,
) -> SimulationConfiguration:
    """Build a valid SimulationConfiguration with sensible defaults.

    Pass initiatives=None explicitly to test the 'no initiatives' case.
    Omit it to get a single default initiative.
    """
    if initiatives is _USE_DEFAULT:
        initiatives = (make_initiative(),)

    defaults = dict(
        world_seed=42,
        time=TimeConfig(tick_horizon=100),
        teams=WorkforceConfig(
            team_count=3, team_size=1, ramp_period=3, ramp_multiplier_shape=RampShape.LINEAR
        ),
        model=make_model_config(),
        governance=make_governance_config(),
        reporting=ReportingConfig(),
        initiatives=initiatives,
        initiative_generator=None,
    )
    defaults.update(overrides)
    return SimulationConfiguration(**defaults)  # type: ignore[arg-type]


def make_initiative_observation(**overrides: object) -> InitiativeObservation:
    """Build a valid InitiativeObservation with sensible defaults.

    Represents an active, staffed initiative with neutral beliefs.
    """
    defaults = dict(
        initiative_id="init-1",
        lifecycle_state="active",
        assigned_team_id="team-1",
        quality_belief_t=0.5,
        observable_ceiling=None,
        required_team_size=1,
        effective_tam_patience_window=None,
        execution_belief_t=None,
        implied_duration_ticks=None,
        planned_duration_ticks=None,
        progress_fraction=None,
        review_count=0,
        staffed_tick_count=0,
        consecutive_reviews_below_tam_ratio=0,
        capability_contribution_scale=0.0,
        belief_history=(),
        generation_tag=None,
    )
    defaults.update(overrides)
    return InitiativeObservation(**defaults)  # type: ignore[arg-type]


def make_team_observation(**overrides: object) -> TeamObservation:
    """Build a valid TeamObservation with sensible defaults."""
    defaults = dict(
        team_id="team-1",
        assigned_initiative_id=None,
        available_next_tick=True,
        team_size=1,
    )
    defaults.update(overrides)
    return TeamObservation(**defaults)  # type: ignore[arg-type]


def make_portfolio_summary(**overrides: object) -> PortfolioSummary:
    """Build a valid PortfolioSummary with sensible defaults.

    Defaults represent an empty portfolio (no active labor).
    """
    defaults = dict(
        active_labor_total=0,
        active_labor_below_quality_threshold=None,
        low_quality_belief_labor_share=None,
        max_single_initiative_labor_share=None,
    )
    defaults.update(overrides)
    return PortfolioSummary(**defaults)  # type: ignore[arg-type]


def make_governance_observation(**overrides: object) -> GovernanceObservation:
    """Build a valid GovernanceObservation with sensible defaults.

    Defaults represent tick 0 with no initiatives and one available team.
    """
    defaults = dict(
        tick=0,
        available_team_count=1,
        exec_attention_budget=1.0,
        default_initial_quality_belief=0.5,
        attention_min_effective=0.1,
        attention_max_effective=1.0,
        portfolio_capability_level=1.0,
        portfolio_summary=make_portfolio_summary(),
        initiatives=(),
        teams=(),
    )
    defaults.update(overrides)
    return GovernanceObservation(**defaults)  # type: ignore[arg-type]
