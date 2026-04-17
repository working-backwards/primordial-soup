# SimulationConfiguration and external interfaces

## Scope statement


### Academic
This document defines the canonical external interfaces for the study. It specifies the configuration contract, the policy API boundary, the observation structure exposed to governance, and the runner outputs required for reproducibility.

The runner outputs serve both reproducibility and downstream comparative analysis: every reported finding must be traceable to a complete provenance record that includes the resolved configuration, the realized initiative pool, and the engine version that produced it.

The purpose of this file is not only to list fields, but to make the architectural boundary explicit. In particular, it distinguishes between parameters that govern how the simulated world evolves and parameters that governance uses when making decisions. That distinction must remain explicit in code.

Collapsing these two parameter domains in the implementation would permit the policy to condition — intentionally or inadvertently — on the transition kernel's parameters rather than on the observation process alone. Because the study's causal identification rests on attributing outcome differences to policy differences under a shared stochastic environment, any leakage of world-evolution parameters into the policy boundary would invalidate that attribution. The architectural separation documented here is therefore load-bearing for the study's experimental design, not merely a code-organization preference.

The current study uses a three-layer conceptual model:

- **Environmental conditions**: exogenous facts of the run that governance must
  take as given.
- **Governance architecture**: structural choices fixed before the run begins,
  including workforce decomposition and standing portfolio guardrails.
- **Operating policy**: recurring tick-by-tick decisions made within that
  architecture.

At the simulator boundary, these layers are compiled into a single declarative
`SimulationConfiguration`. The engine consumes the realized representation; it
does not know how workforce structure or portfolio guardrails were chosen
upstream.

The simulator-policy interface is intentionally descriptive rather than
evaluative. It exposes observable state, derived counters, and configuration
needed for policy logic, but it does not embed judgments about whether an
initiative is "good" or "bad". Policy evaluation happens downstream in
analysis.

Specifically, the interface does not label belief trajectories as "improving" or "deteriorating," classify portfolio composition as "diversified" or "concentrated," evaluate governance actions against any normative benchmark, or characterize the portfolio's state as "healthy" or "unhealthy." The observation bundle provides the information required for the policy's decision function; welfare comparisons and optimality assessments belong to the post-hoc analysis layer, not the interface contract.

Naming rule:
- schema fields should use descriptive names that are easy to read in Python
  code and analysis code,
- compact mathematical symbols remain valid inside equations elsewhere in the
  corpus,
- where the two differ, `docs/study/naming_conventions.md` defines the mapping.

### Business
This document defines the formal contracts that govern how the simulation is configured, what information governance can see when making decisions, and what outputs a run must produce for reproducibility and analysis.

Its purpose is not merely to list parameters and fields. It makes explicit the architectural boundary between two fundamentally different kinds of configuration: parameters that govern how the simulated world evolves (how signals are generated, how beliefs update, how value is realized) and parameters that governance uses when making decisions (thresholds, patience windows, attention bounds). That distinction must remain explicit in the implementation, because collapsing it would allow governance to read — or inadvertently depend on — information about how the world works rather than information about what governance can observe. The entire study depends on that separation.

The study uses a three-layer conceptual model:

- **Environmental conditions**: the facts of the simulated world that governance must take as given — the initiative pool, the underlying quality distributions, the attention-to-signal relationship, the total labor available, the six-year horizon.
- **Governance architecture**: structural choices fixed before the run begins, including how the workforce is divided into teams and what standing portfolio guardrails are set.
- **Operating policy**: the recurring week-by-week decisions made within that architecture — which initiatives to continue or stop, where to allocate executive attention, which teams to assign where.

At the simulation boundary, these three layers are compiled into a single declarative configuration object. The engine consumes the realized representation. It does not know or care how the workforce structure or portfolio guardrails were chosen upstream — whether they were hand-crafted for a specific scenario, drawn from a named organizational archetype, or generated by a parameter sweep. That separation is deliberate: it means the engine's behavior is fully determined by the configuration it receives, regardless of how that configuration was produced.

The interface between the simulation and governance is intentionally descriptive rather than evaluative. It exposes observable state, derived counters, and the configuration parameters needed for governance logic. It does not embed judgments about whether an initiative is "good" or "bad," whether the portfolio is "healthy" or "unhealthy," or whether a governance decision was "right" or "wrong." Those evaluations happen downstream in analysis, not inside the simulation boundary.

The naming convention throughout is plain-language descriptive names — "strategic quality belief" rather than mathematical symbols. Where the technical specification uses compact notation in equations, the mapping between the two is recorded in the project's naming conventions reference.

## SimulationConfiguration (detailed parameter list)


### Academic
The top-level simulation configuration is the single authoritative input contract for a run. It is declarative. Randomness is controlled by seeds, not by implicit hidden runtime sampling.

There are no hidden runtime parameters; every parameter governing engine behavior is either present in the resolved configuration or derived from it deterministically.

The configuration is organized into six constituent blocks, each governing a distinct domain of the simulation. The decomposition reflects the study's architectural boundary: `ModelConfig` contains parameters governing the world-state transition kernel (signal generation, belief dynamics, value realization, capability accumulation), while `GovernanceConfig` contains the immutable decision parameters supplied to the policy function. These must remain in separate configuration domains in the implementation, because a merged structure would permit the policy to condition — intentionally or inadvertently — on transition-model parameters rather than on the observation process alone. The structural separation is therefore load-bearing for the study's causal identification, not merely an organizational convenience.

Canonical structure:

```python
SimulationConfiguration = {
  "world_seed": int,
  "time": TimeConfig,
  "teams": WorkforceConfig,
  "model": ModelConfig,
  "governance": GovernanceConfig,
  "reporting": ReportingConfig,
  "initiatives": list[ResolvedInitiativeConfig] | None,
  "initiative_generator": InitiativeGeneratorConfig | None,
}
```

Exactly one of `initiatives` or `initiative_generator` must be provided. If `initiative_generator` is provided, the runner must deterministically resolve it into a fully materialized `initiatives` list before simulation start using `world_seed`. The engine should always receive a resolved list.

#### TimeConfig

`time` defines the temporal structure of the run.

```python
TimeConfig = {
  "tick_horizon": int,
  "tick_label": str,   # e.g. "week" or "month"
}
```

#### WorkforceConfig

`teams` defines the execution-capacity structure.

```python
WorkforceConfig = {
  "team_count": int,
  "team_size": int | tuple[int, ...],
  # Derived property in code: total_labor_endowment = aggregate labor across
  # all teams. This is an environmental quantity. team_count and team_size are
  # the realized decomposition of that labor into teams.
  "ramp_period": int,
  # "linear" | "exponential". Governs ramp_multiplier computation.
  # Canonical ramp is assignment-relative: t_elapsed = ticks_since_assignment.
  #   linear:      ramp_multiplier = min((t_elapsed + 1) / R, 1.0)
  #   exponential: uses the same normalized fraction with a fixed k.
  # First staffed tick after assignment is partially productive; fully ramped when t_elapsed >= R - 1.
  "ramp_multiplier_shape": str,
}
```

The canonical ramp interpretation is assignment-relative and uses
`ticks_since_assignment`, not lifetime staffed time. The operative tick semantics
and formula are defined in `core_simulator.md`; if these documents diverge,
`core_simulator.md` controls.

If `team_size` is a scalar, all teams are equal-sized. If it is a list, one entry must exist per team. Canonical experiments should still treat teams as equivalent in skill even if size varies.

The simulator consumes `WorkforceConfig` as a **realized workforce
representation**. How that representation was produced — directly,
deterministically from a builder-layer architecture spec, or through a future
experimental sweep over architectures — is outside the engine boundary.

Ramp characteristics (period and shape) are properties of the workforce structure, not of the operating policy. They belong to the governance-architecture layer: chosen before the run begins and held fixed throughout. The ramp formula governs how quickly a newly assigned team achieves full learning efficiency and is therefore an organizational-structure parameter, not a per-tick governance decision.

#### ModelConfig

`model` contains parameters that the engine uses to evolve world state, generate observations, and detect state transitions. These are not governance decision thresholds unless they are explicitly surfaced through the observation interface.

```python
ModelConfig = {
  "exec_attention_budget": float,

  "base_signal_st_dev_default": float,  # sigma_base_default in the design docs
  "dependency_noise_exponent": float,  # alpha_d in the design docs

  # Canonical default initial quality belief used when an initiative does not
  # specify an explicit strategic prior. The canonical value is 0.5.
  #
  # Rationale:
  # - 0.5 is the neutral symmetric baseline in the bounded belief space [0,1].
  # - It keeps early stop/continue behavior from being pre-biased toward either
  #   optimism or pessimism before any initiative-specific signal has been
  #   observed.
  # - Systematic intake optimism or pessimism is still in scope, but it belongs
  #   in sensitivity analysis through explicit variation of this parameter rather
  #   than being embedded in the canonical default.
  "default_initial_quality_belief": float,

  # Normalization constant for prize-relative bounded-prize patience.
  # The canonical study interprets base_tam_patience_window (T_tam) as base
  # patience and scales realized patience linearly with observable_ceiling
  # relative to this value.
  # Must be > 0.
  "reference_ceiling": float,

  "attention_noise_threshold": float,       # a_min in the design docs
  "low_attention_penalty_slope": float,     # k_low in the design docs
  "attention_curve_exponent": float,        # k in the design docs
  "min_attention_noise_modifier": float,    # g_min in the design docs
  "max_attention_noise_modifier": float | None,   # g_max in the design docs; None means no upper clamp is applied to the attention noise modifier

  "learning_rate": float,
  "dependency_learning_scale": float | None,

  # Execution signal parameters.
  # Used only for initiatives where true_duration_ticks is set.
  "execution_signal_st_dev": float,   # sigma_exec in the design docs; observation noise for the per-tick execution progress signal z_t
  "execution_learning_rate": float,   # eta_exec in the design docs; learning rate for execution belief update

  # Portfolio capability parameters.
  # max_portfolio_capability (C_max) is an environmental property of the
  # simulated world: the maximum cumulative portfolio learning capability
  # achievable through enabler completions in this environment. In the
  # canonical study, portfolio_capability_t (C_t) is a portfolio-level scalar
  # initialized at 1.0 and bounded above by C_max. It governs how much enabler
  # completions can reduce effective strategic signal noise through the
  # effective_signal_st_dev_t divisor. It belongs in ModelConfig because it
  # governs how world state evolves, not because governance can choose it. The
  # generator controls the distribution of capability_contribution_scale values
  # across enabler initiatives; C_max controls the state space within which
  # those contributions accumulate. These are distinct concerns and must
  # remain in distinct configuration domains.
  "max_portfolio_capability": float,  # C_max in the design docs; ceiling on portfolio capability C_t; C_t is clamped to [1.0, max_portfolio_capability] after each capability update. Must be >= 1.0.
  "capability_decay": float,  # per-tick exponential decay rate applied to the excess capability stock (C_t - 1.0). Must be >= 0.

  # Per-team value accrual each tick when the team is NOT assigned to a
  # portfolio initiative. Runner-side accounting; the engine does not
  # consume this field. Surfaced on RunResult.cumulative_baseline_value.
  # Default 0.0 (opt-in) — studies that want to credit baseline work
  # (maintenance, operational improvements, etc.) set it explicitly.
  # Per governance.md "Baseline work semantics" and design_decisions.md
  # decision 23.
  "baseline_value_per_tick": float,  # default 0.0; calibrated nonzero value 0.1
}
```

#### GovernanceConfig

`governance` contains the immutable decision parameters supplied to the governance policy.

```python
GovernanceConfig = {
  "policy_id": str,

  # Read-only copy of ModelConfig.exec_attention_budget, populated by the engine at
  # run initialization. The policy must use this value when computing SetExecAttention
  # allocations to avoid budget violations. The policy cannot change this value.
  "exec_attention_budget": float,

  # Read-only copy of the canonical non-TAM stagnation baseline used when
  # evaluating whether quality belief has risen above the neutral starting
  # point.
  "default_initial_quality_belief": float,

  "confidence_decline_threshold": float | None,  # theta_stop in the design docs

  # TAM adequacy rule parameters.
  "tam_threshold_ratio": float,  # theta_tam_ratio in the design docs
  "base_tam_patience_window": int,  # T_tam in the design docs; number of consecutive
                                    # governance evaluations earned by an initiative
                                    # whose observable_ceiling == reference_ceiling.
                                    # Realized bounded-prize patience scales linearly
                                    # with observable_ceiling. TYPE IS int, NOT float or monetary.

  # Stagnation rule parameters.
  "stagnation_window_staffed_ticks": int,     # W_stag in the design docs; length in staffed ticks (not calendar ticks).
  "stagnation_belief_change_threshold": float,  # epsilon_stag in the design docs

  # Attention allocation bounds.
  # Operational meaning:
  # - attention_min is the minimum nonzero executive-attention level that the
  #   policy may assign to a staffed initiative it chooses to cover with explicit
  #   attention. It is not an automatic entitlement and it is not applied by the
  #   engine except as the documented fallback under an attention-feasibility
  #   violation event.
  # - attention_max is the maximum executive-attention level assignable to any
  #   single initiative on a tick.
  # - Canonical policies may assign attention = 0.0 to a staffed initiative unless
  #   they explicitly choose to give it positive attention, in which case the
  #   assigned value must be in [attention_min, attention_max].
  # - In the canonical study, attention_min is required and must be non-null.
  #   This is intentional. The study's attention-to-signal mechanism makes a
  #   substantive claim about a harmful shallow-attention region below a minimum
  #   threshold. That threshold must therefore exist in canonical runs rather than
  #   being optional.
  # - Exception: attention_min = 0.0 is valid when exec_attention_budget = 0.0.
  #   This represents a governance configuration where no executive attention is
  #   allocated. When the budget is zero, the policy emits no SetExecAttention
  #   actions and all initiatives receive attention = 0.0 via the omission-means-zero
  #   contract. The attention curve g(a) still applies at a = 0, so signal quality
  #   is determined entirely by g(0) and the base noise parameters.
  # - If attention_max is None, the canonical interpretation is 1.0.
  "attention_min": float,
  "attention_max": float | None,

  # Budget-feasibility rule:
  # An end-of-tick proposed attention allocation is feasible iff the sum of all
  # SetExecAttention actions in that action vector is <= exec_attention_budget and
  # each individual assigned value satisfies the per-initiative bounds above.
  # The policy must treat exec_attention_budget as a hard constraint, not as a
  # soft target.

  # Execution overrun tolerance.
  # When execution_belief_t falls below this level, governance may flag execution concern.
  # None means no automatic execution flagging; policy logic handles it explicitly.
  "exec_overrun_threshold": float | None,

  # Optional portfolio-risk controls. These are policy-side governance
  # preferences, not engine-enforced constraints.
  #
  # If low_quality_belief_threshold is set together with
  # max_low_quality_belief_labor_share, the policy may treat initiatives whose
  # current strategic belief is below the threshold as low-confidence work and
  # constrain the share of active labor allocated to them.
  "low_quality_belief_threshold": float | None,
  "max_low_quality_belief_labor_share": float | None,

  # Optional concentration control. If set, the policy may constrain the maximum
  # share of currently active labor allocated to any single initiative.
  "max_single_initiative_labor_share": float | None,

  # Portfolio mix targets: desired labor-share distribution across canonical
  # initiative buckets. The policy may use these as soft preferences during
  # team assignment. None means no mix targets configured.
  "portfolio_mix_targets": PortfolioMixTargets | None,
}
```

Decision thresholds belong in `GovernanceConfig`. These values are read by the policy but do not evolve during a run. Any counters or rolling windows required by these thresholds must live in engine-owned initiative state, not in hidden mutable policy memory.

Portfolio-risk parameters are optional governance controls, not engine
obligations. The engine exposes the portfolio state needed to compute them, but
the policy decides whether and how to honor them.

#### ReportingConfig

`reporting` defines output behavior only. It must not affect simulation mechanics.

```python
ReportingConfig = {
  "record_manifest": bool,
  "record_per_tick_logs": bool,
  "record_event_log": bool,
  "label_groupings": tuple[str, ...] | None,
}
```

#### Defaults and validation

The runner should validate required parameters are present and that numeric bounds hold. At minimum, validation should enforce:

- exactly one of `initiatives` or `initiative_generator`
- `tick_horizon > 0`
- `team_count > 0`
- `0 <= attention_noise_threshold <= 1`
- `low_attention_penalty_slope >= 0`
- `reference_ceiling > 0`
- if `max_attention_noise_modifier` is set, then `0 <= min_attention_noise_modifier <= max_attention_noise_modifier`
- `stagnation_window_staffed_ticks >= 1`
- `stagnation_belief_change_threshold >= 0`
- `max_portfolio_capability >= 1.0`
- `capability_decay >= 0`
- `0 < default_initial_quality_belief < 1` or, if boundary values are permitted in
  implementation, at minimum `0 <= default_initial_quality_belief <= 1`. The canonical
  default is `0.5`.
- `attention_min` must be present and satisfy `0 < attention_min <= 1`.
  **Exception:** `attention_min = 0.0` is valid when `exec_attention_budget = 0.0`,
  representing a governance configuration where no executive attention is allocated.
  When the budget is zero, the policy emits no `SetExecAttention` actions and all
  initiatives receive attention = 0.0 (the omission-means-zero contract)
- if `attention_max` is set, then `0 <= attention_max <= 1`
- if `attention_max` is set, then `attention_min <= attention_max`
- `base_tam_patience_window` must be a Python `int`, not a float. YAML parsers may silently coerce
  `5` to `5.0`; enforce with:
  ```python
  assert isinstance(config.base_tam_patience_window, int), (
      f"base_tam_patience_window must be int, got {type(config.base_tam_patience_window).__name__}. "
      f"YAML parsers may silently coerce '5' to float 5.0; "
      f"use explicit int casting when loading YAML configs."
  )
  ```
  Also add `int(config['base_tam_patience_window'])` when constructing `GovernanceConfig` from a
  YAML-sourced dict, since YAML does not distinguish integer 5 from float 5.0
  without a type tag.
- `execution_signal_st_dev >= 0`
- `0 < execution_learning_rate <= 1`
- if `planned_duration_ticks` is set on an initiative, it must be > 0
- if `true_duration_ticks` is set on an initiative, it must be > 0
- if `initial_execution_belief` is set on an initiative, it must be in (0, 1]
- if `true_duration_ticks` is set, `planned_duration_ticks` must also be set
  (the execution channel requires both a latent truth and an observable prior)
- `capability_contribution_scale >= 0` for every initiative where it is set
- if `value_channels.completion_lump.enabled == true`, then
  `value_channels.completion_lump.realized_value` must be present and satisfy
  `realized_value >= 0`. An enabled completion-lump channel with an absent or
  null realized_value is a schema violation. The engine must not silently
  default to zero; the runner must reject the configuration at load time with
  an explicit error.
- if `value_channels.residual.enabled == true`, then `value_channels.residual.residual_decay`
  must be present and satisfy `residual_decay >= 0`.
- capability-on-completion requires duration: if
  `capability_contribution_scale > 0`, then `true_duration_ticks` must be set on
  the initiative. In the canonical model, capability updates occur only at the
  completion transition, so an initiative without a completion condition cannot
  validly contribute capability.
- residual-on-completion requires duration: if `value_channels.residual.enabled == true` and `value_channels.residual.activation_state == "completed"`, then `true_duration_ticks` must be set on the initiative. Without it the engine cannot detect the completion transition that triggers residual activation.

The runner should record the fully resolved configuration in the manifest so provenance is complete even when defaults are applied.

Canonical warning condition:

- if `confidence_decline_threshold is not None` and `confidence_decline_threshold >= default_initial_quality_belief`,
  emit a validation warning that the non-TAM stagnation path may be dominated by
  the confidence-decline threshold and therefore become unreachable in practice.

Terminology note:

- `quality_belief_t` is the descriptive schema name for the strategic belief
  state often written as `c_t` in equations.
- `execution_belief_t` is the descriptive schema name for the execution-fidelity
  belief state often written as `c_exec_t`.
- "base signal st_dev" and "effective signal st_dev" are the descriptive names
  for the quantities often written as `sigma_base` and `sigma_eff`.

Stage 3-5 field additions (documented here for completeness; see
`dynamic_opportunity_frontier.md` and the implementation plan for design
authority):

- `ResolvedInitiativeConfig.staffing_response_scale` (float, default 0.0):
  controls how additional staffing above `required_team_size` accelerates
  learning. Per `opportunity_staffing_intensity_design_for_claude_v2.md`.
- `ResolvedInitiativeConfig.prize_id` (str | None): links right-tail
  frontier re-attempts back to the original prize descriptor. Per
  `dynamic_opportunity_frontier.md` §2.
- `WorldState.frontier_state_by_family` (tuple of (str,
  FamilyFrontierState) pairs): per-family frontier exhaustion tracking.
  Runner-managed. Stored on WorldState for state-completeness but not read or modified by the engine (tick.py).
- `WorldState.available_prize_descriptors` (tuple of PrizeDescriptor):
  right-tail prizes available for re-attempt. Runner-owned.

```python
epsilon_exec: float = 0.05
# Floor on execution_belief_t used in implied_duration_ticks to prevent division by near-zero.
# Caps implied duration at 20× planned_duration_ticks (at execution_belief_t = 0.05).
# Defined as a module-level constant; not a tunable config parameter.
```

### Business
The simulation configuration is the single authoritative input contract for a run. It is a complete, declarative specification of everything needed to execute the simulation. There are no hidden runtime parameters, no implicit defaults that change behavior silently, and no randomness beyond what is explicitly controlled by seeds.

The configuration is organized into six blocks, each governing a distinct aspect of the simulation. Understanding what lives where — and why — matters because it reflects the study's architectural boundary between the world the organization operates in and the governance decisions made within that world.

**Time configuration.** Defines the temporal structure of the run: how many periods the simulation covers and what each period represents (for example, a week or a month). The canonical study uses a six-year horizon measured in weekly periods.

**Workforce configuration.** Defines the organization's execution capacity — how many teams exist, how large each team is, and what happens when a team is newly assigned to an initiative (the ramp-up period and its shape).

The workforce configuration is a realized representation. It specifies the concrete teams the organization has, not the reasoning behind how those teams were formed. Whether the team structure was chosen by a chief operating officer, derived from a workforce planning model, or generated by the study's parameter sweep is outside the engine's concern. The engine consumes the teams it is given and operates with them.

If all teams are equal-sized, a single size value applies to all. If teams differ in size, each team's size must be specified individually. Even when team sizes vary, the canonical study treats all teams as equivalent in skill — size differences affect what initiatives a team can be assigned to (based on staffing requirements) but not the quality of the team's work.

The ramp-up period — how long a newly assigned team operates at reduced learning efficiency — is specified here along with the shape of the ramp (whether productivity increases at a steady rate or improves quickly at first and then levels off). These are properties of the organizational structure, not of individual governance decisions. The precise ramp formula and its tick-level semantics are defined in the core simulator specification; if these documents diverge, the core simulator controls.

**Model configuration.** Contains the parameters that govern how the simulated world evolves — how signals are generated, how noisy those signals are, how beliefs update, how capability accumulates and decays, and how value is realized. These are the physics of the simulated world. They are not governance decision thresholds unless they are explicitly surfaced through the observation interface.

The model configuration includes:

- *Executive attention budget.* The hard weekly limit on total executive attention available across the portfolio. This is an environmental constraint — it defines the scarce resource that governance must allocate.

- *Signal noise parameters.* The default baseline noise level for strategic signals, and how much initiative dependency amplifies that noise. These govern how hard it is, by default, to read the strategic evidence an initiative produces.

- *Default initial quality belief.* The starting point for the organization's estimate of any initiative's strategic quality when no initiative-specific prior is provided. The canonical value is 0.5 — the neutral midpoint of the belief scale, representing maximum prior uncertainty. This keeps early governance decisions from being pre-biased toward either optimism or pessimism before any initiative-specific evidence has been observed. If the study wants to test systematic intake optimism or pessimism, it should do so by explicitly varying this parameter in a sensitivity analysis, not by embedding a bias in the default.

- *Reference ceiling for patience scaling.* A normalization constant used by the bounded-prize patience rule. When governance evaluates whether a bounded opportunity has earned enough patience to justify continued investment, the patience window scales linearly with the initiative's visible opportunity ceiling relative to this reference value. This parameter must be positive.

- *Attention-to-signal curve parameters.* The shape of the relationship between executive attention and signal clarity — the minimum engagement threshold below which attention actively degrades signal quality, how steeply quality deteriorates in the shallow-attention region, the curvature of diminishing returns above the threshold, the floor on how clear signals can ever become regardless of attention, and the optional ceiling on how much noise shallow attention can introduce. These are the structural assumptions about how executive engagement affects organizational learning.

- *Learning rate.* The base rate at which new evidence moves the organization's strategic quality belief. This governs how responsive beliefs are to incoming signals in general.

- *Dependency learning scale.* An optional parameter controlling how dependency level affects learning efficiency. When not set, the canonical linear form applies (learning efficiency decreases in direct proportion to dependency level).

- *Execution signal parameters.* The noise level for execution progress signals and the learning rate for execution belief updates. These govern how quickly the organization can determine whether an initiative is tracking to plan. These parameters apply only to initiatives with a defined timeline.

- *Portfolio capability parameters.* The maximum organizational capability achievable through enabler completions (the capability ceiling) and the rate at which accumulated capability above baseline erodes over time (the capability decay rate). The capability ceiling is an environmental property — it defines the upper bound on how much organizational learning infrastructure can be built in this simulated world. The decay rate determines how quickly that advantage fades without ongoing replenishment. The capability ceiling must be at least 1.0 (the baseline). The decay rate must be non-negative (zero means no erosion; capability accumulates permanently up to the ceiling).

  The capability ceiling and the per-initiative capability contribution scale (which lives on each initiative's configuration) are distinct concerns that must remain in separate configuration domains. The ceiling governs the state space — how high organizational capability can go. The contribution scale governs how much each individual enabler initiative contributes when it completes. The initiative generator controls the distribution of contribution scales across enabler initiatives; the model configuration controls the space within which those contributions accumulate.

**Governance configuration.** Contains the immutable decision parameters supplied to the governance policy — the thresholds, patience windows, attention bounds, and portfolio controls that define a governance regime's decision rules. These values are read by the policy when making decisions but do not change during a run. Any counters or rolling windows required by these thresholds (such as the consecutive-reviews-below-patience counter or the stagnation belief history) live in engine-owned initiative state, not in hidden governance memory.

The governance configuration includes:

- *Policy identifier.* A label identifying which governance regime is operating.

- *Executive attention budget.* A read-only copy of the budget from the model configuration, provided so the policy can compute feasible attention allocations without needing access to model parameters. The policy cannot change this value.

- *Default initial quality belief.* A read-only copy of the canonical neutral baseline, provided so the policy can evaluate the non-bounded-prize stagnation condition (whether an initiative's belief has risen above the starting point). This ensures the policy references the same value the engine used for initialization.

- *Confidence decline threshold.* The strategic quality belief level below which governance considers continued investment no longer justified. Setting this higher makes governance more willing to cut losses early; setting it lower makes governance more patient. Setting it to null disables this stop path entirely.

- *Bounded-prize patience parameters.* Two values define how the bounded-prize adequacy rule works: the threshold ratio (what fraction of the visible opportunity ceiling the expected prize value must exceed to pass the adequacy test) and the base patience window (how many consecutive below-threshold reviews an initiative earns when its visible ceiling equals the reference value). Patience scales linearly with the size of the visible opportunity — larger prizes earn proportionally more patience.

  The base patience window is a count of reviews, not a monetary value or a continuous quantity. It must be a whole number. This matters because configuration files may silently convert whole numbers to decimal values during loading, which would produce subtle type errors downstream. The implementation must enforce integer type explicitly.

- *Stagnation parameters.* The window length (in staffed weeks, not calendar weeks) over which belief movement is assessed, and the minimum belief change threshold below which an initiative is considered informationally stagnant.

- *Attention allocation bounds.* The minimum and maximum executive attention levels that can be assigned to any single initiative on a given week. These bounds have specific operational meaning:

  The minimum attention level is the lowest nonzero attention that the policy may assign when it chooses to give an initiative explicit attention. It is not an automatic entitlement — an initiative can receive zero attention if the policy simply does not mention it. But if the policy does choose to give positive attention, the amount must be at least this minimum. In the canonical study, this minimum is required to exist and must be positive. This is not optional — the study's attention-to-signal mechanism makes a substantive claim about a harmful shallow-attention region below a minimum threshold, so that threshold must exist.

  The maximum attention level is the highest attention assignable to any single initiative. If not set, the effective maximum is 100% of the executive's time.

  The engine uses the minimum attention level as the fallback when an attention budget violation is detected — rather than dropping affected initiatives to zero attention, which would cause artificial signal collapse.

- *Execution overrun threshold.* The execution belief level below which governance may flag execution concern. When set, a governance regime can stop initiatives whose projected completion time has deteriorated enough, independent of strategic conviction. When null, the policy handles execution overrun logic explicitly rather than through a configured threshold.

- *Portfolio risk controls (optional).* Three optional governance-side controls for portfolio management:

  A low-quality-belief threshold paired with a maximum labor share allows the policy to limit how much of the workforce is deployed on initiatives whose strategic conviction is below a certain level.

  A maximum single-initiative labor share allows the policy to prevent any one initiative from consuming a disproportionate fraction of the workforce.

  These are governance preferences, not engine-enforced constraints. The engine provides the portfolio state needed to compute them, but the policy decides whether and how to honor them.

- *Portfolio mix targets (optional).* Desired labor-share distribution across initiative categories. The policy may use these as soft preferences during team assignment. When not configured, no mix targets apply.

**Reporting configuration.** Defines what outputs the simulation produces — whether to record the run manifest, per-week logs, and the event log, and how to group results by initiative labels. Reporting configuration must not affect simulation mechanics. It governs only what is recorded, not what happens.

**Initiative configuration.** The simulation receives either a fully resolved list of initiatives with all attributes determined, or an initiative generator specification that the runner resolves into such a list before the simulation begins. Exactly one of these must be provided. If a generator is used, the runner must resolve it deterministically using the world seed, so the same seed always produces the same initiative pool.

**Validation requirements.** Before the simulation begins, the configuration must be validated to ensure internal consistency. The required checks include:

- Exactly one initiative source (resolved list or generator) must be provided
- The time horizon must be positive
- At least one team must exist
- Attention parameters must be within valid ranges (the attention threshold between zero and one, the penalty slope non-negative, the reference ceiling positive)
- If both minimum and maximum attention noise modifiers are set, the minimum must not exceed the maximum
- The stagnation window must be at least one staffed week
- The stagnation belief change threshold must be non-negative
- The maximum portfolio capability must be at least the baseline of 1.0
- Capability decay must be non-negative
- The default initial quality belief must lie within the valid belief range (canonically between 0 and 1, with the default at 0.5)
- Attention minimum must be present and positive (required in the canonical study)
- If attention maximum is set, it must be between zero and one, and at least as large as the attention minimum
- The base patience window must be a whole number, not a decimal — configuration file parsers may silently convert "5" to "5.0", and the implementation must detect and correct this
- Execution signal noise must be non-negative
- Execution learning rate must be positive and at most 1.0
- If an initiative specifies a planned duration, it must be positive
- If an initiative specifies a true duration, it must be positive
- If an initiative specifies an initial execution belief, it must be in the range (0, 1]
- If a true duration is set, a planned duration must also be set (the execution evidence channel requires both the hidden truth and the observable plan)
- Capability contribution scale must be non-negative for every initiative where it is set
- If a completion-lump value channel is enabled, the configured payout value must be explicitly present and non-negative. The engine must not silently default to zero when this value is missing — the runner must reject the configuration with an explicit error. An enabled value channel with no configured value is a schema violation, not an edge case to handle gracefully.
- If a residual value channel is enabled, the residual decay rate must be present and non-negative
- If an initiative has a positive capability contribution scale, it must also have a true duration set. Capability updates occur only at the completion transition, so an initiative without a completion condition cannot validly contribute capability.
- If a residual value channel is enabled with a completion-triggered activation, the initiative must have a true duration set. Without a true duration, the engine cannot detect the completion transition that triggers residual activation.

The runner should record the fully resolved configuration — including all defaults applied — in the run manifest so that provenance is complete even when the original configuration relied on default values.

**Canonical warning condition.** If the confidence decline threshold is set at or above the default initial quality belief, the implementation should emit a validation warning. In that configuration, the confidence decline rule may trigger before the non-bounded-prize stagnation path ever has a chance to fire, making that stagnation path unreachable in practice. This may be intentional, but it should not happen silently.

**A constant used internally but not configurable.** The execution belief floor — a small positive value (0.05) used to prevent division by near-zero when computing the implied completion time from execution belief — is defined as a fixed implementation constant, not as a tunable parameter. It caps the implied duration at twenty times the planned duration, which is the practical limit of what "this is taking much longer than planned" can express before the number loses operational meaning.

**Stage 3–5 field additions.** Several fields are documented in the configuration for completeness but are governed by their own design documents:

- A per-initiative staffing response scale controlling how additional staffing above the minimum requirement accelerates learning (default zero, meaning team size above the minimum has no effect on learning speed).
- A prize identifier linking right-tail frontier re-attempts back to their original prize descriptor.
- Per-family frontier state tracking how the opportunity frontier evolves as initiatives are resolved (runner-managed, stored for state completeness but not read or modified by the engine during a tick).
- Available prize descriptors for right-tail initiatives available for re-attempt (runner-owned).

## GovernanceObservation


### Academic
The governance policy must not receive the full world state. It receives a policy-visible observation bundle derived from engine-owned state. This preserves the observation boundary established in the architecture: governance sees observables and belief summaries, never latent ground truth.

Canonical observation structure:

```python
GovernanceObservation = {
  "tick": int,
  "available_team_count": int,
  # Read-only copy of the hard per-tick executive-attention budget. Policies are
  # expected to compute feasible SetExecAttention allocations against this value.
  "exec_attention_budget": float,
  # Read-only copy of the canonical non-TAM stagnation baseline.
  "default_initial_quality_belief": float,
  # Read-only per-policy attention bounds after canonical default resolution.
  "attention_min_effective": float,
  "attention_max_effective": float,
  # Current portfolio learning-capability stock (portfolio_capability_t). In the
  # canonical study, higher capability reduces effective strategic signal noise
  # by dividing effective_signal_st_dev_t.
  "portfolio_capability_level": float,
  # Convenience aggregation of current portfolio state for policy-side portfolio
  # management. These are derived from initiative/team state and do not create a
  # second source of truth.
  "portfolio_summary": PortfolioSummary,
  "initiatives": list[InitiativeObservation],
  "teams": list[TeamObservation],
}
```

```python
PortfolioSummary = {
  # Total active labor currently allocated across staffed initiatives.
  "active_labor_total": int,

  # Labor currently allocated to initiatives whose strategic quality belief is
  # below the policy's low_quality_belief_threshold, if one is configured.
  # None when the policy does not define such a threshold.
  "active_labor_below_quality_threshold": int | None,

  # Active labor share currently allocated to initiatives below the configured
  # low-quality threshold. None when no threshold is configured or when
  # active_labor_total == 0.
  "low_quality_belief_labor_share": float | None,

  # Largest labor share currently allocated to any single active initiative.
  # None when no initiatives are active.
  "max_single_initiative_labor_share": float | None,
}
```

The `PortfolioSummary` block is a convenience surface for governance policies.
It does not alter simulator mechanics and should always be derivable from the
authoritative initiative and team state already exposed in the observation.

Where possible, portfolio exposure should be expressed in labor-share terms
rather than initiative counts. This matches the study's treatment of labor as
the scarce investment unit.

---

Where:

```python
InitiativeObservation = {
  "initiative_id": str,
  "lifecycle_state": str,
  "assigned_team_id": str | None,

  # Strategic quality belief (quality_belief_t; c_t in equations).
  # Governance's posterior mean estimate of latent_quality. This is the
  # strategic belief only. It does not encode execution fidelity.
  "quality_belief_t": float,
  # belief_variance was removed. The stagnation window (Δ_c over staffed ticks)
  # provides the equivalent governance signal implicitly.

  # Observable bounded-prize ceiling, when present.
  # Governance uses this together with the current quality belief to evaluate
  # the prize-relative bounded-prize patience rule. None means the initiative
  # has no bounded-prize channel and therefore does not use that rule.
  "observable_ceiling": float | None,

  # Immutable labor requirement for this initiative. Assignment requires
  # team_size >= required_team_size.
  "required_team_size": int,

  # Derived effective TAM patience window (effective_tam_patience_window) used
  # by the canonical bounded-prize patience rule. For initiatives without
  # observable_ceiling, this is None. Computed as:
  #   max(1, ceil(T_tam * observable_ceiling / reference_ceiling))
  "effective_tam_patience_window": int | None,

  # Execution belief (execution_belief_t; c_exec_t in equations).
  # Governance's posterior belief about schedule fidelity relative to plan.
  # 1.0 means the initiative is believed to be tracking exactly to plan.
  # Values below 1.0 indicate a projected overrun relative to planned_duration_ticks.
  # None when true_duration_ticks is not set on the initiative.
  "execution_belief_t": float | None,
  # belief_exec_variance was removed. The engine maintains only the scalar
  # execution_belief_t; this field was always None and constitutes a silent
  # trap identical to the one corrected for belief_variance in AP-4.

  # Derived observable: implied expected duration in ticks, computed as
  #   round(planned_duration_ticks / max(execution_belief_t, epsilon_exec))
  # where epsilon_exec = 0.05 (module-level constant above).
  # Caps implied duration at 20× planned_duration_ticks.
  # None when planned_duration_ticks or execution_belief_t is not available.
  # This is provided so policy logic and reporting can reason in natural business
  # units rather than the normalized fidelity scalar.
  "implied_duration_ticks": int | None,

  # Observable plan reference (set at generation, visible to governance from the start).
  "planned_duration_ticks": int | None,

  "progress_fraction": float | None,
  # None for initiatives where planned_duration_ticks is not set (unbounded duration).
  # For bounded initiatives, min(staffed_tick_count / planned_duration_ticks, 1.0).
  # Derived at the observation boundary from fields on InitiativeState; not stored separately.
  # Count of completed end-of-tick governance evaluations for this initiative.
  # A review occurs exactly when, at the end of a tick, the initiative is both:
  #   (a) in lifecycle_state == "active", and
  #   (b) currently staffed (assigned_team_id is not None)
  # and is therefore required to receive an explicit ContinueStop decision.
  # review_count increments once per such evaluation and never increments on
  # paused/unassigned/stopped/completed ticks.
  "review_count": int,

  # Count of ticks this initiative has been staffed (assigned a team).
  # Used as the basis for the stagnation window, which counts staffed ticks only.
  "staffed_tick_count": int,

  # Count of consecutive reviews at which the bounded-prize adequacy test failed.
  # Updated by the engine before the end-of-tick policy invocation.
  # Resets to zero on any reviewed tick where the test passes, and also resets to
  # zero whenever the initiative is not reviewed on that tick (for example because
  # it is paused/unassigned/stopped/completed).
  "consecutive_reviews_below_tam_ratio": int,

  # Observable capability contribution scale (set at generation, not latent).
  # Governance's expected portfolio learning-capability yield from this
  # initiative is quality_belief_t * capability_contribution_scale. Realized
  # yield on completion is latent_quality * capability_contribution_scale
  # (latent until completion). 0.0 for initiatives with no enabler role. This
  # mirrors the observable_ceiling / latent_quality pattern used in the
  # discovery channel.
  "capability_contribution_scale": float,

  # Generation-time type tag. Set from InitiativeTypeSpec.generation_tag at
  # pool generation and carried through unchanged. None for hand-crafted
  # initiatives not produced by the generator.
  #
  # This is observable metadata, not latent ground truth. It is derived from
  # the public pool-design parameters that are visible in the environment
  # family definition and the run manifest. It does not reveal latent_quality,
  # true_duration_ticks, or any other hidden engine state.
  #
  # The canonical type-independence invariant (canonical_core.md invariant #1)
  # prohibits the ENGINE from branching on this field. It does not prohibit
  # the policy from reading it for governance-architecture purposes such as
  # portfolio mix targeting. This is the same contract as observable_ceiling
  # and capability_contribution_scale, which are also set at generation and
  # surfaced to the policy.
  #
  # Canonical values: "flywheel", "right_tail", "enabler", "quick_win".
  "generation_tag": str | None,
}
```

```python
TeamObservation = {
  "team_id": str,
  "assigned_initiative_id": str | None,
  "available_next_tick": bool,
}
```

### Business
The governance policy must not receive the full internal state of the simulation. It receives a structured observation snapshot — a policy-visible bundle derived from engine-owned state that contains everything governance is permitted to know and nothing it is not. This preserves the observation boundary that the entire study depends on: governance sees observable attributes and belief summaries, never the hidden ground truth about what initiatives are actually worth or how long they will actually take.

The observation snapshot provided to governance at each decision point contains:

**Current week.** Which week of the simulation is being evaluated.

**Available team count.** How many teams are currently unassigned and available for deployment.

**Executive attention budget.** A read-only copy of the hard weekly limit on total executive attention. Governance policies are expected to compute their proposed attention allocations against this value to avoid budget violations.

**Default initial quality belief.** A read-only copy of the neutral starting point for strategic quality beliefs. Governance needs this value to evaluate the non-bounded-prize stagnation condition — specifically, to determine whether an initiative's belief has risen above where the organization started.

**Effective attention bounds.** The resolved minimum and maximum per-initiative attention levels, after applying canonical defaults. These tell governance the operational range within which any positive attention assignment must fall.

**Portfolio capability level.** The organization's current portfolio-wide learning capability stock. In the canonical study, higher capability reduces the effective noise on strategic signals across the entire portfolio.

**Portfolio summary.** A convenience aggregation of the portfolio's current state, designed to support governance-side portfolio management checks without requiring the policy to re-derive these values from individual initiative observations. The summary includes:

- *Total active labor.* The total workforce currently allocated across staffed initiatives.
- *Labor below quality threshold.* How much labor is currently allocated to initiatives whose strategic quality belief is below the policy's configured low-confidence threshold, if one exists. This is null when the policy does not define such a threshold.
- *Low-quality labor share.* The fraction of active labor allocated to below-threshold initiatives. Null when no threshold is configured or when no initiatives are active.
- *Maximum single-initiative labor share.* The largest fraction of active labor currently consumed by any single initiative. Null when no initiatives are active.

The portfolio summary is a convenience surface. It does not alter simulation mechanics and should always be derivable from the authoritative initiative and team state already exposed in the observation. Where possible, portfolio exposure is expressed in labor-share terms rather than initiative counts, consistent with the study's treatment of labor as the scarce investment unit.

**Per-initiative observations.** For each initiative in the portfolio, governance sees:

- *Identity and status.* The initiative's identifier, its current lifecycle state (unassigned, active, stopped, completed), and which team is currently assigned to it (if any).

- *Strategic quality belief.* The organization's current best estimate of the initiative's true strategic quality. This is the strategic belief only — it does not encode anything about execution progress. This is the single most important number governance uses when making continue/stop decisions.

- *Visible opportunity ceiling.* For bounded-prize initiatives, the observable ceiling on potential value. Governance uses this together with the current quality belief to evaluate the prize-relative patience rule. For initiatives without a bounded-prize channel, this is null, and the bounded-prize patience rule does not apply.

- *Required team size.* The minimum team size needed to staff this initiative. A team can only be assigned if its size meets or exceeds this requirement.

- *Effective patience window.* For bounded-prize initiatives, the computed patience window — how many consecutive below-threshold reviews the initiative earns before the inadequacy trigger fires. This is derived from the base patience window scaled by the initiative's visible opportunity ceiling relative to the reference value. Larger visible opportunities earn proportionally more review patience. For initiatives without a visible ceiling, this is null.

- *Execution belief.* The organization's current estimate of how well the initiative is tracking against its original plan. A value of 1.0 means governance believes the initiative is on schedule; values below 1.0 indicate projected overrun. Null for initiatives without a defined timeline.

- *Implied completion time.* A derived quantity that translates the execution belief into concrete time units — the current best estimate of how many weeks the initiative will actually take to complete, based on the original plan and the current execution belief. This is capped at twenty times the planned duration to prevent meaningless extreme values. Null when either the planned duration or the execution belief is unavailable. This translation exists so that governance can reason in natural terms — "this initiative now looks like it will take three years instead of eighteen months" — rather than working with an abstract ratio.

- *Planned duration.* The initiative's original planned timeline, as stated when the initiative was created. This is observable from the start and does not change.

- *Progress fraction.* How far the initiative has progressed relative to its original plan (not the revised estimate). An initiative that has consumed all its originally planned time shows 100% progress, even if the underlying work is not actually finished. This signals to governance that the initiative has overrun its plan. Null for initiatives without a defined timeline.

- *Review count.* The number of completed end-of-week governance evaluations for this initiative. A review occurs exactly when, at the end of a week, the initiative is both active and currently staffed — and therefore required to receive an explicit continue-or-stop decision. The review count increments once per such evaluation and never increments on weeks when the initiative is paused, unstaffed, stopped, or completed.

- *Staffed week count.* The total number of weeks this initiative has had a team assigned, accumulated across all assignments over its entire lifetime. This is the basis for the stagnation window, which counts staffed weeks only.

- *Consecutive reviews below patience threshold.* How many reviews in a row the initiative's expected bounded-prize value has fallen below the adequacy threshold. Updated by the engine before governance is invoked on each week. Resets to zero when the initiative passes the adequacy test on any review, and also resets to zero whenever the initiative is not reviewed on a given week (because it is unstaffed, stopped, or completed). This counter is the mechanism by which the bounded-prize patience rule tracks whether an initiative has exhausted its patience.

- *Capability contribution scale.* The expected portfolio learning-capability yield from this initiative if it completes. Governance's expected contribution is the current quality belief multiplied by this scale. The realized contribution at completion depends on the true underlying quality (which is hidden until completion) multiplied by this scale — mirroring the pattern used for the bounded-prize channel, where governance reasons about expected value while realized value depends on the hidden truth. This is zero for initiatives with no enabler role.

- *Generation tag.* The initiative type label assigned when the initiative was created from the pool generator — for example, "flywheel," "right_tail," "enabler," or "quick_win." Null for hand-crafted initiatives not produced by the generator.

  This is observable metadata, not hidden ground truth. It is derived from the public pool-design parameters that are visible in the environment definition and the run manifest. It does not reveal the initiative's true quality, its actual duration, or any other hidden engine state.

  An important nuance: the canonical type-independence invariant prohibits the simulation engine from branching on this field — the engine never applies different rules because an initiative is labeled as a flywheel versus a right-tail bet. But the invariant does not prohibit governance from reading this field for governance-architecture purposes such as portfolio mix targeting. Governance may use the generation tag in the same way it uses the visible opportunity ceiling or the capability contribution scale — as an observable characteristic that informs resource allocation decisions. What governance may not do is use the tag as a shortcut to avoid evaluating evidence — "keep all flywheels regardless of what the signals say" violates the spirit of evidence-based governance, while "target a portfolio mix that includes persistent-return initiatives" does not.

**Per-team observations.** For each team in the organization, governance sees the team's identifier, which initiative it is currently assigned to (if any), and whether it will be available for reassignment at the start of the next week.

## Policy API


### Academic
The canonical governance policy is a pure decision function with no internal mutable state
across ticks. All evolving memory lives in engine-owned `WorldState` and is surfaced to the
policy through the observation boundary defined in this document.

```python
class GovernancePolicy(Protocol):
    def decide(
        self,
        observation: GovernanceObservation,
        config: GovernanceConfig,
    ) -> GovernanceActions:
        ...
```

`GovernanceObservation` and `GovernanceConfig` are defined in this document. The policy must
not receive the full `SimulationConfiguration` or `ModelConfig`. Engine-side model parameters
and world-transition thresholds must not leak into policy logic unless a later design
explicitly broadens the governance boundary.

This enforces a strict information-partition constraint: the policy's decision function is measurable with respect to the observation filtration only, not with respect to the latent-state filtration or the transition kernel's parameter space. The policy observes the output of the observation process — belief scalars, derived counters, observable initiative attributes — but has no access to the parameters governing signal generation, belief dynamics, capability accumulation, or value realization. This partition is the mechanism by which the study ensures that governance outcome differences are attributable to policy differences rather than to differential information access.

The canonical action schema — `ContinueStop` decisions with required reason classification, `SetExecAttention` allocations subject to per-initiative bounds and a portfolio budget constraint, and `AssignTeam` actions subject to team-size and availability constraints — is fully specified in `governance.md`.

### Business
The governance policy is a pure decision function with no internal memory that persists across weeks. All evolving knowledge — beliefs about initiative quality, execution progress estimates, review counters, patience trackers — lives in engine-owned state and is surfaced to the policy through the observation boundary defined in this document.

The formal interface is:

- **Input:** The observation snapshot of the portfolio's current observable state (as defined above), plus the immutable governance configuration that defines the regime's decision rules.
- **Output:** A complete action vector specifying continue/stop decisions for every active staffed initiative, team assignments, and executive attention allocations.

The policy must not receive the full simulation configuration or the model parameters that govern how the world evolves. Engine-side parameters — how signals are generated, how beliefs update, how capability decays — must not leak into governance logic unless a future design explicitly broadens the governance boundary. This is the same principle that applies in a real organization: the governance function decides what to do based on what it can observe, not based on knowledge of the underlying mechanics that generate the evidence it observes.

The canonical action schema and the detailed semantics of each governance decision type — continue/stop with required reason codes, attention allocation with budget constraints, team assignment with size requirements — are defined in the governance specification.

## Runner responsibilities


### Academic
The runner is responsible for orchestration and reproducibility. Its responsibilities are:

- resolve `initiative_generator` into a deterministic `initiatives` list if provided
- seed all random number generators using `world_seed`
- construct the resolved run input passed to the engine
- run the same resolved initiative pool across governance regimes when performing comparative experiments
- record the run manifest and per-tick logs when configured to do so
- accept a list of `SimulationConfiguration` objects and return a corresponding list
  of `RunResult` objects for batch execution. Each configuration is independently
  seeded and produces an independent result. The runner must not share mutable state
  across configurations in a batch. This interface is required for parameter sweep
  experiments and for parallel execution across multiple worker processes.
- treat `world_seed` as the canonical world identifier for comparative
  experiments. Under the current architecture, once `world_seed` and the resolved
  configuration are fixed, the run is deterministic because initiative pools and
  per-initiative random streams are already fixed.
- therefore, repeated executions with the same `world_seed` and the same resolved
  configuration are exact replays, not new independent samples. They may be used
  for debugging and determinism checks, but they must not be counted as additional
  statistical replications in experimental analysis.
- if a future extension introduces an additional source of run-level randomness
  beyond `world_seed`, that extension must:
  1. define the extra seed explicitly in the configuration or manifest,
  2. document what stochastic mechanism it governs, and
  3. ensure that comparative experiments preserve common-random-numbers
     comparability across governance regimes.

The canonical study does **not** currently assume any such additional run-level
randomness beyond `world_seed`.

The runner is not allowed to change model semantics between policy runs in a comparative experiment.

Varying transition-model parameters (`ModelConfig`) across governance regimes within a single experimental comparison would confound governance effects with environment effects and invalidate the CRN identification strategy. Only the policy function and its configuration parameters (`GovernanceConfig`) may differ across regimes sharing a common `world_seed`. The environmental conditions and organizational architecture must remain constant across the comparison set, so that outcome differences can be attributed to the policy mapping from observations to actions, not to differences in the stochastic process generating those observations.

### Business
The runner is the orchestration layer that sits between the configuration and the simulation engine. It is responsible for setting up, executing, and recording simulation runs in a way that ensures reproducibility and supports the study's comparative method.

The runner's specific responsibilities are:

- **Resolve initiative generators.** If the configuration specifies an initiative generator rather than a pre-built list, the runner must resolve that generator into a deterministic, fully materialized list of initiatives before the simulation begins, using the world seed. The engine always receives a resolved list — it never draws from distributions or generates initiatives during a run.

- **Seed all randomness.** Every source of uncertainty in the simulation is seeded using the world seed. The runner constructs all random number generators before the simulation starts, ensuring full reproducibility.

- **Construct the resolved run input.** The runner assembles the complete, validated input that the engine will consume — all configuration resolved, all initiatives materialized, all random streams created.

- **Preserve common random numbers across regimes.** When performing comparative experiments, the runner must ensure that the same resolved initiative pool is used across governance regimes. This is what makes the controlled comparison possible: every regime faces the same simulated world.

- **Record provenance.** When configured to do so, the runner records the run manifest (the complete provenance artifact for exact replay) and per-week logs (the detailed state evolution for analysis).

- **Support batch execution.** The runner must accept a list of simulation configurations and return a corresponding list of run results. Each configuration is independently seeded and produces an independent result. The runner must not share mutable state across configurations in a batch — each run is fully isolated. This interface is required for parameter sweep experiments and for distributing runs across multiple worker processes.

- **Treat the world seed as the canonical world identifier.** In comparative experiments, the world seed is what defines "the same simulated world." Once the world seed and the resolved configuration are fixed, the run is fully deterministic — initiative pools and per-initiative random streams are already determined. Repeated executions with the same world seed and configuration are exact replays, not new independent samples. They may be useful for debugging and verifying determinism, but they must not be counted as additional statistical replications in experimental analysis.

- **Handle any future sources of randomness explicitly.** The canonical study does not currently assume any source of run-level randomness beyond the world seed. If a future extension introduces one — for example, randomized governance timing or stochastic environmental shocks — that extension must define the extra seed explicitly in the configuration, document what stochastic mechanism it governs, and ensure that the common-random-numbers comparability across governance regimes is preserved. Ad hoc randomness that is not seeded and documented would destroy the study's ability to attribute outcome differences to governance decisions.

The runner is not allowed to change model semantics between policy runs in a comparative experiment. The physics of the simulated world must remain constant — only the governance regime varies. If the runner altered how signals are generated or how beliefs update between runs, the comparison would be confounded and the findings meaningless.

## Implementation sequencing note


### Academic
The batch interface above should be implemented after the single-regime runner is
validated. The single-regime runner is the foundation; the batch interface is a
harness around it. An implementation that attempts to build both simultaneously
will be harder to debug. The parallel execution layer — distributing batch runs
across worker processes — should be added last, after the sequential batch
interface produces correct results.

This layered validation strategy ensures that each component can be verified independently before the next stratum of complexity is introduced. When a failure occurs in the batch or parallel layer, diagnosing whether the root cause lies in the core simulation logic or in the orchestration and distribution machinery requires that the core logic has already been validated in isolation.

### Business
The batch execution interface — running multiple configurations through the simulation — should be implemented only after the single-regime runner has been validated and produces correct results. The single-regime runner is the foundation; the batch interface is a harness around it. Attempting to build both simultaneously creates a debugging problem: when something goes wrong, it becomes difficult to determine whether the issue is in the core simulation logic or in the batching and parallelization layer.

The parallel execution layer — distributing batch runs across multiple worker processes to reduce wall-clock time — should be added last, after the sequential batch interface produces correct results. This layered approach ensures that each component can be validated independently before the next layer of complexity is added on top.

## Run manifest


### Academic
Each run must emit a manifest sufficient for exact replay.

Canonical manifest fields:

```python
RunManifest = {
  "policy_id": str,
  "world_seed": int,
  "is_replay": bool,   # True iff this run repeats an already executed world_seed + resolved_configuration pair
  "resolved_configuration": SimulationConfiguration,
  "resolved_initiatives": list[ResolvedInitiativeConfig],
  "engine_version": str,
}
```

This manifest is the canonical provenance artifact for the study.

Any reported finding that cannot be traced back to a complete manifest — including the resolved configuration, the realized initiative pool, and the engine version — is an unreproducible and therefore unverifiable claim. The manifest is not optional documentation; it is the foundation of the study's reproducibility guarantee and a prerequisite for any comparative analysis across governance regimes.

### Business
Each simulation run must produce a manifest that contains everything needed to reproduce the run exactly. This is the canonical provenance artifact for the study — the record that makes it possible to trace any finding back to the precise configuration, initiative pool, and engine version that produced it.

The manifest includes:

- **Policy identifier.** Which governance regime was operating during this run.

- **World seed.** The seed that determined the simulated world — the initiative pool, the random streams, and every source of stochasticity.

- **Replay flag.** Whether this run is a repeat of an already-executed world seed and configuration pair. This matters for experimental analysis: replays are determinism checks, not additional statistical samples.

- **Resolved configuration.** The complete simulation configuration as consumed by the engine, with all defaults applied and all generators resolved. This is the single authoritative record of what parameters governed the run.

- **Resolved initiatives.** The full list of initiatives with all attributes determined — the concrete pool that the governance regime operated on.

- **Engine version.** Which version of the simulation engine produced the results. This enables traceability if the engine is updated and past results need to be verified against a specific implementation.

This manifest is not optional documentation — it is the foundation of the study's reproducibility guarantee. Any finding that cannot be traced back to a complete manifest is an unverifiable claim.
