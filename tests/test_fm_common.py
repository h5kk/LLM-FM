"""Tests for fm_common.py — load_config, match_path_to_features, get_feature_doc_path, new helpers."""
import sys
import textwrap
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "plugin" / "hooks"))
from fm_common import (
    load_config, match_path_to_features, get_feature_doc_path, _infer_tags,
    _infer_audience, _infer_kind, _keyword_tags_for_entry, rotate_events_if_oversized,
    get_feature_globs,
)


# ---------------------------------------------------------------------------
# load_config
# ---------------------------------------------------------------------------

def _write_config(tmp_path, content):
    cfg = tmp_path / ".feature-memory" / "config.yaml"
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text(textwrap.dedent(content), encoding="utf-8")
    return tmp_path


def test_load_config_basic(tmp_path):
    _write_config(tmp_path, """
        features:
          auth:
            globs:
              - "src/auth/**"
              - "routes/auth.py"
    """)
    features = load_config(tmp_path)
    assert "auth" in features
    globs = features["auth"]["globs"]
    assert "src/auth/**" in globs
    assert "routes/auth.py" in globs


def test_load_config_quoted_globs(tmp_path):
    """Quoted glob values must be stored without surrounding quotes."""
    _write_config(tmp_path, """
        features:
          hooks:
            globs:
              - "plugin/hooks/**"
    """)
    features = load_config(tmp_path)
    assert features["hooks"]["globs"] == ["plugin/hooks/**"]


def test_load_config_single_quoted_globs(tmp_path):
    _write_config(tmp_path, """
        features:
          hooks:
            globs:
              - 'plugin/hooks/**'
    """)
    features = load_config(tmp_path)
    assert features["hooks"]["globs"] == ["plugin/hooks/**"]


def test_load_config_multiple_features(tmp_path):
    _write_config(tmp_path, """
        features:
          auth:
            globs:
              - "src/auth/**"
          billing:
            globs:
              - "src/billing/**"
              - "routes/billing.py"
    """)
    features = load_config(tmp_path)
    assert set(features.keys()) == {"auth", "billing"}
    assert len(features["billing"]["globs"]) == 2


def test_load_config_missing_file(tmp_path):
    assert load_config(tmp_path) == {}


def test_load_config_ignores_metadata_keys(tmp_path):
    """Keys like title:, owner:, status: inside a feature block don't pollute globs."""
    _write_config(tmp_path, """
        features:
          auth:
            title: Auth
            owner: platform
            globs:
              - "src/auth/**"
    """)
    features = load_config(tmp_path)
    assert features["auth"]["globs"] == ["src/auth/**"]


# ---------------------------------------------------------------------------
# load_config rich format (P2.2)
# ---------------------------------------------------------------------------

def test_load_config_rich_returns_title(tmp_path):
    """load_config should return title from config if present."""
    _write_config(tmp_path, """
        features:
          auth:
            title: "Authentication System"
            globs:
              - "src/auth/**"
    """)
    features = load_config(tmp_path)
    assert features["auth"]["title"] == "Authentication System"


def test_load_config_rich_falls_back_to_title_case(tmp_path):
    """load_config should title-case the feature_id when title is absent (hyphens become spaces)."""
    _write_config(tmp_path, """
        features:
          session-hooks:
            globs:
              - "plugin/hooks/**"
    """)
    features = load_config(tmp_path)
    # hyphens become spaces before title-casing: "session-hooks" -> "Session Hooks"
    assert features["session-hooks"]["title"] == "Session Hooks"


def test_load_config_rich_mode_field(tmp_path):
    """load_config should parse per-feature mode key."""
    _write_config(tmp_path, """
        features:
          auth:
            mode: split
            globs:
              - "src/auth/**"
    """)
    features = load_config(tmp_path)
    assert features["auth"]["mode"] == "split"


def test_load_config_rich_mode_none_when_absent(tmp_path):
    """load_config mode field should be None when not set."""
    _write_config(tmp_path, """
        features:
          auth:
            globs:
              - "src/auth/**"
    """)
    features = load_config(tmp_path)
    assert features["auth"]["mode"] is None


def test_get_feature_globs_extracts_flat(tmp_path):
    """get_feature_globs should extract {id: [globs]} from rich format."""
    _write_config(tmp_path, """
        features:
          auth:
            title: Auth
            globs:
              - "src/auth/**"
    """)
    features = load_config(tmp_path)
    flat = get_feature_globs(features)
    assert flat == {"auth": ["src/auth/**"]}


# ---------------------------------------------------------------------------
# match_path_to_features
# ---------------------------------------------------------------------------

FEATURES = {
    "auth":    ["src/auth/**", "routes/auth.py", "tests/test_auth.py"],
    "billing": ["src/billing/**", "routes/billing.py"],
    "infra":   ["app.py", "config.py", "README.md"],
}


@pytest.mark.parametrize("path,expected", [
    ("src/auth/login.py",        ["auth"]),
    ("src/auth/sub/deep.py",     ["auth"]),
    ("routes/auth.py",           ["auth"]),
    ("tests/test_auth.py",       ["auth"]),
    ("src/billing/invoice.py",   ["billing"]),
    ("routes/billing.py",        ["billing"]),
    ("app.py",                   ["infra"]),
    ("README.md",                ["infra"]),
    ("src/unrelated/foo.py",     []),
    ("routes/unknown.py",        []),
])
def test_match_path_to_features(path, expected):
    assert match_path_to_features(path, FEATURES) == expected


def test_match_path_windows_separators():
    """Backslashes are normalised to forward slashes before matching."""
    result = match_path_to_features(r"src\auth\login.py", FEATURES)
    assert result == ["auth"]


def test_match_path_no_features():
    assert match_path_to_features("anything.py", {}) == []


def test_match_path_no_double_match():
    """A path that matches two features returns both, sorted."""
    features = {"a": ["shared/**"], "b": ["shared/**"]}
    result = match_path_to_features("shared/foo.py", features)
    assert sorted(result) == ["a", "b"]


# ---------------------------------------------------------------------------
# get_feature_doc_path
# ---------------------------------------------------------------------------

def test_get_feature_doc_path_flat(tmp_path):
    docs_root = tmp_path / "docs" / "feature-memory"
    # No split-mode directory exists → flat path
    path = get_feature_doc_path("auth", docs_root)
    assert path == docs_root / "features" / "auth.md"


def test_get_feature_doc_path_split(tmp_path):
    docs_root = tmp_path / "docs" / "feature-memory"
    split = docs_root / "features" / "auth" / "index.md"
    split.parent.mkdir(parents=True)
    split.touch()
    path = get_feature_doc_path("auth", docs_root)
    assert path == split


def test_get_feature_doc_path_prefers_split_over_flat(tmp_path):
    docs_root = tmp_path / "docs" / "feature-memory"
    split = docs_root / "features" / "auth" / "index.md"
    split.parent.mkdir(parents=True)
    split.touch()
    # Even if flat file exists, split wins
    flat = docs_root / "features" / "auth.md"
    flat.parent.mkdir(parents=True, exist_ok=True)
    flat.touch()
    assert get_feature_doc_path("auth", docs_root) == split


# ---------------------------------------------------------------------------
# _infer_tags
# ---------------------------------------------------------------------------

def test_infer_tags_empty():
    assert _infer_tags([], "", []) == []


def test_infer_tags_none_inputs():
    assert _infer_tags(None, None, None) == []


def test_infer_tags_breaking_change_keyword():
    assert "breaking-change" in _infer_tags([], "BREAKING: remove old endpoint", [])


def test_infer_tags_breaking_not_triggered_by_remove_api_key():
    """'remove API key' must NOT trigger breaking-change (council-required fix)."""
    assert "breaking-change" not in _infer_tags([], "remove API key from logs", [])


def test_infer_tags_deprecated_triggers_breaking():
    assert "breaking-change" in _infer_tags([], "deprecated: use new auth API instead", [])


def test_infer_tags_auth_from_login():
    assert "auth" in _infer_tags([], "fix login redirect after session expiry", [])


def test_infer_tags_login_does_not_trigger_logging():
    """'login' must not match the logging heuristic."""
    assert "logging" not in _infer_tags([], "fix login redirect", [])


def test_infer_tags_no_language_tags_for_ts():
    """Language/tech tags (typescript, javascript, python) are NOT generated by _infer_tags."""
    tags = _infer_tags(["src/app.tsx", "src/utils.ts"], "", [])
    assert "typescript" not in tags
    assert "javascript" not in tags


def test_infer_tags_no_language_tags_for_jsx():
    tags = _infer_tags(["src/component.jsx"], "", [])
    assert "javascript" not in tags


def test_infer_tags_no_python_tag():
    """Python extension does not generate a 'python' tag (use topic tags for that)."""
    assert "python" not in _infer_tags(["plugin/hooks/fm_common.py"], "", [])


def test_infer_tags_process_tests_directory():
    assert "tests" in _infer_tags(["tests/test_auth.py"], "", [])


def test_infer_tags_process_tests_suffix():
    assert "tests" in _infer_tags(["src/auth_test.go"], "", [])


def test_infer_tags_process_docs_path():
    assert "docs" in _infer_tags(["docs/feature-memory/hooks.md"], "", [])


def test_infer_tags_process_dependency():
    assert "dependency" in _infer_tags(["requirements.txt"], "", [])


def test_infer_tags_process_ci_cd():
    assert "ci-cd" in _infer_tags([".github/workflows/ci.yml"], "", [])


def test_infer_tags_config_change_from_path():
    assert "config-change" in _infer_tags([".feature-memory/config.yaml"], "", [])


def test_infer_tags_windows_backslash_paths():
    assert "tests" in _infer_tags([r"tests\test_auth.py"], "", [])


def test_infer_tags_priority_process_at_cap():
    """With >5 inferences, Process tags should be present within the cap."""
    paths = ["tests/test_auth.py", ".github/workflows/ci.yml", "auth.py"]
    msg = "BREAKING: fix security vulnerability with better error handling"
    tags = _infer_tags(paths, msg, [])
    assert len(tags) <= 5
    # Impact + Quality should fill first slots; Process gets remaining slots
    assert "tests" in tags or "ci-cd" in tags


def test_infer_tags_cap_never_exceeds_5():
    paths = ["src/auth.ts", "styles.css", "query.sql", "deploy.sh", "config.yaml"]
    msg = "BREAKING: fix security oauth login cache schema migration data backfill"
    assert len(_infer_tags(paths, msg, [])) <= 5


@pytest.mark.parametrize("msg,expected_tag", [
    ("optimize database queries for speed", "performance"),
    ("fix security vulnerability in auth module", "security"),
    ("add logging for request tracing and observability", "logging"),
    ("improve error handling in pipeline fallback", "error-handling"),
    ("update schema migration for v2 database", "schema-change"),
    ("improve accessibility with ARIA labels", "accessibility"),
    ("redesign UI layout and theme colors", "ux"),
])
def test_infer_tags_quality_and_impact_parametrized(msg, expected_tag):
    assert expected_tag in _infer_tags([], msg, [])


# ---------------------------------------------------------------------------
# _infer_audience (P2.7)
# ---------------------------------------------------------------------------

def test_infer_audience_developer_for_test_paths():
    """Pure test paths -> developer."""
    result = _infer_audience(["tests/test_auth.py"], "fix login bug", [])
    assert result == "developer"


def test_infer_audience_developer_for_config_paths():
    """Pure config paths -> developer."""
    result = _infer_audience(["config.yaml", "settings.json"], "update config", [])
    assert result == "developer"


def test_infer_audience_product_for_html_paths():
    """Pure HTML paths -> product."""
    result = _infer_audience(["src/index.html", "src/styles.css"], "update homepage layout", [])
    assert result == "product"


def test_infer_audience_both_for_mixed_paths():
    """Mixed test + source -> both."""
    result = _infer_audience(["tests/test_auth.py", "src/auth.py"], "refactor auth", [])
    assert result == "both"


def test_infer_audience_both_for_empty_paths():
    """No paths -> both (conservative)."""
    result = _infer_audience([], "some change", [])
    assert result == "both"


def test_infer_audience_both_for_breaking_message():
    """Breaking change keyword overrides path classification."""
    result = _infer_audience(["tests/test_auth.py"], "breaking: remove old auth endpoint", [])
    assert result == "both"


def test_infer_audience_both_for_api_message():
    """API keyword in message -> both."""
    result = _infer_audience(["tests/test_auth.py"], "change api endpoint signature", [])
    assert result == "both"


# ---------------------------------------------------------------------------
# _infer_kind (shared between stop hook and backfill)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("msg,expected", [
    ("fix login bug", ["bug-fix"]),
    ("hotfix: patch security hole", ["bug-fix"]),
    ("add new feature for users", ["new-feature"]),
    ("feat: implement oauth login", ["new-feature"]),
    ("refactor auth module", ["refactor"]),
    ("cleanup dead code", ["refactor"]),
    ("update docs", ["behavior-change"]),
])
def test_infer_kind_parametrized(msg, expected):
    assert _infer_kind([], msg) == expected


# ---------------------------------------------------------------------------
# _keyword_tags_for_entry (P2.5)
# ---------------------------------------------------------------------------

def test_keyword_tags_for_entry_basic():
    """Should derive tags from non-generic directory components."""
    entry = {"paths": ["src/auth/login.py"]}
    tags = _keyword_tags_for_entry(entry)
    assert len(tags) >= 1
    assert "auth" in tags


def test_keyword_tags_for_entry_no_paths():
    """Empty paths -> empty tags."""
    assert _keyword_tags_for_entry({}) == []
    assert _keyword_tags_for_entry({"paths": []}) == []


def test_keyword_tags_for_entry_max_two():
    """Should return at most 2 tags."""
    entry = {"paths": ["src/auth/login.py", "src/billing/invoice.py", "src/ui/button.py"]}
    tags = _keyword_tags_for_entry(entry)
    assert len(tags) <= 2


def test_keyword_tags_for_entry_kebab_case():
    """Tags should be valid kebab-case."""
    entry = {"paths": ["src/MyFeature/SomeFile.py"]}
    tags = _keyword_tags_for_entry(entry)
    for tag in tags:
        assert tag == tag.lower()


# ---------------------------------------------------------------------------
# rotate_events_if_oversized (P1.5)
# ---------------------------------------------------------------------------

def test_rotate_events_below_threshold(tmp_path):
    """Small file should not be rotated."""
    events_path = tmp_path / "events.jsonl"
    events_path.write_text("small content\n", encoding="utf-8")
    rotate_events_if_oversized(events_path, max_mb=5)
    assert events_path.exists()
    assert events_path.read_text() == "small content\n"


def test_rotate_events_above_threshold(tmp_path):
    """File above threshold should be rotated to overflow."""
    events_path = tmp_path / "events.jsonl"
    # Write just over 0.001 MB (1 KB) and test with very small threshold
    events_path.write_bytes(b"x" * 1100)
    rotate_events_if_oversized(events_path, max_mb=0.001)
    assert not events_path.exists()
    overflows = list(tmp_path.glob("events-overflow-*.jsonl"))
    assert len(overflows) == 1


def test_rotate_events_nonexistent(tmp_path):
    """Should silently no-op when file doesn't exist."""
    events_path = tmp_path / "events.jsonl"
    rotate_events_if_oversized(events_path, max_mb=5)  # Should not raise
