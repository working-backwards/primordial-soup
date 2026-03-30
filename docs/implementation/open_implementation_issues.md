# Open implementation issues

Items here are true implementation blockers, coding-discovered
ambiguities, technical debt intentionally deferred, or future
implementation enhancements. Settled design issues from the design
corpus are not duplicated here.

Closed issues (1–7) have been removed — see git history for details.
New issue tracking uses GitHub Issues.

---

## Open

### 8. Quick-win selection priority

**Status:** OPEN (2026-03-17)

**Files:** `src/primordial_soup/governance.py` (`rank_unassigned_initiatives`)

**Description:** The Balanced policy's selection ranking gives quick wins
no priority despite their short duration. `rank_unassigned_initiatives()`
ranks by prize density (bounded-ceiling first) then quality belief
(descending). Quick wins have no `observable_ceiling` and start at the
same default belief (0.5) as all other types, so they sit at the back
of the id-sorted tiebreak queue. In the baseline run, 41/90 quick wins
were never started and the first completion was tick 206 (Year 4).

**Impact:** This is a legitimate governance finding, not a bug. But it
means all three archetypes systematically deprioritize quick wins.
Duration-aware selection or portfolio-mix targets with quick_win
allocation could be explored as future governance treatments.

**Blocks coding:** No.

---

## Reference — calibration / model revision direction

**Status:** Design-direction notes (not a numbered blocker).

Peer-review consensus on revising domain assumptions (idle vs baseline work,
buffered frontier replenishment, ex-ante rankability, selective observable
thinning) while preserving architectural core. See post_expert_review_plan.md
Step 3 (ex ante rankability) for the next planned implementation step.
