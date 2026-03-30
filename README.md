# Primordial Soup

A Monte Carlo simulation study of how governance regimes affect
long-term organizational value creation.

The simulator models a portfolio of initiatives with latent quality,
noisy signals, multiple value-creation mechanisms (completion lump,
residual streams, major-win discovery, capability building), and
configurable governance policies that allocate attention, assign
teams, and decide when to stop or continue initiatives.

The central research question: under what governance structures do
organizations discover, invest in, and sustain the mix of compounding
mechanisms, speculative opportunities, and capability-building work
that produces long-run value?

> **Study status:** This study is under active development. The
> simulation engine is stable and well-tested (970+ tests). Calibration
> reflects realistic organizational scale (200-person workforce, mixed
> team sizes, portfolio allocation constraints) and produces
> meaningful governance differentiation. Results may change as
> calibration is refined.

---

## Quick start

### Prerequisites

- Python 3.12+
- Git

### Install

```bash
git clone <repo-url> && cd primordial-soup
python -m venv .venv
source .venv/bin/activate        # macOS/Linux
# .venv\Scripts\activate         # Windows PowerShell
pip install -e ".[dev]"
```

### Verify

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

### Level 2: Compare governance regimes (console output)

```bash
python scripts/baseline_governance_campaign.py
python scripts/baseline_governance_campaign.py --seeds 3    # fewer seeds = faster
```

Runs all three governance archetypes across all three environment
families (Balanced Incumbent, Short Cycle Throughput, Discovery
Heavy) with multiple seeds. Prints comparison tables to the console:
value by channel, initiative outcomes by family, timing metrics,
frontier state, and policy deltas vs. the Balanced baseline.

This is a 3 x 3 x 7 = 63-run experiment by default. Takes about
a minute.

### Level 3: Produce a full analysis package (run bundle)

```bash
python scripts/run_experiment.py --output-dir runs/
python scripts/run_experiment.py --seeds 3 --output-dir runs/   # smaller
python scripts/run_experiment.py --families balanced_incumbent --presets balanced --seeds 2 --output-dir runs/  # minimal
```

Produces a self-contained **run bundle** — the canonical on-disk
artifact for the study. Open `report/index.html` in a browser to
see the full report.

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

## Project structure

```
src/primordial_soup/
    runner.py              # tick-loop orchestration (the only impure module)
    tick.py                # pure tick-step and action-application functions
    reporting.py           # RunResult, profiles, and aggregation
    config.py              # SimulationConfiguration and validation
    state.py               # WorldState, InitiativeState, TeamState
    governance.py          # decision primitives (pure functions)
    policy.py              # governance archetypes (Balanced, Aggressive, Patient)
    observation.py         # observation boundary (what governance can see)
    pool.py                # initiative pool generation
    noise.py               # MRG32k3a RNG isolation
    presets.py             # environment families and archetype factories
    evaluator.py           # optimizer-facing evaluation interface
    campaign.py            # experiment design and LHS sweep generation
    diagnostics.py         # ground-truth diagnostic metrics (post-hoc)
    run_bundle.py          # run-bundle creation and orchestration
    tables.py              # Parquet table generation
    figures.py             # matplotlib figure generation
    report_gen.py          # HTML and markdown report generation
    bundle_validation.py   # run-bundle validation

scripts/
    run_design.py                      # Level 1: single YAML-configured run bundle
    baseline_governance_campaign.py    # Level 2: comparison tables
    run_experiment.py                  # Level 3: full multi-condition run bundle
    ground_truth_diagnostics.py        # false-stop, survival, hazard analysis
    fragility_mapping.py               # 3D parameter-sensitivity grid sweep
    calibration_sanity_check.py        # right-tail calibration verification
    validate_environment_families.py   # environment family consistency checks

docs/
    study_overview.md                  # conceptual overview (authoritative)
    research_questions.md              # analytical questions the study addresses
    study/
        brief_wave.md                  #   study brief — academic audience
        brief_particle.md              #   study brief — business audience
    design/                            # design corpus
        index.md                       #   reading order and authority
        canonical_core.md              #   irreducible study identity
        core_simulator.md              #   tick ordering and equations
        governance.md                  #   governance architecture and policy
        initiative_model.md            #   initiative lifecycle and value
        interfaces.md                  #   configuration and output contracts
    guides/
        run_design_guide.md            #   YAML run design walkthrough
        study_conductor_guide.md       #   running experiments end-to-end
    implementation/                    # implementation docs
        reporting_package_specification.md

templates/                             # YAML run design presets (9 configs)

tests/                                 # 970+ tests (pytest)
```

---

## Key concepts

**Four initiative families:**
- **Flywheel** — high-quality, long-duration, residual value streams
- **Right-tail** — speculative, may surface rare major wins on completion
- **Enabler** — builds portfolio capability that benefits all work
- **Quick win** — short-duration, small completion-lump value

**Three governance archetypes:**
- **Balanced** — all stop rules active, moderate thresholds
- **Aggressive Stop-Loss** — tighter thresholds, faster redeployment
- **Patient Moonshot** — confidence-decline disabled, longer patience

**Three environment families:**
- **Balanced Incumbent** — moderate opportunity mix
- **Short Cycle Throughput** — favors fast completion
- **Discovery Heavy** — richer right-tail opportunities

**Primary outcomes:**
- **Total priced value** — lump + residual (does NOT include major wins)
- **Surfaced major wins** — count of right-tail breakthroughs (surfaced, not priced by design)
- **Terminal capability** — organizational learning environment at horizon

---

## Documentation

- [Study Overview](docs/study_overview.md) — conceptual overview
  of the research question and scope
- [Research Questions](docs/research_questions.md) — analytical
  questions the study is designed to answer
- [Study Brief — Academic](docs/study/brief_wave.md) — model
  structure and experimental design for a technical audience
- [Study Brief — Business](docs/study/brief_particle.md) — what the
  study does and why it matters for a practitioner audience
- [Design Corpus Index](docs/design/index.md) — reading order and
  authority structure for the full design corpus
- [Reporting Package Specification](docs/implementation/reporting_package_specification.md) —
  run-bundle structure, table schemas, and report requirements

---

## Development

```bash
pip install -e ".[dev]"
pre-commit install

# Tests
pytest

# Type checking
mypy src/

# Linting
ruff check src/ tests/ scripts/
```

Dependencies: numpy, mrg32k3a, pyyaml, pyarrow, matplotlib.
Dev tools: pytest, ruff, mypy, pre-commit.
