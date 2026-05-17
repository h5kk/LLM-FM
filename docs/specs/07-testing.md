# Spec 07 — Testing Strategy

> Arch plan refs: section 18 (evaluation plan)

## Objective

Define the complete testing approach: unit tests, fixture repos, golden tests, integration tests, hook tests, and evaluation metrics.

---

## 1. Test directory structure

```
tests/
  __init__.py
  conftest.py                          # shared fixtures: tmp project, fm config, db
  unit/
    __init__.py
    test_config.py                     # config discovery, loading, validation
    test_models.py                     # pydantic model validation (valid + invalid)
    test_detect.py                     # file classification, symbol extraction
    test_mapping.py                    # 8-step mapping algorithm
    test_lint.py                       # each FM00x check individually
    test_db.py                        # SQLite CRUD operations
    test_output.py                     # JSON envelope, human formatting
    test_templates.py                  # markdown template rendering
    test_events.py                     # event log writing/reading
  integration/
    __init__.py
    test_cli.py                        # CLI invocation, global options, exit codes
    test_init.py                       # fm init creates correct tree
    test_detect_integration.py         # fm detect against real git repos
    test_map_integration.py            # fm map against real configs
    test_ingest_integration.py         # fm ingest full pipeline
    test_lint_integration.py           # fm lint against fixture repos
    test_review_integration.py         # fm review full pipeline
    test_proposal_integration.py       # fm propose-reorg + apply-proposal
  hooks/
    __init__.py
    test_claude_hooks.py               # claude hook scripts with mocked stdin
    test_codex_hooks.py                # codex hook scripts with mocked stdin
  golden/
    README.md
    simple-auth/                       # expected outputs for fixture 1
      detect.json
      map.json
      lint.json
      feature-page.md
      changelog-entry.md
    route-rename/                      # expected outputs for fixture 2
      ...
  fixtures/
    README.md                          # how fixtures work
  eval/
    README.md
    eval_mapping.py                    # mapping precision/recall measurement
    eval_claims.py                     # claim verification measurement
```

---

## 2. Shared test fixtures (`conftest.py`)

```python
import pytest
from pathlib import Path
from fm.config import FmConfig
from fm.db import FmDatabase

@pytest.fixture
def tmp_project(tmp_path):
    """Create a minimal FM-initialized project directory."""
    docs = tmp_path / "docs" / "feature-memory"
    docs.mkdir(parents=True)
    fm_dir = tmp_path / ".feature-memory"
    fm_dir.mkdir()
    (fm_dir / "events.jsonl").touch()

    # Write default config
    config_path = fm_dir / "config.yaml"
    config_path.write_text("""
schema_version: 1
project_name: test-project
docs_root: docs/feature-memory
mode: mixed
features:
  auth:
    title: Auth
    globs:
      - src/auth/**
      - routes/auth.ts
mapping:
  default_confidence: medium
  unmapped_policy: report
  route_patterns:
    - routes/{feature}.ts
""")

    # Create docs structure
    (docs / "features").mkdir()
    (docs / "reports").mkdir()
    (docs / "index.md").write_text("---\ntype: index\n---\n# Index\n")
    (docs / "recent.md").write_text("---\ntype: recent\n---\n# Recent\n")
    (docs / "changelog.md").write_text("# Changelog\n")

    return tmp_path

@pytest.fixture
def fm_config(tmp_project):
    """Load FM config from the tmp project."""
    from fm.config import load_config
    return load_config(tmp_project / ".feature-memory" / "config.yaml")

@pytest.fixture
def fm_db(tmp_project):
    """Create and initialize an FM database."""
    db = FmDatabase(tmp_project / ".feature-memory" / "state.sqlite")
    db.initialize()
    return db

@pytest.fixture
def git_repo(tmp_project):
    """Initialize a git repo in the tmp project."""
    import subprocess
    subprocess.run(["git", "init"], cwd=tmp_project, check=True)
    subprocess.run(["git", "add", "."], cwd=tmp_project, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_project, check=True)
    return tmp_project
```

---

## 3. Unit test specifications

### `test_config.py`

| Test | Input | Expected |
|------|-------|----------|
| Load valid config | well-formed YAML | `FmConfig` with correct fields |
| Load config with defaults | YAML with only `project_name` | all defaults applied |
| Load config with unknown keys | YAML with extra keys | parsed without error (forward compat) |
| Invalid schema_version | `schema_version: "abc"` | `ValidationError` |
| Config discovery from subdirectory | cwd = `src/auth/` | finds `.feature-memory/config.yaml` two levels up |
| Config not found | no `.feature-memory/` in tree | `FileNotFoundError` |

### `test_models.py`

| Test | Input | Expected |
|------|-------|----------|
| Valid feature frontmatter | all required fields | model validates |
| Missing feature_id | omit feature_id | `ValidationError` |
| Invalid status | `status: "bogus"` | validation passes (string field, not enum in pydantic) |
| Valid changelog event | all fields | model validates |
| Valid review finding | all fields | model validates |
| Date serialization | `created: "2026-05-17"` | parses as `date` |

### `test_detect.py`

| Test | Input | Expected |
|------|-------|----------|
| Classify TypeScript component | `src/components/Button.tsx` | kind: `ui-component` |
| Classify API route | `routes/auth.ts` | kind: `api-route` |
| Classify test file | `tests/auth.test.ts` | kind: `test` |
| Classify config file | `config.yaml` | kind: `config` |
| Classify migration | `migrations/001_users.sql` | kind: `migration` |
| Extract TS symbols | `export function LoginForm()` | `["LoginForm"]` |
| Extract Python symbols | `class UserService:` | `["UserService"]` |
| User-facing heuristic | ui-component path | `likely_user_facing: true` |
| Non-user-facing heuristic | util path | `likely_user_facing: false` |

### `test_mapping.py`

| Test | Input | Expected |
|------|-------|----------|
| Step 1: exact source map match | path in DB | feature_id with high confidence |
| Step 2: config glob match | path matches glob | feature_id with high confidence |
| Step 3: route pattern match | `routes/billing.ts` | feature_id `billing` with high confidence |
| Step 4: directory name match | `src/auth/login.py` | feature_id `auth` with medium confidence |
| Step 6: symbol hint | `LoginForm` matches `auth` | feature_id `auth` with low confidence |
| Step 8: unmapped policy ignore | unmapped path, policy=ignore | no mapping |
| Step 8: unmapped policy report | unmapped path, policy=report | in `unmapped_paths` |
| Step 8: unmapped policy create_draft | unmapped path, policy=create_draft | draft feature created |
| Priority ordering | path matches step 2 and step 4 | step 2 wins (higher confidence) |
| Multiple features | path matches two features | both returned, sorted by confidence |

### `test_lint.py`

One test per lint check:

| Test | Check | Setup | Expected finding |
|------|-------|-------|------------------|
| FM001 | broken wikilink | `[[nonexistent]]` in feature page | FM001 finding |
| FM002 | no source paths | feature with empty `source_paths` | FM002 finding |
| FM003 | source path deleted | `source_paths: ["deleted.ts"]`, file doesn't exist | FM003 finding |
| FM004 | duplicate feature_id | two pages with same `feature_id` | FM004 finding |
| FM005 | no product summary | empty `## Product / business summary` | FM005 finding |
| FM006 | no engineering summary | empty `## Engineering summary` | FM006 finding |
| FM007 | no source map | empty source map table | FM007 finding |
| FM008 | broken relationship | `children: ["nonexistent"]` | FM008 finding |
| FM009 | hierarchy cycle | A parent of B, B parent of A | FM009 finding |
| FM010 | changelog missing date | entry without date | FM010 finding |
| FM011 | recent.md out of sync | recent.md doesn't reflect latest changes | FM011 finding |
| FM012 | index missing feature | feature page exists, not in index.md | FM012 finding |
| FM013 | stale active feature | `last_code_touch` 100 days ago | FM013 finding |
| FM014 | old open proposal | proposal file 30 days old | FM014 finding |
| FM015 | old low-confidence mapping | low confidence, 30 days old | FM015 finding |
| No false positive | well-formed feature page | no findings |

### `test_db.py`

| Test | Operation | Expected |
|------|-----------|----------|
| Initialize tables | `db.initialize()` | all tables exist |
| Upsert feature | insert + update | correct data |
| Get features for path | query | returns matching feature |
| Add and retrieve event | insert + query | correct event |
| Add and retrieve finding | insert + query | correct finding |
| Rebuild from docs | parse markdown, populate DB | DB matches docs |
| Stale features view | feature with old date | appears in view |
| Unmapped paths view | path with no feature_id | appears in view |

---

## 4. Fixture repos

Ten fixture repos for integration and golden tests. Each is created programmatically in test setup.

### Fixture 1: Simple auth feature

```
src/auth/login.py
src/auth/logout.py
tests/test_auth.py
docs/feature-memory/features/auth.md   # pre-populated
docs/feature-memory/index.md
```

Change: modify `login.py` to add email validation.
Expected: auth feature page updated, changelog entry, source map unchanged.

### Fixture 2: Route rename

```
routes/billing.ts -> routes/payments.ts
docs/feature-memory/features/billing.md
```

Change: rename `billing.ts` to `payments.ts`.
Expected: detect shows rename, source map flags old path as deleted, lint finds FM003.

### Fixture 3: Component moved between features

```
src/auth/UserAvatar.tsx -> src/profile/UserAvatar.tsx
docs/feature-memory/features/auth.md       # has UserAvatar in source map
docs/feature-memory/features/profile.md
```

Change: move component.
Expected: auth source map loses UserAvatar, profile gains it, both changelogs updated.

### Fixture 4: Behavior change in tests only

```
tests/test_billing.py                       # modified
src/billing/checkout.py                     # unchanged
docs/feature-memory/features/billing.md
```

Change: add a new test case.
Expected: detect classifies as test change, mapping maps to billing, changelog notes test-only change.

### Fixture 5: Deleted file

```
src/legacy/old_export.py                    # deleted
docs/feature-memory/features/legacy.md      # references old_export.py
```

Change: delete `old_export.py`.
Expected: lint finds FM003 (source path no longer exists).

### Fixture 6: Ambiguous shared component

```
src/shared/DataTable.tsx                    # used by billing and admin
docs/feature-memory/features/billing.md
docs/feature-memory/features/admin.md
```

Change: modify `DataTable.tsx`.
Expected: mapping returns both billing and admin with medium confidence. Both changelogs updated.

### Fixture 7: Stale docs claim

```
docs/feature-memory/features/auth.md        # claims OAuth is supported
src/auth/                                   # no OAuth code exists
```

Change: none (lint/review scenario).
Expected: review finds FM101 (unsupported claim) or lint finds FM003 if an OAuth path is listed.

### Fixture 8: Duplicate feature pages

```
docs/feature-memory/features/auth.md        # feature_id: auth
docs/feature-memory/features/authentication.md  # feature_id: auth (duplicate!)
```

Change: none (lint scenario).
Expected: lint finds FM004 (duplicate feature_id).

### Fixture 9: Privacy-sensitive context

```
src/auth/login.py                           # contains API key pattern
docs/feature-memory/features/auth.md
```

Change: modify login.py.
Expected: privacy redaction patterns catch API key references, review flags FM107.

### Fixture 10: Multi-app feature

```
apps/web/src/billing/Checkout.tsx
apps/api/src/routes/billing.ts
packages/shared/billing-types.ts
docs/feature-memory/features/billing.md
```

Change: modify all three files.
Expected: all three mapped to billing with high confidence, source map includes all three apps.

---

## 5. Golden tests

For each fixture, store expected outputs in `tests/golden/{fixture_name}/`:

```python
# tests/integration/test_golden.py
from syrupy.assertion import SnapshotAssertion

def test_simple_auth_detect(git_repo_simple_auth, snapshot: SnapshotAssertion):
    result = run_fm(["detect", "--diff", "HEAD~1..HEAD", "--json"], cwd=git_repo_simple_auth)
    assert result == snapshot

def test_simple_auth_map(git_repo_simple_auth, snapshot: SnapshotAssertion):
    result = run_fm(["map", "--paths", "src/auth/login.py", "--json"], cwd=git_repo_simple_auth)
    assert result == snapshot
```

Golden test assertions:
- Expected feature mapping (which paths map to which features)
- Expected changed docs (which feature pages were updated)
- Expected changelog entries (correct date, kind, paths)
- No unexpected reorganization (no moves/renames/merges)
- No hallucinated source paths (every source_path in output exists on disk)
- No private data leakage (no redact-pattern matches in output)
- Lint passes or expected lint findings occur

---

## 6. Integration tests

### CLI invocation tests

```python
# tests/integration/test_cli.py
from click.testing import CliRunner
from fm.cli import main

def test_version():
    runner = CliRunner()
    result = runner.invoke(main, ["--version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.output

def test_help():
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "detect" in result.output

def test_init(tmp_path):
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(main, ["init"])
        assert result.exit_code == 0
        assert (Path.cwd() / "docs" / "feature-memory" / "index.md").exists()
        assert (Path.cwd() / ".feature-memory" / "config.yaml").exists()
```

### Full pipeline tests

```python
def test_ingest_pipeline(git_repo_simple_auth):
    """Test detect -> map -> ingest -> lint pipeline."""
    # 1. Make a change
    (git_repo_simple_auth / "src" / "auth" / "login.py").write_text("# changed")
    subprocess.run(["git", "add", "."], cwd=git_repo_simple_auth)
    subprocess.run(["git", "commit", "-m", "change auth"], cwd=git_repo_simple_auth)

    # 2. Run ingest
    result = run_fm(["ingest", "--diff", "HEAD~1..HEAD", "--no-llm", "--json"],
                    cwd=git_repo_simple_auth)
    assert result["status"] == "ok"
    assert "auth" in result["data"]["features_updated"]

    # 3. Verify docs were updated
    feature_page = (git_repo_simple_auth / "docs" / "feature-memory" / "features" / "auth.md")
    content = feature_page.read_text()
    assert "login.py" in content  # source map updated

    # 4. Run lint
    lint_result = run_fm(["lint", "--json"], cwd=git_repo_simple_auth)
    assert lint_result["status"] == "ok"
```

---

## 7. Hook tests

```python
# tests/hooks/test_claude_hooks.py
import json
import subprocess

def test_post_tool_records_event(tmp_project):
    """PostToolUse hook logs path_touched event."""
    hook_input = json.dumps({
        "tool_name": "Edit",
        "tool_input": {"file_path": "src/auth/login.py"},
        "session_id": "test-session-1"
    })

    result = subprocess.run(
        ["python", ".feature-memory/hooks/claude_post_tool.py"],
        input=hook_input, capture_output=True, text=True, cwd=tmp_project
    )

    events = (tmp_project / ".feature-memory" / "events.jsonl").read_text()
    assert "path_touched" in events
    assert "src/auth/login.py" in events
```

---

## 8. Evaluation metrics

### Mapping precision and recall

```python
# tests/eval/eval_mapping.py

def evaluate_mapping(fixture_path, expected_mappings):
    """Run fm map and compare against expected mappings."""
    actual = run_fm(["map", "--paths"] + paths, cwd=fixture_path)
    
    true_positives = len(set(actual) & set(expected))
    false_positives = len(set(actual) - set(expected))
    false_negatives = len(set(expected) - set(actual))
    
    precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0
    recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0
    
    return {"precision": precision, "recall": recall}
```

### Target metrics

| Metric | Target | Notes |
|--------|--------|-------|
| Mapping precision | >90% | false positives waste review time |
| Mapping recall | >85% | false negatives miss doc updates |
| Unsupported claim rate | <10% | claims without source support |
| Stale claim detection rate | >80% | old claims caught by review |
| Docs update minimality | >90% | updates touch only affected features |
| Broken link rate | 0% | lint should catch all |
| False blocking rate | <5% | false positives at blocking severity |

---

## 9. pytest configuration

In `pyproject.toml` (already in spec 00):

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-ra -q --tb=short"
markers = [
    "slow: marks tests as slow (deselect with '-m \"not slow\"')",
    "golden: golden/snapshot tests",
    "eval: evaluation metrics tests",
]
```

Run commands:

```bash
pytest                           # all tests
pytest tests/unit/               # unit only
pytest tests/integration/        # integration only
pytest -m golden                 # golden tests only
pytest -m "not slow"             # skip slow tests
pytest --snapshot-update         # update golden snapshots
```

---

## Key deliverables

- [ ] `conftest.py` with `tmp_project`, `fm_config`, `fm_db`, `git_repo` fixtures
- [ ] Unit tests for all modules (config, models, detect, mapping, lint, db, output, templates)
- [ ] 10 fixture repo definitions implemented as pytest fixtures
- [ ] Golden test snapshots for all fixtures
- [ ] Integration tests for CLI invocation and full pipeline
- [ ] Hook tests with mocked stdin
- [ ] Evaluation metric scripts
- [ ] pytest markers and run configurations
- [ ] All tests pass on CI (GitHub Actions)
