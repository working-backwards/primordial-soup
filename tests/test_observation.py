"""Tests for observation boundary types.

Covers PortfolioSummary, InitiativeObservation (with required_team_size),
GovernanceObservation (with portfolio_summary), and TeamObservation.
"""

from __future__ import annotations

import dataclasses

import pytest

from conftest import (
    make_governance_observation,
    make_initiative_observation,
    make_portfolio_summary,
    make_team_observation,
)
from primordial_soup.observation import (
    PortfolioSummary,
)


class TestPortfolioSummary:
    """Verify PortfolioSummary construction and immutability."""

    def test_default_construction(self) -> None:
        ps = make_portfolio_summary()
        assert ps.active_labor_total == 0
        assert ps.active_labor_below_quality_threshold is None
        assert ps.low_quality_belief_labor_share is None
        assert ps.max_single_initiative_labor_share is None

    def test_with_active_labor(self) -> None:
        ps = make_portfolio_summary(
            active_labor_total=10,
            active_labor_below_quality_threshold=3,
            low_quality_belief_labor_share=0.3,
            max_single_initiative_labor_share=0.4,
        )
        assert ps.active_labor_total == 10
        assert ps.active_labor_below_quality_threshold == 3
        assert ps.low_quality_belief_labor_share == pytest.approx(0.3)
        assert ps.max_single_initiative_labor_share == pytest.approx(0.4)

    def test_frozen(self) -> None:
        ps = make_portfolio_summary()
        with pytest.raises(dataclasses.FrozenInstanceError):
            ps.active_labor_total = 5  # type: ignore[misc]


class TestInitiativeObservation:
    """Verify InitiativeObservation includes required_team_size."""

    def test_default_construction(self) -> None:
        obs = make_initiative_observation()
        assert obs.initiative_id == "init-1"
        assert obs.required_team_size == 1

    def test_required_team_size_custom(self) -> None:
        obs = make_initiative_observation(required_team_size=3)
        assert obs.required_team_size == 3

    def test_bounded_prize_initiative(self) -> None:
        """Bounded-prize initiative has observable_ceiling and TAM window."""
        obs = make_initiative_observation(
            observable_ceiling=200.0,
            effective_tam_patience_window=8,
        )
        assert obs.observable_ceiling == pytest.approx(200.0)
        assert obs.effective_tam_patience_window == 8

    def test_frozen(self) -> None:
        obs = make_initiative_observation()
        with pytest.raises(dataclasses.FrozenInstanceError):
            obs.quality_belief_t = 0.9  # type: ignore[misc]


class TestGovernanceObservation:
    """Verify GovernanceObservation includes portfolio_summary."""

    def test_default_construction(self) -> None:
        obs = make_governance_observation()
        assert obs.tick == 0
        assert isinstance(obs.portfolio_summary, PortfolioSummary)
        assert obs.portfolio_summary.active_labor_total == 0

    def test_with_initiatives_and_portfolio(self) -> None:
        """Full observation with initiatives and portfolio summary."""
        init_obs = make_initiative_observation(
            initiative_id="init-A",
            quality_belief_t=0.7,
            required_team_size=2,
        )
        team_obs = make_team_observation(
            team_id="team-1",
            assigned_initiative_id="init-A",
            available_next_tick=False,
        )
        ps = make_portfolio_summary(
            active_labor_total=2,
            max_single_initiative_labor_share=1.0,
        )
        obs = make_governance_observation(
            tick=5,
            initiatives=(init_obs,),
            teams=(team_obs,),
            portfolio_summary=ps,
        )
        assert obs.tick == 5
        assert len(obs.initiatives) == 1
        assert obs.initiatives[0].required_team_size == 2
        assert obs.portfolio_summary.active_labor_total == 2

    def test_frozen(self) -> None:
        obs = make_governance_observation()
        with pytest.raises(dataclasses.FrozenInstanceError):
            obs.tick = 10  # type: ignore[misc]


class TestTeamObservation:
    """Verify TeamObservation construction."""

    def test_default_construction(self) -> None:
        obs = make_team_observation()
        assert obs.team_id == "team-1"
        assert obs.assigned_initiative_id is None
        assert obs.available_next_tick is True

    def test_assigned_team(self) -> None:
        obs = make_team_observation(
            assigned_initiative_id="init-1",
            available_next_tick=False,
        )
        assert obs.assigned_initiative_id == "init-1"
        assert obs.available_next_tick is False
