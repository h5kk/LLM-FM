---
description: >
  Initializes Feature Memory in the current project. Creates the docs structure,
  config, and event log. Scans the codebase to detect features and creates initial
  feature pages. Use when the user says "initialize feature memory", "set up FM",
  "bootstrap docs", or "scan and create feature pages".
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

Present the proposed features to the user as a list:
- Feature ID (slug), title, source globs
- Ask: "Should I create pages for these? Add or remove any?"

**Wait for confirmation before proceeding.**

## Step 4: Create feature pages

For each confirmed feature, create `docs/feature-memory/features/{id}.md`:

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

## Changelog

- YYYY-MM-DD: Initial documentation created
```

Read key source files (first 80 lines each) to write grounded summaries. Cite actual paths.

## Step 5: Update config, index, and logs

1. **config.yaml**: Add each feature under `features:` with its globs:
   ```yaml
   features:
     auth:
       globs:
         - "src/auth/**"
         - "routes/auth.*"
         - "tests/test_auth.*"
   ```

2. **index.md**: Add a row per feature to the table.

3. **recent.md**: Add today's entries.

4. **changelog.md**: Add initialization entries per feature.

## Step 6: Report

Summarize what was created:
- Number of features documented
- Files created
- Suggest: "Review pages and bump confidence to 'high' after verifying claims."
