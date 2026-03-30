"""Business intent translation layer.

Maps executive-style scenario requests into the repo's three-layer
RunDesignSpec vocabulary: environmental conditions, governance
architecture, operating policy.

This module sits above RunDesignSpec and below any chat/front-end
glue. It loads a structured YAML registry of canonical business
intents, validates requested intent combinations, detects conflicts,
and produces RunDesignSpec instances.

Design contract
---------------

- RunDesignSpec remains the final authoring artifact. This module
  produces RunDesignSpec instances; it does not replace them.
- Translation logic is repo-owned, not front-end glue. The registry
  evolves with the model.
- The first version uses structured registry lookup, not NLP. Intent
  IDs are exact strings, not fuzzy matches.
- Portfolio mix targets are policy-side soft preferences. The engine
  never sees business intents or mix targets.

Per business_intent_translation.md design principles.

Usage example::

    from primordial_soup.business_intent import (
        BusinessIntentRequest,
        build_run_design_from_intents,
        translate_business_intents,
    )

    # Translate structured business intents into a RunDesignSpec.
    spec = build_run_design_from_intents(
        name="patient_discovery_v1",
        intents=(
            BusinessIntentRequest("discovery_heavy_world"),
            BusinessIntentRequest("patient_governance"),
            BusinessIntentRequest(
                "portfolio_mix_targets",
                parameters={
                    "targets": {
                        "flywheel": 0.30,
                        "right_tail": 0.30,
                        "enabler": 0.25,
                        "quick_win": 0.15,
                    },
                },
            ),
        ),
        world_seeds=(42, 43, 44),
    )

Design references:
    - docs/implementation/business_intent_translation.md
    - docs/design/governance.md §Portfolio allocation
    - src/primordial_soup/business_intent_registry.yaml
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from primordial_soup.campaign import WorkforceArchitectureSpec
from primordial_soup.config import (
    CANONICAL_BUCKET_NAMES,
    PortfolioMixTargets,
)
from primordial_soup.workbench import (
    EnvironmentConditionsSpec,
    GovernanceArchitectureSpec,
    OperatingPolicySpec,
    RunDesignSpec,
)

logger = logging.getLogger(__name__)


# Path to the canonical registry YAML, shipped alongside this module.
_REGISTRY_PATH = Path(__file__).parent / "business_intent_registry.yaml"


# ============================================================================
# Request and result types
# ============================================================================


@dataclass(frozen=True)
class BusinessIntentRequest:
    """A single business intent with optional parameters.

    Attributes:
        intent_id: Canonical intent name from the registry (e.g.,
            "patient_governance", "portfolio_mix_targets").
        parameters: Optional dict of intent-specific parameters. For
            example, workforce_shape intents require team_count and
            total_labor_endowment; portfolio_mix_targets requires a
            targets mapping. None means no parameters.
    """

    intent_id: str
    parameters: dict[str, Any] | None = None


@dataclass(frozen=True)
class TranslationResult:
    """Structured deltas from translating business intents.

    Each field is None when the corresponding intent was not requested.
    This is an intermediate representation between raw intents and a
    RunDesignSpec — it captures what the intents resolved to before
    being applied to construct the final spec.

    Attributes:
        environment_family: Resolved environment family name, or None.
        workforce_team_count: Resolved team count, or None.
        workforce_total_labor_endowment: Resolved total labor, or None.
        policy_preset: Resolved operating policy preset, or None.
        portfolio_mix_targets: Resolved portfolio mix targets, or None.
        max_single_initiative_labor_share: Resolved concentration cap.
        low_quality_belief_threshold: Resolved low-quality threshold.
        max_low_quality_belief_labor_share: Resolved low-quality cap.
        warnings: Non-fatal diagnostic messages from translation.
    """

    environment_family: str | None = None
    workforce_team_count: int | None = None
    workforce_total_labor_endowment: int | None = None
    policy_preset: str | None = None
    portfolio_mix_targets: PortfolioMixTargets | None = None
    max_single_initiative_labor_share: float | None = None
    low_quality_belief_threshold: float | None = None
    max_low_quality_belief_labor_share: float | None = None
    warnings: tuple[str, ...] = ()


# ============================================================================
# Registry loading and validation
# ============================================================================


def load_business_intent_registry(
    path: Path | None = None,
) -> dict[str, Any]:
    """Load and validate the business intent registry from YAML.

    The registry is the canonical structured source for translating
    business requests into study-layer concepts. It defines:
    - canonical initiative bucket definitions
    - named business intents with layer mappings and translation rules
    - known conflict pairs
    - default parameter values

    Args:
        path: Path to the registry YAML. None uses the canonical
            registry shipped with the package.

    Returns:
        Parsed and validated registry dict.

    Raises:
        FileNotFoundError: If the registry file does not exist.
        ValueError: If the registry fails structural validation.
    """
    registry_path = path or _REGISTRY_PATH
    with open(registry_path) as f:
        registry = yaml.safe_load(f)

    _validate_registry_structure(registry)
    return registry


def _validate_registry_structure(registry: dict[str, Any]) -> None:
    """Validate that the registry has the required top-level sections.

    Checks for structural completeness only — individual intent
    definitions are validated lazily during translation.

    Raises:
        ValueError: If required sections are missing.
    """
    errors: list[str] = []

    if not isinstance(registry, dict):
        raise ValueError("Business intent registry must be a YAML mapping.")

    if "version" not in registry:
        errors.append("Registry missing 'version' field.")
    if "bucket_definitions" not in registry:
        errors.append("Registry missing 'bucket_definitions' section.")
    if "intents" not in registry:
        errors.append("Registry missing 'intents' section.")
    if "conflicts" not in registry:
        errors.append("Registry missing 'conflicts' section.")

    # Validate that bucket definitions match the canonical set.
    bucket_defs = registry.get("bucket_definitions", {})
    if isinstance(bucket_defs, dict):
        registry_buckets = set(bucket_defs.keys())
        missing = CANONICAL_BUCKET_NAMES - registry_buckets
        if missing:
            errors.append(
                f"Registry bucket_definitions missing canonical buckets: " f"{sorted(missing)}."
            )

    # Validate that each intent has required fields.
    intents = registry.get("intents", {})
    if isinstance(intents, dict):
        for intent_id, intent_def in intents.items():
            if not isinstance(intent_def, dict):
                errors.append(f"Intent {intent_id!r}: must be a mapping.")
                continue
            if "layer" not in intent_def:
                errors.append(f"Intent {intent_id!r}: missing 'layer' field.")
            if "translation" not in intent_def:
                errors.append(f"Intent {intent_id!r}: missing 'translation' field.")

    if errors:
        raise ValueError(
            "Business intent registry validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
        )


# ============================================================================
# Translation
# ============================================================================


def translate_business_intents(
    intents: tuple[BusinessIntentRequest, ...],
    registry: dict[str, Any] | None = None,
) -> TranslationResult:
    """Translate business intents into structured run-design deltas.

    Validates that all intent IDs are known, checks for conflicts among
    the requested intents, and then translates each intent into the
    appropriate field of TranslationResult according to its registry-
    defined translation rules.

    Intent application follows the registry's defined layer order:
    environment, then governance architecture, then operating policy.
    Within a layer, intents are applied in the order provided.

    Args:
        intents: Ordered tuple of business intent requests. Each must
            reference a known intent_id from the registry.
        registry: Pre-loaded registry dict. None loads the canonical
            registry from disk.

    Returns:
        TranslationResult with resolved deltas for each layer.

    Raises:
        ValueError: If any intent is unknown, parameters are missing,
            or conflicting intents are requested.
    """
    if registry is None:
        registry = load_business_intent_registry()

    known_intents = registry.get("intents", {})
    conflicts = registry.get("conflicts", [])
    defaults = registry.get("defaults", {})

    # --- Validate all intent IDs are known ---
    errors: list[str] = []
    for intent in intents:
        if intent.intent_id not in known_intents:
            errors.append(
                f"Unknown intent: {intent.intent_id!r}. "
                f"Known intents: {sorted(known_intents.keys())}."
            )
    if errors:
        raise ValueError("\n".join(errors))

    # --- Check for conflicts ---
    intent_ids = {i.intent_id for i in intents}
    for conflict in conflicts:
        conflicting_set = set(conflict["intents"])
        if conflicting_set.issubset(intent_ids):
            raise ValueError(conflict["message"])

    # --- Translate each intent ---
    env_family: str | None = None
    team_count: int | None = None
    total_labor: int | None = None
    policy_preset: str | None = None
    mix_targets: PortfolioMixTargets | None = None
    max_single: float | None = None
    lqb_threshold: float | None = None
    lqb_share: float | None = None
    warnings: list[str] = []

    for intent in intents:
        spec = known_intents[intent.intent_id]
        translation = spec["translation"]
        kind = translation["kind"]
        params = intent.parameters or {}

        if kind == "environment_family_choice":
            new_family = translation["family"]
            if env_family is not None and env_family != new_family:
                raise ValueError(
                    f"Conflicting environment families from intents: "
                    f"{env_family!r} vs {new_family!r}."
                )
            env_family = new_family

        elif kind == "environment_family_bias":
            # Bias intents suggest a preferred family. Use the first
            # preferred family from the registry.
            preferred = translation.get("preferred_families", [])
            if preferred:
                new_family = preferred[0]
                if env_family is not None and env_family != new_family:
                    raise ValueError(
                        f"Conflicting environment families from intents: "
                        f"{env_family!r} vs {new_family!r}."
                    )
                env_family = new_family

        elif kind == "policy_preset":
            new_preset = translation["preset"]
            if policy_preset is not None and policy_preset != new_preset:
                raise ValueError(
                    f"Conflicting policy presets from intents: "
                    f"{policy_preset!r} vs {new_preset!r}."
                )
            policy_preset = new_preset

        elif kind == "workforce_shape":
            # Workforce-shape intents require team_count and
            # total_labor_endowment as parameters.
            tc = params.get("team_count")
            tl = params.get("total_labor_endowment")
            if tc is None or tl is None:
                param_spec = spec.get("parameters", {})
                required = [
                    k for k, v in param_spec.items() if isinstance(v, dict) and v.get("required")
                ]
                raise ValueError(
                    f"Intent {intent.intent_id!r} requires parameters: "
                    f"{required}. Got: {sorted(params.keys())}."
                )
            team_count = int(tc)
            total_labor = int(tl)

        elif kind == "governance_guardrail":
            # Single-field guardrail (e.g., concentration cap).
            guardrail_field = translation["field"]
            val = params.get(guardrail_field)
            if val is None:
                raise ValueError(
                    f"Intent {intent.intent_id!r} requires parameter: " f"{guardrail_field!r}."
                )
            if guardrail_field == "max_single_initiative_labor_share":
                max_single = float(val)
            else:
                warnings.append(
                    f"Unhandled guardrail field: {guardrail_field!r} "
                    f"for intent {intent.intent_id!r}."
                )

        elif kind == "governance_guardrail_pair":
            # Paired guardrail (e.g., low-quality threshold + cap).
            fields = translation["fields"]
            for f in fields:
                val = params.get(f)
                if val is None:
                    raise ValueError(f"Intent {intent.intent_id!r} requires parameter: " f"{f!r}.")
            lqb_threshold = float(params["low_quality_belief_threshold"])
            lqb_share = float(params["max_low_quality_belief_labor_share"])

        elif kind == "portfolio_mix_targets":
            # Portfolio mix target translation.
            targets_raw = params.get("targets")
            if targets_raw is None:
                raise ValueError(
                    f"Intent {intent.intent_id!r} requires parameter: "
                    f"'targets' (mapping of bucket_name to labor share)."
                )
            if not isinstance(targets_raw, dict):
                raise ValueError(
                    f"Intent {intent.intent_id!r}: 'targets' must be a "
                    f"mapping, got {type(targets_raw).__name__}."
                )

            # Validate bucket names against the canonical set.
            for bucket_name in targets_raw:
                if bucket_name not in CANONICAL_BUCKET_NAMES:
                    raise ValueError(
                        f"Intent {intent.intent_id!r}: unknown bucket "
                        f"{bucket_name!r}. Valid: {sorted(CANONICAL_BUCKET_NAMES)}."
                    )

            tolerance = float(
                params.get(
                    "tolerance",
                    defaults.get("portfolio_mix_tolerance", 0.10),
                )
            )
            bucket_targets = tuple((str(k), float(v)) for k, v in targets_raw.items())
            mix_targets = PortfolioMixTargets(
                bucket_targets=bucket_targets,
                tolerance=tolerance,
            )

        else:
            warnings.append(
                f"Unknown translation kind: {kind!r} for intent " f"{intent.intent_id!r}. Skipped."
            )

    return TranslationResult(
        environment_family=env_family,
        workforce_team_count=team_count,
        workforce_total_labor_endowment=total_labor,
        policy_preset=policy_preset,
        portfolio_mix_targets=mix_targets,
        max_single_initiative_labor_share=max_single,
        low_quality_belief_threshold=lqb_threshold,
        max_low_quality_belief_labor_share=lqb_share,
        warnings=tuple(warnings),
    )


# ============================================================================
# RunDesignSpec construction from intents
# ============================================================================


def build_run_design_from_intents(
    *,
    name: str,
    intents: tuple[BusinessIntentRequest, ...],
    title: str = "",
    description: str = "",
    world_seeds: tuple[int, ...] = (42,),
    registry: dict[str, Any] | None = None,
    base_family: str = "balanced_incumbent",
    base_policy_preset: str = "balanced",
    base_total_labor_endowment: int = 8,
    base_team_count: int = 8,
    base_ramp_period: int = 4,
) -> RunDesignSpec:
    """Build a RunDesignSpec from business intents.

    Translates the intents into structured deltas, then constructs a
    RunDesignSpec using baseline defaults for any unspecified fields.
    Intent-derived values override the corresponding base defaults.

    This is the primary entry point for the business intent translation
    layer. The returned RunDesignSpec can be validated and resolved
    through the standard workbench pipeline (validate_run_design,
    resolve_run_design).

    Args:
        name: Short slug for the design (no spaces).
        intents: Business intent requests to translate.
        title: Human-readable title. Defaults to a generated title.
        description: Longer description. Defaults to empty string.
        world_seeds: World seeds for initiative pool generation.
        registry: Pre-loaded registry dict. None loads canonical registry.
        base_family: Default environment family when no intent overrides it.
        base_policy_preset: Default operating policy when no intent
            overrides it.
        base_total_labor_endowment: Default total labor endowment.
        base_team_count: Default team count.
        base_ramp_period: Default ramp period in ticks.

    Returns:
        RunDesignSpec constructed from translated intents + base defaults.

    Raises:
        ValueError: If intents are unknown, conflicting, or have missing
            parameters.
    """
    result = translate_business_intents(intents, registry)

    # Intent-derived values override base defaults.
    family = result.environment_family or base_family
    preset = result.policy_preset or base_policy_preset
    team_count = result.workforce_team_count or base_team_count
    total_labor = result.workforce_total_labor_endowment or base_total_labor_endowment

    resolved_title = title or f"{family} / {preset}"

    return RunDesignSpec(
        name=name,
        title=resolved_title,
        description=description,
        environment=EnvironmentConditionsSpec(
            family=family,  # type: ignore[arg-type]
        ),
        architecture=GovernanceArchitectureSpec(
            workforce=WorkforceArchitectureSpec(
                total_labor_endowment=total_labor,
                team_count=team_count,
                ramp_period=base_ramp_period,
            ),
            portfolio_mix_targets=result.portfolio_mix_targets,
            low_quality_belief_threshold=result.low_quality_belief_threshold,
            max_low_quality_belief_labor_share=result.max_low_quality_belief_labor_share,
            max_single_initiative_labor_share=result.max_single_initiative_labor_share,
        ),
        policy=OperatingPolicySpec(
            preset=preset,  # type: ignore[arg-type]
        ),
        world_seeds=world_seeds,
    )
