# Primordial Soup

A Monte Carlo simulation study of how governance regimes affect
long-term organizational value creation.

---

## What is this?

Primordial Soup models a portfolio of initiatives with latent quality,
noisy signals, multiple value-creation mechanisms (completion lump,
residual streams, major-win discovery, capability building), and
configurable governance policies that allocate attention, assign
teams, and decide when to stop or continue initiatives.

**The central research question:** under what governance structures do
organizations discover, invest in, and sustain the mix of compounding
mechanisms, speculative opportunities, and capability-building work
that produces long-run value?

!!! note "Study status"
    This study is under active development. The simulation engine is
    stable and well-tested (970+ tests). Calibration reflects realistic
    organizational scale (200-person workforce, mixed team sizes,
    portfolio allocation constraints) and produces meaningful governance
    differentiation. Results may change as calibration is refined.

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

## Where to start

- **New here?** Read the [Study Overview](study_overview.md) for the
  conceptual framing, then the [Research Questions](research_questions.md).
- **Want to run the simulator?** See the [Getting Started](getting-started.md)
  guide.
- **Reviewing the model?** Start with the
  [Design Corpus Reading Order](design/index.md) and follow the
  recommended sequence.
- **Academic audience?** See the [Academic Brief](study/brief_wave.md).
- **Business audience?** See the [Business Brief](study/brief_particle.md).

## Project structure

```
src/primordial_soup/        # simulation engine and analysis modules
scripts/                    # runnable scripts (single run, campaign, diagnostics)
docs/                       # design corpus, guides, and study briefs
templates/                  # YAML run design presets (9 configs)
tests/                      # 970+ tests (pytest)
```

## Development

```bash
git clone https://github.com/working-backwards/primordial-soup.git
cd primordial-soup
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

Dependencies: numpy, mrg32k3a, pyyaml, pyarrow, matplotlib.
Dev tools: pytest, ruff, mypy, pre-commit.
