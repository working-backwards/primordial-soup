# Diminishing Returns Across Similar Initiatives — Design Note

## Status: Deferred


### Academic
This note explains why a cross-initiative diminishing-returns mechanism
is not implemented in the current study and states the conditions under
which it should be revisited.

### Business
This note explains why a mechanism for diminishing returns across initiatives of the same type is not implemented in the current study, and states the conditions under which it should be revisited.

## What was considered


### Academic
The original proposal identified a potential gap: completing many
initiatives of the same family produces linearly additive value, with
no penalty for saturation. In reality, the tenth quick-win or the fifth
flywheel in the same domain might produce less marginal value than the
first, because the organization has already captured the low-hanging
fruit, saturated its market, or cannibalized its own earlier work.

More precisely, the current model treats the value realized by a
completion as independent of the number of prior completions in the
same family. Each completion lump is a function of the initiative's
own attributes (latent quality, value channel parameters); residual
streams compound at their own rates regardless of how many similar
streams are already active. The value function is additive across
completions within a family. This means the model contains no
mechanism for decreasing marginal returns to concentration — the
phenomenon where the incremental value of the k-th completion in a
family declines with k, not because initiative quality is lower, but
because the cumulative value already captured in that domain reduces
the marginal contribution of each additional unit.

Three possible implementation locations were considered:

1. **Frontier process** — degrade the quality distribution of future
   draws as a family accumulates completions.
2. **Value channels** — discount the realized value of a completion
   based on how many similar completions have already occurred.
   Under this mechanism, the initiative's latent quality and
   resolution dynamics would be unchanged; only the mapping from
   completion to realized value would depend on the family-level
   completion count. This models a situation where the opportunity
   is intrinsically sound but the marginal contribution to an
   already-saturated output space is smaller.
3. **Cross-initiative interaction layer** — introduce a new mechanism
   where completed initiatives of the same family reduce each other's
   marginal value contribution. This would model cannibalization
   directly: a newly activated residual stream partially displacing
   the output of an existing stream in the same family, or a
   completion lump discounted by overlap with value already captured
   by prior completions.

### Business
The original design process identified a potential gap in how the simulation models value accumulation: when an organization completes many initiatives of the same type, the simulation currently treats each completion's value independently. There is no penalty for concentration — the tenth quick win produces as much value as the first, and the fifth flywheel compounds at the same rate regardless of how many similar flywheels are already running.

In real organizations, this is often not the case. The tenth process automation initiative in the same operational area typically produces less marginal value than the first, because the most impactful inefficiencies have already been addressed. The fifth distribution-channel flywheel may cannibalize earlier channels or saturate the addressable market. At some point, repeated investment in the same category encounters diminishing returns — not because the individual initiatives are lower quality, but because the organization has already captured most of the available value in that space.

Three possible locations for implementing this mechanism were considered:

1. **In the opportunity frontier** — degrade the quality of future opportunities as a family accumulates completions. This would mean later initiatives of the same type are inherently less promising, reflecting the idea that the best opportunities are found first.

2. **In the value realization mechanism** — discount the value an initiative produces at completion based on how many similar completions have already occurred. This would mean the initiative itself might be just as good, but the organization extracts less value from it because the marginal contribution to an already-saturated area is smaller.

3. **As a cross-initiative interaction layer** — introduce a new mechanism where completed initiatives of the same type reduce each other's ongoing value contribution. This would model cannibalization directly: a new flywheel partially displacing the returns of an existing one, or a new market expansion overlapping with territory already captured.

## Why it is deferred


### Academic
Stage 3 (dynamic opportunity frontier) already introduced the primary
diminishing-returns mechanism the study needed: **frontier depletion on
the opportunity-supply side**. Each family's quality distribution
degrades as opportunities are consumed. The alpha multiplier declines
with `n_resolved`, so later draws from the frontier are systematically
lower-quality. This captures the core intuition that the opportunity
landscape is finite and the best opportunities are found first.

A second mechanism that discounts the value of repeated completions
would model a **different phenomenon**: market saturation or
cannibalization on the value-realization side, not opportunity
depletion on the supply side. The frontier mechanism shifts the
quality distribution of future draws: `E[q]` declines with
`n_resolved`. A value-discounting mechanism would instead reduce the
mapping from a given completion quality to realized value as a function
of prior completions in the same family — the initiative's latent
quality is unchanged, but the value it produces at completion is
discounted. These are formally distinct: the first operates on the
input distribution to the generation process; the second operates on
the output mapping of the value-realization function. Conflating them
in a single model without the ability to attribute effects to one or
the other would reduce, not increase, the study's analytical power.

This is not obviously wrong, but it is:

- **A new hypothesis**, not a generic realism fix. Different study
  questions would require different saturation models (e.g., residual
  decay acceleration, lump-value discounting, cross-family interaction).
  Specifically: cannibalization of residual streams (a new completion
  reducing the effective output rate of existing streams in the same
  family) is a different functional form from lump-value discounting
  (the k-th completion lump scaled by a decreasing function of k),
  which is different again from cross-family interaction (a completion
  in one family reducing the marginal value of completions in another).
  Each represents a distinct hypothesis about the structure of
  diminishing returns, and each would require its own specification,
  calibration, and justification.
- **Currently underspecified.** There is no concrete functional form,
  no calibration evidence, and no identified research question that
  requires it. The open design questions include: which value channels
  are affected (completion lumps, residual streams, or both), what
  the discount function's domain and argument are (number of prior
  completions, cumulative realized value, or some saturation index),
  whether the mechanism operates within families or across them, and
  how it interacts with the frontier degradation already in place.
  Implementing without these specifics would mean inventing
  load-bearing modeling decisions during coding rather than deriving
  them from the study's research questions.
- **Risk of interpretation blur.** If both supply-side depletion
  (frontier degradation) and demand-side saturation (value discounting)
  are active simultaneously, it becomes difficult to attribute
  diminishing returns to either mechanism. When a governance regime
  that concentrates heavily in one family shows declining returns,
  the analysis cannot distinguish whether the frontier degraded
  (supply-side, operating through lower `E[q]` of future draws) or
  the completed portfolio is saturated (demand-side, operating
  through discounted value realization for a given `q`). The study
  would lose the ability to identify the causal pathway, which would
  weaken rather than strengthen the governance findings.

### Business
Stage 3 of the implementation — the dynamic opportunity frontier — already introduced the primary diminishing-returns mechanism the study needed: **declining opportunity quality on the supply side**. As described in the frontier design, each family's quality distribution degrades as the organization works through its best possibilities. Later opportunities drawn from the frontier are systematically less promising than earlier ones. This captures the core organizational intuition that the opportunity landscape is finite: the most compelling automation opportunities, the most attractive market expansions, and the most impactful platform investments surface first, and what remains after the organization has pursued its best options is, on average, less valuable.

A second mechanism that discounts the value of repeated completions would model a **different phenomenon**: market saturation or cannibalization on the value-realization side, not opportunity depletion on the supply side. The frontier mechanism says "later opportunities are less promising." A value-discounting mechanism would say "even if a later opportunity is just as good, the organization gets less out of it because the space is already crowded with its own prior work." These are genuinely different dynamics, and conflating them would obscure the study's ability to understand either one.

The value-discounting mechanism is not implemented because it is:

- **A new hypothesis, not a generic realism improvement.** Different research questions would require different saturation models. Cannibalization of residual streams (a new flywheel partially displacing an older one's compounding returns) is a different mechanism from lump-value discounting (each successive quick win producing a smaller one-time payoff), which is different again from cross-family interaction (a flywheel investment reducing the marginal value of a quick win in the same domain). Each of these represents a specific organizational hypothesis about how value saturation works, and each would need its own design, calibration, and justification.

- **Currently underspecified.** There is no concrete proposal for how the discount would work — which value channels it would affect, how steeply it would apply, whether it would operate within families or across them, or how it would interact with the frontier degradation that is already in place. Implementing a mechanism without these specifics would mean inventing load-bearing design decisions during coding rather than grounding them in the study's research questions.

- **A risk to interpretive clarity.** If both supply-side depletion (the frontier produces lower-quality opportunities over time) and demand-side saturation (completed initiatives produce less value as concentration increases) are active simultaneously, it becomes difficult to attribute diminishing returns to either mechanism in the analysis. When a governance regime that concentrates heavily in one family shows declining returns, is that because the frontier degraded (supply-side) or because the completed portfolio is saturated (demand-side)? The study would lose the ability to distinguish these effects cleanly, which would weaken rather than strengthen the governance findings.

## When to revisit


### Academic
Implement a cross-initiative diminishing-returns mechanism only when:

1. A specific research question requires it — e.g., "How does governance
   respond when repeated investments in the same category produce
   declining marginal value?" The question must distinguish between
   supply-side depletion (already modeled by the frontier) and
   demand-side saturation (the mechanism under consideration). If the
   research question is answerable under frontier degradation alone,
   the additional mechanism is not needed.
2. The mechanism is specified concretely: which value channels are
   affected, what functional form the discount takes, and how it
   interacts with frontier degradation. Specifically: does the
   discount apply to residual stream rates (reducing the per-tick
   output of newly activated streams as a function of the number of
   active streams in the same family), to completion lump values
   (scaling the k-th lump by a decreasing function of k), or to
   both? Is the discount argument the number of prior completions,
   the cumulative value already realized, or some other measure of
   concentration? Are the frontier degradation and value-realization
   discount additive, multiplicative, or does one subsume the other
   in certain parameter regimes?
3. The interaction with frontier depletion is understood well enough
   to attribute effects cleanly in analysis. If both mechanisms are
   active, the experimental design must support identification —
   the study must be able to distinguish supply-side depletion from
   demand-side saturation in its findings. Without that ability,
   adding the mechanism reduces interpretive clarity rather than
   increasing it.

Until these conditions are met, the frontier degradation mechanism
provides sufficient diminishing-returns dynamics for the study's
current research questions. The supply-side mechanism — later draws
from a family's frontier have lower expected quality because the
alpha parameter of the generating Beta distribution declines with
`n_resolved` — captures the primary diminishing-returns dynamic, and
it does so in a way that is cleanly attributable in analysis because
it operates through a single, identified causal pathway.

### Business
A cross-initiative diminishing-returns mechanism on the value-realization side should be implemented only when three conditions are met:

1. **A specific research question requires it.** For example: "How does governance respond when repeated investments in the same category produce declining marginal value — not because the opportunities are worse, but because the organization has saturated that space?" This is a meaningful question about organizational strategy, but it is not one the current study is designed to answer.

2. **The mechanism is specified concretely.** Which value channels are affected — do residual streams from flywheels decay as more flywheels complete, do completion lump values shrink, or do both happen? What is the functional form of the discount — does it scale with the number of completions, with the cumulative value already captured, or with some measure of market saturation? How does it interact with the frontier degradation that is already in place — are the two mechanisms additive, or does one subsume the other in certain regimes?

3. **The interaction with frontier depletion is understood well enough to attribute effects cleanly in analysis.** If both mechanisms are active, the study must be able to distinguish supply-side depletion from demand-side saturation in its findings. Without that ability, adding the mechanism reduces interpretive clarity rather than increasing realism.

Until these conditions are met, the frontier degradation mechanism provides sufficient diminishing-returns dynamics for the study's current research questions. The supply-side mechanism — later opportunities are less promising because the best have already been pursued — captures the most important organizational reality, and it does so in a way that is cleanly attributable in analysis.

## References


### Academic
- `docs/design/dynamic_opportunity_frontier.md` — frontier degradation
  mechanism (the supply-side diminishing returns already implemented)
- `docs/implementation/2026-03-16 Implementation Plan.md` — Stage 6
  deferral rationale

### Business
- `docs/design/dynamic_opportunity_frontier.md` — the frontier degradation mechanism, which provides supply-side diminishing returns by degrading the quality of newly emerging opportunities as each family's landscape is consumed
- `docs/implementation/2026-03-16 Implementation Plan.md` — Stage 6 deferral rationale, where the decision to defer value-side diminishing returns was recorded in the implementation sequence
