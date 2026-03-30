# Primordial Soup glossary (Academic + Business)

This glossary defines key terms used across the Primordial Soup design corpus. It is intentionally **mechanics-grounded**: each term includes code/schema names, observation-boundary status, and citations into the authoritative technical documents.

## latent_quality (q)
### Academic
- **Code/schema name(s)**: `latent_quality` (design/prose), \(q\) (equations)
- **Observation status**: **Latent**. Engine can use for ground-truth computations (signal centers, completion-time outcomes, realized value, capability gains). Governance never sees it; it only sees beliefs and derived observables.
- **Citations**: `docs/design/initiative_model.md` — “Immutable attributes (set at generation)” (`latent_quality ∈ [0,1]`); `docs/design/interfaces.md` — “InitiativeObservation” (governance sees `quality_belief_t`, not latent quality); `docs/design/governance.md` — “Policy inputs (what the policy may see)” (policy must not see latent quality).
### Business
The initiative’s true strategic merit—fixed at creation and unknowable to leadership during the run. Leadership must infer it from noisy evidence, and governance decisions are evaluated against outcomes driven by this hidden truth.

## quality_belief_t (c_t)
### Academic
- **Code/schema name(s)**: `quality_belief_t`, \(c_t\)
- **Observation status**: **Observable to governance** (in `InitiativeObservation`). Engine-owned state; policy reads it but does not own or mutate it.
- **Citations**: `docs/design/core_simulator.md` — “Belief update” (strategic belief update equation); `docs/design/interfaces.md` — “InitiativeObservation” (`quality_belief_t`); `docs/design/governance.md` — “Stop / Continue criteria (canonical)” (confidence decline, prize adequacy, stagnation depend on it).
### Business
Leadership’s current best estimate of an initiative’s strategic promise. It is the primary input to stop/continue decisions and to expected-value reasoning for bounded opportunities.

## base_signal_st_dev (σ_base)
### Academic
- **Code/schema name(s)**: `sigma_base`, “base signal st_dev”, `base_signal_st_dev_default` (default in `ModelConfig`), \(σ_\text{base}\)
- **Observation status**: **Engine-visible parameter** (initiative immutable attribute; also has a model default). Not surfaced to governance in `GovernanceObservation`.
- **Citations**: `docs/design/initiative_model.md` — “Immutable attributes” (`sigma_base`); `docs/design/core_simulator.md` — “Effective noise `σ_eff(d,a,C_t)` and attention shape `g(a)`” (role in \(σ_\text{eff}\)); `docs/design/interfaces.md` — “SimulationConfiguration → ModelConfig” (`base_signal_st_dev_default`).
### Business
How inherently hard it is to read strategic signals for this initiative even before considering dependencies, attention, or organizational capability.

## dependency_level (d)
### Academic
- **Code/schema name(s)**: `dependency_level` / `dependency_d` (initiative attribute), \(d\)
- **Observation status**: **Engine-visible parameter** (immutable initiative attribute). Not surfaced to governance via `InitiativeObservation` in the canonical interface.
- **Citations**: `docs/design/initiative_model.md` — “Immutable attributes” (`dependency_d ∈ [0,1]`); `docs/design/core_simulator.md` — “Learning efficiency `L(d)`” and “Effective noise `σ_eff(d,a,C_t)`…” (enters both learning and noise).
### Business
How much the initiative’s outcomes depend on exogenous factors outside the team’s control, making it harder to learn what the initiative is “really worth.”

## executive_attention_t (a)
### Academic
- **Code/schema name(s)**: `executive_attention_t`, `exec_attention_a_t` (per-tick log), `SetExecAttention.attention`, \(a\)
- **Observation status**: **Chosen by governance** each tick (action), applied by engine, and recorded for reporting. Governance can of course see what it chose; the policy does not rely on hidden persistent attention state (omission means 0).
- **Citations**: `docs/design/governance.md` — “SetExecAttention” (omission-means-zero, bounds, budget); `docs/design/core_simulator.md` — “Production & observation” (attention modulates strategic signal noise, not execution); `docs/design/review_and_reporting.md` — “Primary outputs… PerInitiativeTickRecord” (`exec_attention_a_t`).
### Business
The governance-controlled allocation of scarce executive time. It shapes how noisy strategic evidence is, so attention is an input to the information process—not just a cost.

## attention_noise_modifier g(a)
### Academic
- **Code/schema name(s)**: `g(a)`; `attention_noise_threshold` (\(a_\min\)), `low_attention_penalty_slope` (\(k_\text{low}\)), `attention_curve_exponent` (\(k\)), `min_attention_noise_modifier` (\(g_\min\)), `max_attention_noise_modifier` (\(g_\max\))
- **Observation status**: **Engine-visible model parameters** (in `ModelConfig`). Not directly surfaced to governance via `GovernanceObservation`.
- **Citations**: `docs/design/core_simulator.md` — “Effective noise `σ_eff(d,a,C_t)` and attention shape `g(a)`” (definition + behavioral properties); `docs/design/interfaces.md` — “SimulationConfiguration → ModelConfig” (parameter names).
### Business
The model’s mapping from “how much leadership is truly engaged” to “how clear the strategic signal becomes.” Shallow attention below a minimum threshold is modeled as actively harmful; above it, more attention helps with diminishing returns.

## effective_signal_st_dev_t (σ_eff)
### Academic
- **Code/schema name(s)**: `effective_signal_st_dev_t`, `effective_sigma_t` (per-tick log), \(σ_\text{eff}\)
- **Observation status**: **Engine-derived** per staffed initiative per tick (function of `sigma_base`, dependency, attention, and capability). Exposed for reporting/audit in per-tick logs; not a governance observation field in the canonical `InitiativeObservation`.
- **Citations**: `docs/design/core_simulator.md` — “Effective noise `σ_eff(d,a,C_t)`…” (definition); `docs/design/review_and_reporting.md` — “PerInitiativeTickRecord” (`effective_sigma_t`).
### Business
The “actual noise level this week” for an initiative’s strategic evidence after accounting for dependencies, attention, and organizational capability.

## execution_belief_t (c_exec_t)
### Academic
- **Code/schema name(s)**: `execution_belief_t`, \(c_{\text{exec},t}\)
- **Observation status**: **Observable to governance** when the initiative has duration fields; otherwise `None`. Engine-owned state.
- **Citations**: `docs/design/core_simulator.md` — “Belief update → Execution belief update”; `docs/design/interfaces.md` — “InitiativeObservation” (`execution_belief_t`, `implied_duration_ticks`); `docs/design/governance.md` — “Execution belief and cost tolerance”.
### Business
Leadership’s current estimate of schedule fidelity relative to plan. It supports cost-sensitive governance that may stop initiatives for overruns independent of strategic conviction.

## true_duration_ticks and latent_execution_fidelity (q_exec)
### Academic
- **Code/schema name(s)**: `true_duration_ticks` (latent), `planned_duration_ticks` (observable), `q_exec` (latent derived), `execution_signal_st_dev` (\(σ_\text{exec}\))
- **Observation status**: `true_duration_ticks` is **latent** (engine-only). `planned_duration_ticks` is **observable to governance**. `q_exec` is **latent derived** and never shown to governance.
- **Citations**: `docs/design/core_simulator.md` — “Production & observation → Execution progress signal” (defines \(q_\text{exec}\)); `docs/design/initiative_model.md` — “Immutable attributes” (`true_duration_ticks`, `planned_duration_ticks`); `docs/design/governance.md` — “Policy inputs…” (policy must not see `true_duration_ticks`).
### Business
The “actual time it really takes” (hidden) versus “what we planned” (visible). The ratio is the hidden execution fidelity that the organization gradually learns about via execution signals.

## implied_duration_ticks
### Academic
- **Code/schema name(s)**: `implied_duration_ticks`, `epsilon_exec` (fixed floor used in computation)
- **Observation status**: **Observable to governance** (derived). Computed from `planned_duration_ticks` and `execution_belief_t`; capped via `epsilon_exec`.
- **Citations**: `docs/design/interfaces.md` — “InitiativeObservation” (`implied_duration_ticks`, `epsilon_exec`); `docs/design/governance.md` — “Execution belief and cost tolerance” (purpose: business units).
### Business
The execution belief translated into “how many weeks we now expect this will take,” so policies can reason in calendar terms rather than a ratio.

## portfolio_capability (C_t)
### Academic
- **Code/schema name(s)**: `portfolio_capability` / `portfolio_capability_level`, `capability_C_t` (portfolio tick log), \(C_t\), `max_portfolio_capability` (\(C_\max\))
- **Observation status**: **Observable to governance** (in `GovernanceObservation`). Engine-owned shared state. Mechanically affects only strategic signal noise by dividing \(σ_\text{eff}\).
- **Citations**: `docs/design/core_simulator.md` — “Portfolio capability and strategic signal noise”; `docs/design/interfaces.md` — “GovernanceObservation” (`portfolio_capability_level`); `docs/design/state_definition_and_markov_property.md` — “Portfolio-level state” (`portfolio_capability`); `docs/design/review_and_reporting.md` — “Primary outputs” (`terminal_capability_t`, `max_portfolio_capability_t`).
### Business
A portfolio-wide “learning infrastructure” stock built by completing enablers. Higher capability makes strategic evidence cleaner across all active work, improving decision quality.

## capability_contribution_scale
### Academic
- **Code/schema name(s)**: `capability_contribution_scale`
- **Observation status**: **Observable to governance** (initiative attribute). Realized completion-time gain depends on latent quality and is therefore not known ex ante.
- **Citations**: `docs/design/initiative_model.md` — “Immutable attributes” (`capability_contribution_scale` and completion eligibility); `docs/design/core_simulator.md` — “Completion detection and capability update” (ΔC formula); `docs/design/interfaces.md` — “InitiativeObservation” (governance-facing expected yield).
### Business
How much completing this initiative would improve the organization’s ability to evaluate future work, if it turns out to be high-quality and is carried through to completion.

## observable_ceiling
### Academic
- **Code/schema name(s)**: `observable_ceiling`, `reference_ceiling`, `tam_threshold_ratio` (\(θ_\text{tam\_ratio}\))
- **Observation status**: **Observable to governance** (initiative attribute). Used to compute expected prize value and patience scaling. Not latent.
- **Citations**: `docs/design/initiative_model.md` — “Immutable attributes” (`observable_ceiling` and effective patience window formula); `docs/design/interfaces.md` — “InitiativeObservation” (`observable_ceiling`, `effective_tam_patience_window`); `docs/design/governance.md` — “Prize adequacy (bounded-prize patience condition)”.
### Business
The visible upside ceiling for bounded opportunities (e.g., TAM). It doesn’t tell you whether you’ll win—only how big the prize could be if you do.

## base_tam_patience_window / effective_tam_patience_window / reference_ceiling
### Academic
- **Code/schema name(s)**: `base_tam_patience_window` (\(T_\text{tam}\)), `effective_tam_patience_window`, `reference_ceiling`
- **Observation status**: `base_tam_patience_window` and `reference_ceiling` are **configuration parameters** (engine uses for derived fields; governance reads). `effective_tam_patience_window` is **observable to governance** (derived per initiative when `observable_ceiling` is present).
- **Citations**: `docs/design/governance.md` — “Prize adequacy (bounded-prize patience condition)” (definition and scaling); `docs/design/interfaces.md` — “InitiativeObservation” (`effective_tam_patience_window`) and “SimulationConfiguration → ModelConfig/GovernanceConfig” (`reference_ceiling`, `base_tam_patience_window`).
### Business
The rule that “bigger visible opportunities earn more patience.” A base number of consecutive below-threshold reviews is scaled up or down based on the prize’s visible ceiling.

## consecutive_reviews_below_tam_ratio
### Academic
- **Code/schema name(s)**: `consecutive_reviews_below_tam_ratio`
- **Observation status**: **Observable to governance** (engine-maintained counter). Updated by engine before governance decides on that tick; resets to 0 on any non-review tick.
- **Citations**: `docs/design/core_simulator.md` — “Review-state update (before governance invocation)” (update rule); `docs/design/governance.md` — “Review semantics (canonical)” (reset behavior); `docs/design/interfaces.md` — “InitiativeObservation” (field definition).
### Business
How many reviews in a row the initiative’s expected bounded-prize value has been below the adequacy threshold. It encodes “patience strikes” and resets if you stop reviewing or the initiative rebounds.

## stagnation (belief_history, W_stag, ε_stag)
### Academic
- **Code/schema name(s)**: `belief_history`, `stagnation_window_staffed_ticks` (\(W_\text{stag}\)), `stagnation_belief_change_threshold` (\(ε_\text{stag}\))
- **Observation status**: **Engine-maintained state**. Governance sees the ingredients it needs (e.g., `staffed_tick_count`, `quality_belief_t`, and—depending on interface—may not see `belief_history` directly; the engine still uses it for canonical detection/flags/policy logic).
- **Citations**: `docs/design/core_simulator.md` — “Additional implementation notes” (deque/ring-buffer definition and staffed-tick semantics); `docs/design/governance.md` — “Stagnation rule (informational stasis plus failure to earn continued patience)” (definition); `docs/design/interfaces.md` — “SimulationConfiguration → GovernanceConfig” (parameters); `docs/design/state_definition_and_markov_property.md` — “Per-initiative state” (`belief_history`).
### Business
A stop signal for “we’re not learning anything new anymore.” The model measures net belief movement over a window of **staffed** time (not calendar time) and only stops when stasis coincides with failure to earn patience under the appropriate rule.

## generation_tag
### Academic
- **Code/schema name(s)**: `generation_tag`
- **Observation status**: **Observable metadata**. Policy may read it for portfolio-mix targeting; engine must not branch on it.
- **Citations**: `docs/design/interfaces.md` — “InitiativeObservation” (`generation_tag`, and the type-independence note); `docs/design/initiative_model.md` — “Immutable attributes” (`generation_tag`); `docs/design/index.md` — “Invariants (non-negotiables)” (type-independence).
### Business
The human-facing initiative family label (flywheel/right-tail/enabler/quick-win). Useful for reporting and portfolio guardrails, but the engine treats all initiatives identically based on their resolved attributes.

## portfolio_mix_targets
### Academic
- **Code/schema name(s)**: `portfolio_mix_targets` (in `GovernanceConfig`)
- **Observation status**: **Governance-configured guardrail**, readable by policy; not engine-enforced.
- **Citations**: `docs/design/interfaces.md` — “GovernanceConfig” (`portfolio_mix_targets` and “optional” policy-side nature); `docs/design/governance.md` — “Governance architecture vs. operating policy” and “Selection and portfolio management semantics”.
### Business
Soft portfolio composition goals (e.g., target labor share by initiative family). The engine doesn’t enforce them; the governance regime chooses whether and how to honor them.

## world_seed
### Academic
- **Code/schema name(s)**: `world_seed`
- **Observation status**: **Runner/manifest provenance**; not part of governance observation. It identifies the world used for CRN comparisons and deterministically seeds all randomness.
- **Citations**: `docs/design/interfaces.md` — “SimulationConfiguration” (`world_seed`) and “Runner responsibilities”; `docs/design/core_simulator.md` — “Deterministic behavior & reproducibility” (CRN requirement); `docs/design/review_and_reporting.md` — “Manifest & provenance” (`world_seed`).
### Business
The run’s world identifier. Using the same seed produces an exact replay; using paired seeds across regimes ensures a controlled comparison.

## CRN / per-initiative RNG streams
### Academic
- **Code/schema name(s)**: CRN (common random numbers); `quality_signal_rng`, `exec_signal_rng` (per initiative); frontier RNG streams by family (dynamic frontier)
- **Observation status**: **Hidden from governance**. Engine consumes draws; runner constructs streams; governance sees only the resulting observations/beliefs.
- **Citations**: `docs/design/core_simulator.md` — “Deterministic behavior & reproducibility” (two per-initiative streams, no global RNG); `docs/design/state_definition_and_markov_property.md` — “RNG streams as hidden state”; `docs/design/dynamic_opportunity_frontier.md` — “Deterministic seeding and paired-seed comparability” (per-family frontier streams).
### Business
The comparability trick that makes regime differences interpretable: each initiative has its own dedicated random streams so that stopping one initiative in one regime doesn’t “shuffle the dice” for every other initiative.

## dynamic opportunity frontier
### Academic
- **Code/schema name(s)**: dynamic frontier; `frontier_state_by_family`, `available_prize_descriptors`
- **Observation status**: **Environment/runner-owned** and not visible to governance. Stored in world state for Markov completeness; engine does not generate initiatives.
- **Citations**: `docs/design/dynamic_opportunity_frontier.md` — “Governing design principles” and “Complete per-tick cycle”; `docs/design/interfaces.md` — “Stage 3–5 field additions” (frontier state fields are runner-managed and not read by engine).
### Business
A mechanism that prevents “running out of initiatives” as an artifact. As the organization resolves more opportunities, new ones appear, typically with degrading average quality—except for right-tail, where prizes can be re-attempted.

## FamilyFrontierState
### Academic
- **Code/schema name(s)**: `FamilyFrontierState` (`n_resolved`, `n_frontier_draws`, `effective_alpha_multiplier`)
- **Observation status**: **Runner/world-state** (environment-side). Not exposed to governance.
- **Citations**: `docs/design/dynamic_opportunity_frontier.md` — “State variables added to Markov state” (FamilyFrontierState); `docs/design/review_and_reporting.md` — “Primary outputs” (`frontier_summary`).
### Business
The compact tracking record for how depleted each family’s opportunity frontier is and where its frontier random stream sits for reproducibility.

## PrizeDescriptor (right-tail frontier)
### Academic
- **Code/schema name(s)**: `PrizeDescriptor` (`prize_id`, `observable_ceiling`, `attempt_count`); `ResolvedInitiativeConfig.prize_id`
- **Observation status**: **Runner/world-state** (environment-side). Not visible to governance; governs which right-tail prizes are available for re-attempt.
- **Citations**: `docs/design/dynamic_opportunity_frontier.md` — “PrizeDescriptor” and “Prize lifecycle”; `docs/design/state_definition_and_markov_property.md` — “Dynamic frontier state (Stage 3) → Right-tail prize descriptor state”.
### Business
A record of a persistent right-tail “prize” (market opportunity ceiling) that can be retried after failed attempts, tracking how many attempts have been made.

## major_win_event / is_major_win / MajorWinEvent
### Academic
- **Code/schema name(s)**: `value_channels.major_win_event.enabled`, `value_channels.major_win_event.is_major_win` (hidden), `MajorWinEvent`
- **Observation status**: `is_major_win` is **latent** (generator-assigned, hidden until completion). `MajorWinEvent` is an **engine-emitted output event** at completion (post-hoc evidence), not a governance-visible state during the run.
- **Citations**: `docs/design/core_simulator.md` — “Completion detection…” (completion-time event + threshold rule `is_major_win = (q >= q_major_win_threshold)`); `docs/design/initiative_model.md` — “Immutable attributes → value_channels → major_win_event” and “Major-win event state”; `docs/design/review_and_reporting.md` — “Event schemas → MajorWinEvent”.
### Business
Some right-tail initiatives, if carried through to completion, turn out to be transformational. That fact is hidden until completion, where the simulator emits a rich discovery record for analysis without pricing the downstream economics inside the run.

## residual (residual_rate, residual_decay, activation-at-completion)
### Academic
- **Code/schema name(s)**: `value_channels.residual.*`, `residual_activated`, `residual_activation_tick`, `residual_rate`, `residual_decay`, `cumulative_residual_value_realized`
- **Observation status**: Residual configuration is **initiative parameter** (engine-visible). Activation and realized residual value are **engine state/outputs**. Residual persists independent of staffing and attention after activation.
- **Citations**: `docs/design/core_simulator.md` — “Residual value” (decay law, timing, activation on completion); `docs/design/initiative_model.md` — “value_channels → residual” and “Residual activation semantics”; `docs/design/review_and_reporting.md` — “Primary outputs” (residual value breakdown, terminal residual rate).
### Business
The ongoing value stream left behind by completed mechanisms (flywheels/platforms/etc.). It starts at the configured rate on the activation tick, then decays over calendar time, and continues even after the team has moved on.
