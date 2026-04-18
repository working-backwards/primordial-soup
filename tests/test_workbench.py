"""Tests for the run design workbench (workbench.py).

Tests cover all four new types (EnvironmentConditionsSpec,
GovernanceArchitectureSpec, OperatingPolicySpec, RunDesignSpec),
the validate_run_design() and resolve_run_design() functions, the
ResolvedRunDesign bundle, and the make_baseline_run_design_spec() factory.

Test organisation:
    TestEnvironmentConditionsSpec   — layer-1 resolution and override
    TestGovernanceArchitectureSpec  — layer-2 validation and workforce resolution
    TestOperatingPolicySpec         — layer-3 preset resolution, all three presets
    TestRunDesignSpec               — dataclass construction
    TestValidateRunDesign           — valid spec + all invalid branches
    TestResolveRunDesign            — happy path, field verification
    TestResolvedRunDesignSummary    — smoke test for summary()
    TestMakeBaselineRunDesignSpec   — factory shorthand
    TestPortfolioGuardrailsPassthrough — architecture guardrails appear in GovernanceConfig
    TestRunDesignSpecFromDict       — YAML dict parser
    TestMakePolicy                  — policy registry
"""

from __future__ import annotations

import pytest

from primordial_soup.campaign import WorkforceArchitectureSpec
from primordial_soup.config import (
    ModelConfig,
    ReportingConfig,
    TimeConfig,
    validate_configuration,
)
from primordial_soup.presets import make_baseline_model_config, make_baseline_time_config
from primordial_soup.types import RampShape
from primordial_soup.workbench import (
    EnvironmentConditionsSpec,
    GovernanceArchitectureSpec,
    OperatingPolicySpec,
    ResolvedRunDesign,
    RunDesignSpec,
    make_baseline_run_design_spec,
    make_policy,
    resolve_run_design,
    validate_run_design,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _baseline_workforce_spec(**overrides) -> WorkforceArchitectureSpec:
    """Canonical 24-team baseline workforce spec with optional overrides.

    24 mixed-size teams: 10×5 + 12×10 + 2×20 = 210 total labor.
    """
    defaults: dict = {
        "total_labor_endowment": 210,
        "team_count": 24,
        "team_sizes": (
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
        "ramp_period": 4,
        "ramp_multiplier_shape": RampShape.LINEAR,
    }
    defaults.update(overrides)
    return WorkforceArchitectureSpec(**defaults)


def _baseline_architecture(**overrides) -> GovernanceArchitectureSpec:
    return GovernanceArchitectureSpec(workforce=_baseline_workforce_spec(), **overrides)


def _minimal_spec(**overrides) -> RunDesignSpec:
    """Minimal valid RunDesignSpec suitable for most tests."""
    defaults = dict(
        name="test_run_v1",
        title="Test run",
        description="",
        environment=EnvironmentConditionsSpec(family="balanced_incumbent"),
        architecture=_baseline_architecture(),
        policy=OperatingPolicySpec(preset="balanced"),
        world_seeds=(42,),
    )
    defaults.update(overrides)
    return RunDesignSpec(**defaults)


# ---------------------------------------------------------------------------
# TestEnvironmentConditionsSpec
# ---------------------------------------------------------------------------


class TestEnvironmentConditionsSpec:
    def test_resolve_baseline_family(self):
        spec = EnvironmentConditionsSpec(family="balanced_incumbent")
        env = spec.resolve_environment_base()
        # initiative_generator is present with non-zero pool
        pool = sum(s.count for s in env.initiative_generator.type_specs)
        assert pool == 200

    def test_resolve_all_three_families(self):
        for family in ("balanced_incumbent", "short_cycle_throughput", "discovery_heavy"):
            spec = EnvironmentConditionsSpec(family=family)
            env = spec.resolve_environment_base()
            pool = sum(s.count for s in env.initiative_generator.type_specs)
            assert pool == 200, f"Family {family} should have 200 initiatives"

    def test_time_override_applied(self):
        custom_time = TimeConfig(tick_horizon=500, tick_label="day")
        spec = EnvironmentConditionsSpec(family="balanced_incumbent", time_override=custom_time)
        env = spec.resolve_environment_base()
        assert env.time.tick_horizon == 500
        assert env.time.tick_label == "day"

    def test_model_override_applied(self):
        custom_model = make_baseline_model_config()
        # Use dataclasses.replace to make a distinct model with different field
        import dataclasses

        custom_model = dataclasses.replace(custom_model, learning_rate=0.5)
        spec = EnvironmentConditionsSpec(family="balanced_incumbent", model_override=custom_model)
        env = spec.resolve_environment_base()
        assert env.model.learning_rate == 0.5

    def test_no_override_uses_preset_defaults(self):
        spec = EnvironmentConditionsSpec()
        env = spec.resolve_environment_base()
        baseline = make_baseline_time_config()
        assert env.time.tick_horizon == baseline.tick_horizon

    def test_resolve_returns_environment_spec(self):
        from primordial_soup.campaign import EnvironmentSpec

        spec = EnvironmentConditionsSpec()
        env = spec.resolve_environment_base()
        assert isinstance(env, EnvironmentSpec)


# ---------------------------------------------------------------------------
# TestGovernanceArchitectureSpec
# ---------------------------------------------------------------------------


class TestGovernanceArchitectureSpec:
    def test_resolve_workforce_baseline(self):
        arch = _baseline_architecture()
        wf = arch.resolve_workforce()
        assert wf.team_count == 24
        assert wf.total_labor_endowment == 210
        assert wf.ramp_period == 4

    def test_resolve_workforce_varied_sizes(self):
        arch = GovernanceArchitectureSpec(
            workforce=WorkforceArchitectureSpec(
                total_labor_endowment=10,
                team_count=3,
                team_sizes=(4, 3, 3),
                ramp_period=4,
            )
        )
        wf = arch.resolve_workforce()
        assert wf.team_count == 3
        assert wf.total_labor_endowment == 10

    def test_validate_no_errors_baseline(self):
        errors: list[str] = []
        _baseline_architecture().validate(errors)
        assert errors == []

    def test_validate_low_quality_threshold_out_of_range(self):
        errors: list[str] = []
        arch = _baseline_architecture(low_quality_belief_threshold=0.0)
        arch.validate(errors)
        assert any("low_quality_belief_threshold" in e for e in errors)

    def test_validate_low_quality_threshold_too_high(self):
        errors: list[str] = []
        arch = _baseline_architecture(low_quality_belief_threshold=1.0)
        arch.validate(errors)
        assert any("low_quality_belief_threshold" in e for e in errors)

    def test_validate_labor_share_cap_without_threshold(self):
        errors: list[str] = []
        arch = _baseline_architecture(
            low_quality_belief_threshold=None,
            max_low_quality_belief_labor_share=0.4,
        )
        arch.validate(errors)
        assert any("low_quality_belief_threshold is None" in e for e in errors)

    def test_validate_labor_share_out_of_range(self):
        errors: list[str] = []
        arch = _baseline_architecture(
            low_quality_belief_threshold=0.3,
            max_low_quality_belief_labor_share=1.5,
        )
        arch.validate(errors)
        assert any("max_low_quality_belief_labor_share" in e for e in errors)

    def test_validate_single_initiative_share_out_of_range(self):
        errors: list[str] = []
        arch = _baseline_architecture(max_single_initiative_labor_share=0.0)
        arch.validate(errors)
        assert any("max_single_initiative_labor_share" in e for e in errors)

    def test_validate_portfolio_guardrails_valid(self):
        errors: list[str] = []
        arch = _baseline_architecture(
            low_quality_belief_threshold=0.3,
            max_low_quality_belief_labor_share=0.5,
            max_single_initiative_labor_share=0.6,
        )
        arch.validate(errors)
        assert errors == []


# ---------------------------------------------------------------------------
# TestOperatingPolicySpec
# ---------------------------------------------------------------------------


class TestOperatingPolicySpec:
    @pytest.fixture
    def model(self) -> ModelConfig:
        return make_baseline_model_config()

    def test_balanced_preset(self, model):
        spec = OperatingPolicySpec(preset="balanced")
        gov = spec.resolve(model)
        assert gov.policy_id == "balanced"
        assert gov.confidence_decline_threshold is not None

    def test_aggressive_stop_loss_preset(self, model):
        spec = OperatingPolicySpec(preset="aggressive_stop_loss")
        gov = spec.resolve(model)
        assert gov.policy_id == "aggressive_stop_loss"
        # Aggressive has a higher (stricter) confidence decline threshold
        assert gov.confidence_decline_threshold is not None

    def test_patient_moonshot_preset(self, model):
        spec = OperatingPolicySpec(preset="patient_moonshot")
        gov = spec.resolve(model)
        assert gov.policy_id == "patient_moonshot"
        # Patient moonshot uses a very low confidence-decline threshold
        # (recalibrated from None to prevent paralysis, issue #18)
        assert gov.confidence_decline_threshold == 0.08

    def test_unknown_preset_raises(self, model):
        spec = OperatingPolicySpec(preset="nonexistent")  # type: ignore[arg-type]
        with pytest.raises(ValueError, match="Unknown policy preset"):
            spec.resolve(model)

    def test_model_fields_mirrored(self, model):
        spec = OperatingPolicySpec(preset="balanced")
        gov = spec.resolve(model)
        assert gov.exec_attention_budget == model.exec_attention_budget
        assert gov.default_initial_quality_belief == model.default_initial_quality_belief

    def test_preset_portfolio_fields_are_none(self, model):
        """Presets always set portfolio fields to None; architecture applies them later."""
        for preset in ("balanced", "aggressive_stop_loss", "patient_moonshot"):
            gov = OperatingPolicySpec(preset=preset).resolve(model)  # type: ignore[arg-type]
            assert gov.low_quality_belief_threshold is None
            assert gov.max_low_quality_belief_labor_share is None
            assert gov.max_single_initiative_labor_share is None


# ---------------------------------------------------------------------------
# TestRunDesignSpec
# ---------------------------------------------------------------------------


class TestRunDesignSpec:
    def test_construction(self):
        spec = _minimal_spec()
        assert spec.name == "test_run_v1"
        assert spec.world_seeds == (42,)
        assert spec.reporting is None

    def test_frozen(self):
        spec = _minimal_spec()
        with pytest.raises((AttributeError, TypeError)):
            spec.name = "mutated"  # type: ignore[misc]

    def test_multiple_seeds(self):
        spec = _minimal_spec(world_seeds=(1, 2, 3, 4))
        assert len(spec.world_seeds) == 4

    def test_custom_reporting(self):
        reporting = ReportingConfig(
            record_manifest=True,
            record_per_tick_logs=False,
            record_event_log=False,
        )
        spec = _minimal_spec(reporting=reporting)
        assert spec.reporting is not None
        assert not spec.reporting.record_per_tick_logs


# ---------------------------------------------------------------------------
# TestValidateRunDesign
# ---------------------------------------------------------------------------


class TestValidateRunDesign:
    def test_valid_baseline_passes(self):
        spec = _minimal_spec()
        validate_run_design(spec)  # should not raise

    def test_all_three_presets_pass(self):
        for preset in ("balanced", "aggressive_stop_loss", "patient_moonshot"):
            spec = _minimal_spec(policy=OperatingPolicySpec(preset=preset))  # type: ignore[arg-type]
            validate_run_design(spec)

    def test_all_three_families_pass(self):
        for family in ("balanced_incumbent", "short_cycle_throughput", "discovery_heavy"):
            spec = _minimal_spec(environment=EnvironmentConditionsSpec(family=family))
            validate_run_design(spec)

    def test_empty_name_fails(self):
        with pytest.raises(ValueError, match="name must not be empty"):
            validate_run_design(_minimal_spec(name=""))

    def test_name_with_spaces_fails(self):
        with pytest.raises(ValueError, match="name must not contain spaces"):
            validate_run_design(_minimal_spec(name="has spaces"))

    def test_empty_title_fails(self):
        with pytest.raises(ValueError, match="title must not be empty"):
            validate_run_design(_minimal_spec(title=""))

    def test_empty_world_seeds_fails(self):
        with pytest.raises(ValueError, match="world_seeds must not be empty"):
            validate_run_design(_minimal_spec(world_seeds=()))

    def test_architecture_invalid_portfolio_threshold_fails(self):
        bad_arch = _baseline_architecture(low_quality_belief_threshold=0.0)
        with pytest.raises(ValueError, match="low_quality_belief_threshold"):
            validate_run_design(_minimal_spec(architecture=bad_arch))

    def test_architecture_cap_without_threshold_fails(self):
        bad_arch = _baseline_architecture(
            max_low_quality_belief_labor_share=0.4,
            low_quality_belief_threshold=None,
        )
        with pytest.raises(ValueError, match="low_quality_belief_threshold is None"):
            validate_run_design(_minimal_spec(architecture=bad_arch))

    def test_invalid_workforce_fails(self):
        # non-divisible total_labor_endowment/team_count without team_sizes
        bad_wf = WorkforceArchitectureSpec(
            total_labor_endowment=7,
            team_count=3,
            ramp_period=4,
        )
        bad_arch = GovernanceArchitectureSpec(workforce=bad_wf)
        with pytest.raises(ValueError, match="[Ww]orkforce"):
            validate_run_design(_minimal_spec(architecture=bad_arch))

    def test_error_message_lists_all_issues(self):
        """Multiple validation errors should appear together in one ValueError."""
        with pytest.raises(ValueError) as exc_info:
            validate_run_design(_minimal_spec(name="", title="", world_seeds=()))
        msg = str(exc_info.value)
        assert "name" in msg
        assert "title" in msg
        assert "world_seeds" in msg

    def test_valid_portfolio_guardrails_pass(self):
        arch = _baseline_architecture(
            low_quality_belief_threshold=0.3,
            max_low_quality_belief_labor_share=0.5,
            max_single_initiative_labor_share=0.7,
        )
        spec = _minimal_spec(architecture=arch)
        validate_run_design(spec)  # should not raise


# ---------------------------------------------------------------------------
# TestResolveRunDesign
# ---------------------------------------------------------------------------


class TestResolveRunDesign:
    @pytest.fixture
    def resolved(self) -> ResolvedRunDesign:
        return resolve_run_design(_minimal_spec())

    def test_returns_resolved_run_design(self, resolved):
        assert isinstance(resolved, ResolvedRunDesign)

    def test_spec_provenance_preserved(self, resolved):
        assert resolved.spec.name == "test_run_v1"

    def test_workforce_matches_architecture(self, resolved):
        wf = resolved.workforce
        assert wf.team_count == 24
        assert wf.total_labor_endowment == 210

    def test_environment_spec_teams_is_architecture_workforce(self, resolved):
        """EnvironmentSpec.teams must be the architecture-resolved workforce."""
        env_teams = resolved.environment_spec.teams
        arch_wf = resolved.workforce
        assert env_teams.team_count == arch_wf.team_count
        assert env_teams.team_size == arch_wf.team_size

    def test_governance_policy_id(self, resolved):
        assert resolved.governance.policy_id == "balanced"

    def test_sim_configs_count_matches_seeds(self, resolved):
        assert len(resolved.simulation_configs) == 1

    def test_multiple_seeds_produce_multiple_configs(self):
        spec = _minimal_spec(world_seeds=(10, 20, 30))
        resolved = resolve_run_design(spec)
        assert len(resolved.simulation_configs) == 3

    def test_sim_config_seeds_match_spec(self):
        seeds = (100, 200, 300)
        spec = _minimal_spec(world_seeds=seeds)
        resolved = resolve_run_design(spec)
        actual_seeds = tuple(sc.world_seed for sc in resolved.simulation_configs)
        assert actual_seeds == seeds

    def test_sim_configs_pass_validate_configuration(self, resolved):
        """Every resolved SimulationConfiguration must pass the existing validator."""
        for sim_config in resolved.simulation_configs:
            validate_configuration(sim_config)  # should not raise

    def test_reporting_default_applied(self, resolved):
        """None reporting in spec → baseline reporting in sim configs."""
        assert resolved.spec.reporting is None
        for sim_config in resolved.simulation_configs:
            assert sim_config.reporting.record_manifest is True

    def test_custom_reporting_applied(self):
        reporting = ReportingConfig(
            record_manifest=False,
            record_per_tick_logs=False,
            record_event_log=True,
        )
        spec = _minimal_spec(reporting=reporting)
        resolved = resolve_run_design(spec)
        for sim_config in resolved.simulation_configs:
            assert sim_config.reporting.record_manifest is False

    def test_invalid_spec_raises_before_resolving(self):
        with pytest.raises(ValueError):
            resolve_run_design(_minimal_spec(name=""))

    def test_all_three_presets_resolve(self):
        for preset in ("balanced", "aggressive_stop_loss", "patient_moonshot"):
            spec = _minimal_spec(policy=OperatingPolicySpec(preset=preset))  # type: ignore[arg-type]
            resolved = resolve_run_design(spec)
            assert resolved.governance.policy_id == preset

    def test_environment_family_discovery_heavy(self):
        spec = _minimal_spec(environment=EnvironmentConditionsSpec(family="discovery_heavy"))
        resolved = resolve_run_design(spec)
        right_tail_specs = [
            s
            for s in resolved.environment_spec.initiative_generator.type_specs
            if s.generation_tag == "right_tail"
        ]
        assert len(right_tail_specs) == 1
        assert right_tail_specs[0].count == 56  # discovery_heavy has 56 right-tail

    def test_sim_config_has_initiative_generator_not_initiatives(self, resolved):
        """Generator path: initiative_generator set, initiatives is None."""
        for sc in resolved.simulation_configs:
            assert sc.initiative_generator is not None
            assert sc.initiatives is None

    def test_resolved_has_no_run_method(self, resolved):
        """run() was deliberately removed — workbench resolves, caller executes."""
        assert not hasattr(resolved, "run")


# ---------------------------------------------------------------------------
# TestResolvedRunDesignSummary
# ---------------------------------------------------------------------------


class TestResolvedRunDesignSummary:
    def test_summary_runs_without_error(self):
        resolved = resolve_run_design(_minimal_spec())
        text = resolved.summary()
        assert isinstance(text, str)
        assert len(text) > 0

    def test_summary_contains_name(self):
        resolved = resolve_run_design(_minimal_spec(name="my_design_v2"))
        assert "my_design_v2" in resolved.summary()

    def test_summary_contains_family(self):
        spec = _minimal_spec(
            environment=EnvironmentConditionsSpec(family="short_cycle_throughput")
        )
        resolved = resolve_run_design(spec)
        assert "short_cycle_throughput" in resolved.summary()

    def test_summary_contains_preset(self):
        for preset in ("balanced", "aggressive_stop_loss", "patient_moonshot"):
            spec = _minimal_spec(policy=OperatingPolicySpec(preset=preset))  # type: ignore[arg-type]
            assert preset in resolve_run_design(spec).summary()

    def test_summary_contains_world_seeds(self):
        spec = _minimal_spec(world_seeds=(99, 100, 101))
        assert "99" in resolve_run_design(spec).summary()

    def test_summary_shows_total_labor(self):
        resolved = resolve_run_design(_minimal_spec())
        # "210 total labor" from baseline 24-team mixed-size workforce
        assert "210 total labor" in resolved.summary()

    def test_summary_shows_no_guardrails(self):
        resolved = resolve_run_design(_minimal_spec())
        assert "no guardrails" in resolved.summary()

    def test_summary_shows_guardrails_when_set(self):
        arch = _baseline_architecture(
            low_quality_belief_threshold=0.3,
            max_low_quality_belief_labor_share=0.5,
        )
        spec = _minimal_spec(architecture=arch)
        resolved = resolve_run_design(spec)
        summary = resolved.summary()
        assert "low-quality threshold=0.3" in summary

    def test_summary_shows_low_confidence_decline_for_moonshot(self):
        """Patient moonshot summary shows its low confidence threshold."""
        spec = _minimal_spec(policy=OperatingPolicySpec(preset="patient_moonshot"))
        resolved = resolve_run_design(spec)
        # After issue #18 recalibration, threshold is 0.08 (not disabled).
        assert "threshold=0.08" in resolved.summary()


# ---------------------------------------------------------------------------
# TestMakeBaselineRunDesignSpec
# ---------------------------------------------------------------------------


class TestMakeBaselineRunDesignSpec:
    def test_factory_returns_valid_spec(self):
        spec = make_baseline_run_design_spec(name="factory_test", world_seeds=(1,))
        validate_run_design(spec)  # should not raise

    def test_factory_default_preset_is_balanced(self):
        spec = make_baseline_run_design_spec(name="x", world_seeds=(1,))
        assert spec.policy.preset == "balanced"

    def test_factory_default_family_is_balanced_incumbent(self):
        spec = make_baseline_run_design_spec(name="x", world_seeds=(1,))
        assert spec.environment.family == "balanced_incumbent"

    def test_factory_preset_override(self):
        spec = make_baseline_run_design_spec(
            name="x", policy_preset="patient_moonshot", world_seeds=(1,)
        )
        assert spec.policy.preset == "patient_moonshot"

    def test_factory_family_override(self):
        spec = make_baseline_run_design_spec(name="x", family="discovery_heavy", world_seeds=(1,))
        assert spec.environment.family == "discovery_heavy"

    def test_factory_resolves_cleanly(self):
        spec = make_baseline_run_design_spec(name="resolve_test", world_seeds=(42, 43))
        resolved = resolve_run_design(spec)
        assert len(resolved.simulation_configs) == 2

    def test_factory_auto_title_when_empty(self):
        spec = make_baseline_run_design_spec(name="x", world_seeds=(1,))
        assert spec.title  # should not be empty

    def test_factory_custom_title(self):
        spec = make_baseline_run_design_spec(name="x", title="My Study", world_seeds=(1,))
        assert spec.title == "My Study"

    def test_factory_workforce_defaults(self):
        spec = make_baseline_run_design_spec(name="x", world_seeds=(1,))
        wf = spec.architecture.workforce
        assert wf.total_labor_endowment == 210
        assert wf.team_count == 24
        assert wf.ramp_period == 4

    def test_factory_portfolio_guardrails(self):
        spec = make_baseline_run_design_spec(
            name="x",
            world_seeds=(1,),
            low_quality_belief_threshold=0.3,
            max_low_quality_belief_labor_share=0.5,
        )
        validate_run_design(spec)  # should not raise
        assert spec.architecture.low_quality_belief_threshold == 0.3
        assert spec.architecture.max_low_quality_belief_labor_share == 0.5


# ---------------------------------------------------------------------------
# TestPortfolioGuardrailsPassthrough
# ---------------------------------------------------------------------------


class TestPortfolioGuardrailsPassthrough:
    """Verify that architecture-level portfolio guardrails flow into GovernanceConfig."""

    def test_guardrails_appear_in_governance_config(self):
        arch = _baseline_architecture(
            low_quality_belief_threshold=0.25,
            max_low_quality_belief_labor_share=0.4,
            max_single_initiative_labor_share=0.6,
        )
        spec = _minimal_spec(architecture=arch)
        resolved = resolve_run_design(spec)
        gov = resolved.governance

        assert gov.low_quality_belief_threshold == 0.25
        assert gov.max_low_quality_belief_labor_share == 0.4
        assert gov.max_single_initiative_labor_share == 0.6

    def test_no_guardrails_means_none_in_governance(self):
        spec = _minimal_spec()  # no portfolio guardrails
        resolved = resolve_run_design(spec)
        gov = resolved.governance

        assert gov.low_quality_belief_threshold is None
        assert gov.max_low_quality_belief_labor_share is None
        assert gov.max_single_initiative_labor_share is None

    def test_guardrails_passed_through_all_three_presets(self):
        arch = _baseline_architecture(
            low_quality_belief_threshold=0.3,
            max_single_initiative_labor_share=0.5,
        )
        for preset in ("balanced", "aggressive_stop_loss", "patient_moonshot"):
            spec = _minimal_spec(
                architecture=arch,
                policy=OperatingPolicySpec(preset=preset),  # type: ignore[arg-type]
            )
            resolved = resolve_run_design(spec)
            assert resolved.governance.low_quality_belief_threshold == 0.3
            assert resolved.governance.max_single_initiative_labor_share == 0.5

    def test_guardrails_in_sim_config_governance(self):
        """Portfolio guardrails must be present in the SimulationConfiguration.governance."""
        arch = _baseline_architecture(low_quality_belief_threshold=0.2)
        spec = _minimal_spec(architecture=arch)
        resolved = resolve_run_design(spec)
        for sim_config in resolved.simulation_configs:
            assert sim_config.governance.low_quality_belief_threshold == 0.2


# ---------------------------------------------------------------------------
# TestRunDesignSpecFromDict
# ---------------------------------------------------------------------------


class TestRunDesignSpecFromDict:
    """Tests for RunDesignSpec.from_dict() — the repo-owned YAML parser."""

    def _minimal_dict(self, **overrides) -> dict:
        base = {
            "name": "test_from_dict",
            "title": "From dict test",
            "description": "",
            "environment": {"family": "balanced_incumbent"},
            "architecture": {
                "total_labor_endowment": 8,
                "team_count": 8,
                "ramp_period": 4,
                "ramp_shape": "linear",
            },
            "policy": {"preset": "balanced"},
            "world_seeds": [42],
        }
        base.update(overrides)
        return base

    def test_minimal_dict_produces_valid_spec(self):
        spec = RunDesignSpec.from_dict(self._minimal_dict())
        validate_run_design(spec)  # should not raise

    def test_metadata_fields(self):
        spec = RunDesignSpec.from_dict(
            self._minimal_dict(name="my_run", title="My Title", description="My desc")
        )
        assert spec.name == "my_run"
        assert spec.title == "My Title"
        assert spec.description == "My desc"

    def test_environment_family(self):
        for family in ("balanced_incumbent", "short_cycle_throughput", "discovery_heavy"):
            d = self._minimal_dict()
            d["environment"]["family"] = family
            spec = RunDesignSpec.from_dict(d)
            assert spec.environment.family == family

    def test_all_three_policy_presets(self):
        for preset in ("balanced", "aggressive_stop_loss", "patient_moonshot"):
            d = self._minimal_dict()
            d["policy"]["preset"] = preset
            spec = RunDesignSpec.from_dict(d)
            assert spec.policy.preset == preset

    def test_world_seeds_list(self):
        d = self._minimal_dict(world_seeds=[10, 20, 30])
        spec = RunDesignSpec.from_dict(d)
        assert spec.world_seeds == (10, 20, 30)

    def test_world_seeds_single_int(self):
        d = self._minimal_dict(world_seeds=99)
        spec = RunDesignSpec.from_dict(d)
        assert spec.world_seeds == (99,)

    def test_architecture_team_sizes_list(self):
        d = self._minimal_dict()
        d["architecture"]["team_sizes"] = [4, 2, 2]
        d["architecture"]["total_labor_endowment"] = 8
        d["architecture"]["team_count"] = 3
        spec = RunDesignSpec.from_dict(d)
        assert spec.architecture.workforce.team_sizes == (4, 2, 2)

    def test_architecture_portfolio_guardrails(self):
        d = self._minimal_dict()
        d["architecture"]["low_quality_belief_threshold"] = 0.3
        d["architecture"]["max_low_quality_belief_labor_share"] = 0.5
        d["architecture"]["max_single_initiative_labor_share"] = 0.6
        spec = RunDesignSpec.from_dict(d)
        assert spec.architecture.low_quality_belief_threshold == 0.3
        assert spec.architecture.max_low_quality_belief_labor_share == 0.5
        assert spec.architecture.max_single_initiative_labor_share == 0.6

    def test_null_guardrails_become_none(self):
        d = self._minimal_dict()
        d["architecture"]["low_quality_belief_threshold"] = None
        spec = RunDesignSpec.from_dict(d)
        assert spec.architecture.low_quality_belief_threshold is None

    def test_ramp_shape_linear(self):
        from primordial_soup.types import RampShape

        spec = RunDesignSpec.from_dict(self._minimal_dict())
        assert spec.architecture.workforce.ramp_multiplier_shape == RampShape.LINEAR

    def test_unknown_ramp_shape_raises(self):
        d = self._minimal_dict()
        d["architecture"]["ramp_shape"] = "exponential"
        with pytest.raises(ValueError, match="ramp_shape"):
            RunDesignSpec.from_dict(d)

    def test_reporting_override(self):
        d = self._minimal_dict()
        d["reporting"] = {
            "record_manifest": True,
            "record_per_tick_logs": False,
            "record_event_log": False,
        }
        spec = RunDesignSpec.from_dict(d)
        assert spec.reporting is not None
        assert not spec.reporting.record_per_tick_logs

    def test_no_reporting_key_means_none(self):
        spec = RunDesignSpec.from_dict(self._minimal_dict())
        assert spec.reporting is None

    def test_time_override(self):
        d = self._minimal_dict()
        d["environment"]["time"] = {"tick_horizon": 500, "tick_label": "day"}
        spec = RunDesignSpec.from_dict(d)
        assert spec.environment.time_override is not None
        assert spec.environment.time_override.tick_horizon == 500
        assert spec.environment.time_override.tick_label == "day"

    def test_missing_environment_uses_defaults(self):
        d = self._minimal_dict()
        del d["environment"]
        spec = RunDesignSpec.from_dict(d)
        assert spec.environment.family == "balanced_incumbent"

    def test_from_dict_then_resolve(self):
        """Full round-trip: dict → spec → validate → resolve → sim_configs."""
        spec = RunDesignSpec.from_dict(self._minimal_dict(world_seeds=[42, 43]))
        resolved = resolve_run_design(spec)
        assert len(resolved.simulation_configs) == 2


# ---------------------------------------------------------------------------
# TestMakePolicy
# ---------------------------------------------------------------------------


class TestMakePolicy:
    """Tests for make_policy() — the repo-owned policy registry."""

    @pytest.fixture
    def balanced_governance(self):
        from primordial_soup.presets import (
            make_balanced_governance_config,
            make_baseline_model_config,
        )

        m = make_baseline_model_config()
        return make_balanced_governance_config(
            exec_attention_budget=m.exec_attention_budget,
            default_initial_quality_belief=m.default_initial_quality_belief,
        )

    def test_balanced_policy_id(self, balanced_governance):
        policy = make_policy(balanced_governance)
        assert policy is not None

    def test_all_three_presets_return_policy(self):
        from primordial_soup.presets import (
            make_aggressive_stop_loss_governance_config,
            make_balanced_governance_config,
            make_baseline_model_config,
            make_patient_moonshot_governance_config,
        )

        m = make_baseline_model_config()
        kwargs = dict(
            exec_attention_budget=m.exec_attention_budget,
            default_initial_quality_belief=m.default_initial_quality_belief,
        )
        for factory in (
            make_balanced_governance_config,
            make_aggressive_stop_loss_governance_config,
            make_patient_moonshot_governance_config,
        ):
            gov = factory(**kwargs)
            policy = make_policy(gov)
            assert policy is not None

    def test_unknown_policy_id_raises(self):
        import dataclasses

        from primordial_soup.presets import (
            make_balanced_governance_config,
            make_baseline_model_config,
        )

        m = make_baseline_model_config()
        gov = make_balanced_governance_config(
            exec_attention_budget=m.exec_attention_budget,
            default_initial_quality_belief=m.default_initial_quality_belief,
        )
        bad_gov = dataclasses.replace(gov, policy_id="nonexistent_preset")
        with pytest.raises(ValueError, match="policy_id"):
            make_policy(bad_gov)


# ---------------------------------------------------------------------------
# TestEnvironmentOverrides
# ---------------------------------------------------------------------------


class TestEnvironmentOverrides:
    """Tests for conductor-facing environment overrides (Step 4.1).

    Verifies that staffing response, frontier, and opportunity supply
    overrides are correctly parsed, validated, and applied to the
    resolved InitiativeGeneratorConfig.
    """

    # ── Staffing response overrides ──────────────────────────────────

    def test_staffing_response_override_applied(self):
        """Per-family staffing response ranges should appear in the resolved
        InitiativeTypeSpec."""
        spec = _minimal_spec(
            environment=EnvironmentConditionsSpec(
                family="balanced_incumbent",
                staffing_response_overrides=(
                    ("flywheel", (0.3, 0.8)),
                    ("right_tail", (0.8, 2.0)),
                ),
            ),
        )
        resolved = resolve_run_design(spec)
        gen = resolved.environment_spec.initiative_generator
        for type_spec in gen.type_specs:
            if type_spec.generation_tag == "flywheel":
                assert type_spec.staffing_response_scale_range == (0.3, 0.8)
            elif type_spec.generation_tag == "right_tail":
                assert type_spec.staffing_response_scale_range == (0.8, 2.0)
            else:
                # Families without override keep preset default (None).
                assert type_spec.staffing_response_scale_range is None

    def test_staffing_response_none_preserves_defaults(self):
        """When staffing_response_overrides is None, all families keep defaults."""
        spec = _minimal_spec()
        resolved = resolve_run_design(spec)
        gen = resolved.environment_spec.initiative_generator
        for type_spec in gen.type_specs:
            assert type_spec.staffing_response_scale_range is None

    def test_staffing_response_bad_family_rejected(self):
        """Unknown generation_tag in staffing_response should fail validation."""
        spec = _minimal_spec(
            environment=EnvironmentConditionsSpec(
                staffing_response_overrides=(("nonexistent_family", (0.1, 0.5)),),
            ),
        )
        with pytest.raises(ValueError, match="nonexistent_family"):
            validate_run_design(spec)

    def test_staffing_response_negative_range_rejected(self):
        """Negative staffing response scale should fail validation."""
        spec = _minimal_spec(
            environment=EnvironmentConditionsSpec(
                staffing_response_overrides=(("flywheel", (-0.1, 0.5)),),
            ),
        )
        with pytest.raises(ValueError, match="staffing_response"):
            validate_run_design(spec)

    def test_staffing_response_inverted_range_rejected(self):
        """Min > max in staffing response range should fail validation."""
        spec = _minimal_spec(
            environment=EnvironmentConditionsSpec(
                staffing_response_overrides=(("flywheel", (0.8, 0.3)),),
            ),
        )
        with pytest.raises(ValueError, match="staffing_response"):
            validate_run_design(spec)

    # ── Portfolio mix count overrides (exec_intent_spec.md #5) ───────
    # Each bucket's count is independently overridable; unset buckets keep
    # the family default; total pool size is a derived quantity.

    def test_right_tail_prize_count_override(self):
        """Overriding right-tail count should only change the right-tail bucket."""
        spec = _minimal_spec(
            environment=EnvironmentConditionsSpec(
                family="balanced_incumbent",
                right_tail_prize_count=50,
            ),
        )
        resolved = resolve_run_design(spec)
        gen = resolved.environment_spec.initiative_generator
        rt = [s for s in gen.type_specs if s.generation_tag == "right_tail"][0]
        qw = [s for s in gen.type_specs if s.generation_tag == "quick_win"][0]
        # balanced_incumbent defaults: flywheel=70, enabler=30, right_tail=20, quick_win=80.
        # With right_tail=50 and no other override, quick_win stays at its default 80.
        # Total pool grows to 230 (within the [50, 400] envelope).
        assert rt.count == 50
        assert qw.count == 80
        total = sum(s.count for s in gen.type_specs)
        assert total == 230

    def test_all_bucket_counts_override(self):
        """All four bucket counts can be set independently."""
        spec = _minimal_spec(
            environment=EnvironmentConditionsSpec(
                family="balanced_incumbent",
                right_tail_prize_count=15,
                flywheel_count=60,
                enabler_count=25,
                quick_win_count=90,
            ),
        )
        resolved = resolve_run_design(spec)
        gen = resolved.environment_spec.initiative_generator
        counts = {s.generation_tag: s.count for s in gen.type_specs}
        assert counts["right_tail"] == 15
        assert counts["flywheel"] == 60
        assert counts["enabler"] == 25
        assert counts["quick_win"] == 90
        # Total pool is the straight sum — no hidden rebalance.
        assert sum(counts.values()) == 190

    def test_bucket_count_negative_rejected(self):
        """A negative bucket count must fail validation."""
        spec = _minimal_spec(
            environment=EnvironmentConditionsSpec(flywheel_count=-1),
        )
        with pytest.raises(ValueError, match="flywheel_count must be >= 0"):
            validate_run_design(spec)

    def test_pool_size_below_envelope_rejected(self):
        """A resolved pool below 50 should fail the spec envelope check."""
        # Set all four counts small to force the resolved pool under 50.
        spec = _minimal_spec(
            environment=EnvironmentConditionsSpec(
                flywheel_count=5,
                enabler_count=5,
                quick_win_count=5,
                right_tail_prize_count=5,
            ),
        )
        with pytest.raises(ValueError, match=r"\[50, 400\]"):
            validate_run_design(spec)

    def test_pool_size_above_envelope_rejected(self):
        """A resolved pool above 400 should fail the spec envelope check."""
        spec = _minimal_spec(
            environment=EnvironmentConditionsSpec(
                flywheel_count=200,
                enabler_count=200,
                quick_win_count=200,
                right_tail_prize_count=100,
            ),
        )
        with pytest.raises(ValueError, match=r"\[50, 400\]"):
            validate_run_design(spec)

    def test_right_tail_prize_count_zero_allowed(self):
        """right_tail_prize_count=0 should pass — no right-tail opportunities."""
        # No right-tail bucket means no major-win discovery, which is a
        # legitimate (if constrained) experimental condition. Other buckets
        # stay at family defaults so the pool is still ~180.
        spec = _minimal_spec(
            environment=EnvironmentConditionsSpec(right_tail_prize_count=0),
        )
        resolved = resolve_run_design(spec)
        gen = resolved.environment_spec.initiative_generator
        rt = [s for s in gen.type_specs if s.generation_tag == "right_tail"][0]
        assert rt.count == 0

    # ── Frontier degradation rate overrides ───────────────────────────

    def test_frontier_degradation_rate_override(self):
        """Per-family frontier degradation rate should be applied."""
        spec = _minimal_spec(
            environment=EnvironmentConditionsSpec(
                family="balanced_incumbent",
                frontier_degradation_rate_overrides=(
                    ("flywheel", 0.05),
                    ("quick_win", 0.10),
                ),
            ),
        )
        resolved = resolve_run_design(spec)
        gen = resolved.environment_spec.initiative_generator
        for type_spec in gen.type_specs:
            if type_spec.generation_tag == "flywheel":
                assert type_spec.frontier is not None
                assert type_spec.frontier.frontier_degradation_rate == 0.05
            elif type_spec.generation_tag == "quick_win":
                assert type_spec.frontier is not None
                assert type_spec.frontier.frontier_degradation_rate == 0.10
            elif type_spec.generation_tag == "enabler":
                # Not overridden — should keep preset default (0.005).
                assert type_spec.frontier is not None
                assert type_spec.frontier.frontier_degradation_rate == 0.005

    def test_frontier_degradation_negative_rejected(self):
        """Negative frontier degradation rate should fail validation."""
        spec = _minimal_spec(
            environment=EnvironmentConditionsSpec(
                frontier_degradation_rate_overrides=(("flywheel", -0.01),),
            ),
        )
        with pytest.raises(ValueError, match="frontier_degradation_rate"):
            validate_run_design(spec)

    def test_frontier_degradation_unknown_family_rejected(self):
        """Unknown generation_tag should fail validation."""
        spec = _minimal_spec(
            environment=EnvironmentConditionsSpec(
                frontier_degradation_rate_overrides=(("nonexistent", 0.01),),
            ),
        )
        with pytest.raises(ValueError, match="nonexistent"):
            validate_run_design(spec)

    # ── Right-tail refresh degradation ───────────────────────────────

    def test_right_tail_refresh_degradation_override(self):
        """Right-tail refresh degradation should be applied to right-tail spec."""
        spec = _minimal_spec(
            environment=EnvironmentConditionsSpec(
                family="balanced_incumbent",
                right_tail_refresh_degradation=0.05,
            ),
        )
        resolved = resolve_run_design(spec)
        gen = resolved.environment_spec.initiative_generator
        rt = [s for s in gen.type_specs if s.generation_tag == "right_tail"][0]
        assert rt.frontier is not None
        assert rt.frontier.right_tail_refresh_quality_degradation == 0.05
        # Non-right-tail families should be unaffected.
        fw = [s for s in gen.type_specs if s.generation_tag == "flywheel"][0]
        assert fw.frontier is not None
        assert fw.frontier.right_tail_refresh_quality_degradation == 0.0

    def test_right_tail_refresh_degradation_negative_rejected(self):
        """Negative right-tail refresh degradation should fail validation."""
        spec = _minimal_spec(
            environment=EnvironmentConditionsSpec(
                right_tail_refresh_degradation=-0.01,
            ),
        )
        with pytest.raises(ValueError, match="right_tail_refresh_degradation"):
            validate_run_design(spec)

    # ── Combined overrides ───────────────────────────────────────────

    def test_all_overrides_combined(self):
        """All four override types should work together."""
        spec = _minimal_spec(
            environment=EnvironmentConditionsSpec(
                family="balanced_incumbent",
                staffing_response_overrides=(("right_tail", (0.5, 1.5)),),
                right_tail_prize_count=50,
                frontier_degradation_rate_overrides=(("flywheel", 0.03),),
                right_tail_refresh_degradation=0.02,
            ),
        )
        resolved = resolve_run_design(spec)
        gen = resolved.environment_spec.initiative_generator

        rt = [s for s in gen.type_specs if s.generation_tag == "right_tail"][0]
        assert rt.count == 50
        assert rt.staffing_response_scale_range == (0.5, 1.5)
        assert rt.frontier is not None
        assert rt.frontier.right_tail_refresh_quality_degradation == 0.02

        fw = [s for s in gen.type_specs if s.generation_tag == "flywheel"][0]
        assert fw.frontier is not None
        assert fw.frontier.frontier_degradation_rate == 0.03

        # No auto-rebalance — total pool is (flywheel 70 + enabler 30 +
        # quick_win 80 + right_tail 50) = 230, within the [50, 400] envelope.
        total = sum(s.count for s in gen.type_specs)
        assert total == 230

    def test_summary_shows_overrides(self):
        """summary() should mention active overrides."""
        spec = _minimal_spec(
            environment=EnvironmentConditionsSpec(
                staffing_response_overrides=(("flywheel", (0.3, 0.8)),),
                right_tail_prize_count=50,
                frontier_degradation_rate_overrides=(("flywheel", 0.05),),
                right_tail_refresh_degradation=0.02,
            ),
        )
        resolved = resolve_run_design(spec)
        text = resolved.summary()
        assert "Staffing response" in text
        assert "Right-tail prize count" in text
        assert "Frontier degradation" in text
        assert "Right-tail refresh degradation" in text


# ---------------------------------------------------------------------------
# TestEnvironmentOverridesFromDict
# ---------------------------------------------------------------------------


class TestEnvironmentOverridesFromDict:
    """Tests for YAML dict parsing of environment overrides."""

    def _minimal_dict(self, **overrides) -> dict:
        base = {
            "name": "test_overrides",
            "title": "Override test",
            "description": "",
            "environment": {"family": "balanced_incumbent"},
            "architecture": {
                "total_labor_endowment": 8,
                "team_count": 8,
                "ramp_period": 4,
                "ramp_shape": "linear",
            },
            "policy": {"preset": "balanced"},
            "world_seeds": [42],
        }
        base.update(overrides)
        return base

    def test_staffing_response_from_dict(self):
        d = self._minimal_dict()
        d["environment"]["staffing_response"] = {
            "flywheel": [0.3, 0.8],
            "right_tail": [0.8, 2.0],
        }
        spec = RunDesignSpec.from_dict(d)
        assert spec.environment.staffing_response_overrides is not None
        sr_dict = dict(spec.environment.staffing_response_overrides)
        assert sr_dict["flywheel"] == (0.3, 0.8)
        assert sr_dict["right_tail"] == (0.8, 2.0)

    def test_opportunity_supply_from_dict(self):
        d = self._minimal_dict()
        d["environment"]["opportunity_supply"] = {
            "right_tail_prize_count": 50,
            "frontier_degradation_rate": {
                "flywheel": 0.05,
                "quick_win": 0.10,
            },
            "right_tail_refresh_degradation": 0.02,
        }
        spec = RunDesignSpec.from_dict(d)
        assert spec.environment.right_tail_prize_count == 50
        assert spec.environment.frontier_degradation_rate_overrides is not None
        fd_dict = dict(spec.environment.frontier_degradation_rate_overrides)
        assert fd_dict["flywheel"] == 0.05
        assert fd_dict["quick_win"] == 0.10
        assert spec.environment.right_tail_refresh_degradation == 0.02

    def test_no_overrides_means_none(self):
        d = self._minimal_dict()
        spec = RunDesignSpec.from_dict(d)
        assert spec.environment.staffing_response_overrides is None
        assert spec.environment.right_tail_prize_count is None
        assert spec.environment.frontier_degradation_rate_overrides is None
        assert spec.environment.right_tail_refresh_degradation is None

    def test_overrides_round_trip_resolve(self):
        """Parse overrides from dict, then resolve to sim configs."""
        d = self._minimal_dict()
        d["environment"]["staffing_response"] = {"flywheel": [0.3, 0.8]}
        d["environment"]["opportunity_supply"] = {
            "right_tail_prize_count": 50,
        }
        spec = RunDesignSpec.from_dict(d)
        resolved = resolve_run_design(spec)
        gen = resolved.environment_spec.initiative_generator
        fw = [s for s in gen.type_specs if s.generation_tag == "flywheel"][0]
        assert fw.staffing_response_scale_range == (0.3, 0.8)
        rt = [s for s in gen.type_specs if s.generation_tag == "right_tail"][0]
        assert rt.count == 50

    def test_partial_supply_overrides(self):
        """Only some supply fields set; others remain None."""
        d = self._minimal_dict()
        d["environment"]["opportunity_supply"] = {
            "right_tail_prize_count": 30,
        }
        spec = RunDesignSpec.from_dict(d)
        assert spec.environment.right_tail_prize_count == 30
        assert spec.environment.frontier_degradation_rate_overrides is None
        assert spec.environment.right_tail_refresh_degradation is None


# ---------------------------------------------------------------------------
# TestExecIntentFields — Phase 1 exec input surface (2026-04-18)
# ---------------------------------------------------------------------------
#
# Coverage for the three new exec-facing authoring-surface concerns from
# exec_intent_spec.md:
#   - value_unit (#8)  — top-level report-layer label
#   - architecture.baseline_value_per_team_week (#7) — translates 1:1
#       into ModelConfig.baseline_value_per_tick
#   - environment.opportunity_supply.{flywheel,enabler,quick_win}_count (#5)
#       — per-bucket portfolio mix counts, independent of each other


class TestValueUnitField:
    """value_unit top-level field (exec_intent_spec.md #8)."""

    def test_default_is_units(self):
        """RunDesignSpec without an explicit value_unit should default to 'units'."""
        spec = _minimal_spec()
        assert spec.value_unit == "units"

    def test_dataclass_accepts_custom_label(self):
        """Free-text labels (e.g. '$M', 'pts') are permitted verbatim."""
        spec = _minimal_spec(value_unit="$M")
        assert spec.value_unit == "$M"

    def test_from_dict_parses_value_unit(self):
        """value_unit top-level YAML key should round-trip into the spec."""
        d = {
            "name": "vu_test",
            "title": "Value unit test",
            "description": "",
            "value_unit": "€M",
            "environment": {"family": "balanced_incumbent"},
            "architecture": {
                "total_labor_endowment": 8,
                "team_count": 8,
                "ramp_period": 4,
                "ramp_shape": "linear",
            },
            "policy": {"preset": "balanced"},
            "world_seeds": [42],
        }
        spec = RunDesignSpec.from_dict(d)
        assert spec.value_unit == "€M"

    def test_from_dict_empty_value_unit_falls_back_to_units(self):
        """An empty-string value_unit should fall back to the 'units' default."""
        d = {
            "name": "vu_test",
            "title": "Value unit test",
            "description": "",
            "value_unit": "",
            "environment": {"family": "balanced_incumbent"},
            "architecture": {
                "total_labor_endowment": 8,
                "team_count": 8,
                "ramp_period": 4,
                "ramp_shape": "linear",
            },
            "policy": {"preset": "balanced"},
            "world_seeds": [42],
        }
        spec = RunDesignSpec.from_dict(d)
        assert spec.value_unit == "units"

    def test_summary_shows_value_unit(self):
        """summary() should include the value_unit under the Execution block."""
        spec = _minimal_spec(value_unit="$M")
        resolved = resolve_run_design(spec)
        text = resolved.summary()
        assert "Value unit" in text
        assert "$M" in text

    def test_value_unit_threads_into_experiment_spec(self):
        """build_experiment_spec_from_design should propagate value_unit."""
        # Import locally to avoid circular import at module top.
        from primordial_soup.policy import BalancedPolicy
        from primordial_soup.runner import run_single_regime
        from primordial_soup.workbench import build_experiment_spec_from_design

        spec = _minimal_spec(value_unit="$M")
        resolved = resolve_run_design(spec)
        # One seed run is enough to build a valid ExperimentSpec.
        sim_config = resolved.simulation_configs[0]
        run_result, world_state = run_single_regime(sim_config, BalancedPolicy())
        experiment_spec = build_experiment_spec_from_design(
            resolved,
            ((run_result, world_state),),
        )
        assert experiment_spec.value_unit == "$M"


class TestBaselineValuePerTeamWeek:
    """architecture.baseline_value_per_team_week (exec_intent_spec.md #7)."""

    def test_default_is_none(self):
        """Unset field should leave the model's baseline_value_per_tick untouched."""
        spec = _minimal_spec()
        assert spec.architecture.baseline_value_per_team_week is None
        resolved = resolve_run_design(spec)
        # Family default for model.baseline_value_per_tick is 0.0.
        assert resolved.environment_spec.model.baseline_value_per_tick == 0.0

    def test_override_relabels_into_model(self):
        """Setting baseline_value_per_team_week should set baseline_value_per_tick 1:1."""
        # 1 tick = 1 week and ModelConfig.baseline_value_per_tick is already
        # per-idle-team per-tick, so the authoring-surface number maps
        # directly into the engine field with no arithmetic.
        spec = _minimal_spec(
            architecture=_baseline_architecture(baseline_value_per_team_week=0.25),
        )
        resolved = resolve_run_design(spec)
        assert resolved.environment_spec.model.baseline_value_per_tick == 0.25
        # Every SimulationConfiguration inherits the override.
        for sim in resolved.simulation_configs:
            assert sim.model.baseline_value_per_tick == 0.25

    def test_zero_is_allowed(self):
        """Zero is a legitimate choice (no baseline accrual)."""
        spec = _minimal_spec(
            architecture=_baseline_architecture(baseline_value_per_team_week=0.0),
        )
        resolved = resolve_run_design(spec)
        assert resolved.environment_spec.model.baseline_value_per_tick == 0.0

    def test_negative_rejected(self):
        """A negative baseline value must fail validation."""
        spec = _minimal_spec(
            architecture=_baseline_architecture(baseline_value_per_team_week=-0.1),
        )
        with pytest.raises(ValueError, match="baseline_value_per_team_week"):
            validate_run_design(spec)

    def test_from_dict_parses_baseline_value(self):
        """YAML architecture.baseline_value_per_team_week should parse."""
        d = {
            "name": "bv_test",
            "title": "Baseline value test",
            "description": "",
            "environment": {"family": "balanced_incumbent"},
            "architecture": {
                "total_labor_endowment": 8,
                "team_count": 8,
                "ramp_period": 4,
                "ramp_shape": "linear",
                "baseline_value_per_team_week": 0.1,
            },
            "policy": {"preset": "balanced"},
            "world_seeds": [42],
        }
        spec = RunDesignSpec.from_dict(d)
        assert spec.architecture.baseline_value_per_team_week == 0.1
        resolved = resolve_run_design(spec)
        assert resolved.environment_spec.model.baseline_value_per_tick == 0.1

    def test_summary_shows_baseline_value_with_unit(self):
        """summary() should display the baseline rate with the value_unit label."""
        spec = _minimal_spec(
            value_unit="$M",
            architecture=_baseline_architecture(baseline_value_per_team_week=0.1),
        )
        resolved = resolve_run_design(spec)
        text = resolved.summary()
        assert "Baseline value" in text
        assert "0.1" in text
        assert "$M" in text


class TestPortfolioMixCountsFromDict:
    """Per-bucket portfolio mix count parsing from YAML (exec_intent_spec.md #5)."""

    def _minimal_dict(self, **overrides) -> dict:
        base = {
            "name": "mix_test",
            "title": "Mix test",
            "description": "",
            "environment": {"family": "balanced_incumbent"},
            "architecture": {
                "total_labor_endowment": 8,
                "team_count": 8,
                "ramp_period": 4,
                "ramp_shape": "linear",
            },
            "policy": {"preset": "balanced"},
            "world_seeds": [42],
        }
        base.update(overrides)
        return base

    def test_all_four_counts_from_dict(self):
        """All four counts should round-trip through the YAML dict parser."""
        d = self._minimal_dict()
        d["environment"]["opportunity_supply"] = {
            "right_tail_prize_count": 20,
            "flywheel_count": 70,
            "enabler_count": 30,
            "quick_win_count": 80,
        }
        spec = RunDesignSpec.from_dict(d)
        assert spec.environment.right_tail_prize_count == 20
        assert spec.environment.flywheel_count == 70
        assert spec.environment.enabler_count == 30
        assert spec.environment.quick_win_count == 80

    def test_only_quick_win_count_override(self):
        """Unset buckets should remain None after parsing."""
        d = self._minimal_dict()
        d["environment"]["opportunity_supply"] = {"quick_win_count": 50}
        spec = RunDesignSpec.from_dict(d)
        assert spec.environment.quick_win_count == 50
        assert spec.environment.flywheel_count is None
        assert spec.environment.enabler_count is None
        assert spec.environment.right_tail_prize_count is None

    def test_counts_resolve_to_initiative_type_specs(self):
        """Parsed counts should land on the right InitiativeTypeSpec entries."""
        d = self._minimal_dict()
        d["environment"]["opportunity_supply"] = {
            "flywheel_count": 60,
            "enabler_count": 25,
            "quick_win_count": 90,
            "right_tail_prize_count": 15,
        }
        spec = RunDesignSpec.from_dict(d)
        resolved = resolve_run_design(spec)
        counts = {
            s.generation_tag: s.count
            for s in resolved.environment_spec.initiative_generator.type_specs
        }
        assert counts == {
            "flywheel": 60,
            "enabler": 25,
            "quick_win": 90,
            "right_tail": 15,
        }


class TestPresetYAMLRoundTrip:
    """Smoke test: every preset YAML parses, validates, and carries value_unit."""

    def test_balanced_incumbent_balanced_preset_has_value_unit(self, tmp_path):
        """The canonical balanced preset should load with value_unit='units'."""
        from pathlib import Path

        import yaml

        preset_path = (
            Path(__file__).parent.parent
            / "templates"
            / "presets"
            / "balanced_incumbent_balanced.yaml"
        )
        data = yaml.safe_load(preset_path.read_text(encoding="utf-8"))
        spec = RunDesignSpec.from_dict(data)
        assert spec.value_unit == "units"
        # Full resolve must succeed — presets are the canonical entry points.
        resolve_run_design(spec)
