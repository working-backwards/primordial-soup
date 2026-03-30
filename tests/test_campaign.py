"""Tests for campaign specification, LHS governance sweep, manifest, and campaign runner.

Tests cover:
    - EnvironmentSpec construction and baseline factory
    - LhsParameterBounds construction
    - GovernanceSweepSpec construction
    - CampaignSpec construction
    - LHS unit sample generation (stratification, coverage, reproducibility)
    - Governance config generation from LHS (bounds, types, feasibility)
    - Archetype anchor inclusion
    - Validation of all generated configs
    - Manifest serialization and round-trip
    - Campaign runner (small-scale integration)

Design references:
    - docs/design/experiments.md (sweep design, LHS spec)
    - docs/design/experiments.md (sweep design, LHS spec, sample sizes)
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import numpy as np
import pytest

from primordial_soup.campaign import (
    CampaignResult,
    CampaignSpec,
    EnvironmentSpec,
    GovernanceSweepSpec,
    LhsParameterBounds,
    WorkforceArchitectureSpec,
    generate_governance_configs,
    generate_lhs_unit_sample,
    make_default_parameter_bounds,
    run_campaign,
)
from primordial_soup.config import (
    GovernanceConfig,
    SimulationConfiguration,
    validate_configuration,
)
from primordial_soup.manifest import (
    campaign_result_to_dict,
    campaign_spec_to_dict,
    governance_config_to_dict,
    read_campaign_manifest,
    write_campaign_manifest,
)
from primordial_soup.presets import (
    make_baseline_environment_spec,
    make_baseline_initiative_generator_config,
    make_baseline_model_config,
    make_baseline_time_config,
    make_baseline_workforce_config,
)

if TYPE_CHECKING:
    from pathlib import Path

    from primordial_soup.policy import GovernancePolicy


# ===========================================================================
# Fixtures and helpers
# ===========================================================================


@pytest.fixture
def baseline_environment() -> EnvironmentSpec:
    """Build the baseline EnvironmentSpec for tests."""
    return make_baseline_environment_spec()


@pytest.fixture
def default_bounds() -> LhsParameterBounds:
    """Build the default LHS parameter bounds for tests."""
    return make_default_parameter_bounds()


@pytest.fixture
def small_sweep_spec(default_bounds: LhsParameterBounds) -> GovernanceSweepSpec:
    """Build a small GovernanceSweepSpec for fast tests.

    Uses 10 LHS samples (below the 80 minimum, but fine for unit tests).
    """
    return GovernanceSweepSpec(
        parameter_bounds=default_bounds,
        lhs_sample_count=10,
        design_seed=42,
        include_archetype_anchors=True,
    )


@pytest.fixture
def small_campaign_spec(
    baseline_environment: EnvironmentSpec,
    small_sweep_spec: GovernanceSweepSpec,
) -> CampaignSpec:
    """Build a small CampaignSpec for fast tests."""
    return CampaignSpec(
        campaign_id="test_campaign",
        description="Unit test campaign",
        environment=baseline_environment,
        governance_sweep=small_sweep_spec,
        world_seeds=(12345, 67890),
    )


# ===========================================================================
# Step 7f — Campaign spec types
# ===========================================================================


class TestEnvironmentSpec:
    """Tests for EnvironmentSpec construction and baseline factory."""

    def test_baseline_environment_spec_construction(self) -> None:
        """make_baseline_environment_spec returns a valid EnvironmentSpec."""
        env = make_baseline_environment_spec()
        assert isinstance(env, EnvironmentSpec)
        assert env.time.tick_horizon == 313
        assert env.teams.team_count == 24
        assert env.model.exec_attention_budget == 30.0
        assert len(env.initiative_generator.type_specs) == 4

    def test_baseline_environment_spec_matches_presets(self) -> None:
        """EnvironmentSpec fields match the individual preset factories."""
        env = make_baseline_environment_spec()
        assert env.time == make_baseline_time_config()
        assert env.teams == make_baseline_workforce_config()
        assert env.model == make_baseline_model_config()
        assert env.initiative_generator == make_baseline_initiative_generator_config()

    def test_environment_spec_is_frozen(self) -> None:
        """EnvironmentSpec is immutable (frozen dataclass)."""
        env = make_baseline_environment_spec()
        with pytest.raises(AttributeError):
            env.time = make_baseline_time_config()  # type: ignore[misc]


class TestWorkforceArchitectureSpec:
    """Tests for WorkforceArchitectureSpec construction and resolution.

    WorkforceArchitectureSpec is a builder-layer type that separates the
    environmental given (total labor endowment) from the governance
    architecture choice (team decomposition). It resolves into a
    concrete WorkforceConfig that the simulator consumes.
    """

    def test_resolve_equal_sized_teams(self) -> None:
        """Equal-sized teams when team_sizes is omitted."""
        spec = WorkforceArchitectureSpec(
            total_labor_endowment=12,
            team_count=4,
            ramp_period=3,
        )
        wc = spec.resolve()
        assert wc.team_count == 4
        assert wc.team_size == 3
        assert wc.ramp_period == 3
        assert wc.total_labor_endowment == 12

    def test_resolve_explicit_team_sizes(self) -> None:
        """Explicit per-team sizes when team_sizes is provided."""
        spec = WorkforceArchitectureSpec(
            total_labor_endowment=10,
            team_count=3,
            team_sizes=(2, 3, 5),
            ramp_period=4,
        )
        wc = spec.resolve()
        assert wc.team_count == 3
        assert wc.team_size == (2, 3, 5)
        assert wc.total_labor_endowment == 10

    def test_resolve_baseline_matches_preset(self) -> None:
        """Baseline architecture spec resolves to the same WorkforceConfig
        as the existing make_baseline_workforce_config() factory."""
        # 30 mixed-size teams: 20×5 + 8×10 + 2×20 = 220 total labor.
        baseline_team_sizes = (
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
        spec = WorkforceArchitectureSpec(
            total_labor_endowment=210,
            team_count=24,
            team_sizes=baseline_team_sizes,
            ramp_period=4,
        )
        wc = spec.resolve()
        baseline = make_baseline_workforce_config()
        assert wc.team_count == baseline.team_count
        assert wc.team_size == baseline.team_size
        assert wc.ramp_period == baseline.ramp_period
        assert wc.ramp_multiplier_shape == baseline.ramp_multiplier_shape

    def test_resolve_preserves_ramp_shape(self) -> None:
        """Ramp shape is carried through to the resolved WorkforceConfig."""
        from primordial_soup.types import RampShape

        spec = WorkforceArchitectureSpec(
            total_labor_endowment=6,
            team_count=3,
            ramp_period=5,
            ramp_multiplier_shape=RampShape.EXPONENTIAL,
        )
        wc = spec.resolve()
        assert wc.ramp_multiplier_shape == RampShape.EXPONENTIAL

    def test_resolve_fails_team_sizes_length_mismatch(self) -> None:
        """team_sizes with wrong length raises ValueError."""
        spec = WorkforceArchitectureSpec(
            total_labor_endowment=10,
            team_count=3,
            team_sizes=(5, 5),  # length 2, but team_count is 3
        )
        with pytest.raises(ValueError, match="team_sizes length"):
            spec.resolve()

    def test_resolve_fails_team_sizes_sum_mismatch(self) -> None:
        """team_sizes that don't sum to total_labor_endowment raises ValueError."""
        spec = WorkforceArchitectureSpec(
            total_labor_endowment=10,
            team_count=3,
            team_sizes=(2, 3, 4),  # sum is 9, not 10
        )
        with pytest.raises(ValueError, match="team_sizes sum"):
            spec.resolve()

    def test_resolve_fails_non_divisible_endowment(self) -> None:
        """Non-divisible total_labor_endowment / team_count raises ValueError
        when team_sizes is not provided."""
        spec = WorkforceArchitectureSpec(
            total_labor_endowment=10,
            team_count=3,  # 10 / 3 is not exact
        )
        with pytest.raises(ValueError, match="exactly divisible"):
            spec.resolve()

    def test_spec_is_frozen(self) -> None:
        """WorkforceArchitectureSpec is immutable."""
        spec = WorkforceArchitectureSpec(
            total_labor_endowment=8,
            team_count=4,
        )
        with pytest.raises(AttributeError):
            spec.team_count = 5  # type: ignore[misc]


class TestLhsParameterBounds:
    """Tests for LhsParameterBounds construction."""

    def test_default_bounds_construction(self) -> None:
        """make_default_parameter_bounds returns valid bounds."""
        bounds = make_default_parameter_bounds()
        assert isinstance(bounds, LhsParameterBounds)

    def test_default_bounds_ranges_are_valid(self) -> None:
        """All default bounds have lower <= upper."""
        bounds = make_default_parameter_bounds()
        assert bounds.confidence_decline_threshold[0] < bounds.confidence_decline_threshold[1]
        assert bounds.tam_threshold_ratio[0] < bounds.tam_threshold_ratio[1]
        assert bounds.base_tam_patience_window[0] < bounds.base_tam_patience_window[1]
        swst = bounds.stagnation_window_staffed_ticks
        assert swst[0] < swst[1]
        sbct = bounds.stagnation_belief_change_threshold
        assert sbct[0] < sbct[1]
        assert bounds.attention_min[0] < bounds.attention_min[1]
        assert bounds.attention_span[0] <= bounds.attention_span[1]
        assert bounds.exec_overrun_threshold[0] < bounds.exec_overrun_threshold[1]

    def test_default_bounds_attention_min_positive(self) -> None:
        """attention_min lower bound is positive (per experiments.md)."""
        bounds = make_default_parameter_bounds()
        assert bounds.attention_min[0] > 0

    def test_default_bounds_attention_span_nonnegative(self) -> None:
        """attention_span lower bound is nonnegative."""
        bounds = make_default_parameter_bounds()
        assert bounds.attention_span[0] >= 0


class TestGovernanceSweepSpec:
    """Tests for GovernanceSweepSpec construction."""

    def test_sweep_spec_construction(self, small_sweep_spec: GovernanceSweepSpec) -> None:
        """GovernanceSweepSpec can be constructed with valid parameters."""
        assert small_sweep_spec.lhs_sample_count == 10
        assert small_sweep_spec.design_seed == 42
        assert small_sweep_spec.include_archetype_anchors is True


class TestCampaignSpec:
    """Tests for CampaignSpec construction."""

    def test_campaign_spec_construction(self, small_campaign_spec: CampaignSpec) -> None:
        """CampaignSpec can be constructed with valid parameters."""
        assert small_campaign_spec.campaign_id == "test_campaign"
        assert len(small_campaign_spec.world_seeds) == 2

    def test_campaign_spec_is_frozen(self, small_campaign_spec: CampaignSpec) -> None:
        """CampaignSpec is immutable."""
        with pytest.raises(AttributeError):
            small_campaign_spec.campaign_id = "modified"  # type: ignore[misc]


# ===========================================================================
# Step 7g — LHS generation
# ===========================================================================


class TestLhsUnitSample:
    """Tests for the LHS unit sample generator."""

    def test_shape(self) -> None:
        """LHS unit sample has correct shape (N, D)."""
        rng = np.random.default_rng(42)
        sample = generate_lhs_unit_sample(20, 8, rng)
        assert sample.shape == (20, 8)

    def test_values_in_unit_interval(self) -> None:
        """All values are in [0, 1]."""
        rng = np.random.default_rng(42)
        sample = generate_lhs_unit_sample(100, 8, rng)
        assert np.all(sample >= 0.0)
        assert np.all(sample <= 1.0)

    def test_stratification_property(self) -> None:
        """Each column has exactly one sample per stratum.

        The defining property of LHS: when dividing [0,1] into N
        equal strata, each stratum contains exactly one sample point
        per dimension.
        """
        n_samples = 50
        rng = np.random.default_rng(42)
        sample = generate_lhs_unit_sample(n_samples, 8, rng)

        for dim in range(8):
            column = sample[:, dim]
            # Map each value to its stratum index.
            strata = np.floor(column * n_samples).astype(int)
            # Clamp the maximum index (value == 1.0 edge case).
            strata = np.minimum(strata, n_samples - 1)
            # Each stratum index should appear exactly once.
            unique_strata = np.unique(strata)
            assert (
                len(unique_strata) == n_samples
            ), f"Dimension {dim}: expected {n_samples} unique strata, got {len(unique_strata)}"

    def test_reproducibility(self) -> None:
        """Same seed produces identical samples."""
        sample_a = generate_lhs_unit_sample(20, 8, np.random.default_rng(42))
        sample_b = generate_lhs_unit_sample(20, 8, np.random.default_rng(42))
        np.testing.assert_array_equal(sample_a, sample_b)

    def test_different_seeds_produce_different_samples(self) -> None:
        """Different seeds produce different samples."""
        sample_a = generate_lhs_unit_sample(20, 8, np.random.default_rng(42))
        sample_b = generate_lhs_unit_sample(20, 8, np.random.default_rng(99))
        assert not np.array_equal(sample_a, sample_b)

    def test_single_sample(self) -> None:
        """N=1 produces a valid single-row sample."""
        rng = np.random.default_rng(42)
        sample = generate_lhs_unit_sample(1, 8, rng)
        assert sample.shape == (1, 8)
        assert np.all(sample >= 0.0)
        assert np.all(sample <= 1.0)


class TestGenerateGovernanceConfigs:
    """Tests for the governance config generator."""

    def test_correct_count_with_archetypes(
        self,
        small_sweep_spec: GovernanceSweepSpec,
        baseline_environment: EnvironmentSpec,
    ) -> None:
        """Output count = LHS samples + 3 archetypes."""
        configs = generate_governance_configs(small_sweep_spec, baseline_environment)
        # 10 LHS + 3 archetypes = 13
        assert len(configs) == 13

    def test_correct_count_without_archetypes(
        self,
        default_bounds: LhsParameterBounds,
        baseline_environment: EnvironmentSpec,
    ) -> None:
        """Output count = LHS samples when archetypes excluded."""
        spec = GovernanceSweepSpec(
            parameter_bounds=default_bounds,
            lhs_sample_count=10,
            design_seed=42,
            include_archetype_anchors=False,
        )
        configs = generate_governance_configs(spec, baseline_environment)
        assert len(configs) == 10

    def test_all_configs_are_governance_config_type(
        self,
        small_sweep_spec: GovernanceSweepSpec,
        baseline_environment: EnvironmentSpec,
    ) -> None:
        """All returned objects are GovernanceConfig instances."""
        configs = generate_governance_configs(small_sweep_spec, baseline_environment)
        for config in configs:
            assert isinstance(config, GovernanceConfig)

    def test_lhs_configs_have_sweep_policy_id(
        self,
        small_sweep_spec: GovernanceSweepSpec,
        baseline_environment: EnvironmentSpec,
    ) -> None:
        """LHS-generated configs have lhs_sweep_NNNN policy_id."""
        configs = generate_governance_configs(small_sweep_spec, baseline_environment)
        lhs_configs = configs[:10]  # first 10 are LHS
        for i, config in enumerate(lhs_configs):
            assert config.policy_id == f"lhs_sweep_{i:04d}"

    def test_archetype_policy_ids(
        self,
        small_sweep_spec: GovernanceSweepSpec,
        baseline_environment: EnvironmentSpec,
    ) -> None:
        """Last 3 configs have the named archetype policy_ids."""
        configs = generate_governance_configs(small_sweep_spec, baseline_environment)
        archetype_configs = configs[10:]  # last 3 are archetypes
        policy_ids = [c.policy_id for c in archetype_configs]
        assert policy_ids == ["balanced", "aggressive_stop_loss", "patient_moonshot"]

    def test_parameter_bounds_respected(
        self,
        small_sweep_spec: GovernanceSweepSpec,
        baseline_environment: EnvironmentSpec,
    ) -> None:
        """All LHS-generated parameters fall within specified bounds."""
        configs = generate_governance_configs(small_sweep_spec, baseline_environment)
        bounds = small_sweep_spec.parameter_bounds
        lhs_configs = configs[:10]

        for config in lhs_configs:
            # Continuous parameters.
            cdt = config.confidence_decline_threshold
            cdt_lo, cdt_hi = bounds.confidence_decline_threshold
            assert cdt_lo <= cdt <= cdt_hi
            ttr = config.tam_threshold_ratio
            assert bounds.tam_threshold_ratio[0] <= ttr <= bounds.tam_threshold_ratio[1]
            se = config.stagnation_belief_change_threshold
            sbct = bounds.stagnation_belief_change_threshold
            assert sbct[0] <= se <= sbct[1]
            am = config.attention_min
            assert bounds.attention_min[0] <= am <= bounds.attention_min[1]
            eot = config.exec_overrun_threshold
            assert bounds.exec_overrun_threshold[0] <= eot <= bounds.exec_overrun_threshold[1]

            # Integer parameters (within bounds after rounding).
            btpw = config.base_tam_patience_window
            btpw_lo, btpw_hi = bounds.base_tam_patience_window
            assert btpw_lo <= btpw <= btpw_hi
            swst = config.stagnation_window_staffed_ticks
            swst_lo, swst_hi = bounds.stagnation_window_staffed_ticks
            assert swst_lo <= swst <= swst_hi

    def test_integer_parameters_are_int(
        self,
        small_sweep_spec: GovernanceSweepSpec,
        baseline_environment: EnvironmentSpec,
    ) -> None:
        """Integer governance parameters are actual ints, not floats."""
        configs = generate_governance_configs(small_sweep_spec, baseline_environment)
        for config in configs[:10]:
            assert isinstance(config.base_tam_patience_window, int)
            assert isinstance(config.stagnation_window_staffed_ticks, int)

    def test_attention_max_derived_from_min_plus_span(
        self,
        small_sweep_spec: GovernanceSweepSpec,
        baseline_environment: EnvironmentSpec,
    ) -> None:
        """attention_max = min(attention_min + span, 1.0) and >= attention_min."""
        configs = generate_governance_configs(small_sweep_spec, baseline_environment)
        for config in configs[:10]:
            assert config.attention_max is not None
            # attention_max >= attention_min (feasibility by construction).
            assert config.attention_max >= config.attention_min
            # attention_max <= 1.0 (capped).
            assert config.attention_max <= 1.0

    def test_attention_max_not_exceed_one(
        self,
        baseline_environment: EnvironmentSpec,
    ) -> None:
        """attention_max is capped at 1.0 even with large attention_min + span."""
        # Use bounds where attention_min + attention_span could exceed 1.0.
        bounds = LhsParameterBounds(
            confidence_decline_threshold=(0.1, 0.45),
            tam_threshold_ratio=(0.3, 0.9),
            base_tam_patience_window=(3, 30),
            stagnation_window_staffed_ticks=(5, 40),
            stagnation_belief_change_threshold=(0.005, 0.05),
            attention_min=(0.5, 0.9),  # high floor
            attention_span=(0.3, 0.8),  # wide span
            exec_overrun_threshold=(0.2, 0.6),
        )
        spec = GovernanceSweepSpec(
            parameter_bounds=bounds,
            lhs_sample_count=20,
            design_seed=42,
            include_archetype_anchors=False,
        )
        configs = generate_governance_configs(spec, baseline_environment)
        for config in configs:
            assert config.attention_max is not None
            assert config.attention_max <= 1.0
            assert config.attention_max >= config.attention_min

    def test_portfolio_risk_params_all_none(
        self,
        small_sweep_spec: GovernanceSweepSpec,
        baseline_environment: EnvironmentSpec,
    ) -> None:
        """All generated configs have portfolio-risk params set to None."""
        configs = generate_governance_configs(small_sweep_spec, baseline_environment)
        for config in configs:
            assert config.low_quality_belief_threshold is None
            assert config.max_low_quality_belief_labor_share is None
            assert config.max_single_initiative_labor_share is None

    def test_confidence_decline_always_float_in_lhs(
        self,
        small_sweep_spec: GovernanceSweepSpec,
        baseline_environment: EnvironmentSpec,
    ) -> None:
        """LHS configs always have active confidence_decline_threshold (float, not None).

        Disabled-rule variants are separate design points, not LHS values.
        """
        configs = generate_governance_configs(small_sweep_spec, baseline_environment)
        for config in configs[:10]:
            assert config.confidence_decline_threshold is not None
            assert isinstance(config.confidence_decline_threshold, float)

    def test_exec_overrun_always_float_in_lhs(
        self,
        small_sweep_spec: GovernanceSweepSpec,
        baseline_environment: EnvironmentSpec,
    ) -> None:
        """LHS configs always have active exec_overrun_threshold (float, not None)."""
        configs = generate_governance_configs(small_sweep_spec, baseline_environment)
        for config in configs[:10]:
            assert config.exec_overrun_threshold is not None
            assert isinstance(config.exec_overrun_threshold, float)

    def test_all_configs_pass_validation(
        self,
        small_sweep_spec: GovernanceSweepSpec,
        baseline_environment: EnvironmentSpec,
    ) -> None:
        """Every generated GovernanceConfig produces a valid SimulationConfiguration.

        This is the critical integration test: each generated governance
        config, when combined with the baseline environment, must pass
        validate_configuration without errors.
        """
        configs = generate_governance_configs(small_sweep_spec, baseline_environment)
        env = baseline_environment
        for config in configs:
            sim_config = SimulationConfiguration(
                world_seed=42,
                time=env.time,
                teams=env.teams,
                model=env.model,
                governance=config,
                reporting=_make_minimal_reporting_config(),
                initiative_generator=env.initiative_generator,
            )
            # Should not raise.
            validate_configuration(sim_config)

    def test_reproducibility_same_design_seed(
        self,
        default_bounds: LhsParameterBounds,
        baseline_environment: EnvironmentSpec,
    ) -> None:
        """Same design_seed produces identical governance configs."""
        spec = GovernanceSweepSpec(
            parameter_bounds=default_bounds,
            lhs_sample_count=20,
            design_seed=42,
            include_archetype_anchors=False,
        )
        configs_a = generate_governance_configs(spec, baseline_environment)
        configs_b = generate_governance_configs(spec, baseline_environment)

        assert len(configs_a) == len(configs_b)
        for a, b in zip(configs_a, configs_b, strict=True):
            assert a == b

    def test_different_design_seeds_differ(
        self,
        default_bounds: LhsParameterBounds,
        baseline_environment: EnvironmentSpec,
    ) -> None:
        """Different design_seeds produce different governance configs."""
        spec_a = GovernanceSweepSpec(
            parameter_bounds=default_bounds,
            lhs_sample_count=20,
            design_seed=42,
            include_archetype_anchors=False,
        )
        spec_b = GovernanceSweepSpec(
            parameter_bounds=default_bounds,
            lhs_sample_count=20,
            design_seed=99,
            include_archetype_anchors=False,
        )
        configs_a = generate_governance_configs(spec_a, baseline_environment)
        configs_b = generate_governance_configs(spec_b, baseline_environment)

        # At least some configs should differ.
        differences = sum(1 for a, b in zip(configs_a, configs_b, strict=True) if a != b)
        assert differences > 0

    def test_invalid_sample_count_raises(
        self,
        default_bounds: LhsParameterBounds,
        baseline_environment: EnvironmentSpec,
    ) -> None:
        """lhs_sample_count < 1 raises ValueError."""
        spec = GovernanceSweepSpec(
            parameter_bounds=default_bounds,
            lhs_sample_count=0,
            design_seed=42,
        )
        with pytest.raises(ValueError, match="lhs_sample_count must be >= 1"):
            generate_governance_configs(spec, baseline_environment)

    def test_below_minimum_sample_count_warns(
        self,
        default_bounds: LhsParameterBounds,
        baseline_environment: EnvironmentSpec,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """lhs_sample_count below 10×dimensions logs a warning."""
        spec = GovernanceSweepSpec(
            parameter_bounds=default_bounds,
            lhs_sample_count=10,
            design_seed=42,
        )
        with caplog.at_level("WARNING"):
            generate_governance_configs(spec, baseline_environment)
        assert "below the recommended minimum" in caplog.text

    def test_large_lhs_coverage(
        self,
        default_bounds: LhsParameterBounds,
        baseline_environment: EnvironmentSpec,
    ) -> None:
        """200 LHS samples provide reasonable coverage of the parameter space.

        Checks that the sampled values span most of each parameter's range.
        """
        spec = GovernanceSweepSpec(
            parameter_bounds=default_bounds,
            lhs_sample_count=200,
            design_seed=42,
            include_archetype_anchors=False,
        )
        configs = generate_governance_configs(spec, baseline_environment)

        # Check confidence_decline_threshold coverage.
        cdt_values = [c.confidence_decline_threshold for c in configs]
        cdt_range = max(cdt_values) - min(cdt_values)
        expected_range = (
            default_bounds.confidence_decline_threshold[1]
            - default_bounds.confidence_decline_threshold[0]
        )
        # Coverage should be at least 80% of the full range.
        assert cdt_range > 0.8 * expected_range

        # Check tam_threshold_ratio coverage.
        ttr_values = [c.tam_threshold_ratio for c in configs]
        ttr_range = max(ttr_values) - min(ttr_values)
        ttr_bounds = default_bounds.tam_threshold_ratio
        expected_ttr = ttr_bounds[1] - ttr_bounds[0]
        assert ttr_range > 0.8 * expected_ttr


# ===========================================================================
# Step 7h — Manifest serialization
# ===========================================================================


class TestGovernanceConfigSerialization:
    """Tests for GovernanceConfig JSON serialization."""

    def test_all_fields_present(
        self,
        small_sweep_spec: GovernanceSweepSpec,
        baseline_environment: EnvironmentSpec,
    ) -> None:
        """Serialized dict contains all GovernanceConfig fields."""
        configs = generate_governance_configs(small_sweep_spec, baseline_environment)
        d = governance_config_to_dict(configs[0])

        expected_keys = {
            "policy_id",
            "exec_attention_budget",
            "default_initial_quality_belief",
            "confidence_decline_threshold",
            "tam_threshold_ratio",
            "base_tam_patience_window",
            "stagnation_window_staffed_ticks",
            "stagnation_belief_change_threshold",
            "attention_min",
            "attention_max",
            "exec_overrun_threshold",
            "low_quality_belief_threshold",
            "max_low_quality_belief_labor_share",
            "max_single_initiative_labor_share",
        }
        assert set(d.keys()) == expected_keys

    def test_none_values_serialized_explicitly(
        self,
        small_sweep_spec: GovernanceSweepSpec,
        baseline_environment: EnvironmentSpec,
    ) -> None:
        """None-valued fields are present in the dict (not omitted)."""
        configs = generate_governance_configs(small_sweep_spec, baseline_environment)
        d = governance_config_to_dict(configs[0])
        # Portfolio-risk params should be None.
        assert "low_quality_belief_threshold" in d
        assert d["low_quality_belief_threshold"] is None

    def test_json_roundtrip(
        self,
        small_sweep_spec: GovernanceSweepSpec,
        baseline_environment: EnvironmentSpec,
    ) -> None:
        """GovernanceConfig dict survives JSON round-trip."""
        configs = generate_governance_configs(small_sweep_spec, baseline_environment)
        d = governance_config_to_dict(configs[0])
        json_str = json.dumps(d)
        restored = json.loads(json_str)
        assert restored == d


class TestCampaignSpecSerialization:
    """Tests for CampaignSpec JSON serialization."""

    def test_campaign_spec_to_dict_structure(
        self,
        small_campaign_spec: CampaignSpec,
    ) -> None:
        """campaign_spec_to_dict produces expected top-level keys."""
        d = campaign_spec_to_dict(small_campaign_spec)
        assert "campaign_id" in d
        assert "environment" in d
        assert "governance_sweep" in d
        assert "world_seeds" in d

    def test_design_seed_recorded(
        self,
        small_campaign_spec: CampaignSpec,
    ) -> None:
        """design_seed is recorded in the serialized governance_sweep."""
        d = campaign_spec_to_dict(small_campaign_spec)
        assert d["governance_sweep"]["design_seed"] == 42

    def test_parameter_bounds_recorded(
        self,
        small_campaign_spec: CampaignSpec,
    ) -> None:
        """Parameter bounds are recorded in the serialized governance_sweep."""
        d = campaign_spec_to_dict(small_campaign_spec)
        bounds = d["governance_sweep"]["parameter_bounds"]
        assert "confidence_decline_threshold" in bounds
        assert "attention_span" in bounds
        assert len(bounds["confidence_decline_threshold"]) == 2

    def test_json_roundtrip(
        self,
        small_campaign_spec: CampaignSpec,
    ) -> None:
        """CampaignSpec dict survives JSON round-trip."""
        d = campaign_spec_to_dict(small_campaign_spec)
        json_str = json.dumps(d)
        restored = json.loads(json_str)
        assert restored == d

    def test_world_seeds_preserved(
        self,
        small_campaign_spec: CampaignSpec,
    ) -> None:
        """world_seeds are preserved in serialization."""
        d = campaign_spec_to_dict(small_campaign_spec)
        assert d["world_seeds"] == [12345, 67890]


class TestManifestFileIO:
    """Tests for manifest file I/O."""

    def test_write_and_read_campaign_manifest(
        self,
        small_campaign_spec: CampaignSpec,
        tmp_path: Path,
    ) -> None:
        """Write campaign manifest to JSON and read it back."""
        output_path = tmp_path / "manifest.json"
        write_campaign_manifest(small_campaign_spec, output_path)

        assert output_path.exists()
        data = read_campaign_manifest(output_path)
        assert data["campaign_id"] == "test_campaign"
        assert data["governance_sweep"]["design_seed"] == 42

    def test_write_creates_parent_dirs(
        self,
        small_campaign_spec: CampaignSpec,
        tmp_path: Path,
    ) -> None:
        """write_campaign_manifest creates parent directories."""
        output_path = tmp_path / "nested" / "dir" / "manifest.json"
        write_campaign_manifest(small_campaign_spec, output_path)
        assert output_path.exists()


# ===========================================================================
# Step 7i — Campaign runner
# ===========================================================================


class TestCampaignRunner:
    """Tests for the campaign runner.

    Uses a very small campaign (2 LHS + 3 archetypes × 1 seed) to keep
    test execution fast while verifying correctness.
    """

    @pytest.fixture
    def tiny_campaign(self, baseline_environment: EnvironmentSpec) -> CampaignSpec:
        """Build a tiny campaign for fast runner tests.

        2 LHS samples + 3 archetypes = 5 configs × 1 world seed = 5 runs.
        """
        bounds = make_default_parameter_bounds()
        sweep = GovernanceSweepSpec(
            parameter_bounds=bounds,
            lhs_sample_count=2,
            design_seed=42,
            include_archetype_anchors=True,
        )
        return CampaignSpec(
            campaign_id="tiny_test",
            description="Tiny campaign for runner tests",
            environment=baseline_environment,
            governance_sweep=sweep,
            world_seeds=(12345,),
        )

    @staticmethod
    def _default_policy_factory(gov_config: GovernanceConfig) -> GovernancePolicy:
        """Map GovernanceConfig to policy by policy_id.

        Uses BalancedPolicy for all configs — the LHS sweep points
        don't have named archetype policies, so we use Balanced as
        a generic policy. The governance CONFIG parameters still vary;
        only the policy LOGIC is shared.
        """
        from primordial_soup.policy import (
            AggressiveStopLossPolicy,
            BalancedPolicy,
            PatientMoonshotPolicy,
        )

        policy_map = {
            "balanced": BalancedPolicy(),
            "aggressive_stop_loss": AggressiveStopLossPolicy(),
            "patient_moonshot": PatientMoonshotPolicy(),
        }
        # LHS sweep points use BalancedPolicy as the default.
        return policy_map.get(gov_config.policy_id, BalancedPolicy())

    def test_campaign_runner_produces_correct_run_count(
        self,
        tiny_campaign: CampaignSpec,
    ) -> None:
        """Campaign runner produces the expected number of RunResults."""
        result = run_campaign(tiny_campaign, self._default_policy_factory)
        # 2 LHS + 3 archetypes = 5 configs × 1 seed = 5 runs.
        assert result.total_runs == 5
        assert len(result.run_results) == 5

    def test_campaign_runner_returns_campaign_result(
        self,
        tiny_campaign: CampaignSpec,
    ) -> None:
        """Campaign runner returns a CampaignResult with correct structure."""
        result = run_campaign(tiny_campaign, self._default_policy_factory)
        assert isinstance(result, CampaignResult)
        assert result.campaign_spec == tiny_campaign
        assert len(result.governance_configs) == 5

    def test_campaign_runner_all_runs_produce_value(
        self,
        tiny_campaign: CampaignSpec,
    ) -> None:
        """All runs in the campaign produce non-negative cumulative value."""
        result = run_campaign(tiny_campaign, self._default_policy_factory)
        for run_result in result.run_results:
            assert run_result.cumulative_value_total >= 0.0

    def test_campaign_runner_deterministic(
        self,
        tiny_campaign: CampaignSpec,
    ) -> None:
        """Same campaign spec produces identical results."""
        result_a = run_campaign(tiny_campaign, self._default_policy_factory)
        result_b = run_campaign(tiny_campaign, self._default_policy_factory)
        assert result_a.total_runs == result_b.total_runs
        for a, b in zip(result_a.run_results, result_b.run_results, strict=True):
            assert a.cumulative_value_total == b.cumulative_value_total
            assert a.manifest.world_seed == b.manifest.world_seed
            assert a.manifest.policy_id == b.manifest.policy_id

    def test_campaign_result_serialization(
        self,
        tiny_campaign: CampaignSpec,
    ) -> None:
        """CampaignResult can be serialized to JSON."""
        result = run_campaign(tiny_campaign, self._default_policy_factory)
        d = campaign_result_to_dict(result)
        json_str = json.dumps(d)
        restored = json.loads(json_str)
        assert restored["total_runs"] == 5
        assert len(restored["run_summaries"]) == 5


# ===========================================================================
# Helpers
# ===========================================================================


def _make_minimal_reporting_config():
    """Build a minimal ReportingConfig for validation tests."""
    from primordial_soup.config import ReportingConfig

    return ReportingConfig(
        record_manifest=False,
        record_per_tick_logs=False,
        record_event_log=False,
    )
