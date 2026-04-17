# Governance and reporting

## Role of this document


### Academic
This document specifies the canonical output surface of the Primordial Soup study.
It does **not** define simulator mechanics, governance decisions, or experiment
design. Those belong elsewhere in the corpus.

This document defines the observational and reporting contract only. The
downstream use of these outputs for deterministic summaries, exploratory
interpretation, AI-assisted analysis, and follow-up experiment design is defined
in `analysis_and_experimentation.md`. The reporting layer should therefore be
read as the evidentiary substrate for analysis rather than as the full analysis
workflow. The separation is functional: this layer produces the complete
deterministic evidentiary record; the analysis layer defines how that record is
consumed for inference. No interpretive claim generated downstream acquires
evidentiary standing exceeding that of the outputs defined here.

Throughout this document, schema field names should be read as the canonical
descriptive names for implementation and analysis surfaces. Where compact
mathematical symbols exist elsewhere in the corpus, these reporting names are the
preferred code-facing equivalents.

Style preference:

- use `mean` and `st_dev` in explanatory prose rather than `mu` and `sigma`,
- use descriptive names such as `quality_belief_t` and `latent_quality` in prose,
- reserve compact notation for equations and derivations in other documents.

### Business
This document specifies exactly what the simulation produces as output — the complete set of measurements, records, and structured evidence that every simulation run generates. It does not define how the simulation works, how governance makes decisions, or how experiments are designed. Those are specified elsewhere in the design corpus.

This document defines the reporting and measurement contract only: what gets recorded, in what form, and with what precision. Everything downstream — the standardized comparisons, the exploratory analysis, the AI-assisted pattern recognition, the follow-up experiment design — is defined in the analysis and experimentation document. The reporting layer described here should therefore be understood as the evidentiary foundation on which all analysis rests. It produces the facts. The analysis layer interprets them.

Throughout this document, field names and output labels use plain-language descriptive names — the same names that appear in code and in analysis surfaces. Where compact mathematical symbols exist elsewhere in the design corpus, the names used here are the preferred equivalents for reporting, implementation, and analysis. For example: "strategic quality belief" rather than a symbol, "true underlying quality" rather than a variable letter, "standard deviation" rather than an abbreviation.

## Governance invocation model


### Academic
The engine invokes the governance policy at every tick. For every active staffed
initiative, the policy must emit either `ContinueStop(continue)` or
`ContinueStop(stop)`. There is no abstain option: silence on an active staffed
initiative is not a valid governance posture and the engine does not supply a
default. Effective review depth — how carefully a policy examines an initiative
before deciding — is a behavioral property of the policy's internal logic, not an
engine-level parameter.

### Business
The simulation engine invokes governance at every weekly decision point. For every initiative that is currently active and staffed with a team, governance must produce an explicit decision: continue investing, or stop. There is no option to abstain, defer, or remain silent. An active, staffed initiative that does not receive a verdict is a protocol violation, not a default continuation. The engine does not assume that silence means "keep going."

How carefully a governance regime examines each initiative before making its decision — whether it applies deep scrutiny or a cursory check — is entirely a property of the governance regime's internal logic. The engine does not control or parameterize review depth. It requires only that every active staffed initiative receives a clear verdict at every decision point.

## Primary outputs (per run)

### Academic
Each run of the simulator produces a structured set of response variables and
diagnostic records designed to support rigorous cross-regime comparison under the
study's common-random-numbers experimental design. These outputs are organized
around the three response-variable families defined in the study design —
realized economic performance, major-win discovery performance, and
organizational capability development — along with diagnostic profiles that
characterize how each governance regime allocated resources, generated
information, and made stop decisions. Together, they constitute the complete
deterministic evidentiary record for the run: the factual base from which all
downstream analysis proceeds.

- `cumulative_value_total` (scalar)
- `value_by_channel`:
  - `completion_lump_value`
  - `residual_value` (portfolio-level)
  - `residual_value_by_label`:
    - `flywheel`
    - `right_tail`
    - `enabler`
    - `quick_win`
    This is a mechanism-level decomposition of realized residual value by the
    generation label of the initiative that produced it. In the canonical study,
    this is expected to be populated primarily by flywheel initiatives, which
    are residual-value dominant. Quick wins may contribute a small residual
    tail, but their primary value mechanism is the completion-lump channel.
    Enablers do not use a residual channel, and right-tail initiatives realize
    success through major-win events rather than ordinary residual or lump
    value. The field is still reported generically so the output schema matches
    the initiative pool ontology rather than a narrower assumption about which
    labels will actually produce nonzero residual value.
- `major_win_count` (count of surfaced major wins in the run)
- `time_to_major_win` distribution for surfaced major wins
- `probability_of_major_win` (empirical fraction across runs)
- `major_win_profile`:
  - `major_win_count_by_label` (count of surfaced major wins by generation label)
  - `labor_per_major_win`: for governance regimes that produced at least one
    surfaced major win, the ratio of total labor invested in right-tail
    initiatives to the count of surfaced major wins
  - `major_win_event_log` (when `record_event_log == true`): the structured
    `MajorWinEvent` records defined below
- `aggregate_belief_accuracy`:
  - `mean_absolute_belief_error` = mean over all emitted
    `PerInitiativeTickRecord` rows of `|quality_belief_t - latent_quality|`
  - `mean_squared_belief_error` = mean over all emitted
    `PerInitiativeTickRecord` rows of `(quality_belief_t - latent_quality)^2`
- `quality_distribution` of stopped vs major-win initiatives
- `terminal_capability_t`: value of portfolio_capability_t (C_t) at the final tick of the run. Dimensionless, in `[1.0, C_max]`.
- `max_portfolio_capability_t`: peak value of `portfolio_capability_t` (C_t)
  reached at any tick during the run. Always available regardless of
  `record_per_tick_logs`. Complements `terminal_capability_t`: because capability
  decays exponentially between enabler completions, the terminal value may
  understate the organizational productivity gain that was active during the
  run. Use `max_portfolio_capability_t` to assess the peak effect of enabler
  completions; use `terminal_capability_t` to assess the residual effect at horizon.
  Do not combine these two scalars into a composite — they measure different
  things and any composite must define its weighting explicitly.
- `terminal_aggregate_residual_rate`: sum of `residual_rate` across all `residual_activated` initiatives at the final tick. Units: value/tick. Represents the run-ending "flywheel momentum." Serialized in the run summary output. Do not aggregate these two fields into a single composite — any downstream analysis requiring a composite must define its own weighting explicitly, with awareness of the dimensional mismatch.
- `value_by_family`: cumulative value (lump + residual) decomposed by `generation_tag`. Dict mapping family name to total value. Enables family-level value attribution without requiring per-tick logs.
- `ramp_labor_fraction`: fraction of total team-ticks spent in ramp (switching cost). Scalar in [0, 1]. Complements `cumulative_ramp_labor` (raw count) with a normalized measure.
- `family_timing` (`FamilyTimingProfile`): per-family timing metrics for governance pacing analysis. Contains:
  - `first_completion_tick_by_family`: dict mapping family name to tick of first completion (None if no completions).
  - `mean_completion_tick_by_family`: dict mapping family name to average completion tick (None if no completions).
  - `completion_ticks_by_family`: dict mapping family name to sorted tuple of all completion ticks.
  - `peak_capability_tick`: tick at which `portfolio_capability_t` reached its maximum.
  - `first_right_tail_stop_tick`: tick of first right-tail stop (None if no right-tail stops).
- `frontier_summary` (`FrontierSummary` | None): per-family frontier exhaustion state at end of run. None for fixed-pool runs. Contains `family_frontier_states`: dict mapping family name to `{n_resolved, n_frontier_draws, effective_alpha_multiplier}`.
- `per-initiative per-tick log` (emitted when `record_per_tick_logs == true`):

  ```
  PerInitiativeTickRecord:
      tick:                       int      — simulation tick
      initiative_id:              str
      lifecycle_state:            str
      quality_belief_t:           float    — current quality belief (observable to governance)
      latent_quality:             float    — true quality (post-hoc only; not observable
                                             during run)
      exec_attention_a_t:         float
      effective_sigma_t:          float    — effective_signal_st_dev_t on this tick for
                                             this initiative
      execution_belief_t:         float | None
      is_ramping:                 bool
      ramp_multiplier:            float | None  — None if not ramping
  ```

  These records are the primary input for belief accuracy analysis (RQ1) and
  attention-termination interaction analysis (RQ7). The `latent_quality` field enables
  post-hoc comparison of belief trajectories against true quality without the
  engine ever exposing latent quality to governance during the run. `effective_sigma_t`
  makes the signal path directly auditable for RQ7.

  * `exec_attention_a_t` is the realized attention applied on that tick after engine
  validation, not merely the submitted policy request. Because the canonical
  attention contract is omission-means-zero, this field is never omitted for an
  active initiative in the emitted tick log: an initiative omitted from the
  policy's `SetExecAttention` actions records `exec_attention_a_t = 0.0` for that
  tick rather than inheriting any prior attention state.

- `per-tick portfolio trace` (emitted alongside per-initiative records when
  `record_per_tick_logs == true`):

  ```
  PortfolioTickRecord:
      tick:                           int
      capability_C_t:                 float    — portfolio_capability_t at this tick; required
                                                 for RQ4 capability-investment analysis
      active_initiative_count:        int
      idle_team_count:                int
      total_exec_attention_allocated: float    — portfolio sum across all
                                                 SetExecAttention actions this tick
  ```

  **Trace granularity**: `PerInitiativeTickRecord` captures per-initiative state each
  tick and is the source for RQ1 (belief accuracy), RQ7 (attention-termination
  interaction), and RQ8 (cost-projection sensitivity). `exec_attention_a_t` in that
  record is per-initiative. `PortfolioTickRecord` captures portfolio-level aggregates
  only; `total_exec_attention_allocated` there is the portfolio sum, not
  per-initiative. Analyses requiring per-initiative attention history must use
  `PerInitiativeTickRecord`, not `PortfolioTickRecord`. Because attention does not
  persist across ticks unless re-emitted by policy, attention histories must be
  interpreted tick-by-tick rather than as a sticky state.

- `cumulative_ramp_labor`: total team-ticks consumed during ramp periods (sum of
  `team_size × 1` for each initiative-tick where `is_ramping == true`). Represents
  the labor cost of the productivity-reduction period caused by team reassignment.
  Divide by total team-ticks to obtain the ramp-labor fraction as a normalized
  metric for cross-regime comparison.
- `reassignment_profile`:
  - `reassignment_event_count`: total number of team reassignments in the run
  - `reassignment_event_log` (when `record_event_log == true`):
    ```
    ReassignmentEvent:
        tick:                int
        team_id:             str
        from_initiative_id:  str | None
        to_initiative_id:    str
        triggered_by:        "governance_stop" | "completion" | "idle_reassignment"
    ```
    These event records are required for RQ6. `cumulative_ramp_labor` alone is
    insufficient because multiple governance regimes can incur similar total ramp
    labor through very different reassignment patterns.
    Team release caused by a completion that also surfaces a `MajorWinEvent`
    records `triggered_by = "completion"`. The major-win condition is captured in
    the separate `MajorWinEvent` log rather than by overloading the reassignment
    cause field.
- `idle_capacity_profile`:
  - `cumulative_idle_team_ticks`: total team-ticks during which teams were
    available but governance chose not to assign them to any initiative.
    Reported as an aggregate scalar and as a per-tick trace so the timing
    and duration of idle periods are visible.
  - `idle_team_tick_fraction`: `cumulative_idle_team_ticks` as a fraction of
    total available team-ticks over the run. This normalizes the metric across
    runs with different team counts and horizons.
  - `pool_exhaustion_tick`: the first tick, if any, at which all remaining
    unassigned initiatives were below the governance policy's activation
    threshold and at least one team was idle as a result. None if this
    condition never occurs.
- `cumulative_baseline_value`: total value credited across the run for
  teams on baseline. Each tick, idle (unassigned) teams accrue
  `ModelConfig.baseline_value_per_tick` per team. Runner-side
  accounting only — the engine does not consume this field. Default
  `baseline_value_per_tick` is `0.0`, so this is `0.0` for runs that
  don't enable baseline-value accounting; calibrated nonzero rate is
  `0.1`/tick. Pairs with `idle_capacity_profile` to distinguish
  "idle = wasted" runs (baseline=0) from "idle = on baseline"
  runs (baseline>0). Per governance.md "Baseline work semantics"
  and design_decisions.md decision 23.
- `exploration_cost_profile`:
  - `cumulative_labor_in_stopped_initiatives`: total team-ticks invested in
    initiatives that were stopped before completing.
    Reported in aggregate and broken down by generation label (flywheel,
    right-tail, enabler, quick-win) for interpretive disaggregation.
  - `cumulative_attention_in_stopped_initiatives`: total executive attention
    invested in initiatives that were stopped, reported in the same breakdown.
  - `completion_investment_profile`:
    - `cumulative_labor_in_completed_initiatives`: total team-ticks invested in
      initiatives that completed, reported in aggregate and broken down by
      generation label
    - `cumulative_attention_in_completed_initiatives`: total executive attention
      invested in initiatives that completed, reported in the same breakdown
    - `completed_initiative_count_by_label`: count of completed initiatives by
      generation label
    This profile is required for RQ4 and RQ5. Stopped-only labor is not enough to
    assess whether governance systematically underinvests in enablers or how
    total investment is distributed across the different value-creation
    mechanisms.
  - `latent_quality_distribution_of_stopped`: distribution of true latent quality
    among stopped initiatives. This distribution is the primary evidence for
    whether a governance regime made well-calibrated stop decisions or
    systematically stopped high-quality initiatives.
  - `stopped_initiative_count_by_label`: count of stopped initiatives by
    generation label.

**Reporting language note**: the output schema uses precise observational language
throughout. Initiatives that were stopped or that did not surface a major win are
described neutrally — not as failures. The
exploration cost profile above records the cost of the governance regime's
learning behavior neutrally. A governance regime that invested substantial labor
in right-tail initiatives that did not surface a major win is not a regime that
failed; it may be a regime that explored aggressively and incurred a real but
necessary cost for doing so. Whether that cost was justified given the return is
a question for analysis — it is not a label embedded in the output schema.
Likewise, completed-investment profiles are descriptive rather than evaluative:
high completed enabler investment is not assumed to be good or bad until it is
analyzed against value, major-win, and capability outcomes.
Implementations must not introduce evaluative language (fail, succeed, waste,
productive) into output field names, event types, or log entries.

### Business
Each simulation run produces a comprehensive set of structured outputs designed to support rigorous cross-regime comparison. These outputs fall into several families, each measuring a different dimension of governance performance. Together, they constitute the factual record of what happened under a given governance regime in a given opportunity environment.

### Cumulative economic performance

The primary economic output is the total cumulative value created over the simulation horizon — the sum of all value realized through every channel across the entire portfolio. This single number answers the most basic question: how much value did this governance regime produce?

But the total alone is insufficient. The study decomposes value by the mechanism that produced it:

- **One-time completion value.** The aggregate value realized from initiatives completing and delivering their immediate payoff. This is the "harvest" — the direct return on completed work.

- **Ongoing residual value.** The aggregate value accumulated from self-sustaining mechanisms that completed initiatives left behind — distribution networks, automation systems, marketplace platforms, and other structures that continue producing returns after the teams that built them have moved on. This is measured at the portfolio level (total residual value across all activated mechanisms) and also broken down by initiative family: how much residual value was produced by flywheel initiatives, by right-tail initiatives, by enablers, and by quick wins.

  In the canonical study, this decomposition is expected to be dominated by flywheel initiatives, which are specifically designed around persistent compounding returns. Quick wins may contribute a small residual tail, but their primary value mechanism is the one-time completion payoff. Enablers do not use a residual channel — their value is indirect, flowing through improved organizational capability. Right-tail initiatives realize their most consequential outcomes through major-win discovery events rather than through ordinary residual or one-time value. The breakdown is still reported for all families so the output structure matches the initiative pool design rather than embedding an assumption about which families will actually produce nonzero residual value.

This decomposition matters because two governance regimes can produce similar total value through structurally different mechanisms. A regime that generates most of its value from quick completion payoffs is doing something fundamentally different from one that builds a growing base of self-sustaining value streams — even if their terminal totals are comparable. The first is harvesting; the second is compounding. The distinction is invisible in a single total number but clearly visible in the channel decomposition.

- **Value by initiative family.** Cumulative value — combining both one-time completion payoffs and ongoing residual streams — broken down by initiative type (flywheel, right-tail, enabler, quick win). This enables family-level attribution of where a governance regime's value actually came from, without requiring the detailed per-week logs to be active.

### Major-win discovery performance

The study tracks governance's ability to surface genuinely transformational outcomes through several complementary measures:

- **Major-win count.** The number of major wins surfaced during the run — the count of right-tail initiatives that completed and turned out to be transformational.

- **Time to major win.** The distribution of how long it took to surface each major win, measured from the start of the simulation. For runs that produced multiple major wins, this captures the pacing of discovery.

- **Probability of major win.** The empirical fraction of runs (across replications with different random conditions) in which at least one major win was surfaced. This is the most basic measure of whether a governance regime reliably discovers transformational outcomes or only does so occasionally.

- **Major-win profile.** A richer set of discovery metrics including:
  - Major-win count broken down by initiative family — which types of initiatives produced the transformational outcomes.
  - Labor per major win — for governance regimes that produced at least one major win, the ratio of total labor invested in right-tail initiatives to the number of major wins surfaced. This measures discovery efficiency: how much exploratory investment was required per transformational outcome.
  - The detailed major-win event log (when event logging is enabled): the full structured record of each discovery event, as defined below under Event schemas.

### Belief accuracy

How well did the organization's evolving beliefs about initiative quality track the underlying truth? Two complementary measures are reported:

- **Mean absolute belief error.** The average gap between the organization's belief about each initiative's strategic quality and the initiative's true underlying quality, measured across every initiative at every week of active work throughout the run. This is a direct measure of how well-calibrated the organization's assessments were on average.

- **Mean squared belief error.** The same comparison, but squaring the errors before averaging. This measure penalizes large errors more heavily than small ones, making it more sensitive to cases where the organization's belief was dramatically wrong about a few initiatives rather than slightly wrong about many.

Both measures are computed from the detailed per-week records and use the true underlying quality — information that governance never sees during the run but that is available for post-hoc analysis.

- **Quality distribution of stopped versus major-win initiatives.** The distribution of true underlying quality among initiatives that governance chose to stop, compared with initiatives that turned out to be major wins. This is the most direct evidence of whether governance's stop decisions were well-targeted: a well-calibrated regime should be stopping mostly low-quality initiatives, while a poorly calibrated one will show high-quality initiatives in its stopped population.

### Organizational capability

- **Terminal portfolio capability.** The organization's accumulated learning capability at the final week of the run — the stock of enabler-driven improvement available for evaluating future work. This is a dimensionless measure starting at 1.0 (baseline) and bounded by a configured maximum. Higher values mean the organization would evaluate future initiatives with less noise and greater precision. A governance regime that neglected enabler work will show terminal capability near 1.0; one that invested heavily in enablers and saw them through to completion will show materially higher values.

- **Peak portfolio capability.** The highest level of organizational capability reached at any point during the run. This complements the terminal value because capability decays over time between enabler completions. A regime that completed several enablers in the middle of the run may have operated at high capability for an extended period — benefiting from cleaner signals and better stop/continue decisions — even if capability had partially decayed by the final week. The peak captures the maximum organizational benefit that was active during the run; the terminal value captures what remains at the end. These measure different things. Do not combine them into a single composite — any analysis requiring a composite must define its weighting explicitly.

### Residual momentum at horizon

- **Terminal aggregate residual rate.** The sum of all active ongoing value stream rates at the final week of the run — how much value per week the portfolio's self-sustaining mechanisms were collectively producing at the moment the measurement window closed. This is the "flywheel momentum" the governance regime leaves behind: the rate at which value would continue accumulating if the simulation were extended beyond the horizon, before accounting for decay. A regime that built and completed many flywheel initiatives will show a high terminal residual rate; one that focused on quick wins or stopped flywheels before completion will show a low one.

  The terminal residual rate is measured in value per week. The terminal capability is a dimensionless scalar. These two quantities are not comparable and must not be aggregated into a single composite. Any downstream analysis that needs to combine them must define its own weighting with explicit awareness of the dimensional mismatch.

### Switching cost and ramp labor

- **Cumulative ramp labor.** The total team-weeks consumed during ramp-up periods — the productivity cost incurred every time a new team is assigned to an initiative and operates at reduced learning efficiency during the transition. This is the aggregate switching cost. Governance regimes that frequently stop and reassign teams will show higher ramp labor than regimes that make fewer but more committed assignments.

- **Ramp labor fraction.** The ramp labor expressed as a fraction of total available team-weeks over the run, ranging from zero to one. This normalizes the switching cost so it can be compared across runs with different team sizes and horizons. A ramp labor fraction of 0.15 means that 15% of the organization's total productive capacity was consumed by transition overhead rather than by steady-state work.

### Reassignment patterns

- **Reassignment event count.** The total number of team reassignments during the run — how many times a team was moved from one initiative (or from idle) to a new one.

- **Reassignment event log** (when event logging is enabled). A detailed record of every reassignment, capturing: when it happened, which team moved, where it came from (which initiative, or idle), where it went, and what triggered the move — whether governance stopped the previous initiative, the previous initiative completed naturally, or the team was idle and being deployed for the first time. These records are essential for understanding governance dynamics. Two regimes can incur similar total switching costs through very different reassignment patterns — one through aggressive stop-and-redeploy behavior, the other through a steady stream of natural completions — and the aggregate switching cost alone cannot distinguish them.

  When a team is released because an initiative completed and that completion also surfaced a major win, the reassignment is recorded as triggered by completion. The major-win aspect is captured in the separate major-win event log rather than by overloading the reassignment record, keeping the two event streams clean and independently queryable.

### Family timing profiles

Timing metrics organized by initiative family, designed to reveal how governance pacing differs across initiative types:

- **First completion by family.** For each initiative family (flywheel, right-tail, enabler, quick win), the week at which the first initiative of that type completed. This reveals whether a governance regime prioritizes early completions of certain types — for example, completing quick wins first to free teams, or prioritizing enablers early to build capability for the rest of the run.

- **Average completion timing by family.** The mean completion week for each family, capturing the center of gravity of when different types of work reach completion.

- **All completion timings by family.** The complete list of completion weeks for each family, preserving the full distribution rather than just the average.

- **Peak capability timing.** The week at which organizational capability reached its maximum — revealing when the enabler investments had their greatest cumulative effect.

- **First right-tail stop timing.** The week of the first right-tail initiative stop, if any. This is an early indicator of governance patience: an impatient regime will show early right-tail stops; a patient one may show none or only late stops.

### Frontier summary

For runs using the dynamic opportunity frontier — where stopped right-tail opportunities can be retried with fresh approaches — the output includes a per-family summary of frontier exhaustion state at the end of the run: how many opportunities have been resolved, how many frontier draws have occurred, and the current effective quality adjustment for repeated attempts. This is reported as absent for fixed-pool runs where the dynamic frontier is not active.

### Per-initiative weekly detail log

When detailed per-week logging is enabled, the simulation records a comprehensive snapshot for every active initiative at every week of the run. Each record captures:

- The simulation week and initiative identifier.
- The initiative's current lifecycle state.
- The organization's current strategic quality belief — what governance sees and uses for decisions.
- The initiative's true underlying quality — available only for post-hoc analysis, never visible to governance during the run.
- The executive attention level applied to the initiative that week. This is the realized attention after engine validation, not merely what governance proposed. Because the study's attention contract treats omission as zero, this field is never missing for an active initiative: an initiative that governance did not mention in its attention allocation records zero attention for that week, not a carryover of whatever it received previously.
- The effective signal noise for that initiative on that week — the actual noise level governing how informative the strategic evidence was, after accounting for dependency, attention, and organizational capability. This makes the entire signal path directly auditable for analysis of how attention allocation affects stop/continue decision quality.
- The execution belief, if applicable — how well governance believes the initiative is tracking to plan.
- Whether the initiative is currently in its ramp period (the team is newly assigned and operating at reduced learning efficiency), and if so, the current ramp productivity multiplier.

These detailed records are the primary input for two of the study's most important analytical questions: how accurately do governance beliefs track true initiative quality across different regimes, and how does executive attention allocation interact with termination decisions — specifically, whether initiatives that received too little attention earlier were more likely to be stopped later because their belief estimates were noisier and more likely to drift below stop thresholds.

### Portfolio-level weekly trace

Alongside the per-initiative detail, the simulation records a portfolio-level snapshot at each week when detailed logging is enabled:

- The simulation week.
- The current organizational capability level — required for analyzing how enabler investment translates into portfolio-wide learning improvement over time.
- The count of currently active initiatives.
- The count of idle teams — teams available but not assigned.
- The total executive attention allocated across the portfolio that week — the sum across all initiatives, not the per-initiative breakdown (which is in the per-initiative log).

The distinction between these two log levels matters for analysis. Per-initiative records capture what happened to each initiative individually and are the source for belief accuracy analysis, attention-termination interaction analysis, and cost-projection sensitivity analysis. The per-initiative attention field in that log is the attention received by one initiative. The portfolio trace captures aggregate state only; the total attention field there is the portfolio sum. Analyses requiring per-initiative attention histories must use the per-initiative records, not the portfolio trace. And because attention does not carry forward between weeks unless governance explicitly re-allocates it, attention histories must be interpreted week by week rather than as a persistent state.

### Idle capacity profile

- **Cumulative idle team-weeks.** The total team-weeks during which teams were available but governance chose not to assign them to any initiative. Reported both as an aggregate total and as a per-week trace so the timing, duration, and pattern of idle periods are visible — not just their total magnitude.

- **Idle team-week fraction.** The idle team-weeks expressed as a fraction of total available team-weeks over the run. This normalizes across runs with different workforce sizes and horizons, enabling direct comparison of how much productive capacity different governance regimes left on the table.

- **Pool exhaustion timing.** The first week, if any, at which all remaining unassigned initiatives fell below the governance regime's activation threshold and at least one team was idle as a result. This marks the point at which governance judged the remaining opportunity pool unattractive enough that deploying against it would be worse than deploying nothing — a significant structural event in the run. Absent if this condition never occurs.

### Exploration cost profile

How much did the governance regime invest in work that did not ultimately produce value? And how was total investment distributed across the different types of initiatives? These measures capture the cost side of governance behavior.

- **Cumulative labor in stopped initiatives.** The total team-weeks invested in initiatives that governance stopped before they could complete. Reported in aggregate and broken down by initiative family (flywheel, right-tail, enabler, quick win) so the study can identify whether a governance regime's exploration cost was concentrated in one type of work or spread broadly.

- **Cumulative attention in stopped initiatives.** The total executive attention invested in initiatives that were ultimately stopped, reported in the same aggregate and per-family breakdown.

- **Completion investment profile.** The mirror image of exploration cost: how much was invested in initiatives that did complete?
  - Cumulative labor in completed initiatives, in aggregate and by family.
  - Cumulative attention in completed initiatives, in aggregate and by family.
  - Count of completed initiatives by family.

  This profile is essential for understanding whether governance systematically underinvests in certain types of work — particularly enablers — and how total investment is distributed across the different value-creation mechanisms. Knowing only what was spent on stopped work is not enough; the study needs the complete investment picture.

- **True quality distribution of stopped initiatives.** The distribution of true underlying quality among initiatives that governance chose to stop. This is the most direct measure of stop-decision calibration: a well-calibrated governance regime should be stopping mostly low-quality initiatives. If the stopped population contains a significant number of high-quality initiatives, governance was systematically terminating work that would have been worth continuing — the clearest evidence of premature termination.

- **Stopped initiative count by family.** The number of stopped initiatives broken down by type, enabling analysis of whether a governance regime's termination pattern was concentrated in specific initiative families.

**A note on reporting language.** The output schema uses precise, observational language throughout. Initiatives that were stopped or that did not surface a major win are described neutrally — not as failures, not as waste, not as mistakes. A governance regime that invested substantial labor in right-tail initiatives without surfacing a major win is not a regime that failed. It may be a regime that explored aggressively and incurred a real but necessary cost for doing so. Whether that cost was justified given the return is a question for analysis — it is not a judgment embedded in the output fields.

The same principle applies in the other direction. High completed enabler investment is not assumed to be good, and high stopped right-tail investment is not assumed to be bad. These are facts about what the governance regime did. Whether those choices were wise depends on the outcomes they produced, and that assessment belongs to the analysis layer, not to the reporting layer.

Implementations must not introduce evaluative language — fail, succeed, waste, productive, efficient, inefficient — into output field names, event types, or log entries. The output schema describes; it does not judge.

### Trajectory figures (per-condition)

When per-tick logging is enabled (`record_per_tick_logs: true`), the bundle
includes trajectory figures for each experimental condition:

- **`trajectory_beliefs_<condition_id>.png`** — Multi-subplot figure with one
  row per representative initiative. Shows quality belief evolution over time
  alongside the latent quality reference line. Includes ramp-period shading,
  stop/completion markers, major-win stars, and executive attention as a
  secondary axis.

- **`trajectory_overlay_<condition_id>.png`** — Single-panel overlay of all
  representative initiatives on shared axes. Quick visual comparison of
  belief convergence patterns across initiative families.

Representative initiatives are automatically selected to cover all families:
one flywheel (moderate quality, completed), one right-tail high quality (major-
win candidate), one right-tail low quality (correctly stopped), one enabler,
and one quick-win.

## Idle capacity and pool exhaustion


### Academic
A governance regime may exhaust its fundable set before the simulation horizon.
This occurs when all remaining unassigned initiatives fall below the policy's
activation threshold and no active initiative is worth stopping to free a team
for reassignment. When this happens, governance leaves teams idle — emitting
`AssignTeam` with `initiative_id=null` — and the engine continues ticking.
Residual streams remain active and continue producing value; the portfolio simply
stops growing.

Idle team-ticks are a first-class output, not an edge case. A governance regime
that holds capacity idle for a sustained period is making an observable and
analytically significant choice: it judges the remaining opportunity pool
unattractive enough that deploying against it would be worse than deploying
nothing. Two regimes that produce similar cumulative value may differ sharply in
idle capacity — one arriving at the horizon with teams still active, the other
having held capacity idle for a substantial fraction of the run. That difference
is evidence about governance selectivity and must be visible in the output.

Total labor endowment is fixed for the duration of a simulation run and is an
environmental quantity; the realized team pool (how that labor is decomposed
into teams) is fixed within a run and is a governance-architecture choice (see
`study_overview.md` and `team_and_resources.md`). The simulation does not model
hiring, firing, or mid-run changes to either. In a real organization, leadership
might respond to pool exhaustion by reducing headcount or redeploying people to
non-portfolio work. The simulation does not model that response. Similarly,
active investment in opportunity-pipeline replenishment — generating new
proposals to replace resolved ones — is outside the canonical fixed-pool model's
scope (the dynamic opportunity frontier extension partially relaxes this
constraint for right-tail initiatives, but general pipeline replenishment is not
modeled). Idle team-ticks
therefore represent a real opportunity cost that accumulates in the output and is
available for cross-regime comparison, but the model makes no normative judgment
about whether holding capacity idle is better or worse than deploying against
weak opportunities. That question is left to analysis. In particular, sustained
idle capacity is ambiguous between two interpretations: optimal restraint given
the realized opportunity set, and suboptimal selectivity that fails to identify
fundable opportunities a more discriminating policy would pursue. The analysis
layer, not the output schema, disambiguates.

### Business
A governance regime may exhaust its supply of attractive opportunities before the simulation horizon. This occurs when all remaining unassigned initiatives fall below the regime's threshold for activation — none of them look promising enough to deploy a team against — and no currently active initiative is worth stopping to free a team for redeployment. When this happens, governance leaves teams idle, and the simulation continues. Ongoing value streams from previously completed work remain active and continue producing returns; the portfolio simply stops growing through new completions.

Idle team-weeks are a first-class output of the study, not an edge case or an error condition. A governance regime that holds productive capacity idle for a sustained period is making an observable and analytically significant choice: it judges the remaining opportunity pool unattractive enough that deploying against it would produce less value than deploying nothing. This is a real governance posture — some organizations do exactly this when their pipeline weakens, preferring to hold capacity in reserve rather than staffing marginal projects.

Two regimes that produce similar cumulative value may differ sharply in how much capacity they held idle. One might arrive at the horizon with all teams still actively deployed. The other might have held teams idle for a substantial fraction of the run, having exhausted its fundable opportunities early. That difference is evidence about governance selectivity — how discriminating the regime was about which opportunities to pursue — and it must be visible in the output.

The total workforce is fixed for the duration of a simulation run and is treated as an environmental condition — something governance must take as given. How that workforce is organized into teams is a governance-architecture choice, also fixed within a run. The simulation does not model hiring, firing, or mid-run workforce adjustments. In a real organization, leadership facing an exhausted pipeline might reduce headcount, redeploy people to non-portfolio work, or invest in building a stronger pipeline. The simulation does not model any of those responses.

Idle team-weeks therefore represent a real opportunity cost that accumulates in the output and is available for cross-regime comparison. But the model makes no normative judgment about whether holding capacity idle is better or worse than deploying it against weak opportunities. A regime that holds teams idle rather than staffing marginal projects may be exercising sound discipline — or it may be failing to recognize opportunities that a more perceptive regime would pursue. That question is left to analysis, not embedded in the output.

## Terminal state at horizon


### Academic
When the simulation reaches `tick_horizon`, no lifecycle transitions are induced
by horizon expiry. The runner records the terminal state of every initiative,
every team, and the current portfolio capability `C_t` as the final snapshot of
the run. Specifically:

- Initiatives still in `active` state remain `active`. Their terminal beliefs,
  staffed progress, cumulative value by channel, and residual activation status
  are recorded as-is.
- Initiatives that reached `completed` during the run
  have their terminal residual stream rates recorded in `terminal_aggregate_residual_rate`.
- `terminal_capability_t` records the portfolio learning-capability scalar at the final tick.
  `terminal_aggregate_residual_rate` records the sum of active residual rates at
  the final tick. These two fields are dimensionally incompatible (scalar vs.
  value/tick) and must not be combined into a single composite metric.
- Initiatives still `active` at the horizon contribute to the terminal picture
  as ongoing investments, not as incomplete or abandoned work. Their terminal
  state is evidence about what the governance regime was still building at the
  end of the measurement window. Two governance regimes may produce similar
  cumulative value during the horizon while one has three healthy flywheels
  still running and the other has none; that difference is analytically
  significant and must be visible in the output.

The horizon is a measurement boundary, not a lifecycle event. This principle
must be enforced in the runner, not just documented here.

### Business
When the simulation reaches the end of its measurement window, no lifecycle transitions are triggered by the horizon itself. The simulation does not force-complete active initiatives, does not stop them, and does not treat the horizon as a deadline that changes initiative behavior. The horizon is a measurement boundary — the point at which the study stops observing — not a lifecycle event that the simulated organization experiences.

The runner records the terminal state of every initiative, every team, and the current organizational capability as the final snapshot of the run. Specifically:

- Initiatives still in active state at the horizon remain active. Their terminal beliefs, accumulated staffed progress, cumulative value by channel, and residual activation status are recorded exactly as they stand. These initiatives are ongoing investments at the moment the measurement window closes — they are not incomplete or abandoned work. Their terminal state is evidence about what the governance regime was still building when observation ended.

- Initiatives that completed during the run have their terminal ongoing value stream rates recorded in the aggregate residual rate — the combined output of all self-sustaining mechanisms at the final week.

- Terminal organizational capability records the portfolio learning-capability level at the final week — how much enabler-driven improvement the governance regime has accumulated and retained.

- The terminal aggregate residual rate records the combined flow of all active ongoing value streams at the final week — the flywheel momentum the regime leaves behind.

These two terminal quantities — organizational capability and residual rate — are dimensionally incompatible. Capability is a dimensionless scalar measuring learning precision. Residual rate is measured in value per week. They must not be combined into a single composite metric.

Two governance regimes may produce similar cumulative value during the horizon while leaving the organization in very different terminal states. One may have three healthy flywheel initiatives still running and a high residual rate; the other may have none. One may have invested in enablers and built high organizational capability; the other may be at baseline. These differences are analytically significant — they represent the organization's trajectory beyond the measurement window — and must be clearly visible in the output. This principle must be enforced in the simulation runner, not merely documented.

## Event schemas


### Academic
#### MajorWinEvent

The canonical `MajorWinEvent` payload is defined in `initiative_model.md` under
"Major-win event state." It is emitted when a right-tail initiative completes and
surfaces a major win. Event records are collected under `record_event_log`.

`MajorWinEvent` is a first-class analytical output. It must be queryable without
reconstructing surfaced major wins indirectly from initiative terminal states or
from cumulative aggregates. Any run-level major-win summary (`major_win_count`,
`time_to_major_win`, `probability_of_major_win`, `labor_per_major_win`) must be
derivable directly from this event stream.

#### StopEvent

`StopEvent` is emitted when the engine executes a `Stop` decision — that is, when
a governance `ContinueStop(stop)` action causes an initiative to transition to
`stopped`. One record per executed stop.

```
StopEvent:
    tick:                       int
    initiative_id:              str
    quality_belief_t:           float    — strategic quality belief at time of stop
    execution_belief_t:         float | None  — execution belief at time of stop;
                                                None if initiative has no
                                                planned_duration_ticks
    latent_quality:             float    — post-hoc; not observable during run
    triggering_rule:            str      — one of: "tam_adequacy" | "stagnation" |
                                           "confidence_decline" |
                                           "execution_overrun" | "discretionary"
                                           (governance policy sets this field in
                                           the Stop action; engine records it here)
    cumulative_labor_invested:  float    — team-ticks × team_size up to stop tick
    staffed_ticks:              int
    governance_archetype:       str      — policy_id from GovernanceConfig
```

The `triggering_rule` field requires governance policies to self-report the reason
for each stop. Valid values correspond to the canonical stop rules defined in
`governance.md`: "tam_adequacy", "stagnation", "confidence_decline", and
"execution_overrun". Use "discretionary" for policy-specific or mixed logic not
captured cleanly by one named rule. The `latent_quality` field enables post-hoc
analysis of whether stopped initiatives had high or low true quality — the
primary evidence for whether governance made well-calibrated stop decisions.

The addition of `"execution_overrun"` is intentional. Cost-sensitive governance
is a core comparative dimension in the study, and folding pure overrun-driven
stops into `"discretionary"` would unnecessarily blur a distinction the model
already represents explicitly in its observable state.


### Business
### Major-win discovery event

The canonical major-win event record is defined in the initiative model under major-win event state. It is emitted when a right-tail initiative completes and reveals itself to be a genuinely transformational outcome. Event records are collected when event logging is enabled for the run.

The major-win event is a first-class analytical output. It must be directly queryable — an analyst must be able to retrieve the full list of major-win discoveries, with all their associated detail, without having to reconstruct them indirectly from initiative terminal states or cumulative aggregates. Every run-level major-win summary — how many were discovered, how long they took, the probability of discovery, the labor invested per discovery — must be derivable directly from this event stream.

### Stop event

A stop event is emitted every time governance's stop decision is executed — every time an initiative transitions from active to stopped. One record per stop. Each record captures:

- **When:** the simulation week at which the stop occurred.
- **Which initiative:** the initiative identifier.
- **What governance believed at the time:** the organization's strategic quality belief at the moment of the stop — what governance thought about the initiative's prospects when it decided to terminate. Also the execution belief, if the initiative had an execution timeline — what governance believed about schedule fidelity. If the initiative had no planned duration, this field is absent.
- **What was actually true:** the initiative's true underlying quality — available only for post-hoc analysis, never visible to governance during the run. This is the primary evidence for whether governance made a well-calibrated stop decision: did it stop a low-quality initiative (correct termination) or a high-quality one (premature termination)?
- **Why governance stopped it:** the specific rule that triggered the stop, as self-reported by the governance policy. Valid reasons correspond to the canonical stop rules: bounded-prize patience exhaustion, informational stagnation, confidence decline, and execution overrun. The "discretionary" category is used when the stop was driven by mixed considerations or policy-specific logic that does not map cleanly to one named rule.
- **How much was invested:** the total labor (team-weeks, accounting for team size) invested in the initiative up to the stop, and the total number of staffed weeks.
- **Which governance regime made the decision:** the policy identifier from the governance configuration.

The explicit inclusion of execution overrun as a distinct triggering category is intentional. Cost-sensitive governance is a core comparative dimension of the study. A governance regime that stops initiatives primarily because of cost escalation is making fundamentally different decisions than one that stops primarily because of loss of strategic conviction. Folding pure overrun-driven stops into the "discretionary" category would blur a distinction that the model already represents explicitly and that the study needs to analyze.

The triggering-rule requirement ensures that post-hoc analysis can disaggregate every governance regime's termination pattern by the reason behind each stop. This enables direct comparison: does one regime stop mostly for confidence decline while another stops mostly for stagnation? Does a cost-sensitive regime stop right-tail initiatives earlier than a conviction-driven one, and if so, does that affect major-win discovery rates? These questions require knowing not just that governance stopped an initiative, but why.

## Manifest & provenance

### Academic
- The runner records:
  - `world_seed`
  - resolved `initiatives` list and generator parameters
  - governance policy version identifier
  - per-tick logs and any rejected actions
  - full `GovernanceConfig` parameter values as a flat metadata record, so that
    sweep analysis can slice and aggregate runs by parameter values rather than
    only by named policy identifier. The policy identifier alone is insufficient
    for sweep experiments where thousands of distinct parameter configurations
    are evaluated. Required fields in the flat record are: `policy_id`,
    `theta_stop`, `theta_tam_ratio`, `T_tam`, `W_stag`, `epsilon_stag`,
    `attention_min`, `attention_max`, and `exec_overrun_threshold`.
  - full environmental configuration as a flat metadata record, recording the
    parameter values that define the opportunity environment for the run:
    initiative pool composition, quality distribution parameters, dependency
    distribution parameters, ramp period, and attention curve parameters
    (`a_min`, `k_low`, `k`, `g_min`, `g_max`). This is required so that results
    can be correctly attributed to governance versus environment in sweep analysis.
    Without the environmental parameter record, an apparent governance effect may
    be confounded with an environmental effect, and the study would have no
    mechanism to distinguish the two.
- Manifest is stored as machine-readable JSON for reproducibility. The
  reproducibility contract is strict: any analyst — human or automated — must be
  able to take a manifest and reproduce the exact run that produced it, yielding
  identical outputs.

### Business
Every simulation run produces a machine-readable manifest recording everything needed to reproduce the run and attribute its results correctly. The manifest includes:

- **The world seed** — the single value from which all randomness in the run is deterministically derived.
- **The complete resolved initiative pool** — every initiative with all its concrete attributes — and the generator parameters that produced it, so the pool can be regenerated and verified independently.
- **The governance policy version** — which specific governance regime was tested, identified precisely enough to distinguish it from every other regime in the study.
- **Per-week logs and rejected actions** — the complete operational record, including any governance decisions that the engine rejected due to constraint violations (budget overruns, infeasible team assignments).
- **The full governance configuration as a flat parameter record** — not just the policy name, but every individual parameter value: the confidence decline threshold, the bounded-prize patience ratio, the base patience window, the stagnation window length, the stagnation detection threshold, the minimum and maximum attention levels, and the execution overrun threshold. This flat record is essential for sweep experiments where thousands of distinct parameter configurations are evaluated. The policy name alone is insufficient because it does not distinguish between configurations that share a policy structure but differ in their parameter settings.
- **The full environmental configuration as a flat parameter record** — every parameter value that defines the opportunity environment: initiative pool composition, quality distribution parameters, dependency distribution parameters, the ramp period, and all attention-to-signal curve parameters (the minimum attention threshold, the below-threshold noise amplification rate, the above-threshold noise reduction rate, and the floor and ceiling on the attention noise modifier). This is required so that results can be correctly attributed to governance choices versus environmental conditions in sweep analysis. Without it, a finding that appears to be about governance may actually be about the opportunity environment, and the study would have no way to distinguish the two.

The manifest is stored as machine-readable structured data for reproducibility. Any analyst — human or automated — must be able to take a manifest and reproduce the exact run that produced it.

## Reporting by labels

### Academic
- Labels are used to aggregate results (e.g., median time to major win for right-tail initiatives) but aggregation code reads label metadata only. The engine's internal logic is label-agnostic.

Specific uses in the output surface include: `residual_value_by_label`
decomposes realized residual value by `generation_tag`, `exploration_cost_profile`
disaggregates stopped-initiative labor and attention by label,
`family_timing` reports completion timing per label, and
`stopped_initiative_count_by_label` and `completed_initiative_count_by_label`
break down termination and completion counts by family.

The labels serve the same function in reporting that they serve at pool
generation: they are generator-side metadata over resolved initiative attributes
and value-channel configurations, not engine-level type discriminants. The
analytical validity of the output surface depends on the resolved attributes and
value channels consumed by the engine, not on the stability or correctness of the
label taxonomy. If labels were renamed, reorganized, or extended, the
engine-produced outputs would be unchanged; only the aggregation-key values in
derived reporting artifacts would differ.

### Business
Initiative type labels — flywheel, right-tail, enabler, quick win — are used in the output to organize and aggregate results. For example, the median time to major win is computed across right-tail initiatives; the residual value breakdown reports totals by family; the exploration cost profile disaggregates stopped-initiative investment by type.

All aggregation code reads these labels as reporting metadata only. The simulation engine's internal logic never branches on them. The labels serve the same role in reporting that they serve in scenario design: they are organizational shorthand that helps human analysts and governance practitioners recognize patterns in the results in terms they use to think about their own portfolios. The analytical validity of the output does not depend on the labels being correct or stable — it depends on the underlying initiative attributes and value channel configurations, which are what the engine actually processes.
