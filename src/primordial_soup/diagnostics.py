"""Ground-truth diagnostic metrics for post-hoc analysis.

This module provides five pure diagnostic functions that exploit the
simulator's ground-truth observability to assess governance quality.
These metrics are NOT available to governance during the run — they
use latent state (is_major_win, latent_quality) that is hidden behind
the observation boundary. They exist for post-hoc analysis only.

The five metrics:

1. **False-stop rate on eventual major wins** — among right-tail
   initiatives where is_major_win == True, what fraction were stopped?

2. **Survival curve to revelation** — fraction of right-tail
   initiatives still alive by staffed tick t. Separate curves for
   all RT vs. major-win-eligible.

3. **Belief-at-stop distribution** — quality_belief_t at the moment
   major-win-eligible initiatives are stopped.

4. **Attention-conditioned false negatives** — false-stop rate
   bucketed by mean attention in the window leading up to the stop.

5. **Hazard of stop by staffed tick** — stop frequency by staffed-tick
   bin. Tests whether stops cluster before belief-maturation window.

Design reference: docs/implementation/calibration_plan.md §A.2.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from primordial_soup.config import ResolvedInitiativeConfig
    from primordial_soup.reporting import RunResult

logger = logging.getLogger(__name__)


# ===========================================================================
# Helper functions
# ===========================================================================


def is_right_tail(config: ResolvedInitiativeConfig) -> bool:
    """Return True if the initiative is a right-tail type.

    Args:
        config: Resolved initiative configuration.

    Returns:
        True if generation_tag == "right_tail".
    """
    return config.generation_tag == "right_tail"


def is_major_win_eligible(config: ResolvedInitiativeConfig) -> bool:
    """Return True if the initiative is a major-win-eligible right-tail.

    An initiative is major-win-eligible if its major_win_event channel
    is enabled AND is_major_win is True (latent quality >= threshold).

    Args:
        config: Resolved initiative configuration.

    Returns:
        True if the initiative would surface a major win on completion.
    """
    mw = config.value_channels.major_win_event
    return mw.enabled and mw.is_major_win


def build_config_map(
    result: RunResult,
) -> dict[str, ResolvedInitiativeConfig]:
    """Build initiative_id → ResolvedInitiativeConfig lookup from a RunResult.

    Args:
        result: A completed RunResult with manifest.

    Returns:
        Dict mapping initiative_id to its resolved config.
    """
    return {cfg.initiative_id: cfg for cfg in result.manifest.resolved_initiatives}


# ===========================================================================
# Metric 1: False-stop rate on eventual major wins
# ===========================================================================


@dataclass(frozen=True)
class FalseStopRateResult:
    """Result of false-stop rate computation.

    Attributes:
        total_major_win_eligible: Total right-tail initiatives in the
            pool with is_major_win == True.
        stopped_major_win_eligible: Number of those that were stopped
            by governance.
        completed_major_win_eligible: Number that completed (surfaced).
        false_stop_rate: Fraction stopped / total eligible. None if
            total_major_win_eligible == 0.
    """

    total_major_win_eligible: int
    stopped_major_win_eligible: int
    completed_major_win_eligible: int
    false_stop_rate: float | None


def compute_false_stop_rate(result: RunResult) -> FalseStopRateResult:
    """Compute the false-stop rate on eventual major wins.

    Among right-tail initiatives where is_major_win == True in the
    resolved config, what fraction were stopped by governance?

    This is a ground-truth metric: governance cannot observe is_major_win.
    A high false-stop rate means governance is killing initiatives that
    would have been breakthroughs if pursued to completion.

    Args:
        result: A completed RunResult with event logs and manifest.

    Returns:
        FalseStopRateResult with the false-stop rate and counts.
    """
    # Find all major-win-eligible initiatives in the pool.
    eligible_ids: set[str] = set()
    for cfg in result.manifest.resolved_initiatives:
        if is_major_win_eligible(cfg):
            eligible_ids.add(cfg.initiative_id)

    total_eligible = len(eligible_ids)

    # Count how many were stopped.
    stopped_eligible = 0
    if result.stop_event_log is not None:
        stopped_ids = {e.initiative_id for e in result.stop_event_log}
        stopped_eligible = len(eligible_ids & stopped_ids)

    # Count how many completed (surfaced as major wins).
    completed_eligible = 0
    if result.major_win_event_log is not None:
        completed_ids = {e.initiative_id for e in result.major_win_event_log}
        completed_eligible = len(eligible_ids & completed_ids)

    false_stop_rate: float | None = None
    if total_eligible > 0:
        false_stop_rate = stopped_eligible / total_eligible

    return FalseStopRateResult(
        total_major_win_eligible=total_eligible,
        stopped_major_win_eligible=stopped_eligible,
        completed_major_win_eligible=completed_eligible,
        false_stop_rate=false_stop_rate,
    )


# ===========================================================================
# Metric 2: Survival curve to revelation
# ===========================================================================


@dataclass(frozen=True)
class SurvivalCurveResult:
    """Result of survival curve computation.

    Curves are represented as tuples of (staffed_tick, fraction_alive)
    pairs, sorted by staffed_tick. fraction_alive starts at 1.0 and
    is monotonically non-increasing.

    Attributes:
        all_rt_curve: Survival curve for all right-tail initiatives.
        eligible_curve: Survival curve for major-win-eligible RT only.
        all_rt_count: Total right-tail initiatives that were ever staffed.
        eligible_count: Total major-win-eligible that were ever staffed.
    """

    all_rt_curve: tuple[tuple[int, float], ...]
    eligible_curve: tuple[tuple[int, float], ...]
    all_rt_count: int
    eligible_count: int


def compute_survival_curves(result: RunResult) -> SurvivalCurveResult:
    """Compute survival curves for right-tail initiatives.

    The survival curve shows the fraction of RT initiatives still alive
    (not stopped) as a function of staffed ticks. An initiative "dies"
    at the staffed-tick count recorded in its StopEvent.

    Initiatives that complete or are never assigned are excluded from
    the survival curve (they are censored, not stopped).

    Args:
        result: A completed RunResult with event logs and manifest.

    Returns:
        SurvivalCurveResult with curves for all RT and eligible-only.
    """
    # Identify all right-tail initiatives and major-win-eligible ones.
    rt_ids: set[str] = set()
    eligible_ids: set[str] = set()
    for cfg in result.manifest.resolved_initiatives:
        if is_right_tail(cfg):
            rt_ids.add(cfg.initiative_id)
            if is_major_win_eligible(cfg):
                eligible_ids.add(cfg.initiative_id)

    # Collect stop events for RT initiatives. StopEvent has staffed_ticks.
    rt_stop_ticks: list[int] = []
    eligible_stop_ticks: list[int] = []
    stopped_rt_ids: set[str] = set()
    stopped_eligible_ids: set[str] = set()

    if result.stop_event_log is not None:
        for event in result.stop_event_log:
            if event.initiative_id in rt_ids:
                rt_stop_ticks.append(event.staffed_ticks)
                stopped_rt_ids.add(event.initiative_id)
            if event.initiative_id in eligible_ids:
                eligible_stop_ticks.append(event.staffed_ticks)
                stopped_eligible_ids.add(event.initiative_id)

    # Build survival curves. Only count initiatives that were staffed
    # (had at least one staffed tick = appeared in a stop or completion
    # event). Initiatives that were never assigned are not in the
    # risk set.
    completed_rt_ids: set[str] = set()
    if result.major_win_event_log is not None:
        completed_rt_ids = {e.initiative_id for e in result.major_win_event_log} & rt_ids

    # The risk set = stopped + completed RT initiatives (those that were
    # ever worked on).
    at_risk_rt = len(stopped_rt_ids) + len(completed_rt_ids)
    at_risk_eligible = len(stopped_eligible_ids) + len(completed_rt_ids & eligible_ids)

    all_rt_curve = _build_survival_curve(rt_stop_ticks, at_risk_rt)
    eligible_curve = _build_survival_curve(eligible_stop_ticks, at_risk_eligible)

    return SurvivalCurveResult(
        all_rt_curve=all_rt_curve,
        eligible_curve=eligible_curve,
        all_rt_count=at_risk_rt,
        eligible_count=at_risk_eligible,
    )


def _build_survival_curve(
    stop_ticks: list[int],
    total_at_risk: int,
) -> tuple[tuple[int, float], ...]:
    """Build a Kaplan-Meier-style survival curve from stop tick data.

    Args:
        stop_ticks: Staffed-tick values at which stops occurred.
        total_at_risk: Total initiatives in the risk set.

    Returns:
        Tuple of (staffed_tick, fraction_alive) pairs, sorted by tick.
        Starts with (0, 1.0).
    """
    if total_at_risk == 0:
        return ((0, 1.0),)

    # Sort stop ticks and compute cumulative fraction.
    sorted_ticks = sorted(stop_ticks)
    curve: list[tuple[int, float]] = [(0, 1.0)]
    cumulative_stopped = 0

    # Group stops by tick.
    i = 0
    while i < len(sorted_ticks):
        current_tick = sorted_ticks[i]
        count_at_tick = 0
        while i < len(sorted_ticks) and sorted_ticks[i] == current_tick:
            count_at_tick += 1
            i += 1
        cumulative_stopped += count_at_tick
        fraction_alive = 1.0 - cumulative_stopped / total_at_risk
        curve.append((current_tick, fraction_alive))

    return tuple(curve)


# ===========================================================================
# Metric 3: Belief-at-stop distribution for major-win-eligible
# ===========================================================================


@dataclass(frozen=True)
class BeliefAtStopResult:
    """Belief-at-stop distribution for major-win-eligible initiatives.

    Attributes:
        beliefs: Tuple of quality_belief_t values at the moment each
            major-win-eligible initiative was stopped.
        count: Number of major-win-eligible stops.
        mean_belief: Mean belief at stop. None if count == 0.
        min_belief: Minimum belief at stop. None if count == 0.
        max_belief: Maximum belief at stop. None if count == 0.
    """

    beliefs: tuple[float, ...]
    count: int
    mean_belief: float | None
    min_belief: float | None
    max_belief: float | None


def compute_belief_at_stop(result: RunResult) -> BeliefAtStopResult:
    """Compute belief-at-stop distribution for major-win-eligible initiatives.

    For each major-win-eligible initiative that was stopped, record the
    quality_belief_t at the moment of the stop decision. This reveals
    whether governance is stopping potential breakthroughs while beliefs
    are still high (information failure) or after beliefs have declined
    (rational response to signals).

    Args:
        result: A completed RunResult with event logs and manifest.

    Returns:
        BeliefAtStopResult with the belief distribution and summary stats.
    """
    eligible_ids: set[str] = {
        cfg.initiative_id
        for cfg in result.manifest.resolved_initiatives
        if is_major_win_eligible(cfg)
    }

    beliefs: list[float] = []
    if result.stop_event_log is not None:
        for event in result.stop_event_log:
            if event.initiative_id in eligible_ids:
                beliefs.append(event.quality_belief_t)

    count = len(beliefs)
    mean_belief: float | None = None
    min_belief: float | None = None
    max_belief: float | None = None

    if count > 0:
        mean_belief = sum(beliefs) / count
        min_belief = min(beliefs)
        max_belief = max(beliefs)

    return BeliefAtStopResult(
        beliefs=tuple(beliefs),
        count=count,
        mean_belief=mean_belief,
        min_belief=min_belief,
        max_belief=max_belief,
    )


# ===========================================================================
# Metric 4: Attention-conditioned false negatives
# ===========================================================================


@dataclass(frozen=True)
class AttentionConditionedResult:
    """False-stop rate bucketed by mean attention level.

    Attributes:
        bucket_edges: Tuple of bucket edge values (N+1 edges for N buckets).
        bucket_false_stop_rates: Per-bucket false-stop rate. None for
            empty buckets.
        bucket_counts: Number of stopped major-win-eligible initiatives
            in each bucket.
        bucket_total_eligible: Total major-win-eligible initiatives
            (stopped + completed) in each bucket.
    """

    bucket_edges: tuple[float, ...]
    bucket_false_stop_rates: tuple[float | None, ...]
    bucket_counts: tuple[int, ...]
    bucket_total_eligible: tuple[int, ...]


def compute_attention_conditioned_false_negatives(
    result: RunResult,
    *,
    n_buckets: int = 5,
) -> AttentionConditionedResult:
    """Compute false-stop rate bucketed by mean attention.

    Uses cumulative_attention_invested / staffed_ticks as the mean
    attention proxy. This is computed from StopEvent fields
    (cumulative_labor_invested serves as a proxy for attention exposure
    when per-tick attention data is not available) and from
    MajorWinEvent fields for completed initiatives.

    Bucket edges are evenly spaced from 0 to 1.

    Args:
        result: A completed RunResult with event logs and manifest.
        n_buckets: Number of attention buckets (default: 5).

    Returns:
        AttentionConditionedResult with per-bucket false-stop rates.
    """
    eligible_ids: set[str] = {
        cfg.initiative_id
        for cfg in result.manifest.resolved_initiatives
        if is_major_win_eligible(cfg)
    }

    # Compute mean attention for each stopped eligible initiative.
    # Use cumulative_attention_invested from MajorWinEvent if available,
    # otherwise approximate from StopEvent.
    stopped_attentions: list[float] = []
    if result.stop_event_log is not None:
        for event in result.stop_event_log:
            if event.initiative_id in eligible_ids and event.staffed_ticks > 0:
                # Mean attention approximation: cumulative_labor / staffed_ticks.
                # This is a reasonable proxy when per-tick attention records
                # are not available.
                mean_attn = event.cumulative_labor_invested / event.staffed_ticks
                stopped_attentions.append(mean_attn)

    # Compute mean attention for each completed eligible initiative.
    completed_attentions: list[float] = []
    if result.major_win_event_log is not None:
        for event in result.major_win_event_log:
            # Include eligible initiatives with positive attention/labor data.
            if (
                event.initiative_id in eligible_ids
                and event.cumulative_attention_invested > 0
                and event.cumulative_labor_invested > 0
            ):
                # Approximate staffed ticks from labor (1 per staffed tick).
                mean_attn = event.cumulative_attention_invested / event.cumulative_labor_invested
                completed_attentions.append(mean_attn)

    # Build buckets.
    bucket_step = 1.0 / n_buckets
    bucket_edges = tuple(i * bucket_step for i in range(n_buckets + 1))

    bucket_stopped: list[int] = [0] * n_buckets
    bucket_completed: list[int] = [0] * n_buckets

    def _bucket_index(attn: float) -> int:
        """Map attention value to bucket index."""
        idx = int(attn / bucket_step)
        # Clamp to valid range.
        return min(max(idx, 0), n_buckets - 1)

    for attn in stopped_attentions:
        bucket_stopped[_bucket_index(attn)] += 1

    for attn in completed_attentions:
        bucket_completed[_bucket_index(attn)] += 1

    # Compute false-stop rate per bucket.
    bucket_rates: list[float | None] = []
    bucket_totals: list[int] = []
    for i in range(n_buckets):
        total = bucket_stopped[i] + bucket_completed[i]
        bucket_totals.append(total)
        if total > 0:
            bucket_rates.append(bucket_stopped[i] / total)
        else:
            bucket_rates.append(None)

    return AttentionConditionedResult(
        bucket_edges=bucket_edges,
        bucket_false_stop_rates=tuple(bucket_rates),
        bucket_counts=tuple(bucket_stopped),
        bucket_total_eligible=tuple(bucket_totals),
    )


# ===========================================================================
# Metric 5: Hazard of stop by staffed tick
# ===========================================================================


@dataclass(frozen=True)
class StopHazardResult:
    """Stop hazard by staffed-tick bin for right-tail initiatives.

    Attributes:
        bin_edges: Tuple of bin edge values (N+1 edges for N bins).
        stop_counts: Number of stops in each bin.
        total_stops: Total right-tail stops.
        bin_fractions: Fraction of total stops in each bin.
    """

    bin_edges: tuple[int, ...]
    stop_counts: tuple[int, ...]
    total_stops: int
    bin_fractions: tuple[float, ...]


def compute_stop_hazard(
    result: RunResult,
    *,
    bin_width: int = 20,
    max_tick: int = 200,
) -> StopHazardResult:
    """Compute stop frequency by staffed-tick bin for right-tail initiatives.

    Tests whether stops cluster before the belief-maturation window
    (early stops before enough information has accumulated) or are
    spread across the run.

    Args:
        result: A completed RunResult with event logs and manifest.
        bin_width: Width of each staffed-tick bin (default: 20).
        max_tick: Maximum staffed tick for binning (default: 200).

    Returns:
        StopHazardResult with per-bin stop counts and fractions.
    """
    rt_ids: set[str] = {
        cfg.initiative_id for cfg in result.manifest.resolved_initiatives if is_right_tail(cfg)
    }

    # Collect staffed ticks at stop for RT initiatives.
    rt_stop_ticks: list[int] = []
    if result.stop_event_log is not None:
        for event in result.stop_event_log:
            if event.initiative_id in rt_ids:
                rt_stop_ticks.append(event.staffed_ticks)

    # Build bins.
    n_bins = (max_tick + bin_width - 1) // bin_width
    bin_edges = tuple(i * bin_width for i in range(n_bins + 1))
    bin_counts: list[int] = [0] * n_bins

    for tick in rt_stop_ticks:
        idx = min(tick // bin_width, n_bins - 1)
        bin_counts[idx] += 1

    total = len(rt_stop_ticks)
    bin_fractions: list[float] = []
    for count in bin_counts:
        bin_fractions.append(count / total if total > 0 else 0.0)

    return StopHazardResult(
        bin_edges=bin_edges,
        stop_counts=tuple(bin_counts),
        total_stops=total,
        bin_fractions=tuple(bin_fractions),
    )
