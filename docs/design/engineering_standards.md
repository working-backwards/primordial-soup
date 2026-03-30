# Engineering standards

## Role of this document


### Academic
This document defines the code-quality and repository-hygiene expectations for
the Primordial Soup implementation.

`implementation_guidelines.md` protects model integrity and future
optimization-oriented compatibility. This document covers the engineering
discipline needed to keep the implementation maintainable.

---


### Business
## Project configuration


### Academic
- Use `pyproject.toml` as the primary home for project and tool configuration
  whenever practical.
- Keep tool configuration explicit and version-controlled.
- Avoid undocumented local-only tooling assumptions.

---


### Business
## Formatting and linting


### Academic
- Run the formatter before finalizing changes.
- Run `ruff check` and satisfy it before merging changes.
- Do not leave formatting, lint, or import-order issues for later cleanup.

The code base should remain clean by default rather than relying on periodic
bulk cleanups.

---


### Business
## Typing


### Academic
- Add type hints to all new or modified production code.
- Do not introduce new mypy errors.
- Treat unclear types as a design smell worth resolving rather than bypassing
  casually.

Type information is especially important in this project because the simulator,
governance logic, reporting layer, and experiment runner have strong interface
contracts.

---


### Business
## Testing


### Academic
- Add or update `pytest` tests for behavior changes.
- Prefer narrow, behavior-focused tests over brittle implementation-detail tests.
- Add regression tests for bug fixes.
- Preserve deterministic replay in tests wherever possible.

At minimum, tests should cover:

- state-transition correctness,
- stop-rule behavior,
- seed/reproducibility guarantees,
- schema validation,
- and key reporting outputs tied to the research questions.

---


### Business
## Error handling


### Academic
- Handle expected failures at I/O and API boundaries explicitly.
- Raise clear, actionable errors for schema violations and invalid parameter
  combinations.
- Do not silently coerce invalid scientific inputs into "reasonable" behavior
  unless the design corpus explicitly says to do so.

---


### Business
## Change discipline


### Academic
- Do not violate immutability rules set out in the design corpus.
- Do not mix simulator-mechanics changes with broad refactors unless necessary.
- Keep commits reviewable and semantically coherent.
- When a behavior change is made, update the relevant documentation alongside the
  code.

---


### Business
## Documentation hygiene


### Academic
- Keep docstrings and user-facing comments aligned with the design corpus.
- Prefer comments that explain invariants and non-obvious reasoning over comments
  that merely narrate the code.
- If a design change affects output semantics, update the reporting and analysis
  docs, not just the implementation.

---


### Business
## AI-assisted tooling boundary


### Academic
AI tools may be used for development assistance, test-idea generation,
documentation review, or exploratory analysis support.

They should not be treated as authoritative on simulator behavior. Canonical
behavior must remain grounded in the design corpus and verified through code,
tests, and deterministic outputs.


### Business
