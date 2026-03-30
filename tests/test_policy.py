"""Tests for governance policy archetypes.

Each test exercises a policy's decide() method with known observation
state and verifies the structure and content of the returned action
vector. Edge cases (no active initiatives, all stopped, empty pool)
get their own tests.

Per governance.md policy interface, interfaces.md Policy API.
"""

from __future__ import annotations

import pytest

from conftest import (
    make_governance_config,
    make_governance_observation,
    make_initiative_observation,
    make_portfolio_summary,
    make_team_observation,
)
from primordial_soup.policy import (
    AggressiveStopLossPolicy,
    BalancedPolicy,
    GovernancePolicy,
    PatientMoonshotPolicy,
)
from primordial_soup.types import StopContinueDecision, TriggeringRule

# ============================================================================
# Protocol compliance
# ============================================================================


class TestProtocolCompliance:
    """Verify all archetypes satisfy the GovernancePolicy protocol."""

    def test_balanced_is_governance_policy(self) -> None:
        policy: GovernancePolicy = BalancedPolicy()
        assert hasattr(policy, "decide")

    def test_aggressive_is_governance_policy(self) -> None:
        policy: GovernancePolicy = AggressiveStopLossPolicy()
        assert hasattr(policy, "decide")

    def test_patient_is_governance_policy(self) -> None:
        policy: GovernancePolicy = PatientMoonshotPolicy()
        assert hasattr(policy, "decide")


# ============================================================================
# Helper to extract action details
# ============================================================================


def _stop_decisions(actions) -> dict[str, StopContinueDecision]:
    """Extract initiative_id → decision mapping from ContinueStop actions."""
    return {a.initiative_id: a.decision for a in actions.continue_stop}


def _stop_rules(actions) -> dict[str, TriggeringRule | None]:
    """Extract initiative_id → triggering_rule mapping."""
    return {a.initiative_id: a.triggering_rule for a in actions.continue_stop}


def _assigned_teams(actions) -> dict[str, str | None]:
    """Extract team_id → initiative_id mapping from AssignTeam actions."""
    return {a.team_id: a.initiative_id for a in actions.assign_team}


def _attention_levels(actions) -> dict[str, float]:
    """Extract initiative_id → attention mapping from SetExecAttention."""
    return {a.initiative_id: a.attention for a in actions.set_exec_attention}


# ============================================================================
# BalancedPolicy tests
# ============================================================================


class TestBalancedPolicy:
    """Test the canonical reference baseline archetype."""

    def test_continue_healthy_initiative(self) -> None:
        """A healthy initiative is continued with attention."""
        init = make_initiative_observation(
            initiative_id="init-1",
            lifecycle_state="active",
            assigned_team_id="team-1",
            quality_belief_t=0.7,
        )
        team = make_team_observation(
            team_id="team-1",
            assigned_initiative_id="init-1",
            available_next_tick=False,
        )
        obs = make_governance_observation(
            initiatives=(init,),
            teams=(team,),
        )
        config = make_governance_config(confidence_decline_threshold=0.3)
        actions = BalancedPolicy().decide(obs, config)

        decisions = _stop_decisions(actions)
        assert decisions["init-1"] == StopContinueDecision.CONTINUE

        # Should receive attention.
        attention = _attention_levels(actions)
        assert "init-1" in attention
        assert attention["init-1"] > 0

    def test_stop_on_confidence_decline(self) -> None:
        init = make_initiative_observation(
            initiative_id="init-1",
            lifecycle_state="active",
            assigned_team_id="team-1",
            quality_belief_t=0.1,
        )
        team = make_team_observation(
            team_id="team-1",
            assigned_initiative_id="init-1",
        )
        obs = make_governance_observation(initiatives=(init,), teams=(team,))
        config = make_governance_config(confidence_decline_threshold=0.3)
        actions = BalancedPolicy().decide(obs, config)

        decisions = _stop_decisions(actions)
        assert decisions["init-1"] == StopContinueDecision.STOP

        rules = _stop_rules(actions)
        assert rules["init-1"] == TriggeringRule.CONFIDENCE_DECLINE

    def test_stop_on_tam_adequacy(self) -> None:
        init = make_initiative_observation(
            initiative_id="init-1",
            lifecycle_state="active",
            assigned_team_id="team-1",
            quality_belief_t=0.5,
            observable_ceiling=100.0,
            effective_tam_patience_window=3,
            consecutive_reviews_below_tam_ratio=3,
        )
        team = make_team_observation(
            team_id="team-1",
            assigned_initiative_id="init-1",
        )
        obs = make_governance_observation(initiatives=(init,), teams=(team,))
        config = make_governance_config(confidence_decline_threshold=0.1)
        actions = BalancedPolicy().decide(obs, config)

        decisions = _stop_decisions(actions)
        assert decisions["init-1"] == StopContinueDecision.STOP
        assert _stop_rules(actions)["init-1"] == TriggeringRule.TAM_ADEQUACY

    def test_stop_on_execution_overrun(self) -> None:
        init = make_initiative_observation(
            initiative_id="init-1",
            lifecycle_state="active",
            assigned_team_id="team-1",
            quality_belief_t=0.7,
            execution_belief_t=0.3,
        )
        team = make_team_observation(
            team_id="team-1",
            assigned_initiative_id="init-1",
        )
        obs = make_governance_observation(initiatives=(init,), teams=(team,))
        config = make_governance_config(
            confidence_decline_threshold=0.1,
            exec_overrun_threshold=0.5,
        )
        actions = BalancedPolicy().decide(obs, config)

        decisions = _stop_decisions(actions)
        assert decisions["init-1"] == StopContinueDecision.STOP
        assert _stop_rules(actions)["init-1"] == TriggeringRule.EXECUTION_OVERRUN

    def test_stop_on_stagnation(self) -> None:
        # belief_history shows flat belief below initial baseline.
        init = make_initiative_observation(
            initiative_id="init-1",
            lifecycle_state="active",
            assigned_team_id="team-1",
            quality_belief_t=0.4,
            observable_ceiling=None,
            belief_history=(0.40, 0.40, 0.40),
        )
        team = make_team_observation(
            team_id="team-1",
            assigned_initiative_id="init-1",
        )
        obs = make_governance_observation(initiatives=(init,), teams=(team,))
        config = make_governance_config(
            confidence_decline_threshold=0.1,
            default_initial_quality_belief=0.5,
            stagnation_window_staffed_ticks=3,
            stagnation_belief_change_threshold=0.02,
        )
        actions = BalancedPolicy().decide(obs, config)

        decisions = _stop_decisions(actions)
        assert decisions["init-1"] == StopContinueDecision.STOP
        assert _stop_rules(actions)["init-1"] == TriggeringRule.STAGNATION

    def test_no_active_initiatives_empty_actions(self) -> None:
        """No active initiatives → empty ContinueStop and attention."""
        obs = make_governance_observation(initiatives=(), teams=())
        config = make_governance_config()
        actions = BalancedPolicy().decide(obs, config)

        assert len(actions.continue_stop) == 0
        assert len(actions.set_exec_attention) == 0

    def test_freed_team_gets_assigned(self) -> None:
        """A stopped initiative frees a team, which gets assigned."""
        # Active initiative about to be stopped (low belief).
        active = make_initiative_observation(
            initiative_id="init-1",
            lifecycle_state="active",
            assigned_team_id="team-1",
            quality_belief_t=0.05,
        )
        # Unassigned candidate waiting in pool.
        candidate = make_initiative_observation(
            initiative_id="init-2",
            lifecycle_state="unassigned",
            assigned_team_id=None,
            quality_belief_t=0.6,
            observable_ceiling=100.0,
        )
        team = make_team_observation(
            team_id="team-1",
            assigned_initiative_id="init-1",
            available_next_tick=False,
        )
        obs = make_governance_observation(
            initiatives=(active, candidate),
            teams=(team,),
        )
        config = make_governance_config(confidence_decline_threshold=0.3)
        actions = BalancedPolicy().decide(obs, config)

        # init-1 should be stopped.
        decisions = _stop_decisions(actions)
        assert decisions["init-1"] == StopContinueDecision.STOP

        # team-1 should be assigned to init-2.
        assignments = _assigned_teams(actions)
        assert assignments.get("team-1") == "init-2"

    def test_equal_attention_allocation(self) -> None:
        """Two continuing initiatives split attention equally."""
        init_a = make_initiative_observation(
            initiative_id="A",
            lifecycle_state="active",
            assigned_team_id="team-1",
            quality_belief_t=0.7,
        )
        init_b = make_initiative_observation(
            initiative_id="B",
            lifecycle_state="active",
            assigned_team_id="team-2",
            quality_belief_t=0.6,
        )
        team_a = make_team_observation(
            team_id="team-1",
            assigned_initiative_id="A",
        )
        team_b = make_team_observation(
            team_id="team-2",
            assigned_initiative_id="B",
        )
        obs = make_governance_observation(
            initiatives=(init_a, init_b),
            teams=(team_a, team_b),
        )
        config = make_governance_config(
            exec_attention_budget=1.0,
            attention_min=0.1,
            confidence_decline_threshold=0.1,
        )
        actions = BalancedPolicy().decide(obs, config)

        attention = _attention_levels(actions)
        assert attention["A"] == pytest.approx(0.5)
        assert attention["B"] == pytest.approx(0.5)

    def test_stopped_initiatives_get_no_attention(self) -> None:
        """Stopped initiatives are excluded from attention allocation."""
        stopped_init = make_initiative_observation(
            initiative_id="init-1",
            lifecycle_state="active",
            assigned_team_id="team-1",
            quality_belief_t=0.05,
        )
        continuing_init = make_initiative_observation(
            initiative_id="init-2",
            lifecycle_state="active",
            assigned_team_id="team-2",
            quality_belief_t=0.7,
        )
        team_1 = make_team_observation(
            team_id="team-1",
            assigned_initiative_id="init-1",
        )
        team_2 = make_team_observation(
            team_id="team-2",
            assigned_initiative_id="init-2",
        )
        obs = make_governance_observation(
            initiatives=(stopped_init, continuing_init),
            teams=(team_1, team_2),
        )
        config = make_governance_config(confidence_decline_threshold=0.3)
        actions = BalancedPolicy().decide(obs, config)

        attention = _attention_levels(actions)
        assert "init-1" not in attention
        assert "init-2" in attention

    def test_multiple_initiatives_deterministic_order(self) -> None:
        """Actions are ordered by initiative_id for determinism."""
        inits = tuple(
            make_initiative_observation(
                initiative_id=f"init-{i}",
                lifecycle_state="active",
                assigned_team_id=f"team-{i}",
                quality_belief_t=0.7,
            )
            for i in range(5)
        )
        teams = tuple(
            make_team_observation(
                team_id=f"team-{i}",
                assigned_initiative_id=f"init-{i}",
            )
            for i in range(5)
        )
        obs = make_governance_observation(initiatives=inits, teams=teams)
        config = make_governance_config(confidence_decline_threshold=0.1)
        actions = BalancedPolicy().decide(obs, config)

        # ContinueStop actions should be in initiative_id order.
        ids = [a.initiative_id for a in actions.continue_stop]
        assert ids == sorted(ids)

    def test_all_initiatives_stopped_no_attention(self) -> None:
        """If all initiatives are stopped, no attention is allocated."""
        init = make_initiative_observation(
            initiative_id="init-1",
            lifecycle_state="active",
            assigned_team_id="team-1",
            quality_belief_t=0.0,
        )
        team = make_team_observation(
            team_id="team-1",
            assigned_initiative_id="init-1",
        )
        obs = make_governance_observation(
            initiatives=(init,),
            teams=(team,),
        )
        config = make_governance_config(confidence_decline_threshold=0.3)
        actions = BalancedPolicy().decide(obs, config)

        assert len(actions.set_exec_attention) == 0

    def test_portfolio_risk_blocks_assignment(self) -> None:
        """Portfolio-risk check can prevent team assignment."""
        # Initiative with large team size would exceed concentration.
        candidate = make_initiative_observation(
            initiative_id="init-1",
            lifecycle_state="unassigned",
            assigned_team_id=None,
            quality_belief_t=0.7,
            observable_ceiling=100.0,
            required_team_size=5,
        )
        idle_team = make_team_observation(
            team_id="team-1",
            assigned_initiative_id=None,
            team_size=5,
        )
        ps = make_portfolio_summary(active_labor_total=2)
        obs = make_governance_observation(
            initiatives=(candidate,),
            teams=(idle_team,),
            portfolio_summary=ps,
        )
        config = make_governance_config(
            # 5 / (2+5) = 71% > 50% cap
            max_single_initiative_labor_share=0.5,
        )
        actions = BalancedPolicy().decide(obs, config)

        # No assignment should be made.
        assert len(actions.assign_team) == 0

    def test_confidence_decline_priority_over_tam(self) -> None:
        """Confidence decline fires before TAM adequacy."""
        init = make_initiative_observation(
            initiative_id="init-1",
            lifecycle_state="active",
            assigned_team_id="team-1",
            quality_belief_t=0.1,
            observable_ceiling=100.0,
            effective_tam_patience_window=3,
            consecutive_reviews_below_tam_ratio=5,
        )
        team = make_team_observation(
            team_id="team-1",
            assigned_initiative_id="init-1",
        )
        obs = make_governance_observation(initiatives=(init,), teams=(team,))
        config = make_governance_config(confidence_decline_threshold=0.3)
        actions = BalancedPolicy().decide(obs, config)

        # Should trigger confidence_decline, not tam_adequacy.
        assert _stop_rules(actions)["init-1"] == TriggeringRule.CONFIDENCE_DECLINE


# ============================================================================
# AggressiveStopLossPolicy tests
# ============================================================================


class TestAggressiveStopLossPolicy:
    """Test the aggressive stop-loss archetype."""

    def test_stops_on_low_belief(self) -> None:
        """Same behavior as balanced — aggressiveness comes from config."""
        init = make_initiative_observation(
            initiative_id="init-1",
            lifecycle_state="active",
            assigned_team_id="team-1",
            quality_belief_t=0.25,
        )
        team = make_team_observation(
            team_id="team-1",
            assigned_initiative_id="init-1",
        )
        obs = make_governance_observation(initiatives=(init,), teams=(team,))
        config = make_governance_config(confidence_decline_threshold=0.3)
        actions = AggressiveStopLossPolicy().decide(obs, config)

        assert _stop_decisions(actions)["init-1"] == StopContinueDecision.STOP

    def test_continues_healthy_initiative(self) -> None:
        init = make_initiative_observation(
            initiative_id="init-1",
            lifecycle_state="active",
            assigned_team_id="team-1",
            quality_belief_t=0.8,
        )
        team = make_team_observation(
            team_id="team-1",
            assigned_initiative_id="init-1",
        )
        obs = make_governance_observation(initiatives=(init,), teams=(team,))
        config = make_governance_config(confidence_decline_threshold=0.3)
        actions = AggressiveStopLossPolicy().decide(obs, config)

        assert _stop_decisions(actions)["init-1"] == StopContinueDecision.CONTINUE

    def test_execution_overrun_fires(self) -> None:
        """Execution overrun triggers before TAM."""
        init = make_initiative_observation(
            initiative_id="init-1",
            lifecycle_state="active",
            assigned_team_id="team-1",
            quality_belief_t=0.7,
            execution_belief_t=0.2,
            observable_ceiling=100.0,
            effective_tam_patience_window=3,
            consecutive_reviews_below_tam_ratio=5,
        )
        team = make_team_observation(
            team_id="team-1",
            assigned_initiative_id="init-1",
        )
        obs = make_governance_observation(initiatives=(init,), teams=(team,))
        config = make_governance_config(
            confidence_decline_threshold=0.1,
            exec_overrun_threshold=0.5,
        )
        actions = AggressiveStopLossPolicy().decide(obs, config)

        assert _stop_rules(actions)["init-1"] == TriggeringRule.EXECUTION_OVERRUN


# ============================================================================
# PatientMoonshotPolicy tests
# ============================================================================


class TestPatientMoonshotPolicy:
    """Test the patient moonshot archetype."""

    def test_ignores_confidence_decline(self) -> None:
        """Patient moonshot does NOT stop on confidence decline alone."""
        init = make_initiative_observation(
            initiative_id="init-1",
            lifecycle_state="active",
            assigned_team_id="team-1",
            quality_belief_t=0.05,
        )
        team = make_team_observation(
            team_id="team-1",
            assigned_initiative_id="init-1",
        )
        obs = make_governance_observation(initiatives=(init,), teams=(team,))
        config = make_governance_config(confidence_decline_threshold=0.3)
        actions = PatientMoonshotPolicy().decide(obs, config)

        # Should continue despite very low belief.
        decisions = _stop_decisions(actions)
        assert decisions["init-1"] == StopContinueDecision.CONTINUE

    def test_still_stops_on_tam_adequacy(self) -> None:
        """Patient moonshot still respects TAM adequacy."""
        init = make_initiative_observation(
            initiative_id="init-1",
            lifecycle_state="active",
            assigned_team_id="team-1",
            quality_belief_t=0.2,
            observable_ceiling=100.0,
            effective_tam_patience_window=3,
            consecutive_reviews_below_tam_ratio=3,
        )
        team = make_team_observation(
            team_id="team-1",
            assigned_initiative_id="init-1",
        )
        obs = make_governance_observation(initiatives=(init,), teams=(team,))
        config = make_governance_config(confidence_decline_threshold=0.3)
        actions = PatientMoonshotPolicy().decide(obs, config)

        assert _stop_decisions(actions)["init-1"] == StopContinueDecision.STOP
        assert _stop_rules(actions)["init-1"] == TriggeringRule.TAM_ADEQUACY

    def test_still_stops_on_execution_overrun(self) -> None:
        init = make_initiative_observation(
            initiative_id="init-1",
            lifecycle_state="active",
            assigned_team_id="team-1",
            quality_belief_t=0.7,
            execution_belief_t=0.2,
        )
        team = make_team_observation(
            team_id="team-1",
            assigned_initiative_id="init-1",
        )
        obs = make_governance_observation(initiatives=(init,), teams=(team,))
        config = make_governance_config(exec_overrun_threshold=0.5)
        actions = PatientMoonshotPolicy().decide(obs, config)

        assert _stop_decisions(actions)["init-1"] == StopContinueDecision.STOP
        assert _stop_rules(actions)["init-1"] == TriggeringRule.EXECUTION_OVERRUN

    def test_still_stops_on_stagnation(self) -> None:
        init = make_initiative_observation(
            initiative_id="init-1",
            lifecycle_state="active",
            assigned_team_id="team-1",
            quality_belief_t=0.4,
            observable_ceiling=None,
            belief_history=(0.40, 0.40, 0.40),
        )
        team = make_team_observation(
            team_id="team-1",
            assigned_initiative_id="init-1",
        )
        obs = make_governance_observation(initiatives=(init,), teams=(team,))
        config = make_governance_config(
            default_initial_quality_belief=0.5,
            stagnation_window_staffed_ticks=3,
            stagnation_belief_change_threshold=0.02,
        )
        actions = PatientMoonshotPolicy().decide(obs, config)

        assert _stop_decisions(actions)["init-1"] == StopContinueDecision.STOP
        assert _stop_rules(actions)["init-1"] == TriggeringRule.STAGNATION

    def test_continues_declining_but_not_stagnant(self) -> None:
        """Moonshot continues a declining initiative that isn't stagnant."""
        # Not enough history for stagnation.
        init = make_initiative_observation(
            initiative_id="init-1",
            lifecycle_state="active",
            assigned_team_id="team-1",
            quality_belief_t=0.15,
            observable_ceiling=None,
            belief_history=(0.2, 0.15),
        )
        team = make_team_observation(
            team_id="team-1",
            assigned_initiative_id="init-1",
        )
        obs = make_governance_observation(initiatives=(init,), teams=(team,))
        config = make_governance_config(
            confidence_decline_threshold=0.3,
            exec_overrun_threshold=None,
            stagnation_window_staffed_ticks=5,
        )
        actions = PatientMoonshotPolicy().decide(obs, config)

        assert _stop_decisions(actions)["init-1"] == StopContinueDecision.CONTINUE

    def test_assigns_teams_to_unassigned(self) -> None:
        """Patient moonshot also assigns freed teams."""
        candidate = make_initiative_observation(
            initiative_id="init-1",
            lifecycle_state="unassigned",
            assigned_team_id=None,
            quality_belief_t=0.7,
            observable_ceiling=100.0,
        )
        idle_team = make_team_observation(
            team_id="team-1",
            assigned_initiative_id=None,
        )
        obs = make_governance_observation(
            initiatives=(candidate,),
            teams=(idle_team,),
        )
        config = make_governance_config()
        actions = PatientMoonshotPolicy().decide(obs, config)

        assignments = _assigned_teams(actions)
        assert assignments.get("team-1") == "init-1"


# ============================================================================
# Edge cases shared across archetypes
# ============================================================================


class TestEdgeCases:
    """Edge cases that apply to all archetypes."""

    def test_unassigned_initiatives_not_reviewed(self) -> None:
        """Unassigned initiatives do not receive ContinueStop actions."""
        init = make_initiative_observation(
            initiative_id="init-1",
            lifecycle_state="unassigned",
            assigned_team_id=None,
        )
        obs = make_governance_observation(initiatives=(init,))
        config = make_governance_config()
        actions = BalancedPolicy().decide(obs, config)

        assert len(actions.continue_stop) == 0

    def test_completed_initiatives_not_reviewed(self) -> None:
        init = make_initiative_observation(
            initiative_id="init-1",
            lifecycle_state="completed",
            assigned_team_id=None,
        )
        obs = make_governance_observation(initiatives=(init,))
        config = make_governance_config()
        actions = BalancedPolicy().decide(obs, config)

        assert len(actions.continue_stop) == 0

    def test_stopped_initiatives_not_reviewed(self) -> None:
        init = make_initiative_observation(
            initiative_id="init-1",
            lifecycle_state="stopped",
            assigned_team_id=None,
        )
        obs = make_governance_observation(initiatives=(init,))
        config = make_governance_config()
        actions = BalancedPolicy().decide(obs, config)

        assert len(actions.continue_stop) == 0

    def test_unstaffed_active_not_reviewed(self) -> None:
        """Active but unstaffed initiative gets no ContinueStop."""
        init = make_initiative_observation(
            initiative_id="init-1",
            lifecycle_state="active",
            assigned_team_id=None,
        )
        obs = make_governance_observation(initiatives=(init,))
        config = make_governance_config()
        actions = BalancedPolicy().decide(obs, config)

        assert len(actions.continue_stop) == 0

    def test_team_too_small_for_initiative_skips_assignment(self) -> None:
        """Team that doesn't meet required_team_size is skipped."""
        candidate = make_initiative_observation(
            initiative_id="init-1",
            lifecycle_state="unassigned",
            assigned_team_id=None,
            quality_belief_t=0.7,
            observable_ceiling=100.0,
            required_team_size=3,
        )
        small_team = make_team_observation(
            team_id="team-1",
            assigned_initiative_id=None,
        )
        obs = make_governance_observation(
            initiatives=(candidate,),
            teams=(small_team,),
        )
        config = make_governance_config()
        # team-1 has size 1, but init-1 requires size 3.
        actions = BalancedPolicy().decide(obs, config)

        assert len(actions.assign_team) == 0

    def test_newly_assigned_initiative_receives_attention(self) -> None:
        """A newly assigned initiative receives attention this tick."""
        candidate = make_initiative_observation(
            initiative_id="init-1",
            lifecycle_state="unassigned",
            assigned_team_id=None,
            quality_belief_t=0.8,
            observable_ceiling=200.0,
        )
        idle_team = make_team_observation(
            team_id="team-1",
            assigned_initiative_id=None,
        )
        obs = make_governance_observation(
            initiatives=(candidate,),
            teams=(idle_team,),
        )
        config = make_governance_config(
            exec_attention_budget=1.0,
            attention_min=0.1,
        )
        actions = BalancedPolicy().decide(obs, config)

        attention = _attention_levels(actions)
        assert "init-1" in attention
        assert attention["init-1"] > 0

    def test_triggering_rule_required_on_stop(self) -> None:
        """Every stop action has a non-None triggering_rule."""
        init = make_initiative_observation(
            initiative_id="init-1",
            lifecycle_state="active",
            assigned_team_id="team-1",
            quality_belief_t=0.05,
        )
        team = make_team_observation(
            team_id="team-1",
            assigned_initiative_id="init-1",
        )
        obs = make_governance_observation(initiatives=(init,), teams=(team,))
        config = make_governance_config(confidence_decline_threshold=0.3)
        actions = BalancedPolicy().decide(obs, config)

        for action in actions.continue_stop:
            if action.decision == StopContinueDecision.STOP:
                assert action.triggering_rule is not None

    def test_triggering_rule_none_on_continue(self) -> None:
        """Continue actions have triggering_rule=None."""
        init = make_initiative_observation(
            initiative_id="init-1",
            lifecycle_state="active",
            assigned_team_id="team-1",
            quality_belief_t=0.9,
        )
        team = make_team_observation(
            team_id="team-1",
            assigned_initiative_id="init-1",
        )
        obs = make_governance_observation(initiatives=(init,), teams=(team,))
        config = make_governance_config()
        actions = BalancedPolicy().decide(obs, config)

        for action in actions.continue_stop:
            if action.decision == StopContinueDecision.CONTINUE:
                assert action.triggering_rule is None
