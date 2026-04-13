"""Tests for configuration types and validation."""

from __future__ import annotations

import dataclasses

import pytest

from conftest import (
    make_governance_config,
    make_initiative,
    make_model_config,
    make_simulation_config,
    make_value_channels,
)
from primordial_soup.config import (
    GovernanceConfig,
    TimeConfig,
    WorkforceConfig,
    validate_configuration,
)
from primordial_soup.types import RampShape


class TestConfigConstruction:
    """Verify that valid configs can be constructed."""

    def test_time_config(self) -> None:
        tc = TimeConfig(tick_horizon=200, tick_label="month")
        assert tc.tick_horizon == 200
        assert tc.tick_label == "month"

    def test_workforce_config_scalar_team_size(self) -> None:
        wc = WorkforceConfig(team_count=5, team_size=3, ramp_period=4)
        assert wc.team_count == 5
        assert wc.team_size == 3
        assert wc.ramp_multiplier_shape == RampShape.LINEAR

    def test_workforce_config_per_team_sizes(self) -> None:
        wc = WorkforceConfig(team_count=3, team_size=(2, 3, 4), ramp_period=5)
        assert wc.team_size == (2, 3, 4)

    def test_total_labor_endowment_scalar_team_size(self) -> None:
        """total_labor_endowment = team_count * team_size for uniform teams."""
        wc = WorkforceConfig(team_count=5, team_size=3, ramp_period=4)
        assert wc.total_labor_endowment == 15

    def test_total_labor_endowment_tuple_team_size(self) -> None:
        """total_labor_endowment = sum of per-team sizes for heterogeneous teams."""
        wc = WorkforceConfig(team_count=3, team_size=(2, 3, 4), ramp_period=5)
        assert wc.total_labor_endowment == 9

    def test_total_labor_endowment_single_team(self) -> None:
        """Edge case: single team."""
        wc = WorkforceConfig(team_count=1, team_size=7, ramp_period=2)
        assert wc.total_labor_endowment == 7

    def test_total_labor_endowment_unit_teams(self) -> None:
        """Baseline case: many teams of size 1."""
        wc = WorkforceConfig(team_count=8, team_size=1, ramp_period=4)
        assert wc.total_labor_endowment == 8

    def test_model_config(self) -> None:
        mc = make_model_config()
        assert mc.default_initial_quality_belief == pytest.approx(0.5)
        assert mc.max_attention_noise_modifier is None

    def test_governance_config(self) -> None:
        gc = make_governance_config()
        assert gc.policy_id == "balanced"
        assert isinstance(gc.base_tam_patience_window, int)

    def test_governance_config_portfolio_risk_defaults(self) -> None:
        """Portfolio-risk fields default to None (disabled)."""
        gc = make_governance_config()
        assert gc.low_quality_belief_threshold is None
        assert gc.max_low_quality_belief_labor_share is None
        assert gc.max_single_initiative_labor_share is None

    def test_governance_config_portfolio_risk_set(self) -> None:
        """Portfolio-risk fields can be explicitly set."""
        gc = make_governance_config(
            low_quality_belief_threshold=0.4,
            max_low_quality_belief_labor_share=0.2,
            max_single_initiative_labor_share=0.3,
        )
        assert gc.low_quality_belief_threshold == pytest.approx(0.4)
        assert gc.max_low_quality_belief_labor_share == pytest.approx(0.2)
        assert gc.max_single_initiative_labor_share == pytest.approx(0.3)

    def test_resolved_initiative_defaults(self) -> None:
        init = make_initiative()
        assert init.required_team_size == 1
        assert init.initial_execution_belief == pytest.approx(1.0)
        assert init.capability_contribution_scale == pytest.approx(0.0)
        assert init.true_duration_ticks is None

    def test_simulation_config_with_initiatives(self) -> None:
        config = make_simulation_config()
        assert config.initiatives is not None
        assert config.initiative_generator is None

    def test_configs_are_frozen(self) -> None:
        config = make_simulation_config()
        with pytest.raises(dataclasses.FrozenInstanceError):
            config.world_seed = 99  # type: ignore[misc]


class TestValidation:
    """Test each validation rule from interfaces.md."""

    def test_valid_config_passes(self) -> None:
        config = make_simulation_config()
        validate_configuration(config)  # should not raise

    def test_both_initiatives_and_generator_rejected(self) -> None:
        from primordial_soup.config import InitiativeGeneratorConfig, InitiativeTypeSpec
        from primordial_soup.types import BetaDistribution

        gen = InitiativeGeneratorConfig(
            type_specs=(
                InitiativeTypeSpec(
                    generation_tag="test",
                    count=5,
                    quality_distribution=BetaDistribution(alpha=2.0, beta=5.0),
                    base_signal_st_dev_range=(0.05, 0.15),
                    dependency_level_range=(0.1, 0.4),
                ),
            )
        )
        config = make_simulation_config(
            initiatives=(make_initiative(),),
            initiative_generator=gen,
        )
        with pytest.raises(ValueError, match="Exactly one"):
            validate_configuration(config)

    def test_neither_initiatives_nor_generator_rejected(self) -> None:
        config = make_simulation_config(initiatives=None, initiative_generator=None)
        with pytest.raises(ValueError, match="Exactly one"):
            validate_configuration(config)

    def test_tick_horizon_must_be_positive(self) -> None:
        config = make_simulation_config(time=TimeConfig(tick_horizon=0))
        with pytest.raises(ValueError, match="tick_horizon"):
            validate_configuration(config)

    def test_team_count_must_be_positive(self) -> None:
        config = make_simulation_config(
            teams=WorkforceConfig(team_count=0, team_size=1, ramp_period=3)
        )
        with pytest.raises(ValueError, match="team_count"):
            validate_configuration(config)

    def test_attention_noise_threshold_bounds(self) -> None:
        config = make_simulation_config(model=make_model_config(attention_noise_threshold=1.5))
        with pytest.raises(ValueError, match="attention_noise_threshold"):
            validate_configuration(config)

    def test_low_attention_penalty_slope_nonnegative(self) -> None:
        config = make_simulation_config(model=make_model_config(low_attention_penalty_slope=-1.0))
        with pytest.raises(ValueError, match="low_attention_penalty_slope"):
            validate_configuration(config)

    def test_reference_ceiling_positive(self) -> None:
        config = make_simulation_config(model=make_model_config(reference_ceiling=0))
        with pytest.raises(ValueError, match="reference_ceiling"):
            validate_configuration(config)

    def test_min_le_max_attention_noise_modifier(self) -> None:
        config = make_simulation_config(
            model=make_model_config(
                min_attention_noise_modifier=5.0,
                max_attention_noise_modifier=2.0,
            )
        )
        with pytest.raises(ValueError, match="min_attention_noise_modifier"):
            validate_configuration(config)

    def test_max_portfolio_capability_ge_one(self) -> None:
        config = make_simulation_config(model=make_model_config(max_portfolio_capability=0.5))
        with pytest.raises(ValueError, match="max_portfolio_capability"):
            validate_configuration(config)

    def test_capability_decay_nonnegative(self) -> None:
        config = make_simulation_config(model=make_model_config(capability_decay=-0.1))
        with pytest.raises(ValueError, match="capability_decay"):
            validate_configuration(config)

    def test_execution_signal_st_dev_nonnegative(self) -> None:
        config = make_simulation_config(model=make_model_config(execution_signal_st_dev=-1.0))
        with pytest.raises(ValueError, match="execution_signal_st_dev"):
            validate_configuration(config)

    def test_execution_learning_rate_bounds(self) -> None:
        config = make_simulation_config(model=make_model_config(execution_learning_rate=0.0))
        with pytest.raises(ValueError, match="execution_learning_rate"):
            validate_configuration(config)

    def test_stagnation_window_staffed_ticks_ge_one(self) -> None:
        config = make_simulation_config(
            governance=make_governance_config(stagnation_window_staffed_ticks=0)
        )
        with pytest.raises(ValueError, match="stagnation_window_staffed_ticks"):
            validate_configuration(config)

    def test_stagnation_belief_change_threshold_nonnegative(self) -> None:
        config = make_simulation_config(
            governance=make_governance_config(stagnation_belief_change_threshold=-0.1)
        )
        with pytest.raises(ValueError, match="stagnation_belief_change_threshold"):
            validate_configuration(config)

    def test_attention_min_positive(self) -> None:
        """attention_min=0 is rejected when exec_attention_budget > 0."""
        config = make_simulation_config(governance=make_governance_config(attention_min=0.0))
        with pytest.raises(ValueError, match="attention_min"):
            validate_configuration(config)

    def test_attention_min_zero_valid_when_budget_zero(self) -> None:
        """attention_min=0 is valid when exec_attention_budget=0.

        Per governance.md §Zero-budget special case: when the executive
        allocates no time, attention_min=0 is valid because the attention
        floor is irrelevant.
        """
        config = make_simulation_config(
            model=make_model_config(exec_attention_budget=0.0),
            governance=make_governance_config(
                exec_attention_budget=0.0,
                attention_min=0.0,
            ),
        )
        validate_configuration(config)  # should not raise

    def test_attention_min_zero_still_invalid_when_budget_positive(self) -> None:
        """attention_min=0 is still rejected when budget > 0."""
        config = make_simulation_config(
            model=make_model_config(exec_attention_budget=5.0),
            governance=make_governance_config(
                exec_attention_budget=5.0,
                attention_min=0.0,
            ),
        )
        with pytest.raises(ValueError, match="attention_min"):
            validate_configuration(config)

    def test_attention_min_le_attention_max(self) -> None:
        config = make_simulation_config(
            governance=make_governance_config(attention_min=0.5, attention_max=0.3)
        )
        with pytest.raises(ValueError, match="attention_min must be <= attention_max"):
            validate_configuration(config)

    def test_team_size_tuple_length_must_match_team_count(self) -> None:
        """Tuple team_size with wrong length is rejected."""
        config = make_simulation_config(
            teams=WorkforceConfig(team_count=3, team_size=(1, 2), ramp_period=4)
        )
        with pytest.raises(ValueError, match="team_size tuple length"):
            validate_configuration(config)

    def test_team_size_tuple_matching_length_passes(self) -> None:
        """Tuple team_size with correct length passes validation."""
        config = make_simulation_config(
            teams=WorkforceConfig(team_count=3, team_size=(1, 2, 3), ramp_period=4)
        )
        validate_configuration(config)  # should not raise

    def test_base_tam_patience_window_must_be_int(self) -> None:
        # Simulate YAML coercion: base_tam_patience_window as float
        gc = make_governance_config()
        # Manually construct with float value to test the check
        gc_dict = {f.name: getattr(gc, f.name) for f in dataclasses.fields(gc)}
        gc_dict["base_tam_patience_window"] = 5.0  # type: ignore[assignment]
        bad_gc = GovernanceConfig(**gc_dict)  # type: ignore[arg-type]
        config = make_simulation_config(governance=bad_gc)
        with pytest.raises(ValueError, match="base_tam_patience_window must be int"):
            validate_configuration(config)


class TestInitiativeValidation:
    """Test per-initiative validation rules from interfaces.md."""

    def test_planned_duration_must_be_positive(self) -> None:
        init = make_initiative(planned_duration_ticks=0, true_duration_ticks=10)
        config = make_simulation_config(initiatives=(init,))
        with pytest.raises(ValueError, match="planned_duration_ticks must be > 0"):
            validate_configuration(config)

    def test_true_duration_must_be_positive(self) -> None:
        init = make_initiative(planned_duration_ticks=10, true_duration_ticks=0)
        config = make_simulation_config(initiatives=(init,))
        with pytest.raises(ValueError, match="true_duration_ticks must be > 0"):
            validate_configuration(config)

    def test_true_duration_requires_planned_duration(self) -> None:
        init = make_initiative(true_duration_ticks=20, planned_duration_ticks=None)
        config = make_simulation_config(initiatives=(init,))
        with pytest.raises(ValueError, match="requires planned_duration_ticks"):
            validate_configuration(config)

    def test_capability_requires_duration(self) -> None:
        init = make_initiative(capability_contribution_scale=1.0, true_duration_ticks=None)
        config = make_simulation_config(initiatives=(init,))
        with pytest.raises(ValueError, match="capability_contribution_scale > 0 requires"):
            validate_configuration(config)

    def test_lump_enabled_requires_realized_value(self) -> None:
        vc = make_value_channels(lump_enabled=True, lump_value=None)
        init = make_initiative(value_channels=vc)
        config = make_simulation_config(initiatives=(init,))
        with pytest.raises(ValueError, match="realized_value is absent"):
            validate_configuration(config)

    def test_lump_realized_value_nonnegative(self) -> None:
        vc = make_value_channels(lump_enabled=True, lump_value=-5.0)
        init = make_initiative(value_channels=vc)
        config = make_simulation_config(initiatives=(init,))
        with pytest.raises(ValueError, match="realized_value must be >= 0"):
            validate_configuration(config)

    def test_residual_decay_nonnegative(self) -> None:
        vc = make_value_channels(residual_enabled=True, residual_decay=-0.1)
        init = make_initiative(
            value_channels=vc, true_duration_ticks=20, planned_duration_ticks=20
        )
        config = make_simulation_config(initiatives=(init,))
        with pytest.raises(ValueError, match="residual_decay must be >= 0"):
            validate_configuration(config)

    def test_residual_on_completion_requires_duration(self) -> None:
        vc = make_value_channels(residual_enabled=True)
        init = make_initiative(value_channels=vc, true_duration_ticks=None)
        config = make_simulation_config(initiatives=(init,))
        with pytest.raises(ValueError, match="residual with activation_state='completed'"):
            validate_configuration(config)

    def test_valid_initiative_with_all_channels(self) -> None:
        """A fully-configured initiative should pass validation."""
        vc = make_value_channels(
            lump_enabled=True,
            lump_value=100.0,
            residual_enabled=True,
            residual_rate=5.0,
            residual_decay=0.02,
            major_win_enabled=True,
            is_major_win=True,
        )
        init = make_initiative(
            value_channels=vc,
            true_duration_ticks=30,
            planned_duration_ticks=25,
            observable_ceiling=500.0,
            capability_contribution_scale=0.5,
        )
        config = make_simulation_config(initiatives=(init,))
        validate_configuration(config)  # should not raise
