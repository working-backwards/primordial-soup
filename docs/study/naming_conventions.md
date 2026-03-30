# Primordial Soup naming conventions

## Role of this document

This document defines the canonical naming convention for the Primordial Soup
corpus.

Its purpose is to make the design easier to read and the implementation easier
to follow without sacrificing mathematical clarity.

**Enforcement:** Domain naming (symbol → descriptive name, style preferences) is
enforced only via this document and the Claude rules in `CLAUDE.md`. We do not
use linter rules (e.g. Ruff pep8-naming) or pre-commit hooks for domain naming;
those would conflict with schema-matching identifiers (e.g. `T_tam`, `C_max`)
and cannot express the mapping table. Follow this doc and the Naming section in
`CLAUDE.md`; reviewers and the implementation plan reference the same.

The rule is simple:

- equations may use compact symbolic notation,
- prose, pseudocode, schema commentary, examples, and code should use
  descriptive snake_case names by default,
- and the mapping between the two should remain stable across the corpus.

### Use compact symbols in equations

Examples:

- `c_t`
- `c_exec_t`
- `q`
- `q_exec`
- `sigma_eff`
- `T_tam`
- `W_stag`

### Use descriptive names everywhere else

Examples:

- `quality_belief_t`
- `execution_belief_t`
- `latent_quality`
- `latent_execution_fidelity`
- `effective_signal_st_dev_t`
- `base_tam_patience_window`
- `effective_tam_patience_window`
- `stagnation_window_staffed_ticks`

### Mapping table (symbol → descriptive name)

| Symbolic notation | Descriptive name |
|---|---|
| `c_t` | `quality_belief_t` |
| `c_exec_t` | `execution_belief_t` |
| `q` | `latent_quality` |
| `q_exec` | `latent_execution_fidelity` |
| `sigma_eff` | `effective_signal_st_dev_t` |
| `sigma_base` | `base_signal_st_dev` |
| `eta` | `learning_rate` |
| `eta_exec` | `execution_learning_rate` |
| `d` | `dependency_level` |
| `a` | `executive_attention_t` |
| `C_t` | `portfolio_capability_t` |
| `C_max` | `max_portfolio_capability` |
| `T_tam` | `base_tam_patience_window` |
| `T_tam_effective` | `effective_tam_patience_window` |
| `θ_tam_ratio` | `tam_threshold_ratio` |
| `θ_stop` | `confidence_decline_threshold` |
| `W_stag` | `stagnation_window_staffed_ticks` |
| `ε_stag` | `stagnation_belief_change_threshold` |
| `R` | `ramp_period_ticks` |
| `g(a)` | `attention_noise_modifier` |
| `g_min` | `min_attention_noise_modifier` |
| `g_max` | `max_attention_noise_modifier` |
| `k` | `attention_curve_exponent` |
| `k_low` | `low_attention_penalty_slope` |
| `a_min` | `attention_noise_threshold` |
| `mu` | `mean` |
| `sigma` | `st_dev` |
| `E[v_prize]` | `expected_prize_value` |
| `E[v_lump]` | `expected_completion_lump_value` |
| `Δ_c` | `belief_change_over_window` |
| `τ_residual` | `ticks_since_residual_activation` |

### Code and comments

Code should use the descriptive names by default.

When a code path directly implements a documented equation, comments may include
the compact symbolic notation as a secondary reference, for example:

`quality_belief_t  # c_t in the design docs`

The implementation should not invent a third naming dialect.

### Prose and documentation

When a section introduces or explains a mechanism:

- use descriptive names in the explanatory prose,
- keep equations compact,
- and, where helpful, explicitly bind the symbol to the descriptive name once at
  the start of the section.

This is the preferred pattern for future edits to the corpus.

---

## Style preferences

Prefer:

- `mean` over `mu`
- `st_dev` over `sigma`, `std`, or Greek letters in prose and code
- `latent_quality` over single-letter names in prose and code
- `quality_belief_t` over names that preserve cryptic source letters
- `ticks_since_...` over Greek time-index notation in prose and code

Do not preserve symbolic letters inside descriptive names unless doing so is
genuinely helpful. For example, prefer `quality_belief_t` to `belief_c_t`.
