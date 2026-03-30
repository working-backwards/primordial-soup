"""Tests for baseline configuration presets and end-to-end smoke tests.

Phase 7, Milestone 1: Steps 7a–7e.

Tests validate:
    - Preset construction produces valid configurations
    - Balanced smoke test (first execution milestone): end-to-end run
      with meaningful outcomes
    - All three archetypes produce different governance behavior
    - CRN discipline: identical pools across regimes on shared seeds
    - Determinism: same seed → identical RunResult
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from primordial_soup.config import validate_configuration
from primordial_soup.policy import (
    AggressiveStopLossPolicy,
    BalancedPolicy,
    PatientMoonshotPolicy,
)
from primordial_soup.presets import (
    EnvironmentFamilyName,
    make_aggressive_stop_loss_config,
    make_balanced_config,
    make_baseline_initiative_generator_config,
    make_baseline_model_config,
    make_baseline_time_config,
    make_baseline_workforce_config,
    make_environment_spec,
    make_initiative_generator_config,
    make_patient_moonshot_config,
)
from primordial_soup.runner import run_single_regime

if TYPE_CHECKING:
    from primordial_soup.reporting import RunResult

# ===========================================================================
# Step 7a — Baseline environment configuration tests
# ===========================================================================


class TestBaselineEnvironment:
    """Tests for shared baseline environment components."""

    def test_baseline_time_config_reasonable_horizon(self) -> None:
        """Horizon is long enough for multi-year dynamics."""
        time_config = make_baseline_time_config()
        # Must be long enough that flywheels (20–60 ticks) and
        # right-tail initiatives (20–80 ticks) can complete and
        # residual channels have time to accrue.
        assert time_config.tick_horizon >= 100

    def test_baseline_workforce_has_multiple_teams(self) -> None:
        """Workforce provides meaningful parallelism."""
        workforce = make_baseline_workforce_config()
        assert workforce.team_count >= 4
        assert workforce.ramp_period >= 1

    def test_baseline_model_config_high_attention_budget(self) -> None:
        """exec_attention_budget is conservatively high.

        Per experiments.md: budget should be set so attention-feasibility
        violations are negligible. Budget should exceed worst-case sum
        of per-initiative attention allocations.
        """
        model = make_baseline_model_config()
        workforce = make_baseline_workforce_config()
        # Budget should be > team_count (even if every initiative gets 1.0)
        assert model.exec_attention_budget > workforce.team_count

    def test_baseline_generator_has_all_four_types(self) -> None:
        """Generator includes flywheel, right-tail, enabler, quick-win."""
        gen_config = make_baseline_initiative_generator_config()
        tags = {spec.generation_tag for spec in gen_config.type_specs}
        assert tags == {"flywheel", "right_tail", "enabler", "quick_win"}

    def test_baseline_generator_pool_size_oversized(self) -> None:
        """Pool is deliberately larger than team capacity over horizon.

        Per experiments.md §Pool sizing requirement: pool exhaustion
        is a configuration error.
        """
        gen_config = make_baseline_initiative_generator_config()
        total_count = sum(spec.count for spec in gen_config.type_specs)
        workforce = make_baseline_workforce_config()
        # Pool should be substantially larger than team_count to
        # allow for stops and reassignments.
        assert total_count > workforce.team_count * 3

    def test_baseline_generator_flywheel_has_residual(self) -> None:
        """Flywheel type spec enables residual on completion."""
        gen_config = make_baseline_initiative_generator_config()
        flywheel_spec = next(s for s in gen_config.type_specs if s.generation_tag == "flywheel")
        assert flywheel_spec.residual_enabled is True
        assert flywheel_spec.residual_activation_state == "completed"
        assert flywheel_spec.true_duration_range is not None

    def test_baseline_generator_right_tail_has_major_win(self) -> None:
        """Right-tail type spec enables major-win events."""
        gen_config = make_baseline_initiative_generator_config()
        right_tail_spec = next(
            s for s in gen_config.type_specs if s.generation_tag == "right_tail"
        )
        assert right_tail_spec.major_win_event_enabled is True
        assert right_tail_spec.observable_ceiling_distribution is not None

    def test_baseline_generator_enabler_has_capability(self) -> None:
        """Enabler type spec has positive capability_contribution_scale."""
        gen_config = make_baseline_initiative_generator_config()
        enabler_spec = next(s for s in gen_config.type_specs if s.generation_tag == "enabler")
        assert enabler_spec.capability_contribution_scale_range is not None
        low, high = enabler_spec.capability_contribution_scale_range
        assert low > 0
        assert high > low

    def test_baseline_generator_quick_win_short_duration(self) -> None:
        """Quick-win type spec has short duration range."""
        gen_config = make_baseline_initiative_generator_config()
        quick_win_spec = next(s for s in gen_config.type_specs if s.generation_tag == "quick_win")
        assert quick_win_spec.true_duration_range is not None
        assert quick_win_spec.true_duration_range[1] <= 15
        assert quick_win_spec.residual_enabled is True


# ===========================================================================
# Step 7b — Balanced preset construction tests
# ===========================================================================


class TestBalancedPreset:
    """Tests for Balanced archetype configuration construction."""

    def test_balanced_config_passes_validation(self) -> None:
        """Balanced preset produces a config that passes all validation."""
        config = make_balanced_config(world_seed=42)
        # Should not raise.
        validate_configuration(config)

    def test_balanced_config_uses_generator_path(self) -> None:
        """Balanced uses initiative_generator, not explicit initiatives."""
        config = make_balanced_config(world_seed=42)
        assert config.initiatives is None
        assert config.initiative_generator is not None

    def test_balanced_governance_policy_id(self) -> None:
        """Balanced governance has policy_id='balanced'."""
        config = make_balanced_config(world_seed=42)
        assert config.governance.policy_id == "balanced"

    def test_balanced_governance_all_stop_rules_active(self) -> None:
        """Balanced activates all four stop rules."""
        config = make_balanced_config(world_seed=42)
        governance = config.governance
        # Confidence decline: enabled (not None)
        assert governance.confidence_decline_threshold is not None
        # TAM adequacy: patience window > 0
        assert governance.base_tam_patience_window > 0
        # Stagnation: window > 0
        assert governance.stagnation_window_staffed_ticks > 0
        # Execution overrun: enabled (not None)
        assert governance.exec_overrun_threshold is not None

    def test_balanced_portfolio_risk_params_explicit(self) -> None:
        """All portfolio-risk params are explicitly set (even if None).

        Per plan Step 7b: set ALL portfolio-risk parameters explicitly.
        """
        config = make_balanced_config(world_seed=42)
        governance = config.governance
        # These must be explicitly None in the baseline.
        assert governance.low_quality_belief_threshold is None
        assert governance.max_low_quality_belief_labor_share is None
        assert governance.max_single_initiative_labor_share is None

    def test_balanced_governance_reads_from_model(self) -> None:
        """GovernanceConfig read-only copies match ModelConfig values."""
        config = make_balanced_config(world_seed=42)
        assert config.governance.exec_attention_budget == config.model.exec_attention_budget
        assert (
            config.governance.default_initial_quality_belief
            == config.model.default_initial_quality_belief
        )


# ===========================================================================
# Step 7c — Balanced smoke test (first execution milestone)
# ===========================================================================


class TestBalancedSmokeTest:
    """End-to-end smoke test for the Balanced archetype.

    Runs one full run_single_regime() with the Balanced preset and
    inspects the RunResult for basic sanity. Per plan Step 7c.
    """

    @pytest.fixture()
    def balanced_result(self) -> RunResult:
        """Run a single Balanced regime and return the RunResult.

        Uses a fixed seed for determinism.
        """
        config = make_balanced_config(world_seed=42)
        policy = BalancedPolicy()
        return run_single_regime(config, policy)[0]

    def test_nonzero_total_value(self, balanced_result: RunResult) -> None:
        """Total realized value across channels is positive."""
        assert balanced_result.cumulative_value_total > 0

    def test_some_initiatives_completed(self, balanced_result: RunResult) -> None:
        """At least some initiatives reach 'completed' lifecycle state."""
        # Completed count is inferred from exploration cost profile.
        completed_total = sum(
            balanced_result.exploration_cost_profile.completed_initiative_count_by_label.values()
        )
        assert completed_total > 0

    def test_some_initiatives_stopped(self, balanced_result: RunResult) -> None:
        """At least some initiatives are stopped (governance exercises stop rules).

        Per plan Step 7c: governance is exercising stop rules, not just
        holding everything.
        """
        stopped_count = sum(
            balanced_result.exploration_cost_profile.stopped_initiative_count_by_label.values()
        )
        assert stopped_count > 0

    def test_lump_value_positive(self, balanced_result: RunResult) -> None:
        """Completion lump and/or residual channels produce value."""
        vbc = balanced_result.value_by_channel
        # At least one value channel should produce positive value.
        assert vbc.completion_lump_value + vbc.residual_value > 0

    def test_no_pool_exhaustion(self, balanced_result: RunResult) -> None:
        """Pool is not exhausted (or exhaustion is very late).

        Per plan Step 7c: pool_exhaustion_tick is None or very late.
        """
        pet = balanced_result.idle_capacity_profile.pool_exhaustion_tick
        if pet is not None:
            # If exhaustion occurs, it should be late in the run.
            assert pet > 150, (
                f"Pool exhausted at tick {pet} — too early. "
                "Increase pool size in the generator config."
            )

    def test_capability_grows_if_enablers_complete(self, balanced_result: RunResult) -> None:
        """Terminal capability >= 1.0 (baseline).

        If any enablers completed, capability should be above the 1.0
        baseline. Even without enabler completions, capability never
        drops below 1.0 minus decay (which is small).
        """
        # Capability starts at 1.0 and can only increase above 1.0
        # through enabler completions (minus decay). Terminal value
        # should be close to or above 1.0.
        assert balanced_result.terminal_capability_t >= 0.9

    def test_residual_streams_produce_value(self, balanced_result: RunResult) -> None:
        """Residual channels activate for completed flywheels/quick-wins."""
        assert balanced_result.value_by_channel.residual_value > 0

    def test_determinism_same_seed_identical_result(self) -> None:
        """Same seed produces identical RunResult."""
        config = make_balanced_config(world_seed=42)
        policy = BalancedPolicy()
        result_a, _ = run_single_regime(config, policy)
        result_b, _ = run_single_regime(config, policy)
        # Floating-point equality: same seed + pure functions = exact match.
        assert result_a.cumulative_value_total == result_b.cumulative_value_total
        assert (
            result_a.exploration_cost_profile.stopped_initiative_count_by_label
            == result_b.exploration_cost_profile.stopped_initiative_count_by_label
        )
        assert (
            result_a.major_win_profile.major_win_count
            == result_b.major_win_profile.major_win_count
        )
        assert result_a.terminal_capability_t == result_b.terminal_capability_t


# ===========================================================================
# Step 7d — Aggressive Stop-Loss and Patient Moonshot presets
# ===========================================================================


class TestAggressiveStopLossPreset:
    """Tests for Aggressive Stop-Loss archetype configuration."""

    def test_config_passes_validation(self) -> None:
        """Aggressive preset produces a config that passes validation."""
        config = make_aggressive_stop_loss_config(world_seed=42)
        validate_configuration(config)

    def test_policy_id_is_aggressive(self) -> None:
        """Policy ID distinguishes this archetype."""
        config = make_aggressive_stop_loss_config(world_seed=42)
        assert config.governance.policy_id == "aggressive_stop_loss"

    def test_tighter_thresholds_than_balanced(self) -> None:
        """Aggressive has tighter stop thresholds than Balanced."""
        balanced = make_balanced_config(world_seed=42).governance
        aggressive = make_aggressive_stop_loss_config(world_seed=42).governance

        # Both thresholds are not None for aggressive and balanced.
        assert aggressive.confidence_decline_threshold is not None
        assert balanced.confidence_decline_threshold is not None
        assert aggressive.exec_overrun_threshold is not None
        assert balanced.exec_overrun_threshold is not None

        # Higher confidence threshold = stops sooner (belief must stay higher).
        assert aggressive.confidence_decline_threshold > balanced.confidence_decline_threshold
        # Shorter patience windows.
        assert aggressive.base_tam_patience_window < balanced.base_tam_patience_window
        assert (
            aggressive.stagnation_window_staffed_ticks < balanced.stagnation_window_staffed_ticks
        )
        # Tighter execution overrun.
        assert aggressive.exec_overrun_threshold > balanced.exec_overrun_threshold

    def test_portfolio_risk_params_explicit(self) -> None:
        """All portfolio-risk params are explicitly set."""
        config = make_aggressive_stop_loss_config(world_seed=42)
        governance = config.governance
        assert governance.low_quality_belief_threshold is None
        assert governance.max_low_quality_belief_labor_share is None
        assert governance.max_single_initiative_labor_share is None

    def test_same_environment_as_balanced(self) -> None:
        """Shares the same baseline environment as Balanced."""
        balanced = make_balanced_config(world_seed=42)
        aggressive = make_aggressive_stop_loss_config(world_seed=42)
        assert balanced.time == aggressive.time
        assert balanced.teams == aggressive.teams
        assert balanced.model == aggressive.model
        assert balanced.initiative_generator == aggressive.initiative_generator


class TestPatientMoonshotPreset:
    """Tests for Patient Moonshot archetype configuration."""

    def test_config_passes_validation(self) -> None:
        """Patient Moonshot produces a valid config."""
        config = make_patient_moonshot_config(world_seed=42)
        validate_configuration(config)

    def test_policy_id_is_patient_moonshot(self) -> None:
        """Policy ID distinguishes this archetype."""
        config = make_patient_moonshot_config(world_seed=42)
        assert config.governance.policy_id == "patient_moonshot"

    def test_confidence_decline_very_low(self) -> None:
        """Patient Moonshot uses a very low confidence-decline threshold.

        Per issue #18 recalibration: a very low threshold (0.08) replaces
        the previous None (disabled) to prevent paralysis while preserving
        the patient philosophy. Much lower than Balanced (0.2).
        """
        config = make_patient_moonshot_config(world_seed=42)
        balanced = make_balanced_config(world_seed=42)
        patient_threshold = config.governance.confidence_decline_threshold
        balanced_threshold = balanced.governance.confidence_decline_threshold
        assert patient_threshold is not None
        assert balanced_threshold is not None
        assert patient_threshold < balanced_threshold

    def test_longer_patience_than_balanced(self) -> None:
        """Patient Moonshot has longer patience windows."""
        balanced = make_balanced_config(world_seed=42).governance
        patient = make_patient_moonshot_config(world_seed=42).governance

        assert patient.base_tam_patience_window > balanced.base_tam_patience_window
        assert patient.stagnation_window_staffed_ticks > balanced.stagnation_window_staffed_ticks

    def test_more_tolerant_exec_overrun(self) -> None:
        """Patient Moonshot tolerates more execution overrun."""
        balanced = make_balanced_config(world_seed=42).governance
        patient = make_patient_moonshot_config(world_seed=42).governance

        # Both must be not-None for the comparison.
        assert patient.exec_overrun_threshold is not None
        assert balanced.exec_overrun_threshold is not None

        # Lower threshold = more tolerant (belief can drop further before stop).
        assert patient.exec_overrun_threshold < balanced.exec_overrun_threshold

    def test_portfolio_risk_params_explicit(self) -> None:
        """All portfolio-risk params are explicitly set."""
        config = make_patient_moonshot_config(world_seed=42)
        governance = config.governance
        assert governance.low_quality_belief_threshold is None
        assert governance.max_low_quality_belief_labor_share is None
        assert governance.max_single_initiative_labor_share is None

    def test_same_environment_as_balanced(self) -> None:
        """Shares the same baseline environment as Balanced."""
        balanced = make_balanced_config(world_seed=42)
        patient = make_patient_moonshot_config(world_seed=42)
        assert balanced.time == patient.time
        assert balanced.teams == patient.teams
        assert balanced.model == patient.model
        assert balanced.initiative_generator == patient.initiative_generator


# ===========================================================================
# Step 7e — Three-archetype comparison test
# ===========================================================================


class TestThreeArchetypeComparison:
    """Compare all three archetypes against shared seeds.

    Per plan Step 7e: verify CRN discipline, different outcomes,
    and each archetype's stop-rule profile matches intended posture.
    """

    @pytest.fixture()
    def comparison_results(self) -> dict[str, RunResult]:
        """Run all three archetypes on the same seed.

        Returns a dict mapping archetype name to RunResult.
        """
        seed = 42
        results: dict[str, RunResult] = {}

        config_b = make_balanced_config(seed)
        results["balanced"], _ = run_single_regime(config_b, BalancedPolicy())

        config_a = make_aggressive_stop_loss_config(seed)
        results["aggressive"], _ = run_single_regime(config_a, AggressiveStopLossPolicy())

        config_p = make_patient_moonshot_config(seed)
        results["patient"], _ = run_single_regime(config_p, PatientMoonshotPolicy())

        return results

    def test_identical_pools_across_regimes(self) -> None:
        """CRN discipline: same seed → identical initial initiative pools.

        All three configs use the same initiative_generator and
        world_seed, so the initial pool (before frontier materialization)
        must be identical. With dynamic frontier enabled, different
        governance trajectories may produce different frontier-generated
        initiatives — this is intended per dynamic_opportunity_frontier.md
        §Governance-trajectory dependence.
        """
        seed = 42
        config_b = make_balanced_config(seed)
        config_a = make_aggressive_stop_loss_config(seed)
        config_p = make_patient_moonshot_config(seed)

        # All use generator path — initial pools resolved deterministically.
        assert config_b.initiative_generator == config_a.initiative_generator
        assert config_b.initiative_generator == config_p.initiative_generator

        # Run all three regimes.
        result_b, _ = run_single_regime(config_b, BalancedPolicy())
        result_a, _ = run_single_regime(config_a, AggressiveStopLossPolicy())
        result_p, _ = run_single_regime(config_p, PatientMoonshotPolicy())

        # The initial pool size is determined by the generator config.
        # All type spec counts sum to the family pool size.
        initial_pool_size = sum(ts.count for ts in config_b.initiative_generator.type_specs)

        # Compare the INITIAL pool initiatives (init-0 through init-N-1).
        # These must be identical across all three regimes.
        initiatives_b = result_b.manifest.resolved_initiatives[:initial_pool_size]
        initiatives_a = result_a.manifest.resolved_initiatives[:initial_pool_size]
        initiatives_p = result_p.manifest.resolved_initiatives[:initial_pool_size]

        assert len(initiatives_b) == len(initiatives_a) == len(initiatives_p)
        for ib, ia, ip in zip(initiatives_b, initiatives_a, initiatives_p, strict=True):
            assert ib.initiative_id == ia.initiative_id == ip.initiative_id
            assert ib.latent_quality == ia.latent_quality == ip.latent_quality

    def test_different_terminal_outcomes(self, comparison_results: dict[str, RunResult]) -> None:
        """Governance differences produce measurable behavioral differences.

        At least two of the three archetypes should produce different
        total value outcomes.
        """
        values = {name: r.cumulative_value_total for name, r in comparison_results.items()}
        # Not all three identical.
        unique_values = set(values.values())
        assert len(unique_values) > 1, f"All archetypes produced identical total value: {values}"

    def test_aggressive_stops_more_than_balanced(
        self, comparison_results: dict[str, RunResult]
    ) -> None:
        """Aggressive archetype stops more initiatives than Balanced.

        Per plan Step 7e: each archetype's stop-rule profile matches
        its intended posture — Aggressive stops more and earlier.
        """
        balanced_stopped = sum(
            comparison_results[
                "balanced"
            ].exploration_cost_profile.stopped_initiative_count_by_label.values()
        )
        aggressive_stopped = sum(
            comparison_results[
                "aggressive"
            ].exploration_cost_profile.stopped_initiative_count_by_label.values()
        )
        assert aggressive_stopped >= balanced_stopped, (
            f"Aggressive ({aggressive_stopped}) should stop at least as "
            f"many initiatives as Balanced ({balanced_stopped})."
        )

    def test_patient_stops_fewer_than_balanced(
        self, comparison_results: dict[str, RunResult]
    ) -> None:
        """Patient Moonshot stops fewer initiatives than Balanced.

        Per plan Step 7e: Patient holds longer, stops fewer.
        """
        balanced_stopped = sum(
            comparison_results[
                "balanced"
            ].exploration_cost_profile.stopped_initiative_count_by_label.values()
        )
        patient_stopped = sum(
            comparison_results[
                "patient"
            ].exploration_cost_profile.stopped_initiative_count_by_label.values()
        )
        assert patient_stopped <= balanced_stopped, (
            f"Patient ({patient_stopped}) should stop at most as "
            f"many initiatives as Balanced ({balanced_stopped})."
        )

    def test_all_archetypes_no_pool_exhaustion(
        self, comparison_results: dict[str, RunResult]
    ) -> None:
        """No archetype exhausts the pool (or only very late)."""
        for name, result in comparison_results.items():
            pet = result.idle_capacity_profile.pool_exhaustion_tick
            if pet is not None:
                assert pet > 150, f"{name} exhausted pool at tick {pet}. Increase pool size."

    def test_all_archetypes_produce_nonnegative_value_and_activity(
        self, comparison_results: dict[str, RunResult]
    ) -> None:
        """Every archetype produces non-negative value and meaningful activity.

        After right-tail calibration, patient moonshot may legitimately
        produce zero direct value if all completions are right-tail
        (which have no lump/residual channels). The test checks for
        non-negative value AND that the run shows governance activity
        (completions, stops, or major wins).
        """
        for name, result in comparison_results.items():
            assert result.cumulative_value_total >= 0, f"{name} produced negative total value."

            # The archetype must show governance activity: either
            # completions, stops, or major wins.
            completed_count = sum(
                result.exploration_cost_profile.completed_initiative_count_by_label.values()
            )
            stopped_count = sum(
                result.exploration_cost_profile.stopped_initiative_count_by_label.values()
            )
            major_wins = result.major_win_profile.major_win_count
            assert (
                completed_count + stopped_count + major_wins > 0
            ), f"{name} produced no completions, stops, or major wins."


# ===========================================================================
# Environment family tests
# ===========================================================================


class TestEnvironmentFamilies:
    """Tests for named environment families."""

    # All valid family names for parametrized tests.
    ALL_FAMILIES: tuple[EnvironmentFamilyName, ...] = (
        "balanced_incumbent",
        "short_cycle_throughput",
        "discovery_heavy",
    )

    @pytest.mark.parametrize("family", ALL_FAMILIES)
    def test_family_generator_config_valid(self, family: EnvironmentFamilyName) -> None:
        """Each family produces a valid InitiativeGeneratorConfig with all four types."""
        gen_config = make_initiative_generator_config(family)
        tags = {spec.generation_tag for spec in gen_config.type_specs}
        assert tags == {"flywheel", "right_tail", "enabler", "quick_win"}

    @pytest.mark.parametrize("family", ALL_FAMILIES)
    def test_family_pool_size_is_200(self, family: EnvironmentFamilyName) -> None:
        """Total initiative count is 200 in every family."""
        gen_config = make_initiative_generator_config(family)
        total = sum(spec.count for spec in gen_config.type_specs)
        assert total == 200

    @pytest.mark.parametrize("family", ALL_FAMILIES)
    def test_family_config_passes_validation(self, family: EnvironmentFamilyName) -> None:
        """Each family produces a SimulationConfiguration that passes validation."""
        config = make_balanced_config(world_seed=42, family=family)
        validate_configuration(config)

    @pytest.mark.parametrize("family", ALL_FAMILIES)
    def test_family_environment_spec_valid(self, family: EnvironmentFamilyName) -> None:
        """Each family produces a valid EnvironmentSpec."""
        env = make_environment_spec(family)
        gen_config = env.initiative_generator
        total = sum(spec.count for spec in gen_config.type_specs)
        assert total == 200

    def test_baseline_wrapper_returns_balanced_incumbent(self) -> None:
        """make_baseline_initiative_generator_config returns balanced_incumbent."""
        baseline = make_baseline_initiative_generator_config()
        family = make_initiative_generator_config("balanced_incumbent")
        assert baseline == family

    def test_baseline_environment_spec_wrapper_returns_balanced_incumbent(self) -> None:
        """make_baseline_environment_spec returns balanced_incumbent."""
        from primordial_soup.presets import make_baseline_environment_spec

        baseline = make_baseline_environment_spec()
        family = make_environment_spec("balanced_incumbent")
        assert baseline == family

    def test_default_family_is_balanced_incumbent(self) -> None:
        """Calling without family argument defaults to balanced_incumbent."""
        default = make_initiative_generator_config()
        explicit = make_initiative_generator_config("balanced_incumbent")
        assert default == explicit

    def test_families_differ_on_right_tail_parameters(self) -> None:
        """The three families produce different right-tail type specs."""
        configs = {
            family: make_initiative_generator_config(family) for family in self.ALL_FAMILIES
        }
        # Extract right-tail specs.
        right_tail_specs = {
            family: next(s for s in config.type_specs if s.generation_tag == "right_tail")
            for family, config in configs.items()
        }
        # No two families should have the same right-tail spec.
        specs_list = list(right_tail_specs.values())
        assert specs_list[0] != specs_list[1]
        assert specs_list[0] != specs_list[2]
        assert specs_list[1] != specs_list[2]

    def test_families_share_non_right_tail_parameters(self) -> None:
        """Flywheel, enabler, and quick-win type parameters (excluding count) are shared.

        Flywheel and quick-win counts vary by family (more flywheels in
        balanced_incumbent, more quick-wins in short_cycle_throughput), but
        all other parameters must be identical across families. We compare
        specs after normalizing count to rule out count-only differences.
        """
        import dataclasses

        configs = {
            family: make_initiative_generator_config(family) for family in self.ALL_FAMILIES
        }
        for tag in ("flywheel", "enabler", "quick_win"):
            specs = [
                next(s for s in config.type_specs if s.generation_tag == tag)
                for config in configs.values()
            ]
            # Normalize count to the first spec's count so that only
            # non-count differences cause a failure.
            normalized = [dataclasses.replace(s, count=specs[0].count) for s in specs]
            assert (
                normalized[0] == normalized[1] == normalized[2]
            ), f"{tag} non-count fields differ across families"

    def test_short_cycle_has_more_quick_wins(self) -> None:
        """short_cycle_throughput has more quick wins than balanced_incumbent."""
        balanced = make_initiative_generator_config("balanced_incumbent")
        short_cycle = make_initiative_generator_config("short_cycle_throughput")
        qw_balanced = next(s for s in balanced.type_specs if s.generation_tag == "quick_win").count
        qw_short = next(s for s in short_cycle.type_specs if s.generation_tag == "quick_win").count
        assert qw_short > qw_balanced

    def test_discovery_heavy_has_more_right_tail(self) -> None:
        """discovery_heavy has more right-tail initiatives than balanced_incumbent."""
        balanced = make_initiative_generator_config("balanced_incumbent")
        discovery = make_initiative_generator_config("discovery_heavy")
        rt_balanced = next(
            s for s in balanced.type_specs if s.generation_tag == "right_tail"
        ).count
        rt_discovery = next(
            s for s in discovery.type_specs if s.generation_tag == "right_tail"
        ).count
        assert rt_discovery > rt_balanced

    def test_archetype_factory_accepts_family(self) -> None:
        """All three archetype config factories accept family parameter."""
        factories = (
            make_balanced_config,
            make_aggressive_stop_loss_config,
            make_patient_moonshot_config,
        )
        for factory_fn in factories:
            for family in self.ALL_FAMILIES:
                config = factory_fn(world_seed=42, family=family)
                validate_configuration(config)

    def test_invalid_family_raises_value_error(self) -> None:
        """Passing an unrecognized family name raises ValueError."""
        with pytest.raises(ValueError, match="Unknown environment family"):
            make_initiative_generator_config("nonexistent_family")  # type: ignore[arg-type]


# ===========================================================================
# Canonical initiative-family semantic consistency tests
# ===========================================================================
#
# These tests enforce the canonical value-channel and capability semantics
# for each initiative family. They exist to catch semantic drift: if a
# future change accidentally makes enablers produce residual value, or
# removes the completion-lump channel from quick wins, these tests fail
# immediately.
#
# The executable authority for family semantics is the canonical
# InitiativeTypeSpec definitions in presets.py. These tests verify that
# those definitions match the intended semantics from the study design.
#
# Per comprehensive_design_to_align_study_model_and_authoring_v2.md §Part III.


class TestCanonicalFamilySemantics:
    """Enforce canonical value-channel semantics for each initiative family.

    These consistency tests verify that the canonical InitiativeTypeSpec
    definitions in presets.py match the intended family semantics:

        Flywheel:   residual-value dominant, no completion lump in v1
        Quick-win:  completion-lump dominant, at most a small residual tail
        Enabler:    capability-only, no direct value channels
        Right-tail: major-win / discovery driven, no ordinary direct value

    Tests are parametrized across all three environment families so that
    family-specific right-tail variation does not accidentally change
    the shared type semantics.
    """

    ALL_FAMILIES: tuple[EnvironmentFamilyName, ...] = (
        "balanced_incumbent",
        "short_cycle_throughput",
        "discovery_heavy",
    )

    def _get_spec(self, family: EnvironmentFamilyName, tag: str):
        """Helper: extract the type spec with the given generation_tag."""
        gen_config = make_initiative_generator_config(family)
        return next(s for s in gen_config.type_specs if s.generation_tag == tag)

    # --- Flywheel: residual-value dominant, no completion lump ---

    @pytest.mark.parametrize("family", ALL_FAMILIES)
    def test_flywheel_is_residual_enabled(self, family: EnvironmentFamilyName) -> None:
        """Flywheel must have residual channel enabled (its primary value mechanism)."""
        spec = self._get_spec(family, "flywheel")
        assert spec.residual_enabled is True
        assert spec.residual_rate_range is not None
        assert spec.residual_rate_range[0] > 0

    @pytest.mark.parametrize("family", ALL_FAMILIES)
    def test_flywheel_has_no_completion_lump(self, family: EnvironmentFamilyName) -> None:
        """Flywheel must not have completion-lump enabled in v1.

        Per design: flywheel value comes from durable residual streams
        after completion. A completion-lump channel may be added later
        as a separate decision, but is not part of v1.
        """
        spec = self._get_spec(family, "flywheel")
        assert spec.completion_lump_enabled is False

    @pytest.mark.parametrize("family", ALL_FAMILIES)
    def test_flywheel_has_no_capability_contribution(self, family: EnvironmentFamilyName) -> None:
        """Flywheel does not contribute to portfolio capability (that's enabler's role)."""
        spec = self._get_spec(family, "flywheel")
        assert spec.capability_contribution_scale_range is None

    # --- Quick-win: completion-lump dominant, small residual tail ---

    @pytest.mark.parametrize("family", ALL_FAMILIES)
    def test_quick_win_is_completion_lump_enabled(self, family: EnvironmentFamilyName) -> None:
        """Quick-win must have completion-lump channel enabled (its primary value mechanism).

        Per design: quick wins are completion-lump-dominant opportunities.
        """
        spec = self._get_spec(family, "quick_win")
        assert spec.completion_lump_enabled is True
        assert spec.completion_lump_value_range is not None
        assert spec.completion_lump_value_range[0] > 0

    @pytest.mark.parametrize("family", ALL_FAMILIES)
    def test_quick_win_residual_is_small_tail_only(self, family: EnvironmentFamilyName) -> None:
        """Quick-win residual, if present, must be a small tail — not the dominant channel.

        The residual rate range upper bound must be well below the completion-lump
        value range lower bound, ensuring the lump is the dominant value mechanism.
        """
        spec = self._get_spec(family, "quick_win")
        if spec.residual_enabled:
            assert spec.residual_rate_range is not None
            assert spec.completion_lump_value_range is not None
            # The residual rate upper bound should be materially smaller than
            # the lump value lower bound, ensuring lump dominance.
            residual_rate_max = spec.residual_rate_range[1]
            lump_value_min = spec.completion_lump_value_range[0]
            assert residual_rate_max < lump_value_min, (
                f"Quick-win residual rate max ({residual_rate_max}) must be "
                f"smaller than lump value min ({lump_value_min}) to ensure "
                f"completion-lump dominance."
            )

    @pytest.mark.parametrize("family", ALL_FAMILIES)
    def test_quick_win_has_no_capability_contribution(self, family: EnvironmentFamilyName) -> None:
        """Quick-win does not contribute to portfolio capability."""
        spec = self._get_spec(family, "quick_win")
        assert spec.capability_contribution_scale_range is None

    # --- Enabler: capability-only, no direct value ---

    @pytest.mark.parametrize("family", ALL_FAMILIES)
    def test_enabler_has_capability_contribution(self, family: EnvironmentFamilyName) -> None:
        """Enabler must have positive capability contribution (its sole value mechanism)."""
        spec = self._get_spec(family, "enabler")
        assert spec.capability_contribution_scale_range is not None
        assert spec.capability_contribution_scale_range[0] > 0

    @pytest.mark.parametrize("family", ALL_FAMILIES)
    def test_enabler_has_no_completion_lump(self, family: EnvironmentFamilyName) -> None:
        """Enabler must not produce direct value through completion lump.

        Per design: enablers improve future capability, they do not generate
        direct value.
        """
        spec = self._get_spec(family, "enabler")
        assert spec.completion_lump_enabled is False

    @pytest.mark.parametrize("family", ALL_FAMILIES)
    def test_enabler_has_no_residual(self, family: EnvironmentFamilyName) -> None:
        """Enabler must not have residual channel enabled.

        Per design: enablers are capability-only.
        """
        spec = self._get_spec(family, "enabler")
        assert spec.residual_enabled is False

    # --- Right-tail: major-win / discovery driven, no ordinary direct value ---

    @pytest.mark.parametrize("family", ALL_FAMILIES)
    def test_right_tail_has_major_win_enabled(self, family: EnvironmentFamilyName) -> None:
        """Right-tail must have major-win event channel enabled (its discovery mechanism)."""
        spec = self._get_spec(family, "right_tail")
        assert spec.major_win_event_enabled is True
        assert spec.observable_ceiling_distribution is not None

    @pytest.mark.parametrize("family", ALL_FAMILIES)
    def test_right_tail_has_no_completion_lump(self, family: EnvironmentFamilyName) -> None:
        """Right-tail must not produce ordinary direct value through completion lump.

        Per design: right-tail success is a major-win event recorded
        separately, not priced as ordinary completion revenue.
        """
        spec = self._get_spec(family, "right_tail")
        assert spec.completion_lump_enabled is False

    @pytest.mark.parametrize("family", ALL_FAMILIES)
    def test_right_tail_has_no_residual(self, family: EnvironmentFamilyName) -> None:
        """Right-tail must not have residual channel enabled.

        Per design: right-tail does not produce ordinary residual value.
        """
        spec = self._get_spec(family, "right_tail")
        assert spec.residual_enabled is False

    @pytest.mark.parametrize("family", ALL_FAMILIES)
    def test_right_tail_has_no_capability_contribution(
        self, family: EnvironmentFamilyName
    ) -> None:
        """Right-tail does not contribute to portfolio capability (that's enabler's role)."""
        spec = self._get_spec(family, "right_tail")
        assert spec.capability_contribution_scale_range is None
