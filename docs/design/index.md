# Primordial Soup design corpus

This index describes the role of each design document in the corpus and how the documents should be read together.

## Authority and precedence

The corpus has a two-level authority structure.

1. `study_overview.md` is authoritative about the **phenomena the study is intended to model**, the practitioner-facing interpretation of those phenomena, and the deliberate simplifying assumptions that define the scope of the canonical study.
2. The technical specification documents — especially `initiative_model.md`, `core_simulator.md`, `governance.md`, and `interfaces.md` — are authoritative about **how those phenomena are operationalized** in the simulation: state variables, equations, lifecycle rules, tick ordering, observation boundaries, and action semantics.

This split is intentional. The overview defines **what** the study is about. The technical docs define **how** that study is implemented.

No document should contradict this hierarchy:

- `experiments.md`, `review_and_reporting.md`, and `research_questions.md` must remain consistent with both layers.
- If a practitioner-facing description and a technical mechanism appear to diverge, the correct repair is to make the technical docs faithfully implement the intended phenomenon while keeping the implementation precise and unambiguous.
- Human-facing initiative labels are explanatory and generator-side only; engine behavior must be defined in terms of resolved attributes and canonical mechanisms.

The corpus also uses a three-layer study framing that cuts across multiple
documents:

- **Environmental conditions**: the exogenous facts of a run.
- **Governance architecture**: pre-run structural choices such as labor
  decomposition and standing portfolio guardrails.
- **Operating policy**: tick-by-tick governance decisions.

`study_overview.md` is the main reader-facing entry point for this framing.
`governance.md`, `interfaces.md`, and `team_and_resources.md` make the same
distinction operational. `architecture.md` defines the corresponding engine and
runner boundary.

## Invariants (non-negotiables)

- Initiative types are only for initialization and reporting; they do not alter engine transitions.
- No team splitting: a team is an indivisible assignment unit.
- Governance acts on observables and beliefs only, not latent ground truth.
- Actions decided at end-of-tick take effect at the start of next tick (unless otherwise specified).
- The engine receives a *resolved initiatives list* (or a generator block that the runner resolves into a list before simulation).

## Documents

> **Note:** `study_overview.md` and `research_questions.md` live in `docs/` (the repository's docs root), not in `docs/design/`. All other documents listed here are in `docs/design/`.

- `canonical_core.md` — defines the irreducible identity of the study: abstractions, invariants, and scope boundaries. Top of the authority hierarchy.
- `study_overview.md` describes the scope, goals, intended audience, simplifying assumptions, and the practitioner-facing interpretation of the model.
- `design_decisions.md` records the major tradeoffs, rejected alternatives, and rationale behind the canonical design choices.
- `research_questions.md` enumerates the substantive questions the study is intended to answer.
- `initiative_model.md` defines immutable initiative attributes, mutable state, lifecycle transitions, and generator contracts.
- `core_simulator.md` defines the canonical tick loop, state updates, learning equations, value realization, and timing semantics.
- `governance.md` defines the governance action space, canonical stop rules, and how governance interacts with observable state.
- `interfaces.md` defines the schema-level contract between runner, engine, governance policy, and outputs.
- `team_and_resources.md` defines the realized workforce model consumed by the
  simulator and clarifies which labor concepts are environmental versus
  governance-architectural.
- `sourcing_and_generation.md` defines how initiative instances are generated or resolved before simulation start.
- `architecture.md` defines core invariants and high-level architectural decisions.
- `review_and_reporting.md` defines primary outputs, reporting schema, and event schemas.
- `analysis_and_experimentation.md` defines the post-run analysis layer, including deterministic summaries, AI-assisted exploratory interpretation, and targeted follow-up experiment design.
- `implementation_guidelines.md` defines architecture, invariants, reproducibility, interface discipline, and future SimOpt-compatibility guidance for implementation.
- `engineering_standards.md` defines project-wide coding and testing expectations for the implementation team.
- `experiments.md` defines named governance archetypes, parameter sweep design, and reproducibility requirements.
- `state_definition_and_markov_property.md` defines the compact Markov state of the simulator, distinguishes state from parameters and derived quantities, documents RNG stream positions, and reserves space for dynamic frontier state extensions.
- `dynamic_opportunity_frontier.md` specifies the dynamic frontier redesign: declining quality for flywheel/quick-win, prize-preserving refresh for right-tail, enabler frontier, engine boundary preservation, and the complete per-tick cycle with runner-side inter-tick materialization. **Requires review before implementation.**
- `diminishing_returns_deferral.md` — design note explaining why cross-initiative value saturation is deferred and the conditions for revisiting.
- `future_directions.md` — documents potential future extensions beyond the current study scope.
- `calibration_note.md` — empirical calibration evidence and parameter grounding for the initiative generator and environment families; preserves the evidence chain from external research to generator parameters.
- `generator_validity_memo.md` — calibration evidence and validation reasoning for the initiative generator parameters.

## Reading order

Recommended reading order for implementation or review:

1. `canonical_core.md` — read first; defines the study identity, invariants, and scope boundaries that all other documents must respect
2. `study_overview.md`
3. `design_decisions.md`
4. `research_questions.md`
5. `initiative_model.md`
6. `core_simulator.md`
7. `governance.md`
8. `interfaces.md`
9. `review_and_reporting.md`
10. `analysis_and_experimentation.md`
11. `implementation_guidelines.md`
12. `state_definition_and_markov_property.md`
13. remaining documents as needed

The intent of this reading order is to move from:

- study purpose and scope,
- to major design tradeoffs and rationale,
- to formalized research questions,
- to canonical mechanics and interfaces,
- to reporting, analysis, and implementation discipline.
