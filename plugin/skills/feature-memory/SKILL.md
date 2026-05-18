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
3. Read the affected feature pages under `docs/feature-memory/features/`.
4. Verify key claims against the current source code.
5. Update product summary, engineering summary, source map, and changelog only where needed.
6. Update `docs/feature-memory/index.md` if a feature's summary or status changed.
7. Update `docs/feature-memory/recent.md` with today's changes.
8. Summarize what changed and what could not be verified.

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

### Initialization

If `docs/feature-memory/` does not exist, tell the user to say "initialize feature memory" to trigger the `feature-memory-init` skill, which scaffolds the structure and scans the project for features.
