# Configuring and Running a Simulation

This guide is for the person responsible for setting up and running a simulation. No Python programming is required — you fill in a YAML configuration file and run one command.

---

## How this works

You edit a YAML file that describes what you want to test. When you are ready, you run:

```
python scripts/run_design.py path/to/my_run.yaml
```

The script reads your file, validates your choices, prints a human-readable summary of the resolved configuration for you to confirm, and then executes the simulation. Results are written to the `results/` directory.

That is the complete workflow. You never write Python code.

---

## Step 1 — Get a starting file

The fastest path is to copy a pre-filled template that already matches the environment and policy you want:

```
templates/presets/
  balanced_incumbent_balanced.yaml           ← canonical baseline (start here)
  balanced_incumbent_aggressive_stop_loss.yaml
  balanced_incumbent_patient_moonshot.yaml
  short_cycle_throughput_balanced.yaml
  short_cycle_throughput_aggressive_stop_loss.yaml
  short_cycle_throughput_patient_moonshot.yaml
  discovery_heavy_balanced.yaml
  discovery_heavy_aggressive_stop_loss.yaml
  discovery_heavy_patient_moonshot.yaml
```

Copy the one closest to what you need and rename it:

```bash
cp templates/presets/balanced_incumbent_balanced.yaml my_run.yaml
```

If you want to see and understand every available option, use the master template instead:

```bash
cp templates/run_design_template.yaml my_run.yaml
```

The master template has a comment above every field explaining what it does and what values are valid.

---

## Step 2 — Understand the three layers

Every run is defined by three layers. You will see these as sections in your YAML file.

**Layer 1: Environment** — the world the organization operates in. The main choice is the initiative pool family.

| Family | Character |
|---|---|
| `balanced_incumbent` | Mid-case major-win environment. Multi-year right-tail durations. **Start here.** |
| `short_cycle_throughput` | Mature, quick-win-heavy world. Fewer and shorter right-tail opportunities. |
| `discovery_heavy` | Favorable domain. More right-tail initiatives, longer exploratory durations. |

**Layer 2: Architecture** — how leadership chose to organize before the run begins. The main choices are workforce structure (team count, sizes, ramp) and optional portfolio guardrails.

**Layer 3: Policy** — how governance actually decides per-tick. Select by name.

| Preset | Character |
|---|---|
| `balanced` | Moderate thresholds. All four stop rules active. **The canonical reference.** |
| `aggressive_stop_loss` | Tight thresholds. Short patience windows. Stops early and redeploys fast. |
| `patient_moonshot` | Confidence-decline stopping disabled. Long patience. Holds on high-potential initiatives. |

---

## Step 3 — Edit your file

Open your copied file in any text editor. Lines beginning with `#` are comments explaining the options — read them, then edit the values.

The fields you will most commonly change:

```yaml
# Identification
name: my_run_v1          # no spaces; used in output filenames
title: "My run"          # free text; appears in the printed summary

# What world?
environment:
  family: balanced_incumbent   # see family table above

# How many teams and how structured?
architecture:
  total_labor_endowment: 210   # total workforce size
  team_count: 24               # number of parallel teams

# Which governance posture?
policy:
  preset: balanced             # see preset table above

# How many independent draws?
world_seeds: [42, 43, 44]      # one run per seed
```

Everything else — ramp shape, portfolio guardrails, model parameters, reporting options — has a working default and can be left alone unless you have a specific reason to change it. All options are documented in `templates/run_design_template.yaml`.

---

## Step 4 — Check your config before running

Use `--dry-run` to validate and print the resolved configuration without executing:

```bash
python scripts/run_design.py my_run.yaml --dry-run
```

This prints a full human-readable summary of what the simulator will actually receive, for example:

```
Run Design: "balanced_incumbent_balanced_v1"
Title:       Canonical baseline — balanced policy

── Environment ─────────────────────────────────────────────
  Family:  balanced_incumbent
  Horizon: 313 weeks
  Pool:    200 initiatives (70 flywheel, 20 right_tail, 30 enabler, 80 quick_win)
  Model:   exec_budget=30.0, init_belief=0.5, ref_ceiling=50.0, learning_rate=0.1

── Governance Architecture ──────────────────────────────────
  Workforce: 24 teams (10×5 + 12×10 + 2×20) = 210 total labor
  Ramp:      4 ticks, linear
  Portfolio: no guardrails

── Operating Policy ─────────────────────────────────────────
  Preset:   balanced (policy_id='balanced')
  Confidence decline: threshold=0.3
  TAM:      ratio=0.6, patience=10 ticks
  Stagnation: window=15 staffed ticks, Δbelief<0.02
  Attention: min=0.15, max=uncapped
  Exec overrun: threshold=0.4

── Execution ────────────────────────────────────────────────
  World seeds: [42, 43, 44]
  → 3 simulation runs
```

Review this output before proceeding. It shows exactly what will run.

If anything is wrong, the script will print a clear error message. Common problems and their fixes are listed at the end of this guide.

---

## Step 5 — Run

```bash
python scripts/run_design.py my_run.yaml
```

The script prints the summary, then asks:

```
Run 3 simulations? [y/N]
```

Type `y` and press Enter. Progress is logged to the console as each run completes.

To skip the confirmation prompt (for batch use):

```bash
python scripts/run_design.py my_run.yaml --no-confirm
```

To write results to a specific directory:

```bash
python scripts/run_design.py my_run.yaml --output-dir /data/my_results
```

---

## Step 6 — Find your results

Results are written as a **run bundle** — a self-contained directory under `results/` (or the directory you specified with `--output-dir`). The bundle contains everything needed to understand, reproduce, and present the run.

```
results/<run_name>_<YYYYMMDD_HHMMSS>/
  manifest.json                          ← bundle identity and provenance
  config/
    run_spec.json                        ← resolved run design
    simulation_config.json               ← exact simulator inputs
    ...
  outputs/
    seed_runs.parquet                    ← one row per seed run (value, major wins, capability, ...)
    experimental_conditions.parquet      ← aggregated across seeds per condition
    family_outcomes.parquet              ← per-family per-seed value decomposition
    yearly_timeseries.parquet            ← per-year per-seed per-family time series
    initiative_outcomes.parquet          ← per-initiative per-seed drill-down
    diagnostics.parquet                  ← false-stop rate, survival, belief-at-stop
    event_log.parquet                    ← starts, stops, completions, major wins
  derived/
    pairwise_deltas.parquet              ← metric deltas vs baseline condition
    enabler_coupling.parquet             ← enabler investment vs downstream outcomes
    representative_runs.parquet          ← median/max/min seed selection
  figures/
    value_by_year_stacked.png            ← priced value per year by family
    cumulative_value_by_year.png         ← cumulative value over time
    surfaced_major_wins_by_year.png      ← cumulative major wins over time
    tradeoff_frontier.png                ← value vs major wins scatter
    terminal_capability.png              ← terminal capability bar chart
    rt_survival_curves.png               ← right-tail false-stop rate
    enabler_dashboard.png                ← enabler metrics per condition
    seed_distributions.png               ← boxplots of key metrics across seeds
    representative_timelines.png         ← event timeline for median-value seed
    trajectory_beliefs_*.png             ← per-initiative belief evolution (if per-tick logs enabled)
    trajectory_overlay_*.png             ← overlaid belief trajectories (if per-tick logs enabled)
  report/
    index.html                           ← human-readable HTML report
    report.md                            ← companion markdown
  provenance/
    command.txt                          ← exact command used
    git_commit.txt                       ← source commit hash
    environment.json                     ← platform and dependency versions
```

Start with `manifest.json` to confirm the run completed as intended. Open `report/index.html` in a browser for the full human-readable report. For ad hoc analysis, load the Parquet tables directly:

```python
import pyarrow.parquet as pq
table = pq.read_table("results/<bundle>/outputs/seed_runs.parquet")
values = table.column("total_value").to_pylist()
```

---

## Portfolio guardrails (optional)

If you want to test a governance architecture with explicit portfolio risk controls, uncomment and set these fields in the `architecture` section:

```yaml
architecture:
  # ... workforce fields ...

  # Flag initiatives below this quality belief as low-confidence:
  low_quality_belief_threshold: 0.3

  # Cap the share of active labor in low-confidence initiatives:
  max_low_quality_belief_labor_share: 0.4   # 40%

  # Cap the share of active labor any single initiative can receive:
  max_single_initiative_labor_share: 0.5    # 50%
```

These are architecture-level constraints. They are passed to the governance policy; the engine does not enforce them directly.

---

## Portfolio mix targets (optional)

Portfolio mix targets let you express a desired labor-share distribution across categories of work. This is the governance architecture answer to "what portfolio composition does leadership want?" — separate from the operating policy's per-tick decisions.

Add a `portfolio_mix_targets` block inside `architecture`:

```yaml
architecture:
  total_labor_endowment: 210
  team_count: 24

  portfolio_mix_targets:
    flywheel: 0.40
    right_tail: 0.20
    enabler: 0.30
    quick_win: 0.10
```

The four canonical buckets are:

| Bucket | What it represents | How the policy identifies it |
|---|---|---|
| `flywheel` | Compounding work with long-lived residual value | No bounded-prize ceiling, no capability contribution, longer duration |
| `right_tail` | Exploratory bets with observable upside ceiling | Has an `observable_ceiling` |
| `enabler` | Capability-building work | Has positive `capability_contribution_scale` |
| `quick_win` | Short-cycle delivery | No ceiling, no capability, short duration |

The targets must sum to 1.0. They are **soft preferences**, not hard constraints — the policy biases new team assignments toward under-target buckets but never blocks an assignment.

For more control, use the structured form:

```yaml
  portfolio_mix_targets:
    targets:
      flywheel: 0.40
      right_tail: 0.20
      enabler: 0.30
      quick_win: 0.10
    tolerance: 0.05              # how far off-target before biasing (default: 0.10)
    duration_threshold_ticks: 15  # boundary between quick_win and flywheel (default: 15)
```

When mix targets are configured, the `--dry-run` summary shows them:

```
── Governance Architecture ──────────────────────────────────
  Workforce: 24 teams (10×5 + 12×10 + 2×20) = 210 total labor
  Ramp:      4 ticks, linear
  Portfolio: no guardrails
  Mix targets: flywheel=40%, right_tail=20%, enabler=30%, quick_win=10%
  Mix tolerance: 10%, duration threshold: 15 ticks
```

Mix targets and portfolio guardrails are independent — you can use either, both, or neither.

---

## Business intent layer (Python API)

If you are starting from a business-style request rather than hand-assembling YAML fields, the business intent translation layer can map executive-style language into the three-layer vocabulary for you.

This requires Python. The translation layer accepts structured intent requests and produces a `RunDesignSpec` that you can validate, inspect, and run through the standard pipeline.

### Quick start

```python
from primordial_soup.business_intent import (
    BusinessIntentRequest,
    build_run_design_from_intents,
)
from primordial_soup.workbench import resolve_run_design, make_policy
from primordial_soup.runner import run_single_regime

# Build a run design from business intents.
spec = build_run_design_from_intents(
    name="patient_discovery_v1",
    intents=(
        BusinessIntentRequest("discovery_heavy_world"),
        BusinessIntentRequest("patient_governance"),
        BusinessIntentRequest(
            "portfolio_mix_targets",
            parameters={
                "targets": {
                    "flywheel": 0.30,
                    "right_tail": 0.30,
                    "enabler": 0.25,
                    "quick_win": 0.15,
                },
            },
        ),
    ),
    world_seeds=(42, 43, 44),
)

# Inspect before running.
resolved = resolve_run_design(spec)
print(resolved.summary())

# Execute.
policy = make_policy(resolved.governance)
for sim_config in resolved.simulation_configs:
    result = run_single_regime(sim_config, policy)
```

### Available intents

Intents are organized by the study layer they affect. The canonical set is defined in `src/primordial_soup/business_intent_registry.yaml`.

**Environment intents** — choose or bias the world:

| Intent ID | Effect |
|---|---|
| `balanced_baseline_world` | Use the `balanced_incumbent` environment family |
| `discovery_heavy_world` | Use the `discovery_heavy` environment family |
| `shorter_cycle_world` | Use the `short_cycle_throughput` environment family |
| `more_right_tail` | Bias toward `discovery_heavy` (more exploratory bets) |

**Operating policy intents** — choose the governance posture:

| Intent ID | Effect |
|---|---|
| `balanced_governance` | Use the `balanced` policy preset |
| `patient_governance` | Use the `patient_moonshot` policy preset |
| `aggressive_stop_loss` | Use the `aggressive_stop_loss` policy preset |

**Governance architecture intents** — shape workforce or portfolio structure:

| Intent ID | Required parameters | Effect |
|---|---|---|
| `fewer_larger_teams` | `team_count`, `total_labor_endowment` | Set workforce structure |
| `more_parallel_teams` | `team_count`, `total_labor_endowment` | Set workforce structure |
| `concentration_cap` | `max_single_initiative_labor_share` | Cap any single initiative's labor share |
| `low_confidence_exposure_cap` | `low_quality_belief_threshold`, `max_low_quality_belief_labor_share` | Cap labor in low-confidence work |
| `portfolio_mix_targets` | `targets` (bucket-to-share mapping) | Set portfolio composition targets |

### Combining intents

You can combine intents from different layers in a single request:

```python
spec = build_run_design_from_intents(
    name="aggressive_throughput_v1",
    intents=(
        BusinessIntentRequest("shorter_cycle_world"),
        BusinessIntentRequest("aggressive_stop_loss"),
        BusinessIntentRequest(
            "fewer_larger_teams",
            parameters={"team_count": 4, "total_labor_endowment": 8},
        ),
        BusinessIntentRequest(
            "concentration_cap",
            parameters={"max_single_initiative_labor_share": 0.4},
        ),
    ),
    world_seeds=(42, 43, 44),
)
```

Conflicting intents (e.g., `patient_governance` + `aggressive_stop_loss`, or two explicit environment families) are detected and rejected with a clear error message.

### Defaults

Any layer not addressed by an intent uses baseline defaults:

- Environment: `balanced_incumbent`
- Policy: `balanced`
- Workforce: 24 mixed-size teams (10×5 + 12×10 + 2×20), ramp period 4
- Portfolio guardrails: none
- Mix targets: none

You can override these defaults with the `base_*` keyword arguments to `build_run_design_from_intents()`.

---

## Validation errors and fixes

| Error message | Fix |
|---|---|
| `name must not be empty` | Set `name:` to a non-empty value |
| `name must not contain spaces` | Use underscores or hyphens: `my_run_v1` |
| `title must not be empty` | Set `title:` to a non-empty string |
| `world_seeds must not be empty` | Provide at least one seed: `world_seeds: [42]` |
| `total_labor_endowment must be exactly divisible by team_count` | Change `team_count` to a value that divides evenly into `total_labor_endowment`, or provide explicit `team_sizes` |
| `team_sizes length N must match team_count M` | Make `team_sizes` a list with exactly `team_count` values |
| `team_sizes sum S must equal total_labor_endowment T` | Make the values in `team_sizes` sum to `total_labor_endowment` |
| `max_low_quality_belief_labor_share is set but low_quality_belief_threshold is None` | Set `low_quality_belief_threshold` to a value in (0, 1) first |
| `Unknown policy preset` | The `policy.preset` value must be exactly one of: `balanced`, `aggressive_stop_loss`, `patient_moonshot` |
| `portfolio_mix_targets: unknown bucket` | Bucket names must be exactly: `flywheel`, `right_tail`, `enabler`, `quick_win` |
| `portfolio_mix_targets: bucket shares must sum to 1.0` | Adjust the share values so they add up to 1.0 |
| `Unknown intent` | Check the intent ID against the registry in `src/primordial_soup/business_intent_registry.yaml` |
| `Conflicting` intents | You requested two intents that cannot coexist (e.g., two different policy presets). Remove one. |

---

## Going beyond the presets

**Different environment:** The three named families cover the canonical study environments. If you need a different initiative pool composition, add a new family to `src/primordial_soup/presets.py` and reference it by name in your YAML.

**Different policy posture:** The three named presets cover the canonical governance archetypes. If you need a different posture, add a new preset to `src/primordial_soup/presets.py`. Do not try to override individual policy fields in the YAML — that would reintroduce the low-level assembly complexity this tool is designed to avoid.

**Systematic parameter sweeps:** This tool is for a single named governance design point. If you need to run many governance configurations systematically (the core study), use `CampaignSpec` and `run_campaign()` in `campaign.py` directly. That machinery was built for exactly this purpose.

**Comparative experiments with full reporting:** For the canonical governance comparison study (3 archetypes × 3 environments × N seeds), use `scripts/baseline_governance_campaign.py`. It produces a complete **run bundle** with Parquet tables, PNG figures, an HTML report, and validation — the canonical on-disk artifact for the study. See the README for usage and the conductor guide (`docs/guides/study_conductor_guide.md`) for interpreting outputs.

**Python API:** If you need more control than the YAML surface provides, you can construct a `RunDesignSpec` directly in Python. See `src/primordial_soup/workbench.py` for the full API.

**Business intent layer:** If you want to start from business-style requests and have the repo translate them into run designs, see the "Business intent layer" section above. The canonical registry of intents is in `src/primordial_soup/business_intent_registry.yaml`.
