# Exec Intent Spec

**Status:** draft — 2026-04-18
**Purpose:** define the small, stable set of business-unit inputs an
executive user specifies to configure one simulation run. This spec is
the contract the exec-facing authoring surface (YAML, notebook sliders,
or a future web form) must satisfy. It does NOT propose new model
mechanics; every input here already has a simulator-side counterpart.

## Why this document exists

The current authoring layer (`RunDesignSpec`, `run_design_template.yaml`,
the business-intent registry) already reaches most of what an exec
needs, but three problems remain:

1. Several inputs are in researcher units (abstract "labor units,"
   attention floats, ticks) rather than business units (people, hours
   per week, weeks).
2. A few exec-relevant inputs are not exposed on the authoring surface
   at all (`baseline_value_per_tick`; value-unit label for reporting).
3. Several researcher-only inputs *are* exposed, inviting execs to
   touch model physics they should not. The boundary is not currently
   explicit.

This spec fixes the contract. Implementation work then becomes
mechanical: surface the inputs below in exec-facing form, translate
units, and remove or hide everything else from the exec surface.

## Scope boundary

- **Exec surface:** the ~8 inputs in the table below, in business
  units, with defaults. Exec can start from a reference-case preset
  (e.g. `balanced_incumbent_balanced.yaml`) and change a handful of
  fields.
- **Researcher surface:** everything else — model physics, operating-
  policy internal thresholds, environment family mechanics, frontier
  and staffing-response shape. Researchers edit these through the
  existing `RunDesignSpec` / presets path.
- **Tool is evaluation, not optimization.** Exec states constraints;
  the sim shows consequences. No search loops over exec inputs.
  (See `feedback_evaluation_not_optimization.md`.)

## The exec inputs

All defaults below reference the canonical balanced-incumbent baseline.
"Maps to" names the existing simulator-side field. "Status" is
EXISTS (already on the exec surface), TRANSLATE (exists but in
researcher units — need a business-unit wrapper), or GAP (not on the
exec surface today, needs adding).

| # | Input | Business unit | Default | Allowed range | Maps to | Status |
|---|---|---|---|---|---|---|
| 1 | Attention budget | hours per week | 8 | 1–40 | `ModelConfig.exec_attention_budget` (currently 30.0, abstract) | TRANSLATE |
| 2 | Horizon | weeks | 313 (≈6 yr) | 26–520 | `TimeConfig.tick_horizon` (1 tick = 1 week by convention) | EXISTS |
| 3 | Workforce size | people | 210 | 20–500 | `WorkforceArchitectureSpec.total_labor_endowment` (1 unit ≈ 1 person) | TRANSLATE (doc-only; unit is already 1:1) |
| 4 | Team structure | per-team people counts | 24 teams (10×5, 12×10, 2×20) | any integer partition of workforce size | `WorkforceArchitectureSpec.team_count` + `team_sizes` | EXISTS |
| 5 | Portfolio mix | counts of QW / FW / EN / RT | 80 / 70 / 30 / 20 (balanced_incumbent) | each ≥ 0; total 50–400 | `InitiativeTypeSpec.count` inside the environment family | TRANSLATE (counts are currently locked inside family presets; `right_tail_prize_count` is the only exec-editable count) |
| 6 | Governance archetype | named posture | `balanced` | `balanced` \| `aggressive_stop_loss` \| `patient_moonshot` | `OperatingPolicySpec.preset` | EXISTS |
| 7 | Baseline value per team per week | dollars / team-week (or other value unit) | 0 | 0 – (small positive, order ~0.1 in raw units) | `ModelConfig.baseline_value_per_tick` | GAP (field exists; not exposed on authoring surface) |
| 8 | Value unit label | string | "units" | free text (e.g. `"$M"`, `"pts"`) | currently none — reporting label only | GAP |
| 9 | Seeds | list of integers | `[42, 43, 44]` | 1–20 seeds, any ints | `RunDesignSpec.world_seeds` | EXISTS |

Nine fields, not eight — the report-side value-unit label (#8) is a
thin add that makes all dollar/value outputs interpretable, so it
belongs here even though it does not touch mechanics.

## Resolved open questions

Decisions from the project-usability-direction doc, closed here so
implementation is not blocked:

- **Value unit.** Exec specifies a free-text unit label (#8) plus a
  per-team-per-week baseline rate (#7) in that unit. The simulator
  is unit-agnostic; it runs in the same numeric scale regardless of
  the label. The label is propagated to the report layer only. All
  completion-lump, residual-stream, and major-win value outputs
  inherit the same unit by convention — no per-mechanism unit
  overrides.
- **Horizon unit.** Weeks. One tick = one week. `tick_label`
  defaults to `"week"` already; the exec surface will show weeks in
  every input and every output. Months are not offered — translating
  week-resolution mechanics into months would invite off-by-one
  confusion for no analytical gain.
- **Replication.** A "run" from the exec's viewpoint is a cohort of
  seeds, not a single seed. Default cohort is 3 seeds. Exec edits the
  seed list directly (#9). Reporting averages across the cohort with
  the per-seed range shown alongside.
- **Portfolio mix.** Specified as absolute counts (80 / 70 / 30 / 20),
  not percentages. Counts are more legible to execs ("we want 30
  enabler initiatives in the funnel") and round-trip cleanly into
  `InitiativeTypeSpec.count`. Total pool size is a derived quantity,
  not a separate input.

## Explicitly NOT exposed to execs

Any field not in the table above is researcher-only. In particular,
these are the temptingly simple-sounding fields the exec surface
must *not* expose, with the reason:

- `default_initial_quality_belief`, `learning_rate`,
  `dependency_learning_scale`, `execution_learning_rate` —
  calibrated belief-update physics. Changing these redefines what
  "governance sees" and breaks cross-regime comparability.
- `base_signal_st_dev_default`, `execution_signal_st_dev`,
  `dependency_noise_exponent` — signal-noise physics.
- `attention_noise_threshold`, `low_attention_penalty_slope`,
  `attention_curve_exponent`, `min_attention_noise_modifier`,
  `max_attention_noise_modifier` — attention-curve shape. Exec chooses
  the *budget*; the *curve* is calibrated.
- `max_portfolio_capability`, `capability_decay` — enabler-effect
  physics.
- `reference_ceiling` — TAM-patience scaling constant.
- All operating-policy internals
  (`confidence_decline_threshold`, `tam_threshold_ratio`,
  `base_tam_patience_window`, `stagnation_window_staffed_ticks`,
  `stagnation_belief_change_threshold`, `attention_min`,
  `attention_max`, `exec_overrun_threshold`). Exec chooses a named
  preset (#6); per-field overrides belong to systematic sweeps in
  `campaign.py`, not to the exec surface.
- `staffing_response_overrides`, `frontier_degradation_rate_overrides`,
  `right_tail_refresh_degradation` — environment conductor overrides
  that belong to researcher-side robustness studies.
- Portfolio guardrails (`low_quality_belief_threshold`,
  `max_low_quality_belief_labor_share`,
  `max_single_initiative_labor_share`, `portfolio_mix_targets` as
  soft policy preferences) — architecture-level research levers.
  Not exposed in the exec-v1 surface. If an exec wants "cap any one
  bet at 40%," promote it to an exec input in a later revision; do
  not quietly enable it from the researcher surface.
- `ReportingConfig` flags — recording is always full-logging for exec
  runs (the report relies on per-tick logs).

## Out of scope for v1

- Comparison regimes in the same YAML. The user rejected mandatory
  comparison framing. If an exec wants A-vs-B, they run two designs
  and compare manually. A future comparison-first layer can sit above
  this spec without changing it.
- Hosted web form / notebook sliders. The spec is surface-independent;
  a CLI YAML entry point is sufficient for v1. Front-ends can be
  added without changing the input contract.
- Reference-case starting points ("early-stage startup," "mature
  enterprise," etc.). Covered by the existing
  `templates/presets/*.yaml` files, which already collapse the
  exec inputs into nine starting configs. No new mechanism required —
  rename or reorganize the presets if the exec-oriented labels are
  clearer than the current family-×-policy naming.

## Implementation notes

Not part of the spec itself; included for the follow-on task so it
is not lost.

- Most work is in `workbench.py` (`RunDesignSpec.from_dict` and
  `summary()`), `run_design_template.yaml`, and `run_design.py`.
  `business_intent.py` and the registry already encode several of
  these translations; they can be retired, extended, or kept as a
  secondary intent-driven entry point — that is an implementation
  choice, not a spec choice.
- Unit translation lives at the YAML-parse boundary. The simulator
  boundary stays as it is: the engine receives
  `SimulationConfiguration` with the existing abstract numbers. Only
  the authoring layer speaks hours, weeks, people, dollars.
- Inputs #7 and #8 require new fields on the authoring surface
  (`architecture.baseline_value_per_team_week` and a top-level
  `value_unit` or `reporting.value_unit`). Everything else is a
  rename / unit wrap / documentation change.
