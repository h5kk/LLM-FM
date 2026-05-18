---
description: >
  Maintains Feature Memory docs for changed source files. Keeps product summaries,
  engineering summaries, source maps, relationships, and changelogs current.
  Use when the user asks about architecture, feature docs, repo memory, changelogs,
  or when code changes may affect docs.
allowed-tools: Bash, Read, Grep, Glob, Edit, Write
---

# Feature Memory Maintainer

## Live context

Feature Memory docs are at `docs/feature-memory/`.

## When to activate

- User asks about project architecture, features, or how something works
- User asks to update docs after a change
- Code changes affect user-facing behavior, APIs, routes, data models, or tests
- User mentions "feature memory", "docs update", "changelog", or "source map"
- After significant code changes that touch multiple files

## Instructions

You maintain `docs/feature-memory/` as a compiled memory layer for this repository.

### Workflow

1. Identify which files changed (read the diff or ask the user).
2. Check `.feature-memory/config.yaml` to map changed paths to features.
3. Detect the layout for each affected feature:
   - If `docs/feature-memory/features/{id}/index.md` exists → **split mode**
   - Otherwise → **small mode** (`features/{id}.md`)
4. Read the affected feature page(s).
5. Verify key claims against the current source code.
6. Update docs based on layout:
   - **Small mode**: update `features/{id}.md` — product summary, engineering summary, source map, and both changelog sections
   - **Split mode**: route updates to the appropriate sub-page:
     - User-facing behavior changes → `features/{id}/product.md`
     - Internal/technical changes → `features/{id}/engineering.md`
     - All changes → append to both sub-page changelogs + `features/{id}/index.md` updated date
7. Determine the **audience** for this change:
   - `product` — user-facing behavior, UI, API contract, product-visible fix
   - `developer` — internal refactor, dependency change, test change, config change
   - `both` — when it affects both (default if unsure)
8. Append a structured changelog entry to the feature's changelog section with the audience.
9. Update `docs/feature-memory/index.md` if a feature's summary or status changed.
10. Update `docs/feature-memory/recent.md` with today's changes.
11. If the change adds or removes a relationship between features, regenerate the Mermaid diagram in `index.md` (see diagram rules below).
12. Summarize what changed and what could not be verified.

### Changelog entry format

In feature pages, append entries under the appropriate audience heading:

```markdown
## Changelog

### Developer

- YYYY-MM-DD: <Engineering-level description. Cite files changed.>

### Product

- YYYY-MM-DD: <User-facing description. Plain language.>
```

For split-mode features, the changelogs live in `product.md` and `engineering.md` respectively.

**Audience assignment rules:**
- Default is `both` unless the change is clearly internal (refactor, test, config) or clearly user-facing
- Refactors, test changes, dependency bumps → `developer` only
- New user-visible features, UI changes, API contract changes → `both`
- Bug fixes that affect user behavior → `both`; fixes that are invisible to users → `developer`

### Relationship link syntax

In `## Relationships` sections, use these link forms:
- `[[feature-id]]` — sibling relationship
- `[[feature-id|parent]]` — that feature is a parent of this one
- `[[feature-id|child]]` — that feature is a child of this one
- `[[feature-id|reuses]]` — this feature reuses a shared component

### Diagram regeneration rules

Regenerate the Mermaid diagram in `docs/feature-memory/index.md` **only when**:
- A relationship link is added or removed from a feature page
- A new feature page is created
- A feature is deprecated or removed

To regenerate:
1. Read `## Relationships` from every feature page under `features/`
2. Extract all `[[id]]`, `[[id|parent]]`, `[[id|child]]`, `[[id|reuses]]` links
3. Convert to Mermaid edges:
   - `[[id]]` sibling: `A --- B` (deduplicate — add only one direction)
   - `[[id|parent]]`: `id --> current` (parent → child direction)
   - `[[id|child]]`: `current --> id`
   - `[[id|reuses]]`: `current -.-> id`
4. Replace the `graph TD` block in `index.md`

### Rules

1. Raw code and project sources are the source of truth. Never fabricate behavior claims.
2. Update only docs that are affected by the current change.
3. Keep product summaries short, direct, and useful to non-engineers.
4. Keep engineering summaries concise but source-grounded. Name files, routes, components, and tests.
5. Add or update source maps when files move or features change.
6. Append changelog entries. Never erase history.
7. Mark uncertain claims with `confidence: low` or `review_status: needs_review`.
8. Propose renames, moves, merges, and hierarchy changes in `docs/feature-memory/reports/`. Do not apply them automatically.
9. Cite source paths for every factual claim about code behavior.
10. **Verify before trusting**: If a feature page has `review_status: needs_review` or `stale`, or `confidence: low`, verify key claims against source files before relying on them.
11. Do not regenerate the Mermaid diagram unless relationships actually changed — it adds noise to diffs.

### Initialization

If `docs/feature-memory/` does not exist, tell the user to say "initialize feature memory" to trigger the `feature-memory-init` skill, which scaffolds the structure and scans the project for features.
