---
description: >
  Initializes Feature Memory in the current project. Creates the docs structure,
  config, changelog viewer, and event log. Scans the codebase to detect features
  and creates initial feature pages. Use when the user says "initialize feature
  memory", "set up FM", "bootstrap docs", or "scan and create feature pages".
allowed-tools: Bash, Read, Grep, Glob, Edit, Write
---

# Feature Memory Init

## When to activate

- User says "initialize feature memory", "set up FM", "bootstrap feature memory"
- User says "scan this project and create feature pages"
- `docs/feature-memory/` does not exist and user asks about feature docs

## Pre-check

Before doing anything, check if `docs/feature-memory/index.md` exists. If it does, tell the user FM is already initialized and offer to re-scan for new features instead.

## Step 1: Scaffold the directory structure

Create these files and directories:

### `docs/feature-memory/index.md`
```markdown
---
type: index
schema_version: 1
updated: "YYYY-MM-DD"
---

# Feature Memory Index

| Feature | Summary | Status | Review | Updated |
|---------|---------|--------|--------|---------|

## Relationship Diagram

```mermaid
graph TD
```
```

### `docs/feature-memory/recent.md`
```markdown
---
type: recent
updated: "YYYY-MM-DD"
---

# Recent Activity

- YYYY-MM-DD: Feature Memory initialized
```

### `docs/feature-memory/changelog.md`
```markdown
---
type: changelog
updated: "YYYY-MM-DD"
---

# Feature Memory Changelog

## YYYY-MM-DD

- **system**: Feature Memory initialized for this project
```

### `docs/feature-memory/features/` (empty directory — use .gitkeep)
### `docs/feature-memory/reports/` (empty directory — use .gitkeep)
### `docs/feature-memory/changelogs/` (empty directory)
### `docs/feature-memory/custom/` (empty directory — use .gitkeep)

User-authored custom changelog entries and wiki docs live here. They are
re-scanned fresh on every Stop into a SEPARATE viewer data slot
(`custom-docs-data`) and never written into `changelog.json`. Author them via
the `/feature-memory-changelog-custom` skill.

### `docs/feature-memory/changelogs/changelog.json`
```json
{
  "schema_version": 2,
  "generated": "YYYY-MM-DDTHH:MM:SSZ",
  "entries": []
}
```

### `docs/feature-memory/changelog-viewer.html`

Copy the viewer template from the plugin assets. If the plugin root is available via `${CLAUDE_PLUGIN_ROOT}`, copy from `${CLAUDE_PLUGIN_ROOT}/assets/changelog-viewer.html`. Otherwise create a minimal placeholder with a note to copy the template.

### `.feature-memory/config.yaml`
```yaml
schema_version: 1
project_name: <detected-from-directory-name>
docs_root: docs/feature-memory
mode: small

features: {}

mapping:
  default_confidence: medium
  unmapped_policy: report
  route_patterns:
    - "routes/{feature}.py"
    - "src/routes/{feature}.ts"
  test_patterns:
    - "tests/test_*.py"
    - "**/*_test.*"
    - "**/*.test.*"

# Optional — changelog configurability (omission keeps default behavior).
changelog:
  verbosity: normal          # terse | normal | detailed
  summary_rule: ""           # optional steering instruction for topic tagging
  tagging: true              # master switch; false => no topic tags
  highlight_tags:
    - breaking-change
    - api-change
    - security
    - schema-change
    - data-migration
  metrics:
    enabled: true
    code_churn: false        # backfill-only git numstat (--code-churn)
  custom_docs:
    enabled: true
    dir: docs/feature-memory/custom
```

### `.feature-memory/events.jsonl` (empty file)

Replace `YYYY-MM-DD` with today's date.

## Step 2: Scan the project

Use Glob to inventory the codebase:

1. Find top-level source directories: `src/*`, `app/*`, `lib/*`, `packages/*`
2. Find route/controller files: `**/routes/**`, `**/controllers/**`, `**/api/**`
3. Find test directories: `tests/**`, `__tests__/**`
4. Read `package.json`, `pyproject.toml`, `README.md`, or similar for project context

## Step 3: Propose features

Identify features by heuristic:
- Each immediate subdirectory of `src/` (or equivalent) is likely a feature
- Each route file that groups endpoints is likely a feature
- Group related tests with their source directories

For each proposed feature, estimate its size (number of source files). Mark features with 10+ source files as candidates for split mode.

Present the proposed features to the user:
- Feature ID (slug), title, source globs, estimated file count
- For large features: "This feature has N source files. Use split mode (sub-folder with product/engineering/changelog pages)?"
- Ask: "Should I create pages for these? Add or remove any? Mark any as split mode?"

**Wait for confirmation before proceeding.**

## Step 4: Create feature pages

### Small mode (default): single file

For each confirmed small-mode feature, create `docs/feature-memory/features/{id}.md`:

```markdown
---
title: <Feature Title>
id: <feature-id>
status: active
confidence: medium
review_status: needs_review
updated: "YYYY-MM-DD"
source_count: <N>
test_count: <N>
---

# <Feature Title>

## Product summary

<One paragraph: what this feature does for users.>

## Engineering summary

<One paragraph: key files, patterns, dependencies. Cite paths.>

## Source map

| Path | Role | Notes |
|------|------|-------|
| <path> | <role> | <notes> |

## Relationships

- <links to related features via [[feature-id]]>
  - Use `[[feature-id]]` for siblings
  - Use `[[feature-id|parent]]` for parent features
  - Use `[[feature-id|child]]` for child features
  - Use `[[feature-id|reuses]]` for shared components

## Changelog

### Developer

- YYYY-MM-DD: Initial documentation created

### Product

- YYYY-MM-DD: Feature documented
```

### Split mode: sub-folder

For each confirmed split-mode feature, create `docs/feature-memory/features/{id}/`:

**`features/{id}/index.md`** (navigation hub):
```markdown
---
title: <Feature Title>
id: <feature-id>
type: feature
status: active
confidence: medium
review_status: needs_review
updated: "YYYY-MM-DD"
---

# <Feature Title>

<One-sentence summary.>

- [Product summary](product.md)
- [Engineering summary](engineering.md)
- [Changelog](changelog.md)

## Relationships

- <[[feature-id]] links>
```

**`features/{id}/product.md`** (product audience):
```markdown
---
type: feature-section
section: product
parent_feature: <feature-id>
audience: product
updated: "YYYY-MM-DD"
---

# <Feature Title> — Product Summary

## What it does

<One paragraph for non-engineers.>

## Changelog

- YYYY-MM-DD: Initial documentation created
```

**`features/{id}/engineering.md`** (engineering audience):
```markdown
---
type: feature-section
section: engineering
parent_feature: <feature-id>
audience: developer
updated: "YYYY-MM-DD"
---

# <Feature Title> — Engineering Summary

## Overview

<One paragraph: key files, patterns, dependencies. Cite paths.>

## Source map

| Path | Role | Notes |
|------|------|-------|

## Changelog

- YYYY-MM-DD: Initial documentation created
```

Read key source files (first 80 lines each) to write grounded summaries. Cite actual paths.

## Step 5: Update config, index, and logs

1. **config.yaml**: Add each feature under `features:` with its globs. For split-mode features, add `mode: split`:
   ```yaml
   features:
     auth:
       mode: split
       globs:
         - "src/auth/**"
         - "routes/auth.*"
         - "tests/test_auth.*"
     billing:
       globs:
         - "src/billing/**"
   ```

2. **index.md**: Add a row per feature to the table.

3. **recent.md**: Add today's entries.

4. **changelog.md**: Add initialization entries per feature.

## Step 6: Generate relationship diagram

After all feature pages are created, generate the Mermaid diagram in `docs/feature-memory/index.md`.

Parse each feature page's `## Relationships` section and extract `[[feature-id]]` links:
- `[[id]]` → sibling edge: `A --- B`
- `[[id|parent]]` → parent edge: `id --> A` (parent points to child)
- `[[id|child]]` → child edge: `A --> id`
- `[[id|reuses]]` → reuse edge: `A -.-> id`

Replace the `graph TD` block in `index.md` with the compiled diagram. If there are no relationships, leave the block empty with a comment.

## Step 7: Report

Summarize what was created:
- Number of features documented (N small, M split)
- Files created
- Changelog viewer available at `docs/feature-memory/changelog-viewer.html`
- Suggest: "Review pages and bump confidence to 'high' after verifying claims."
