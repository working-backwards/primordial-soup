# Primordial Soup implementation plan

## Summary

This plan describes how to implement the canonical Primordial Soup
simulation from the frozen design corpus. The system is a discrete-time
Monte Carlo study comparing governance regimes over a fixed portfolio of
initiatives under uncertainty. The simulator is neutral, deterministic
given a seed, and produces analyst-agnostic outputs.

The design corpus is authoritative. This plan translates it into a
buildable module structure, implementation sequence, and testing
strategy. It does not redesign the study.

**Naming:** Use descriptive Python names in code per
`docs/study/naming_conventions.md`. Reserve compact symbols (e.g. `c_t`, `q`,
`sigma_eff`) for equations and design-doc references; in Python use
`quality_belief_t`, `latent_quality`, `effective_signal_st_dev_t`, and the
mapping table in that doc. Do not invent a third naming dialect.

---

## Package and module structure

```
src/primordial_soup/
├── __init__.py            # Package docstring and public surface
├── config.py              # SimulationConfiguration and all sub-configs
│                          #   TimeConfig, WorkforceConfig, ModelConfig,
│                          #   GovernanceConfig, ReportingConfig,
│                          #   ResolvedInitiativeConfig
│                          #   Validation logic lives here.
├── types.py               # Enums (LifecycleState), value channel
│                          #   dataclasses, shared type aliases
├── state.py               # WorldState, InitiativeState, TeamState,
│                          #   CapabilityState, MetricsState
├── observation.py         # GovernanceObservation, InitiativeObservation,
│                          #   TeamObservation — the observation boundary
├── actions.py             # ContinueStop, SetExecAttention, AssignTeam,
│                          #   GovernanceActions — the action schema
├── noise.py               # Per-initiative CRN streams (quality_signal_rng,
│                          #   exec_signal_rng), seeded from world_seed +
│                          #   initiative_id via SHA-256
├── pool.py                # Initiative generator: resolves
│                          #   InitiativeGeneratorConfig into a concrete
│                          #   list of ResolvedInitiativeConfig using
│                          #   world_seed. Also instantiates per-initiative
│                          #   RNG streams.
├── learning.py            # Attention curve g(a), effective noise σ_eff,
│                          #   strategic signal y_t, execution signal z_t,
│                          #   belief updates for quality_belief_t and execution_belief_t,
│                          #   learning efficiency L(d), ramp multiplier
├── tick.py                # step_world (production, observation, belief
│                          #   update, review-state update, completion
│                          #   detection, capability update, residual pass)
│                          #   and apply_actions (ContinueStop, AssignTeam,
│                          #   SetExecAttention with feasibility check).
│                          #   Both are pure functions.
├── governance.py          # Decision primitives: confidence_decline_stop,
│                          #   tam_adequacy_stop, stagnation_stop,
│                          #   execution_overrun_stop, attention allocation
│                          #   helpers. Pure functions over observations.
├── policy.py              # GovernancePolicy protocol and archetype
│                          #   implementations (Balanced, Aggressive
│                          #   Stop-Loss, Patient Moonshot). Compose
│                          #   primitives from governance.py.
├── events.py              # MajorWinEvent, StopEvent, CompletionEvent,
│                          #   ReassignmentEvent, AttentionViolationEvent
├── reporting.py           # PerInitiativeTickRecord, PortfolioTickRecord,
│                          #   RunSummary, RunManifest — output schemas
├── runner.py              # Tick loop orchestration, single-regime runner,
│                          #   batch runner, manifest construction, I/O.
│                          #   Only impure code in the package.
│                          #   Returns tuple[RunResult, WorldState].
├── evaluator.py           # Optimizer-facing evaluation interface
├── campaign.py            # Experiment design and LHS sweep generation
├── presets.py             # Environment families and archetype factories
├── workbench.py           # YAML authoring layer for run_design.py
├── diagnostics.py         # Ground-truth diagnostic metrics (post-hoc):
│                          #   false-stop rate, survival curves,
│                          #   belief-at-stop, attention-conditioned
│                          #   false negatives, stop hazard
├── run_bundle.py          # Run-bundle creation and orchestration:
│                          #   directory layout, manifest, config/provenance
│                          #   serialization, telemetry
├── tables.py              # Canonical and derived Parquet table generation:
│                          #   7 canonical + 3 derived tables
├── figures.py             # Matplotlib figure generation (9 PNG figures)
├── report_gen.py          # HTML and markdown report generation
└── bundle_validation.py   # Run-bundle validation (manifest, tables,
                           #   report, telemetry)

tests/
├── __init__.py
├── conftest.py            # Shared fixtures and factory functions
├── test_config.py         # Config construction and validation
├── test_types.py          # Enum and value channel dataclass tests
├── test_state.py          # State construction, frozen immutability
├── test_noise.py          # CRN determinism, per-initiative isolation
├── test_pool.py           # Generator determinism, attribute ranges,
│                          #   invariant enforcement
├── test_learning.py       # g(a) shape, σ_eff, belief convergence,
│                          #   dependency effects, ramp multiplier
├── test_tick.py           # Tick-level state transitions, completion
│                          #   detection, residual activation, capability
│                          #   update, value realization ordering
├── test_observation.py    # Observation boundary: q never leaks
├── test_governance.py     # Decision primitives at boundary conditions
├── test_policy.py         # Archetype behavior, valid action vectors
├── test_events.py         # Event emission correctness
├── test_reporting.py      # Output schema correctness
├── test_runner.py         # End-to-end determinism, multi-regime
│                          #   comparison on shared seeds
├── test_presets.py        # Preset factories and archetype comparison
├── test_frontier.py       # Dynamic opportunity frontier
├── test_diagnostics.py    # Ground-truth diagnostic metrics
├── test_run_bundle.py     # Run-bundle scaffolding and manifest
├── test_tables.py         # Parquet table generation
├── test_figures.py        # Figure generation smoke tests
├── test_report_gen.py     # HTML/markdown report generation
└── test_bundle_validation.py  # Bundle validation rules
```

---

## Implementation phases

### Phase 0: Repo plumbing (current)
- `pyproject.toml` with ruff, mypy, pytest config
- `.pre-commit-config.yaml`
- Source and test directory scaffolding
- Updated `CLAUDE.md` with project context
- This implementation plan
- Deprecate `docs/engineering.md`

### Phase 1: Domain types and configuration
- `types.py` — LifecycleState enum, value channel dataclasses
- `config.py` — all configuration dataclasses from `interfaces.md`
- `validation.py` — all validation rules from `interfaces.md`
- `state.py` — WorldState, InitiativeState, TeamState, CapabilityState
- `observation.py` — GovernanceObservation, InitiativeObservation
- `actions.py` — action schema dataclasses
- `events.py` — event payload dataclasses
- Tests for construction, immutability, validation

### Phase 2: RNG and initiative pool
- `noise.py` — per-initiative CRN stream construction using MRG32k3a
  (L'Ecuyer's combined multiple recursive generator). Uses native
  stream/substream partitioning for CRN discipline: world_seed
  determines the generator state, each initiative gets a dedicated
  pair of substreams (quality signal, execution signal) indexed by
  initiative_id. Pool generator gets its own substream. All RNG
  construction is isolated behind this single module.
- `pool.py` — initiative generator with a flexible
  `InitiativeGeneratorConfig` schema that accepts per-type distribution
  specs and ranges. Ships with canonical defaults matching the sourcing
  doc's attribute ranges. All resolved parameters recorded in manifest.
- Tests for determinism, CRN isolation, generator invariants

### Phase 3: Learning and signal model
- `learning.py` — g(a), σ_eff, L(d), ramp multiplier, belief updates
- Tests for attention curve shape, convergence, boundary behavior

### Phase 4: Tick engine
- `tick.py` — step_world and apply_actions, full tick ordering
- Tests for each tick substep, completion detection, residual
  activation, capability update, value realization ordering

### Phase 5: Governance and policy
- `governance.py` — decision primitives
- `policy.py` — GovernancePolicy protocol, Balanced archetype
- Tests for each stop rule at boundaries, valid action vectors

### Phase 6: Reporting and runner — DONE
- `reporting.py` — output schemas and aggregation functions:
  - PerInitiativeTickRecord, PortfolioTickRecord frozen dataclasses
  - ValueByChannel, MajorWinProfile, BeliefAccuracy, IdleCapacityProfile,
    ExplorationCostProfile, ReassignmentProfile frozen dataclasses
  - RunManifest frozen dataclass (provenance for exact replay)
  - RunResult frozen dataclass (complete run output)
  - RunCollector mutable accumulator for tick loop
  - Aggregation functions: compute_belief_accuracy, compute_value_by_channel,
    compute_major_win_profile, compute_idle_capacity_profile,
    compute_exploration_cost_profile, compute_terminal_aggregate_residual_rate,
    assemble_run_result
- `runner.py` — tick loop orchestration (only impure module):
  - run_single_regime: validate → resolve generator → seed RNGs → init state →
    tick loop → assemble RunResult
  - run_batch: sequential wrapper, no shared mutable state
  - _build_governance_observation: observation boundary enforced, derived fields
  - _detect_reassignments: governance_stop, completion, idle_reassignment triggers
  - _initialize_world_state: UNASSIGNED, idle, C_t=1.0, tick=0
- GovernancePolicy Protocol updated with belief_histories/team_sizes kwargs
- 63 new tests (27 reporting + 36 runner), 430 total passing, lint/format/mypy clean

### Phase 7: Experiment specification and campaign generation

The core simulator is complete. Phase 7 builds the full experiment-
definition layer: the machinery for constructing experiments,
campaigns, and sweeps. The baseline preset work is the first execution
milestone, not the full scope.

#### Framing: three experiment-design levels

The study has three distinct levels of experimental control. Each uses
a different generation method because each plays a different role.

**Level 1 — Initiative instances.** These are stochastic draws from
the initiative generator under a fixed environment configuration.
Each `world_seed` produces one deterministic pool from the configured
`InitiativeGeneratorConfig`. Do not use LHS here. The generator
already handles per-type distributions, attribute ranges, and pool
composition. Multiple worlds are sampled by varying `world_seed`, not
by varying initiative attributes directly.

**Level 2 — Governance parameters.** These define the governance
design space. Named archetypes (Balanced, Aggressive Stop-Loss,
Patient Moonshot) are fixed anchor points. The broader governance
sweep uses LHS over the continuous `GovernanceConfig` parameters
(`confidence_decline_threshold`, `tam_threshold_ratio`,
`base_tam_patience_window`, `stagnation_window_staffed_ticks`,
`stagnation_epsilon`, `attention_min`, `attention_max`,
`exec_overrun_threshold`). Per `experiments.md`, sample
`attention_min` plus a nonnegative span, derive `attention_max`,
to avoid infeasible draws. The three named archetypes are fixed
supplemental design points, not LHS draws.

If portfolio-risk controls are studied, they are a **targeted
follow-on sweep family**, not folded into the main LHS (per
`experiments.md` §Parameter sweep design). This keeps the canonical
baseline sweep interpretable while allowing focused study of
portfolio-risk posture separately.

**Level 3 — Environment / generator configurations.** These define
different opportunity environments (tail-heaviness of the `q`
distribution, dependency distribution, initiative-type mix, ramp
period, attention-to-signal curve parameters, `reference_ceiling`).
These are a separate experimental dimension from governance. Do not
fold environment variation into the initial baseline campaign. Later,
if needed, use a separate design method (LHS or hand-designed
scenario family) for environment configuration sweeps.

A single run therefore gets:
- one governance policy (from Level 2)
- one `world_seed`
- one resolved initiative pool (Level 1, drawn from the Level 3
  environment configuration)

The canonical governance study holds the environment configuration
fixed and varies governance regime × `world_seed`. The environmental
study later varies generator/environment parameters as a separate
experimental dimension.

#### Internal sequencing

**Milestone 1: Baseline preset layer (first execution milestone)**

Do this work first. No LHS, no campaign abstractions yet.

**Step 7a — Baseline environment configuration.**
Build a shared baseline `InitiativeGeneratorConfig` with
`InitiativeTypeSpec` entries for all four canonical initiative types
(flywheel, right-tail, enabler, quick-win) using the attribute ranges
from `sourcing_and_generation.md`. Use the initiative generator path,
not hand-crafted `ResolvedInitiativeConfig` tuples.

Pool sizing: deliberately oversize. The canonical sweep must never
exhaust the pool under any governance regime within the simulation
horizon. Pool exhaustion is a configuration error, not a meaningful
managerial result — companies do not conclude "we have literally no
work worth doing, so everyone waits." Err on the side of too many
initiatives. Pilot the most aggressive archetype first and verify no
exhaustion.

Shared environment parameters (`TimeConfig`, `WorkforceConfig`,
`ModelConfig`) defined once and reused across all archetypes. The
`exec_attention_budget` should be set conservatively high so that
attention-feasibility violations are negligible (per `experiments.md`
§Canonical experiment posture on budget binding).

**Step 7b — Balanced preset factory.**
Build `make_balanced_config(world_seed) → SimulationConfiguration`
that returns a complete configuration using the baseline environment
from 7a plus a `GovernanceConfig` with moderate stop thresholds and
even attention distribution. This is the canonical reference baseline.

The `GovernanceConfig` must set **all** portfolio-risk parameters
explicitly, even when the baseline value is `None`:
- `low_quality_belief_threshold = None`
- `max_low_quality_belief_labor_share = None`
- `max_single_initiative_labor_share = None`

This makes the baseline complete and future changes easier to compare.

Pair the config with `BalancedPolicy()` as the policy object.

**Step 7c — Balanced smoke test (first execution milestone).**
Run one end-to-end `run_single_regime()` with the Balanced preset.
Inspect the `RunResult` manually for sanity:

- Non-zero total realized value across channels
- At least some initiatives reach `completed` lifecycle state
- At least some initiatives are stopped (governance is exercising
  stop rules, not just holding everything)
- Belief trajectories show convergence (`quality_belief_t` moves
  toward `latent_quality` over staffed ticks)
- Portfolio capability scalar grows if enablers complete
- Residual streams activate for completed flywheels/quick-wins
- No pool exhaustion (`pool_exhaustion_tick` is None or very late)
- No attention-feasibility violations (or very few)
- Determinism: same seed produces identical `RunResult`

Write this as a proper test in `tests/test_presets.py` (or
`tests/test_integration.py`) that asserts these properties.

**Step 7d — Aggressive Stop-Loss and Patient Moonshot presets.**
Add `make_aggressive_stop_loss_config(world_seed)` and
`make_patient_moonshot_config(world_seed)` against the **same**
baseline environment from 7a. Only the `GovernanceConfig` and
`policy_id` differ.

- Aggressive: lower `confidence_decline_threshold`, tighter
  `exec_overrun_threshold`, shorter patience windows
- Patient Moonshot: `confidence_decline_threshold` disabled (None),
  longer patience windows, higher exec_overrun tolerance

Again, all portfolio-risk parameters set explicitly (even if None).

**Step 7e — Three-archetype comparison test.**
Run all three archetypes against shared `world_seed` values. Verify:
- Identical initiative pools across regimes (CRN discipline)
- Different terminal outcomes (the governance differences are
  producing measurable behavioral differences)
- Each archetype's stop-rule profile matches its intended posture
  (Aggressive stops more and earlier, Patient holds longer)

**Milestone 2: Campaign abstractions**

After the baseline preset family is working and trusted (Milestone 1
COMPLETE as of 2026-03-12).

**Step 7f — Campaign specification types.**
Define frozen dataclasses for experiment and campaign construction:

- `EnvironmentSpec` — encapsulates a complete environment
  configuration: `TimeConfig`, `WorkforceConfig`, `ModelConfig`, and
  `InitiativeGeneratorConfig`. Represents one Level 3 environment.
  The baseline environment from 7a is the first `EnvironmentSpec`.
  Add a factory `make_baseline_environment_spec()` in `presets.py`
  that wraps the existing baseline component factories.

- `GovernanceSweepSpec` — describes how to generate governance
  configurations for a campaign. Contains: the fixed archetype
  anchor points (always included), LHS parameters for the continuous
  sweep (dimensionality, sample count, parameter bounds), and
  optional targeted follow-on sweep families (e.g. portfolio-risk
  controls). Per `experiments.md`: minimum LHS sample size is
  10 × dimensionality (8 params → 80 minimum, 200 recommended).

  The 8 LHS dimensions (all continuous or integer):
  1. `confidence_decline_threshold` (float or None → sample float,
     with probability of None as a discrete option OR always float
     within bounds)
  2. `tam_threshold_ratio` (float, bounds e.g. [0.3, 0.9])
  3. `base_tam_patience_window` (int, bounds e.g. [3, 30])
  4. `stagnation_window_staffed_ticks` (int, bounds e.g. [5, 40])
  5. `stagnation_epsilon` (float, bounds e.g. [0.005, 0.05])
  6. `attention_min` (float, bounds e.g. [0.05, 0.4])
  7. `attention_span` (float >= 0, bounds e.g. [0.0, 0.6]) →
     `attention_max = attention_min + attention_span` (capped at 1.0)
  8. `exec_overrun_threshold` (float or None → sample float)

  `confidence_decline_threshold = None` is a structural choice (disable
  the rule entirely). If the sweep should include disabled-confidence
  as a design point, either: (a) treat it as a separate binary
  dimension not in the LHS, or (b) set the LHS lower bound to a value
  below any practical belief (e.g. 0.01) so it is effectively disabled.
  Same consideration for `exec_overrun_threshold`. Decision needed
  before implementing Step 7g.

- `CampaignSpec` — combines one `EnvironmentSpec` with one
  `GovernanceSweepSpec`, a set of `world_seed` values, and metadata.
  Represents a complete experiment definition: every
  (`governance_config`, `world_seed`) pair is one run. Total runs =
  `len(governance_configs) × len(world_seeds)`.

These types live in the experiment layer, outside the core simulator.
The simulator only sees `SimulationConfiguration` and
`GovernancePolicy`. Campaign types produce those as output.

**Step 7g — Governance sweep generator.**
Build the LHS generator for governance parameter sweeps:

- Input: `GovernanceSweepSpec` (parameter bounds, sample count)
- Output: a list of `GovernanceConfig` instances

The generator samples `attention_min` and a nonnegative
`attention_span`, derives `attention_max = attention_min +
attention_span`, to guarantee feasibility by construction (per
`experiments.md`). The three named archetype `GovernanceConfig`
values are appended as fixed supplemental points, not drawn from
the LHS.

Portfolio-risk control parameters are **not** included in the
baseline LHS. They are available for targeted follow-on sweeps only.

**RNG for LHS — mrg32k3a consideration (see open issue 7):**

LHS is *design-time* randomness (generating experimental design
points), not *simulation-time* stochasticity. SimOpt controls
replication (world_seed → per-run RNG streams), not experimental
design. Using numpy for LHS is defensible because:
  - LHS output is a fixed set of GovernanceConfig recorded in manifest
  - The LHS RNG does not affect within-run reproducibility
  - SimOpt's `replicate(rng_list)` provides streams for a single run,
    not for design-of-experiments

However, if we want the LHS design itself reproducible with a
`design_seed` (for audit/provenance), and if we want to keep the
option of having SimOpt also control the DOE layer, then using
mrg32k3a for LHS may be forward-compatible.

**Recommended approach:** Use numpy for LHS, seeded with a
`design_seed` parameter. Document the design-time vs simulation-time
RNG distinction. If SimOpt integration later requires mrg32k3a LHS,
the swap is localized.

LHS implementation: implement directly with numpy (no scipy
dependency). The algorithm is straightforward: for N samples across
D dimensions, divide each dimension's [0,1] range into N equal strata,
sample uniformly within each stratum, then randomly permute columns.
Scale from [0,1] to parameter bounds after sampling.

**Step 7h — Experiment manifest writer.**
Serialize `RunManifest` (and optionally `CampaignSpec`) to JSON on
disk. This is required for provenance, exact replay, and sweep
analysis. The manifest must record the full `GovernanceConfig`
parameter values, the resolved initiative list, the environment
configuration, and the engine version.

**Step 7i — Batch execution hooks.**
Extend `runner.run_batch()` or add campaign-level orchestration that:

- Takes a `CampaignSpec` and produces all runs
- Supports sequential execution (parallel is Phase 8)
- Records per-run manifests
- Produces a campaign-level output bundle

#### Deliverables

- `src/primordial_soup/presets.py` — (already done) baseline preset
  factories; add `make_baseline_environment_spec()` wrapper
- `src/primordial_soup/campaign.py` — `EnvironmentSpec`,
  `GovernanceSweepSpec`, `CampaignSpec`, LHS governance generator,
  campaign runner
- `src/primordial_soup/manifest.py` — JSON serialization for
  `RunManifest` and `CampaignSpec`
- `tests/test_presets.py` — (already done) smoke tests and
  three-archetype comparison
- `tests/test_campaign.py` — sweep generation, campaign spec
  construction, manifest round-trip
- All portfolio-risk parameters explicitly set in every preset
  (already done in Milestone 1)

#### Scope constraints

- Do not move SimOpt into Phase 7
- Do not add environment sweeps (Level 3 variation) yet
- Do not start with LHS-generated governance policies before the
  named archetype baseline runs are working (Milestone 1 DONE)
- Do not treat pool exhaustion as a normal outcome; it is a
  configuration error
- Do not fold portfolio-risk controls into the main LHS; they are
  a targeted follow-on sweep family
- Do not add scipy — implement LHS with numpy alone

### Phase 8: Execution infrastructure and SimOpt (future)
- Parallel batch execution — distribute campaign runs across workers
- SimOpt wrapper — connect to SimOpt optimization framework
- Portfolio-risk control sweep — targeted follow-up experiment
  family (per `experiments.md` §Parameter sweep design)
- Environment configuration sweeps (Level 3 variation)

### Phase 9: Analysis substrate (deferred)
- Deterministic post-processing and campaign summaries
- Summary table generation
- Not required for initial simulator validation

---

## Core invariants to preserve

1. **Type independence.** Engine branches on attributes, never labels.
2. **Observation boundary.** Latent quality (q) and `true_duration_ticks` hidden from
   policy.
3. **CRN discipline.** Per-initiative streams seeded from
   `sha256(world_seed, initiative_id, tag)`. Two regimes sharing a
   world_seed get identical observations per initiative regardless of
   which initiatives are active.
4. **Action timing.** Decisions at end-of-tick T take effect at
   start-of-tick T+1.
5. **Completion-gated value.** No streaming value. Lump, residual, and
   capability all activate at the completion transition.
6. **Stable iteration.** All iteration over initiatives and teams uses
   sorted `id` order. Ties broken by `id`.
7. **Frozen config.** SimulationConfiguration is immutable and opaque to
   the engine.
8. **Policy purity.** No private mutable state across ticks.

---

## Reproducibility and RNG strategy

The design corpus specifies (architecture invariant 9) that each
initiative must have two dedicated random streams for CRN discipline.

### MRG32k3a from the start

The implementation uses **MRG32k3a** (L'Ecuyer's combined multiple
recursive generator) directly, rather than deferring to a future
migration. Rationale: the simulator is likely to transition from
evaluation to optimization (SimOpt search), and MRG32k3a is SimOpt's
native RNG. Using it from the start eliminates a migration that would
invalidate all prior reproducibility fixtures.

### Stream/substream mapping

MRG32k3a provides 2^127 independent streams, each with 2^76
substreams of 2^51 values. The mapping:

- **world_seed** → deterministic initial state for the MRG32k3a
  generator (derived via SHA-256 to produce the six 64-bit seed
  components MRG32k3a requires).
- **Per-initiative streams**: each initiative gets a dedicated pair
  of substreams indexed by `initiative_id`:
  - `substream(2 * initiative_index)` → quality signal draws
  - `substream(2 * initiative_index + 1)` → execution signal draws
- **Pool generator**: gets its own substream (before all initiative
  substreams) for attribute draws during generation.

This replaces the SHA-256-per-stream derivation scheme described in
`architecture.md`. The CRN invariant is preserved: two runs sharing
the same `world_seed` receive identical observation noise for each
initiative regardless of governance regime, because each initiative's
substream is independent of which other initiatives are active.

### Implementation boundary

All MRG32k3a stream construction, substream indexing, and random
variate generation is isolated in `noise.py`. The engine and policy
code never import or reference MRG32k3a directly — they receive
opaque RNG objects from `noise.py`.

The `noise.py` module exposes:
- A function to create per-initiative RNG stream pairs
- A function to create the pool generator RNG
- Variate-drawing helpers (normal, uniform, beta, lognormal) that
  accept the opaque RNG object

### Dependency

The `mrg32k3a` package (PyPI) provides a standalone Python
implementation of MRG32k3a with stream/substream support. This is
maintained by the SimOpt project team. Add to `pyproject.toml` as
a runtime dependency.

---

## Simulator / policy / analysis / orchestration boundaries

```
┌─────────────────────────────────────────────────────┐
│  Runner (runner.py) — impure orchestration shell    │
│  - resolves config, seeds RNG, runs tick loop       │
│  - records manifest and outputs                     │
│  - batch execution across regimes                   │
│                                                     │
│  ┌───────────────────────────────────────────────┐  │
│  │  Engine (tick.py) — pure state transitions    │  │
│  │  - step_world: production → observation →     │  │
│  │    belief update → review state → completion  │  │
│  │    → capability → residual → outputs          │  │
│  │  - apply_actions: stop → assign → attention   │  │
│  │  - owns all mutable WorldState                │  │
│  │                                               │  │
│  │  ┌─────────────────────────────────────────┐  │  │
│  │  │  Policy (policy.py) — pure function     │  │  │
│  │  │  GovernanceObservation + GovernanceConfig│  │  │
│  │  │    → GovernanceActions                  │  │  │
│  │  │  No access to WorldState or latent q    │  │  │
│  │  └─────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────┘  │
│                                                     │
│  ┌───────────────────────────────────────────────┐  │
│  │  Reporting (reporting.py) — output schemas    │  │
│  │  - per-tick records, event logs, summaries    │  │
│  └───────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│  Analysis (analysis.py) — deterministic post-proc   │
│  - reads raw outputs, produces derived artifacts    │
│  - never mutates run artifacts                      │
│  - supports human, AI, and hybrid workflows         │
└─────────────────────────────────────────────────────┘
```

---

## Testing strategy

- **Unit tests per module.** Each module gets a corresponding test file.
- **Pure function tests.** belief updates, g(a), σ_eff, L(d), ramp
  multiplier, stop-rule predicates — all tested with known inputs and
  expected outputs.
- **Determinism tests.** Same seed produces identical results. Two runs
  differing only in governance regime produce identical per-initiative
  noise draws.
- **Observation boundary tests.** Verify latent_quality (q) and `true_duration_ticks`
  never appear in `GovernanceObservation` or `InitiativeObservation`.
- **Edge case tests.** Empty pool, all initiatives stopped, ramp on
  first tick, zero pivots remaining, horizon reached with active
  initiatives, completion on final tick.
- **Integration tests.** Full tick-loop runs with known seeds,
  verifying terminal state against expected values.
- **Regression fixtures.** Pin a known seed and assert exact values
  for a short run. Use these to catch accidental semantic changes.

---

## SimOpt compatibility

The implementation preserves the option to later wrap the simulator as
a SimOpt problem class by:

1. **Explicit factors.** `SimulationConfiguration` is a declarative
   frozen object containing all simulation parameters. It is trivially
   serializable. Maps directly to SimOpt "model factors."
2. **Reproducible replications.** Each `world_seed` produces an
   independent replication. The runner exposes a single-run function
   `run(config, seed) → RunSummary` that SimOpt can call once per
   replication.
3. **No hidden global state.** All mutable state is scoped to a single
   run via `WorldState`.
4. **Clean objective extraction.** `RunSummary` exposes all primary
   outputs as named fields. A SimOpt wrapper would extract objectives
   and constraints from this object. See
   `docs/implementation/simopt_notes.md` for candidate mappings.
5. **Solver independence.** The simulator has no knowledge of search
   or optimization logic.
6. **Native MRG32k3a.** The simulator uses MRG32k3a from the start,
   which is SimOpt's native RNG. No migration needed when wrapping
   as a SimOpt problem class.
7. **Replication control compatibility.** SimOpt controls replication
   count externally and passes seeds. The `world_seed` model is
   compatible — SimOpt calls the simulator once per replication with
   its own seed. The runner does not assume it controls the outer
   replication loop.

---

## Risks and unresolved questions

See `docs/implementation/open_implementation_issues.md` for tracked
items. All three initial questions have been resolved:

1. **RNG seed width** — resolved: design updated to 64-bit seeds.
2. **Stale legacy engineering spec** — resolved: moved to deprecated.
3. **`required_team_size` default** — resolved: design updated to
   default 1.

Remaining open items (non-blocking):
- Issue 4: `belief_history` sizing — implemented as tuple trimmed to
  `GovernanceConfig.stagnation_window_staffed_ticks` (resolved in code).
- Issue 5: `g_max` None handling — resolved and closed.
- Issue 6: `dependency_noise_exponent` config comment misnomer — deferred
  cosmetic fix.

---

## What to build first

1. Domain types and configuration (Phase 1)
2. RNG and initiative pool (Phase 2)
3. Learning model (Phase 3)

These are the foundations everything else depends on. They can be
tested in isolation before the tick engine exists.

## What to explicitly NOT build in the first pass (Phases 1–6)

- Analysis and post-processing (`analysis.py`)
- Parameter sweep harness (→ Phase 7, Milestone 2)
- Parallel execution (→ Phase 8)
- SimOpt integration wrapper (→ Phase 8)
- AI-assisted analysis tooling
- Visualization or dashboards
- Multiple environmental configuration generators (→ Phase 8)
- Mid-run sourcing (explicitly out of canonical scope)
