# Implementation guidelines

## Role of this document


### Academic
This document defines the implementation-level rules that protect the integrity
of the Primordial Soup study.

It is not a coding-style guide. It is not a substitute for the technical design
documents. Its purpose is to make the canonical implementation:

- faithful to the design corpus,
- reproducible and auditable,
- easier to test,
- easier to analyze downstream,
- and easier to adapt later to optimization-oriented frameworks such as SimOpt.

This document is complementary to `architecture.md`, not a replacement for it.
`architecture.md` remains part of the technical design authority and defines the
top-level technical contract, execution model, and non-negotiable architectural
invariants. This document translates that authority structure into
implementation-facing guidance for engineers, with emphasis on preserving model
integrity, reproducibility, and future compatibility.

This document is intentionally stricter about invariants than about internal code
organization. Teams should have agency over implementation choices that do not
violate the rules below.

---


### Business
## 1. Preserve the authority structure


### Academic
The implementation must respect the corpus authority structure:

- `study_overview.md` is authoritative about the modeled phenomena and scope.
- the technical docs are authoritative about mechanics, schemas, timing, and
  interfaces.
- `design_decisions.md` records rationale, not alternate mechanics.

If a coding convenience conflicts with the design corpus, the design corpus wins.

---


### Business
## 2. Keep the simulator neutral


### Academic
The simulator accepts a governance regime and evaluates its consequences under
the shared mechanics. It should not embed evaluator-side judgment.

Implementation consequences:

- avoid judgment-laden state or output names,
- do not encode "good" or "bad" governance directly into simulator logic,
- keep analysis conclusions out of the engine,
- and treat regime comparison as a downstream analytical task.

The simulator describes what happened. It does not decide what should have
happened.

---


### Business
## 3. Separate boundaries cleanly


### Academic
The implementation should preserve explicit boundaries between:

- simulator dynamics,
- governance policy logic,
- experiment orchestration,
- reporting/post-processing,
- and exploratory analysis.

In particular:

- governance should operate only on observables and permitted beliefs,
- the engine should remain the authority on state evolution,
- experiment runners should not silently modify simulator semantics,
- and analysis code should not mutate canonical run artifacts.

Portfolio-risk controls, if implemented, must remain policy-side. The engine may
surface convenience aggregates such as `PortfolioSummary`, but it must not
silently enforce diversification, labor-share limits, or concentration limits
unless the design corpus explicitly says to do so.

---


### Business
## 4. Prefer object-oriented boundaries and functional kernels


### Academic
The recommended implementation style is hybrid:

- use objects or structured classes at the boundaries for durable domain entities
  such as model configuration, experiment configuration, governance policy
  wrappers, run results, and future optimization wrappers,
- but keep the core state-transition logic as functional and side-effect-light as
  possible.

Examples of logic that should ideally be implemented as pure or nearly pure
functions:

- belief updates,
- decay updates,
- stop-rule evaluation,
- attention-feasibility evaluation,
- lifecycle transitions,
- event generation from explicit state transitions,
- and deterministic post-processing transforms.

This pattern improves testability, replayability, and future compatibility with
problem-solver wrappers.

---


### Business
## 5. Make randomness explicit and reproducible


### Academic
Random-number handling is a first-class invariant of the study.

Implementation requirements:

- no hidden global RNG state,
- no silent dependence on ambient library randomness,
- explicit seed provenance for every run,
- and stable random-stream handling under diverging governance paths.

The common-random-numbers discipline described in the corpus must be preserved.
If two governance regimes are meant to be compared under the same world, they
must remain comparable even when their action paths diverge.

---


### Business
## 6. Preserve resolved-input discipline


### Academic
The engine should receive a resolved initiative list or a generator block that is
resolved before simulation begins, exactly as the design corpus specifies.

Implementation must not let hidden generation-time randomness leak into the
middle of a run unless such behavior is explicitly added as a future extension.

Likewise, configuration and factor objects should remain explicit and serializable.

---


### Business
## 7. Treat outputs as part of the scientific interface


### Academic
The simulator's output contract is not an afterthought. It is part of the
study's method.

Implementation requirements:

- outputs must be machine-readable,
- outputs must preserve provenance,
- deterministic summaries must be reproducible from raw run artifacts,
- and the output design must support human analysts, AI analysts, and hybrid
  workflows over the same evidentiary base.

Do not optimize away fields that are needed for the stated research questions
just because they seem redundant during implementation.

Likewise, if the implementation provides a `PortfolioSummary` convenience block
in the governance observation, it should remain transparently derivable from the
authoritative initiative and team state rather than becoming an independent
stateful subsystem.

---


### Business
## 8. Keep facts, derived metrics, and interpretations separate


### Academic
The implementation should keep a clean boundary between:

- raw run artifacts,
- deterministic derived analytical artifacts,
- and interpretive reports or exploratory hypotheses.

This matters for both scientific discipline and future tooling. AI-assisted
analysis, dashboards, notebooks, and follow-up experiment planners should all be
downstream consumers of the same stable evidentiary substrate.

---


### Business
## 9. SimOpt-oriented compatibility rules


### Academic
Future compatibility with SimOpt should be preserved from the start, even if the
first implementation is not immediately wrapped as a SimOpt problem class.

That means the implementation should be structured as if it may later need to
support:

- explicit model/problem factors,
- controlled macroreplications,
- clean objective and constraint evaluation,
- and solver-independent experiment execution.

To preserve that option:

- keep governance policy logic separate from simulator mechanics,
- make model and experiment factors explicit and serializable,
- avoid hidden mutable state crossing replication boundaries,
- expose run results in a way that can later be wrapped into a reusable problem
  interface,
- and keep objective computation downstream and explicit rather than hiding it
  inside ad hoc notebooks or one-off scripts.

The implementation should make later wrapping into a simulation-optimization test
bed easier, not harder.

---


### Business
## 10. Preserve immutability where the design requires it


### Academic
The implementation must not violate immutability rules established by the design.

In particular:

- initiative attributes resolved at generation remain fixed unless the design
  explicitly states otherwise,
- latent truth remains latent,
- policy does not gain access to hidden engine statistics,
- and run manifests should be treated as immutable records of what was run.

Mutable state belongs only in the places the design corpus says it belongs.

This applies to portfolio exposure as well. Portfolio-level labor shares and
concentration measures should be derived views over the current world state, not
separately maintained hidden state that can drift out of sync.

---


### Business
## 11. Boundary error handling


### Academic
Expected failures at I/O, configuration, and external-tool boundaries should be
handled explicitly.

Examples include:

- malformed config files,
- schema violations,
- missing output directories,
- invalid parameter combinations,
- incomplete experiment manifests,
- and partial batch-run failures.

The implementation should fail loudly and traceably at boundaries rather than
silently degrading core scientific guarantees.

---


### Business
## 12. What teams may choose freely


### Academic
The implementation team should retain agency over choices that do not violate the
rules above. Examples include:

- internal module structure,
- helper abstractions,
- package naming,
- performance optimizations that preserve semantics,
- use of dataclasses or equivalent typed structures,
- and orchestration tooling for local and batch runs.

The goal is not to over-prescribe. The goal is to preserve the study's integrity
while leaving room for engineering judgment.


### Business
