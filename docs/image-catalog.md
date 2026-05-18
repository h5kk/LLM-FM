# Image Catalog

All images live in `images/` (kebab-case filenames) and are referenced from the README and concept gists.

---

## 1. value.png

**Description:** Side-by-side comparison framed by the question "How does auth work?" The left panel ("Without Feature Memory") lists five manual steps — grepping the codebase, opening 6 files, asking on Slack, reading a stale README, piecing together a mental model — totaling ~20 minutes. The right panel ("With Feature Memory") lists four steps — open `features/auth.md`, read summaries, check source map, glance at recent changes — totaling ~40 seconds. Coral box on the left vs green box on the right emphasizes the contrast.

**Concept:** Core value proposition. The hero image — immediately conveys why FM matters by making the time savings tangible.

**Alt text:** Side-by-side comparison showing ~20 minutes of manual investigation without Feature Memory vs ~40 seconds of reading a compiled feature page with it.

---

## 2. three-layer-architecture.png

**Description:** Three vertically stacked rounded rectangles connected by labeled arrows. Bottom layer (peach): "Source Code — Always the Truth" with example file paths. Middle layer (green): "Feature Memory — Compiled Docs" with doc filenames and capability tags (cross-references, source maps, synthesized changelogs). Top layer (purple): "Consumers" — agents, engineers, PMs, reviewers. A dashed green footer notes "Fully automatic: hooks detect changes in the bottom layer -> compiler updates the middle layer -> consumers always see current docs."

**Concept:** The architectural mental model at a glance. Source is truth, FM compiles it, consumers read from compiled docs.

**Alt text:** Three-layer architecture diagram: source code at the bottom compiled into feature docs in the middle, consumed by agents, engineers, PMs, and reviewers at the top, with a fully automatic hook pipeline connecting the layers.

---

## 3. hook-lifecycle.png

**Description:** Horizontal five-stage timeline — File Edit, Commit, Pull Request, Merge, Nightly — each with a circular icon connected by a light line. Below each stage is a card describing what FM does: log changed path (deterministic <2s), draft ingest from diff (LLM ~15s), impact report (LLM ~30s), promote draft docs (deterministic <30s), stale checks and reorg proposals (LLM unbounded). Green tags for cheap deterministic ops, orange for expensive LLM-batched ops. Legend at the bottom.

**Concept:** Tiered hook architecture showing cost-conscious design — cheap hooks fire often, expensive ones batch at boundaries.

**Alt text:** Five-stage hook lifecycle pipeline from File Edit to Nightly showing deterministic operations (green) at high-frequency triggers and LLM-powered operations (orange) batched at lower-frequency boundaries.

---

## 4. feature-page-anatomy.png

**Description:** Annotated mock-up of a compiled feature page (`features/auth.md`). Shows YAML frontmatter (type, feature_id, status, confidence, source_paths, related_features), followed by sections: one-sentence summary, product summary, engineering summary, source map table, and recent changes log. Right-margin annotations label sections as "queryable metadata," "for PMs + designers," "for engineers," and "verifiable provenance." Green "EXAMPLE" badge at top.

**Concept:** Concrete example of FM's core output artifact. Shows every section a feature page contains and who each section serves.

**Alt text:** Annotated Feature Memory page for auth showing YAML metadata, layered summaries for different audiences, a source map table, and recent changes, with margin annotations explaining each section's purpose.

---

## 5. project-structure-example.png

**Description:** Split layout. Left: indented file tree showing `docs/feature-memory/` (compiled docs) and `.feature-memory/` (internal state) alongside normal project folders, with `CLAUDE.md` at the root. Right: three explanatory cards — compiled docs ("what agents and humans read"), internal state ("glitchproof machinery"), and a CLAUDE.md connection snippet showing the one-line instruction that bridges the agent to FM. Green "EXAMPLE" badge at top.

**Concept:** How FM fits into an existing project with minimal footprint — two directories and one instruction line.

**Alt text:** Diagram showing Feature Memory's two directories (docs/feature-memory for compiled docs, .feature-memory for internal state) and a single CLAUDE.md instruction line integrated into a project file tree.

---

## 6. changelog-raw-vs-synthesized.png

**Description:** Side-by-side comparison. Left ("Without Feature Memory"): dark terminal showing ~10 raw git commit messages (fix, refactor, chore, etc.) with the question "25 commits. Which ones matter?" Right ("Feature Memory changelog"): clean document showing three dated, categorized changelog entries with human-readable summaries. Footer: "3 entries. 15 seconds to read. You're caught up." Green "VALUE" badge at top.

**Concept:** Changelog synthesis — transforming noisy git history into concise, categorized, glanceable summaries.

**Alt text:** Comparison of 25 raw git commit messages versus three concise Feature Memory changelog entries, demonstrating how FM synthesizes git noise into categorized summaries.

---

## 7. cross-reference-propagation.png

**Description:** Shows a single `git commit` to `packages/session/index.ts` triggering updates across three feature pages (auth.md, billing.md, onboarding.md), each with a green checkmark and description of what was auto-updated. Below: index.md and changelog.md also updated. Green callout box explains "Without FM, a developer changing the session helper would never think to update billing or onboarding docs."

**Concept:** Cross-reference propagation — one code change automatically updates every feature page that references the shared dependency.

**Alt text:** Diagram of a single git commit to a shared session helper automatically propagating documentation updates to three feature pages, the index, and the changelog.

---

## 8. data-pipeline.png

**Description:** Two horizontal pipelines stacked vertically. Top ("LLM Wiki by Andrej Karpathy — PRIOR ART"): Raw Sources -> LLM Reads -> Wiki Pages -> Human, shown in gray. Bottom ("Feature Memory"): Code Activity -> Hooks -> FM Compiler -> Feature Docs -> Agents + Humans, shown in green with a dashed "+ MEMORY LAYER" boundary. Four feature badges below: cross-references, synthesized changelogs, reviewer verifies, staleness detection.

**Concept:** Positioning FM vs prior art. FM is automatic (hook-triggered), self-organizing, cross-referenced, and consumed by both agents and humans.

**Alt text:** Pipeline comparison: LLM Wiki's manual linear flow versus Feature Memory's automatic hook-triggered pipeline with cross-references, synthesized changelogs, and staleness detection.

---

## 9. lint-review-pipeline.png

**Description:** Two-column flowchart. Left column ("Lint — deterministic," green): Trigger, Dead path scan, Hash mismatch check, Timestamp delta, Orphan & missing checks -> Lint report. Right column ("Review — LLM-powered," pink): Trigger, Verify claims against code, Check for drift, Validate cross-references, Surface coverage gaps -> Review report. Each step is a numbered card with a bold title and one-line description.

**Concept:** Two-phase quality assurance — fast deterministic lint runs first, then slower LLM-powered semantic review.

**Alt text:** Two-column flowchart showing five deterministic lint steps on the left producing a lint report and five LLM-powered review steps on the right producing a review report.
