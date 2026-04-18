# Single-Run Report Spec

**Status:** draft — 2026-04-18
**Purpose:** define what the single-run report contains so an exec (or
anyone not living in the code) can read the output of one simulation
run — a cohort of seeds under one governance design — without asking
what anything means. Pairs with `exec_intent_spec.md`.

## Why this document exists

The current report (`report/index.html` + `report/report.md`, rendered
by `report_gen.py` from the Parquet tables in `outputs/`) is built for
multi-condition comparison. Even when you run a single design, the
shell is comparison-shaped: a "Headline Comparison" table with one
row, figures and text framed around conditions, no plain-language
definitions, no units, no ranges, no narrative. The "Metric guide"
text block that `run_design.py` prints to the console is *not* in the
report.

This spec fixes the contract for the single-run case:
- what metrics appear,
- what each one means in one sentence,
- what unit it is in and what range counts as normal,
- and how the report narrates the run in plain text.

Multi-condition reports are a separate concern and keep their current
shape; nothing here blocks them.

## Scope boundary

- **In scope:** the report the exec reads after running one
  `RunDesignSpec` (one environment × one architecture × one policy)
  across a seed cohort (default 3 seeds). Runs that include multiple
  conditions use the existing comparison report; this spec does not
  govern them.
- **Out of scope:** comparison against a reference regime; PDF export;
  academic-validity sections; per-seed statistical inference (CIs,
  bootstrap); the two-audience split the team considered and
  rejected on 2026-04-18.

## Report structure

Six sections, in this order. Both HTML and markdown renderers follow
the same structure.

1. **Run identity.** Design name, title, description, resolved
   business-unit inputs (echoes exec_intent_spec.md fields: hours/week,
   horizon in weeks, people, team structure, portfolio counts,
   archetype, seed list, value unit), run-bundle id, git commit.
   No mechanics parameters here — those live in the appendix.

2. **Headline outcomes.** The metric table defined below, showing
   mean-across-seeds with a min–max range. For single-seed runs,
   no range. No comparison column.

3. **Narrative paragraph.** Four short paragraphs generated from the
   headline data using the template in §Narrative below. This is
   the part that makes the report skimmable.

4. **Figures.** The core figure set currently produced by
   `figures.py` stays. Each figure gets a one-sentence caption that
   says what it shows and what to look for. Captions today are
   title-only.

5. **Governance actions detail.** Tables for stops, completions, and
   time-to-first completion, broken down by initiative family
   (quick-win / flywheel / enabler / right-tail). Same source data as
   today (family_outcomes.parquet, seed_runs.parquet), just labeled
   in plain language with units.

6. **Appendix — methods and provenance.** Full resolved
   configuration, baseline_spec_version, seed list, command,
   reproduction instructions. Today's "Methods and Reproducibility"
   section grown to include the full resolved config.

## The headline metrics

Every surfaced metric has: plain-language definition, unit, reasonable
range. "Source" names the existing reporting-layer field so
implementation is mechanical. "Status" is EXISTS (already surfaced in
the report), LABEL (field is surfaced but needs plain-language
labeling and units), or GAP (derived or new; needs implementation).

Ranges are anchored to the canonical `balanced_incumbent` environment
at `total_labor_endowment=210`, `tick_horizon=313`, seed cohort of 3,
under the three named policy presets. Ranges are indicative, not
calibration targets — they tell the reader whether their number is
ordinary or unusual. See §Range maintenance below.

| # | Metric | Plain-language one-liner | Unit | Reasonable range (balanced baseline) | Source | Status |
|---|---|---|---|---|---|---|
| 1 | Total value | Sum of all value created during the run: completion payoffs + residual streams + baseline-work value. | value-unit label (e.g. `$M`) | ~3 000 – 7 000 | `RunResult.cumulative_value_total` | LABEL |
| 2 | Value from completions | Share of total value from one-time payoffs when initiatives finished. | % of #1 | 40–70 % | `value_by_channel.completion_lump_value` | GAP (ratio; label) |
| 3 | Value from residual streams | Share of total value from ongoing flywheel and quick-win streams after completion. | % of #1 | 30–55 % | `value_by_channel.residual_value` | GAP (ratio; label) |
| 4 | Value from baseline work | Share of total value from idle-team baseline activity (maintenance, support, etc.). | % of #1 | 0 % unless the exec set a baseline rate | `RunResult.cumulative_baseline_value` | GAP (surface; label) |
| 5 | Major wins surfaced | Right-tail breakthroughs that governance allowed to complete. Count only; not priced into #1. | count | 0–5 | `major_win_profile.major_win_count` | EXISTS |
| 6 | Productivity multiplier at end | Portfolio-capability multiplier at the final week; 1.0× = baseline, >1 = enablers have compounded. | × | 1.5×–3.0× | `RunResult.terminal_capability_t` | LABEL |
| 7 | Peak productivity multiplier | Highest multiplier reached at any week during the run. | ×  (+ week reached) | 1.8×–3.0× | `max_portfolio_capability_t`, `family_timing.peak_capability_tick` | LABEL |
| 8 | Free value per week at end | Value per week the portfolio would keep generating with no further labor, from residual streams alive at the last week. | value-unit per week | 2–15 | `terminal_aggregate_residual_rate` | LABEL |
| 9 | Idle team-weeks share | Fraction of team-weeks where the team had no portfolio assignment. | % | 40 %–70 % | `idle_capacity_profile.idle_team_tick_fraction` | LABEL |
| 10 | Pool exhaustion week | First week when governance had labor to spare but no initiative above its activation threshold. "Not reached" if it never happened. | week or `not reached` | weeks 100–250 under balanced | `idle_capacity_profile.pool_exhaustion_tick` | LABEL |
| 11 | Initiatives stopped | Count of initiatives governance stopped before completion, with a QW/FW/EN/RT breakdown. | count | 40–100 total | `exploration_cost_profile.stopped_initiative_count_by_label` | LABEL |
| 12 | Initiatives completed | Count of initiatives that reached completion, with a QW/FW/EN/RT breakdown. | count | 40–90 total | `exploration_cost_profile.completed_initiative_count_by_label` | LABEL |
| 13 | Right-tail false-stop rate | Of right-tail initiatives that *would* have surfaced a major win, the fraction governance stopped before completion. `n/a` if no eligibles existed. | % or `n/a` | 0–40 % | `right_tail_false_stop_profile.right_tail_false_stop_rate` | LABEL |
| 14 | Time to first completion (by family) | The earliest week a quick-win / flywheel / enabler / right-tail initiative completed. "None" if none did. | week per family | QW: ~10; FW: ~40; EN: ~20; RT: ~150 | `family_timing.first_completion_tick_by_family` | LABEL |
| 15 | Ramp overhead | Share of team-weeks spent ramping up after a reassignment (not yet fully productive). | % | 3–8 % | `RunResult.ramp_labor_fraction` | GAP (surface; label) |
| 16 | Quality estimation error | Mean absolute gap between governance's quality belief and the latent true quality, averaged over all initiative-weeks. Lower is better. | 0–1 scale | 0.05–0.15 | `belief_accuracy.mean_absolute_belief_error` | EXISTS |

Fifteen metrics visible by default. Everything else in `RunResult`
(event logs, per-tick records, per-family residual dictionaries,
full distributions) is available in the Parquet tables for drill-down
but does not crowd the headline.

## Unit and label conventions

- **Weeks, not ticks.** Every time reference in the report uses the
  exec-facing unit: "week 142," "hold for 12 weeks." The tick count
  is available in the appendix.
- **People and hours/week.** Workforce and attention echo the exec
  input labels from `exec_intent_spec.md`. No raw "labor units" or
  abstract attention floats in the reader-facing sections.
- **Value unit.** Inherits the label the exec supplied
  (`exec_intent_spec.md` input #8). All value metrics (#1, #2, #3, #4,
  #8) render with that label. The simulator still runs in unitless
  numerics; the label is a report-layer concern — it is applied at
  render time in `report_gen.py`, not in `reporting.py` or the engine.
- **Seeds.** Mean-across-seeds is the headline number; min–max range
  is shown inline (`5 123 (4 870–5 410)`). Single-seed runs show the
  value with no range. No variance, no confidence interval — that is
  academic-validity territory and was explicitly scoped out.

## Narrative paragraph

Four short paragraphs, generated from the same data that fills the
headline table. One idea per paragraph so the reader can skim.

1. **Value sources.** "Over N weeks, this run produced `<#1>` `<unit>`
   of value. `<#2>` came from initiative completions, `<#3>` from
   ongoing flywheel and quick-win streams, `<#4>` from baseline
   non-portfolio work. `<#5>` major wins were surfaced but are not
   priced into the total."
2. **Governance actions.** "Governance stopped `<#11-total>`
   initiatives and completed `<#12-total>`. Quick-wins: `<N stopped /
   M completed>`. Flywheels: `<…>`. Enablers: `<…>`. Right-tails:
   `<…>`, of which `<#13>` of those that could have surfaced a major
   win were stopped."
3. **Idle capacity.** "Teams were without a portfolio assignment
   `<#9>` of the run. The initiative pool was exhausted at week
   `<#10>` / the pool was never exhausted. `<#15>` of team-weeks went
   into ramp-up after reassignments."
4. **Capability and discovery.** "Productivity peaked at `<#7>` at
   week `<peak-week>` and ended at `<#6>`. At the final week the
   portfolio was still generating `<#8>` `<unit>` per week from
   ongoing streams without new labor."

Templating is mechanical string interpolation; no NLG library. When a
field is `None` or `n/a`, the corresponding sub-clause is dropped
(e.g. "pool exhaustion" paragraph simply says "was never exhausted").

## Resolved open questions

Decisions from `project_usability_direction.md`, closed here so
implementation is not blocked:

- **Range source.** Author-curated guidance, stored in one place
  alongside this spec (a small YAML or constants module used by
  `report_gen.py`). Reason: empirical ranges from calibration runs
  are sensitive to the governance regime and recalibrate whenever
  model physics move; theoretical bounds rarely exist for
  multi-mechanism aggregates. Curation lets the range be meaningful
  and maintained intentionally. The ranges here are tagged to
  `baseline_spec_version` — when a model revision lands, the ranges
  are reviewed as part of that revision (see
  `calibration_model_revision_carryover.md` for the pattern).
- **Granularity.** One regime across a seed cohort. Default cohort
  is 3 seeds (from `exec_intent_spec.md` #9). Report shows mean and
  min–max; variance and CIs are out of scope. Single-seed runs drop
  the range and show the value alone.
- **Report units own the translation.** The simulator stays
  unit-agnostic. `report_gen.py` (and the table-build helpers it
  calls in `tables.py`) receives unit labels from the
  `RunDesignSpec`/exec-layer and applies them at render time. The
  engine and `RunResult` never change.

## Figure captions

No new figures. Each existing figure gets a one-sentence
plain-language caption. Current captions:

- Value by Year — Stacked by Family
- Cumulative Priced Value by Year
- Surfaced Major Wins by Year
- Tradeoff Frontier
- Terminal Capability Comparison
- Right-Tail False-Stop Rate
- Enabler Dashboard
- Representative-Run Timelines
- Quality Belief Trajectories
- Trajectory Overlay
- Seed-Level Distributions

For each, the caption answers two questions in one sentence: what the
axes show, and what pattern means "this governance regime did its
job." (E.g., Enabler Dashboard: "When enablers complete, productivity
multiplier steps up; long flat stretches mean enablers are stalled or
being stopped.") The exact caption text lives next to the figure in
`report_gen.py`; it is not part of this spec beyond "every figure has
one, and it says what to look for."

## Range maintenance

The ranges in the metrics table are indicative anchors, not tests.
When they drift out of date (model revision, preset change), update
them in the same commit as the code change that moved them.
Reviewers should treat an un-updated range as a smell, the same way
they treat a stale comment. The ranges are not asserted in tests —
runs that fall outside them are not errors, only reasons for the
reader to look more carefully.

## Implementation notes

Not part of the spec itself; included for the follow-on task.

- Three source files change: `report_gen.py` (structure and
  narrative), `tables.py` (add the derived ratios #2/#3/#4 and
  surface `ramp_labor_fraction` if they are not already in the
  condition-level row), and the figure captions inside `figures.py`
  or next to the figure filename in `report_gen.py`.
- `summarize_run_result()` in `workbench.py` already contains most
  of the needed fields. The report generator can reuse it rather
  than re-reading Parquet for scalar metrics; the Parquet tables
  remain the source of truth for per-family and timeseries data.
- For the single-run shape vs. the multi-condition shape, the
  generator can branch on
  `len(table_data["experimental_conditions"]) == 1`. No separate
  entry point required.
- Value-unit label propagation: `RunDesignSpec` needs the
  `value_unit` field (exec_intent_spec #8); `ResolvedRunDesign`
  passes it into `ExperimentSpec`; `report_gen.py` reads it off the
  manifest at render time.
