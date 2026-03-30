"""Tests for the business intent translation layer.

Covers:
- Registry loading and structural validation
- Unknown intent detection
- Conflict detection between intents
- Environment intent translation
- Operating policy intent translation
- Workforce shape intent translation
- Guardrail intent translation
- Portfolio mix target intent translation
- End-to-end RunDesignSpec construction from intents
- PortfolioMixTargets validation in the workbench
- Initiative bucket classification (generation_tag-based)
- Portfolio mix computation
- Policy soft re-ranking under mix targets
"""

from __future__ import annotations

import pytest

from primordial_soup.business_intent import (
    BusinessIntentRequest,
    build_run_design_from_intents,
    load_business_intent_registry,
    translate_business_intents,
)
from primordial_soup.config import (
    CANONICAL_BUCKET_NAMES,
    GovernanceConfig,
    PortfolioMixTargets,
)
from primordial_soup.governance import (
    classify_initiative_bucket,
    compute_current_portfolio_mix,
)
from primordial_soup.observation import (
    GovernanceObservation,
    InitiativeObservation,
    PortfolioSummary,
    TeamObservation,
)
from primordial_soup.workbench import (
    GovernanceArchitectureSpec,
    resolve_run_design,
    validate_run_design,
)

# ============================================================================
# Helpers
# ============================================================================


def _make_initiative_obs(
    *,
    initiative_id: str = "I-1",
    lifecycle_state: str = "unassigned",
    assigned_team_id: str | None = None,
    quality_belief_t: float = 0.5,
    observable_ceiling: float | None = None,
    required_team_size: int = 1,
    effective_tam_patience_window: int | None = None,
    execution_belief_t: float | None = None,
    implied_duration_ticks: int | None = None,
    planned_duration_ticks: int | None = None,
    progress_fraction: float | None = None,
    review_count: int = 0,
    staffed_tick_count: int = 0,
    consecutive_reviews_below_tam_ratio: int = 0,
    capability_contribution_scale: float = 0.0,
    generation_tag: str | None = None,
) -> InitiativeObservation:
    """Build an InitiativeObservation with sensible defaults."""
    return InitiativeObservation(
        initiative_id=initiative_id,
        lifecycle_state=lifecycle_state,
        assigned_team_id=assigned_team_id,
        quality_belief_t=quality_belief_t,
        observable_ceiling=observable_ceiling,
        required_team_size=required_team_size,
        effective_tam_patience_window=effective_tam_patience_window,
        execution_belief_t=execution_belief_t,
        implied_duration_ticks=implied_duration_ticks,
        planned_duration_ticks=planned_duration_ticks,
        progress_fraction=progress_fraction,
        review_count=review_count,
        staffed_tick_count=staffed_tick_count,
        consecutive_reviews_below_tam_ratio=consecutive_reviews_below_tam_ratio,
        capability_contribution_scale=capability_contribution_scale,
        generation_tag=generation_tag,
    )


# ============================================================================
# Registry loading
# ============================================================================


class TestRegistryLoading:
    """Tests for registry loading and structural validation."""

    def test_loads_canonical_registry(self) -> None:
        """The canonical registry YAML loads and passes validation."""
        registry = load_business_intent_registry()
        assert registry["version"] == 1
        assert "bucket_definitions" in registry
        assert "intents" in registry
        assert "conflicts" in registry

    def test_canonical_buckets_present(self) -> None:
        """All four canonical buckets are defined in the registry."""
        registry = load_business_intent_registry()
        bucket_defs = registry["bucket_definitions"]
        for bucket in CANONICAL_BUCKET_NAMES:
            assert bucket in bucket_defs, f"Missing bucket: {bucket}"

    def test_all_intents_have_required_fields(self) -> None:
        """Every intent in the registry has a layer and translation."""
        registry = load_business_intent_registry()
        for intent_id, intent_def in registry["intents"].items():
            assert "layer" in intent_def, f"Intent {intent_id!r} missing 'layer'"
            assert "translation" in intent_def, f"Intent {intent_id!r} missing 'translation'"

    def test_invalid_registry_missing_sections(self, tmp_path) -> None:
        """Registry with missing sections raises ValueError."""
        bad_yaml = tmp_path / "bad_registry.yaml"
        bad_yaml.write_text("version: 1\n")
        with pytest.raises(ValueError, match="missing"):
            load_business_intent_registry(bad_yaml)


# ============================================================================
# Unknown intent detection
# ============================================================================


class TestUnknownIntents:
    """Tests for unknown intent error handling."""

    def test_unknown_intent_raises(self) -> None:
        """Requesting an unknown intent raises ValueError."""
        with pytest.raises(ValueError, match="Unknown intent"):
            translate_business_intents((BusinessIntentRequest("totally_fake_intent"),))

    def test_unknown_intent_lists_known(self) -> None:
        """Error message lists known intents for discoverability."""
        with pytest.raises(ValueError, match="Known intents"):
            translate_business_intents((BusinessIntentRequest("nonexistent"),))


# ============================================================================
# Conflict detection
# ============================================================================


class TestConflictDetection:
    """Tests for conflict detection between intents."""

    def test_patient_vs_aggressive_conflicts(self) -> None:
        """Patient and aggressive stop-loss are conflicting intents."""
        with pytest.raises(ValueError, match="patient.*aggressive|aggressive.*patient"):
            translate_business_intents(
                (
                    BusinessIntentRequest("patient_governance"),
                    BusinessIntentRequest("aggressive_stop_loss"),
                )
            )

    def test_two_explicit_environments_conflict(self) -> None:
        """Two explicit environment family choices conflict."""
        with pytest.raises(ValueError, match="environment famil"):
            translate_business_intents(
                (
                    BusinessIntentRequest("balanced_baseline_world"),
                    BusinessIntentRequest("discovery_heavy_world"),
                )
            )

    def test_non_conflicting_intents_pass(self) -> None:
        """Non-conflicting intents from different layers succeed."""
        result = translate_business_intents(
            (
                BusinessIntentRequest("discovery_heavy_world"),
                BusinessIntentRequest("patient_governance"),
            )
        )
        assert result.environment_family == "discovery_heavy"
        assert result.policy_preset == "patient_moonshot"


# ============================================================================
# Layer-specific translation
# ============================================================================


class TestEnvironmentIntents:
    """Tests for environment-layer intent translation."""

    def test_environment_family_choice(self) -> None:
        """An explicit family choice resolves to that family."""
        result = translate_business_intents((BusinessIntentRequest("balanced_baseline_world"),))
        assert result.environment_family == "balanced_incumbent"

    def test_environment_family_bias(self) -> None:
        """A family bias intent resolves to the preferred family."""
        result = translate_business_intents((BusinessIntentRequest("more_right_tail"),))
        assert result.environment_family == "discovery_heavy"

    def test_shorter_cycle_world(self) -> None:
        """Shorter-cycle intent resolves to short_cycle_throughput."""
        result = translate_business_intents((BusinessIntentRequest("shorter_cycle_world"),))
        assert result.environment_family == "short_cycle_throughput"


class TestPolicyIntents:
    """Tests for operating-policy-layer intent translation."""

    def test_patient_governance(self) -> None:
        """Patient governance resolves to patient_moonshot preset."""
        result = translate_business_intents((BusinessIntentRequest("patient_governance"),))
        assert result.policy_preset == "patient_moonshot"

    def test_aggressive_stop_loss(self) -> None:
        """Aggressive stop-loss resolves to aggressive_stop_loss preset."""
        result = translate_business_intents((BusinessIntentRequest("aggressive_stop_loss"),))
        assert result.policy_preset == "aggressive_stop_loss"

    def test_balanced_governance(self) -> None:
        """Balanced governance resolves to balanced preset."""
        result = translate_business_intents((BusinessIntentRequest("balanced_governance"),))
        assert result.policy_preset == "balanced"


class TestWorkforceIntents:
    """Tests for governance-architecture workforce intents."""

    def test_fewer_larger_teams(self) -> None:
        """Workforce shape intent resolves team count and labor."""
        result = translate_business_intents(
            (
                BusinessIntentRequest(
                    "fewer_larger_teams",
                    parameters={
                        "team_count": 4,
                        "total_labor_endowment": 8,
                    },
                ),
            )
        )
        assert result.workforce_team_count == 4
        assert result.workforce_total_labor_endowment == 8

    def test_workforce_intent_missing_params(self) -> None:
        """Workforce intent without required parameters raises."""
        with pytest.raises(ValueError, match="requires parameters"):
            translate_business_intents((BusinessIntentRequest("fewer_larger_teams"),))


class TestGuardrailIntents:
    """Tests for governance-architecture guardrail intents."""

    def test_concentration_cap(self) -> None:
        """Concentration cap intent sets max_single_initiative_labor_share."""
        result = translate_business_intents(
            (
                BusinessIntentRequest(
                    "concentration_cap",
                    parameters={"max_single_initiative_labor_share": 0.4},
                ),
            )
        )
        assert result.max_single_initiative_labor_share == pytest.approx(0.4)

    def test_concentration_cap_missing_param(self) -> None:
        """Concentration cap without the parameter raises."""
        with pytest.raises(ValueError, match="requires parameter"):
            translate_business_intents((BusinessIntentRequest("concentration_cap"),))

    def test_low_confidence_exposure_cap(self) -> None:
        """Low-confidence exposure cap sets both threshold and share."""
        result = translate_business_intents(
            (
                BusinessIntentRequest(
                    "low_confidence_exposure_cap",
                    parameters={
                        "low_quality_belief_threshold": 0.3,
                        "max_low_quality_belief_labor_share": 0.25,
                    },
                ),
            )
        )
        assert result.low_quality_belief_threshold == pytest.approx(0.3)
        assert result.max_low_quality_belief_labor_share == pytest.approx(0.25)


# ============================================================================
# Portfolio mix targets
# ============================================================================


class TestPortfolioMixTargetIntents:
    """Tests for portfolio mix target intent translation."""

    def test_basic_mix_targets(self) -> None:
        """Mix target intent produces PortfolioMixTargets."""
        result = translate_business_intents(
            (
                BusinessIntentRequest(
                    "portfolio_mix_targets",
                    parameters={
                        "targets": {
                            "flywheel": 0.40,
                            "right_tail": 0.20,
                            "enabler": 0.30,
                            "quick_win": 0.10,
                        },
                    },
                ),
            )
        )
        assert result.portfolio_mix_targets is not None
        pmt = result.portfolio_mix_targets
        targets = pmt.targets_dict
        assert targets["flywheel"] == pytest.approx(0.40)
        assert targets["right_tail"] == pytest.approx(0.20)
        assert targets["enabler"] == pytest.approx(0.30)
        assert targets["quick_win"] == pytest.approx(0.10)

    def test_mix_targets_default_tolerance(self) -> None:
        """Mix targets use the registry default tolerance (0.10)."""
        result = translate_business_intents(
            (
                BusinessIntentRequest(
                    "portfolio_mix_targets",
                    parameters={
                        "targets": {
                            "flywheel": 0.50,
                            "right_tail": 0.50,
                        },
                    },
                ),
            )
        )
        assert result.portfolio_mix_targets is not None
        assert result.portfolio_mix_targets.tolerance == pytest.approx(0.10)

    def test_mix_targets_custom_tolerance(self) -> None:
        """Mix targets accept an explicit tolerance parameter."""
        result = translate_business_intents(
            (
                BusinessIntentRequest(
                    "portfolio_mix_targets",
                    parameters={
                        "targets": {"flywheel": 1.0},
                        "tolerance": 0.05,
                    },
                ),
            )
        )
        assert result.portfolio_mix_targets is not None
        assert result.portfolio_mix_targets.tolerance == pytest.approx(0.05)

    def test_mix_targets_missing_targets_param(self) -> None:
        """Mix target intent without targets parameter raises."""
        with pytest.raises(ValueError, match="requires parameter.*targets"):
            translate_business_intents((BusinessIntentRequest("portfolio_mix_targets"),))

    def test_mix_targets_unknown_bucket(self) -> None:
        """Mix targets with an unknown bucket name raises."""
        with pytest.raises(ValueError, match="unknown bucket"):
            translate_business_intents(
                (
                    BusinessIntentRequest(
                        "portfolio_mix_targets",
                        parameters={
                            "targets": {"nonexistent_bucket": 1.0},
                        },
                    ),
                )
            )


# ============================================================================
# PortfolioMixTargets type
# ============================================================================


class TestPortfolioMixTargetsType:
    """Tests for the PortfolioMixTargets dataclass."""

    def test_targets_dict_property(self) -> None:
        """targets_dict returns a proper dict for lookup."""
        pmt = PortfolioMixTargets(
            bucket_targets=(
                ("flywheel", 0.5),
                ("enabler", 0.5),
            ),
        )
        d = pmt.targets_dict
        assert d["flywheel"] == pytest.approx(0.5)
        assert d["enabler"] == pytest.approx(0.5)

    def test_default_tolerance(self) -> None:
        """Default tolerance is 0.10."""
        pmt = PortfolioMixTargets(bucket_targets=(("flywheel", 1.0),))
        assert pmt.tolerance == pytest.approx(0.10)


# ============================================================================
# Workbench validation of mix targets
# ============================================================================


class TestWorkbenchMixTargetValidation:
    """Tests for mix target validation in GovernanceArchitectureSpec."""

    def _make_arch(
        self,
        mix_targets: PortfolioMixTargets | None = None,
    ) -> GovernanceArchitectureSpec:
        """Build a GovernanceArchitectureSpec with mix targets."""
        from primordial_soup.campaign import WorkforceArchitectureSpec

        return GovernanceArchitectureSpec(
            workforce=WorkforceArchitectureSpec(
                total_labor_endowment=8,
                team_count=8,
                ramp_period=4,
            ),
            portfolio_mix_targets=mix_targets,
        )

    def test_valid_mix_targets_pass_validation(self) -> None:
        """Valid mix targets pass architecture validation."""
        pmt = PortfolioMixTargets(
            bucket_targets=(
                ("flywheel", 0.40),
                ("right_tail", 0.20),
                ("enabler", 0.30),
                ("quick_win", 0.10),
            ),
        )
        arch = self._make_arch(pmt)
        errors: list[str] = []
        arch.validate(errors)
        assert not errors

    def test_unknown_bucket_name_fails(self) -> None:
        """Unknown bucket names are caught by validation."""
        pmt = PortfolioMixTargets(
            bucket_targets=(("unknown_type", 1.0),),
        )
        arch = self._make_arch(pmt)
        errors: list[str] = []
        arch.validate(errors)
        assert any("unknown bucket" in e for e in errors)

    def test_negative_share_fails(self) -> None:
        """Negative target shares are caught by validation."""
        pmt = PortfolioMixTargets(
            bucket_targets=(("flywheel", -0.1), ("enabler", 1.1)),
        )
        arch = self._make_arch(pmt)
        errors: list[str] = []
        arch.validate(errors)
        assert any("must be >= 0" in e for e in errors)

    def test_shares_not_summing_to_one_fails(self) -> None:
        """Target shares that don't sum to 1.0 are caught."""
        pmt = PortfolioMixTargets(
            bucket_targets=(("flywheel", 0.5), ("enabler", 0.3)),
        )
        arch = self._make_arch(pmt)
        errors: list[str] = []
        arch.validate(errors)
        assert any("sum to 1.0" in e for e in errors)

    def test_invalid_tolerance_fails(self) -> None:
        """Tolerance outside [0, 1] is caught by validation."""
        pmt = PortfolioMixTargets(
            bucket_targets=(("flywheel", 1.0),),
            tolerance=1.5,
        )
        arch = self._make_arch(pmt)
        errors: list[str] = []
        arch.validate(errors)
        assert any("tolerance" in e for e in errors)


# ============================================================================
# Initiative bucket classification
# ============================================================================


class TestBucketClassification:
    """Tests for classify_initiative_bucket() generation_tag-based rules.

    The classifier uses InitiativeObservation.generation_tag as the single
    source of truth for bucket identity. This is the key design property:
    classification is determined by the tag set at pool generation, not
    by heuristic inference from observable attributes.
    """

    def test_flywheel_tag(self) -> None:
        """generation_tag='flywheel' classifies as flywheel."""
        init = _make_initiative_obs(generation_tag="flywheel")
        assert classify_initiative_bucket(init) == "flywheel"

    def test_right_tail_tag(self) -> None:
        """generation_tag='right_tail' classifies as right_tail."""
        init = _make_initiative_obs(generation_tag="right_tail")
        assert classify_initiative_bucket(init) == "right_tail"

    def test_enabler_tag(self) -> None:
        """generation_tag='enabler' classifies as enabler."""
        init = _make_initiative_obs(generation_tag="enabler")
        assert classify_initiative_bucket(init) == "enabler"

    def test_quick_win_tag(self) -> None:
        """generation_tag='quick_win' classifies as quick_win."""
        init = _make_initiative_obs(generation_tag="quick_win")
        assert classify_initiative_bucket(init) == "quick_win"

    def test_none_tag_returns_uncategorized(self) -> None:
        """generation_tag=None returns 'uncategorized'."""
        init = _make_initiative_obs(generation_tag=None)
        assert classify_initiative_bucket(init) == "uncategorized"

    def test_unknown_tag_returns_uncategorized(self) -> None:
        """A non-canonical generation_tag returns 'uncategorized'."""
        init = _make_initiative_obs(generation_tag="infrastructure")
        assert classify_initiative_bucket(init) == "uncategorized"

    def test_tag_is_sole_source_of_truth(self) -> None:
        """Observable attributes do not override generation_tag.

        An initiative tagged 'flywheel' but with observable_ceiling set
        (which would have been 'right_tail' under the old heuristic)
        is still classified as 'flywheel'. The tag is authoritative.
        """
        init = _make_initiative_obs(
            generation_tag="flywheel",
            observable_ceiling=50.0,
        )
        assert classify_initiative_bucket(init) == "flywheel"

    def test_all_canonical_buckets_recognized(self) -> None:
        """Every canonical bucket name is recognized by the classifier."""
        for bucket in CANONICAL_BUCKET_NAMES:
            init = _make_initiative_obs(generation_tag=bucket)
            assert classify_initiative_bucket(init) == bucket


# ============================================================================
# Portfolio mix computation
# ============================================================================


class TestPortfolioMixComputation:
    """Tests for compute_current_portfolio_mix()."""

    def test_empty_portfolio(self) -> None:
        """Empty portfolio returns empty dict."""
        result = compute_current_portfolio_mix((), set())
        assert result == {}

    def test_single_bucket(self) -> None:
        """Single active initiative gives 100% in its bucket."""
        init = _make_initiative_obs(
            initiative_id="I-1",
            lifecycle_state="active",
            assigned_team_id="T-1",
            generation_tag="flywheel",
        )
        result = compute_current_portfolio_mix((init,), set())
        assert result == {"flywheel": pytest.approx(1.0)}

    def test_excludes_stopped_initiatives(self) -> None:
        """Stopped initiatives are excluded from the mix."""
        flywheel = _make_initiative_obs(
            initiative_id="I-1",
            lifecycle_state="active",
            assigned_team_id="T-1",
            generation_tag="flywheel",
        )
        enabler = _make_initiative_obs(
            initiative_id="I-2",
            lifecycle_state="active",
            assigned_team_id="T-2",
            generation_tag="enabler",
        )
        result = compute_current_portfolio_mix((flywheel, enabler), stopped_ids={"I-2"})
        assert result == {"flywheel": pytest.approx(1.0)}

    def test_multiple_buckets(self) -> None:
        """Multiple buckets compute correct labor shares."""
        inits = (
            _make_initiative_obs(
                initiative_id="I-1",
                lifecycle_state="active",
                assigned_team_id="T-1",
                generation_tag="flywheel",
            ),
            _make_initiative_obs(
                initiative_id="I-2",
                lifecycle_state="active",
                assigned_team_id="T-2",
                generation_tag="right_tail",
            ),
            _make_initiative_obs(
                initiative_id="I-3",
                lifecycle_state="active",
                assigned_team_id="T-3",
                generation_tag="right_tail",
            ),
        )
        result = compute_current_portfolio_mix(inits, set())
        assert result["flywheel"] == pytest.approx(1 / 3)
        assert result["right_tail"] == pytest.approx(2 / 3)


# ============================================================================
# End-to-end RunDesignSpec construction from intents
# ============================================================================


class TestBuildRunDesignFromIntents:
    """Tests for build_run_design_from_intents()."""

    def test_no_intents_uses_defaults(self) -> None:
        """Empty intents produce baseline defaults."""
        spec = build_run_design_from_intents(
            name="test_baseline",
            intents=(),
            title="Test baseline",
        )
        assert spec.environment.family == "balanced_incumbent"
        assert spec.policy.preset == "balanced"
        assert spec.architecture.portfolio_mix_targets is None

    def test_environment_intent_overrides_family(self) -> None:
        """Environment intent overrides the base family."""
        spec = build_run_design_from_intents(
            name="test_discovery",
            intents=(BusinessIntentRequest("discovery_heavy_world"),),
            title="Test discovery",
        )
        assert spec.environment.family == "discovery_heavy"

    def test_policy_intent_overrides_preset(self) -> None:
        """Policy intent overrides the base preset."""
        spec = build_run_design_from_intents(
            name="test_patient",
            intents=(BusinessIntentRequest("patient_governance"),),
            title="Test patient",
        )
        assert spec.policy.preset == "patient_moonshot"

    def test_mix_targets_flow_through(self) -> None:
        """Portfolio mix targets from intents reach the architecture."""
        spec = build_run_design_from_intents(
            name="test_mix",
            intents=(
                BusinessIntentRequest(
                    "portfolio_mix_targets",
                    parameters={
                        "targets": {
                            "flywheel": 0.40,
                            "right_tail": 0.20,
                            "enabler": 0.30,
                            "quick_win": 0.10,
                        },
                    },
                ),
            ),
            title="Test mix targets",
        )
        pmt = spec.architecture.portfolio_mix_targets
        assert pmt is not None
        assert pmt.targets_dict["flywheel"] == pytest.approx(0.40)

    def test_combined_intents(self) -> None:
        """Multiple intents from different layers compose correctly."""
        spec = build_run_design_from_intents(
            name="test_combined",
            intents=(
                BusinessIntentRequest("discovery_heavy_world"),
                BusinessIntentRequest("patient_governance"),
                BusinessIntentRequest(
                    "concentration_cap",
                    parameters={"max_single_initiative_labor_share": 0.5},
                ),
            ),
            title="Combined test",
        )
        assert spec.environment.family == "discovery_heavy"
        assert spec.policy.preset == "patient_moonshot"
        assert spec.architecture.max_single_initiative_labor_share == pytest.approx(0.5)

    def test_result_validates_and_resolves(self) -> None:
        """RunDesignSpec from intents passes validation and resolution."""
        spec = build_run_design_from_intents(
            name="test_e2e",
            intents=(
                BusinessIntentRequest("balanced_governance"),
                BusinessIntentRequest(
                    "portfolio_mix_targets",
                    parameters={
                        "targets": {
                            "flywheel": 0.40,
                            "right_tail": 0.20,
                            "enabler": 0.30,
                            "quick_win": 0.10,
                        },
                    },
                ),
            ),
            title="End-to-end test",
            world_seeds=(42,),
        )
        # Should not raise.
        validate_run_design(spec)
        resolved = resolve_run_design(spec)

        # Mix targets flow through to GovernanceConfig.
        assert resolved.governance.portfolio_mix_targets is not None
        targets = resolved.governance.portfolio_mix_targets.targets_dict
        assert targets["flywheel"] == pytest.approx(0.40)

        # Summary should mention mix targets.
        summary = resolved.summary()
        assert "Mix targets" in summary
        assert "flywheel" in summary


# ============================================================================
# YAML round-trip (mix targets in RunDesignSpec.from_dict)
# ============================================================================


class TestYamlMixTargets:
    """Tests for portfolio_mix_targets in RunDesignSpec.from_dict()."""

    def test_flat_form_parsing(self) -> None:
        """Flat YAML form {bucket: share} parses correctly."""
        from primordial_soup.workbench import RunDesignSpec

        data = {
            "name": "test_yaml",
            "title": "YAML test",
            "description": "",
            "environment": {"family": "balanced_incumbent"},
            "architecture": {
                "total_labor_endowment": 8,
                "team_count": 8,
                "portfolio_mix_targets": {
                    "flywheel": 0.40,
                    "right_tail": 0.20,
                    "enabler": 0.30,
                    "quick_win": 0.10,
                },
            },
            "policy": {"preset": "balanced"},
            "world_seeds": [42],
        }
        spec = RunDesignSpec.from_dict(data)
        pmt = spec.architecture.portfolio_mix_targets
        assert pmt is not None
        assert pmt.targets_dict["flywheel"] == pytest.approx(0.40)
        assert pmt.tolerance == pytest.approx(0.10)

    def test_structured_form_parsing(self) -> None:
        """Structured YAML form with targets/tolerance parses correctly."""
        from primordial_soup.workbench import RunDesignSpec

        data = {
            "name": "test_structured",
            "title": "Structured test",
            "description": "",
            "environment": {"family": "balanced_incumbent"},
            "architecture": {
                "total_labor_endowment": 8,
                "team_count": 8,
                "portfolio_mix_targets": {
                    "targets": {
                        "flywheel": 0.50,
                        "enabler": 0.50,
                    },
                    "tolerance": 0.05,
                },
            },
            "policy": {"preset": "balanced"},
            "world_seeds": [42],
        }
        spec = RunDesignSpec.from_dict(data)
        pmt = spec.architecture.portfolio_mix_targets
        assert pmt is not None
        assert pmt.tolerance == pytest.approx(0.05)

    def test_no_mix_targets_in_yaml(self) -> None:
        """Omitting portfolio_mix_targets from YAML gives None."""
        from primordial_soup.workbench import RunDesignSpec

        data = {
            "name": "test_none",
            "title": "No mix",
            "description": "",
            "environment": {"family": "balanced_incumbent"},
            "architecture": {
                "total_labor_endowment": 8,
                "team_count": 8,
            },
            "policy": {"preset": "balanced"},
            "world_seeds": [42],
        }
        spec = RunDesignSpec.from_dict(data)
        assert spec.architecture.portfolio_mix_targets is None


# ============================================================================
# Integration tests: full path from intent → resolve → policy → bucket vocab
# ============================================================================


class TestFullPathIntegration:
    """Integration tests proving the complete pipeline.

    These tests verify the full path:
      1. Business intent (or YAML) specifies mix targets
      2. Workbench resolves them into GovernanceConfig
      3. Policy uses generation_tag via classify_initiative_bucket
      4. Portfolio mix computation uses the same bucket vocabulary

    This is the end-to-end proof that bucket classification is
    generation_tag-driven at every layer, with a single vocabulary.
    """

    def test_intent_to_resolve_to_policy_classification(self) -> None:
        """Full path: intent → resolve → classify matches bucket vocabulary.

        Proves that the bucket names used in mix targets (authored via
        business intent) are the same names that classify_initiative_bucket
        returns at runtime from generation_tag.
        """
        # Step 1: Author mix targets via business intent.
        spec = build_run_design_from_intents(
            name="test_full_path",
            intents=(
                BusinessIntentRequest(
                    "portfolio_mix_targets",
                    parameters={
                        "targets": {
                            "flywheel": 0.40,
                            "right_tail": 0.20,
                            "enabler": 0.30,
                            "quick_win": 0.10,
                        },
                    },
                ),
            ),
            title="Full path integration test",
            world_seeds=(42,),
        )

        # Step 2: Resolve through the workbench.
        resolved = resolve_run_design(spec)
        gov = resolved.governance
        assert gov.portfolio_mix_targets is not None
        target_buckets = set(gov.portfolio_mix_targets.targets_dict.keys())

        # Step 3: Classify initiatives using generation_tag — same vocab.
        for tag in ("flywheel", "right_tail", "enabler", "quick_win"):
            init = _make_initiative_obs(generation_tag=tag)
            classified = classify_initiative_bucket(init)
            assert classified == tag, (
                f"classify_initiative_bucket returned {classified!r} for "
                f"generation_tag={tag!r}"
            )
            assert classified in target_buckets, (
                f"Classified bucket {classified!r} is not in target vocabulary "
                f"{target_buckets}"
            )

    def test_policy_reranking_uses_generation_tag(self) -> None:
        """Policy re-ranking is driven by generation_tag, not observable attrs.

        Constructs a scenario where mix targets want more enablers, and
        two unassigned candidates differ only in generation_tag. Proves
        the enabler-tagged candidate is promoted ahead of the flywheel.
        """
        from primordial_soup.policy import _rerank_for_mix_targets

        # Mix targets: heavily favor enablers (80%) over flywheels (20%).
        pmt = PortfolioMixTargets(
            bucket_targets=(
                ("flywheel", 0.20),
                ("enabler", 0.80),
            ),
            tolerance=0.05,
        )
        gov = GovernanceConfig(
            policy_id="balanced",
            exec_attention_budget=10.0,
            default_initial_quality_belief=0.5,
            confidence_decline_threshold=0.3,
            tam_threshold_ratio=0.6,
            base_tam_patience_window=10,
            stagnation_window_staffed_ticks=15,
            stagnation_belief_change_threshold=0.02,
            attention_min=0.15,
            attention_max=None,
            exec_overrun_threshold=0.4,
            portfolio_mix_targets=pmt,
        )

        # Current portfolio: one active flywheel, zero enablers.
        # So enabler bucket (0%) is under-target (80%), flywheel is not.
        active_flywheel = _make_initiative_obs(
            initiative_id="active-fw",
            lifecycle_state="active",
            assigned_team_id="T-1",
            generation_tag="flywheel",
        )

        # Two unassigned candidates: one flywheel, one enabler.
        candidate_fw = _make_initiative_obs(
            initiative_id="cand-fw",
            lifecycle_state="unassigned",
            generation_tag="flywheel",
        )
        candidate_en = _make_initiative_obs(
            initiative_id="cand-en",
            lifecycle_state="unassigned",
            generation_tag="enabler",
        )

        # Original ranking puts flywheel first (alphabetical by id).
        ranked = (candidate_fw, candidate_en)

        observation = GovernanceObservation(
            tick=1,
            available_team_count=1,
            exec_attention_budget=10.0,
            default_initial_quality_belief=0.5,
            attention_min_effective=0.15,
            attention_max_effective=1.0,
            portfolio_capability_level=1.0,
            portfolio_summary=PortfolioSummary(
                active_labor_total=1,
                active_labor_below_quality_threshold=None,
                low_quality_belief_labor_share=None,
                max_single_initiative_labor_share=1.0,
            ),
            initiatives=(active_flywheel, candidate_fw, candidate_en),
            teams=(
                TeamObservation(
                    team_id="T-1",
                    assigned_initiative_id="active-fw",
                    available_next_tick=False,
                ),
                TeamObservation(
                    team_id="T-2",
                    assigned_initiative_id=None,
                    available_next_tick=True,
                ),
            ),
        )

        reranked = _rerank_for_mix_targets(ranked, observation, stopped_ids=set(), config=gov)

        # Enabler should be promoted to first position because its
        # bucket (enabler) is at 0% vs 80% target — well under-target.
        assert reranked[0].initiative_id == "cand-en"
        assert reranked[1].initiative_id == "cand-fw"

    def test_uncategorized_treated_as_residual(self) -> None:
        """Uncategorized initiatives are de-prioritized, not blocked.

        Proves that an initiative with no generation_tag still appears
        in the re-ranked list but behind canonical-bucket candidates
        that are under-target.
        """
        from primordial_soup.policy import _rerank_for_mix_targets

        pmt = PortfolioMixTargets(
            bucket_targets=(("enabler", 1.0),),
            tolerance=0.05,
        )
        gov = GovernanceConfig(
            policy_id="balanced",
            exec_attention_budget=10.0,
            default_initial_quality_belief=0.5,
            confidence_decline_threshold=0.3,
            tam_threshold_ratio=0.6,
            base_tam_patience_window=10,
            stagnation_window_staffed_ticks=15,
            stagnation_belief_change_threshold=0.02,
            attention_min=0.15,
            attention_max=None,
            exec_overrun_threshold=0.4,
            portfolio_mix_targets=pmt,
        )

        # No active initiatives — everything is under-target.
        candidate_none = _make_initiative_obs(
            initiative_id="cand-none",
            lifecycle_state="unassigned",
            generation_tag=None,  # uncategorized
        )
        candidate_en = _make_initiative_obs(
            initiative_id="cand-en",
            lifecycle_state="unassigned",
            generation_tag="enabler",
        )

        # None-tagged candidate listed first in original ranking.
        ranked = (candidate_none, candidate_en)

        observation = GovernanceObservation(
            tick=1,
            available_team_count=2,
            exec_attention_budget=10.0,
            default_initial_quality_belief=0.5,
            attention_min_effective=0.15,
            attention_max_effective=1.0,
            portfolio_capability_level=1.0,
            portfolio_summary=PortfolioSummary(
                active_labor_total=0,
                active_labor_below_quality_threshold=None,
                low_quality_belief_labor_share=None,
                max_single_initiative_labor_share=None,
            ),
            initiatives=(candidate_none, candidate_en),
            teams=(
                TeamObservation(
                    team_id="T-1",
                    assigned_initiative_id=None,
                    available_next_tick=True,
                ),
                TeamObservation(
                    team_id="T-2",
                    assigned_initiative_id=None,
                    available_next_tick=True,
                ),
            ),
        )

        reranked = _rerank_for_mix_targets(ranked, observation, stopped_ids=set(), config=gov)

        # Enabler is under-target (0% vs 100% target) → promoted.
        # Uncategorized has implicit target 0.0 → at-or-over-target → demoted.
        assert reranked[0].initiative_id == "cand-en"
        assert reranked[1].initiative_id == "cand-none"

        # Both candidates are still present — uncategorized is not dropped.
        assert len(reranked) == 2

    def test_portfolio_mix_computation_matches_bucket_vocabulary(self) -> None:
        """compute_current_portfolio_mix uses the same bucket vocab as targets.

        Proves that the bucket names in the computed mix dict are the same
        strings that appear in PortfolioMixTargets.bucket_targets, so the
        policy's under/over-target comparison uses a single vocabulary.
        """
        # Set up active initiatives with canonical tags.
        inits = (
            _make_initiative_obs(
                initiative_id="I-1",
                lifecycle_state="active",
                assigned_team_id="T-1",
                generation_tag="flywheel",
            ),
            _make_initiative_obs(
                initiative_id="I-2",
                lifecycle_state="active",
                assigned_team_id="T-2",
                generation_tag="enabler",
            ),
            _make_initiative_obs(
                initiative_id="I-3",
                lifecycle_state="active",
                assigned_team_id="T-3",
                generation_tag="enabler",
            ),
        )

        current_mix = compute_current_portfolio_mix(inits, stopped_ids=set())

        # The keys in current_mix are generation_tag values.
        assert set(current_mix.keys()) == {"flywheel", "enabler"}

        # These are the same strings that would appear in bucket_targets.
        pmt = PortfolioMixTargets(
            bucket_targets=(
                ("flywheel", 0.50),
                ("enabler", 0.50),
            ),
        )
        for bucket in current_mix:
            assert bucket in pmt.targets_dict, (
                f"Bucket {bucket!r} from compute_current_portfolio_mix is not "
                f"in the mix target vocabulary"
            )
