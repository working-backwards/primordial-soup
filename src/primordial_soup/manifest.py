"""Campaign manifest serialization to JSON.

This module serializes CampaignSpec and RunManifest objects to JSON
for provenance, exact replay, and sweep analysis. The manifest must
record the full GovernanceConfig parameter values, the environment
configuration, the design_seed, and the engine version.

Serialization is lossy for complex objects (e.g. distribution specs,
numpy arrays) — we serialize to a human-readable, round-trippable
JSON representation suitable for audit and provenance, not for
reconstructing live Python objects.

Design reference:
    - docs/design/experiments.md §Reproducibility
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

    from primordial_soup.campaign import CampaignResult, CampaignSpec
    from primordial_soup.config import GovernanceConfig
    from primordial_soup.reporting import RunManifest

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Governance config serialization
# ---------------------------------------------------------------------------


def governance_config_to_dict(config: GovernanceConfig) -> dict[str, Any]:
    """Serialize a GovernanceConfig to a JSON-compatible dict.

    All fields are included, including None-valued optional fields.
    This ensures the manifest is complete and explicit.

    Args:
        config: The GovernanceConfig to serialize.

    Returns:
        Dict with all governance parameter values.
    """
    return {
        "policy_id": config.policy_id,
        "exec_attention_budget": config.exec_attention_budget,
        "default_initial_quality_belief": config.default_initial_quality_belief,
        "confidence_decline_threshold": config.confidence_decline_threshold,
        "tam_threshold_ratio": config.tam_threshold_ratio,
        "base_tam_patience_window": config.base_tam_patience_window,
        "stagnation_window_staffed_ticks": config.stagnation_window_staffed_ticks,
        "stagnation_belief_change_threshold": config.stagnation_belief_change_threshold,
        "attention_min": config.attention_min,
        "attention_max": config.attention_max,
        "exec_overrun_threshold": config.exec_overrun_threshold,
        "low_quality_belief_threshold": config.low_quality_belief_threshold,
        "max_low_quality_belief_labor_share": config.max_low_quality_belief_labor_share,
        "max_single_initiative_labor_share": config.max_single_initiative_labor_share,
    }


# ---------------------------------------------------------------------------
# Campaign spec serialization
# ---------------------------------------------------------------------------


def campaign_spec_to_dict(spec: CampaignSpec) -> dict[str, Any]:
    """Serialize a CampaignSpec to a JSON-compatible dict.

    Includes campaign metadata, environment configuration summary,
    governance sweep parameters, and world seeds. Sufficient for
    provenance and audit of the experimental design.

    Args:
        spec: The CampaignSpec to serialize.

    Returns:
        Dict suitable for json.dumps().
    """
    env = spec.environment
    sweep = spec.governance_sweep
    bounds = sweep.parameter_bounds

    return {
        "campaign_id": spec.campaign_id,
        "description": spec.description,
        "environment": {
            "time": {
                "tick_horizon": env.time.tick_horizon,
                "tick_label": env.time.tick_label,
            },
            "teams": {
                "team_count": env.teams.team_count,
                # Convert tuple to list for JSON round-trip compatibility.
                # When team_size is a tuple of per-team sizes, json.dumps
                # converts it to a JSON array, but json.loads returns a list.
                # Using list() here ensures the pre-serialization dict matches
                # the post-deserialization dict.
                "team_size": (
                    list(env.teams.team_size)
                    if isinstance(env.teams.team_size, tuple)
                    else env.teams.team_size
                ),
                "ramp_period": env.teams.ramp_period,
                "ramp_multiplier_shape": env.teams.ramp_multiplier_shape.value,
            },
            "model": {
                "exec_attention_budget": env.model.exec_attention_budget,
                "reference_ceiling": env.model.reference_ceiling,
                "default_initial_quality_belief": env.model.default_initial_quality_belief,
                "learning_rate": env.model.learning_rate,
                "execution_signal_st_dev": env.model.execution_signal_st_dev,
                "execution_learning_rate": env.model.execution_learning_rate,
                "max_portfolio_capability": env.model.max_portfolio_capability,
                "capability_decay": env.model.capability_decay,
            },
            "initiative_generator": {
                "type_count": len(env.initiative_generator.type_specs),
                "total_initiatives": sum(ts.count for ts in env.initiative_generator.type_specs),
                "types": [
                    {
                        "generation_tag": ts.generation_tag,
                        "count": ts.count,
                    }
                    for ts in env.initiative_generator.type_specs
                ],
            },
        },
        "governance_sweep": {
            "lhs_sample_count": sweep.lhs_sample_count,
            "design_seed": sweep.design_seed,
            "include_archetype_anchors": sweep.include_archetype_anchors,
            "parameter_bounds": {
                "confidence_decline_threshold": list(bounds.confidence_decline_threshold),
                "tam_threshold_ratio": list(bounds.tam_threshold_ratio),
                "base_tam_patience_window": list(bounds.base_tam_patience_window),
                "stagnation_window_staffed_ticks": list(bounds.stagnation_window_staffed_ticks),
                "stagnation_belief_change_threshold": list(
                    bounds.stagnation_belief_change_threshold
                ),
                "attention_min": list(bounds.attention_min),
                "attention_span": list(bounds.attention_span),
                "exec_overrun_threshold": list(bounds.exec_overrun_threshold),
            },
        },
        "world_seeds": list(spec.world_seeds),
    }


def run_manifest_to_dict(manifest: RunManifest) -> dict[str, Any]:
    """Serialize a RunManifest to a JSON-compatible dict.

    Includes the governance config and provenance fields. Does NOT
    include the full resolved configuration or initiative list (those
    are large and available in the RunResult).

    Args:
        manifest: The RunManifest to serialize.

    Returns:
        Dict suitable for json.dumps().
    """
    return {
        "policy_id": manifest.policy_id,
        "world_seed": manifest.world_seed,
        "is_replay": manifest.is_replay,
        "baseline_spec_version": manifest.baseline_spec_version,
        "governance_config": governance_config_to_dict(manifest.resolved_configuration.governance),
    }


# ---------------------------------------------------------------------------
# Campaign result serialization
# ---------------------------------------------------------------------------


def campaign_result_to_dict(result: CampaignResult) -> dict[str, Any]:
    """Serialize a CampaignResult to a JSON-compatible summary dict.

    Includes the campaign spec, generated governance configs, and
    per-run summary metrics including value channel decomposition,
    organizational health indicators, completion and stop counts by
    initiative type, and belief accuracy. Per-tick data is not included.
    Suitable for campaign-level analysis and provenance.

    Args:
        result: The CampaignResult to serialize.

    Returns:
        Dict suitable for json.dumps().
    """
    return {
        "campaign_spec": campaign_spec_to_dict(result.campaign_spec),
        "total_runs": result.total_runs,
        "governance_configs": [governance_config_to_dict(gc) for gc in result.governance_configs],
        "run_summaries": [
            {
                # --- existing fields (unchanged) ---
                "policy_id": rr.manifest.policy_id,
                "world_seed": rr.manifest.world_seed,
                "cumulative_value_total": rr.cumulative_value_total,
                "major_win_count": rr.major_win_profile.major_win_count,
                "terminal_capability_t": rr.terminal_capability_t,
                "idle_team_tick_fraction": rr.idle_capacity_profile.idle_team_tick_fraction,
                "pool_exhaustion_tick": rr.idle_capacity_profile.pool_exhaustion_tick,
                # --- value channel decomposition ---
                "completion_lump_value": rr.value_by_channel.completion_lump_value,
                "residual_value": rr.value_by_channel.residual_value,
                "residual_value_by_label": rr.value_by_channel.residual_value_by_label,
                # --- organizational health ---
                "max_portfolio_capability_t": rr.max_portfolio_capability_t,
                "terminal_aggregate_residual_rate": rr.terminal_aggregate_residual_rate,
                # --- completion and stop counts by initiative type ---
                "completed_initiative_count_by_label": (
                    rr.exploration_cost_profile.completed_initiative_count_by_label
                ),
                "cumulative_labor_in_completed_initiatives": (
                    rr.exploration_cost_profile.cumulative_labor_in_completed_initiatives
                ),
                "stopped_initiative_count_by_label": (
                    rr.exploration_cost_profile.stopped_initiative_count_by_label
                ),
                # --- belief accuracy ---
                "mean_absolute_belief_error": rr.belief_accuracy.mean_absolute_belief_error,
            }
            for rr in result.run_results
        ],
    }


# ---------------------------------------------------------------------------
# File I/O
# ---------------------------------------------------------------------------


def write_campaign_manifest(
    spec: CampaignSpec,
    output_path: Path,
) -> None:
    """Write a campaign specification to a JSON manifest file.

    Args:
        spec: The CampaignSpec to serialize.
        output_path: Path to write the JSON file.
    """
    data = campaign_spec_to_dict(spec)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    logger.info("Wrote campaign manifest to %s.", output_path)


def write_campaign_result(
    result: CampaignResult,
    output_path: Path,
) -> None:
    """Write a campaign result summary to a JSON file.

    Args:
        result: The CampaignResult to serialize.
        output_path: Path to write the JSON file.
    """
    data = campaign_result_to_dict(result)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    logger.info("Wrote campaign result to %s.", output_path)


def read_campaign_manifest(input_path: Path) -> dict[str, Any]:
    """Read a campaign manifest JSON file and return the parsed dict.

    This returns the raw dict, not a reconstructed CampaignSpec.
    Round-trip reconstruction is deferred to a future utility if needed.

    Args:
        input_path: Path to the JSON manifest file.

    Returns:
        Parsed dict from the JSON file.

    Raises:
        FileNotFoundError: If the file does not exist.
        json.JSONDecodeError: If the file is not valid JSON.
    """
    with input_path.open("r", encoding="utf-8") as f:
        result: dict[str, Any] = json.load(f)
        return result
