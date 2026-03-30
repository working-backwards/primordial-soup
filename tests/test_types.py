"""Tests for core domain types."""

from __future__ import annotations

import dataclasses

import pytest

from primordial_soup.types import (
    MIN_EXECUTION_BELIEF,
    RAMP_EXPONENTIAL_K,
    BetaDistribution,
    CompletionLumpChannel,
    LifecycleState,
    LogNormalDistribution,
    MajorWinEventChannel,
    RampShape,
    ReassignmentTrigger,
    ResidualChannel,
    StopContinueDecision,
    TriggeringRule,
    UniformDistribution,
    ValueChannels,
)


class TestEnums:
    def test_lifecycle_state_values(self) -> None:
        assert LifecycleState.UNASSIGNED.value == "unassigned"
        assert LifecycleState.ACTIVE.value == "active"
        assert LifecycleState.STOPPED.value == "stopped"
        assert LifecycleState.COMPLETED.value == "completed"

    def test_ramp_shape_values(self) -> None:
        assert RampShape.LINEAR.value == "linear"
        assert RampShape.EXPONENTIAL.value == "exponential"

    def test_triggering_rule_values(self) -> None:
        assert TriggeringRule.TAM_ADEQUACY.value == "tam_adequacy"
        assert TriggeringRule.STAGNATION.value == "stagnation"
        assert TriggeringRule.CONFIDENCE_DECLINE.value == "confidence_decline"
        assert TriggeringRule.EXECUTION_OVERRUN.value == "execution_overrun"
        assert TriggeringRule.DISCRETIONARY.value == "discretionary"

    def test_stop_continue_decision_values(self) -> None:
        assert StopContinueDecision.CONTINUE.value == "continue"
        assert StopContinueDecision.STOP.value == "stop"

    def test_reassignment_trigger_values(self) -> None:
        assert ReassignmentTrigger.GOVERNANCE_STOP.value == "governance_stop"
        assert ReassignmentTrigger.COMPLETION.value == "completion"
        assert ReassignmentTrigger.IDLE_REASSIGNMENT.value == "idle_reassignment"


class TestConstants:
    def test_epsilon_exec_value(self) -> None:
        assert pytest.approx(0.05) == MIN_EXECUTION_BELIEF

    def test_ramp_exponential_k_value(self) -> None:
        assert pytest.approx(3.0) == RAMP_EXPONENTIAL_K


class TestDistributionSpecs:
    def test_beta_distribution_construction(self) -> None:
        d = BetaDistribution(alpha=2.0, beta=5.0)
        assert d.alpha == pytest.approx(2.0)
        assert d.beta == pytest.approx(5.0)

    def test_uniform_distribution_construction(self) -> None:
        d = UniformDistribution(low=0.1, high=0.9)
        assert d.low == pytest.approx(0.1)
        assert d.high == pytest.approx(0.9)

    def test_lognormal_distribution_construction(self) -> None:
        d = LogNormalDistribution(mean=1.0, st_dev=0.5)
        assert d.mean == pytest.approx(1.0)
        assert d.st_dev == pytest.approx(0.5)

    def test_distribution_specs_are_frozen(self) -> None:
        d = BetaDistribution(alpha=2.0, beta=5.0)
        with pytest.raises(dataclasses.FrozenInstanceError):
            d.alpha = 3.0  # type: ignore[misc]


class TestValueChannels:
    def test_completion_lump_disabled(self) -> None:
        ch = CompletionLumpChannel(enabled=False)
        assert not ch.enabled
        assert ch.realized_value is None

    def test_completion_lump_enabled(self) -> None:
        ch = CompletionLumpChannel(enabled=True, realized_value=100.0)
        assert ch.enabled
        assert ch.realized_value == pytest.approx(100.0)

    def test_residual_defaults(self) -> None:
        ch = ResidualChannel(enabled=False)
        assert ch.activation_state == "completed"
        assert ch.residual_rate == pytest.approx(0.0)
        assert ch.residual_decay == pytest.approx(0.0)

    def test_residual_enabled(self) -> None:
        ch = ResidualChannel(enabled=True, residual_rate=5.0, residual_decay=0.02)
        assert ch.enabled
        assert ch.residual_rate == pytest.approx(5.0)
        assert ch.residual_decay == pytest.approx(0.02)

    def test_major_win_defaults(self) -> None:
        ch = MajorWinEventChannel(enabled=False)
        assert not ch.is_major_win

    def test_major_win_enabled(self) -> None:
        ch = MajorWinEventChannel(enabled=True, is_major_win=True)
        assert ch.enabled
        assert ch.is_major_win

    def test_value_channels_composition(self) -> None:
        vc = ValueChannels(
            completion_lump=CompletionLumpChannel(enabled=True, realized_value=50.0),
            residual=ResidualChannel(enabled=True, residual_rate=2.0, residual_decay=0.01),
            major_win_event=MajorWinEventChannel(enabled=True, is_major_win=True),
        )
        assert vc.completion_lump.enabled
        assert vc.residual.enabled
        assert vc.major_win_event.is_major_win

    def test_value_channels_frozen(self) -> None:
        vc = ValueChannels(
            completion_lump=CompletionLumpChannel(enabled=False),
            residual=ResidualChannel(enabled=False),
            major_win_event=MajorWinEventChannel(enabled=False),
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            vc.completion_lump = CompletionLumpChannel(enabled=True)  # type: ignore[misc]
