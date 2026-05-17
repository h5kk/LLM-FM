# Spec 03 — Core Commands

> Arch plan refs: sections 6 (CLI design), 13 (feature mapping algorithm), 14 (write policy), 17 (lint checks)

## Objective

Implement every `fm` subcommand. This is the largest spec and the core product.

---

## 1. `fm init`

### Synopsis

```
fm init [--docs-dir PATH] [--mode small|split|mixed] [--project-name NAME]
```

### Behavior

1. Create the docs directory tree:
   ```
   {docs_root}/
     index.md          # empty index from template
     recent.md         # empty recent from template
     changelog.md      # empty global changelog
     README.md         # human explanation of the system
     features/         # empty dir
     reports/          # empty dir
   ```
2. Create the metadata directory:
   ```
   .feature-memory/
     config.yaml       # default config with project_name and docs_root
     schemas/          # JSON schema files exported from pydantic models
     proposals/        # empty dir
     hooks/            # empty dir
   ```
3. Initialize `state.sqlite` with the DDL from spec 02.
4. Print a summary of what was created.

### Flags

| Flag | Default | Effect |
|------|---------|--------|
| `--docs-dir` | `docs/feature-memory` | Set `docs_root` in config |
| `--mode` | `mixed` | Set `mode` in config |
| `--project-name` | directory name | Set `project_name` in config |

### Idempotency

If directories/files already exist, skip them and report "already exists". Never overwrite existing files.

### Exit codes

- 0: success
- 1: error (e.g., filesystem permission)

---

## 2. `fm detect`

### Synopsis

```
fm detect --diff REF [--json]
fm detect --paths PATH... [--json]
fm detect --since-session [--json]
```

### Behavior

1. **`--diff REF`**: Run `git diff --name-status REF` and parse the output. Extract added, modified, deleted, and renamed paths.
2. **`--paths PATH...`**: Accept explicit file paths.
3. **`--since-session`**: Read `.feature-memory/events.jsonl` for `path_touched` events from the current session.

For each path, produce a `FileFact`:

```python
from typing import Literal
from fm.models import FileKind  # Literal type defined in spec 02

FileStatus = Literal["added", "modified", "deleted", "renamed"]
Language = Literal["typescript", "python", "go", "yaml", "json", "markdown", "unknown"]


class FileFact(BaseModel):
    path: str
    status: FileStatus
    kind: FileKind
    language: Language
    symbols: list[str] = []
    likely_user_facing: bool = False
    rename_from: str | None = None
```

### File classification rules

| Pattern | Kind |
|---------|------|
| `*.test.*`, `*.spec.*`, `*_test.*`, `test_*.*` | test |
| `**/routes/**`, `**/api/**`, `**/endpoints/**` | api-route |
| `**/components/**`, `*.tsx`, `*.vue`, `*.svelte` | ui-component |
| `**/models/**`, `**/schemas/**`, `**/entities/**` | model |
| `**/migrations/**`, `**/migrate/**` | migration |
| `*.yaml`, `*.yml`, `*.toml`, `*.json`, `*.ini` | config |
| `**/utils/**`, `**/helpers/**`, `**/lib/**` | util |
| everything else | unknown |

### Symbol extraction

Best-effort, regex-based (no AST dependency in MVP):

- **TypeScript/JavaScript**: match `export (default )?(function|class|const|let|type|interface|enum) (\w+)`
- **Python**: match `^(class|def) (\w+)` at top indent level
- **Go**: match `^func (\w+)`

### `likely_user_facing` heuristic

True if kind is `ui-component`, `api-route`, or `migration`. Also true if the path matches any route pattern from config.

### Output

```json
{
  "changed_paths": ["apps/web/src/auth/LoginForm.tsx"],
  "file_facts": [
    {
      "path": "apps/web/src/auth/LoginForm.tsx",
      "status": "modified",
      "kind": "ui-component",
      "language": "typescript",
      "symbols": ["LoginForm"],
      "likely_user_facing": true,
      "rename_from": null
    }
  ],
  "deleted_paths": [],
  "renamed_paths": []
}
```

---

## 3. `fm map`

### Synopsis

```
fm map --paths PATH... [--json]
fm map --detect-output FILE [--json]
```

### Behavior

Takes paths (or piped detect output) and maps each to zero or more feature IDs with confidence. Implements the 8-step algorithm from arch plan section 13.

### Mapping algorithm implementation

Execute steps in order. Stop at the first match that produces `high` confidence, or continue to accumulate `medium`/`low` candidates.

```python
class FeatureMapping(BaseModel):
    path: str
    feature_id: str
    confidence: str          # high | medium | low
    reason: str              # human-readable explanation
    step: int                # which algorithm step matched (1-8)


def map_paths(paths: list[str], config: FmConfig, db: FmDatabase) -> MapResult:
    ...
```

#### Step 1: Exact source map match

Query `source_path` table. If the path exists with a `feature_id`, return `high` confidence.

```python
def _step1_source_map(path: str, db: FmDatabase) -> FeatureMapping | None:
    row = db.get_features_for_path(path)
    if row:
        return FeatureMapping(path=path, feature_id=row[0]["feature_id"],
                              confidence="high", reason="Exact source map match", step=1)
    return None
```

#### Step 2: Config glob match

Check `config.features[*].globs` against the path using `fnmatch` or `pathlib.PurePath.match`.

#### Step 3: Route pattern match

Check `config.mapping.route_patterns`. Extract the `{feature}` capture group and look up the feature ID.

**Route pattern syntax:**

Route patterns use `{feature}` as a named placeholder that captures a single path segment (no slashes). The placeholder is converted to a regex group `([^/]+)` for matching. The captured value is normalized to kebab-case and matched against known feature IDs and their aliases.

Examples:
- `routes/{feature}.ts` matches `routes/billing.ts` → captures `billing`
- `apps/api/src/routes/{feature}.ts` matches `apps/api/src/routes/auth.ts` → captures `auth`
- `apps/web/src/app/{feature}/**` matches `apps/web/src/app/billing/Checkout.tsx` → captures `billing`

The `**` wildcard matches any remaining path segments (standard glob). Only `{feature}` is a named capture; other path segments must match literally.

#### Step 4: Directory name match

Extract directory segments from the path. Match against existing feature IDs/slugs. Return `medium` confidence.

#### Step 5: Import graph hint

*Deferred to Phase 2.* Placeholder that returns `None`.

#### Step 6: Text/symbol hint

Match detected symbols (from `fm detect`) against feature titles and aliases. Use case-insensitive substring matching. Return `low` confidence.

#### Step 7: Embedding hint

*Deferred to post-MVP.* Placeholder that returns `None`.

#### Step 8: Unknown path policy

Apply `config.mapping.unmapped_policy`:
- `ignore`: skip
- `report`: include in output as unmapped
- `create_draft`: create a draft feature page with the directory name as feature_id

### Output

```json
{
  "mappings": [
    {
      "path": "apps/web/src/auth/LoginForm.tsx",
      "feature_id": "auth",
      "confidence": "high",
      "reason": "Config glob match: apps/web/src/auth/**",
      "step": 2
    }
  ],
  "unmapped_paths": [],
  "draft_features_created": []
}
```

---

## 4. `fm ingest`

### Synopsis

```
fm ingest --diff REF [--no-llm | --llm | --draft-only] [--json]
fm ingest --paths PATH... [--no-llm | --llm | --draft-only] [--json]
```

### Pipeline

```
detect → map → read existing docs → [generate patches] → update source maps
→ append changelogs → update index/recent → validate → write findings
```

### Modes

| Mode | Summary updates | Source maps | Changelogs | Writes to canonical docs |
|------|----------------|------------|------------|--------------------------|
| `--no-llm` (default) | No | Yes | Stub entries | Yes (metadata only) |
| `--llm` | Yes (via LLM) | Yes | Full entries | Yes |
| `--draft-only` | Yes if --llm | Yes | Full entries | No (writes to `.feature-memory/proposals/`) |

### `--no-llm` behavior (Phase 1)

1. Run `fm detect` internally.
2. Run `fm map` internally.
3. For each mapped feature:
   - Update `updated` and `last_code_touch` timestamps in frontmatter.
   - Add/update source map entries for changed paths.
   - Append a changelog stub: date, paths, kind (from detect), `needs_review`.
4. Update `index.md` timestamps.
5. Update `recent.md` with the new changes.
6. Run `fm lint --changed-only` internally and report findings.

### `--llm` behavior (Phase 2)

Same as `--no-llm`, plus:

1. For each mapped feature, read the existing feature page and the diff/file contents.
2. Send to the configured LLM with the **maintainer prompt** (see below).
3. Parse the LLM response as a structured patch: updated product summary, engineering summary, and changelog entry.
4. Apply the patch to the feature page.
5. Mark the update with `confidence: medium` and `review_status: needs_review`.
6. If staleness was detected during ingest (source hash mismatch or dead paths), downgrade confidence accordingly:
   - Source hash mismatch on a `high` confidence feature → downgrade to `medium`
   - Dead source path → downgrade to `low`, remove path from source_map

#### Maintainer prompt

```
You are a documentation maintainer for the "{project_name}" project.

Your job: given a diff and the current feature page, produce an update patch.

## Context

Feature: {feature_title} ({feature_id})
Current feature page:
---
{current_feature_page_content}
---

Diff:
```
{diff_content}
```

Changed files (full content if short, excerpts if long):
{source_file_contents}

## Instructions

1. Analyze the diff to understand what changed in terms of behavior, APIs, UI, and data flow.
2. Update the product summary ONLY if user-visible behavior changed. Keep it under 3 sentences.
3. Update the engineering summary to reflect new/changed files, routes, or components. Cite exact file paths.
4. Update the source map table: add new paths, mark removed paths, update roles.
5. Write a changelog entry: one sentence describing what changed, with the kind (behavior-change, refactor, new-feature, bug-fix, etc.).
6. Do NOT fabricate behavior. If you are unsure, mark confidence as "low" and add to "Open questions".

## Output format (JSON)

{
  "product_summary": "Updated text or null if unchanged",
  "engineering_summary": "Updated text or null if unchanged",
  "source_map_additions": [{"path": "...", "kind": "...", "role": "..."}],
  "source_map_removals": ["path1", "path2"],
  "changelog_entry": {
    "summary": "One sentence",
    "kind": ["behavior-change"],
    "confidence": "medium"
  },
  "open_questions": []
}
```

### `--draft-only` behavior

Write all updates to `.feature-memory/proposals/ingest-{timestamp}.yaml` instead of canonical docs. The proposal can be reviewed and applied with `fm apply-proposal`.

### Output

```json
{
  "features_updated": ["auth"],
  "features_created": [],
  "changelog_entries": 1,
  "findings": [],
  "mode": "no-llm"
}
```

---

## 5. `fm lint`

### Synopsis

```
fm lint [--changed-only] [--fail-on SEVERITY] [--fix] [--json]
```

### Deterministic checks

| ID | Description | Implementation | Auto-fixable |
|----|-------------|----------------|-------------|
| FM001 | Broken wikilink | Regex `\[\[.*?\]\]`, resolve against feature index | No |
| FM002 | Feature has no source paths in frontmatter | Check `source_paths` field | No |
| FM003 | Source path in frontmatter no longer exists on disk | `Path.exists()` check | Yes (remove) |
| FM004 | Duplicate `feature_id` across pages | Scan all frontmatter | No |
| FM005 | Feature has no product summary | Check `## Product / business summary` section is non-empty | No |
| FM006 | Feature has no engineering summary | Check `## Engineering summary` section is non-empty | No |
| FM007 | Current behavior section has no source map | Check `## Source map` table has rows | No |
| FM008 | Relationship points to nonexistent feature | Cross-reference `related_features` against index | Yes (remove) |
| FM009 | Hierarchy cycle detected | Topological sort of parent/child edges | No |
| FM010 | Changelog entry missing date | Regex check on changelog entries | No |
| FM011 | `recent.md` is out of sync | Compare recent.md content against last N days of changelog | Yes (regenerate) |
| FM012 | `index.md` is missing a known feature | Compare index entries against feature pages on disk | Yes (add entry) |
| FM013 | Feature marked active but no source path seen in N days | Compare `last_code_touch` against threshold (default 90 days) | No |
| FM014 | Open proposal older than N days (default 14) | Check proposal files' timestamps | No |
| FM015 | Low-confidence mapping older than N days (default 14) | Query `source_path` table | No |

### `--changed-only`

Only lint features that were touched since the last ingest. Uses `events.jsonl` or accepts a `--diff` ref.

### `--fail-on SEVERITY`

Exit with code 2 if any finding meets or exceeds the given severity. Default: do not fail (exit 0 with warnings).

### `--fix`

Auto-fix findings marked as auto-fixable. Report what was fixed.

### Output

```json
{
  "findings": [
    {
      "id": "FM003",
      "severity": "medium",
      "feature_id": "auth",
      "message": "Source path apps/web/src/auth/OldForm.tsx no longer exists.",
      "auto_fixable": true
    }
  ],
  "summary": { "info": 0, "low": 0, "medium": 1, "high": 0, "blocking": 0 }
}
```

---

## 6. `fm review`

### Synopsis

```
fm review [--feature ID] [--diff REF] [--write-report] [--strict] [--fail-on SEVERITY] [--json]
```

### Behavior

1. Run all deterministic lint checks first.
2. If `--strict` or LLM is available, run LLM-assisted checks (FM101-FM109, arch plan section 17).
3. Produce a review report.

### LLM-assisted checks (Phase 2)

| ID | Description |
|----|-------------|
| FM101 | Unsupported claim in product summary |
| FM102 | Unsupported claim in engineering summary |
| FM103 | Stale current-behavior claim |
| FM104 | Likely duplicate feature |
| FM105 | Missing child feature |
| FM106 | Suspicious parent/child relation |
| FM107 | Privacy or roadmap leakage |
| FM108 | Summary too verbose for audience |
| FM109 | Changed behavior not reflected in docs |

### Reviewer prompt

Send the following to the configured LLM:
- The feature page content
- The diff (if `--diff` provided)
- The relevant source files (read from disk)

Parse the LLM response as structured findings.

```
You are a documentation reviewer for the "{project_name}" project.

Your job: verify that a feature page is accurate, complete, and grounded in source code.

## Feature page to review

{feature_page_content}

## Source files

{source_file_contents}

## Diff (if available)

{diff_content_or_none}

## Instructions

For each claim in the product summary and engineering summary:
1. Verify it against the source files. If the source does not support the claim, flag it.
2. Check if behavior described as "current" still exists in the code.
3. Check if the diff introduced behavior not reflected in the docs.
4. Flag any privacy-sensitive content (API keys, internal URLs, employee names, roadmap details).
5. Flag if product summary contains implementation details, or engineering summary contains marketing language.

## Output format (JSON)

{
  "summary": "Brief review summary",
  "decision": "pass | needs_review | block",
  "findings": [
    {
      "severity": "info | low | medium | high | blocking",
      "category": "stale-claim | missing-source | broken-link | unsupported-claim | hierarchy-risk | privacy-risk",
      "feature_id": "...",
      "claim": "The specific claim being questioned",
      "evidence": ["path or reference"],
      "recommendation": "What to do"
    }
  ]
}
```

### Post-review state changes

After `fm review` completes, update feature metadata based on the decision:

| Decision | Confidence change | Review status change |
|----------|------------------|---------------------|
| `pass` | Bump to `high` (if currently `medium`) | Set `reviewed` |
| `needs_review` | No change | Keep `needs_review` |
| `block` | No change | Set `blocked` |

When a blocking finding is later resolved (human marks it `resolved` or `wontfix`):
- If no other blocking findings remain, set `review_status: needs_review` (requires re-review to reach `reviewed`).

### Conflict resolution workflow

```
reviewer flags issue → finding recorded with severity → gate or advise
  advisory (info/low/medium/high): surfaced in reports and PR comments, does not block
  blocking: gates commit (pre-commit hook) or PR merge
  resolution: human fixes doc (sides with reviewer),
              marks wontfix (sides with maintainer, must provide justification),
              or escalates
```

The reviewer never edits docs. The maintainer never silently ignores a `blocking` finding. The human is always the tiebreaker.

### `--write-report`

Write the review report to `docs/feature-memory/reports/review-{date}.md`.

### Output

```json
{
  "summary": "Auth review: 1 unsupported claim, 2 stale source paths.",
  "decision": "needs_review",
  "findings": [ ... ]
}
```

---

## 7. `fm propose-reorg`

### Synopsis

```
fm propose-reorg [--kind merge|split|rename|restructure] [--features ID...] [--json]
```

### Behavior

1. Analyze feature docs for overlap, orphans, hierarchy issues, or naming inconsistencies.
2. Generate a proposal YAML file in `.feature-memory/proposals/`.
3. Do not mutate canonical docs.

### Output

Writes a proposal file and prints its path.

---

## 8. `fm apply-proposal`

### Synopsis

```
fm apply-proposal PATH [--dry-run] [--json]
```

### Behavior

1. Read the proposal YAML.
2. Execute each change in the `changes` array (move files, update frontmatter, etc.).
3. Run `fm lint --changed-only` after applying.
4. Update the proposal status to `applied`.

### Safety

- `--dry-run`: print what would happen without writing.
- Fail if any referenced file does not exist.
- Create a git-friendly changeset (individual file moves, not bulk operations).

---

## 9. Utility commands

### `fm context --for-agent`

Print a compact context block for agent injection:

```
Feature Memory is enabled.
Docs root: docs/feature-memory
Features: 5 active, 1 draft
Changed files since HEAD: apps/web/src/auth/LoginForm.tsx
Likely affected features: auth
Stale features: billing (source hash mismatch, last verified 2026-04-01)
Required behavior: update docs only for affected features; propose reorgs.
  Stale pages: verify claims against source before trusting.
```

Implementation: read config, run a quick detect against HEAD, run staleness checks on affected features, summarize. The staleness section appears only when stale features are detected — it warns the agent which pages to distrust before reading them.

### `fm query QUERY [--limit N] [--json]`

Search feature docs by keyword. Implementation: grep through markdown files and index entries. Return matching feature IDs and relevant excerpts.

**Algorithm:**
1. Tokenize the query string into search terms.
2. Search feature titles, one-sentence summaries (from index), product summaries, and engineering summaries.
3. Score matches by: title match (weight 3), summary match (weight 2), body match (weight 1).
4. Return top N results (default 10) sorted by score.

**Output:**
```json
{
  "query": "authentication login",
  "results": [
    {
      "feature_id": "auth",
      "title": "Auth",
      "score": 5,
      "excerpt": "Handles user sign-in, sign-out, and session management.",
      "matches": ["title", "product_summary"]
    }
  ]
}
```

### `fm source-map [--feature ID] [--paths PATH...]`

Display or update the source map for a feature. With `--paths`, map new paths. Without, display the current map.

### `fm changelog --since DURATION`

Display changelog entries from the last N days/commits. Parse duration strings: `5d`, `1w`, `3m`, `10commits`.

### `fm recent --days N`

Regenerate `recent.md` from changelog entries.

### `fm export --format graph-json|csv [--output PATH] [--json]`

Export feature data for external tools.

**`graph-json` format:**
```json
{
  "nodes": [
    {"id": "auth", "title": "Auth", "status": "active", "confidence": "high", "source_path_count": 5}
  ],
  "edges": [
    {"from": "auth", "to": "session", "type": "parent", "confidence": "medium"}
  ]
}
```

**`csv` format:**
```
feature_id,title,status,confidence,review_status,source_paths,updated
auth,Auth,active,high,reviewed,5,2026-05-17
billing,Billing,active,medium,needs_review,3,2026-05-16
```

If `--output` is provided, write to file; otherwise print to stdout.

### `fm index rebuild`

Rebuild `state.sqlite` from the canonical markdown docs. Parse all feature pages, extract frontmatter, populate tables.

---

## Key deliverables

- [ ] `fm init` creates the full directory tree and default config
- [ ] `fm detect` classifies changed files with correct kinds and symbols
- [ ] `fm map` implements all 8 mapping steps with correct confidence
- [ ] `fm ingest --no-llm` updates timestamps, source maps, changelogs, index, recent
- [ ] `fm lint` implements all 15 deterministic checks
- [ ] `fm review` runs lint + optional LLM checks and produces structured reports
- [ ] `fm propose-reorg` generates valid proposal YAML without mutating docs
- [ ] `fm apply-proposal` executes proposals safely and runs lint after
- [ ] All utility commands produce correct output in both human and JSON modes
- [ ] All commands respect `--dry-run` where applicable
