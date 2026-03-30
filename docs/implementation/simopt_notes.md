# SimOpt compatibility notes

This document records design decisions and deferred work items related
to future SimOpt integration. The simulator is not yet wrapped as a
SimOpt problem class, but these notes ensure the implementation does
not paint itself into a corner.

See also:
- `docs/design/implementation_guidelines.md` §9 (SimOpt-oriented
  compatibility rules — frozen design authority)
- `docs/design/implementation_guidelines.md` §9 (SimOpt-oriented compatibility)

---

## Decided: MRG32k3a from the start

The simulator uses MRG32k3a (via the `mrg32k3a` PyPI package) as its
RNG from v1. This eliminates a future migration when wrapping the
simulator as a SimOpt problem class.

MRG32k3a provides native stream/substream partitioning that maps
directly to our CRN discipline:
- world_seed → generator initial state
- Per-initiative substream pairs (quality signal, execution signal)
- Pool generator substream for attribute draws

The `noise.py` module owns all MRG32k3a construction. No other module
imports or references MRG32k3a directly.

---

## Decided: replication control is external

SimOpt controls how many replications to run and with what seeds. Our
`world_seed` model is compatible: SimOpt calls
`run(config, seed) → RunSummary` once per replication. The runner must
expose this single-replication interface cleanly. The batch runner
(multi-seed, multi-regime) is a convenience layer on top, not a
requirement.

Key constraint: `runner.py` must not assume it owns the outer
replication loop. The single-run function must be callable
independently.

---

## Deferred: SimOpt Problem class wrapper (Phase 7+)

A SimOpt Problem subclass requires:
- `model` attribute: describes the simulation model
- `model_default_factors`: default parameter values
- `specifications`: objective types, constraint types
- `simulate(solution, budget)`: run `budget` replications for a
  given solution (parameter vector) and return responses
- `replicate(rng_list)`: run a single replication with provided RNG
  streams

Implementation plan when the time comes:
- Create `simopt_wrapper.py` outside the core simulator
- Map `SimulationConfiguration` fields to SimOpt factors
- Map `RunSummary` fields to SimOpt responses
- The wrapper calls `runner.run()` internally

This is NOT built in v1. The constraint on v1 is only: don't make
wrapping harder than it needs to be.

---

## Deferred: objective and constraint mapping

When the simulator becomes a SimOpt problem, certain `RunSummary`
fields will map to optimization objectives and stochastic constraints.

**Candidate objective fields** (to be refined when optimization
scope is defined):
- `total_portfolio_value_realized` — primary value objective
- `total_capability_gained` — capability objective
- `fraction_of_high_quality_completed` — discovery effectiveness
- `total_labor_wasted_on_stopped` — efficiency constraint

**Candidate constraint fields:**
- `fraction_of_portfolio_idle` — utilization lower bound
- `max_concurrent_active` — capacity constraint

These fields do not need to exist in v1's `RunSummary` with these
exact names. The requirement is only that `RunSummary` captures
enough raw data that these metrics can be computed. When defining
`RunSummary` (Phase 6), ensure the underlying data is available.

---

## No conflict: MRG32k3a substream model vs. SimOpt stream model

SimOpt's `replicate()` method receives a list of RNG streams. Our
`noise.py` constructs its own streams from `world_seed`. When
wrapped, the SimOpt wrapper would either:

(a) Pass SimOpt-provided streams through to `noise.py`, replacing
    the seed-based construction, or
(b) Derive `world_seed` from the SimOpt-provided stream state and
    let `noise.py` construct streams as usual.

Option (a) is cleaner but requires `noise.py` to accept pre-built
streams as an alternative to seed-based construction. This is a
minor interface extension, not a redesign. The `noise.py` abstraction
should be designed with this in mind: accept either a seed or
pre-built stream objects.
