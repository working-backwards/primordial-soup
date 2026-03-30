# Analysis and experimentation layer

## Role of this document


### Academic
This document defines the post-run analysis layer for the canonical Primordial
Soup study.

`review_and_reporting.md` defines what the simulator must emit. This document
defines how those outputs are intended to be consumed for learning:

- deterministic summary and comparison generation,
- exploratory interpretation,
- anomaly detection,
- follow-up experiment suggestion,
- and iterative refinement of the experiment set.

It is not authoritative about simulator mechanics. It is authoritative about the
workflow that sits downstream of simulator execution.

### Business
This document defines what happens after the simulation runs are complete — how the results are intended to be examined, compared, and used to generate actionable insight.

The reporting and output specification defines what the simulator must produce. This document defines the discipline for learning from those outputs:

- generating standardized comparisons across governance regimes,
- exploring the results for patterns, surprises, and interactions that were not anticipated in advance,
- identifying anomalies that may signal either genuine findings or implementation issues,
- designing follow-up experiments to test promising hypotheses,
- and refining the set of governance regimes under study as understanding deepens.

This document does not define how the simulation works. It defines how the organization learns from what the simulation produces.

## Core principle


### Academic
The simulator is analyst-agnostic. It should not know whether its outputs will
be consumed by:

- a human analyst,
- an AI analyst,
- or a hybrid human-AI workflow.

The analysis layer therefore works from the same deterministic evidentiary base
regardless of analyst modality.

The intended structure is:

1. the simulator emits canonical outputs,
2. deterministic post-processing computes agreed summaries and derived features,
3. exploratory interpretation may be done by humans, AI systems, or both,
4. no interpreted claim becomes a study finding until it is checked against the
   deterministic outputs.

Step 2 carries a strict reproducibility invariant: the same post-processing code
applied to the same raw outputs must produce identical summaries regardless of
when, where, or by whom it is executed. This is the condition under which
deterministic derived artifacts qualify as part of the evidentiary base rather
than as analyst-dependent interpretations.

The foundational methodological principle is the separation of observation from
inference. The analysis layer is structured so that the evidentiary record
(Layers 1 and 2) is fully determined before any interpretive claim is advanced,
and no interpretive claim acquires the status of a study finding without
traceability to that record. This separation is load-bearing: it is the
mechanism by which the study prevents narrative-driven conclusions from
substituting for evidence-driven conclusions.

### Business
The simulation produces the same structured evidence regardless of who or what will analyze it. It does not know whether a human analyst, an AI system, or a combined team will examine its outputs, and it does not need to know.

This is a deliberate design choice. The analysis workflow is built on a principle that any serious governance review process should follow:

1. The simulation produces its raw results — the factual record of what happened under each governance regime in each environment.
2. A standardized processing step computes agreed-upon comparisons and summaries from those results. These computations are deterministic: anyone running the same processing code on the same results will get identical summaries.
3. Exploratory interpretation — looking for patterns, surprises, interactions, and hypotheses — may be done by people, AI systems, or both working together.
4. No interpreted claim becomes a study finding until it has been checked against the deterministic outputs.

The point is to separate what the evidence shows from what someone thinks the evidence means. This separation is the foundation of the entire analysis discipline.

## Why this layer exists


### Academic
The study is about accelerating learning and value creation under uncertainty.
The analysis workflow should reflect that same principle.

Static reporting alone is not sufficient for the kinds of questions this study is
trying to answer. Many of the key findings will be about:

- interaction effects across governance and environment,
- threshold behavior and inflection points,
- phase changes in regime performance,
- anomalous or unexpectedly fragile regions of the parameter space,
- and candidate regimes worth testing after an initial sweep.

Those are not always visible in a small fixed dashboard. The analysis layer
therefore exists to support structured iterative learning from the simulator's
outputs.

### Business
The study is about how organizations learn and create value under uncertainty. The analysis workflow should embody that same principle — it should be designed for iterative learning, not one-shot reporting.

A fixed dashboard or static set of charts is not sufficient for the kinds of questions this study is designed to answer. Many of the most important findings will involve:

- how governance choices and environmental conditions interact — a governance approach that works well in one type of opportunity environment may fail in another,
- tipping points where small changes in governance posture produce large changes in outcomes,
- regions where a governance regime's apparent advantage is fragile or dependent on specific conditions,
- surprising reversals where a regime that looks strong on one metric looks weak on another,
- and governance approaches worth testing that only become visible after examining the initial results.

These are not the kinds of findings that surface in a summary table. They require structured exploration — the ability to follow leads, test hypotheses against the evidence, and design targeted follow-up experiments when the initial results point somewhere interesting. The analysis layer exists to support that kind of disciplined investigative work.

## Layers of evidence


### Academic
The analysis workflow should preserve a strict distinction between three layers.
This distinction is the structural mechanism that prevents the study from
conflating what the evidence shows with what an analyst believes the evidence
means.

#### 1. Raw simulation outputs

These are the artifacts emitted directly by the engine and defined in
`review_and_reporting.md`: run manifests, per-tick records, event records, and
primary outputs.

#### 2. Deterministic derived analytical artifacts

These are computed from raw outputs by explicit code and should be reproducible
from the same inputs. Examples include:

- regime-level summary tables,
- pairwise regime comparisons,
- effect-size tables,
- confidence intervals,
- dominance comparisons,
- environment-conditioned subgroup summaries,
- anomaly flags based on deterministic rules,
- and candidate interaction summaries computed from fixed procedures.

These derived artifacts should be treated as part of the study's evidentiary
surface. They are reproducible computations over raw outputs, not interpretive
claims. Their status as evidence depends on the reproducibility invariant
described under Core principle: any analyst applying the same code to the same
raw outputs must obtain identical derived artifacts.

#### 3. Interpretive conclusions and hypotheses

These are statements such as:

- "patient governance dominates only when ramp cost is low,"
- "large-TAM patience appears valuable only in specific ceiling distributions,"
- "this region of the sweep suggests a new regime worth testing,"
- "the apparent regime advantage may actually be driven by one environment slice."

These statements may be generated by humans, AI systems, or both. They are not
study findings until verified against the first two layers.

The traceability requirement is strict: an interpretive claim that cannot be
traced back to a specific deterministic computation over raw outputs does not
qualify as a study conclusion. A plausible narrative about governance
effectiveness is not evidence. It acquires evidentiary standing only when it
corresponds to a reproducible computation over the canonical outputs.

### Business
The analysis workflow maintains a strict separation between three types of evidence. This separation matters because it prevents the study from drifting from "what the data shows" to "what we think the data means" without anyone noticing.

#### 1. Raw simulation outputs

These are the direct results produced by each simulation run: the complete record of what happened week by week under each governance regime, including every initiative's trajectory, every stop decision, every major-win event, every team assignment, and every resource allocation. These are the primary facts of the study.

#### 2. Standardized comparisons and derived metrics

These are computed from the raw results using explicit, reproducible procedures. Anyone running the same analysis code on the same raw outputs will get identical results. Examples include:

- summary tables showing how each governance regime performed in each environment,
- side-by-side comparisons of governance regimes on the primary outcomes (cumulative value, major-win discovery, organizational capability),
- measures of how large the differences between regimes are and how confident the study is in those differences,
- comparisons showing which regime outperforms which under each set of conditions,
- breakdowns showing how governance performance varies across different types of opportunity environments,
- flags identifying results that fall outside expected ranges based on explicit rules,
- and structured summaries of where governance and environment conditions appear to interact.

These standardized artifacts are part of the study's evidentiary base. They are not interpretations — they are reproducible computations.

#### 3. Interpretive conclusions and hypotheses

These are claims about what the evidence means. Examples:

- "Patient governance outperforms impatient governance only when the cost of switching teams between initiatives is low."
- "Scaling patience with the size of the visible opportunity appears to be valuable only in certain types of environments."
- "This region of the governance parameter space suggests a governance approach worth testing that was not included in the initial sweep."
- "The apparent advantage of regime A may actually be driven by its performance in one specific type of environment rather than being a general advantage."

These interpretive claims may be generated by human analysts, AI systems, or both working together. They are not study findings until they have been verified against the first two layers. The distinction matters: a plausible-sounding narrative about governance effectiveness is not evidence. It becomes evidence only when it can be traced back to reproducible computations on the raw results.

## Deterministic post-processing requirements


### Academic
The implementation should include a deterministic post-processing layer that can
produce at least the following artifacts from a completed experiment batch:

- a regime manifest linking governance parameters, environment parameters, and
  replication seeds,
- regime-by-environment summary tables,
- pairwise regime comparison tables for the primary outcomes,
- uncertainty intervals for each primary outcome,
- summaries keyed to the stated research questions,
- and machine-readable provenance linking every summary back to the source runs.

The primary outcomes referenced above are the three response-variable families
defined in the study design:

1. **Realized economic performance** — cumulative value created over the horizon,
   decomposed into completion-lump value and residual value. Includes the value
   trajectory over time, not merely the terminal level, because residual-stream
   accumulation accelerates as the portfolio of completed flywheel initiatives
   grows.
2. **Major-win discovery performance** — surfaced major-win count, time to first
   major win, and labor per major win.
3. **Organizational capability development** — terminal portfolio capability
   (C_T) and peak portfolio capability during the run.

Pairwise regime comparison tables must report direction, magnitude, and
uncertainty of the difference on each of these response-variable families.

The research-question-aligned summaries must address at minimum:

- How does governance patience affect major-win discovery rates across different
  initiative portfolio compositions?
- Do governance regimes that invest in enablers produce materially different
  long-run capability trajectories?
- What is the relationship between executive attention allocation strategy and
  the quality of stop/continue decisions?

<!-- specification-gap: The document does not specify which statistical methods should be used to construct uncertainty intervals (e.g., independent replications with Student-t, batched means, bootstrap), what confidence level to target, or what effect-size measures to report in pairwise comparisons. An OR reader would expect these choices to be stated explicitly or deferred to a statistical analysis plan with clear criteria. -->

If a claim cannot be traced back to deterministic outputs through this layer, it
should not be treated as a canonical result.

### Business
The implementation must include a standardized analysis layer that can produce at least the following from a completed batch of simulation runs:

- A complete registry linking each run to the governance approach it tested, the opportunity environment it faced, and the specific conditions that defined the run — so that any result can be traced back to the exact configuration that produced it.
- Summary tables organized by governance regime and environment, showing how each approach performed across the primary outcomes.
- Side-by-side comparison tables for every pair of governance regimes on the primary outcomes: cumulative value created, major-win discovery rate, and organizational capability at the end of the horizon.
- Confidence intervals for each primary outcome, so the study can distinguish genuine performance differences from noise.
- Summaries organized around the study's stated research questions — how does governance patience affect major-win discovery? Do enabler-investing regimes build materially different capability trajectories? How does attention allocation strategy affect stop/continue decision quality?
- Machine-readable traceability linking every summary number back to the specific runs that produced it.

If a claim about governance effectiveness cannot be traced back through this layer to the deterministic outputs, it should not be treated as a study finding. This is not a bureaucratic requirement — it is the discipline that makes the difference between a rigorous governance comparison and an anecdotal narrative.

## AI-assisted analysis


### Academic
AI systems may be used in the analysis layer, but only in specific roles.

#### Appropriate uses

- surfacing candidate patterns across many regimes,
- identifying surprising reversals or outliers,
- proposing useful subgroup views or slices,
- generating candidate follow-up experiments,
- suggesting additional governance regimes to test,
- and helping synthesize verified findings into practitioner-facing language.

The comparative advantage of AI-assisted analysis is strongest in the
high-dimensional case: when the experiment batch spans hundreds or thousands of
governance-environment combinations, exhaustive manual inspection of pairwise
comparisons and interaction candidates is impractical. AI triage can prioritize
which regions of the parameter space warrant focused human investigation.

#### Inappropriate uses

- defining simulator behavior,
- computing canonical study metrics,
- replacing deterministic statistical verification,
- silently changing experiment definitions,
- or introducing findings that cannot be traced back to reproducible outputs.

#### Governing rule

AI-assisted analysis is hypothesis-generating and triage-oriented, not
authority-granting.

Any AI-suggested pattern must be checked through deterministic post-processing
before it becomes part of the study's findings.

### Business
AI systems may be used in the analysis process, but only in roles that are appropriate to their strengths and limitations.

#### Where AI adds value

- Scanning results across hundreds or thousands of governance-environment combinations to surface candidate patterns that a human analyst might miss or take weeks to find.
- Identifying surprising reversals — cases where a governance approach that performs well overall performs poorly under specific conditions, or vice versa.
- Proposing useful ways to slice the results: by opportunity environment, by governance parameter, by initiative type, or by other dimensions that reveal structure in the data.
- Generating candidate follow-up experiments when initial results suggest a governance approach worth testing or a region of the parameter space worth exploring more densely.
- Suggesting additional governance regimes to test based on patterns in the existing results.
- Helping translate verified findings into language that practitioners and decision-makers can act on.

#### Where AI should not be used

- Defining how the simulation works. The simulation's mechanics are defined by the design corpus and verified through code and tests, not generated by AI.
- Computing the study's canonical metrics. The standardized comparisons must be produced by explicit, auditable code — not by AI systems whose computations cannot be inspected or reproduced.
- Replacing rigorous statistical verification with AI-generated conclusions. An AI system may identify a pattern worth investigating, but the pattern is not a finding until it has been verified through deterministic analysis.
- Silently modifying experiment definitions. Every experiment must be explicitly defined, versioned, and run under the same reproducibility standards.
- Introducing findings that cannot be traced back to the reproducible evidence base.

#### The governing principle

AI-assisted analysis generates hypotheses and helps prioritize where to look. It does not grant authority to claims. Think of it the way a well-run organization uses consultants or junior analysts: they can surface patterns, do initial triage, and draft narratives — but the findings do not become official until the senior team has verified them against the primary evidence.

Any pattern identified by an AI system must be checked through the deterministic post-processing layer before it becomes part of the study's conclusions.

## Follow-up experiment design


### Academic
The canonical study should not assume that one initial sweep is always enough.
The purpose of the initial sweep is not only to estimate performance, but also to
surface candidate interactions and regions worth deeper inspection.

Follow-up experiments may be proposed when:

- a threshold or phase transition appears in the results,
- a regime shows strong environment dependence,
- an anomaly suggests possible implementation or interpretation issues,
- two regimes appear nearly tied and need denser local comparison,
- or exploratory analysis suggests a plausible regime not represented in the
  initial sweep.

All follow-up experiments should be versioned explicitly. A suggested follow-up
regime is not part of the study until it is written into the experiment
definition and run under the same reproducibility standards as the initial batch.

This requirement prevents progressive drift from reproducible experimental
design into informal exploration presented under the same evidentiary standard
as the initial sweep. Every follow-up experiment, regardless of how it was
motivated, must satisfy the same provenance, versioning, and deterministic
output requirements as the original batch.

### Business
The study should not assume that one initial sweep of governance regimes will answer every question. The initial sweep serves two purposes: estimating how different governance approaches perform, and revealing where deeper investigation is warranted.

Follow-up experiments may be proposed when:

- The results reveal a tipping point — a governance parameter value at which outcomes shift sharply, suggesting the region deserves closer examination.
- A governance regime performs very differently depending on the opportunity environment, and the study needs to understand what drives that sensitivity.
- An anomalous result suggests either a genuine finding worth confirming or a potential implementation issue worth diagnosing.
- Two governance regimes appear nearly indistinguishable on the primary outcomes, and a denser comparison is needed to understand whether there is a meaningful difference or whether the difference depends on conditions not yet examined.
- The initial results suggest a governance approach not included in the original sweep that is worth testing — for example, a hybrid of two regimes that each showed complementary strengths.

All follow-up experiments must be explicitly defined and versioned. A suggested follow-up regime is not part of the study until it has been formally specified and run under the same reproducibility standards as the initial batch. This prevents the study from drifting into informal, unreproducible exploration disguised as rigorous comparison.

The analogy is to how a well-run organization handles pilot programs: the initial pilot surfaces hypotheses and identifies promising directions, but scaling decisions are based on structured follow-up tests with clear criteria — not on extrapolation from the pilot alone.

## Recommended analysis protocol


### Academic
The intended protocol for a completed run batch is:

1. generate deterministic summaries and comparison artifacts,
2. run exploratory interpretation over those artifacts,
3. record candidate findings, anomalies, and follow-up suggestions,
4. verify promising claims with deterministic checks,
5. only then elevate the verified claims into study conclusions.

This protocol applies regardless of whether the exploratory interpretation is
done by a human, an AI system, or both.

The sequence is load-bearing. Step 1 must complete before step 2 begins: the
full deterministic evidence base must be computed before any interpretive
analysis is conducted. This ordering prevents a well-known failure mode in
output analysis — forming a hypothesis from partial inspection of the data and
then selectively querying the remaining evidence for confirmation. By
constructing the complete summary surface first, the protocol ensures that
exploratory interpretation operates over a fixed evidentiary record rather than
co-evolving with it.

Verification in step 4 requires at minimum the following checks for each
candidate finding:

- Does the pattern hold across environment configurations, or is it an artifact
  of a single factor level?
- Is the effect magnitude large enough to be analytically meaningful given the
  uncertainty intervals?
- Could the observed pattern be driven by a specific initial condition or
  parameter region rather than being a structural property of the governance
  policy?

These criteria distinguish robust findings from fragile or conditional patterns
that require further investigation before they can be elevated to study
conclusions.

### Business
The intended protocol for analyzing a completed batch of simulation runs follows a specific sequence, and the sequence matters:

1. **Generate standardized comparisons first.** Before anyone interprets anything, produce the deterministic summary tables, pairwise regime comparisons, and research-question-aligned summaries. These are the facts of the study.
2. **Explore the results.** Look for patterns, surprises, interactions, and anomalies across the standardized outputs. This is where human judgment, AI-assisted pattern recognition, or both add the most value.
3. **Record candidate findings.** Document what looks interesting — including anomalies, potential interactions between governance and environment, and suggestions for follow-up experiments. At this stage, these are hypotheses, not conclusions.
4. **Verify the promising claims.** Go back to the deterministic outputs and check whether each candidate finding holds up. Does the pattern persist across environments? Is the effect large enough to be meaningful? Could it be an artifact of a specific condition rather than a general governance property?
5. **Elevate only verified claims to study conclusions.** A finding becomes part of the study's results only after it has survived verification against the reproducible evidence base.

This protocol applies regardless of whether the exploration in step 2 is done by a human analyst, an AI system, or a combined team. The discipline is the same: facts first, interpretation second, verification before conclusion.

The reason this sequence matters is that it prevents a common failure mode in organizational analysis: starting with a compelling narrative and then selectively citing evidence that supports it. By generating the full evidence base before any interpretation begins, the study ensures that conclusions are shaped by what the data shows rather than by what the analyst expected to find.

## Analyst-facing artifact classes


### Academic
To support both human and AI consumers, the analysis layer should aim to produce
structured artifacts with clear roles, such as:

- `regime_summary`
- `regime_environment_summary`
- `regime_pairwise_comparison`
- `interaction_candidate`
- `anomaly_flag`
- `followup_experiment_suggestion`
- `verified_finding`
- `unverified_hypothesis`

The intended semantics of each class:

- **`regime_summary`** — marginal performance profile of a single governance
  policy, aggregated across all environment configurations and macroreplications
  under which it was evaluated. Contains point estimates and uncertainty
  intervals for each primary response variable.
- **`regime_environment_summary`** — policy performance conditioned on a
  specific environment configuration. The atomic unit for interaction analysis:
  policy effects that vary across environment factor levels are visible only at
  this resolution.
- **`regime_pairwise_comparison`** — direct comparison of two policies on the
  primary response variables, reporting direction, magnitude, and uncertainty of
  the difference. The building block for dominance ordering.
- **`interaction_candidate`** — a structured flag indicating that the effect of
  governance policy on one or more response variables appears to depend on the
  environment factor level — a candidate policy-by-environment interaction in
  the factorial sense. Triggers focused investigation, not automatic
  classification.
- **`anomaly_flag`** — a structured flag indicating that one or more observed
  outcomes fall outside the expected range under a deterministic rule. Anomalies
  may indicate either genuine regime dynamics or implementation issues; the flag
  triggers investigation rather than automatic interpretation.
- **`followup_experiment_suggestion`** — a structured proposal for an
  augmentation to the experimental design: a new policy configuration, a denser
  grid in a region of interest, or an additional environment level. Includes the
  motivating observation and the question the proposed experiment would address.
- **`verified_finding`** — a hypothesis that has been tested against the
  deterministic summary layer and confirmed. The only artifact class that
  qualifies as a study conclusion.
- **`unverified_hypothesis`** — a candidate hypothesis generated during
  exploratory analysis, explicitly labeled as untested against the deterministic
  evidence base. Its epistemic status is provisional until verification is
  completed.

<!-- specification-gap: The anomaly_flag class references "deterministic rules" for identifying out-of-range outcomes but the rules themselves — thresholds, distributional assumptions, or flagging criteria — are not specified in this document. An OR reader would expect either the rule definitions or a reference to where they will be defined. -->

Any consumer of the analysis layer — human or automated — should be able to
determine the epistemic status of an artifact from its class label alone:
reproducible computation, untested hypothesis, or recommendation for further
work.

These names are illustrative rather than prescriptive. The key idea is that the
analysis layer should distinguish evidence, interpretation, and recommendation
rather than flattening them into one report.

### Business
To support both human analysts and AI-assisted analysis workflows, the analysis layer should produce structured outputs with clearly defined roles. Each type of output serves a distinct purpose in the learning process:

- **Regime summary** — a complete profile of how a single governance approach performed across all conditions it was tested in.
- **Regime-environment summary** — how a specific governance approach performed in a specific type of opportunity environment. This is the building block for understanding governance-environment interactions.
- **Regime pairwise comparison** — a direct side-by-side comparison of two governance approaches on the primary outcomes, showing the direction and magnitude of difference.
- **Interaction candidate** — a structured flag indicating that governance performance appears to depend on environmental conditions in a way worth investigating further.
- **Anomaly flag** — a structured flag indicating that a result falls outside expected ranges, warranting examination of whether it reflects a genuine governance dynamic or a potential issue.
- **Follow-up experiment suggestion** — a structured proposal for an additional experiment, including what question it would answer and why the existing results motivate it.
- **Verified finding** — a claim that has been checked against the deterministic evidence base and confirmed. This is the only type of output that should be treated as a study conclusion.
- **Unverified hypothesis** — a plausible claim that has been surfaced through exploration but has not yet been verified. It is explicitly labeled as provisional.

These specific names are illustrative — the implementation may use different labels. The essential principle is that the analysis layer must distinguish between evidence, interpretation, and recommendation rather than combining them into a single undifferentiated report. A reader — whether human or AI — should be able to tell at a glance whether they are looking at a reproducible fact, an unverified hypothesis, or a suggestion for further work.

This matters because governance decisions in real organizations routinely suffer from exactly this conflation. A data team produces a report that mixes verified metrics, exploratory observations, and recommendations without clearly labeling which is which. Leadership acts on the recommendations as if they had the same evidentiary standing as the metrics. The analysis layer is designed to make that confusion structurally impossible.

## Relationship to implementation guidance


### Academic
This document describes the analysis workflow and its intended structure.

`implementation_guidelines.md` describes how the implementation should preserve
the output discipline, provenance, and reproducibility needed for this workflow.
`engineering_standards.md` describes the project hygiene needed to keep the code
base maintainable.

Together, these documents make the study easier to implement, easier to analyze,
and easier to extend.

The three documents form a dependency chain: the implementation produces
trustworthy, reproducible outputs; `review_and_reporting.md` defines the contract
for what those outputs contain; and this document defines how those outputs are
consumed for learning. Each link depends on the integrity of the preceding link.
If the implementation does not preserve reproducibility, the deterministic
post-processing layer cannot guarantee identical summaries from identical inputs.
If the analysis layer does not enforce the distinction between evidence and
interpretation, the study's conclusions lose their traceability guarantee. The
chain is only as strong as its weakest link.

### Business
This document describes how the study's results are intended to be analyzed and what discipline that analysis must follow.

The implementation guidelines describe how the simulation code must be structured to preserve the output quality, traceability, and reproducibility that this analysis workflow depends on. The engineering standards describe the project-level discipline needed to keep the codebase maintainable and auditable.

Together, these three documents form a chain: the implementation produces trustworthy outputs, the reporting layer defines what those outputs contain, and this document defines how those outputs are consumed for learning. Each link depends on the one before it. If the implementation does not preserve reproducibility, the analysis layer cannot verify its claims. If the analysis layer does not distinguish evidence from interpretation, the study's conclusions cannot be trusted.
