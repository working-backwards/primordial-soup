"""Governance policy archetypes.

This module composes the decision primitives from governance.py into
complete governance strategies (archetypes). Each archetype implements
the GovernancePolicy protocol: a decide() method that receives a
GovernanceObservation and GovernanceConfig and returns a GovernanceActions
vector.

Archetypes choose strategies; they do not duplicate the mechanics of
stop evaluation, reassignment, or ramp application. Shared execution
logic lives in governance.py.

Three canonical archetypes are provided:

- **BalancedPolicy**: The canonical reference baseline. Applies all
  four stop rules, uses equal attention, ranks unassigned initiatives
  by prize density then belief. Optionally applies portfolio-risk
  controls when configured.

- **AggressiveStopLossPolicy**: Lower confidence threshold, tighter
  execution overrun tolerance. Stops earlier and more aggressively.
  Favors reallocating freed teams quickly.

- **PatientMoonshotPolicy**: Disables confidence-decline stopping,
  uses higher patience windows. Holds longer on high-potential
  initiatives. Less sensitive to short-term belief declines.

Per governance.md policy interface, interfaces.md Policy API, and
governance.md selection and portfolio management semantics.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Protocol

from primordial_soup.actions import (
    AssignTeamAction,
    ContinueStopAction,
    GovernanceActions,
    SetExecAttentionAction,
)
from primordial_soup.governance import (
    classify_initiative_bucket,
    compute_current_portfolio_mix,
    compute_equal_attention,
    rank_unassigned_initiatives,
    should_stop_confidence_decline,
    should_stop_execution_overrun,
    should_stop_stagnation,
    should_stop_tam_adequacy,
    would_assignment_exceed_concentration,
    would_assignment_exceed_low_quality_share,
)
from primordial_soup.types import (
    StopContinueDecision,
    TriggeringRule,
)

if TYPE_CHECKING:
    from primordial_soup.config import GovernanceConfig
    from primordial_soup.observation import (
        GovernanceObservation,
        InitiativeObservation,
        TeamObservation,
    )

logger = logging.getLogger(__name__)


# ============================================================================
# GovernancePolicy protocol
# ============================================================================


class GovernancePolicy(Protocol):
    """Protocol for governance policy implementations.

    A governance policy is a pure decision function. It receives
    the policy-visible observation bundle and the immutable governance
    parameters, and returns a complete action vector for the tick.

    The policy must not maintain private mutable state across ticks.
    All evolving memory lives in engine-owned WorldState and is surfaced
    through GovernanceObservation.

    Per interfaces.md Policy API and governance.md policy interface.
    """

    def decide(
        self,
        observation: GovernanceObservation,
        config: GovernanceConfig,
    ) -> GovernanceActions:
        """Produce an action vector for the current tick.

        Args:
            observation: Complete policy-visible state for this tick.
                Includes belief_history on each InitiativeObservation
                and team_size on each TeamObservation.
            config: Immutable governance parameters for this run.

        Returns:
            GovernanceActions containing all ContinueStop, AssignTeam,
            and SetExecAttention actions for this tick.
        """
        ...


# ============================================================================
# Internal helpers shared by archetypes
# ============================================================================


def _get_active_staffed(
    observation: GovernanceObservation,
) -> tuple[InitiativeObservation, ...]:
    """Extract active staffed initiatives, sorted by id for determinism.

    Per governance.md: every active staffed initiative must receive an
    explicit ContinueStop decision. There is no abstain option.
    """
    active_staffed = [
        init
        for init in observation.initiatives
        if init.lifecycle_state == "active" and init.assigned_team_id is not None
    ]
    # Deterministic order by initiative_id.
    active_staffed.sort(key=lambda i: i.initiative_id)
    return tuple(active_staffed)


def _get_available_teams(
    observation: GovernanceObservation,
) -> tuple[TeamObservation, ...]:
    """Extract teams available for assignment, sorted by id for determinism.

    A team is available if it has no current assignment. Teams freed by
    stop decisions this tick are identified by checking which stopped
    initiatives had teams.
    """
    available = [team for team in observation.teams if team.assigned_initiative_id is None]
    available.sort(key=lambda t: t.team_id)
    return tuple(available)


def _find_team_for_initiative(
    initiative: InitiativeObservation,
    available_teams: list[TeamObservation],
) -> TeamObservation | None:
    """Find the first available team that can staff the initiative.

    Assignment requires team_size >= initiative.required_team_size.
    Uses the first match in the already-sorted available_teams list
    for determinism.

    Args:
        initiative: The candidate initiative to assign a team to.
        available_teams: Mutable list of teams not yet assigned.

    Returns:
        The matched TeamObservation, or None if no team fits.
    """
    for team in available_teams:
        if team.team_size >= initiative.required_team_size:
            return team
    return None


def _collect_stop_actions_balanced(
    active_staffed: tuple[InitiativeObservation, ...],
    config: GovernanceConfig,
) -> tuple[tuple[ContinueStopAction, ...], set[str]]:
    """Evaluate stop/continue for each active staffed initiative.

    Applies all four canonical stop rules in priority order:
    1. Confidence decline (lowest belief → stop first)
    2. Execution overrun
    3. TAM adequacy
    4. Stagnation

    Returns the action tuple and the set of stopped initiative ids.

    Args:
        active_staffed: Active staffed initiatives sorted by id.
        config: Governance config with thresholds.

    Returns:
        Tuple of (actions, stopped_ids).
    """
    actions = []
    stopped_ids: set[str] = set()

    for initiative in active_staffed:
        # Evaluate stop rules in priority order.
        # Per governance.md section 4 (combined rule application).
        triggering_rule: TriggeringRule | None = None

        if should_stop_confidence_decline(initiative, config):
            triggering_rule = TriggeringRule.CONFIDENCE_DECLINE
        elif should_stop_execution_overrun(initiative, config):
            triggering_rule = TriggeringRule.EXECUTION_OVERRUN
        elif should_stop_tam_adequacy(initiative):
            triggering_rule = TriggeringRule.TAM_ADEQUACY
        elif should_stop_stagnation(initiative, config):
            triggering_rule = TriggeringRule.STAGNATION

        if triggering_rule is not None:
            actions.append(
                ContinueStopAction(
                    initiative_id=initiative.initiative_id,
                    decision=StopContinueDecision.STOP,
                    triggering_rule=triggering_rule,
                )
            )
            stopped_ids.add(initiative.initiative_id)
        else:
            actions.append(
                ContinueStopAction(
                    initiative_id=initiative.initiative_id,
                    decision=StopContinueDecision.CONTINUE,
                )
            )

    return tuple(actions), stopped_ids


def _rerank_for_mix_targets(
    ranked: tuple[InitiativeObservation, ...],
    observation: GovernanceObservation,
    stopped_ids: set[str],
    config: GovernanceConfig,
) -> tuple[InitiativeObservation, ...]:
    """Re-rank candidates to prefer under-target buckets when mix targets are set.

    This is a soft preference layer: candidates whose bucket is under-target
    (relative to portfolio_mix_targets) are promoted ahead of at-or-over-target
    candidates, preserving the existing rank within each group.

    If no mix targets are configured, returns the input unchanged.

    Per portfolio_allocation_targets_proposal.md §5: the preference is a soft
    bias on selection order, not a hard block. The policy never blocks an
    assignment to enforce the mix — it only biases selection order.

    Args:
        ranked: Candidates already ranked by the standard selection logic.
        observation: The full governance observation.
        stopped_ids: Initiative ids being stopped this tick.
        config: Governance config containing portfolio_mix_targets.

    Returns:
        Re-ranked candidates with under-target bucket members first.
    """
    if config.portfolio_mix_targets is None:
        return ranked

    pmt = config.portfolio_mix_targets
    target_mix = pmt.targets_dict

    # Compute current bucket labor shares (after stops, before new assignments).
    current_mix = compute_current_portfolio_mix(observation.initiatives, stopped_ids)

    # Partition candidates into under-target and at-or-over-target groups.
    #
    # Uncategorized initiatives (generation_tag is None or non-canonical)
    # have no target in the mix — target_mix.get returns 0.0. Since their
    # current share is always >= 0.0 - tolerance, they land in the
    # at-or-over-target group. This is deliberate: uncategorized work is
    # a residual bucket that does not participate in mix-target biasing.
    # It is still assignable — just not prioritized by mix targets.
    under_target: list[InitiativeObservation] = []
    at_target: list[InitiativeObservation] = []

    for candidate in ranked:
        bucket = classify_initiative_bucket(candidate)
        target = target_mix.get(bucket, 0.0)
        current = current_mix.get(bucket, 0.0)

        # Under-target: current share is below target minus tolerance.
        if current < target - pmt.tolerance:
            under_target.append(candidate)
        else:
            at_target.append(candidate)

    # Under-target candidates get priority; existing rank preserved within
    # each group for determinism.
    return tuple(under_target) + tuple(at_target)


def _assign_freed_teams(
    observation: GovernanceObservation,
    stopped_ids: set[str],
    config: GovernanceConfig,
) -> tuple[AssignTeamAction, ...]:
    """Assign freed and idle teams to the best unassigned initiatives.

    Teams freed by stops this tick plus any already-idle teams are
    matched against ranked unassigned initiatives.

    When portfolio_mix_targets is configured in GovernanceConfig, the
    ranked candidate list is re-sorted to prefer initiatives whose
    bucket is under-target. This is a soft preference: it biases
    selection order without blocking any assignment.

    Args:
        observation: The full governance observation. Team sizes are
            available on each TeamObservation.team_size.
        stopped_ids: Initiative ids stopped this tick.
        config: Governance config (for portfolio checks and mix targets).

    Returns:
        Tuple of AssignTeamAction for new assignments.
    """
    # Collect all teams that will be available after stops are applied.
    # Currently idle teams + teams freed from stopped initiatives.
    available = []
    for team in observation.teams:
        if team.assigned_initiative_id is None or team.assigned_initiative_id in stopped_ids:
            available.append(team)
    # Deterministic order by team_id.
    available.sort(key=lambda t: t.team_id)

    # Rank all unassigned initiatives for selection.
    ranked = rank_unassigned_initiatives(observation.initiatives)

    # If portfolio mix targets are configured, re-rank to prefer
    # candidates whose bucket is under-target. This is a soft bias
    # layered on top of the existing ranked selection.
    ranked = _rerank_for_mix_targets(ranked, observation, stopped_ids, config)

    assignments = []
    available_list = list(available)

    for candidate in ranked:
        if not available_list:
            break

        # Portfolio-risk checks: skip if assignment would violate caps.
        if would_assignment_exceed_concentration(candidate, observation.portfolio_summary, config):
            continue
        if would_assignment_exceed_low_quality_share(
            candidate, observation.portfolio_summary, config
        ):
            continue

        matched_team = _find_team_for_initiative(candidate, available_list)
        if matched_team is not None:
            assignments.append(
                AssignTeamAction(
                    team_id=matched_team.team_id,
                    initiative_id=candidate.initiative_id,
                )
            )
            available_list.remove(matched_team)

    return tuple(assignments)


def _allocate_equal_attention(
    active_staffed: tuple[InitiativeObservation, ...],
    stopped_ids: set[str],
    new_assignments: tuple[AssignTeamAction, ...],
    config: GovernanceConfig,
) -> tuple[SetExecAttentionAction, ...]:
    """Allocate equal attention to all continuing + newly assigned initiatives.

    Initiatives stopped this tick do not receive attention.
    Newly assigned initiatives receive attention starting this tick.

    Args:
        active_staffed: All initiatives that were active+staffed entering
            this tick's governance decision.
        stopped_ids: Initiatives stopped this tick (excluded).
        new_assignments: New AssignTeam actions (newly staffed initiatives
            also receive attention).
        config: Governance config with attention budget and bounds.

    Returns:
        Tuple of SetExecAttentionAction for each initiative receiving
        attention.
    """
    # Initiatives continuing from this tick.
    continuing_ids = {
        init.initiative_id for init in active_staffed if init.initiative_id not in stopped_ids
    }
    # Add newly assigned initiatives.
    newly_assigned_ids = {
        action.initiative_id for action in new_assignments if action.initiative_id is not None
    }
    all_receiving_attention = continuing_ids | newly_assigned_ids

    count = len(all_receiving_attention)
    if count == 0:
        return ()

    attention_level = compute_equal_attention(count, config)

    # Deterministic ordering by initiative_id.
    sorted_ids = sorted(all_receiving_attention)
    return tuple(
        SetExecAttentionAction(
            initiative_id=init_id,
            attention=attention_level,
        )
        for init_id in sorted_ids
    )


# ============================================================================
# Balanced policy (canonical reference baseline)
# ============================================================================


class BalancedPolicy:
    """Canonical reference baseline governance archetype.

    Applies all four stop rules (confidence decline, execution overrun,
    TAM adequacy, stagnation). Uses equal attention allocation. Ranks
    unassigned initiatives by prize density then belief. Optionally
    applies portfolio-risk controls when configured in GovernanceConfig.

    This is the default policy for canonical experiments.
    """

    def decide(
        self,
        observation: GovernanceObservation,
        config: GovernanceConfig,
    ) -> GovernanceActions:
        """Produce balanced governance actions for the current tick.

        Args:
            observation: Complete policy-visible state. Includes
                belief_history on each InitiativeObservation and
                team_size on each TeamObservation.
            config: Immutable governance parameters.

        Returns:
            Complete GovernanceActions for this tick.
        """
        # --- Step 1: Stop / Continue decisions ---
        active_staffed = _get_active_staffed(observation)
        stop_actions, stopped_ids = _collect_stop_actions_balanced(active_staffed, config)

        # --- Step 2: Assign freed and idle teams ---
        assign_actions = _assign_freed_teams(observation, stopped_ids, config)

        # --- Step 3: Attention allocation ---
        attention_actions = _allocate_equal_attention(
            active_staffed, stopped_ids, assign_actions, config
        )

        return GovernanceActions(
            continue_stop=stop_actions,
            assign_team=assign_actions,
            set_exec_attention=attention_actions,
        )


# ============================================================================
# Aggressive stop-loss policy
# ============================================================================


class AggressiveStopLossPolicy:
    """Aggressive stop-loss governance archetype.

    Applies all four stop rules with a lower bar: if confidence decline
    OR execution overrun triggers, stops immediately. More aggressive
    than Balanced in cutting losses. Uses the same attention and
    selection logic as Balanced.

    Key behavioral differences from Balanced:
    - Checks execution overrun before TAM adequacy (prioritizes cost
      control over prize patience).
    - Applies the same four rules but a policy config with tighter
      thresholds would produce earlier stops.
    """

    def decide(
        self,
        observation: GovernanceObservation,
        config: GovernanceConfig,
    ) -> GovernanceActions:
        """Produce aggressive stop-loss governance actions.

        Uses the same evaluation as BalancedPolicy — the aggressiveness
        comes from the GovernanceConfig thresholds, not from different
        rule logic. This ensures the study compares governance *settings*
        rather than different rule implementations.

        Args:
            observation: Complete policy-visible state. Includes
                belief_history on each InitiativeObservation and
                team_size on each TeamObservation.
            config: Governance parameters (expected to have tighter
                thresholds than the balanced baseline).

        Returns:
            Complete GovernanceActions for this tick.
        """
        active_staffed = _get_active_staffed(observation)

        # Same stop logic as balanced but with execution overrun
        # checked before TAM (prioritize cost control).
        actions = []
        stopped_ids: set[str] = set()

        for initiative in active_staffed:
            triggering_rule: TriggeringRule | None = None

            # Priority: confidence decline → execution overrun → TAM → stagnation.
            if should_stop_confidence_decline(initiative, config):
                triggering_rule = TriggeringRule.CONFIDENCE_DECLINE
            elif should_stop_execution_overrun(initiative, config):
                triggering_rule = TriggeringRule.EXECUTION_OVERRUN
            elif should_stop_tam_adequacy(initiative):
                triggering_rule = TriggeringRule.TAM_ADEQUACY
            elif should_stop_stagnation(initiative, config):
                triggering_rule = TriggeringRule.STAGNATION

            if triggering_rule is not None:
                actions.append(
                    ContinueStopAction(
                        initiative_id=initiative.initiative_id,
                        decision=StopContinueDecision.STOP,
                        triggering_rule=triggering_rule,
                    )
                )
                stopped_ids.add(initiative.initiative_id)
            else:
                actions.append(
                    ContinueStopAction(
                        initiative_id=initiative.initiative_id,
                        decision=StopContinueDecision.CONTINUE,
                    )
                )

        stop_actions = tuple(actions)

        assign_actions = _assign_freed_teams(observation, stopped_ids, config)
        attention_actions = _allocate_equal_attention(
            active_staffed, stopped_ids, assign_actions, config
        )

        return GovernanceActions(
            continue_stop=stop_actions,
            assign_team=assign_actions,
            set_exec_attention=attention_actions,
        )


# ============================================================================
# Patient moonshot policy
# ============================================================================


class PatientMoonshotPolicy:
    """Patient moonshot governance archetype.

    Holds longer on high-potential initiatives. Disables confidence
    decline as a stop trigger (relies only on TAM adequacy, stagnation,
    and execution overrun for stops). Less sensitive to short-term
    belief declines.

    Key behavioral differences from Balanced:
    - Does NOT apply confidence_decline_threshold as a stop rule.
    - Only stops on TAM adequacy, stagnation, or execution overrun.
    - Uses the same attention and selection logic as Balanced.
    """

    def decide(
        self,
        observation: GovernanceObservation,
        config: GovernanceConfig,
    ) -> GovernanceActions:
        """Produce patient moonshot governance actions.

        Skips the confidence-decline stop rule entirely. Even if
        config.confidence_decline_threshold is set, this archetype
        ignores it. The study models this as a governance philosophy
        that tolerates short-term belief declines in pursuit of
        long-term discoveries.

        Args:
            observation: Complete policy-visible state. Includes
                belief_history on each InitiativeObservation and
                team_size on each TeamObservation.
            config: Governance parameters.

        Returns:
            Complete GovernanceActions for this tick.
        """
        active_staffed = _get_active_staffed(observation)

        actions = []
        stopped_ids: set[str] = set()

        for initiative in active_staffed:
            triggering_rule: TriggeringRule | None = None

            # Patient moonshot: skip confidence decline entirely.
            # Priority: execution overrun → TAM adequacy → stagnation.
            if should_stop_execution_overrun(initiative, config):
                triggering_rule = TriggeringRule.EXECUTION_OVERRUN
            elif should_stop_tam_adequacy(initiative):
                triggering_rule = TriggeringRule.TAM_ADEQUACY
            elif should_stop_stagnation(initiative, config):
                triggering_rule = TriggeringRule.STAGNATION

            if triggering_rule is not None:
                actions.append(
                    ContinueStopAction(
                        initiative_id=initiative.initiative_id,
                        decision=StopContinueDecision.STOP,
                        triggering_rule=triggering_rule,
                    )
                )
                stopped_ids.add(initiative.initiative_id)
            else:
                actions.append(
                    ContinueStopAction(
                        initiative_id=initiative.initiative_id,
                        decision=StopContinueDecision.CONTINUE,
                    )
                )

        stop_actions = tuple(actions)

        assign_actions = _assign_freed_teams(observation, stopped_ids, config)
        attention_actions = _allocate_equal_attention(
            active_staffed, stopped_ids, assign_actions, config
        )

        return GovernanceActions(
            continue_stop=stop_actions,
            assign_team=assign_actions,
            set_exec_attention=attention_actions,
        )
