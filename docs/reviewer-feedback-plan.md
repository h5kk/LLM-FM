# Plan: Address Reviewer Feedback on Feature Memory

## Context

A reviewer gave feedback on the Feature Memory concept gists. Three concerns were raised. This plan assesses each one against what's already in the gists and the `docs/specs/` code specs, and recommends where to address them.

---

## Concern 1: Confidence score lifecycle is vague

**"Who sets initial confidence? How does it decay? How does it recover after review?"**

### What exists today

| Location | What it says |
|----------|-------------|
| Gist (minimal) | Mapping algorithm assigns `high/medium/low` per source_path match type |
| Spec 02 (data model) | `confidence: Literal["low", "medium", "high"]`, default `low` |
| Spec 03 (`fm ingest --llm`) | Sets `confidence: medium` and `review_status: needs_review` on LLM-generated updates |
| Spec 03 (`fm lint` FM015) | Flags "Low-confidence mapping older than 14 days" |

### What's missing

- **Initial confidence on feature pages** (vs per-path): unclear. New draft pages get `low` by default, but no explanation of when they graduate.
- **Decay**: Only the lint check (FM015) and staleness detection (hash, 90-day, dead paths) indirectly address this. No explicit "confidence decays from high to medium after X" rule.
- **Recovery**: No specification of what happens after `fm review` passes. Does confidence go up? Does `review_status` change to `reviewed`? (The `ReviewStatus` enum has `reviewed` but nothing triggers it.)
- **Who sets it**: Both agent (via mapping algorithm) and human (manual edits) can set it, but this isn't spelled out.

### Verdict: Needs addressing

**In gists:** Add a short "Confidence Lifecycle" section explaining transitions (who sets, when it decays, when it recovers).

**In specs:** 
- Spec 03: `fm review` should set `review_status: reviewed` and optionally bump confidence when findings are resolved.
- Spec 03: `fm ingest` should downgrade confidence when staleness is detected (hash mismatch → `needs_review`, dead path → `low`).

---

## Concern 2: What if reviewer disagrees with maintainer?

**"In practice this conflict tends to resolve to whoever has write access — maybe a contradiction?"**

### What exists today

| Location | What it says |
|----------|-------------|
| Full gist | "maintainer writes → reviewer checks → human approves → docs commit" |
| Full gist | Reviewer "cannot edit canonical docs" — just verifies |
| Spec 03 (`fm review`) | Reviewer outputs `decision: pass | needs_review | block` and structured findings |
| Spec 02 (finding schema) | `FindingStatus = Literal["open", "resolved", "wontfix"]` |
| Pre-commit hook | `fm lint --fail-on blocking` blocks commit on blocking severity |

### What's missing

- **Explicit escalation flow**: If reviewer says "block" and maintainer wrote the claim, what happens next? The human gate is stated but the path from "reviewer flags issue" → "human resolves" → "docs land" isn't specified.
- **The contradiction**: Reviewer is read-only but its findings can block the commit via the pre-commit hook. This isn't actually a contradiction — it's enforcement without write access (like a CI check). But the gists don't make this clear.
- **Practical resolution**: In automated flows (nightly, post-commit), reviewer findings just accumulate as `open` findings. For PR flows, they appear in the PR comment. The human is the tiebreaker. This needs to be stated explicitly.

### Verdict: Needs addressing (mostly in gists, minor in specs)

**In gists:** Add a "Conflict Resolution" paragraph in the Reviewer section. Clarify: reviewer produces findings → findings are advisory unless `blocking` severity → `blocking` findings gate the commit/PR → human resolves (fix the doc, override as `wontfix`, or side with reviewer). The reviewer never overwrites; the maintainer never silently ignores a `blocking` finding.

**In specs:** The mechanism already exists (finding status + severity + pre-commit hook). Just need to document the resolution workflow in spec 03's `fm review` section or a new "review workflow" subsection.

---

## Concern 3: Must verify feature memory is accurate before agent acts on it

**"Before the agent acts on feature memory, need to verify if still accurate. Imagine the agent reads the doc first and the code doesn't match."**

### What exists today

| Location | What it says |
|----------|-------------|
| Full gist | Staleness detection: hash mismatch, 90-day silence, dead paths |
| Spec 03 (`fm context --for-agent`) | Prints compact summary with "likely affected features" but NO staleness warnings |
| Spec 05 (skill) | "Read affected feature docs" — no "verify before trusting" instruction |
| CLAUDE.md snippet | "Read the relevant feature page before editing" — no staleness caveat |

### What's missing

- **Context injection doesn't flag stale pages**: If auth's source hash is stale, the SessionStart hook doesn't warn the agent.
- **Skill doesn't instruct "verify first"**: The workflow says "Read affected feature docs" then "Make updates" — no step for "check if the page is still accurate."
- **Dangerous failure mode**: Agent reads a stale page claiming "LoginForm validates emails client-side", code was refactored to server-side validation, agent makes changes trusting the old behavior.

### Verdict: Needs addressing in both gists and specs/code

**In gists:** Add a "Verify Before Trust" principle. Something like: "The feature page is a cache, not a source of truth. Before acting on a claim, verify the source paths still support it — especially if `review_status: needs_review` or staleness signals are present."

**In specs:**
- Spec 03: `fm context --for-agent` should include a staleness summary, e.g., "⚠ auth: source hash stale (last verified 2026-04-01)"
- Spec 05: Skill workflow should add a step: "If the feature page is marked `needs_review` or `stale`, verify key claims against source files before trusting them."
- Spec 04: SessionStart hook output should include stale feature warnings when present.

---

## Summary: What to change where

### Gists (conceptual docs — both files)

1. **Add "Confidence Lifecycle" section** — who sets initial (mapping algorithm for paths, `low` for new pages, LLM sets `medium`), how it decays (staleness signals downgrade), how it recovers (human review or `fm review` pass → `high`)
2. **Expand Reviewer section with conflict resolution** — findings are advisory unless blocking, blocking gates commit, human is tiebreaker, finding status tracks resolution
3. **Add "Verify Before Trust" principle** — feature page is a cache not truth, agent must verify stale claims against source before acting

### Specs (code-level — existing files)

| File | Change |
|------|--------|
| `docs/specs/02-data-model.md` | Add a "Confidence transitions" subsection with state machine rules |
| `docs/specs/03-core-commands.md` | `fm context --for-agent`: add staleness warnings to output |
| `docs/specs/03-core-commands.md` | `fm review`: add "post-review state changes" (set `review_status: reviewed`, optionally bump confidence) |
| `docs/specs/03-core-commands.md` | `fm ingest`: document confidence downgrade on staleness |
| `docs/specs/05-skills.md` | Add "verify stale pages" step to skill workflow |
| `docs/specs/04-hooks-and-triggers.md` | SessionStart hook: include stale feature warnings in context |

### Plugin code (when implemented)

The data model already supports all needed fields. The changes are behavioral:
- `fm context` output format gains a staleness section
- `fm review` gains a post-review state update
- `fm ingest` gains confidence downgrade logic on staleness detection
- Skill instructions gain a verification step

---

## Verification

After changes:
1. Read both gists — the three concerns should be directly addressable by pointing to a specific section
2. Read spec 02 — confidence transitions should be a clear state diagram
3. Read spec 03 — `fm context` output should show staleness, `fm review` should document what state changes after review
4. Read spec 05 — skill workflow should include a "verify if stale" step
