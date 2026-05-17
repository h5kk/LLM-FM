# Spec 02 — Data Model

> Arch plan refs: sections 5 (canonical data model), 12 (storage and indexing)

## Objective

Define and implement every schema, markdown template, SQLite table, and JSON Schema file used by Feature Memory. After this spec, all data structures exist as code and as reference files.

## 1. Feature page template

### Single-file mode (`mode: small`)

Used when a feature fits in one markdown file.

```markdown
---
type: feature
schema_version: 1
feature_id: "{feature_id}"
slug: "{slug}"
title: "{title}"
status: draft
created: "{date}"
updated: "{date}"
last_code_touch: null
confidence: low
review_status: needs_review
owner: unknown
source_paths: []
source_hashes: {}
related_features:
  parents: []
  children: []
  siblings: []
shared_elements: []
tags: []
---

# {title}

## One-sentence summary

## Product / business summary

## Engineering summary

## Current behavior

## Source map

| Path | Kind | Role | Confidence | Last verified |
|------|------|------|------------|---------------|

## Relationships

### Parent / child features

### Similar or sibling features

### Reused elements

## Recent changes

## Known gaps / risks

## Open questions

## Historical notes
```

### Split-file mode (`mode: split`)

Used when a feature warrants separate files:

```
features/{feature_id}/
  index.md           # full frontmatter + one-sentence summary + links to sub-pages
  product.md         # product/business summary
  engineering.md     # engineering summary
  relationships.md   # relationships section
  source-map.md      # source map table
  changelog.md       # local append-only changelog
  review.md          # latest review notes
```

Each sub-page has minimal frontmatter:

```yaml
---
type: feature-section
parent_feature: "{feature_id}"
section: product
updated: "{date}"
---
```

### Mixed mode (`mode: mixed`)

Default. Small features use single-file. Features can be promoted to split-file when they grow. `fm lint` warns when a single-file feature exceeds a configurable line threshold (default: 200 lines).

## 2. Frontmatter schema

### Feature page fields

| Field | Type | Required | Default | Allowed values |
|-------|------|----------|---------|----------------|
| `type` | string | yes | — | `feature`, `feature-section` |
| `schema_version` | int | yes | 1 | positive integer |
| `feature_id` | string | yes | — | kebab-case slug |
| `slug` | string | yes | — | same as feature_id |
| `title` | string | yes | — | human-readable title |
| `status` | string | yes | `draft` | `active`, `draft`, `deprecated`, `removed`, `needs_review` |
| `created` | date | yes | — | ISO 8601 date |
| `updated` | date | yes | — | ISO 8601 date |
| `last_code_touch` | date/null | no | null | ISO 8601 date or null |
| `confidence` | string | no | `low` | `low`, `medium`, `high` |
| `review_status` | string | no | `needs_review` | `reviewed`, `needs_review`, `stale`, `blocked` |

### Confidence transitions

State machine for `confidence` and `review_status`:

```
CONFIDENCE:
  low → medium    : fm ingest --llm produces update
  low → high      : human verifies manually
  medium → high   : fm review passes with no findings, or human verifies
  high → medium   : source hash mismatch detected (code changed since last doc update)
  high → low      : source path deleted from disk
  medium → low    : source path deleted from disk

REVIEW_STATUS:
  needs_review → reviewed  : fm review passes with decision "pass"
  needs_review → stale     : 90+ days since last_code_touch on active feature
  reviewed → needs_review  : fm ingest runs (new changes arrived)
  reviewed → needs_review  : source hash mismatch detected
  stale → needs_review     : fm ingest runs or human updates
  blocked → needs_review   : blocking finding resolved

WHO SETS CONFIDENCE:
  - Mapping algorithm (per source_path): high (exact/glob match), medium (directory), low (symbol hint)
  - fm ingest --llm (per feature page): medium
  - fm review (per feature page): bumps to high on pass
  - Human (manual edit): any value
  - Staleness detection (automatic): downgrades only
```
| `owner` | string | no | `unknown` | any string |
| `source_paths` | list[string] | no | [] | file paths or globs |
| `source_hashes` | dict[string, string] | no | {} | path -> `sha256:...` |
| `related_features.parents` | list[string] | no | [] | feature_id references |
| `related_features.children` | list[string] | no | [] | feature_id references |
| `related_features.siblings` | list[string] | no | [] | feature_id references |
| `shared_elements` | list[string] | no | [] | file paths |
| `tags` | list[string] | no | [] | free-form tags |

### Pydantic model

`src/fm/models.py`:

```python
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

FeatureStatus = Literal["active", "draft", "deprecated", "removed", "needs_review"]
Confidence = Literal["low", "medium", "high"]
ReviewStatus = Literal["reviewed", "needs_review", "stale", "blocked"]
FileKind = Literal["ui-component", "api-route", "test", "config", "migration", "model", "util", "unknown"]
Severity = Literal["info", "low", "medium", "high", "blocking"]
ChangeKind = Literal[
    "behavior-change", "validation", "refactor", "new-feature", "bug-fix",
    "deprecation", "removal", "config-change", "test-change", "doc-change",
    "dependency-change",
]


class RelatedFeatures(BaseModel):
    parents: list[str] = []
    children: list[str] = []
    siblings: list[str] = []


class FeatureFrontmatter(BaseModel):
    type: Literal["feature", "feature-section"] = "feature"
    schema_version: int = 1
    feature_id: str
    slug: str
    title: str
    status: FeatureStatus = "draft"
    created: date
    updated: date
    last_code_touch: date | None = None
    confidence: Confidence = "low"
    review_status: ReviewStatus = "needs_review"
    owner: str = "unknown"
    source_paths: list[str] = []
    source_hashes: dict[str, str] = {}
    related_features: RelatedFeatures = RelatedFeatures()
    shared_elements: list[str] = []
    tags: list[str] = []
```

## 3. Index entry format

`docs/feature-memory/index.md`:

```markdown
---
type: index
schema_version: 1
updated: "{date}"
---

# Feature Memory Index

| Feature | Summary | Status | Review | Updated |
|---------|---------|--------|--------|---------|
| [{title}](features/{slug}.md) | {one_sentence} | {status} | {review_status} | {updated} |
```

## 4. Recent activity format

`docs/feature-memory/recent.md`:

```markdown
---
type: recent
schema_version: 1
generated: "{datetime}"
days: 5
---

# Recent Activity

## {date}

- **{feature_title}** — {summary_of_change}. Source: `{path}`.
```

## 5. Changelog event schema

### Markdown format (append-only)

`docs/feature-memory/changelog.md` and per-feature `changelog.md`:

```markdown
### {date} — {feature_title}: {summary}

- **Scope:** {feature_id}
- **Kind:** {kind_list}
- **Source:** {source_ref}
- **Paths:** {path_list}
- **Confidence:** {confidence}
- **Review:** {review_status}
```

### Pydantic model

```python
class ChangelogEvent(BaseModel):
    type: Literal["change_event"] = "change_event"
    schema_version: int = 1
    event_id: str
    created: datetime
    feature_id: str
    scope: str = "feature"
    source: str
    source_ref: str
    confidence: Confidence = "medium"
    review_status: ReviewStatus = "needs_review"
    paths: list[str] = []
    kind: list[ChangeKind] = []
    summary: str = ""
```

### Kind values

`behavior-change`, `validation`, `refactor`, `new-feature`, `bug-fix`, `deprecation`, `removal`, `config-change`, `test-change`, `doc-change`, `dependency-change`.

## 6. Review finding schema

```python
FindingCategory = Literal[
    "stale-claim", "missing-source", "broken-link", "unsupported-claim",
    "hierarchy-risk", "privacy-risk", "bad-mapping", "missing-doc",
]
FindingStatus = Literal["open", "resolved", "wontfix"]


class ReviewFinding(BaseModel):
    finding_id: str
    severity: Severity
    category: FindingCategory
    feature_id: str
    claim: str = ""
    evidence: list[str] = []
    recommendation: str = ""
    status: FindingStatus = "open"
```

## 7. Proposal schema

```python
ProposalAction = Literal[
    "move", "merge", "rename", "update-frontmatter",
    "add-relationship", "remove-relationship", "deprecate",
]
ProposalKind = Literal["merge-features", "split-feature", "rename-feature", "restructure"]
ProposalStatus = Literal["proposed", "approved", "applied", "rejected"]


class ProposalChange(BaseModel):
    action: ProposalAction
    from_path: str = ""
    to_path: str = ""
    details: dict[str, Any] = {}


class Proposal(BaseModel):
    proposal_id: str
    kind: ProposalKind
    status: ProposalStatus = "proposed"
    summary: str
    changes: list[ProposalChange]
    risks: list[str] = []
    validation: list[str] = []
```

## 8. SQLite DDL

`src/fm/schema.sql` (also used by `fm init` and `fm index rebuild`):

```sql
CREATE TABLE IF NOT EXISTS feature (
    feature_id TEXT PRIMARY KEY,
    slug TEXT NOT NULL,
    path TEXT NOT NULL,
    title TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft',
    updated_at TEXT,
    review_status TEXT DEFAULT 'needs_review',
    confidence TEXT DEFAULT 'low',
    one_sentence TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS source_path (
    path TEXT PRIMARY KEY,
    feature_id TEXT,
    kind TEXT,
    confidence TEXT DEFAULT 'medium',
    last_seen_at TEXT,
    source_hash TEXT,
    FOREIGN KEY (feature_id) REFERENCES feature(feature_id)
);

CREATE TABLE IF NOT EXISTS relationship (
    from_feature TEXT NOT NULL,
    to_feature TEXT NOT NULL,
    rel_type TEXT NOT NULL,
    confidence TEXT DEFAULT 'medium',
    source TEXT,
    needs_review INTEGER DEFAULT 1,
    PRIMARY KEY (from_feature, to_feature, rel_type),
    FOREIGN KEY (from_feature) REFERENCES feature(feature_id),
    FOREIGN KEY (to_feature) REFERENCES feature(feature_id)
);

CREATE TABLE IF NOT EXISTS event (
    event_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    event_type TEXT NOT NULL,
    feature_id TEXT,
    path TEXT,
    payload_json TEXT
);

CREATE TABLE IF NOT EXISTS finding (
    finding_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    severity TEXT NOT NULL,
    category TEXT NOT NULL,
    feature_id TEXT,
    status TEXT NOT NULL DEFAULT 'open',
    payload_json TEXT
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_source_path_feature ON source_path(feature_id);
CREATE INDEX IF NOT EXISTS idx_event_feature ON event(feature_id);
CREATE INDEX IF NOT EXISTS idx_event_created ON event(created_at);
CREATE INDEX IF NOT EXISTS idx_finding_feature ON finding(feature_id);
CREATE INDEX IF NOT EXISTS idx_finding_status ON finding(status);
CREATE INDEX IF NOT EXISTS idx_relationship_to ON relationship(to_feature);

-- Views
CREATE VIEW IF NOT EXISTS stale_features AS
SELECT f.feature_id, f.title, f.updated_at, f.review_status
FROM feature f
WHERE f.status = 'active'
  AND f.updated_at < date('now', '-30 days');

CREATE VIEW IF NOT EXISTS unmapped_paths AS
SELECT sp.path, sp.kind, sp.last_seen_at
FROM source_path sp
WHERE sp.feature_id IS NULL;

CREATE VIEW IF NOT EXISTS open_findings AS
SELECT * FROM finding WHERE status = 'open'
ORDER BY
  CASE severity
    WHEN 'blocking' THEN 0
    WHEN 'high' THEN 1
    WHEN 'medium' THEN 2
    WHEN 'low' THEN 3
    WHEN 'info' THEN 4
  END;
```

### SQLite operations module

`src/fm/db.py` wraps all database operations:

```python
class FmDatabase:
    def __init__(self, db_path: Path): ...
    def initialize(self) -> None: ...
    def rebuild_from_docs(self, docs_root: Path) -> None: ...
    def upsert_feature(self, feature: FeatureFrontmatter) -> None: ...
    def upsert_source_path(self, path: str, feature_id: str, kind: str, confidence: str) -> None: ...
    def add_event(self, event: ChangelogEvent) -> None: ...
    def add_finding(self, finding: ReviewFinding) -> None: ...
    def get_feature(self, feature_id: str) -> dict | None: ...
    def get_features_for_path(self, path: str) -> list[dict]: ...
    def get_stale_features(self, days: int = 30) -> list[dict]: ...
    def get_unmapped_paths(self) -> list[dict]: ...
    def get_open_findings(self) -> list[dict]: ...
```

### Concurrency and locking

SQLite may be accessed concurrently by hooks, CLI invocations, and CI. Use these settings:

```python
import sqlite3

def _connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path), timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn
```

- **WAL mode**: allows concurrent readers with a single writer.
- **busy_timeout**: writer retries for 5s before failing, preventing hook/CLI races.
- **Single writer assumption**: hooks append events; CLI does heavier writes. WAL handles this gracefully.
- **Rebuild operations** (`fm index rebuild`) acquire an exclusive lock and should not run concurrently with other writes. The CLI prints a warning if the lock cannot be acquired within the timeout.

## 9. Event log format

`.feature-memory/events.jsonl` — one JSON object per line:

```json
{"event_id": "2026-05-17T21-44-12Z-path-touched", "created_at": "2026-05-17T21:44:12Z", "event_type": "path_touched", "session_id": "s-20260517-214400-a1b2", "source": "claude-hook", "path": "apps/web/src/auth/LoginForm.tsx", "feature_id": "auth", "payload": {}}
```

### Session ID format

The `session_id` field groups events from a single agent session or CLI invocation:

- **Format**: `s-{YYYYMMDD}-{HHMMSS}-{4-char-hex}` — e.g., `s-20260517-214400-a1b2`.
- **Generation**: created at `session_start` event time. For hooks, the session ID is read from the hook input JSON (`hook_input.get("session_id", "")`) when the agent provides one. If not provided, the hook generates one from the current timestamp.
- **CLI invocations**: each `fm ingest`, `fm lint`, etc. call generates its own session ID.
- **Scope**: used by `fm detect --since-session` to find paths touched in the current session. Also useful for auditing which session produced which events.

Event types: `path_touched`, `feature_updated`, `feature_created`, `lint_run`, `review_run`, `proposal_created`, `proposal_applied`, `ingest_run`, `session_start`.

### Rotation policy

The events.jsonl file grows unboundedly during active development. Rotation rules:

- **Rotation trigger**: when the file exceeds 10 MB or 50,000 lines (checked at the start of `fm ingest`).
- **Rotation action**: rename current file to `events-{ISO-date}.jsonl` and create a fresh empty `events.jsonl`.
- **Retention**: keep the 3 most recent rotated files. Older files are deleted.
- **Manual rotation**: `fm index rebuild --rotate-events` forces rotation regardless of size.
- **Hooks**: hooks only append; they never rotate. Rotation is a CLI responsibility.

## 10. JSON Schema files

Store in `.feature-memory/schemas/` for external validation:

```
.feature-memory/schemas/
  feature-page.schema.json
  changelog-event.schema.json
  review-finding.schema.json
  proposal.schema.json
  config.schema.json
```

These are generated from the pydantic models:

```python
# src/fm/schemas.py
def export_schemas(output_dir: Path) -> None:
    schemas = {
        "feature-page": FeatureFrontmatter,
        "changelog-event": ChangelogEvent,
        "review-finding": ReviewFinding,
        "proposal": Proposal,
        "config": FmConfig,
    }
    for name, model in schemas.items():
        path = output_dir / f"{name}.schema.json"
        path.write_text(json.dumps(model.model_json_schema(), indent=2))
```

## 11. Template rendering

`src/fm/templates.py` provides functions to render markdown from models:

```python
def render_feature_page(frontmatter: FeatureFrontmatter) -> str: ...
def render_index_entry(feature: FeatureFrontmatter, one_sentence: str) -> str: ...
def render_changelog_entry(event: ChangelogEvent) -> str: ...
def render_recent_entry(event: ChangelogEvent) -> str: ...
def render_review_report(findings: list[ReviewFinding]) -> str: ...
```

Use string formatting, not a template engine. Keep it simple.

## Key deliverables

- [ ] All pydantic models defined in `src/fm/models.py` and validate correctly
- [ ] Feature page template renders valid markdown with correct frontmatter
- [ ] SQLite DDL creates all tables, indexes, and views
- [ ] `FmDatabase` class wraps all CRUD operations
- [ ] JSON Schemas export from pydantic models
- [ ] Template functions render correct markdown for all document types
- [ ] Event log format documented and write utility implemented
- [ ] Unit tests cover model validation (valid + invalid inputs)
