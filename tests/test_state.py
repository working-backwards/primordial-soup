"""Tests for simulation state types."""

from __future__ import annotations

import dataclasses

import pytest

from primordial_soup.state import InitiativeState, TeamState, WorldState
from primordial_soup.types import LifecycleState


def make_initiative_state(
    *,
    initiative_id: str = "init-1",
    lifecycle_state: LifecycleState = LifecycleState.ACTIVE,
    assigned_team_id: str | None = "team-1",
    quality_belief_t: float = 0.5,
    execution_belief_t: float | None = None,
    executive_attention_t: float = 0.0,
    staffed_tick_count: int = 0,
    ticks_since_assignment: int = 0,
    age_ticks: int = 0,
    completed_tick: int | None = None,
) -> InitiativeState:
    """Build a valid InitiativeState with sensible defaults."""
    return InitiativeState(
        initiative_id=initiative_id,
        lifecycle_state=lifecycle_state,
        assigned_team_id=assigned_team_id,
        quality_belief_t=quality_belief_t,
        execution_belief_t=execution_belief_t,
        executive_attention_t=executive_attention_t,
        staffed_tick_count=staffed_tick_count,
        ticks_since_assignment=ticks_since_assignment,
        age_ticks=age_ticks,
        cumulative_value_realized=0.0,
        cumulative_lump_value_realized=0.0,
        cumulative_residual_value_realized=0.0,
        cumulative_labor_invested=0.0,
        cumulative_attention_invested=0.0,
        belief_history=(),
        review_count=0,
        consecutive_reviews_below_tam_ratio=0,
        residual_activated=False,
        residual_activation_tick=None,
        major_win_surfaced=False,
        major_win_tick=None,
        completed_tick=completed_tick,
    )


class TestInitiativeState:
    def test_construction(self) -> None:
        state = make_initiative_state()
        assert state.initiative_id == "init-1"
        assert state.lifecycle_state == LifecycleState.ACTIVE
        assert state.quality_belief_t == pytest.approx(0.5)

    def test_frozen(self) -> None:
        state = make_initiative_state()
        with pytest.raises(dataclasses.FrozenInstanceError):
            state.quality_belief_t = 0.8  # type: ignore[misc]

    def test_replace_creates_new_instance(self) -> None:
        state = make_initiative_state(quality_belief_t=0.5)
        updated = dataclasses.replace(state, quality_belief_t=0.7)
        assert state.quality_belief_t == pytest.approx(0.5)
        assert updated.quality_belief_t == pytest.approx(0.7)
        assert state is not updated

    def test_belief_history_as_tuple(self) -> None:
        state = make_initiative_state()
        assert state.belief_history == ()
        # Simulate appending a belief and trimming to window
        new_history = state.belief_history + (0.5,)
        updated = dataclasses.replace(state, belief_history=new_history)
        assert updated.belief_history == (0.5,)

    def test_unassigned_state(self) -> None:
        state = make_initiative_state(
            lifecycle_state=LifecycleState.UNASSIGNED,
            assigned_team_id=None,
        )
        assert state.assigned_team_id is None

    def test_completed_state(self) -> None:
        state = make_initiative_state(
            lifecycle_state=LifecycleState.COMPLETED,
            completed_tick=50,
        )
        assert state.completed_tick == 50


class TestTeamState:
    def test_construction(self) -> None:
        team = TeamState(team_id="team-1", team_size=3, assigned_initiative_id="init-1")
        assert team.team_id == "team-1"
        assert team.team_size == 3

    def test_idle_team(self) -> None:
        team = TeamState(team_id="team-2", team_size=2, assigned_initiative_id=None)
        assert team.assigned_initiative_id is None

    def test_frozen(self) -> None:
        team = TeamState(team_id="team-1", team_size=1, assigned_initiative_id=None)
        with pytest.raises(dataclasses.FrozenInstanceError):
            team.assigned_initiative_id = "init-1"  # type: ignore[misc]


class TestWorldState:
    def test_construction(self) -> None:
        world = WorldState(
            tick=0,
            initiative_states=(make_initiative_state(),),
            team_states=(
                TeamState(team_id="team-1", team_size=1, assigned_initiative_id="init-1"),
            ),
            portfolio_capability=1.0,
        )
        assert world.tick == 0
        assert len(world.initiative_states) == 1
        assert world.portfolio_capability == pytest.approx(1.0)

    def test_frozen(self) -> None:
        world = WorldState(
            tick=0,
            initiative_states=(),
            team_states=(),
            portfolio_capability=1.0,
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            world.tick = 1  # type: ignore[misc]

    def test_portfolio_capability_initialized_at_one(self) -> None:
        world = WorldState(
            tick=0,
            initiative_states=(),
            team_states=(),
            portfolio_capability=1.0,
        )
        assert world.portfolio_capability == pytest.approx(1.0)
