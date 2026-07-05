"""Drift guard between tools/run_designer.html and the workbench YAML schema.

The run designer page is a static HTML form that emits run-design YAML.
Its serializer is hand-written JavaScript, so nothing in the Python type
system ties it to RunDesignSpec.from_dict() — these fixtures are that tie.

Two committed fixtures under tests/fixtures/ are snapshots of the page's
output:

    run_designer_default.yaml      — every control left at its default.
                                     Must resolve identically to the
                                     canonical baseline template.
    run_designer_all_options.yaml  — every optional block enabled. Every
                                     YAML key the page can emit appears
                                     here exactly once.

If RunDesignSpec.from_dict() changes shape (a key is renamed, moved, or
re-typed), the assertions here fail — the signal to update both the
fixtures and tools/run_designer.html together.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from primordial_soup.workbench import (
    RunDesignSpec,
    resolve_run_design,
    validate_run_design,
)

# Repo-relative locations. tests/ sits at the repo root beside templates/.
REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
TEMPLATE_PATH = REPO_ROOT / "templates" / "run_design_template.yaml"


def _load_spec(path: Path) -> RunDesignSpec:
    """Parse a YAML file into a RunDesignSpec via the repo-owned parser."""
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return RunDesignSpec.from_dict(data)


# ---------------------------------------------------------------------------
# Default-output fixture: must match the canonical baseline template.
# ---------------------------------------------------------------------------


class TestDefaultFixture:
    def test_default_fixture_validates(self) -> None:
        spec = _load_spec(FIXTURES_DIR / "run_designer_default.yaml")
        validate_run_design(spec)  # raises ValueError on any issue

    def test_default_fixture_resolves_identically_to_template(self) -> None:
        # The designer's untouched defaults are the canonical baseline, and
        # the template file itself is a valid design with those same values.
        # Comparing resolved summaries covers every layer (environment pool,
        # workforce, governance parameters, seeds) in one assertion.
        fixture_resolved = resolve_run_design(
            _load_spec(FIXTURES_DIR / "run_designer_default.yaml")
        )
        template_resolved = resolve_run_design(_load_spec(TEMPLATE_PATH))
        assert fixture_resolved.summary() == template_resolved.summary()


# ---------------------------------------------------------------------------
# All-options fixture: every optional key parses into the intended field.
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def all_options_spec() -> RunDesignSpec:
    return _load_spec(FIXTURES_DIR / "run_designer_all_options.yaml")


class TestAllOptionsParsing:
    """from_dict() consumes every designer-emitted key into the right field."""

    def test_metadata(self, all_options_spec: RunDesignSpec) -> None:
        assert all_options_spec.name == "designer_all_options"
        assert all_options_spec.value_unit == "$M"

    def test_time_override(self, all_options_spec: RunDesignSpec) -> None:
        assert all_options_spec.environment.time_override is not None
        assert all_options_spec.environment.time_override.tick_horizon == 200
        assert all_options_spec.environment.time_override.tick_label == "week"

    def test_staffing_response_overrides(self, all_options_spec: RunDesignSpec) -> None:
        overrides = dict(all_options_spec.environment.staffing_response_overrides)
        assert overrides["flywheel"] == pytest.approx((0.3, 0.8))
        assert overrides["right_tail"] == pytest.approx((0.8, 2.0))
        assert set(overrides) == {"flywheel", "right_tail"}

    def test_opportunity_supply_counts(self, all_options_spec: RunDesignSpec) -> None:
        env = all_options_spec.environment
        assert env.right_tail_prize_count == 50
        assert env.flywheel_count == 40
        assert env.enabler_count == 30
        assert env.quick_win_count == 60

    def test_frontier_settings(self, all_options_spec: RunDesignSpec) -> None:
        env = all_options_spec.environment
        rates = dict(env.frontier_degradation_rate_overrides)
        assert rates["flywheel"] == pytest.approx(0.01)
        assert rates["quick_win"] == pytest.approx(0.02)
        assert env.right_tail_refresh_degradation == pytest.approx(0.10)

    def test_model_override(self, all_options_spec: RunDesignSpec) -> None:
        model = all_options_spec.environment.model_override
        assert model is not None
        assert model.exec_attention_budget == pytest.approx(30.0)
        assert model.attention_noise_scale == pytest.approx(1.3)
        assert model.attention_noise_decay == pytest.approx(1.5)
        # The designer emits "~" for the canonical L(d) = 1 - d formula.
        assert model.dependency_learning_scale is None
        assert model.capability_decay == pytest.approx(0.005)

    def test_architecture_guardrails(self, all_options_spec: RunDesignSpec) -> None:
        arch = all_options_spec.architecture
        assert arch.low_quality_belief_threshold == pytest.approx(0.3)
        assert arch.max_low_quality_belief_labor_share == pytest.approx(0.4)
        assert arch.max_single_initiative_labor_share == pytest.approx(0.5)

    def test_portfolio_mix_targets(self, all_options_spec: RunDesignSpec) -> None:
        # The designer emits the structured form: targets + tolerance.
        mix = all_options_spec.architecture.portfolio_mix_targets
        assert mix is not None
        targets = dict(mix.bucket_targets)
        assert targets == {
            "flywheel": pytest.approx(0.40),
            "quick_win": pytest.approx(0.35),
            "enabler": pytest.approx(0.15),
            "right_tail": pytest.approx(0.10),
        }
        assert mix.tolerance == pytest.approx(0.10)

    def test_baseline_value(self, all_options_spec: RunDesignSpec) -> None:
        assert all_options_spec.architecture.baseline_value_per_team_week == pytest.approx(0.1)

    def test_policy_and_seeds(self, all_options_spec: RunDesignSpec) -> None:
        assert all_options_spec.policy.preset == "patient_moonshot"
        assert all_options_spec.world_seeds == (42, 43)

    def test_reporting_override(self, all_options_spec: RunDesignSpec) -> None:
        assert all_options_spec.reporting is not None
        assert all_options_spec.reporting.record_manifest is True
        assert all_options_spec.reporting.record_per_tick_logs is True
        assert all_options_spec.reporting.record_event_log is False


class TestAllOptionsResolution:
    """The fixture survives full validation and resolves as intended."""

    def test_validates(self, all_options_spec: RunDesignSpec) -> None:
        validate_run_design(all_options_spec)

    def test_resolved_pool_counts_apply_overrides(self, all_options_spec: RunDesignSpec) -> None:
        resolved = resolve_run_design(all_options_spec)
        counts = {
            spec.generation_tag: spec.count
            for spec in resolved.environment_spec.initiative_generator.type_specs
        }
        assert counts == {
            "right_tail": 50,
            "flywheel": 40,
            "enabler": 30,
            "quick_win": 60,
        }

    def test_resolved_horizon_and_seeds(self, all_options_spec: RunDesignSpec) -> None:
        resolved = resolve_run_design(all_options_spec)
        assert resolved.environment_spec.time.tick_horizon == 200
        assert len(resolved.simulation_configs) == 2

    def test_resolved_workforce(self, all_options_spec: RunDesignSpec) -> None:
        resolved = resolve_run_design(all_options_spec)
        assert resolved.workforce.total_labor_endowment == 210
        assert resolved.workforce.team_count == 21

    def test_resolved_governance_carries_guardrails_and_mix(
        self, all_options_spec: RunDesignSpec
    ) -> None:
        resolved = resolve_run_design(all_options_spec)
        gov = resolved.governance
        assert gov.policy_id == "patient_moonshot"
        assert gov.low_quality_belief_threshold == pytest.approx(0.3)
        # Architecture-level mix targets override the preset's calibrated mix.
        assert dict(gov.portfolio_mix_targets.bucket_targets)["right_tail"] == pytest.approx(0.10)

    def test_resolved_baseline_value_reaches_model(self, all_options_spec: RunDesignSpec) -> None:
        # baseline_value_per_team_week maps 1:1 onto the engine's
        # ModelConfig.baseline_value_per_tick (1 tick = 1 week).
        resolved = resolve_run_design(all_options_spec)
        assert resolved.environment_spec.model.baseline_value_per_tick == pytest.approx(0.1)
