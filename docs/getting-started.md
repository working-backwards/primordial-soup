# Getting Started

## Prerequisites

- Python 3.12+
- Git

## Install

```bash
git clone https://github.com/working-backwards/primordial-soup.git
cd primordial-soup
python -m venv .venv
source .venv/bin/activate        # macOS/Linux
# .venv\Scripts\activate         # Windows PowerShell
pip install -e ".[dev]"
```

## Verify

```bash
pytest
```

You should see 970+ tests passing.

---

## Three ways to use the simulator

The scripts are organized as a progression. Start at Level 1 and
work your way up.

### Level 1: Run a single design from YAML

```bash
python scripts/run_design.py templates/presets/balanced_incumbent_balanced.yaml --no-confirm
```

Runs a single governance configuration (3 seeds) from a YAML file
and produces a full run bundle. The simulator runs a 313-tick
simulation (6 study years) with 200 initiatives and a 210-person
workforce across 24 mixed-size teams. You'll see key metrics: total
value, major-win count, terminal capability, idle capacity, and
value decomposition by initiative family.

Nine preset YAML files are in `templates/presets/` — one for each
combination of environment family and governance archetype. Try
different presets with the same seeds to see how governance regime
alone changes outcomes. Use `--dry-run` to inspect the resolved
configuration without running.

### Level 2: Compare governance regimes (run bundle)

```bash
python scripts/baseline_governance_campaign.py
python scripts/baseline_governance_campaign.py --seeds 3                        # fewer seeds = faster
python scripts/baseline_governance_campaign.py --families balanced_incumbent    # single environment
```

Runs all three governance archetypes across all three environment
families (Balanced Incumbent, Short Cycle Throughput, Discovery
Heavy) with multiple seeds and produces a self-contained **run
bundle** — the canonical on-disk artifact for the study. Open
`report/index.html` in a browser to see the full report.

This is a 3 x 3 x 7 = 63-run experiment by default. Takes about
90 seconds.

A simplified variant isolates the selection decision alone:

```bash
python scripts/model0_campaign.py
```

Model 0 disables stopping, attention, ramp, frontier, and screening.
The three archetypes differ only in portfolio mix targets. Comparing
Model 0 to the baseline reveals how much of the outcome spread is
explained by selection vs. the full governance machinery.

A run bundle contains:

```
runs/<timestamp>_baseline_governance_comparison/
    manifest.json                          # bundle identity and provenance
    config/                                # resolved simulation configuration
    outputs/                               # 7 canonical Parquet tables
        seed_runs.parquet                  #   per-seed metrics
        experimental_conditions.parquet    #   condition-level summaries
        family_outcomes.parquet            #   per-family decomposition
        yearly_timeseries.parquet          #   value/events by study year
        initiative_outcomes.parquet        #   per-initiative outcomes
        diagnostics.parquet                #   false-stop, survival, hazard
        event_log.parquet                  #   all events (starts, stops, completions, major wins)
    derived/                               # 3 derived tables
        pairwise_deltas.parquet            #   condition-vs-baseline deltas
        representative_runs.parquet        #   selected representative seeds
        enabler_coupling.parquet           #   enabler-capability-outcome coupling
    figures/                               # 9 standard + trajectory PNGs
    report/
        index.html                         #   full HTML report
        report.md                          #   companion markdown
    provenance/                            # git commit, pip freeze, platform
    logs/                                  # timing telemetry
```

The HTML report includes headline comparison tables, value-by-year
charts, a tradeoff frontier, terminal capability comparison,
right-tail false-stop diagnostics, enabler dashboard, seed-level
distributions, representative-run timelines, and per-condition
initiative trajectory plots.

---

## What's next

- [Run Design Guide](guides/run_design_guide.md) — walkthrough of
  the YAML configuration format and authoring your own designs
- [Study Conductor Guide](guides/study_conductor_guide.md) — running
  full experiments end-to-end, interpreting results, working with
  run bundles
