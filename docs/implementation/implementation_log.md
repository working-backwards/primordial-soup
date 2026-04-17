# Implementation log

Running engineering log for the Primordial Soup implementation.

---

## 2026-03-25 — Design corpus update for calibration revision (D1–D4)

### What was done

Updated 13 design-corpus documents to reflect four design decisions from
the calibration model revision (see
`docs/implementation/calibration_model_revision_carryover.md`
§"Resolved design decisions"):

- **D1 — Buffered frontier replenishment.** `replenishment_threshold=2`,
  `target_buffer=4`, uniform across families. Resolves two specification
  gaps in `dynamic_opportunity_frontier.md`. Materialization never
  triggered by assignment.
- **D2 — Baseline work.** Teams not assigned to portfolio initiatives
  produce baseline value at 0.1/tick. No signals, no capability. Runner-
  side accounting; engine unchanged. "Idle" renamed to "on baseline."
- **D3 — Intake signal.** Informative initial quality belief drawn as
  `clamp(q + Normal(0, sigma), 0.05, 0.95)`. Per-family sigma: QW=0.10,
  FW=0.15, EN=0.15, RT=0.25. Semantic contract: intake screening, not
  posterior.
- **D4 — Observable frontier thinning.** Planned duration grows for
  flywheel/quick-win. Capability scale upper bound shrinks for enabler.
  Right-tail unchanged (prize-preserving).

### Documents changed

1. `dynamic_opportunity_frontier.md` — D1 (trigger/buffer), D4 (thinning
   tables, right-tail note, enabler thinning). Both perspectives.
2. `interfaces.md` — D1 (FrontierSpec fields), D2 (baseline_value_per_tick,
   teams_on_baseline), D3 (intake semantics), D4 (thinning fields). Both.
3. `initiative_model.md` — D2 (baseline is not an initiative), D3 (intake
   signal semantics for initial_belief_c0). Both.
4. `governance.md` — D2 (baseline as legitimate choice), D3 (informative
   ranking at t=0). Both.
5. `sourcing_and_generation.md` — D1 (threshold+buffer), D3 (generator
   intake formula), D4 (observable thinning). Both.
6. `core_simulator.md` — D2 (baseline is runner-side). Both.
7. `review_and_reporting.md` — D2 (baseline metrics, idle→baseline). Both.
8. `calibration_note.md` — D3 (intake noise table), D4 (thinning rates
   table). Both.
9. `glossary.md` — D2 (baseline work), D3 (intake signal).
10. `state_definition_and_markov_property.md` — D1 (threshold+buffer),
    D2 (cumulative_baseline_value).
11. `study_overview.md` — D2 (idle→baseline), D3 (intake priors).
12. `design_decisions.md` — D1–D4 recorded with rationale.
13. `implementation_log.md` — this entry.

### What did NOT change

- `canonical_core.md` — architectural invariants preserved.
- Engine code (`tick.py`, `learning.py`) — no engine changes.
- No backward-compat shims. Version control handles history.

---

## 2026-03-10 — Repo assessment and initial scaffolding

### What was done

1. Read all 16 required design corpus documents.
2. Assessed the repo: design docs complete and frozen, no source code,
   no project config, one stale legacy engineering spec.
3. Created repo plumbing:
   - `pyproject.toml` — Python 3.12+, numpy, dev deps (pytest, ruff,
     mypy, pre-commit), ruff config (E/F/I/UP/B/SIM/TCH, line 99),
     mypy strict mode, pytest config.
   - `.pre-commit-config.yaml` — ruff lint+format, yaml check,
     whitespace, large file check.
   - `src/primordial_soup/__init__.py` — package with docstring.
   - `tests/__init__.py` and `tests/conftest.py` — test scaffolding.
4. Updated `CLAUDE.md` with project purpose, authority structure,
   design freeze rule, implementation invariants, ambiguity handling
   protocol, persistent state locations, and updated architecture
   rules to match the current design corpus.
5. Created `docs/implementation/claude_plan.md` — full implementation
   plan with module structure, phases, invariants, RNG strategy,
   boundary diagram, testing strategy, SimOpt compatibility notes.
6. Created `docs/implementation/implementation_log.md` (this file).
7. Created `docs/implementation/open_implementation_issues.md`.
8. Moved `docs/engineering.md` to `docs/deprecated/` — it predates
   the current four-type design and would mislead implementers.
9. Updated `.gitignore` to include output directories.

### What changed

- `CLAUDE.md` rewritten: added ~80 lines of project context and
  invariants before existing coding rules; updated architecture rules
  to use current design terminology (`GovernanceObservation`,
  `InitiativeObservation`) instead of legacy names.
- `docs/engineering.md` moved to `docs/deprecated/engineering.md`.

### Why

The repo had a complete design corpus but no implementation
infrastructure. A competent engineer could not begin building without
first creating project configuration, understanding which engineering
spec was current, and establishing where to store implementation state.

### What remains

- Phase 1: domain types and configuration
- Phase 2: RNG and initiative pool
- Phase 3+: learning model, tick engine, governance, policy, reporting,
  runner

### Notable decisions

- **src layout** chosen over flat layout for cleaner import isolation
  and standard packaging practice.
- **numpy** included as a dependency for distribution sampling per
  CLAUDE.md allowance and design corpus guidance on pool.py / noise.py.
- **`docs/engineering.md` deprecated** — it was based on a two-type
  (flywheel/right-tail) model with streaming value, pivots, review
  cadence, and other concepts removed in the current design.

---

## 2026-03-10 — Design patches and question resolution

### What was done

1. Resolved three implementation questions with project owner.
2. Patched `docs/design/architecture.md`: changed RNG seed derivation
   from 32-bit to 64-bit (first 8 bytes of SHA-256 digest). Added RNG
   abstraction requirement for future SimOpt stream-based migration.
3. Patched `docs/design/initiative_model.md`: added explicit
   `required_team_size` default of 1 with documentation.
4. Updated `docs/implementation/open_implementation_issues.md`: closed
   issues 1, 2, 3.
5. Updated `docs/implementation/claude_plan.md`: revised RNG strategy,
   generator schema approach (flexible with canonical defaults), and
   risks section.

### Why

The 32-bit seed width was not a deliberate design choice and introduced
unnecessary collision risk. SimOpt compatibility requires stream-based
RNG (MRG32k3a), not 32-bit hash truncation — the implementation should
keep RNG derivation abstract enough for future migration.

`required_team_size` was referenced in the initiative model and team
model but never given a canonical default. Defaulting to 1 matches the
study scope (not about multi-team staffing).

The generator schema should be flexible with canonical defaults rather
than hardcoded, to support future experiment configuration.

---

## 2026-03-10 — Phase 1: domain types and configuration

### What was done

1. Implemented all Phase 1 source modules:
   - `types.py` — LifecycleState, RampShape, TriggeringRule,
     StopContinueDecision, ReassignmentTrigger enums; BetaDistribution,
     UniformDistribution, LogNormalDistribution specs; CompletionLumpChannel,
     ResidualChannel, MajorWinEventChannel, ValueChannels dataclasses;
     EPSILON_EXEC, RAMP_EXPONENTIAL_K constants.
   - `config.py` — TimeConfig, WorkforceConfig, ModelConfig,
     GovernanceConfig, ReportingConfig, ResolvedInitiativeConfig,
     InitiativeTypeSpec, InitiativeGeneratorConfig,
     SimulationConfiguration; validate_configuration with all
     interfaces.md rules.
   - `state.py` — InitiativeState, TeamState, CapabilityState,
     MetricsState, WorldState frozen dataclasses.
   - `observation.py` — GovernanceObservation, InitiativeObservation,
     TeamObservation (observation boundary enforced: no latent q).
   - `actions.py` — ContinueStop, SetExecAttention, AssignTeam,
     GovernanceActions.
   - `events.py` — MajorWinEvent, StopEvent, CompletionEvent,
     ReassignmentEvent, AttentionViolationEvent.
2. Full naming convention rename pass applied across all source and tests
   per `docs/study/naming_conventions.md`.
3. 66 tests passing, lint-clean, ruff-formatted.

### Notable decisions

- All dataclasses use `frozen=True`.
- `belief_history` stored as `tuple[float, ...]` (not deque) since
  InitiativeState is frozen — engine rebuilds each tick.
- `DistributionSpec` is a union type, not a Protocol — pool generator
  dispatches on isinstance.

---

## 2026-03-11 — Phase 2: noise.py and pool.py

### What was done

1. Implemented `noise.py` — MRG32k3a CRN stream construction:
   - `derive_ref_seed`: world_seed → SHA-256 → 6-component ref_seed
     with modular reduction and nonzero guarantees.
   - Substream mapping: pool generator at substream 0, initiative i
     quality signal at 2i+1, exec signal at 2i+2.
   - Factory functions: `create_pool_rng`, `create_initiative_rng_pair`,
     `create_all_initiative_rngs` — all accept either world_seed or
     pre-built RNG streams for SimOpt wrapper compatibility.
   - Variate helpers: `draw_normal`, `draw_uniform`, `draw_uniform_int`,
     `draw_beta`, `draw_lognormal`, `draw_from_distribution`.
   - `SimulationRng` type alias and `InitiativeRngPair` frozen dataclass.
   - No other module imports mrg32k3a directly.
2. Implemented `pool.py` — initiative pool generator:
   - `generate_initiative_pool`: resolves InitiativeGeneratorConfig into
     concrete ResolvedInitiativeConfig tuple via pool-generator RNG.
   - Dispatches on DistributionSpec type for attribute draws.
   - Builds ValueChannels from type spec templates (completion lump,
     residual, major-win event).
   - `is_major_win` assigned deterministically: `q >= q_major_win_threshold`.
   - Enforces generator invariants: residual-on-completion and
     capability-on-completion both require true_duration_ticks.
   - Sequential initiative IDs, generation_tag propagated.
3. Added `mrg32k3a>=2.0` to pyproject.toml dependencies.
4. Committed doc updates from prior session alongside code:
   CLAUDE.md (MRG32k3a invariant, dependency list), simopt_notes.md (new),
   claude_plan.md (RNG strategy update).
5. 73 new tests (39 noise, 34 pool), 139 total passing.
   Lint, format, mypy strict all clean.

### Notable decisions

- **MRG32k3a from the start** — uses SimOpt's native RNG directly
  rather than deferring migration. See `simopt_notes.md`.
- **Substream-per-instance** — each RNG use case gets its own MRG32k3a
  instance positioned at a specific substream via `s_ss_sss_index`,
  rather than sharing/advancing a single instance. This gives true
  CRN isolation.
- **SHA-256 seed derivation** — `str(world_seed)` hashed to produce
  6 × 32-bit components reduced modulo MRG32k3a moduli. Defensive
  nonzero clamping for the astronomically unlikely all-zeros case.
- **Pool RNG uses substream 0** — initiative substreams offset by +1/+2
  to avoid collision.

---

## 2026-03-11 — Phase 3: learning.py (signal model and belief updates)

### What was done

1. Implemented `learning.py` — signal model, belief updates, and
   learning mechanics. All functions are pure:
   - `attention_noise_modifier`: g(a) piecewise curve with floor/ceiling
     clamping. Handles g_max=None per open issue 5.
   - `effective_signal_st_dev_t`: σ_eff = σ_base * (1 + α_d * d) * g(a) / C_t
     per core_simulator.md. Uses the canonical linear form for dependency
     noise (not the power form erroneously described in config.py comments).
   - `learning_efficiency`: L(d) = 1 - d canonical formula with optional
     ModelConfig override via dependency_learning_scale.
   - `ramp_multiplier`: linear and exponential shapes. Returns 1.0 when
     is_ramping is False (t_elapsed >= R - 1). Handles R <= 1 edge case.
   - `draw_quality_signal`: y_t ~ Normal(q, σ_eff^2) via noise.draw_normal.
   - `draw_execution_signal`: z_t ~ Normal(q_exec, σ_exec^2), NOT
     attention-modulated (asymmetry by design).
   - `update_quality_belief`: c_{t+1} = clamp(c_t + η * ramp * L(d) * (y_t - c_t), 0, 1).
     Attention does NOT appear in the update formula — it affects
     learning indirectly through σ_eff in the signal distribution.
   - `update_execution_belief`: c_exec_{t+1} = clamp(c_exec_t + η_exec * (z_t - c_exec_t), 0, 1).
     No dependency modulation, no ramp, no attention.
2. 62 new tests covering:
   - g(a) shape: boundary conditions, clamping, continuity at threshold,
     exact formulas for both branches.
   - σ_eff: formula correctness, dependency/capability/attention effects.
   - L(d): canonical formula, override, boundary values.
   - Ramp: linear/exponential shapes, first tick, fully ramped, past
     ramp, monotonicity, period edge cases (R=0, R=1, R=2).
   - Signal draws: determinism, distributional convergence, RNG isolation.
   - Quality belief: convergence, clamping, zero-rate edges, ramp and
     dependency slowdown effects.
   - Execution belief: convergence, clamping, no dependency modulation.
   - End-to-end: attention → noise → signal → belief pipeline determinism.
3. 201 total tests passing. Lint, format, mypy all clean.

### Notable decisions

- **σ_eff uses (1 + α_d * d) not (1 + d)^α_d** — core_simulator.md
  specifies the linear form. The config.py comment from Phase 1
  erroneously describes a power form. The design doc is authoritative.
  The config field name `dependency_noise_exponent` is a legacy misnomer
  but renaming it is deferred to avoid unnecessary churn.
- **Attention affects noise, not the belief update directly** — g(a)
  enters through σ_eff (signal distribution), not through the update
  formula. This matches core_simulator.md step 5 exactly.
- **Ramp multiplier returns 1.0 when is_ramping = False** — at
  t_elapsed >= R-1, the multiplier is 1.0 regardless of shape, even
  though the exponential formula would give ~0.95 at ramp_fraction = 1.0.
- **learning_efficiency supports dependency_learning_scale override** —
  when ModelConfig.dependency_learning_scale is not None, it replaces
  the canonical L(d) = 1 - d formula entirely.

---

## 2026-03-11 — Phase 4: tick.py (tick engine)

### What was done

1. Implemented `tick.py` — two pure functions implementing the full
   tick sequence from core_simulator.md:
   - `apply_actions`: applies GovernanceActions to WorldState in
     deterministic order: ContinueStop → AssignTeam → SetExecAttention.
     Handles stop transitions (lifecycle → STOPPED, team release, StopEvent
     emission), new assignments (lifecycle → ACTIVE, ticks_since_assignment
     reset), same-team re-assignment (no ramp reset), idle assignment
     (team release), and attention (reset to 0.0 when omitted).
   - `step_world`: implements steps 3–7 of the canonical tick sequence.
     Production & observation (signal draws via learning.py, counter
     increments), belief updates (quality and execution), review-state
     update (review_count, TAM adequacy counter with proper accumulation),
     belief history ring buffer (tuple-based, trimmed to W_stag),
     completion detection (staffed_tick_count >= true_duration_ticks),
     completion-lump value realization, major-win event emission,
     residual activation at completion, capability update (decay then
     gains, clamped to [1.0, C_max]), end-of-tick residual value pass
     with exponential decay, team release on completion.
   - `TickResult` frozen dataclass: new world state, completion/major-win/
     stop events, channel-separated value realized this tick.
   - Helper functions: `_update_tam_counter` (TAM adequacy test with
     accumulation), `_append_belief_history` (tuple ring buffer),
     `_update_portfolio_capability` (decay + gains + clamp).
2. 59 new tests covering:
   - apply_actions: stop transitions, team release, stop events, continue
     no-op, assignment lifecycle transitions, ramp reset on new assignment,
     no ramp reset on same-team, idle assignment, attention set/reset.
   - step_world production: counter increments (staffed_tick_count,
     ticks_since_assignment, age_ticks, labor, attention), unstaffed and
     stopped initiatives skipped.
   - Belief updates: quality belief convergence toward latent quality,
     execution belief updates for bounded-duration, None for unbounded.
   - Review state: review_count increment, TAM counter accumulation when
     belief below threshold, TAM counter reset when no ceiling or unstaffed.
   - Belief history: append, trim to window, empty start, integration.
   - Completion: at threshold, before threshold, event emission, no
     completion for unbounded.
   - Lump value: realized on completion, zero when disabled.
   - Major-win: event emitted when flagged, no event when not flagged.
   - Residual: activation on completion, same-tick firing (τ=0), decay.
   - Capability: gains from completion, decay without completions, C_max
     clamp, floor at 1.0, decay-then-gains order.
   - Team release on completion.
   - Tick counter advancement.
   - Determinism: same seed → same result, different seeds → different.
   - Stable iteration: output sorted by initiative_id.
   - Multi-initiative: independent processing, multiple completions same
     tick with aggregated capability gains.
3. 260 total tests passing. Lint (ruff), format (ruff), mypy strict all clean.

### Key implementation details

- **Pre-increment ramp**: ramp_multiplier uses ticks_since_assignment
  BEFORE incrementing, per core_simulator.md step 2/3. On the first
  staffed tick (ticks_since_assignment=0), ramp_fraction = 1/R.
- **TAM counter accumulates**: _update_tam_counter takes current_count
  and returns current_count + 1 when below threshold (not just 1).
- **Belief history as tuple**: since InitiativeState is frozen, the ring
  buffer is rebuilt each tick by appending and trimming. Per decisions.md
  issue 4.
- **Residual fires same tick as completion**: per core_simulator.md
  step 5c/6, residual_activation_tick = current_tick, then the residual
  pass at step 6 computes τ_residual = 0 and realizes the full rate.
- **Capability update order**: decay existing excess first, then add new
  gains undecked, per core_simulator.md step 5c formula.
- **Team release on completion**: applied to end-of-tick state so it's
  visible at start of next tick, per action-timing invariant.
- **Attention non-persistence**: all initiatives reset to attention=0.0
  before applying SetExecAttention actions.
- **TYPE_CHECKING imports**: GovernanceActions, ResolvedInitiativeConfig,
  SimulationConfiguration, InitiativeRngPair moved to TYPE_CHECKING block
  per project TCH lint rules.

---

## 2026-03-11 — Phase 5: governance.py and policy.py

### What was done

1. Pre-Phase-5 code updates (from design corpus patch in commit 271c8f8):
   - `config.py` — added 3 optional fields to GovernanceConfig:
     `low_quality_belief_threshold`, `max_low_quality_belief_labor_share`,
     `max_single_initiative_labor_share` (all `float | None = None`).
   - `observation.py` — added `PortfolioSummary` frozen dataclass
     (active_labor_total, active_labor_below_quality_threshold,
     low_quality_belief_labor_share, max_single_initiative_labor_share),
     added `portfolio_summary: PortfolioSummary` to GovernanceObservation,
     added `required_team_size: int` to InitiativeObservation.
   - `conftest.py` — updated make_governance_config with new fields,
     added factory functions: make_initiative_observation,
     make_team_observation, make_portfolio_summary,
     make_governance_observation.

2. Implemented `governance.py` — decision primitives (all pure functions):
   - **Stop primitives**: `should_stop_confidence_decline` (policy-side
     threshold on quality_belief_t), `should_stop_tam_adequacy` (counter
     >= effective patience window, bounded-prize only),
     `should_stop_stagnation` (conjunctive: informational stasis AND
     second-leg patience condition — bounded-prize uses TAM counter > 0,
     non-TAM uses belief <= initial baseline),
     `should_stop_execution_overrun` (execution_belief_t < threshold).
   - **Attention helpers**: `compute_equal_attention` (equal budget split
     with per-initiative clamping), `compute_weighted_attention`
     (proportional allocation with clamping and budget scaling).
   - **Selection helpers**: `expected_prize_value`,
     `expected_prize_value_density` (normalized by required_team_size),
     `rank_unassigned_bounded_prize` (descending density, ties by id),
     `rank_unassigned_initiatives` (bounded first by density, then
     unbounded by belief).
   - **Portfolio-risk helpers**: `is_low_quality_labor_share_exceeded`,
     `is_single_initiative_concentration_exceeded`,
     `would_assignment_exceed_concentration`,
     `would_assignment_exceed_low_quality_share`.

3. Implemented `policy.py` — archetype compositions:
   - `GovernancePolicy` Protocol with `decide()` method.
   - **BalancedPolicy**: canonical reference baseline. Applies all four
     stop rules in priority order (confidence decline → execution overrun
     → TAM adequacy → stagnation). Equal attention allocation. Ranks
     unassigned by prize density then belief. Applies portfolio-risk
     controls when configured.
   - **AggressiveStopLossPolicy**: same rule set as Balanced but
     prioritizes execution overrun before TAM. Aggressiveness comes from
     GovernanceConfig thresholds, not different rule logic.
   - **PatientMoonshotPolicy**: skips confidence decline entirely. Only
     stops on execution overrun, TAM adequacy, or stagnation. Tolerates
     short-term belief declines in pursuit of long-term discovery.
   - Shared internal helpers: `_get_active_staffed`,
     `_get_available_teams`, `_find_team_for_initiative`,
     `_collect_stop_actions_balanced`, `_assign_freed_teams`,
     `_allocate_equal_attention`.

4. Tests:
   - `test_observation.py` — 12 tests: PortfolioSummary construction and
     immutability, InitiativeObservation with required_team_size,
     GovernanceObservation with portfolio_summary, TeamObservation.
   - `test_governance.py` — 60 tests: all primitives in isolation with
     known inputs. Edge cases: None thresholds, no observable_ceiling,
     empty/short belief history, zero active labor, window size 1,
     threshold boundary conditions (strict < vs <=).
   - `test_policy.py` — 33 tests: protocol compliance, each archetype's
     decide() method, action vector structure, stop decisions with correct
     triggering_rule, team assignment, attention allocation, portfolio-risk
     blocking, confidence-decline priority, edge cases (unassigned/completed/
     stopped/unstaffed not reviewed, team too small, newly assigned gets
     attention, all stopped no attention).
   - `test_config.py` — 2 new tests for portfolio-risk config defaults
     and explicit values.

5. 367 total tests passing. Ruff lint, ruff format, mypy strict all clean.

### Key design choices

- **Primitives vs policies**: governance.py exports stateless pure
  functions that evaluate one concern. policy.py composes them. This
  matches the CLAUDE.md architecture rule: "governance.py exports
  decision primitives; policy.py composes those primitives into
  governance archetypes."
- **Rule priority order**: Balanced and Aggressive use confidence decline
  → execution overrun → TAM → stagnation. Patient Moonshot omits
  confidence decline entirely. The priority order determines which
  triggering_rule is recorded — it does not change the outcome for
  initiatives that trigger only one rule.
- **Aggressiveness via config, not logic**: AggressiveStopLossPolicy
  uses the same stop rules as Balanced. The study compares governance
  *settings* (tighter thresholds in GovernanceConfig) rather than
  different rule implementations.
- **Portfolio-risk as optional policy-side checks**: The primitives
  `would_assignment_exceed_concentration` and
  `would_assignment_exceed_low_quality_share` are checked during
  team assignment. The engine never enforces these — per canonical
  invariant #7 (portfolio controls remain governance-side).
- **Selection ranking**: bounded-prize initiatives ranked by
  expected_prize_value / required_team_size (density). Non-bounded
  ranked by quality_belief_t. Bounded always precede unbounded.
- **belief_histories passed explicitly**: policies receive
  belief_histories as a dict parameter from the caller (runner) rather
  than extracting it from the observation bundle. This avoids adding
  mutable history to the observation boundary.
- **team_sizes passed explicitly**: policies receive team_sizes as a
  dict parameter because TeamObservation does not carry team_size
  (it's a workforce-level attribute). Default assumption is size 1.

---

## 2026-03-12 — Phase 6: reporting.py and runner.py

### What was done

1. Implemented `reporting.py` — output schemas and aggregation:
   - **Per-tick record types**: `PerInitiativeTickRecord` (tick, initiative_id,
     lifecycle_state, quality_belief_t, latent_quality post-hoc,
     exec_attention_a_t realized, effective_sigma_t, execution_belief_t,
     is_ramping, ramp_multiplier), `PortfolioTickRecord` (tick,
     capability_C_t, active_initiative_count, idle_team_count,
     total_exec_attention_allocated). All frozen dataclasses.
   - **Value breakdown types**: `ValueByChannel` (lump, residual,
     residual_by_label), `MajorWinProfile` (count, time_to_major_win,
     count_by_label, labor_per_major_win), `BeliefAccuracy` (MAE, MSE),
     `IdleCapacityProfile`, `ExplorationCostProfile` (stopped and completed
     investment by label), `ReassignmentProfile`.
   - **RunManifest**: policy_id, world_seed, is_replay, resolved config,
     resolved initiatives, engine_version.
   - **RunResult**: complete frozen output record with all primary outputs
     per review_and_reporting.md. Event logs and per-tick logs conditional
     on ReportingConfig flags.
   - **RunCollector**: mutable accumulator used by the runner during the
     tick loop, then consumed by assemble_run_result().
   - **Aggregation functions**: compute_belief_accuracy, compute_value_by_channel,
     compute_major_win_profile, compute_idle_capacity_profile,
     compute_exploration_cost_profile, compute_terminal_aggregate_residual_rate,
     assemble_run_result.

2. Implemented `runner.py` — tick loop orchestration (only impure module):
   - **run_single_regime**: validate config → resolve generator → seed RNGs
     → initialize WorldState → main tick loop → assemble RunResult.
   - **run_batch**: sequential wrapper, no shared mutable state across configs.
   - **Tick loop**: each tick counts idle teams, applies pending actions,
     calls step_world, collects events/values, builds GovernanceObservation
     (observation boundary enforced), invokes policy, stores pending actions.
   - **_build_governance_observation**: constructs InitiativeObservation with
     derived fields (effective_tam_patience_window, implied_duration_ticks,
     progress_fraction), computes PortfolioSummary, enforces observation
     boundary (no latent_quality, no true_duration_ticks).
   - **_detect_reassignments**: identifies reassignment triggers
     (governance_stop, completion, idle_reassignment) from action vectors.
   - **_initialize_world_state**: all initiatives UNASSIGNED, all teams idle,
     portfolio_capability=1.0, tick=0. Supports per-initiative initial beliefs.
   - **_collect_per_tick_records**: computes effective_sigma_t, ramp state,
     and attention for PerInitiativeTickRecord. Conditional on ReportingConfig.
   - **_accumulate_ramp_labor**: tracks team-ticks consumed during ramp.
   - **_extract_belief_histories**: pulls belief_history tuples from WorldState.

3. Updated `policy.py` — added belief_histories and team_sizes keyword
   arguments to the GovernancePolicy Protocol to match the actual policy
   implementations and the runner's call site.

4. Tests:
   - `test_reporting.py` — 27 tests: frozen dataclass contracts, belief
     accuracy with known inputs (perfect, known errors, empty), value-by-channel
     label disaggregation (single/multiple/none), major-win profile (no wins,
     single, multiple), idle capacity profile (no idle, all idle, partial,
     zero total), exploration cost profile (no events, mixed stop/completion),
     terminal residual rate (no residual, no decay, with decay, multiple summed),
     RunCollector mutability, assemble_run_result integration (minimal assembly,
     conditional event logs).
   - `test_runner.py` — 36 tests: _initialize_world_state (all unassigned,
     all idle, tick zero, capability baseline, team count, default/specific
     initial beliefs, stable ordering), _build_governance_observation
     (no latent quality, effective TAM patience window, implied duration,
     progress fraction, attention max default, capability level),
     _detect_reassignments (idle, governance stop), _extract_belief_histories,
     run_single_regime integration (basic run, deterministic replay, horizon
     boundary, per-tick logs enabled/disabled, event logs enabled/disabled,
     value accumulation, idle counting, manifest contents), run_with_generator,
     run_batch (list of results, length mismatch, empty, independent results),
     invariants (value = lump + residual, terminal capability baseline,
     ramp labor non-negative, idle fraction in [0,1]).

5. 430 total tests passing (367 existing + 27 reporting + 36 runner).
   Ruff lint, ruff format, mypy strict all clean.

### Key design choices

- **RunCollector pattern**: mutable accumulator during tick loop, then
  consumed by assemble_run_result() to produce immutable RunResult. Keeps
  the tick loop simple and avoids accumulating state in multiple places.
- **Observation boundary enforcement**: _build_governance_observation
  constructs observations directly from WorldState without ever copying
  latent_quality or true_duration_ticks into any observation field.
- **Pending actions pattern**: governance decides at end of tick T, actions
  stored in pending_actions, applied at start of tick T+1 via apply_actions.
  At tick 0, pending_actions is None (no prior governance decision).
- **Idle counting at tick start**: idle teams counted before actions are
  applied, matching core_simulator.md rule that a team-tick is idle when
  the team has no assignment at the start of the tick.
- **Ramp labor uses pre-increment ticks_since_assignment**: since step_world
  increments ticks_since_assignment, the runner subtracts 1 from the
  post-step value to recover the pre-increment value used during production.
- **Pool exhaustion detection**: detected when at least one team is idle AND
  no UNASSIGNED initiatives remain in the pool.
- **GovernancePolicy Protocol updated**: added belief_histories and team_sizes
  as optional keyword arguments to match the actual policy implementations
  and the runner's call site.
- **Per-tick record sigma computation**: effective_sigma_t recomputed from
  initiative config and world state for each record, matching the sigma
  used during that tick's production step.

---

## 2026-03-12 — Phase 7 plan: experiment specification and campaign generation

### What was done

Revised `claude_plan.md` Phase 7 from a narrow "baseline preset layer"
to a full "experiment specification and campaign generation" phase. This
was a planning-only session — no code changes.

### Key design decisions

1. **Three experiment-design levels articulated**: (1) initiative
   instances are stochastic draws from the generator — no LHS;
   (2) governance parameters use named archetypes + LHS for the
   continuous sweep; (3) environment/generator configurations are a
   separate experimental dimension, deferred to Phase 8.

2. **Phase 7 structured with two milestones**: Milestone 1 is the
   baseline preset layer (presets.py, smoke tests, three-archetype
   comparison). Milestone 2 is the campaign abstraction layer
   (EnvironmentSpec, GovernanceSweepSpec, CampaignSpec, LHS generator,
   manifest serialization, batch execution hooks).

3. **Portfolio-risk controls not folded into main LHS**: per
   experiments.md, portfolio-risk parameters are a targeted follow-on
   sweep family, not part of the baseline governance sweep.

4. **Pool exhaustion treated as configuration error**: the canonical
   baseline must oversize the pool so no governance regime exhausts
   it within the simulation horizon.

5. **All portfolio-risk parameters explicit in presets**: even when
   the baseline value is None, presets must set these fields explicitly
   for completeness and comparability.

6. **JSON manifest, sweep harness, and batch hooks pulled into Phase 7**:
   previously deferred to Phase 8, these belong in the experiment-
   definition layer. SimOpt and parallel execution remain Phase 8.

### Rationale

The previous Phase 7 draft was scoped too narrowly. It would have
gotten a first simulation running but then needed a Phase 7.5 for
all the campaign infrastructure. The user's guidance is that Phase 7
should contain the full experiment-definition layer, with the baseline
preset work as the first execution milestone inside that phase.

---

## 2026-03-12 — Phase 7, Milestone 1: baseline preset layer

### What was done

1. **`src/primordial_soup/presets.py`** — baseline configuration presets:
   - `make_baseline_time_config()` — 200-tick horizon
   - `make_baseline_workforce_config()` — 8 teams, ramp period 4
   - `make_baseline_model_config()` — exec_attention_budget=10.0
     (conservatively high), reference_ceiling=50.0, standard
     learning/attention curve parameters
   - `make_baseline_initiative_generator_config()` — 100 initiatives
     across 4 canonical types: 20 flywheels, 20 right-tail,
     15 enablers, 45 quick-wins. Pool deliberately oversized to
     prevent exhaustion under any governance regime.
   - `make_balanced_config(world_seed)` — Balanced archetype factory.
     Moderate thresholds: confidence_decline=0.3, tam_ratio=0.6,
     tam_patience=10, stagnation_window=15, exec_overrun=0.4.
     All portfolio-risk params explicitly None.
   - `make_aggressive_stop_loss_config(world_seed)` — Aggressive
     archetype. Tighter thresholds: confidence_decline=0.4,
     tam_patience=5, stagnation_window=8, exec_overrun=0.5.
   - `make_patient_moonshot_config(world_seed)` — Patient Moonshot
     archetype. confidence_decline=None (disabled), tam_patience=20,
     stagnation_window=25, exec_overrun=0.3.
   - All three share the same baseline environment (TimeConfig,
     WorkforceConfig, ModelConfig, InitiativeGeneratorConfig).

2. **`tests/test_presets.py`** — 41 tests covering:
   - Baseline environment validation (9 tests): pool sizing, type
     composition, attribute ranges
   - Balanced preset construction (6 tests): validation, generator
     path, policy_id, stop rules, portfolio-risk params, model copy
   - Balanced smoke test (8 tests): nonzero value, completions,
     stops, lump/residual value, no pool exhaustion, capability,
     residual streams, determinism
   - Aggressive Stop-Loss preset (5 tests): validation, policy_id,
     tighter thresholds, portfolio-risk, same environment
   - Patient Moonshot preset (7 tests): validation, policy_id,
     confidence-decline disabled, longer patience, tolerant overrun,
     portfolio-risk, same environment
   - Three-archetype comparison (6 tests): identical pools (CRN),
     different outcomes, aggressive stops more, patient stops fewer,
     no pool exhaustion, positive value

3. **471 tests passing**, lint/format/mypy clean.

### Design decisions

- **Pool size 100** (20+20+15+45): initial 50-initiative pool exhausted
  at tick 82 under Balanced governance. Doubled to 100 to provide
  comfortable headroom under all archetypes.

- **exec_attention_budget=10.0**: with 8 teams and attention_max=None,
  worst case is 8 initiatives each getting 1.0 attention = 8.0 total.
  10.0 provides headroom against feasibility violations.

- **Attention bounds same across archetypes**: per experiments.md,
  attention allocation breadth is a sweep dimension, not an archetype
  distinction. All three archetypes use attention_min=0.15,
  attention_max=None.

- **Parameter values chosen for qualitative distinctiveness**: the design
  corpus describes archetypes qualitatively. Concrete parameter values
  were chosen so that Aggressive stops measurably more than Balanced,
  and Patient measurably fewer — verified by the comparison tests.

---

## 2026-03-12 — Phase 7, Milestone 2: campaign abstractions

### What was done

1. **`src/primordial_soup/campaign.py`** — campaign specification types
   and LHS governance sweep generator:
   - `EnvironmentSpec` — frozen dataclass wrapping TimeConfig,
     WorkforceConfig, ModelConfig, InitiativeGeneratorConfig. Represents
     one Level 3 environment.
   - `LhsParameterBounds` — 8-dimensional bounds for the LHS governance
     parameter space.
   - `GovernanceSweepSpec` — LHS parameters (bounds, sample count,
     design_seed) plus archetype anchor control.
   - `CampaignSpec` — combines EnvironmentSpec + GovernanceSweepSpec +
     world_seeds. Each (governance_config, world_seed) pair is one run.
   - `generate_lhs_unit_sample()` — pure NumPy LHS implementation.
     Stratified sampling with column permutation, no scipy dependency.
   - `generate_governance_configs()` — scales LHS to parameter bounds,
     rounds integer params, derives attention_max from attention_min +
     attention_span, appends 3 archetype anchors as fixed supplemental
     points. All portfolio-risk params set to None.
   - `make_default_parameter_bounds()` — canonical default ranges.
   - `CampaignResult` — frozen output bundle with all RunResults.
   - `run_campaign()` — sequential campaign runner with PolicyFactory
     callable for policy instantiation.

2. **`src/primordial_soup/manifest.py`** — JSON serialization:
   - `governance_config_to_dict()` — all fields explicit, including None.
   - `campaign_spec_to_dict()` — environment summary, sweep params,
     design_seed, parameter bounds, world_seeds.
   - `run_manifest_to_dict()` — provenance fields.
   - `campaign_result_to_dict()` — per-run summary metrics.
   - `write_campaign_manifest()` / `read_campaign_manifest()` — file I/O
     with automatic parent directory creation.

3. **`src/primordial_soup/presets.py`** — added
   `make_baseline_environment_spec()` factory wrapping the four baseline
   component configs into an EnvironmentSpec. Uses deferred import to
   avoid circular dependency with campaign.py.

4. **`tests/test_campaign.py`** — 49 tests covering:
   - EnvironmentSpec: construction, preset matching, immutability (3)
   - LhsParameterBounds: construction, range validity, constraints (4)
   - GovernanceSweepSpec/CampaignSpec: construction, immutability (3)
   - LHS unit sample: shape, unit interval, stratification property,
     reproducibility, seed variation, single sample (6)
   - Governance config generation: counts with/without archetypes,
     type checking, policy_id naming, bounds respected, integer types,
     attention_max derivation and capping, portfolio-risk None,
     disabled rules always active in LHS, validation pass,
     reproducibility, seed variation, invalid count, warning (18)
   - Manifest serialization: field completeness, None explicit, JSON
     round-trip, structure, design_seed/bounds recorded, world_seeds,
     file I/O with parent dir creation (10)
   - Campaign runner: correct run count, result structure, positive
     value, determinism, serialization (5)

5. **520 total tests passing** (471 + 49 new). Ruff lint, ruff format,
   mypy strict all clean.

### Key design decisions

- **NumPy for LHS design-time randomness**: LHS generates experimental
  design points (which governance configs to test), not simulation-time
  stochasticity. SimOpt controls replication (world_seed → per-run RNG
  streams), not experimental design. NumPy seeded with design_seed,
  recorded in manifest for provenance. Swap to MRG32k3a is localized
  if needed later.

- **Disabled governance rules as separate design points**: baseline LHS
  samples only over active parameters (all 8 float/int values within
  bounds). confidence_decline_threshold=None and
  exec_overrun_threshold=None are structural choices handled as explicit
  supplemental design points or separate campaign families, not encoded
  in the LHS. Keeps interpretation clean.

- **attention_span as sweep dimension**: the canonical sweep samples
  attention_min directly and a nonnegative attention_span. attention_max
  is derived as min(attention_min + attention_span, 1.0). attention_max
  is constructed, not sampled — guaranteeing feasibility by construction.

- **Portfolio-risk params excluded from baseline LHS**: set to None in
  every generated GovernanceConfig. Targeted follow-on sweep family
  per experiments.md.

- **Sequential campaign runner**: no parallelism, no optimization. The
  goal of Milestone 2 is a correct, reproducible campaign-definition
  layer, not a high-throughput runner. Parallel execution is Phase 8.

- **Circular import avoidance**: campaign.py imports preset governance
  config factories; presets.py imports EnvironmentSpec via deferred
  import inside make_baseline_environment_spec().

---

## 2026-03-13 — Reporting surface expansion and human-readable summary labels

### What was done

1. **`src/primordial_soup/reporting.py`** — added `max_portfolio_capability_t`:
   - `RunCollector`: new field with default 1.0 (matches initial C_t).
   - `RunResult`: new field in terminal state block alongside
     `terminal_capability_t`. Documents that it complements
     terminal_capability_t which may be lower due to capability decay.
   - `assemble_run_result`: wires collector field to RunResult.

2. **`src/primordial_soup/runner.py`** — unconditional tracking:
   - After `world_state = tick_result.world_state` in `_run_tick_loop`,
     updates `collector.max_portfolio_capability_t` with running max.
   - Not gated on reporting flags — this is a run-level summary scalar.

3. **`src/primordial_soup/manifest.py`** — expanded `campaign_result_to_dict`
   run summaries with fields already on RunResult but not previously
   serialized:
   - Value channel decomposition: completion_lump_value, residual_value,
     residual_value_by_label (dict[str, float]).
   - Organizational health: max_portfolio_capability_t,
     terminal_aggregate_residual_rate.
   - Completion/stop counts by type: completed_initiative_count_by_label,
     cumulative_labor_in_completed_initiatives,
     stopped_initiative_count_by_label (all dict[str, int]).
   - Belief accuracy: mean_absolute_belief_error.
   - Updated docstring to describe the expanded content.

4. **`docs/design/review_and_reporting.md`** — documentation:
   - Added `max_portfolio_capability_t` bullet after `terminal_C_t`
     with full usage guidance.
   - Updated `terminal_aggregate_residual_rate` bullet to note it is
     now serialized in run summary output.

5. **`scripts/run_single.py`** — human-readable output:
   - Grouped metrics by category (value, organizational momentum,
     discovery, governance quality, initiative outcomes).
   - Inline comments explain less obvious metrics.

6. **`scripts/run_campaign_small.py`** — human-readable output:
   - Added metric guide legend block printed once before per-archetype
     breakdown. Explains: cumulative value, idle %, major wins, free
     value/tick, peak productivity, productivity at end, quality est.
     error.
   - Relabeled per-archetype metrics with practitioner-friendly names.

### Why

The JSON serialization gap meant campaign-level analysis could not see
value channel decomposition, enabler impact, completion/stop patterns,
or belief accuracy without post-processing individual RunResult objects.
`max_portfolio_capability_t` was needed because `terminal_capability_t`
alone understates enabler impact — capability decays exponentially
between enabler completions, so the terminal value can be substantially
lower than the peak effect that was active during the run.

The human-readable labels address the interpretation gap: raw field
names like `terminal_aggregate_residual_rate` and `terminal_capability_t`
do not communicate their practical meaning to practitioners. The study's
position on right-tail value (count discoveries, do not estimate value)
is reflected in the summary showing major win count only.

### No changes to

- Engine modules (tick.py, state.py, learning.py, events.py, noise.py,
  observation.py, actions.py, policy.py).
- No new aggregation functions — all data was already computed.
- 520 tests passing, no test changes needed.

---

## 2026-03-14 — Three-layer model Phase 1

### What was done

1. **`src/primordial_soup/config.py`** — added `total_labor_endowment`
   computed property to `WorkforceConfig`, tuple `team_size` length
   validation in `validate_configuration`, updated `GovernanceConfig`
   docstring with two-section layout.

2. **`src/primordial_soup/campaign.py`** — added `WorkforceArchitectureSpec`
   frozen dataclass with `resolve()` method producing concrete
   `WorkforceConfig`. Supports uniform teams (divisibility check) and
   explicit `team_sizes`.

3. **`src/primordial_soup/presets.py`** — added
   `make_baseline_workforce_architecture_spec()` factory.

4. **Tests**: 14 new tests (config, campaign, presets).

5. **Design docs**: updated by user (governance.md, interfaces.md,
   study_overview.md, team_and_resources.md, architecture.md,
   experiments.md, index.md). Committed separately as 9bf82cb.

### Why

Phase 1 of the three-layer conceptual model (environment, governance
architecture, operating policy). Purely additive — no breaking changes,
simulator boundary untouched.

---

## 2026-03-14 — Run design workbench with YAML authoring surface

### What was done

1. **`src/primordial_soup/workbench.py`** — new module, the single
   human-facing authoring layer for simulation runs:
   - `EnvironmentConditionsSpec` — Layer 1: family + optional overrides
   - `GovernanceArchitectureSpec` — Layer 2: workforce + guardrails
   - `OperatingPolicySpec` — Layer 3: preset-only policy selection
   - `RunDesignSpec` — top-level spec with `from_dict()` YAML parser
   - `ResolvedRunDesign` — resolution output with `summary()`
   - `validate_run_design()` — eager multi-error validation
   - `resolve_run_design()` — three-layer resolution
   - `make_baseline_run_design_spec()` — convenience factory
   - `make_policy()` — policy_id → policy class registry
   - `summarize_run_result()` — RunResult summary extraction matching
     campaign script output format

2. **`scripts/run_design.py`** — CLI entry point:
   `python scripts/run_design.py my_run.yaml`
   - `--dry-run` validates and prints summary without executing
   - `--no-confirm` skips interactive prompt
   - `--output-dir` sets result directory (default: output/)
   - Console output matches campaign script: value min/max/mean,
     metric guide legend, aggregate stats
   - JSON result files with full metrics

3. **YAML templates**:
   - `templates/run_design_template.yaml` — fully documented master
   - `templates/presets/` — 9 preset YAML files (3 families × 3 policies)

4. **`docs/guides/run_design_guide.md`** — user-facing guide
   for the YAML workflow

5. **`tests/test_workbench.py`** — 95 tests across 11 classes:
   TestEnvironmentConditionsSpec, TestGovernanceArchitectureSpec,
   TestOperatingPolicySpec, TestRunDesignSpec, TestValidateRunDesign,
   TestResolveRunDesign, TestResolvedRunDesignSummary,
   TestMakeBaselineRunDesignSpec, TestPortfolioGuardrailsPassthrough,
   TestRunDesignSpecFromDict, TestMakePolicy

6. **`pyproject.toml`** — added `pyyaml>=6.0` dependency

7. **650 total tests passing**. Ruff lint, ruff format all clean.

### Key design decisions

- **YAML, not Python**: users edit a YAML file and run one command.
  The Python API remains available for programmatic use and campaigns.
- **`from_dict()` on RunDesignSpec**: all YAML schema interpretation
  lives on the type itself — single update point when model evolves.
- **`make_policy()` registry**: central policy_id → class mapping
  keeps the CLI script thin and avoids requiring callers to know the
  preset → policy class relationship.
- **`summarize_run_result()` matches campaign output**: same fields
  as `run_campaign_small.py` for direct comparability. Includes
  cumulative_value, lump/residual, free_value_per_tick, peak/end
  productivity, idle_fraction, quality_est_error, completed/stopped
  by label.
- **Policy classes take no constructor args**: `make_policy()` calls
  `registry[policy_id]()` not `registry[policy_id](governance_config)`.
  GovernanceConfig is passed to `decide()` at each tick.
- **PyYAML dependency justified**: user-facing authoring surface
  requires YAML parsing. Graceful error message if not installed.

### No changes to

- Engine modules (tick.py, state.py, learning.py, noise.py, pool.py,
  observation.py, actions.py, events.py, governance.py, policy.py,
  reporting.py, runner.py, config.py, campaign.py, presets.py,
  manifest.py, types.py).
- Simulator boundary fully preserved — engine receives only frozen
  SimulationConfiguration objects.

---

## 2026-03-15 — Business intent translation layer, portfolio mix targets, generation_tag observation extension

### What was done

Three related features, implemented across one session:

1. **Portfolio mix targets** — governance-architecture inputs for
   desired labor-share distribution across initiative buckets.
   `PortfolioMixTargets` dataclass in config.py, carried through
   `GovernanceArchitectureSpec` → `GovernanceConfig` → policy. Soft
   preference only; engine never sees them.

2. **Business intent translation layer** — structured registry-based
   translation from executive-style scenario requests into the
   three-layer RunDesignSpec vocabulary. Registry YAML defines 12
   named intents, 4 bucket definitions, 2 conflict rules.
   `business_intent.py` module loads registry, validates intents,
   detects conflicts, produces RunDesignSpec instances.

3. **generation_tag observation extension** — added `generation_tag`
   to `InitiativeObservation` so the policy can classify initiatives
   into canonical buckets by authoritative tag rather than
   heuristic inference from observable attributes.

### Observation-interface extension rationale

`generation_tag` is surfaced as observable metadata, not latent ground
truth. It is set at pool generation from public `InitiativeTypeSpec`
parameters visible in environment family definitions, YAML templates,
and the run manifest. It does not reveal latent_quality,
true_duration_ticks, or any other hidden engine state.

The engine does not read, branch on, or enforce generation_tag. Only
the policy reads it, for governance-architecture purposes (portfolio
mix targeting via `classify_initiative_bucket()` in governance.py).

This preserves canonical invariant #1 (type-independence): the engine
never branches on initiative labels. The policy reading a label for
soft portfolio preferences is a governance-architecture choice, not
an engine behavior.

`initiative_model.md` was updated to reflect that generation_tag is
now used for "reporting and policy-side portfolio classification"
rather than "reporting only." `interfaces.md` was updated with the
full `generation_tag` field documentation.

### Files created

- `src/primordial_soup/business_intent.py` — translation module
- `src/primordial_soup/business_intent_registry.yaml` — canonical
  structured registry
- `tests/test_business_intent.py` — 57 tests
- `docs/implementation/archive/portfolio_allocation_targets_proposal.md` —
  design proposal (written before implementation)

### Files modified

- `src/primordial_soup/config.py` — `CANONICAL_BUCKET_NAMES`,
  `PortfolioMixTargets`, `GovernanceConfig.portfolio_mix_targets`
- `src/primordial_soup/observation.py` — `generation_tag` field on
  `InitiativeObservation` with rationale documentation
- `src/primordial_soup/runner.py` — populate `generation_tag` from
  `ResolvedInitiativeConfig` when building observations
- `src/primordial_soup/governance.py` — `classify_initiative_bucket()`
  (generation_tag-based), `compute_current_portfolio_mix()`
- `src/primordial_soup/policy.py` — `_rerank_for_mix_targets()` soft
  bias in `_assign_freed_teams()`
- `src/primordial_soup/workbench.py` — `GovernanceArchitectureSpec`
  with mix targets, YAML parsing, validation, resolution, summary
- `docs/design/interfaces.md` — `generation_tag` in
  InitiativeObservation schema
- `docs/design/initiative_model.md` — updated generation_tag scope
- `docs/guides/run_design_guide.md` — portfolio mix targets
  section, business intent layer section, updated error table
- `tests/conftest.py` — `generation_tag` default in test helper

### Key design decisions

- **generation_tag as canonical bucket identifier** — eliminated drift
  risk between heuristic classification and actual generator types.
  Observable-attribute classification was the v1 approach; replaced
  with direct tag lookup after design review identified the dual
  source-of-truth problem.
- **"uncategorized" is deliberate residual** — initiatives without a
  canonical generation_tag get implicit target 0.0 in the policy's
  mix-target logic. They are de-prioritized, not blocked.
- **PortfolioMixTargets on GovernanceConfig** (Option A from proposal)
  — follows the existing pattern for concentration guardrails. No
  policy protocol changes needed.
- **Registry is structural, not NLP** — intent IDs are exact string
  lookups. Business phrases in the registry are documentation, not
  matching targets.

### No changes to

- Engine tick loop (tick.py, state.py, learning.py)
- SimulationConfiguration structure
- Campaign infrastructure (campaign.py, manifest.py)
- Preset factories (presets.py)
- Simulator boundary fully preserved

### 707 total tests passing.

---

## 2026-03-17 — A.1/A.2/B.1: Calibration, Diagnostics, Fragility Mapping

### Context

A 63-run baseline campaign showed zero major wins across all archetypes
and families. Four deep research projects (Projects 1-4) identified the
root cause: the right-tail Beta distributions had near-zero tail
probability at their respective thresholds (~0.003% for balanced_incumbent).
This was a generator-collapse artifact, not a governance finding.

### A.1 — Empirical Grounding of Generator Parameters

**Root cause fixed.** Recalibrated right-tail Beta distributions and
unified threshold to 0.80 across all three families:

- balanced_incumbent: Beta(0.8, 2.0), ~3% major-win incidence
- short_cycle_throughput: Beta(0.6, 2.5), ~1% (scarce)
- discovery_heavy: Beta(1.2, 1.8), ~5-8% (rich)

Duration ranges calibrated to multi-year exploratory timelines:
(104,182) / (80,156) / (130,260) ticks.

Pool counts and pool size unchanged — pool composition is an
environmental condition, not a calibration target.

**Validation:** 63-run campaign produced 48 major wins (vs. zero before).
No pool exhaustion. All acceptance criteria passed.

**Files created/modified:**
- `docs/design/calibration_note.md` — full evidence chain
- `docs/design/generator_validity_memo.md` — updated parameter table
- `src/primordial_soup/presets.py` — Beta/threshold/duration changes
- `tests/test_presets.py` — relaxed positive-value assertion
- `scripts/calibration_sanity_check.py` — analytical + empirical harness

### A.2 — Ground-Truth Diagnostic Metrics

Five pure diagnostic functions exploiting ground-truth observability:
1. False-stop rate on eventual major wins
2. Survival curve to revelation
3. Belief-at-stop distribution
4. Attention-conditioned false negatives
5. Hazard of stop by staffed tick

**Key findings (63-run diagnostic campaign):**
- Aggressive: 92-100% false-stop rate on eligible initiatives
- Patient: 0% false-stop rate
- Balanced/Aggressive cluster 97-100% of RT stops in first 20 staffed ticks
- Belief-at-stop for eligible: mean ~0.55

**Files created:**
- `src/primordial_soup/diagnostics.py` — 5 functions + helpers
- `tests/test_diagnostics.py` — 25 tests
- `scripts/ground_truth_diagnostics.py` — study script

### B.1 — Fragility Mapping

3D grid sweep script: confidence_decline_threshold (7) x attention_min
(5) x exec_overrun_threshold (5) = 175 points x N seeds x 3 families.
Produces 2D response slices, gradient analysis, cliff identification,
cross-family comparison, and optional CSV export.

**File created:** `scripts/fragility_mapping.py`

### Test status

871 total tests passing (846 original + 25 new diagnostic tests).

---

## Reporting Package — Phase 1 (2026-03-17)

### What was done

- Added `RightTailFalseStopProfile` to `reporting.py` (false-stop rate,
  eligible counts, belief-at-stop).
- Changed `run_single_regime()` to return `tuple[RunResult, WorldState]`
  so post-hoc diagnostics can access ground-truth state.
- Created 5 new modules:
  - `run_bundle.py` — run-bundle data structure and persistence
  - `tables.py` — 7 canonical Parquet tables + 3 derived tables
  - `figures.py` — 9 PNG figures (7 executive-summary + 2 appendix)
  - `report_gen.py` — static HTML report and companion markdown
  - `bundle_validation.py` — structural validation of bundles
- Created `scripts/run_experiment.py` (experiment → run bundle pipeline).
- Terminology audit: fixed `governance_architecture.json` content,
  added `governance_archetype` to event_log.
- Updated `README.md` with three-level onboarding progression.
- Added `pyarrow` and `matplotlib` as base dependencies.

### Test status

963 tests passing (47 new tests across 5 new test files).
