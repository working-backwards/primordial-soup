# Primordial Soup — Project Rules

## Project Purpose

Primordial Soup is a discrete-time Monte Carlo simulation study of how
governance regimes affect long-term organizational value creation. The
simulator models a portfolio of initiatives with latent quality, noisy
strategic and execution signals, multiple value-creation mechanisms
(completion lump, residual, major-win discovery, capability), and
configurable governance policies that allocate attention, assign teams,
and decide when to stop or continue initiatives.

The central research question is: under what governance structures do
organizations discover, invest in, and sustain the mix of compounding
mechanisms, speculative opportunities, and capability-building work
that produces long-run value?

## Authority Structure

The design corpus is the current specification for the simulator.
It is organized in three layers:

1. **Core principles.** `docs/design/canonical_core.md` defines the
   study's identity: abstractions, structural principles, and scope
   boundaries. Changes to core principles require explicit design
   decisions with documented rationale.
2. **Conceptual authority.** `docs/study_overview.md` is authoritative
   about the phenomena in scope, practitioner-facing interpretation,
   and deliberate simplifying assumptions.
3. **Technical authority.** `docs/design/initiative_model.md`,
   `core_simulator.md`, `governance.md`, and `interfaces.md` are
   authoritative about state variables, equations, tick ordering,
   observation boundaries, and action semantics.

Supporting documents (`design_decisions.md`,
`analysis_and_experimentation.md`, `implementation_guidelines.md`,
`engineering_standards.md`) record rationale and implementation
guidance but do not override the technical specs.

If any implementation file conflicts with the design corpus, the
design corpus wins. See `docs/design/index.md` for the full reading
order.

## Design Revision Process

The design corpus is a living specification. It can be revised when
calibration evidence, expert feedback, or implementation experience
reveals that a modeling choice should change. Revisions follow this
process:

1. Identify what is changing and why (calibration finding, expert
   feedback, simplification, etc.).
2. Check whether the change affects a structural principle in
   `canonical_core.md`. If so, evaluate whether the study's ability
   to attribute outcome differences to governance is preserved.
3. Update the authoritative design doc(s) first, then the code.
4. Document the rationale in a commit message or design decision
   record so future readers understand why the change was made.

Do not silently invent semantics. If a design doc is ambiguous,
resolve the ambiguity explicitly in the design doc before coding.

## Structural Properties

The structural principles in `docs/design/canonical_core.md`
(type-independence, observation boundary, action timing, belief
ownership, deterministic resolution, deterministic pool, portfolio
controls governance-side) define the experimental methodology. They
exist because without them, the cross-regime comparison does not
work. They can be revised, but doing so requires evaluating whether
the study's controlled-comparison methodology is preserved.

Additional implementation-level structural properties:

1. **Per-initiative RNG streams (CRN).** Each initiative has two
   dedicated MRG32k3a substreams (quality signal, execution signal)
   indexed by `initiative_id`. A single global stream is prohibited.
   All RNG construction is isolated in `noise.py`.
2. **Deterministic iteration.** All iteration uses stable `id`
   ordering. Ties broken by `id`. Reproducibility must not depend
   on dict insertion order.
3. **No team splitting.** A team is atomic and assigned to at most
   one initiative at a time.
4. **Simulator neutrality.** The simulator describes what happened.
   It does not embed evaluative judgment. No normative labels in
   state, events, or output fields.
5. **AI boundary.** AI/prompting may be used for analysis support
   and development assistance. AI must not define simulator
   behavior. Simulator behavior must remain grounded in the design
   corpus and verified through code and tests.

## Session Workflow

- At session start, read `docs/implementation/open_implementation_issues.md`
  to pick up current blockers and deferred work. Do NOT rely on
  conversation continuation summaries.
- Do NOT pre-read files speculatively. Read only the specific files
  needed for the current task, on demand.
- Prefer fresh sessions over conversation continuations to avoid
  context window exhaustion.

## Persistent State

Implementation state lives in tracked repo files, not chat context:

- `docs/implementation/open_implementation_issues.md` — blockers and
  deferred issues
- `docs/implementation/post_expert_review_plan.md` — post-review roadmap
- `docs/implementation/calibration_plan.md` — calibration methodology
- `docs/implementation/reporting_package_specification.md` — run-bundle
  structure, table schemas, and report requirements
- `CLAUDE.md` (this file) — project rules and coding conventions

## Handling Ambiguities and Design Changes

1. Check whether the design corpus already resolves it.
2. If resolved, implement as specified.
3. If genuinely ambiguous, resolve it explicitly: update the
   design doc with the resolution, then implement. For small
   clarifications, fix the doc inline. For larger changes, follow
   the Design Revision Process above.
4. If calibration or expert feedback suggests a modeling choice
   should change, update the design doc first, then the code.
5. Record open questions in
   `docs/implementation/open_implementation_issues.md` or GitHub
   Issues when they cannot be resolved immediately.
6. Do not silently invent semantics.

---

## Values

**Simplicity.** Prefer the straightforward solution. Do not add
abstraction, indirection, or generality unless the current task
demands it. Three clear lines beat one clever one.

**Reliability.** Code should be correct first. Every pure function
should be testable in isolation with known inputs and expected outputs.
If something can fail, handle it explicitly — do not swallow errors.

**Readability.** Code is read far more often than it is written.
Optimize for the reader.

## Code Style

### Comments
- **Err on the side of over-commenting.** This is a research
  simulation with dense domain logic. A reader unfamiliar with the
  design corpus should be able to follow the code from comments
  alone.
- Comment both the *why* and the *what* when the *what* is not
  immediately obvious. Do not assume the reader knows the model.
- Every module gets a module-level docstring explaining its
  responsibility and where it fits in the system.
- Every public function gets a docstring describing its contract:
  what it accepts, what it returns, and any important constraints.
- Every non-trivial private/helper function gets a docstring.
- Use inline comments for:
  - Domain logic and formulas (reference the design doc section
    or equation, e.g. "per core_simulator.md step 5a").
  - Data flow: where values come from and where they go.
  - Non-obvious control flow: why a branch exists, what edge
    case it handles.
  - Units and ranges of numeric values when not obvious from
    the variable name.
- Block comments before logical sections of a function are
  encouraged to narrate the steps.

### Naming
- **Domain naming is enforced only here and in
  `docs/study/naming_conventions.md`.** We do not use linter naming
  rules (e.g. Ruff pep8-naming) or pre-commit hooks for domain naming.
- **Always favor readable names over short ones.** Clarity is
  more important than brevity. `initiative_confidence` over `ic`.
  `cumulative_labor_cost` over `clc`. `staffed_tick_count` over
  `stc`. If a name can be misread, it is too short.
- **Use descriptive names from the naming conventions**, not
  compact equation symbols. The canonical mapping is in
  `docs/study/naming_conventions.md`. Code uses descriptive names;
  equations in comments may use compact symbols as secondary
  references. Examples:
  - `quality_belief_t` not `c_t` or `belief_c_t`
  - `effective_signal_st_dev_t` not `sigma_eff`
  - `confidence_decline_threshold` not `theta_stop`
  - `stagnation_window_staffed_ticks` not `W_stag`
  - `mean` not `mu`; `st_dev` not `sigma`
- **Do not invent a third naming dialect.** Use either the compact
  equation symbol (in formulas/comments) or the descriptive name
  (in code/prose). Do not create hybrid names like `belief_c_t`.
- **When implementing an equation**, the code uses descriptive
  names and a comment references the compact form:
  ```python
  quality_belief_t  # c_t in the design docs
  ```
- Boolean variables and functions read as assertions:
  `is_review_tick`, `has_pivots_remaining`, not `review` or `pivots`.
- Loop variables and temporaries still get meaningful names:
  `for initiative in active_initiatives`, not `for i in inits`.

### Python Conventions
- Python 3.12+.
- Type hints on all function signatures and dataclass fields.
  Return types are not optional — always annotate them.
- `frozen=True` on all dataclasses. No mutable state objects.
- `from __future__ import annotations` at the top of every module.
- Use `tuple` for fixed-length or immutable sequences. Use `dict`
  only where O(1) keyed lookup is required in hot paths.
- No wildcard imports. Explicit imports only.
- One class per file is not required — group related types in the
  same module (e.g. all state dataclasses in `state.py`).
- Use `logging` (standard library), never `print`, for all runtime
  output. Each module gets its own logger via
  `logger = logging.getLogger(__name__)`. Log levels: `debug` for
  per-tick tracing, `info` for run-level milestones (seed started,
  regime complete), `warning` for recoverable issues, `error` for
  failures. The runner configures the root logger; no other module
  touches logging configuration.
- Raise specific exceptions with descriptive messages. Prefer
  `ValueError` for bad inputs, `TypeError` for wrong types, and
  custom exception classes only when callers need to catch a
  specific failure mode. Never use bare `except:` or
  `except Exception:` without re-raising or logging.
- Use `pathlib.Path` instead of string manipulation for file paths.
- Use context managers (`with`) for any resource that needs cleanup
  (files, locks, temporary directories).
- Tests use `pytest`. No unittest subclasses.

## Architecture Rules

### SimulationConfiguration is opaque and immutable
- `SimulationConfiguration` is a frozen data object. The simulator
  receives it and reads from it. It never modifies it.
- The simulator does not know or care how the configuration was
  produced — hand-crafted, loaded from a preset archetype, or
  generated by a parameter sweep. No field in the configuration
  references its origin.
- Configuration validation (e.g. threshold ordering, team mapping
  completeness) is the responsibility of the construction site, not
  the simulator. The simulator may assert preconditions defensively
  but must not reshape the configuration.
- Archetype presets, parameter sweeps, and other configuration
  generators live outside the core simulator and produce a valid
  `SimulationConfiguration` as output.

### Observation boundary
- Latent quality `q` must never appear in any data structure that
  governance logic can access (`GovernanceObservation`,
  `InitiativeObservation`).
- The `generation_tag` field is for initialization and post-hoc
  reporting. Governance policies must not branch on it.

### Governance primitives and policy composition
- `governance.py` exports decision primitives — pure functions that
  evaluate a single concern (should this initiative stop? is it
  stagnant? should this be reallocated?). They operate on
  `GovernanceObservation` and `InitiativeObservation`, never on
  `WorldState`.
- `policy.py` composes those primitives into governance archetypes.
  Archetypes choose strategies; they do not duplicate the mechanics
  of stop evaluation, reassignment, or ramp application.
- Shared execution lives in `governance.py`. Archetypes never
  reimplement edge-case handling that a primitive already covers.

### Purity
- `step_world` and `apply_action` (in `tick.py`) are pure: same
  inputs produce same outputs, no side effects, no random calls.
- All policy functions are pure.
- All stochasticity is pre-drawn from the world seed and passed in
  as data.
- The only impure code lives in `runner.py` (I/O, orchestration).

### Determinism
- All iteration over initiatives and teams uses stable `id` ordering.
- Ties in governance decisions are broken by `id`.
- Reproducibility must not depend on dict insertion order or Python
  runtime behavior.

## Testing
- Every module has a corresponding test file.
- Tests are small, focused, and named to describe the behavior
  being verified: `test_confidence_converges_toward_q`,
  not `test_learning_1`.
- Use deterministic seeds in tests. Never rely on statistical
  properties holding for a single draw — either use enough draws
  for the law of large numbers, or pin the seed and assert exact
  values.
- Edge cases get their own tests: zero pivots remaining, ramp on
  first tick, all initiatives stopped, empty pool.
- Use `pytest.raises` for expected exceptions. Use `pytest.approx`
  for floating-point comparisons — never bare `==` on floats.
- Keep test fixtures minimal. Prefer factory functions that build
  valid test objects with sensible defaults over large shared
  fixtures.

## Git and GitHub
- Commit messages: imperative mood, short first line (≤ 72 chars),
  blank line, then body if needed. Example: "Add confidence update
  with dependency-adjusted learning".
- One logical change per commit. Do not mix unrelated changes.
- Branch naming: `feature-<short-description>`,
  `fix-<short-description>`, `refactor-<short-description>`.
- Pull requests get a summary of *what* changed and *why*, plus a
  test plan. Keep PRs small enough to review in one sitting.
- Never commit secrets, credentials, or large binary files.
- Keep `.gitignore` up to date: include `__pycache__/`, `*.pyc`,
  `.pytest_cache/`, `dist/`, `*.egg-info/`, `.venv/`, and any
  output directories.

## Script Output Conventions
- All simulation output goes under `results/` (already in `.gitignore`).
  Do not create ad-hoc output directories outside `results/`.
- Use a descriptive, non-colliding subdirectory name. Include the
  script purpose, key parameters, and a UTC timestamp:
  `results/<purpose>_<params>_<YYYYMMDD_HHMMSS>/`.
- For full experiment bundles with provenance, use the `run_bundle.py`
  infrastructure which writes timestamped bundles under `runs/`.
- Console-only diagnostic scripts (no file output) are acceptable.
- Optional CSV/JSON export should default to `results/`, not `.` or
  a custom top-level directory.
- Never create output directories that require new `.gitignore` entries.
  `results/` and `runs/` already cover all simulation output.

## What Not To Do
- Do not add features, parameters, or abstractions beyond what the
  current design docs specify. If a change is needed, update the
  design docs first.
- Do not optimize for performance prematurely. Readable Python is
  sufficient. Vectorization is a clean later pass.
- Do not use third-party libraries beyond the standard library,
  `pytest`, `numpy`, and `mrg32k3a` unless there is a specific,
  justified need. NumPy is used for distribution sampling in
  `pool.py`. MRG32k3a is the native RNG for SimOpt compatibility
  (see `docs/implementation/simopt_notes.md`).
- Do not use `print` for runtime output. Use `logging`.
- Do not catch exceptions you cannot handle. Let them propagate.
- Do not commit commented-out code. Delete it; git has history.
