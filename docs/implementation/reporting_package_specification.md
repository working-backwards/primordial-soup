# Reporting Package Specification

## Purpose

This document specifies the canonical **run bundle** and **report package** for the Primordial Soup study.

Its purpose is to define:

* the on-disk artifact produced by a top-level simulation or experiment execution,
* the canonical machine-readable outputs required for rerun, audit, and ad hoc analysis,
* the generated human-facing report package,
* and the reporting terminology and artifact boundaries used by the reporting layer.

This document is about the **observational and reporting contract**, not simulator mechanics or experiment design. Reporting is the evidentiary substrate for deterministic summaries, exploratory interpretation, AI-assisted analysis, and follow-up experiment design, not the place where simulator behavior or study design are redefined.

The reporting package must support both perspectives that govern the study:

* an **academic** perspective that requires reproducibility, stable semantics, clear provenance, and analyzable output contracts;
* a **business executive** perspective that requires readable summaries, clear visual tradeoffs, and evidence tied to recognizable managerial questions.

The report package is therefore a methodological component of the study, not a cosmetic add-on. The study’s lessons learned are explicit that the work should be designed from both perspectives throughout, and that readability and bridge artifacts are methodological requirements.

## Scope

This specification covers:

* terminology for reporting artifacts,
* run-bundle structure,
* report-package structure,
* canonical storage formats,
* manifest and provenance requirements,
* required output tables and traces,
* required figures and summaries,
* and validation rules for reporting completeness.

This specification does **not** define:

* simulator mechanics,
* governance decision logic,
* experiment design,
* or downstream LLM interpretation workflows.

Those belong elsewhere in the corpus. In particular, experiment structure already distinguishes **environmental conditions**, **governance architecture**, and **operating policy**, and this reporting spec reuses that terminology rather than inventing a parallel vocabulary.

## Terminology rule

This document adopts existing study terminology wherever possible.

New terms are introduced only for reporting-artifact concepts that do not already have a clean home in the design corpus. If a term is already defined clearly in the study design, this document should reuse it rather than introduce a parallel synonym.

This document is the designated home for **reporting terminology** and **reporting artifact boundaries**. Other documents may use these terms, but should defer to the definitions here rather than restating or modifying them.

## Inheritance rule for study taxonomies and presets

The reporting package must **inherit** study-defined taxonomies, preset labels, and grouping vocabularies from the run configuration and realized input state. It must not define them independently or assume that every current preset label is universally required.

This does **not** prohibit the reporting schema from using fixed field names for **stable study concepts** that are central to the observational and reporting contract. A concept may remain a stable reporting concept even if its numeric calibration changes across study versions.

For the current study, examples of stable reporting concepts include:

* `right_tail`
* `major_win`
* `terminal_capability`
* `false_stop_rate`

By contrast, named presets such as specific governance archetype names or environment-preset names should usually appear as inherited metadata values rather than being hard-coded as permanent schema fields.

More specifically:

* **Initiative types / labels** such as `flywheel`, `right_tail`, `enabler`, and `quick_win` are generator- and reporting-layer classifications. They are used to define priors and presets and to tag initiatives for analysis, but the engine operates on resolved initiative records with concrete immutable attributes.
* **Named governance archetypes** such as `Balanced`, `Aggressive Stop-Loss`, and `Patient Moonshot` are study presets for governance configuration. They are inherited from the run bundle and may be used in reports, but the reporting system must not assume they are the only valid governance regimes.
* **Named environment families** such as `balanced_incumbent`, `short_cycle_throughput`, and `discovery_heavy` are study presets for environmental conditions. They are inherited from the run bundle and may be used in reports, but the reporting system must not assume they are the only valid environmental conditions.

The reporting layer should therefore distinguish between:

* **core simulator primitives** recorded in resolved configurations and initiative records, and
* **study-level preset vocabulary** used for generation, tagging, grouping, and explanation.

Where a report uses study-level labels, those labels must be loaded from the run bundle’s resolved configuration or realized input state rather than hard-coded into reporting logic.

The reporting package must be able to render current canonical study presets directly and readably. However, it must do so by consuming preset metadata from the run bundle, not by assuming a fixed permanent vocabulary in its core schema.

Any grouping or chart keyed to initiative families, named governance archetypes, or named environment families must degrade gracefully if a future run bundle uses a different study taxonomy.

## Glossary

**Run bundle**
The canonical on-disk artifact produced by one top-level execution of a simulation or experiment script. A run bundle is self-contained: it stores the exact resolved configuration, initial state snapshots, provenance, raw outputs, derived outputs, figures, and generated report package needed to rerun, audit, or analyze that execution later.

**Report package**
The human-facing subset of a run bundle. It includes the generated HTML report, companion markdown, figures, and summary tables intended for direct reading. The report package is derived from canonical data artifacts and is never the sole source of truth.

**Experiment**
A top-level study execution. An experiment compares governance regimes under specified environmental conditions, governance architecture, and operating-policy settings. Some studies may refer to this as a campaign. This reporting specification prefers **experiment**.

**Experimental condition**
One evaluated combination of environmental conditions, governance architecture, and operating policy inside an experiment. Where the experiment design uses sweep language, this corresponds to one experimental cell. This reporting specification prefers **experimental condition** in prose and allows **cell** as a compact table or index label when needed. The experiment design already states that each governance-regime and environmental-configuration combination is a distinct experimental cell.

**Governance regime**
The comparative governance posture being studied. In practice, a governance regime may refer either to a named anchor archetype or to a sampled governance configuration, depending on context. Reporting should preserve this term.

**Environmental conditions**
The world the governance regime faces. In the experiment design, this is already a canonical layer of variation and should be used unchanged in reporting.

**Governance architecture**
The pre-run structural organization of labor and standing portfolio guardrails. This is an existing experimental-design term and should be used unchanged in reporting.

**Operating policy**
The recurring tick-by-tick decision logic. This is an existing experimental-design term and should be used unchanged in reporting.

**Seed run**
One Monte Carlo realization of a single experimental condition under a specific `world_seed`. Distinct `world_seed` values are the independent stochastic worlds; repeating the same `world_seed` with the same resolved configuration is a replay, not a new observation.

**Initial state snapshot**
The stored realized starting world for a seed run, including the resolved initiative set and any other state needed for exact replay or post hoc analysis.

**Canonical data artifact**
A machine-readable file inside the run bundle designated as authoritative for a specific reporting surface, such as manifest metadata, seed-run summaries, experimental-condition summaries, yearly time series, event logs, or diagnostics.

**Derived artifact**
A file computed from canonical data artifacts, such as pairwise deltas, charts, diagnostic flags, summary markdown, or HTML pages.

## Artifact hierarchy

The reporting layer uses the following hierarchy.

### 1. Run bundle

The outermost artifact. One top-level script execution produces one run bundle.

A run bundle may contain:

* one experiment with a single experimental condition and multiple seed runs, or
* one experiment with multiple experimental conditions and multiple seed runs per condition.

For example, a script that evaluates three governance regimes across three environmental conditions with seven shared seeds produces:

* one run bundle
* containing one experiment
* with nine experimental conditions
* and sixty-three seed runs

This structure matches the existing experiment design, which treats governance-regime comparisons across multiple environmental configurations as first-class experimental structure rather than as separate unrelated artifacts.

### 2. Experiment

The experimental design executed inside the run bundle.

The experiment layer records:

* which environmental conditions were included,
* which governance architecture was fixed or varied,
* which operating policies or named governance regimes were included,
* which seed set was used,
* and which comparison structure the report package should present.

### 3. Experimental condition

One evaluated condition inside the experiment.

An experimental condition is typically the unit summarized in top-level comparison tables and charts. It is also the natural grouping key for aggregating seed runs into means, medians, confidence intervals, and other summary statistics.

### 4. Seed run

The atomic stochastic execution unit.

Seed runs are the basis for:

* empirical probability estimates,
* confidence intervals,
* seed-level diagnostics,
* representative-run selection,
* and exact replay.

## Naming rule

The reporting package should avoid using the bare word **run** by itself in schemas, field names, and artifact labels when the level is ambiguous.

Prefer the more specific terms:

* `run_bundle`
* `experiment`
* `experimental_condition`
* `seed_run`

This guards against semantic drift. The study’s lessons learned are explicit that unstable vocabulary is more dangerous than obvious software bugs because it preserves execution while corrupting interpretation.

## Run-bundle structure

A run bundle is the canonical on-disk artifact produced by one top-level execution of a simulation or experiment script. It must be self-contained enough to support:

* rerun from resolved configuration,
* replay or reanalysis of the realized starting world,
* deterministic report regeneration,
* ad hoc analysis without reconstructing hidden context,
* and human-readable review through the report package.

The run bundle is the system of record for reporting. The report package is derived from it and must never contain information that cannot be traced back to canonical artifacts in the run bundle.

### Design requirements

Every run bundle must satisfy the following requirements:

1. **Self-containment**
   The bundle must contain the resolved configuration, provenance, output data, and generated report artifacts needed to understand and reproduce the execution later.

2. **Separation of canonical vs derived artifacts**
   Canonical machine-readable outputs must be distinguishable from derived artifacts such as charts, HTML, markdown summaries, and pairwise comparison tables.

3. **Support for both rerun modes**
   The bundle must support:

   * rerun from configuration and seed, and
   * analysis of the exact realized starting world used in the execution.

4. **Stable artifact boundaries**
   Each major reporting concept must have one designated home.

5. **Readable from both academic and executive perspectives**
   The bundle must support reproducible quantitative analysis and also a report package that translates results into an intelligible managerial view.

### Bundle granularity

One top-level script execution produces one run bundle.

A run bundle may represent:

* one experiment with one experimental condition and multiple seed runs, or
* one experiment with multiple experimental conditions and multiple seed runs per condition.

### Required directory layout

```text
results/
  <run_bundle_id>/
    manifest.json

    config/
      run_spec.json
      simulation_config.json
      governance_architecture.json
      operating_policies.json
      environmental_conditions.json
      reporting_config.json

    inputs/
      seed_manifest.json
      initial_state_index.parquet
      initial_state_snapshots/
        <experimental_condition_id>__seed_<seed>.parquet

    outputs/
      experimental_conditions.parquet
      seed_runs.parquet
      family_outcomes.parquet
      yearly_timeseries.parquet
      initiative_outcomes.parquet
      diagnostics.parquet
      event_log.parquet

    derived/
      pairwise_deltas.parquet
      diagnostic_flags.json
      representative_runs.parquet
      enabler_coupling.parquet

    figures/
      value_by_year_stacked.png
      cumulative_value_by_year.png
      surfaced_major_wins_by_year.png
      tradeoff_frontier.png
      terminal_capability.png
      rt_survival_curves.png
      enabler_dashboard.png
      trajectory_beliefs_<condition_id>.png      (when per-tick logs enabled)
      trajectory_overlay_<condition_id>.png      (when per-tick logs enabled)

    report/
      index.html
      report.md
      appendix.html
      representative_runs.html

    logs/
      stdout.txt
      stderr.txt
      timing.json

    provenance/
      command.txt
      git_commit.txt
      environment.json
      pip_freeze.txt
      schema_versions.json
```

### Directory purpose

**`manifest.json`**
Root authority file for the bundle. It identifies the run bundle, its scope, provenance, canonical artifacts, and report package.

**`config/`**
Resolved configuration inputs used to generate the execution. These must reflect the actual settings used.

**`inputs/`**
Seed manifests and realized starting-world artifacts. This directory exists to support exact replay and post hoc world-level analysis.

**`outputs/`**
Canonical machine-readable outputs produced directly by simulation and reporting pipelines.

**`derived/`**
Machine-readable artifacts computed from canonical outputs, such as deltas, flags, or representative-run selections.

**`figures/`**
Generated visual artifacts used by the report package.

**`report/`**
Human-facing report package, including the primary HTML report and companion markdown.

**`logs/`**
Execution logs and timing information for debugging and performance review.

**`provenance/`**
Software, environment, and schema metadata required for auditability and reproducibility.

### Required storage rule

A reporting result must not exist only in:

* a notebook,
* console output,
* an HTML page,
* or an LLM-produced summary.

If a result is part of the reporting contract, it must exist first as a canonical or derived artifact in the run bundle.

## Canonical artifact formats

The reporting layer uses a small number of canonical file formats, each with a specific role.

### Format rules

**JSON**
Use JSON for:

* manifest files,
* configuration snapshots,
* diagnostic flags,
* provenance metadata,
* and any artifact whose primary purpose is structured metadata rather than bulk tabular analysis.

**Parquet**
Use Parquet for:

* seed-run outputs,
* experimental-condition summaries,
* grouped family outcomes,
* yearly time series,
* initiative outcomes,
* diagnostics,
* initial-state indices,
* event logs,
* and other tabular data intended for analysis, filtering, aggregation, or external loading.

Parquet is the canonical format for bulk reporting data.

**PNG or SVG**
Use PNG or SVG for generated figures included in the report package.

**HTML**
Use static HTML for the primary human-facing report package. The HTML report must be fully derivable from canonical and derived artifacts in the run bundle and must not require a server.

**Markdown**
Use markdown for the companion plain-text report. Markdown is secondary to HTML but should contain enough structure to preserve the core results and interpretation in a diffable, portable format.

**Plain text**
Use plain text for raw logs, command capture, and lightweight provenance notes.

### Format constraints

1. No spreadsheet or notebook as canonical store.
2. No chart-only metrics.
3. No HTML-only interpretation-critical content.
4. No silent schema drift.

## Manifest requirements

`manifest.json` is the root authority file for a run bundle.

It serves four purposes:

1. identify the bundle,
2. describe what was executed,
3. declare which artifacts are authoritative,
4. provide enough provenance and indexing to load the bundle without inspecting the whole directory tree manually.

### Manifest rules

1. Every run bundle must contain exactly one `manifest.json` at the root.
2. The manifest must be sufficient to identify:

   * the bundle,
   * the experiment it contains,
   * the script that produced it,
   * and the authoritative files inside it.
3. The manifest must not duplicate large tabular results.
4. All paths referenced in the manifest must be relative to the bundle root.

### Required manifest fields

```json
{
  "run_bundle_id": "2026-03-17_143200_baseline_governance",
  "title": "Baseline governance comparison",
  "description": "Three governance regimes across three environmental conditions with shared seeds.",
  "run_kind": "experiment",
  "created_at": "2026-03-17T14:32:00-07:00",
  "script": "scripts/baseline_governance_campaign.py",
  "command": "python scripts/baseline_governance_campaign.py",
  "git_commit": "abc1234",
  "python_version": "3.12.2",
  "platform": "Windows-11",
  "schema_version": "1.0.0",
  "study_phase": "evaluation",
  "experiment_name": "baseline_governance_comparison",
  "seed_count": 7,
  "world_seeds": [42, 43, 44, 45, 46, 47, 48],
  "experimental_condition_count": 9,
  "rerun_supported": true,
  "replay_supported": true,
  "authoritative_files": {
    "run_spec": "config/run_spec.json",
    "simulation_config": "config/simulation_config.json",
    "environmental_conditions": "config/environmental_conditions.json",
    "governance_architecture": "config/governance_architecture.json",
    "operating_policies": "config/operating_policies.json",
    "initial_state_index": "inputs/initial_state_index.parquet",
    "experimental_conditions": "outputs/experimental_conditions.parquet",
    "seed_runs": "outputs/seed_runs.parquet",
    "family_outcomes": "outputs/family_outcomes.parquet",
    "yearly_timeseries": "outputs/yearly_timeseries.parquet",
    "initiative_outcomes": "outputs/initiative_outcomes.parquet",
    "diagnostics": "outputs/diagnostics.parquet",
    "event_log": "outputs/event_log.parquet",
    "pairwise_deltas": "derived/pairwise_deltas.parquet",
    "diagnostic_flags": "derived/diagnostic_flags.json",
    "report_html": "report/index.html",
    "report_markdown": "report/report.md"
  }
}
```

### Additional recommended manifest fields

* `author`
* `workspace`
* `time_zone`
* `horizon_ticks`
* `tick_interval_description`
* `named_governance_regimes`
* `environment_names`
* `notes`
* `tags`
* `parent_run_bundle_id`
* `derived_from_run_bundle_ids`
* `validation_status`

### Initial-state requirement

The manifest must indicate whether the bundle contains:

* only resolved generator and config inputs,
* or full realized initial-state snapshots for exact replay.

The preferred default is to support both.

Add these boolean fields:

* `rerun_supported`
* `replay_supported`

If replay is supported, the manifest must reference `inputs/initial_state_index.parquet`.

### Validation requirements for the manifest

A run bundle is invalid if any of the following is true:

* `manifest.json` is missing,
* a required field is missing,
* a path in `authoritative_files` does not exist (except: in Phase 1, `diagnostic_flags` is optional and the path need not exist),
* `seed_count` disagrees with `world_seeds`,
* `experimental_condition_count` disagrees with the canonical condition table,
* `schema_version` is missing,
* or the report files cited in the manifest cannot be traced back to canonical artifacts.

## Telemetry and execution metadata

The run bundle must include a minimal, study-appropriate provenance and performance layer.

The purpose of this layer is not operational monitoring. It exists to support:

* reproducibility,
* execution auditability,
* bundle completeness checks,
* and lightweight planning/debugging for larger experiment sweeps.

Telemetry records **what ran, how much ran, how long it took, and whether it completed cleanly**. It does not introduce a second analytical layer or an application-performance-monitoring system.

### Telemetry rules

1. Telemetry is required for every run bundle.
2. Telemetry must describe execution of the simulation and reporting pipeline, not interpret study findings.
3. Telemetry must be lightweight enough to remain on by default.
4. Telemetry must not become the sole location of any concept needed for interpretation.
5. Telemetry must support both single-condition executions and multi-condition experiments.

### Required telemetry fields

Store these in the manifest under top-level `telemetry`:

```json
"telemetry": {
  "status": "completed",
  "started_at": "2026-03-17T14:32:00-07:00",
  "completed_at": "2026-03-17T14:34:11-07:00",
  "wall_clock_seconds_total": 131.2,
  "experimental_condition_count": 9,
  "seed_count": 7,
  "seed_run_count_total": 63,
  "seed_runs_completed": 63,
  "mean_wall_clock_seconds_per_experimental_condition": 14.58,
  "mean_wall_clock_seconds_per_seed_run": 2.08,
  "simulation_seconds": 118.4,
  "derivation_seconds": 4.8,
  "figure_generation_seconds": 5.9,
  "report_render_seconds": 1.6,
  "validation_seconds": 0.5
}
```

### Storage locations

Telemetry is stored in two places:

1. `manifest.json` for authoritative summary telemetry.
2. `logs/timing.json` for convenient direct loading.

### Validation requirements

A run bundle fails telemetry validation if:

* the `telemetry` object is missing,
* `status` is missing,
* `started_at` or `completed_at` is missing,
* `wall_clock_seconds_total` is missing or negative,
* `seed_run_count_total` is missing,
* `seed_runs_completed` exceeds `seed_run_count_total`,
* or any required phase-timing field is missing.

## Required output tables and schemas

The run bundle must contain a small set of canonical machine-readable output tables that together support:

* deterministic report generation,
* cross-condition comparison,
* seed-level uncertainty analysis,
* time-series visualization,
* initiative-level diagnostics,
* and ad hoc downstream analysis.

These tables are the canonical analytical substrate of the run bundle. The HTML report, markdown report, figures, and any later notebook or LLM analysis layer must derive from them rather than reconstructing results from logs or console text.

### Design rules

1. Each required table must have one designated semantic purpose.
2. Tables should be normalized enough to avoid duplicated meaning, but not so fragmented that simple analysis requires joining many unrelated files.
3. Tables must distinguish between:

   * core simulator primitives and resolved records, and
   * study-level grouping labels inherited from the run bundle.
4. The canonical machine-readable layer must not assume that the current initiative-family set, governance-archetype set, or environmental-condition set is permanent or exhaustive.
5. Current study labels may appear in canonical tables as data values, but should not be baked into the schema as required fixed column names except for stable study concepts.
6. All tables must be stored in Parquet format.
7. Every table must carry a schema version.
8. If a quantity is shown in a standard figure or cited in the report package, it must be recoverable from one of these canonical tables or from a documented derived artifact.

### Canonical grouping rule

The reporting layer must treat initiative families, named governance archetypes, named environment families, and similar study-defined buckets as **inherited grouping metadata**.

That means:

* the run bundle must store the grouping labels actually used by the experiment,
* canonical tables may record those labels as row values,
* but canonical schemas must not depend on a fixed hard-coded set of family or archetype columns.

This does **not** prohibit fixed columns for stable study concepts such as `right_tail`, `major_win`, `terminal_capability`, or `false_stop_rate`.

### Zero-category robustness rule

Some experiments may contain **zero initiatives** for one or more inherited initiative-family labels, including `right_tail`, `enabler`, or other categories. The reporting system must still work in these cases.

Specifically:

1. A run bundle remains valid if a study-defined grouping bucket has zero initiatives in some or all experimental conditions.
2. Canonical tables and derived figures must distinguish:

   * `zero observed` or `zero present in this run bundle`
   * from `missing data`
   * from `not applicable`
3. Grouped tables may omit absent categories at the row level, but report generation must be able to render stable views for the current study without failing when a category is absent.
4. Figures and summary tables for a zero-count category may show:

   * zero-valued series,
   * empty panels with an explicit label,
   * or “not present in this experiment” notes,
     but must not silently disappear if that would materially confuse interpretation.
5. Derived convenience views for the current canonical study may include stable display positions for known study categories, but they must populate absent categories explicitly as zero or not-present rather than erroring.

## Required canonical tables

### 1. `outputs/experimental_conditions.parquet`

Each row represents one experimental condition.

#### Required identifier columns

* `run_bundle_id`
* `experiment_name`
* `experimental_condition_id`

#### Required inherited grouping columns

* `environmental_conditions_id`
* `environmental_conditions_name`
* `governance_architecture_id`
* `governance_architecture_name`
* `operating_policy_id`
* `operating_policy_name`
* `governance_regime_label`

#### Required execution columns

* `seed_count`
* `seed_runs_completed`

#### Required summary metrics

* `total_value_mean`

* `total_value_median`

* `total_value_std`

* `total_value_p25`

* `total_value_p75`

* `surfaced_major_wins_mean`

* `surfaced_major_wins_median`

* `surfaced_major_wins_std`

* `terminal_capability_mean`

* `terminal_capability_median`

* `terminal_capability_std`

* `right_tail_completions_mean`

* `right_tail_stops_mean`

* `right_tail_false_stop_rate_mean`

* `idle_pct_mean`

* `free_teams_mean`

* `peak_capacity_mean`

#### Notes

* This is the canonical source for cross-condition summary reporting.
* Means and medians are both required.
* Family-specific decomposition does not belong in fixed columns here.

### 2. `outputs/seed_runs.parquet`

Each row represents one seed run under one experimental condition.

#### Required identifier columns

* `run_bundle_id`
* `experiment_name`
* `experimental_condition_id`
* `seed_run_id`
* `world_seed`

#### Required outcome metrics

* `total_value`

* `surfaced_major_wins`

* `terminal_capability`

* `right_tail_completions`

* `right_tail_stops`

* `right_tail_eligible_count`

* `right_tail_stopped_eligible_count`

* `right_tail_false_stop_rate`

* `idle_pct`

* `free_teams_mean`

* `peak_capacity`

#### Required timing markers

* `first_completion_tick_any`
* `first_right_tail_completion_tick`
* `first_right_tail_stop_tick`

#### Required completeness markers

* `status`
* `completed_ticks`
* `horizon_ticks`

### 3. `outputs/family_outcomes.parquet`

Each row represents one grouping bucket within one seed run or experimental condition. For the current study, the grouping bucket will usually be the inherited `initiative_family` label.

#### Required identifier columns

* `run_bundle_id`
* `experiment_name`
* `experimental_condition_id`
* `seed_run_id` (nullable for condition-level aggregated rows)
* `world_seed` (nullable for condition-level aggregated rows)

#### Required grouping columns

* `grouping_namespace`
* `grouping_key`
* `grouping_label`

For the current study, examples would be:

* `grouping_namespace = "initiative_family"`
* `grouping_key = "right_tail"`
* `grouping_label = "Right Tail"`

#### Required metrics

* `initiative_count`

* `completed_count`

* `stopped_count`

* `active_at_horizon_count`

* `never_started_count`

* `realized_value_lump`

* `realized_value_residual`

* `realized_value_total`

* `surfaced_major_wins`

* `eligible_count`

* `stopped_eligible_count`

#### Required aggregation column

* `aggregation_level`

Allowed initial values:

* `seed_run`
* `experimental_condition`

#### Notes

* This is the canonical source for all family-level charts and summaries.
* The report package may pivot this table into wide display format for readability.
* Zero-count categories must be representable without error.

### 4. `outputs/yearly_timeseries.parquet`

Each row represents one time bin within one seed run and one grouping bucket. The default reporting bin is the study year, defined as 52 ticks unless the run bundle states otherwise.

#### Required identifier columns

* `run_bundle_id`
* `experiment_name`
* `experimental_condition_id`
* `seed_run_id`
* `world_seed`
* `time_bin_index`
* `time_bin_label`
* `tick_start`
* `tick_end`

#### Required grouping columns

* `grouping_namespace`
* `grouping_key`
* `grouping_label`

For overall totals, use:

* `grouping_namespace = "overall"`
* `grouping_key = "all"`
* `grouping_label = "All"`

#### Required metrics

* `value_lump`

* `value_residual`

* `value_total`

* `value_lump_cumulative`

* `value_residual_cumulative`

* `value_total_cumulative`

* `surfaced_major_wins`

* `surfaced_major_wins_cumulative`

* `completions`

* `stops`

* `enabler_completions`

* `terminal_capability`

#### Notes

* This is the canonical source for yearly charts.
* Overall totals and grouped decompositions may coexist.
* Zero-count categories must not break aggregation or plotting.

### 5. `outputs/initiative_outcomes.parquet`

Each row represents one realized initiative within one seed run.

#### Required identifier columns

* `run_bundle_id`
* `experiment_name`
* `experimental_condition_id`
* `seed_run_id`
* `world_seed`
* `initiative_id`

#### Required inherited classification columns

* `initiative_family`
* `initiative_family_label`

#### Required initiative attributes

* `true_quality`
* `initial_quality_belief`
* `final_quality_belief`
* `required_team_size`
* `true_duration_ticks`
* `planned_duration_ticks`

#### Required outcome fields

* `status`

* `completed`

* `stopped`

* `completion_tick`

* `stop_tick`

* `staffed_ticks_total`

* `realized_value_lump`

* `realized_value_residual`

* `realized_value_total`

* `is_major_win_eligible`

* `surfaced_major_win`

* `belief_at_stop`

#### Source fields and computation (implementation instruction)

Implementers must use the following definitions. Do not infer from context.

* **`is_major_win_eligible`** (per initiative): From the resolved initiative config at run start. Set to true if and only if `cfg.value_channels.major_win_event.enabled` is true and `cfg.value_channels.major_win_event.is_major_win` is true, where `cfg` is the `ResolvedInitiativeConfig` for that initiative. Both conditions are required; the initiative must be of the right-tail family (by `generation_tag` or equivalent) for the flag to be meaningful in false-stop diagnostics.
* **`belief_at_stop`** (per stopped initiative): The value of `quality_belief_t` at the time the initiative was stopped. Source: the `StopEvent` for that initiative carries `quality_belief_t`; map it into `initiative_outcomes.parquet` as `belief_at_stop` for rows where the initiative was stopped. No other field should be used.
* **Right-tail false-stop rate** (per seed run or experimental condition): `right_tail_false_stop_rate` = `right_tail_stopped_eligible_count` / `right_tail_eligible_count`, where *eligible* means the initiative has `is_major_win_eligible` true (as defined above) and belongs to the right-tail initiative family. When `right_tail_eligible_count` is zero, the rate is undefined; the reporting layer must represent that case explicitly (e.g. null or a sentinel) and must not emit an arbitrary value. This rate is required in `seed_runs.parquet`, `experimental_conditions.parquet`, and diagnostics; it must be produced by a single canonical computation (e.g. a RightTailFalseStopProfile in the reporting layer) and reused everywhere.

#### Notes

* `status` should distinguish at least:

  * `completed`
  * `stopped`
  * `active_at_horizon`
  * `never_started`

### 6. `outputs/diagnostics.parquet`

Each row represents one diagnostic metric for one experimental condition, optionally broken out by grouping bucket, staffed-time bin, or other slice.

#### Required columns

* `run_bundle_id`
* `experiment_name`
* `experimental_condition_id`
* `diagnostic_group`
* `diagnostic_name`
* `slice_namespace`
* `slice_key`
* `slice_label`
* `metric_value`
* `metric_unit`

#### Required diagnostic coverage

At minimum:

* right-tail false-stop rate
* stopped-eligible count
* eligible count
* belief-at-stop for stopped eligible right-tail initiatives
* stop hazard by staffed-time bin
* representative survival diagnostics for right-tail initiatives
* terminal capability summary

### 7. `outputs/event_log.parquet`

Each row represents one event in one seed run.

#### Required identifier columns

* `run_bundle_id`
* `experiment_name`
* `experimental_condition_id`
* `seed_run_id`
* `world_seed`
* `tick`
* `event_type`
* `initiative_id`

#### Required inherited classification columns

* `initiative_family`
* `initiative_family_label`

#### Required event payload fields

* `value_delta`
* `capability_delta`
* `quality_belief`
* `notes_json`

#### Required event types

At minimum:

* `initiative_started`
* `initiative_stopped`
* `initiative_completed`
* `major_win_surfaced`
* `enabler_completed`

## Required derived tables

### 1. `derived/pairwise_deltas.parquet`

Each row represents one pairwise comparison between two experimental conditions, typically relative to a baseline condition.

#### Required columns

* `run_bundle_id`
* `experiment_name`
* `comparison_name`
* `lhs_experimental_condition_id`
* `rhs_experimental_condition_id`

#### Required delta metrics

* `delta_total_value_mean`
* `delta_surfaced_major_wins_mean`
* `delta_terminal_capability_mean`
* `delta_right_tail_false_stop_rate_mean`
* `delta_idle_pct_mean`

### 2. `derived/diagnostic_flags.json` (Phase 2)

Simple rule-based flags that support interpretation and report rendering. **This artifact is scoped to Phase 2.** Phase 1 run bundles need not include it. When implemented, the spec must define the **threshold rules** for each flag so that implementers and consumers share the same semantics. Do not leave threshold rules unspecified; otherwise report rendering will invent rules and results will be inconsistent.

Planned flag concepts (threshold rules to be added in a future spec update before Phase 2 implementation):

* `rt_value_unpriced_by_design`
* `aggressive_false_stop_pathology` (e.g. fires when `right_tail_false_stop_rate` &gt; a specified threshold such as 0.5)
* `patient_throughput_collapse`
* `surface_flat_attention_minimum`
* `balanced_non_pathological`

### 3. `derived/representative_runs.parquet`

Records which seed runs were selected as representative drill-down examples and why.

#### Required columns

* `run_bundle_id`
* `experiment_name`
* `experimental_condition_id`
* `seed_run_id`
* `selection_rule`
* `selection_rank`
* `selection_reason`

### 4. `derived/enabler_coupling.parquet`

Materializes enabler-related relationships the report package must show clearly.

#### Required columns

* `run_bundle_id`
* `experiment_name`
* `experimental_condition_id`
* `seed_run_id` (nullable at condition-summary level)

#### Required metrics

* `enabler_completions`
* `terminal_capability`
* `right_tail_false_stop_rate`
* `right_tail_completions`
* `surfaced_major_wins`
* `value_total`
* `value_total_late_period`
* `mean_belief_at_stop_for_stopped_eligible_rt`

#### Derived-metric definition: `value_total_late_period`

**`value_total_late_period`** is the sum of realized value over the **final third of the tick horizon**. For a run with `tick_horizon` T, the late period is the interval of ticks from `ceil(2*T/3)` through T−1 (inclusive). Example: for a 300-tick run, the late period is ticks 200–299. The value is computed from the canonical **`outputs/yearly_timeseries.parquet`** (or equivalent tick-level value series) by summing `value_total` (or the appropriate cumulative-delta column) over ticks in that range. This metric supports interpretation of whether value is back-loaded (e.g. patient regimes realizing value late) versus front-loaded. The definition must not be changed without a spec update.

## Table validation rules

A run bundle fails table validation if any of the following is true:

1. A required table is missing.
2. A required identifier column is missing.
3. `experimental_condition_id` values in seed-level tables do not map to the condition table.
4. `seed_run_id` values are duplicated within the same experimental condition.
5. A required report figure depends on a quantity that is not present in canonical or derived tables.
6. Condition-level summary metrics cannot be reproduced from corresponding seed-level tables within allowed tolerance.
7. Any required table is present but empty for a completed run bundle, unless emptiness is expected by design for that artifact class and is explicitly marked valid.
8. Zero-count grouping categories are represented ambiguously as missing data rather than as zero or not-present.

## Derived convenience views

The report package may generate wide, current-study-specific convenience views for readability, including tables or charts that display the current initiative families or named governance regimes in fixed positions.

However:

* these are derived convenience artifacts,
* they must be generated from canonical long-form or grouping-aware tables,
* and they must not be treated as the deepest reporting contract.

## Required figures

The report package must include a standard set of generated figures that make the experiment readable from both an academic and a business-executive perspective.

These figures are part of the reporting contract.

### Figure rules

1. Every required figure must be derivable from canonical or documented derived artifacts in the run bundle.
2. Figures must use inherited study labels from the run bundle rather than hard-coded preset labels wherever possible.
3. Figures must remain valid if governance-archetype labels, environmental-condition labels, or initiative-family taxonomies evolve, provided the underlying stable study concepts remain present.
4. The current canonical study should still render directly and readably using its current vocabulary.
5. Every figure must have:

   * a clear title,
   * a short subtitle or caption,
   * labeled axes,
   * and explicit units where applicable.
6. Any figure using aggregation across seed runs must state the summary statistic.
7. Figures must handle zero-count categories without failing. For the current canonical study, a category that is absent in a run bundle should still be displayed coherently if its omission would confuse interpretation.

## Required executive-summary figures

### 1. Value by year, stacked by initiative family

**Purpose**
Show how priced value accrues over time and how that accrual decomposes across initiative families.

**Source**
`outputs/yearly_timeseries.parquet`

**Form**

* x-axis: reporting year
* y-axis: priced realized value
* stacks: initiative-family grouping values from the run bundle
* facet or group by experimental condition

### 2. Cumulative priced value by year

**Purpose**
Show timing, crossover behavior, and total priced-value accumulation.

**Source**
`outputs/yearly_timeseries.parquet`

**Form**

* x-axis: reporting year
* y-axis: cumulative priced value
* one line per experimental condition or governance regime

### 3. Surfaced major wins by year

**Purpose**
Show the time structure of rare-opportunity surfacing, distinct from priced value.

**Source**
`outputs/yearly_timeseries.parquet`

**Form**

* x-axis: reporting year
* y-axis: cumulative surfaced major wins
* one line per experimental condition or governance regime

**Interpretation note**
This figure must be presented consistently with the rule that right-tail wins are surfaced-not-priced by design.

### 4. Tradeoff frontier

**Purpose**
Show the central tradeoff among priced value, surfaced major wins, and terminal capability.

**Source**
`outputs/experimental_conditions.parquet`

**Form**

* x-axis: total priced value
* y-axis: surfaced major wins
* point size or color: terminal capability
* one point per experimental condition

### 5. Terminal capability comparison

**Purpose**
Make terminal capability a first-class outcome.

**Source**
`outputs/experimental_conditions.parquet`

**Form**

* bar chart or dot plot
* x-axis: experimental condition
* y-axis: terminal capability
* optional error bars

### 6. Right-tail false-stop / survival view

**Purpose**
Show whether governance regimes preserve or kill latent breakthrough opportunities.

**Source**
`outputs/diagnostics.parquet`

**Form**
At least one of:

* survival curves,
* staffed-time-bin stop-hazard chart,
* or both

### 7. Enabler dashboard

**Purpose**
Make the enabler channel visible, especially its indirect relationship to capability, false-stop behavior, and downstream outcomes.

**Source**

* `derived/enabler_coupling.parquet`
* `outputs/yearly_timeseries.parquet`
* `outputs/experimental_conditions.parquet`

**Form**
A compact multi-panel figure or dashboard including at least:

* enabler completions,
* terminal capability,
* right-tail false-stop rate,
* right-tail completions,
* surfaced major wins,
* and at least one downstream priced-value measure.

## Required appendix figures

### 8. Seed-level distribution view

**Purpose**
Show uncertainty and dispersion for main outputs.

**Source**
`outputs/seed_runs.parquet`

**Form**
Boxplots, violin plots, or dot plots for:

* total priced value,
* surfaced major wins,
* terminal capability

### 9. Representative-run timelines

**Purpose**
Provide concrete mechanism-level intuition for how one seed run evolved.

**Source**

* `outputs/event_log.parquet`
* `outputs/yearly_timeseries.parquet`
* `derived/representative_runs.parquet`

### 10. Fragility / sensitivity surfaces

**Purpose**
Show where a policy surface is stable, steep, or cliff-like.

**Requirement**
Only required when the run bundle is a sensitivity or fragility study rather than a basic comparison experiment.

## Figure naming and storage

Use stable descriptive filenames, such as:

* `value_by_year_stacked.png`
* `cumulative_value_by_year.png`
* `surfaced_major_wins_by_year.png`
* `tradeoff_frontier.png`
* `terminal_capability.png`
* `rt_survival_curves.png`
* `enabler_dashboard.png`

## HTML report-package structure

The report package is the human-facing subset of the run bundle. Its primary artifact is a static HTML report at:

* `report/index.html`

A companion markdown version must also be generated at:

* `report/report.md`

### Report rules

1. The report package must be fully derivable from artifacts inside the run bundle.
2. The HTML report must not require a server.
3. The report must separate:

   * top-line findings,
   * diagnostics,
   * representative traces,
   * and reproducibility/provenance.
4. The report must preserve the study’s interpretation rules, including:

   * surfaced-not-priced right-tail wins,
   * terminal capability as a primary output,
   * and the distinction between priced value and breakthrough surfacing.
5. The report must be understandable to a reader who did not watch the run in the console.

## Required report sections

### 1. Title and metadata

Must include:

* experiment title
* run bundle ID
* script name
* creation timestamp
* git commit
* schema version
* experiment summary sentence

### 2. Study interpretation notes

Must include a short note block stating the main study framing needed to read the outputs correctly.

For the current canonical study, this must include at least:

* right-tail wins are surfaced-not-priced by design,
* terminal capability is a primary outcome,
* experimental-condition labels are inherited study presets from the run bundle.

### 3. Executive summary

Must include:

* short top-line findings,
* key tradeoffs,
* one compact summary table,
* and the most important figures.

### 4. Headline comparison tables

Must include at least one table with:

* total priced value,
* surfaced major wins,
* terminal capability,
* right-tail false-stop rate,
* and idle or free-capacity metrics

grouped by experimental condition.

### 5. Core figures

Must include the required executive-summary figures.

### 6. Diagnostic interpretation

Must include:

* false-stop diagnostics,
* survival or hazard views,
* enabler-coupling evidence,
* and any required study-specific warnings or flags.

### 7. Representative runs

Must include at least one representative drill-down view when multiple seed runs are present.

### 8. Methods and reproducibility

Must include:

* seed set,
* number of experimental conditions,
* number of completed seed runs,
* horizon definition,
* command used,
* and links or references to canonical artifacts in the run bundle.

### 9. Appendix

May include:

* seed-level distribution plots,
* additional diagnostic tables,
* sensitivity views,
* additional representative traces,
* and artifact inventories.

## Report-package outputs

The baseline report package must include at least:

* `report/index.html`
* `report/report.md`

It may also include:

* `report/appendix.html`
* `report/representative_runs.html`

## Validation and phased implementation

### Validation rules

A run bundle fails report-package validation if any of the following is true:

1. `report/index.html` is missing.
2. `report/report.md` is missing.
3. A required figure is missing.
4. A required report section is missing.
5. A required figure or table in the report cannot be traced to canonical or documented derived artifacts.
6. The report contradicts bundle metadata.
7. The report omits the study interpretation notes required to avoid known misreadings.
8. The report fails to handle zero-count categories coherently.

### Phase 1 implementation scope

The minimum implementation scope is:

* run-bundle directory creation
* manifest generation
* required canonical tables
* required derived tables (excluding `derived/diagnostic_flags.json`, which is Phase 2)
* required executive-summary figures
* static HTML report
* markdown report
* basic validation

**Implementation note — RightTailFalseStopProfile:** The current codebase does not define a `RightTailFalseStopProfile` dataclass or a compute function for right-tail false-stop metrics. The spec requires `right_tail_false_stop_rate` (and related counts) in `seed_runs.parquet`, `experimental_conditions.parquet`, and diagnostics. Implementers must add a new profile type in `reporting.py` analogous to `ExplorationCostProfile`, compute it from the resolved initiative configs and stop events (using the source-field rules in this spec), and wire it through `assemble_run_result`. This task must be explicitly called out in the implementation plan so it is not missed.

### Phase 2 implementation scope

After Phase 1 is stable:

* representative-run appendix
* richer diagnostic appendix
* notebook template that loads a run bundle by path

### Phase 3 implementation scope

Only after deterministic reporting is stable:

* optional LLM-assisted narrative analysis driven by canonical run-bundle artifacts
* optional interactive exploration layers

### Implementation rule

Later tooling must consume the run bundle and report package rather than redefining the reporting contract.

## Non-goals

The baseline schema does not attempt to capture every possible internal simulator state.

It is intentionally designed to support:

* reporting,
* auditability,
* ad hoc analysis,
* representative replay,
* and flexible regrouping under changing study taxonomies,

without turning the run bundle into a full internal-state archive.
