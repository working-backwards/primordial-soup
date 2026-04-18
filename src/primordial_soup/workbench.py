"""Run design workbench — the single human-facing authoring layer.

This module provides RunDesignSpec: the primary artifact for defining a
single simulation run in the three-layer vocabulary without hand-assembling
overlapping low-level types.

Three-layer vocabulary
----------------------

    1. Environmental conditions (EnvironmentConditionsSpec)
       What world is this organization operating in?
       → initiative pool mix, horizon, noise parameters, learning rates.

    2. Governance architecture (GovernanceArchitectureSpec)
       How did leadership choose to organize before the run begins?
       → workforce structure (team decomposition, ramp), portfolio guardrails.

    3. Operating policy (OperatingPolicySpec)
       How does governance actually decide per-tick within the architecture?
       → stop thresholds, attention bounds, patience windows.

Design contract
---------------

- RunDesignSpec is the single stable authoring artifact above current config
  types and below campaign execution.
- validate_run_design() collects all issues eagerly — fix everything at once.
- resolve_run_design() validates, then produces a ResolvedRunDesign containing
  only concrete types the engine and runner already understand.
- The simulator boundary is fully preserved: the engine receives only frozen
  SimulationConfiguration objects; it never sees RunDesignSpec or its children.

Relationship to existing types
-------------------------------

RunDesignSpec resolves into:
    WorkforceConfig    ← from GovernanceArchitectureSpec.workforce
    EnvironmentSpec    ← environment family + architecture workforce
    GovernanceConfig   ← operating policy preset + architecture guardrails
    SimulationConfiguration (one per world seed)

Existing types are unchanged. The workbench layer is purely additive.

Usage example::

    from primordial_soup.workbench import (
        EnvironmentConditionsSpec,
        GovernanceArchitectureSpec,
        OperatingPolicySpec,
        RunDesignSpec,
        resolve_run_design,
        validate_run_design,
        make_baseline_run_design_spec,
    )
    from primordial_soup.campaign import WorkforceArchitectureSpec

    # Option A: hand-assembled spec
    spec = RunDesignSpec(
        name="baseline_balanced_v1",
        title="Baseline run — Balanced policy",
        description="Canonical reference baseline with Balanced governance.",
        environment=EnvironmentConditionsSpec(family="balanced_incumbent"),
        architecture=GovernanceArchitectureSpec(
            workforce=WorkforceArchitectureSpec(
                total_labor_endowment=210,
                team_count=24,
                team_sizes=(
                    5, 5, 5, 5, 5, 5, 5, 5, 5, 5,
                    10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10,
                    20, 20,
                ),
                ramp_period=4,
            ),
        ),
        policy=OperatingPolicySpec(preset="balanced"),
        world_seeds=(42, 43, 44),
    )

    # Option B: factory shorthand
    spec = make_baseline_run_design_spec(
        name="baseline_balanced_v1",
        policy_preset="balanced",
        world_seeds=(42, 43, 44),
    )

    validate_run_design(spec)           # raises ValueError if invalid
    resolved = resolve_run_design(spec) # → ResolvedRunDesign
    print(resolved.summary())          # inspect before running

    # Execute: the workbench resolves; the caller owns execution wiring.
    from primordial_soup.runner import run_single_regime
    policy = policy_factory(resolved.governance)  # caller supplies factory
    results = [run_single_regime(sc, policy)[0] for sc in resolved.simulation_configs]

Design references:
    - docs/implementation/three_layer_model_plan.md
    - docs/implementation/primordial_soup_checkpoint_2026-03-14.md
    - docs/design/governance.md (architecture vs policy distinction)
    - docs/design/interfaces.md (config types)
"""

from __future__ import annotations

import dataclasses
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

from primordial_soup.campaign import EnvironmentSpec, WorkforceArchitectureSpec
from primordial_soup.config import (
    CANONICAL_BUCKET_NAMES,
    GovernanceConfig,
    InitiativeGeneratorConfig,
    InitiativeTypeSpec,
    ModelConfig,
    PortfolioMixTargets,
    ReportingConfig,
    SimulationConfiguration,
    TimeConfig,
    WorkforceConfig,
    validate_configuration,
)
from primordial_soup.presets import (
    EnvironmentFamilyName,
    make_aggressive_stop_loss_governance_config,
    make_balanced_governance_config,
    make_baseline_reporting_config,
    make_environment_spec,
    make_patient_moonshot_governance_config,
)
from primordial_soup.types import RampShape

if TYPE_CHECKING:
    from primordial_soup.policy import GovernancePolicy
    from primordial_soup.reporting import RunResult
    from primordial_soup.run_bundle import (
        ExperimentSpec,
        SeedRunRecord,
    )
    from primordial_soup.state import WorldState

logger = logging.getLogger(__name__)

# The three named operating-policy presets recognized by OperatingPolicySpec.
OperatingPolicyName = Literal["balanced", "aggressive_stop_loss", "patient_moonshot"]


# ---------------------------------------------------------------------------
# Layer 1: Environmental Conditions
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EnvironmentConditionsSpec:
    """Environmental conditions layer for a RunDesignSpec.

    Selects the initiative-pool environment family and optionally
    overrides the shared time or model configuration. These are the
    exogenous world conditions that governance takes as given: the
    opportunity landscape, temporal horizon, signal noise, and learning
    dynamics.

    In the three-layer model, environmental conditions include:
    - The initiative pool (archetype mix, quality distributions, durations)
    - Temporal structure (tick horizon, tick label)
    - World-evolution parameters (signal noise, learning rates, attention curve,
      exec_attention_budget, reference_ceiling)
    - Total labor endowment (the aggregate resource constraint; how that labor
      is decomposed into teams is a governance architecture choice)

    Typical usage: specify only the family name. Override time or model only
    when deliberately exploring non-baseline world conditions.

    Available families:
        "balanced_incumbent"    — Mid-case major-win environment, multi-year
                                  right-tail durations. The canonical baseline.
        "short_cycle_throughput" — Mature world, quick-win-heavy, shorter
                                  right-tail representation and durations.
        "discovery_heavy"       — Favorable domain, more right-tail
                                  initiatives, longer exploratory durations.

    Conductor-facing overrides (all optional — omit for preset defaults):
        staffing_response_overrides: Per-family staffing-response scale ranges.
            Controls how strongly additional staffing above the minimum
            threshold accelerates learning for each initiative family.
        right_tail_prize_count: Right-tail prize abundance. Overrides how
            many right-tail initiatives exist in the initial pool (which
            determines how many distinct prize opportunities are available
            for re-attempt when right-tail initiatives are stopped).
        frontier_degradation_rate_overrides: Per-family frontier degradation
            rates. Lower values mean a deeper frontier (more draws before
            quality degrades meaningfully). 0.0 = non-degrading.
        right_tail_refresh_degradation: Per-attempt quality degradation for
            right-tail prize re-attempts. 0.0 = each re-attempt draws from
            the original quality distribution.
    """

    family: EnvironmentFamilyName = "balanced_incumbent"
    # Override the shared baseline TimeConfig. None → use preset default.
    time_override: TimeConfig | None = None
    # Override the shared baseline ModelConfig. None → use preset default.
    model_override: ModelConfig | None = None

    # ── Conductor-facing environment overrides ────────────────────────
    # These allow the conductor to adjust environment parameters without
    # needing to define a new family preset. When None, preset defaults
    # apply. All are optional.

    # Per-family staffing-response scale ranges. Each entry is
    # (generation_tag, (min_scale, max_scale)) for uniform draw.
    # When set, overrides the preset default (0.0) for that family.
    # Keys must be from CANONICAL_BUCKET_NAMES.
    # Per opportunity_staffing_intensity_design_for_claude_v2.md.
    staffing_response_overrides: tuple[tuple[str, tuple[float, float]], ...] | None = None

    # ── Portfolio mix count overrides (per exec_intent_spec.md #5) ────
    # Each bucket's initial-pool count can be overridden independently.
    # When None, the family preset default applies. When set, the value is
    # used verbatim — total pool size is a derived quantity, not a separate
    # input, so these do not rebalance each other. Must be >= 0 when set.
    # These correspond to the exec-facing "portfolio mix as counts of
    # QW / FW / EN / RT" input: specifying 80 / 70 / 30 / 20 here reproduces
    # the balanced_incumbent default; setting any subset keeps the others
    # at the family default.

    # Right-tail prize abundance: override the right-tail count in the
    # initial pool. More right-tail prizes = more re-attempt opportunities
    # when right-tail initiatives are stopped. Must be >= 0.
    right_tail_prize_count: int | None = None

    # Per-bucket count overrides. Independent of right_tail_prize_count.
    # When set, replaces the family default for that bucket verbatim.
    flywheel_count: int | None = None
    enabler_count: int | None = None
    quick_win_count: int | None = None

    # Per-family frontier degradation rate overrides. Each entry is
    # (generation_tag, degradation_rate). Lower rate = deeper frontier
    # (more draws before quality degrades meaningfully). 0.0 means
    # non-degrading (unlimited replenishment at original quality).
    # Only meaningful for families that have frontier enabled in the preset.
    # Per dynamic_opportunity_frontier.md §1.
    frontier_degradation_rate_overrides: tuple[tuple[str, float], ...] | None = None

    # Per-attempt quality degradation for right-tail prize re-attempts.
    # 0.0 = each re-attempt draws from the original quality distribution.
    # Positive values degrade quality after each failed attempt on a
    # specific prize, modeling learning about the difficulty of a
    # particular opportunity space.
    # Per dynamic_opportunity_frontier.md §2.
    right_tail_refresh_degradation: float | None = None

    def resolve_environment_base(self) -> EnvironmentSpec:
        """Resolve into a base EnvironmentSpec from the named family.

        Applies any conductor-facing overrides (staffing response, frontier
        settings, opportunity supply) to the family preset before returning.

        Design note: The returned EnvironmentSpec carries a placeholder
        WorkforceConfig in its .teams field — the preset default, not the
        architecture-resolved workforce. This is the standard pattern:
        EnvironmentSpec includes a teams field for structural completeness,
        but the actual workforce is determined by the governance architecture.
        resolve_run_design() replaces .teams with the architecture-resolved
        WorkforceConfig before building any SimulationConfiguration. This
        object must not be passed to the engine or runner directly.

        Returns:
            EnvironmentSpec with family-specific initiative_generator, baseline
            (or overridden) time and model, and a placeholder teams field that
            resolve_run_design() will replace.

        Raises:
            ValueError: If the family name is not recognized.
        """
        base = make_environment_spec(self.family)

        # Apply conductor-facing overrides to the initiative generator.
        generator = base.initiative_generator
        has_generator_overrides = (
            self.staffing_response_overrides is not None
            or self.right_tail_prize_count is not None
            or self.flywheel_count is not None
            or self.enabler_count is not None
            or self.quick_win_count is not None
            or self.frontier_degradation_rate_overrides is not None
            or self.right_tail_refresh_degradation is not None
        )
        if has_generator_overrides:
            generator = _apply_environment_overrides(
                generator=generator,
                staffing_response_overrides=self.staffing_response_overrides,
                right_tail_prize_count=self.right_tail_prize_count,
                flywheel_count=self.flywheel_count,
                enabler_count=self.enabler_count,
                quick_win_count=self.quick_win_count,
                frontier_degradation_rate_overrides=self.frontier_degradation_rate_overrides,
                right_tail_refresh_degradation=self.right_tail_refresh_degradation,
            )

        # Apply time/model overrides if present.
        has_time_or_model_override = (
            self.time_override is not None or self.model_override is not None
        )
        if not has_time_or_model_override and not has_generator_overrides:
            return base
        return EnvironmentSpec(
            time=self.time_override if self.time_override is not None else base.time,
            teams=base.teams,  # Placeholder — replaced by resolve_run_design()
            model=self.model_override if self.model_override is not None else base.model,
            initiative_generator=generator,
        )


# ---------------------------------------------------------------------------
# Layer 2: Governance Architecture
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GovernanceArchitectureSpec:
    """Governance architecture layer for a RunDesignSpec.

    Combines the workforce structure (how total labor is decomposed into
    parallel work units) with portfolio-level guardrails (structural
    concentration limits set before the run begins).

    In the three-layer model, governance architecture includes:
    - Team decomposition: how total labor is divided into parallel work units.
    - Ramp parameters: switching-cost structure of the chosen workforce design.
    - Portfolio guardrails: diversification targets and concentration limits.

    These are design-time choices fixed within a run and varied across runs as
    experimental treatments. They answer: "how did leadership choose to
    organize?" — not "how does governance decide per-tick?" (operating policy)
    and not "what environment exists?" (environmental conditions).

    Portfolio guardrail semantics:
        These fields are passed into GovernanceConfig for policy access but
        are governance architecture choices, not per-tick operating parameters.
        The engine does not enforce them; the policy decides whether and how to
        honor them. Setting a guardrail here is a structural intent signal;
        the policy implementation determines whether it is binding.

    Attributes:
        workforce: Workforce architecture specification (team count,
            total_labor_endowment, optional per-team sizes, ramp).
        low_quality_belief_threshold: Quality belief level below which an
            initiative is considered low-confidence for portfolio exposure.
            None means this guardrail is not set.
        max_low_quality_belief_labor_share: Maximum share of active labor
            that may be allocated to low-confidence initiatives. None means
            no cap. Requires low_quality_belief_threshold to be set.
        max_single_initiative_labor_share: Maximum share of active labor
            that any single initiative may receive. None means no cap.
    """

    workforce: WorkforceArchitectureSpec

    # Portfolio guardrails (architecture-level, not per-tick operating policy).
    low_quality_belief_threshold: float | None = None
    max_low_quality_belief_labor_share: float | None = None
    max_single_initiative_labor_share: float | None = None

    # Portfolio mix targets: desired labor-share distribution across
    # canonical initiative buckets. None = no mix targets configured.
    # Per portfolio_allocation_targets_proposal.md.
    portfolio_mix_targets: PortfolioMixTargets | None = None

    # Baseline value per team per week (exec_intent_spec.md #7). Value per
    # week that an idle team produces through baseline (non-portfolio) work:
    # maintenance, customer support, incremental process improvement, etc.
    # The simulator's 1 tick = 1 week convention makes this a 1:1 relabel of
    # ModelConfig.baseline_value_per_tick (which is already per-idle-team per
    # tick — see runner.py). None = preserve the environment family's model
    # default (currently 0.0 by default; 0.1 in calibrated presets).
    # Must be >= 0 when set.
    baseline_value_per_team_week: float | None = None

    def resolve_workforce(self) -> WorkforceConfig:
        """Resolve the workforce specification into a concrete WorkforceConfig.

        Delegates to WorkforceArchitectureSpec.resolve(), which validates
        team sizes, divisibility, and total endowment consistency.

        Returns:
            Concrete WorkforceConfig for use by the simulator.

        Raises:
            ValueError: If the workforce spec is internally inconsistent.
        """
        return self.workforce.resolve()

    def validate(self, errors: list[str]) -> None:
        """Validate architecture-level constraints. Appends issues to errors.

        Does not raise — the caller (validate_run_design) collects all issues
        from all layers before raising a single ValueError.
        """
        if self.low_quality_belief_threshold is not None and not (
            0.0 < self.low_quality_belief_threshold < 1.0
        ):
            errors.append(
                f"low_quality_belief_threshold must be in (0, 1), "
                f"got {self.low_quality_belief_threshold}."
            )
        if self.max_low_quality_belief_labor_share is not None:
            if self.low_quality_belief_threshold is None:
                errors.append(
                    "max_low_quality_belief_labor_share is set but "
                    "low_quality_belief_threshold is None: the cap has no "
                    "threshold to reference."
                )
            if not (0.0 < self.max_low_quality_belief_labor_share <= 1.0):
                errors.append(
                    f"max_low_quality_belief_labor_share must be in (0, 1], "
                    f"got {self.max_low_quality_belief_labor_share}."
                )
        if self.max_single_initiative_labor_share is not None and not (
            0.0 < self.max_single_initiative_labor_share <= 1.0
        ):
            errors.append(
                f"max_single_initiative_labor_share must be in (0, 1], "
                f"got {self.max_single_initiative_labor_share}."
            )
        # Baseline value per team per week must be non-negative.
        # Per exec_intent_spec.md #7: small positive allowed; 0 means no
        # idle-team baseline accrual (the engine default).
        if (
            self.baseline_value_per_team_week is not None
            and self.baseline_value_per_team_week < 0.0
        ):
            errors.append(
                f"baseline_value_per_team_week must be >= 0, "
                f"got {self.baseline_value_per_team_week}."
            )

        # --- Portfolio mix targets validation ---
        if self.portfolio_mix_targets is not None:
            pmt = self.portfolio_mix_targets

            # Bucket names must be from the canonical set.
            for bucket_name, _ in pmt.bucket_targets:
                if bucket_name not in CANONICAL_BUCKET_NAMES:
                    errors.append(
                        f"portfolio_mix_targets: unknown bucket {bucket_name!r}. "
                        f"Valid buckets: {sorted(CANONICAL_BUCKET_NAMES)}."
                    )

            # Target shares must be non-negative.
            for bucket_name, share in pmt.bucket_targets:
                if share < 0.0:
                    errors.append(
                        f"portfolio_mix_targets: share for {bucket_name!r} "
                        f"must be >= 0, got {share}."
                    )

            # Target shares must sum to 1.0 (within tolerance).
            total = sum(share for _, share in pmt.bucket_targets)
            if abs(total - 1.0) > 0.01:
                errors.append(
                    f"portfolio_mix_targets: bucket shares must sum to 1.0, got {total:.4f}."
                )

            # Tolerance must be in [0, 1].
            if not (0.0 <= pmt.tolerance <= 1.0):
                errors.append(
                    f"portfolio_mix_targets: tolerance must be in [0, 1], got {pmt.tolerance}."
                )


# ---------------------------------------------------------------------------
# Layer 3: Operating Policy
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class OperatingPolicySpec:
    """Operating policy layer for a RunDesignSpec.

    Selects a named governance policy preset. The preset determines all
    per-tick decision parameters: stop thresholds, patience windows, and
    attention allocation bounds.

    In the three-layer model, operating policy parameters answer: "given
    this architecture, how does governance actually decide?" They are the
    recurring levers exercised per-tick within the chosen governance
    architecture.

    **Preset-only selection is deliberate, not a first-pass limitation.**
    Field-level operating-policy overrides are intentionally absent here.
    Introducing them would recreate the low-level config assembly problem
    that RunDesignSpec exists to escape — the caller would again need to
    know which GovernanceConfig fields to patch and how they interact.
    Systematic operating-policy variation (the natural domain of this
    study) belongs in the existing LHS sweep and campaign machinery, which
    is purpose-built for it. The workbench's job is to provide a clean
    upstream authoring layer that resolves a single, named governance
    posture into concrete config types. If you need a posture that no
    existing preset captures, add a preset in presets.py; do not add
    field-level overrides here.

    Named presets:
        "balanced"             — Moderate thresholds, all four stop rules
                                 active. The canonical reference baseline.
        "aggressive_stop_loss" — Tight thresholds, short patience windows.
                                 Stops early and redeploys teams faster.
        "patient_moonshot"     — Confidence-decline stopping disabled, long
                                 patience windows, higher execution tolerance.
                                 Holds longer on high-potential initiatives.

    Note: portfolio-risk fields (low_quality_belief_threshold etc.) in the
    resolved GovernanceConfig come from GovernanceArchitectureSpec, not from
    the operating policy preset. The presets set those fields to None;
    resolve_run_design() applies the architecture-level guardrails afterward.
    """

    preset: OperatingPolicyName = "balanced"

    def resolve(self, model: ModelConfig) -> GovernanceConfig:
        """Resolve into a GovernanceConfig using model-derived parameters.

        GovernanceConfig mirrors two fields from ModelConfig (exec_attention_budget,
        default_initial_quality_belief) so the policy can access them without
        the full model config. The model argument supplies those values.

        Portfolio-risk fields in the returned config are set to None by the
        preset factory. resolve_run_design() applies architecture guardrails
        afterward via _apply_architecture_guardrails().

        Args:
            model: Resolved ModelConfig from the environment layer.

        Returns:
            GovernanceConfig from the named preset.

        Raises:
            ValueError: If the preset name is not recognized.
        """
        kwargs = {
            "exec_attention_budget": model.exec_attention_budget,
            "default_initial_quality_belief": model.default_initial_quality_belief,
        }
        if self.preset == "balanced":
            return make_balanced_governance_config(**kwargs)
        if self.preset == "aggressive_stop_loss":
            return make_aggressive_stop_loss_governance_config(**kwargs)
        if self.preset == "patient_moonshot":
            return make_patient_moonshot_governance_config(**kwargs)
        raise ValueError(
            f"Unknown policy preset: {self.preset!r}. "
            f"Valid presets: balanced, aggressive_stop_loss, patient_moonshot."
        )


# ---------------------------------------------------------------------------
# Top-level spec
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RunDesignSpec:
    """Complete run design in the three-layer vocabulary.

    This is the single human-facing authoring artifact for defining a
    simulation run or campaign. It composes environmental conditions,
    governance architecture, and operating policy into one stable
    representation that resolves — via resolve_run_design() — into the
    repo's current concrete config types without changing the simulator
    boundary.

    Design workflow::

        spec = RunDesignSpec(...)
        validate_run_design(spec)       # raises ValueError with all issues
        resolved = resolve_run_design(spec)
        print(resolved.summary())      # inspect before running

        # Execute: the workbench resolves; execution wiring is the caller's job.
        from primordial_soup.runner import run_single_regime
        policy = policy_factory(resolved.governance)
        results = [run_single_regime(sc, policy)[0] for sc in resolved.simulation_configs]

    Attributes:
        name: Short slug for this design (e.g., "baseline_balanced_v1").
            Must be non-empty and contain no spaces. Used in manifest
            provenance and file naming.
        title: Human-readable title for display and reporting.
        description: Longer description of what this run tests or represents.
            May be empty string.
        environment: Environmental conditions — initiative pool mix and
            world-evolution parameters.
        architecture: Governance architecture — workforce structure and
            portfolio guardrails.
        policy: Operating policy — per-tick decision logic (preset selection).
        world_seeds: One or more seeds for initiative pool generation.
            Each seed produces one SimulationConfiguration (one run).
        reporting: Output behavior. None → canonical baseline reporting config
            (all channels enabled).
    """

    # Metadata
    name: str
    title: str
    description: str

    # Three-layer inputs
    environment: EnvironmentConditionsSpec
    architecture: GovernanceArchitectureSpec
    policy: OperatingPolicySpec

    # Execution
    world_seeds: tuple[int, ...]

    # Optional; None → use make_baseline_reporting_config()
    reporting: ReportingConfig | None = None

    # Report-layer label for monetary outputs (per exec_intent_spec.md #8).
    # Free-text — the simulator is unit-agnostic. Propagated through
    # ExperimentSpec → manifest → report_gen so every value-dimension metric
    # renders with this label. Default "units" matches the spec.
    value_unit: str = "units"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RunDesignSpec:
        """Construct a RunDesignSpec from a plain dictionary (e.g. parsed YAML).

        This is the repo-owned parser for the YAML authoring surface. All
        schema interpretation, enum mapping, default application, and config
        construction lives here rather than in the front-end script. When the
        model evolves, this method is the single update point.

        The dict shape mirrors the YAML template exactly:

            name, title, description
            environment:
                family, time (optional), model (optional)
            architecture:
                total_labor_endowment, team_count, ramp_period, ramp_shape
                team_sizes (optional)
                low_quality_belief_threshold (optional)
                max_low_quality_belief_labor_share (optional)
                max_single_initiative_labor_share (optional)
            policy:
                preset
            world_seeds
            reporting (optional):
                record_manifest, record_per_tick_logs, record_event_log

        Args:
            data: Dictionary produced by yaml.safe_load() or equivalent.

        Returns:
            RunDesignSpec ready for validate_run_design() and resolve_run_design().

        Raises:
            KeyError: If a required field is missing.
            ValueError: If a field value is not recognised (e.g. unknown preset).
            TypeError: If a field value has the wrong type.
        """
        # ── Metadata ──────────────────────────────────────────────────────
        name = str(data.get("name", "")).strip()
        title = str(data.get("title", "")).strip()
        description = str(data.get("description", "")).strip()

        # Report-layer unit label (exec_intent_spec.md #8). Free-text,
        # propagated to the report; the simulator is unit-agnostic. Default
        # "units" mirrors the spec's default for runs that don't specify one.
        value_unit = str(data.get("value_unit", "units")).strip() or "units"

        # ── Environment ───────────────────────────────────────────────────
        env_data: dict = data.get("environment", {})
        family = str(env_data.get("family", "balanced_incumbent"))

        time_override: TimeConfig | None = None
        if env_data.get("time") is not None:
            t = env_data["time"]
            time_override = TimeConfig(
                tick_horizon=int(t["tick_horizon"]),
                tick_label=str(t.get("tick_label", "week")),
            )

        model_override: ModelConfig | None = None
        if env_data.get("model") is not None:
            m = env_data["model"]
            model_override = ModelConfig(
                exec_attention_budget=float(m["exec_attention_budget"]),
                base_signal_st_dev_default=float(m["base_signal_st_dev_default"]),
                dependency_noise_exponent=float(m["dependency_noise_exponent"]),
                default_initial_quality_belief=float(m["default_initial_quality_belief"]),
                reference_ceiling=float(m["reference_ceiling"]),
                attention_noise_threshold=float(m["attention_noise_threshold"]),
                low_attention_penalty_slope=float(m["low_attention_penalty_slope"]),
                attention_curve_exponent=float(m["attention_curve_exponent"]),
                min_attention_noise_modifier=float(m["min_attention_noise_modifier"]),
                max_attention_noise_modifier=(
                    float(m["max_attention_noise_modifier"])
                    if m.get("max_attention_noise_modifier") is not None
                    else None
                ),
                learning_rate=float(m["learning_rate"]),
                dependency_learning_scale=(
                    float(m["dependency_learning_scale"])
                    if m.get("dependency_learning_scale") is not None
                    else None
                ),
                execution_signal_st_dev=float(m["execution_signal_st_dev"]),
                execution_learning_rate=float(m["execution_learning_rate"]),
                max_portfolio_capability=float(m["max_portfolio_capability"]),
                capability_decay=float(m["capability_decay"]),
            )

        # ── Staffing response overrides ────────────────────────────────
        # Per-family staffing-response scale ranges.
        # YAML shape: staffing_response: {flywheel: [0.3, 0.8], ...}
        staffing_response_overrides: tuple[tuple[str, tuple[float, float]], ...] | None = None
        sr_raw = env_data.get("staffing_response")
        if sr_raw is not None and isinstance(sr_raw, dict):
            staffing_response_overrides = tuple(
                (str(tag), (float(vals[0]), float(vals[1]))) for tag, vals in sr_raw.items()
            )

        # ── Opportunity supply overrides ──────────────────────────────
        # Conductor-facing controls for opportunity supply and frontier.
        # YAML shape: opportunity_supply: {right_tail_prize_count: 50, ...}
        right_tail_prize_count: int | None = None
        frontier_degradation_rate_overrides: tuple[tuple[str, float], ...] | None = None
        right_tail_refresh_degradation: float | None = None

        # Per-bucket portfolio-mix count overrides (exec_intent_spec.md #5).
        # Each override replaces the family default for that bucket verbatim;
        # total pool size is derived. `quick_win_count`, `flywheel_count`,
        # `enabler_count` live under the same opportunity_supply: YAML block
        # as `right_tail_prize_count` so all four counts are specified in one
        # place.
        flywheel_count: int | None = None
        enabler_count: int | None = None
        quick_win_count: int | None = None

        supply_raw = env_data.get("opportunity_supply")
        if supply_raw is not None and isinstance(supply_raw, dict):
            if supply_raw.get("right_tail_prize_count") is not None:
                right_tail_prize_count = int(supply_raw["right_tail_prize_count"])
            if supply_raw.get("flywheel_count") is not None:
                flywheel_count = int(supply_raw["flywheel_count"])
            if supply_raw.get("enabler_count") is not None:
                enabler_count = int(supply_raw["enabler_count"])
            if supply_raw.get("quick_win_count") is not None:
                quick_win_count = int(supply_raw["quick_win_count"])

            fd_raw = supply_raw.get("frontier_degradation_rate")
            if fd_raw is not None and isinstance(fd_raw, dict):
                frontier_degradation_rate_overrides = tuple(
                    (str(tag), float(rate)) for tag, rate in fd_raw.items()
                )

            if supply_raw.get("right_tail_refresh_degradation") is not None:
                right_tail_refresh_degradation = float(
                    supply_raw["right_tail_refresh_degradation"]
                )

        environment = EnvironmentConditionsSpec(
            family=family,  # type: ignore[arg-type]
            time_override=time_override,
            model_override=model_override,
            staffing_response_overrides=staffing_response_overrides,
            right_tail_prize_count=right_tail_prize_count,
            flywheel_count=flywheel_count,
            enabler_count=enabler_count,
            quick_win_count=quick_win_count,
            frontier_degradation_rate_overrides=frontier_degradation_rate_overrides,
            right_tail_refresh_degradation=right_tail_refresh_degradation,
        )

        # ── Architecture ──────────────────────────────────────────────────
        arch_data: dict = data.get("architecture", {})

        ramp_shape_str = str(arch_data.get("ramp_shape", "linear")).lower()
        ramp_shape_map: dict[str, RampShape] = {"linear": RampShape.LINEAR}
        if ramp_shape_str not in ramp_shape_map:
            raise ValueError(
                f"Unknown ramp_shape {ramp_shape_str!r}. Valid values: {list(ramp_shape_map)}."
            )
        ramp_shape = ramp_shape_map[ramp_shape_str]

        team_sizes_raw = arch_data.get("team_sizes")
        team_sizes: tuple[int, ...] | None = (
            tuple(int(s) for s in team_sizes_raw) if team_sizes_raw is not None else None
        )

        workforce = WorkforceArchitectureSpec(
            total_labor_endowment=int(arch_data.get("total_labor_endowment", 210)),
            team_count=int(arch_data.get("team_count", 24)),
            team_sizes=team_sizes,
            ramp_period=int(arch_data.get("ramp_period", 4)),
            ramp_multiplier_shape=ramp_shape,
        )

        def _opt_float(v: Any) -> float | None:
            return float(v) if v is not None else None

        # Parse portfolio mix targets if provided.
        mix_targets_raw = arch_data.get("portfolio_mix_targets")
        parsed_mix_targets: PortfolioMixTargets | None = None
        if mix_targets_raw is not None and isinstance(mix_targets_raw, dict):
            # Flat form: {flywheel: 0.40, right_tail: 0.20, ...}
            # or structured form with 'targets' key.
            if "targets" in mix_targets_raw:
                targets_data = mix_targets_raw["targets"]
                tolerance = float(mix_targets_raw.get("tolerance", 0.10))
            else:
                # Flat form: all keys are bucket names.
                targets_data = mix_targets_raw
                tolerance = 0.10

            bucket_targets = tuple((str(k), float(v)) for k, v in targets_data.items())
            parsed_mix_targets = PortfolioMixTargets(
                bucket_targets=bucket_targets,
                tolerance=tolerance,
            )

        architecture = GovernanceArchitectureSpec(
            workforce=workforce,
            low_quality_belief_threshold=_opt_float(arch_data.get("low_quality_belief_threshold")),
            max_low_quality_belief_labor_share=_opt_float(
                arch_data.get("max_low_quality_belief_labor_share")
            ),
            max_single_initiative_labor_share=_opt_float(
                arch_data.get("max_single_initiative_labor_share")
            ),
            portfolio_mix_targets=parsed_mix_targets,
            # exec_intent_spec.md #7: baseline value per idle team per week.
            # YAML key is the exec-facing name; it maps 1:1 to the engine's
            # ModelConfig.baseline_value_per_tick at resolve time.
            baseline_value_per_team_week=_opt_float(arch_data.get("baseline_value_per_team_week")),
        )

        # ── Policy ────────────────────────────────────────────────────────
        policy_data: dict = data.get("policy", {})
        preset = str(policy_data.get("preset", "balanced"))
        policy = OperatingPolicySpec(preset=preset)  # type: ignore[arg-type]

        # ── World seeds ───────────────────────────────────────────────────
        seeds_raw = data.get("world_seeds", [42])
        if isinstance(seeds_raw, int):
            seeds_raw = [seeds_raw]
        world_seeds = tuple(int(s) for s in seeds_raw)

        # ── Reporting ─────────────────────────────────────────────────────
        reporting_cfg: ReportingConfig | None = None
        if data.get("reporting") is not None:
            r = data["reporting"]
            reporting_cfg = ReportingConfig(
                record_manifest=bool(r.get("record_manifest", True)),
                record_per_tick_logs=bool(r.get("record_per_tick_logs", True)),
                record_event_log=bool(r.get("record_event_log", True)),
            )

        return cls(
            name=name,
            title=title,
            description=description,
            environment=environment,
            architecture=architecture,
            policy=policy,
            world_seeds=world_seeds,
            reporting=reporting_cfg,
            value_unit=value_unit,
        )


# ---------------------------------------------------------------------------
# Resolution result
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ResolvedRunDesign:
    """Concrete configuration objects resolved from a RunDesignSpec.

    The output of resolve_run_design(). Contains all simulator-ready
    configuration objects together with the source RunDesignSpec for
    provenance. All fields are fully resolved, frozen, and ready for
    the engine to consume.

    Attributes:
        spec: Source RunDesignSpec for provenance. Not consumed by the engine.
        workforce: Resolved WorkforceConfig from the governance architecture.
        environment_spec: EnvironmentSpec with architecture-resolved workforce.
            initiative_generator, time, and model come from the environment
            family; teams comes from the governance architecture.
        governance: GovernanceConfig with operating policy parameters from the
            preset and portfolio guardrails from the architecture.
        simulation_configs: One SimulationConfiguration per world seed, ready
            for run_single_regime() or equivalent.
    """

    spec: RunDesignSpec
    workforce: WorkforceConfig
    environment_spec: EnvironmentSpec
    governance: GovernanceConfig
    simulation_configs: tuple[SimulationConfiguration, ...]

    def summary(self) -> str:
        """Human-readable summary of the resolved design for inspection.

        Formats all three layers plus execution parameters. Intended for
        interactive inspection before running, log output, and debugging.
        The format is stable enough for copy-paste into docs but is not
        a serialization format.

        Returns:
            Multi-line string summarizing the resolved design.
        """
        spec = self.spec
        env = self.environment_spec
        gov = self.governance
        wf = self.workforce
        arch = spec.architecture

        lines: list[str] = []

        lines.append(f'Run Design: "{spec.name}"')
        lines.append(f"Title:       {spec.title}")
        if spec.description:
            lines.append(f"Description: {spec.description}")
        lines.append("")

        # ── Environment ──────────────────────────────────────────────────
        lines.append("── Environment ─────────────────────────────────────────────")
        lines.append(f"  Family:  {spec.environment.family}")
        lines.append(f"  Horizon: {env.time.tick_horizon} {env.time.tick_label}s")
        gen = env.initiative_generator
        pool_size = sum(s.count for s in gen.type_specs)
        type_summary = ", ".join(f"{s.count} {s.generation_tag}" for s in gen.type_specs)
        lines.append(f"  Pool:    {pool_size} initiatives ({type_summary})")
        m = env.model
        lines.append(
            f"  Model:   exec_budget={m.exec_attention_budget}, "
            f"init_belief={m.default_initial_quality_belief}, "
            f"ref_ceiling={m.reference_ceiling}, "
            f"learning_rate={m.learning_rate}"
        )

        # Show conductor-facing environment overrides if any are set.
        env_spec = spec.environment
        if env_spec.staffing_response_overrides is not None:
            sr_parts = [
                f"{tag}=[{lo}, {hi}]" for tag, (lo, hi) in env_spec.staffing_response_overrides
            ]
            lines.append(f"  Staffing response: {', '.join(sr_parts)}")
        # Per-bucket portfolio-mix count overrides (exec_intent_spec.md #5).
        # Each surfaces only if the exec explicitly set it, so default pool
        # compositions stay hidden in the summary.
        if env_spec.right_tail_prize_count is not None:
            lines.append(f"  Right-tail prize count: {env_spec.right_tail_prize_count}")
        if env_spec.flywheel_count is not None:
            lines.append(f"  Flywheel count: {env_spec.flywheel_count}")
        if env_spec.enabler_count is not None:
            lines.append(f"  Enabler count: {env_spec.enabler_count}")
        if env_spec.quick_win_count is not None:
            lines.append(f"  Quick-win count: {env_spec.quick_win_count}")
        if env_spec.frontier_degradation_rate_overrides is not None:
            fd_parts = [
                f"{tag}={rate}" for tag, rate in env_spec.frontier_degradation_rate_overrides
            ]
            lines.append(f"  Frontier degradation: {', '.join(fd_parts)}")
        if env_spec.right_tail_refresh_degradation is not None:
            lines.append(
                f"  Right-tail refresh degradation: {env_spec.right_tail_refresh_degradation}"
            )
        lines.append("")

        # ── Governance Architecture ───────────────────────────────────────
        lines.append("── Governance Architecture ──────────────────────────────────")
        if isinstance(wf.team_size, int):
            team_desc = f"{wf.team_count} teams × {wf.team_size}"
        else:
            team_desc = f"{wf.team_count} teams (varied sizes: {list(wf.team_size)})"
        lines.append(f"  Workforce: {team_desc} = {wf.total_labor_endowment} total labor")
        try:
            ramp_name = wf.ramp_multiplier_shape.name.lower()
        except AttributeError:
            ramp_name = str(wf.ramp_multiplier_shape)
        lines.append(f"  Ramp:      {wf.ramp_period} ticks, {ramp_name}")
        guardrails: list[str] = []
        if arch.low_quality_belief_threshold is not None:
            guardrails.append(f"low-quality threshold={arch.low_quality_belief_threshold}")
        if arch.max_low_quality_belief_labor_share is not None:
            guardrails.append(
                f"max low-quality share={arch.max_low_quality_belief_labor_share:.0%}"
            )
        if arch.max_single_initiative_labor_share is not None:
            guardrails.append(
                f"max single-initiative share={arch.max_single_initiative_labor_share:.0%}"
            )
        lines.append(f"  Portfolio: {', '.join(guardrails) if guardrails else 'no guardrails'}")
        if arch.portfolio_mix_targets is not None:
            pmt = arch.portfolio_mix_targets
            mix_parts = [f"{name}={share:.0%}" for name, share in pmt.bucket_targets]
            lines.append(f"  Mix targets: {', '.join(mix_parts)}")
            lines.append(f"  Mix tolerance: {pmt.tolerance:.0%}")
        # Surface the exec-facing baseline value rate if set. The resolved
        # model field is equivalent (see _apply_baseline_value_override);
        # we display the authoring-surface label for clarity.
        if arch.baseline_value_per_team_week is not None:
            lines.append(
                f"  Baseline value: {arch.baseline_value_per_team_week} "
                f"{spec.value_unit}/team-week"
            )
        lines.append("")

        # ── Operating Policy ─────────────────────────────────────────────
        lines.append("── Operating Policy ─────────────────────────────────────────")
        lines.append(f"  Preset:   {spec.policy.preset} (policy_id={gov.policy_id!r})")
        if gov.confidence_decline_threshold is not None:
            lines.append(f"  Confidence decline: threshold={gov.confidence_decline_threshold}")
        else:
            lines.append("  Confidence decline: disabled")
        lines.append(
            f"  TAM:      ratio={gov.tam_threshold_ratio}, "
            f"patience={gov.base_tam_patience_window} ticks"
        )
        lines.append(
            f"  Stagnation: window={gov.stagnation_window_staffed_ticks} staffed ticks, "
            f"Δbelief<{gov.stagnation_belief_change_threshold}"
        )
        attn_max = gov.attention_max if gov.attention_max is not None else "uncapped"
        lines.append(f"  Attention: min={gov.attention_min}, max={attn_max}")
        if gov.exec_overrun_threshold is not None:
            lines.append(f"  Exec overrun: threshold={gov.exec_overrun_threshold}")
        else:
            lines.append("  Exec overrun: disabled")
        lines.append("")

        # ── Execution ────────────────────────────────────────────────────
        lines.append("── Execution ────────────────────────────────────────────────")
        n = len(spec.world_seeds)
        lines.append(f"  World seeds: {list(spec.world_seeds)}")
        lines.append(f"  → {n} simulation run{'s' if n != 1 else ''}")
        # Report-layer value-unit label (exec_intent_spec.md #8). Free-text;
        # the simulator is unit-agnostic.
        lines.append(f"  Value unit: {spec.value_unit}")

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Public API: validate and resolve
# ---------------------------------------------------------------------------


def validate_run_design(spec: RunDesignSpec) -> None:
    """Validate a RunDesignSpec. Raises ValueError with all issues collected.

    Checks all three layers plus metadata and execution parameters.
    Collects every violation before raising so the caller can fix all
    issues at once rather than discovering them one at a time.

    Validation stages:
        1. Metadata constraints (name non-empty, no spaces; title non-empty;
           world_seeds non-empty).
        2. Architecture-level guardrail constraints (portfolio field ranges
           and cross-field consistency).
        3. Workforce resolution (delegates to WorkforceArchitectureSpec.resolve()).
        4. Environment resolution (delegates to make_environment_spec()).
        5. Full GovernanceConfig construction and SimulationConfiguration
           validation via validate_configuration() for the first world seed.

    Args:
        spec: RunDesignSpec to validate.

    Raises:
        ValueError: If any validation rule is violated. The message lists
            all violations, one per line.
    """
    errors: list[str] = []

    # ── Metadata ──────────────────────────────────────────────────────────
    if not spec.name:
        errors.append("name must not be empty.")
    elif " " in spec.name:
        errors.append(
            f"name must not contain spaces (use underscores or hyphens), got: {spec.name!r}."
        )
    if not spec.title:
        errors.append("title must not be empty.")
    if not spec.world_seeds:
        errors.append("world_seeds must not be empty.")

    # ── Environment overrides (early validation) ────────────────────────
    env = spec.environment
    if env.staffing_response_overrides is not None:
        for tag, (lo, hi) in env.staffing_response_overrides:
            if tag not in CANONICAL_BUCKET_NAMES:
                errors.append(
                    f"staffing_response: unknown family {tag!r}. "
                    f"Valid families: {sorted(CANONICAL_BUCKET_NAMES)}."
                )
            if lo < 0 or hi < 0:
                errors.append(
                    f"staffing_response[{tag!r}]: scale range values must be "
                    f">= 0, got ({lo}, {hi})."
                )
            if lo > hi:
                errors.append(f"staffing_response[{tag!r}]: min ({lo}) must be <= max ({hi}).")

    # Per-bucket portfolio-mix counts (exec_intent_spec.md #5). Each must be
    # non-negative when set. Aggregate total is also checked when any count is
    # set, enforcing the spec's 50–400 envelope on the initial pool size.
    if env.right_tail_prize_count is not None and env.right_tail_prize_count < 0:
        errors.append(f"right_tail_prize_count must be >= 0, got {env.right_tail_prize_count}.")
    if env.flywheel_count is not None and env.flywheel_count < 0:
        errors.append(f"flywheel_count must be >= 0, got {env.flywheel_count}.")
    if env.enabler_count is not None and env.enabler_count < 0:
        errors.append(f"enabler_count must be >= 0, got {env.enabler_count}.")
    if env.quick_win_count is not None and env.quick_win_count < 0:
        errors.append(f"quick_win_count must be >= 0, got {env.quick_win_count}.")

    # Total-pool-size envelope check: when any count override is set, the
    # resolved pool (applying only the specified overrides; family defaults
    # fill in the rest) must fall in [50, 400] per exec_intent_spec.md #5.
    # Defer this check to after environment resolution when all four values
    # can be known — done in the main validation pass below.

    if env.frontier_degradation_rate_overrides is not None:
        for tag, rate in env.frontier_degradation_rate_overrides:
            if tag not in CANONICAL_BUCKET_NAMES:
                errors.append(
                    f"frontier_degradation_rate: unknown family {tag!r}. "
                    f"Valid families: {sorted(CANONICAL_BUCKET_NAMES)}."
                )
            if rate < 0:
                errors.append(
                    f"frontier_degradation_rate[{tag!r}]: rate must be >= 0, got {rate}."
                )

    if env.right_tail_refresh_degradation is not None and env.right_tail_refresh_degradation < 0:
        errors.append(
            f"right_tail_refresh_degradation must be >= 0, "
            f"got {env.right_tail_refresh_degradation}."
        )

    # ── Architecture layer ────────────────────────────────────────────────
    spec.architecture.validate(errors)

    workforce: WorkforceConfig | None = None
    try:
        workforce = spec.architecture.resolve_workforce()
    except ValueError as exc:
        errors.append(f"Workforce architecture resolution failed: {exc}")

    # ── Environment layer ─────────────────────────────────────────────────
    env_base: EnvironmentSpec | None = None
    try:
        env_base = spec.environment.resolve_environment_base()
    except (ValueError, KeyError) as exc:
        errors.append(f"Environment resolution failed: {exc}")

    # Initial-pool size envelope (exec_intent_spec.md #5). If any count
    # override is set, check the resolved total against the spec envelope
    # [50, 400]. Done after environment resolution so family defaults are
    # counted for unspecified buckets.
    has_any_count_override = (
        env.right_tail_prize_count is not None
        or env.flywheel_count is not None
        or env.enabler_count is not None
        or env.quick_win_count is not None
    )
    if env_base is not None and has_any_count_override:
        total_pool = sum(s.count for s in env_base.initiative_generator.type_specs)
        if not (50 <= total_pool <= 400):
            errors.append(
                f"portfolio mix total pool size {total_pool} is outside the "
                f"allowed range [50, 400] (per exec_intent_spec.md #5). "
                f"Check quick_win_count, flywheel_count, enabler_count, "
                f"and right_tail_prize_count."
            )

    # ── Policy + full config validation ───────────────────────────────────
    # Only attempt if environment and workforce both resolved cleanly — we
    # need both to build a valid SimulationConfiguration for validation.
    if env_base is not None and workforce is not None and spec.world_seeds:
        # Apply architecture-side baseline_value_per_team_week before policy
        # resolution so the validated configuration reflects the final model.
        env_base_with_value = _apply_baseline_value_override(env_base, spec.architecture)
        try:
            gov = _resolve_governance_config(
                spec.architecture, spec.policy, env_base_with_value.model
            )
        except ValueError as exc:
            errors.append(f"Policy resolution failed: {exc}")
            gov = None

        if gov is not None:
            env_with_workforce = _replace_teams(env_base_with_value, workforce)
            reporting = (
                spec.reporting if spec.reporting is not None else make_baseline_reporting_config()
            )
            try:
                sim_config = _build_sim_config(
                    env_with_workforce, gov, spec.world_seeds[0], reporting
                )
                validate_configuration(sim_config)
            except ValueError as exc:
                errors.append(f"SimulationConfiguration validation failed: {exc}")

    if errors:
        slug = spec.name or "(unnamed)"
        raise ValueError(
            f"RunDesignSpec '{slug}' validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
        )


def resolve_run_design(spec: RunDesignSpec) -> ResolvedRunDesign:
    """Resolve a RunDesignSpec into concrete configuration objects.

    Validates the spec (raising ValueError if invalid), then resolves all
    three layers into the concrete repo types that the simulator and runner
    already understand.

    Resolution order:
        1. Environment family → EnvironmentSpec (time, model, initiative_generator).
        2. Workforce architecture → WorkforceConfig (team count, sizes, ramp).
        3. Operating policy → base GovernanceConfig from preset.
        4. Architecture guardrails applied to GovernanceConfig.
        5. EnvironmentSpec assembled with architecture-resolved teams.
        6. One SimulationConfiguration built per world seed.

    The simulator boundary is preserved: the engine receives only frozen
    SimulationConfiguration objects. RunDesignSpec and its children are
    never passed to the engine or runner.

    Args:
        spec: RunDesignSpec to resolve.

    Returns:
        ResolvedRunDesign containing all concrete config objects and provenance.

    Raises:
        ValueError: If the spec fails validation.
    """
    validate_run_design(spec)

    env_base = spec.environment.resolve_environment_base()
    # Apply architecture-side baseline_value_per_team_week to env.model
    # before building downstream configs. The engine's accounting
    # (runner.py) computes cumulative baseline value as
    # `idle_team_count * ModelConfig.baseline_value_per_tick`, and the
    # 1 tick = 1 week convention makes this a 1:1 relabel of the exec's
    # "per team per week" figure.
    env_base = _apply_baseline_value_override(env_base, spec.architecture)
    workforce = spec.architecture.resolve_workforce()
    gov = _resolve_governance_config(spec.architecture, spec.policy, env_base.model)
    reporting = spec.reporting if spec.reporting is not None else make_baseline_reporting_config()

    # Replace the placeholder teams in the base EnvironmentSpec with the
    # architecture-resolved workforce. The environment family contributes
    # time, model, and initiative_generator; the governance architecture
    # contributes the concrete team structure.
    env_spec = _replace_teams(env_base, workforce)

    sim_configs = tuple(
        _build_sim_config(env_spec, gov, seed, reporting) for seed in spec.world_seeds
    )

    return ResolvedRunDesign(
        spec=spec,
        workforce=workforce,
        environment_spec=env_spec,
        governance=gov,
        simulation_configs=sim_configs,
    )


# ---------------------------------------------------------------------------
# Convenience factory
# ---------------------------------------------------------------------------


def make_baseline_run_design_spec(
    *,
    name: str,
    policy_preset: OperatingPolicyName = "balanced",
    world_seeds: tuple[int, ...] = (42,),
    family: EnvironmentFamilyName = "balanced_incumbent",
    title: str = "",
    description: str = "",
    total_labor_endowment: int = 210,
    team_count: int = 24,
    team_sizes: tuple[int, ...] | None = (
        5,
        5,
        5,
        5,
        5,
        5,
        5,
        5,
        5,
        5,
        10,
        10,
        10,
        10,
        10,
        10,
        10,
        10,
        10,
        10,
        10,
        10,
        20,
        20,
    ),
    ramp_period: int = 4,
    ramp_multiplier_shape: RampShape = RampShape.LINEAR,
    low_quality_belief_threshold: float | None = None,
    max_low_quality_belief_labor_share: float | None = None,
    max_single_initiative_labor_share: float | None = None,
    portfolio_mix_targets: PortfolioMixTargets | None = None,
) -> RunDesignSpec:
    """Build a RunDesignSpec using canonical baseline defaults.

    Convenience factory for the most common case: baseline environment,
    one of the three named policy presets, and the canonical 30-team
    mixed-size workforce. All parameters are keyword-only.

    This provides the canonical baseline design via the workbench authoring
    surface, without requiring callers to assemble the three layers manually.

    Args:
        name: Short slug for this design (no spaces).
        policy_preset: Operating policy preset name.
        world_seeds: World seeds for initiative pool generation.
        family: Environment family name.
        title: Human-readable title. Defaults to a generated title.
        description: Longer description. Defaults to empty string.
        total_labor_endowment: Total labor units (environmental quantity).
        team_count: Number of parallel work units (architecture choice).
        team_sizes: Per-team sizes. None = equal-sized teams. Defaults to
            the canonical 30-team mixed-size workforce (20x5 + 8x10 + 2x20).
        ramp_period: Team switching-cost ramp duration in ticks.
        ramp_multiplier_shape: Shape of the ramp multiplier curve.
        low_quality_belief_threshold: Portfolio guardrail threshold. None = not set.
        max_low_quality_belief_labor_share: Portfolio cap. None = not set.
        max_single_initiative_labor_share: Concentration cap. None = not set.
        portfolio_mix_targets: Portfolio mix targets. None = not set.

    Returns:
        RunDesignSpec with baseline defaults applied.
    """
    resolved_title = title or f"{family} / {policy_preset}"
    return RunDesignSpec(
        name=name,
        title=resolved_title,
        description=description,
        environment=EnvironmentConditionsSpec(family=family),
        architecture=GovernanceArchitectureSpec(
            workforce=WorkforceArchitectureSpec(
                total_labor_endowment=total_labor_endowment,
                team_count=team_count,
                team_sizes=team_sizes,
                ramp_period=ramp_period,
                ramp_multiplier_shape=ramp_multiplier_shape,
            ),
            low_quality_belief_threshold=low_quality_belief_threshold,
            max_low_quality_belief_labor_share=max_low_quality_belief_labor_share,
            max_single_initiative_labor_share=max_single_initiative_labor_share,
            portfolio_mix_targets=portfolio_mix_targets,
        ),
        policy=OperatingPolicySpec(preset=policy_preset),
        world_seeds=world_seeds,
    )


# ---------------------------------------------------------------------------
# Internal helpers (not part of the public API)
# ---------------------------------------------------------------------------


def _apply_environment_overrides(
    *,
    generator: InitiativeGeneratorConfig,
    staffing_response_overrides: tuple[tuple[str, tuple[float, float]], ...] | None,
    right_tail_prize_count: int | None,
    flywheel_count: int | None,
    enabler_count: int | None,
    quick_win_count: int | None,
    frontier_degradation_rate_overrides: tuple[tuple[str, float], ...] | None,
    right_tail_refresh_degradation: float | None,
) -> InitiativeGeneratorConfig:
    """Apply conductor-facing environment overrides to an InitiativeGeneratorConfig.

    Takes the family preset's generator config and applies any overrides that
    the conductor specified. Each override modifies the relevant fields on the
    InitiativeTypeSpec(s) for the targeted family. When an override is None,
    the preset default is preserved.

    The function works by iterating over the type specs and applying relevant
    overrides to each spec, then rebuilding the InitiativeGeneratorConfig with
    the modified specs.

    Portfolio-mix count overrides (per exec_intent_spec.md #5) are independent:
    setting `right_tail_prize_count`, `flywheel_count`, `enabler_count`, or
    `quick_win_count` replaces the corresponding bucket's count verbatim. Total
    pool size is a derived quantity, not a constraint — no cross-bucket
    rebalance happens. Callers that care about pool size control it by
    specifying all four counts explicitly.

    Args:
        generator: Base InitiativeGeneratorConfig from the family preset.
        staffing_response_overrides: Per-family staffing-response scale ranges.
            Each entry is (generation_tag, (min_scale, max_scale)).
        right_tail_prize_count: Override for the right-tail bucket's count.
        flywheel_count: Override for the flywheel bucket's count.
        enabler_count: Override for the enabler bucket's count.
        quick_win_count: Override for the quick-win bucket's count.
        frontier_degradation_rate_overrides: Per-family frontier degradation
            rate overrides. Each entry is (generation_tag, degradation_rate).
        right_tail_refresh_degradation: Per-attempt quality degradation for
            right-tail prize re-attempts.

    Returns:
        New InitiativeGeneratorConfig with overrides applied.

    Raises:
        ValueError: If an override references an unknown generation_tag.
    """
    # Build lookup dicts for per-family overrides.
    staffing_map: dict[str, tuple[float, float]] = (
        dict(staffing_response_overrides) if staffing_response_overrides else {}
    )
    frontier_map: dict[str, float] = (
        dict(frontier_degradation_rate_overrides) if frontier_degradation_rate_overrides else {}
    )

    # Validate override keys against the actual generation_tag values
    # in the generator config.
    valid_tags = {spec.generation_tag for spec in generator.type_specs}
    for tag in staffing_map:
        if tag not in valid_tags:
            raise ValueError(
                f"staffing_response_overrides: unknown generation_tag {tag!r}. "
                f"Valid tags: {sorted(valid_tags)}."
            )
    for tag in frontier_map:
        if tag not in valid_tags:
            raise ValueError(
                f"frontier_degradation_rate_overrides: unknown generation_tag {tag!r}. "
                f"Valid tags: {sorted(valid_tags)}."
            )

    # Build a per-bucket count-override lookup. Each entry replaces the
    # family-default count for that bucket; buckets not listed keep the
    # preset default. No cross-bucket rebalance — pool size is derived.
    count_overrides: dict[str, int] = {}
    if right_tail_prize_count is not None:
        count_overrides["right_tail"] = right_tail_prize_count
    if flywheel_count is not None:
        count_overrides["flywheel"] = flywheel_count
    if enabler_count is not None:
        count_overrides["enabler"] = enabler_count
    if quick_win_count is not None:
        count_overrides["quick_win"] = quick_win_count

    # Apply overrides to each type spec.
    modified_specs: list[InitiativeTypeSpec] = []
    for spec in generator.type_specs:
        tag = spec.generation_tag
        replacements: dict[str, Any] = {}

        # Staffing response override for this family.
        if tag in staffing_map:
            replacements["staffing_response_scale_range"] = staffing_map[tag]

        # Per-bucket count override. Value is used verbatim.
        if tag in count_overrides:
            replacements["count"] = count_overrides[tag]

        # Frontier degradation rate override for this family.
        if tag in frontier_map and spec.frontier is not None:
            replacements["frontier"] = dataclasses.replace(
                spec.frontier,
                frontier_degradation_rate=frontier_map[tag],
            )

        # Right-tail refresh degradation override.
        if (
            tag == "right_tail"
            and right_tail_refresh_degradation is not None
            and spec.frontier is not None
        ):
            # If we already replaced the frontier above, apply to the
            # replacement; otherwise replace the original.
            base_frontier = replacements.get("frontier", spec.frontier)
            replacements["frontier"] = dataclasses.replace(
                base_frontier,
                right_tail_refresh_quality_degradation=right_tail_refresh_degradation,
            )

        if replacements:
            modified_specs.append(dataclasses.replace(spec, **replacements))
        else:
            modified_specs.append(spec)

    return InitiativeGeneratorConfig(type_specs=tuple(modified_specs))


def _resolve_governance_config(
    architecture: GovernanceArchitectureSpec,
    policy: OperatingPolicySpec,
    model: ModelConfig,
) -> GovernanceConfig:
    """Resolve operating policy + architecture guardrails into a GovernanceConfig.

    Resolves the operating policy preset to get a base GovernanceConfig, then
    applies architecture-level portfolio guardrails via dataclasses.replace().
    This ensures the GovernanceConfig contains both operating-policy parameters
    (from the preset) and architecture-level portfolio constraints (from the
    architecture spec).

    The two-step approach is necessary because:
        - Operating-policy presets set all portfolio-risk fields to None
          (correct for their standalone use case).
        - The architecture layer owns the portfolio guardrails conceptually,
          but GovernanceConfig surfaces them for policy access (per Phase 1
          design: portfolio-risk fields remain flat in GovernanceConfig for
          backward compatibility).
    """
    base = policy.resolve(model)
    return dataclasses.replace(
        base,
        low_quality_belief_threshold=architecture.low_quality_belief_threshold,
        max_low_quality_belief_labor_share=architecture.max_low_quality_belief_labor_share,
        max_single_initiative_labor_share=architecture.max_single_initiative_labor_share,
        portfolio_mix_targets=architecture.portfolio_mix_targets,
    )


def _replace_teams(env: EnvironmentSpec, workforce: WorkforceConfig) -> EnvironmentSpec:
    """Return a new EnvironmentSpec with the teams field replaced.

    Design note: EnvironmentSpec carries a WorkforceConfig in its .teams
    field for structural completeness, but the actual workforce is determined
    by the governance architecture, not the environment. The environment family
    preset supplies a placeholder WorkforceConfig, and this helper substitutes
    the architecture-resolved workforce before the EnvironmentSpec is used to
    build any SimulationConfiguration. The placeholder must never reach the
    engine; this function is the correction point.
    """
    return EnvironmentSpec(
        time=env.time,
        teams=workforce,
        model=env.model,
        initiative_generator=env.initiative_generator,
    )


def _apply_baseline_value_override(
    env: EnvironmentSpec,
    architecture: GovernanceArchitectureSpec,
) -> EnvironmentSpec:
    """Apply architecture.baseline_value_per_team_week to the env model.

    Per exec_intent_spec.md #7, execs specify baseline-work value in
    business units (per-team per-week). The simulator's accounting already
    computes per-idle-team per-tick via ModelConfig.baseline_value_per_tick
    (see runner.py: `idle_team_count * config.model.baseline_value_per_tick`),
    and by convention 1 tick = 1 week. So the authoring-surface number maps
    1:1 into the engine field — no arithmetic conversion.

    Returns env unchanged when the architecture does not set the override.
    Otherwise returns a new EnvironmentSpec whose .model field has
    baseline_value_per_tick replaced.
    """
    if architecture.baseline_value_per_team_week is None:
        return env
    new_model = dataclasses.replace(
        env.model,
        baseline_value_per_tick=architecture.baseline_value_per_team_week,
    )
    return EnvironmentSpec(
        time=env.time,
        teams=env.teams,
        model=new_model,
        initiative_generator=env.initiative_generator,
    )


def _build_sim_config(
    env: EnvironmentSpec,
    gov: GovernanceConfig,
    seed: int,
    reporting: ReportingConfig,
) -> SimulationConfiguration:
    """Build one SimulationConfiguration from resolved components."""
    return SimulationConfiguration(
        world_seed=seed,
        time=env.time,
        teams=env.teams,
        model=env.model,
        governance=gov,
        reporting=reporting,
        initiative_generator=env.initiative_generator,
    )


# ---------------------------------------------------------------------------
# Public API: policy construction
# ---------------------------------------------------------------------------


def make_policy(governance_config: GovernanceConfig) -> GovernancePolicy:
    """Instantiate the GovernancePolicy matching the resolved GovernanceConfig.

    This is the repo-owned registry for the policy_id → policy class mapping.
    Front-end scripts should call this rather than importing and instantiating
    policy classes directly, so that adding a new preset to presets.py and
    registering it here is the only change required.

    The GovernanceConfig is not passed to the constructor — policy classes
    are stateless and receive the config via decide() at each tick. The
    config argument here is used only to look up the policy_id.

    Args:
        governance_config: Resolved GovernanceConfig whose policy_id identifies
            which policy class to instantiate.

    Returns:
        GovernancePolicy instance ready for run_single_regime().

    Raises:
        ValueError: If policy_id is not registered here.
    """
    from primordial_soup.policy import (
        AggressiveStopLossPolicy,
        BalancedPolicy,
        PatientMoonshotPolicy,
    )

    policy_id = governance_config.policy_id
    registry: dict[str, type] = {
        "balanced": BalancedPolicy,
        "aggressive_stop_loss": AggressiveStopLossPolicy,
        "patient_moonshot": PatientMoonshotPolicy,
    }
    if policy_id not in registry:
        raise ValueError(
            f"No policy class registered for policy_id={policy_id!r}. "
            f"Registered ids: {sorted(registry)}. "
            f"Add the new policy class to make_policy() in workbench.py."
        )
    return registry[policy_id]()


# ---------------------------------------------------------------------------
# Public API: result summarisation
# ---------------------------------------------------------------------------


def summarize_run_result(result: RunResult) -> dict[str, Any]:
    """Extract a flat summary dictionary from a RunResult.

    Provides the repo-owned definition of which RunResult fields constitute
    a meaningful per-run summary. Front-end scripts should call this rather
    than accessing RunResult internals directly, so that field name changes
    in reporting.py require only an update here.

    Fields match the campaign script output (run_campaign_small.py) so that
    single-run and campaign results are directly comparable.

    Args:
        result: RunResult from run_single_regime().

    Returns:
        Dictionary of scalar summary fields suitable for JSON serialisation
        or tabular display. All values are JSON-compatible primitives.
    """
    manifest = result.manifest
    cost = result.exploration_cost_profile
    timing = result.family_timing
    summary: dict[str, Any] = {
        "world_seed": manifest.world_seed,
        "policy_id": manifest.policy_id,
        "total_ticks": manifest.resolved_configuration.time.tick_horizon,
        # Value
        "cumulative_value": result.cumulative_value_total,
        "lump_value": result.value_by_channel.completion_lump_value,
        "residual_value": result.value_by_channel.residual_value,
        # Value by initiative family (Step 5.1)
        "value_by_family": dict(result.value_by_family),
        # Organisational momentum
        "free_value_per_tick": result.terminal_aggregate_residual_rate,
        "peak_productivity": result.max_portfolio_capability_t,
        "productivity_at_end": result.terminal_capability_t,
        # Ramp labor fraction (Step 5.1)
        "ramp_labor_fraction": result.ramp_labor_fraction,
        # Discovery
        "major_win_count": result.major_win_profile.major_win_count,
        # Governance quality
        "idle_team_tick_fraction": result.idle_capacity_profile.idle_team_tick_fraction,
        "pool_exhaustion_tick": result.idle_capacity_profile.pool_exhaustion_tick,
        "quality_est_error": result.belief_accuracy.mean_absolute_belief_error,
        # Initiative outcomes
        "initiatives_completed": sum(cost.completed_initiative_count_by_label.values()),
        "initiatives_stopped": sum(cost.stopped_initiative_count_by_label.values()),
        "completed_by_label": dict(cost.completed_initiative_count_by_label),
        "stopped_by_label": dict(cost.stopped_initiative_count_by_label),
        # Family timing (Step 5.2)
        "first_completion_tick_by_family": dict(timing.first_completion_tick_by_family),
        "mean_completion_tick_by_family": dict(timing.mean_completion_tick_by_family),
        "peak_capability_tick": timing.peak_capability_tick,
        "first_right_tail_stop_tick": timing.first_right_tail_stop_tick,
    }

    # Frontier summary (Step 5.1 — conditional on frontier being active).
    if result.frontier_summary is not None:
        summary["frontier_state_by_family"] = dict(result.frontier_summary.family_frontier_states)

    return summary


# ---------------------------------------------------------------------------
# Bridge: RunDesignSpec → ExperimentSpec
# ---------------------------------------------------------------------------


def build_experiment_spec_from_design(
    resolved: ResolvedRunDesign,
    seed_results: tuple[tuple[RunResult, WorldState], ...],
) -> ExperimentSpec:
    """Build an ExperimentSpec from a resolved YAML run design and its results.

    This bridges the YAML authoring layer (RunDesignSpec / ResolvedRunDesign)
    to the reporting-bundle layer (ExperimentSpec). A single YAML design
    represents one experimental condition across N world seeds, so this
    function produces an ExperimentSpec containing exactly one
    ExperimentalConditionRecord with N SeedRunRecords.

    The field mapping follows the output-unification plan:

    - experiment_name  = spec.name   (short slug from the YAML)
    - condition_id     = spec.name   (one design = one condition)
    - env_conditions   = environment family name
    - policy_id        = governance.policy_id (from the resolved GovernanceConfig)
    - regime_label     = spec.title  (human-readable)

    Args:
        resolved: A fully resolved run design (from resolve_run_design()).
        seed_results: One (RunResult, WorldState) pair per world seed, in the
            same order as resolved.simulation_configs / resolved.spec.world_seeds.

    Returns:
        An ExperimentSpec ready for create_run_bundle().
    """
    # Lazy imports to avoid circular dependencies at module load time.
    # These types are only used inside this bridge function; they live in
    # run_bundle.py which itself imports from reporting.py and state.py.
    from primordial_soup.run_bundle import (
        ExperimentalConditionRecord,
        ExperimentalConditionSpec,
        ExperimentSpec,
        SeedRunRecord,
        extract_initiative_final_states,
    )

    design_spec: RunDesignSpec = resolved.spec

    # --- Build the condition spec (identity / grouping metadata) ---
    # One YAML design = one experimental condition. We reuse the design name
    # as both the condition id and architecture id because the YAML is the
    # single defining artifact for this condition.
    environment_family_name: str = design_spec.environment.family
    operating_policy_preset_name: str = design_spec.policy.preset

    condition_spec = ExperimentalConditionSpec(
        experimental_condition_id=design_spec.name,
        environmental_conditions_id=environment_family_name,
        environmental_conditions_name=environment_family_name,
        governance_architecture_id=design_spec.name,
        governance_architecture_name=design_spec.name,
        operating_policy_id=resolved.governance.policy_id,
        operating_policy_name=operating_policy_preset_name,
        governance_regime_label=design_spec.title,
    )

    # --- Build one SeedRunRecord per (RunResult, WorldState) pair ---
    seed_run_records: list[SeedRunRecord] = []
    for run_result, world_state in seed_results:
        initiative_final_states = extract_initiative_final_states(world_state)
        seed_run_record = SeedRunRecord(
            world_seed=run_result.manifest.world_seed,
            run_result=run_result,
            initiative_final_states=initiative_final_states,
            initiative_configs=run_result.manifest.resolved_initiatives,
        )
        seed_run_records.append(seed_run_record)

    # --- Assemble the condition record ---
    # All seed runs share the same SimulationConfiguration template (only
    # world_seed varies). Use the first config as the representative.
    condition_record = ExperimentalConditionRecord(
        condition_spec=condition_spec,
        seed_run_records=tuple(seed_run_records),
        simulation_config=resolved.simulation_configs[0],
    )

    # --- Build the top-level ExperimentSpec ---
    # value_unit flows from the authoring layer (YAML / RunDesignSpec)
    # through the experiment spec into the manifest; report_gen.py applies
    # it as a display label. The engine and RunResult are unit-agnostic.
    experiment_spec = ExperimentSpec(
        experiment_name=design_spec.name,
        title=design_spec.title,
        description=design_spec.description,
        world_seeds=design_spec.world_seeds,
        condition_records=(condition_record,),
        script_name="run_design.py",
        study_phase="evaluation",
        value_unit=design_spec.value_unit,
    )

    return experiment_spec
