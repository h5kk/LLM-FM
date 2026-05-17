# Spec 05 — Skills

> Arch plan refs: section 9 (skill design)

## Objective

Create SKILL.md files for Claude Code and Codex, plus project instruction snippets for CLAUDE.md and AGENTS.md.

---

## 1. Claude Code skill

### File path

`.claude/skills/feature-memory/SKILL.md`

### Contents

```markdown
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

!`fm context --for-agent 2>/dev/null || echo "Feature Memory not initialized. Run fm init to set up."`

## When to activate

- User asks about project architecture, features, or how something works
- User asks to update docs after a change
- Code changes affect user-facing behavior, APIs, routes, data models, or tests
- User mentions "feature memory", "docs update", "changelog", or "source map"
- After significant code changes that touch multiple files

## Instructions

You maintain `docs/feature-memory/` as a compiled memory layer for this repository.

### Rules

1. Raw code and project sources are the source of truth. Never fabricate behavior claims.
2. Update only docs that are affected by the current change.
3. Keep product summaries short, direct, and useful to non-engineers.
4. Keep engineering summaries concise but source-grounded. Name files, routes, components, and tests.
5. Add or update source maps when files move or features change.
6. Append changelog entries. Never erase history.
7. Mark uncertain claims with `confidence: low` or `review_status: needs_review`.
8. Propose renames, moves, merges, and hierarchy changes in `docs/feature-memory/reports/`. Do not apply them automatically.
9. Run `fm lint --changed-only` after edits when the CLI is available.
10. Cite source paths for every factual claim about code behavior.

### Suggested workflow

1. Run `fm detect --diff HEAD --json` or inspect the relevant diff.
2. Run `fm map --paths <changed_paths> --json` for changed paths.
3. Read affected feature docs under `docs/feature-memory/features/`.
4. **Verify before trusting**: If the feature page has `review_status: needs_review` or `stale`, or `confidence: low`, verify key claims against source files before relying on them. Check that source paths exist and that described behavior matches the current code. The feature page is a cache — not a source of truth.
5. Update product summary, engineering summary, source map, relationships, and changelog only where needed.
6. Update `docs/feature-memory/index.md` and `docs/feature-memory/recent.md` if a feature's summary or status changed.
7. Run `fm lint --changed-only` and address any blocking findings.
8. Summarize what changed and what could not be verified.

### Common tasks

**Add a new feature page:**
```bash
fm init  # if not already initialized
# Create docs/feature-memory/features/{feature-id}.md from template
fm lint --changed-only
```

**Update docs after a code change:**
```bash
fm detect --diff HEAD~1..HEAD --json
fm map --paths <paths> --json
# Edit the relevant feature page(s)
fm lint --changed-only
```

**Check docs health:**
```bash
fm lint
fm review --write-report
```
```

---

## 2. Codex skill

### File path

`.agents/skills/feature-memory/SKILL.md`

### Contents

```markdown
---
description: >
  Maintains Feature Memory documentation for changed source files.
  Keeps product summaries, engineering summaries, source maps, relationships,
  and changelogs current. Use when code changes may affect docs or when
  asked about project architecture and features.
---

# Feature Memory Maintainer

## Context

Run `fm context --for-agent` to see current Feature Memory status.

## When to activate

- After code changes that affect user-facing behavior
- When asked about project architecture or features
- When asked to update documentation
- When multiple files change in the same feature area

## Instructions

You maintain `docs/feature-memory/` as a compiled memory layer for this repository.

### Rules

1. Raw code is the source of truth. Never fabricate behavior claims.
2. Update only docs affected by the current change.
3. Product summaries: short, useful to non-engineers.
4. Engineering summaries: concise, name files and routes, cite source paths.
5. Update source maps when files move or features change.
6. Append changelog entries. Never erase history.
7. Mark uncertain claims as `needs_review`.
8. Do not reorganize feature hierarchy. Write proposals to `docs/feature-memory/reports/` instead.
9. Run `fm lint --changed-only` after edits.

### Workflow

1. Run `fm detect --diff HEAD --json` to identify changes.
2. Run `fm map --paths <paths> --json` to find affected features.
3. Read the affected feature pages.
4. **Verify before trusting**: If a page is `needs_review`, `stale`, or `low` confidence, check source paths exist and claims match current code before relying on them.
5. Make the smallest correct doc update.
6. Run `fm lint --changed-only`.
7. Summarize changes and unverified claims.
```

### Differences from Claude skill

- No `allowed-tools` field (not a Claude Code concept).
- No `!` live context syntax (Codex uses `UserPromptSubmit` hooks for context injection).
- Simpler formatting for broader compatibility.

---

## 3. CLAUDE.md project instruction

Add this block to the project's `CLAUDE.md`:

```markdown
## Feature Memory

This repo uses Feature Memory under `docs/feature-memory/`. The `feature-memory` skill is available for maintaining feature documentation.

Before changing a major feature, read the relevant feature page if it exists under `docs/feature-memory/features/`.

After changing user-facing behavior, APIs, routes, data models, components, or tests, update the affected feature docs or invoke the `feature-memory` skill.

Do not reorganize feature hierarchy automatically. Write a proposal under `docs/feature-memory/reports/` instead.

The `fm` CLI is available for deterministic operations: `fm detect`, `fm map`, `fm lint`, `fm ingest`.
```

---

## 4. AGENTS.md project instruction

> **Note:** The AGENTS.md and CLAUDE.md snippets are intentionally similar. CLAUDE.md targets Claude Code specifically (references the skill by name, mentions `fm` CLI). AGENTS.md targets any agent (Codex, Cursor, Windsurf, etc.) with a vendor-neutral framing. Projects using only Claude Code can skip AGENTS.md; projects using multiple agents should include both.

Add this block to the project's `AGENTS.md`:

```markdown
## Feature Memory

This repo uses Feature Memory under `docs/feature-memory/`.

- Before changing a major feature, read the relevant feature page if it exists.
- After changing user-facing behavior, APIs, routes, data models, components, or tests, update the affected feature docs. The `fm` CLI provides: `fm detect`, `fm map`, `fm lint`, `fm ingest`.
- Do not reorganize feature hierarchy automatically; write a proposal under `docs/feature-memory/reports/`.
- Use `fm lint --changed-only` to verify docs health after changes.
```

---

## 5. Skill testing checklist

### Manual test scenarios

| # | Scenario | Expected behavior |
|---|----------|-------------------|
| 1 | Ask "how does auth work?" | Skill activates, reads feature page, answers from compiled docs |
| 2 | Ask "update docs for auth" | Skill runs detect/map, updates the auth feature page |
| 3 | Make a code change, then ask about docs | Skill detects the change and suggests updating affected docs |
| 4 | Ask "run feature memory lint" | Skill runs `fm lint` and reports findings |
| 5 | Ask about a feature that doesn't exist yet | Skill suggests creating a new feature page |
| 6 | Ask to reorganize features | Skill creates a proposal instead of directly reorganizing |
| 7 | Ask about project architecture | Skill reads index.md and summarizes the feature landscape |

### Automated skill testing

Use Claude Code's skill evaluation framework (if available) or manual test scripts:

```bash
# Test that the skill description triggers on relevant queries
echo "How does the auth feature work in this project?" | fm-test-skill-trigger
echo "Update the documentation for billing" | fm-test-skill-trigger
echo "What features does this project have?" | fm-test-skill-trigger
```

---

## Key deliverables

- [ ] Claude SKILL.md written with correct frontmatter, live context, rules, and workflow
- [ ] Codex SKILL.md written with compatible format
- [ ] CLAUDE.md snippet ready to add
- [ ] AGENTS.md snippet ready to add
- [ ] All 7 manual test scenarios documented
- [ ] Skills reference `fm` CLI commands correctly
- [ ] Live context command (`fm context --for-agent`) works when FM is initialized
