"""Tests for fm_common.py — load_config, match_path_to_features, get_feature_doc_path."""
import sys
import textwrap
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "plugin" / "hooks"))
from fm_common import load_config, match_path_to_features, get_feature_doc_path, _infer_tags


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
    assert "src/auth/**" in features["auth"]
    assert "routes/auth.py" in features["auth"]


def test_load_config_quoted_globs(tmp_path):
    """Quoted glob values must be stored without surrounding quotes."""
    _write_config(tmp_path, """
        features:
          hooks:
            globs:
              - "plugin/hooks/**"
    """)
    features = load_config(tmp_path)
    assert features["hooks"] == ["plugin/hooks/**"]


def test_load_config_single_quoted_globs(tmp_path):
    _write_config(tmp_path, """
        features:
          hooks:
            globs:
              - 'plugin/hooks/**'
    """)
    features = load_config(tmp_path)
    assert features["hooks"] == ["plugin/hooks/**"]


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
    assert len(features["billing"]) == 2


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
    assert features["auth"] == ["src/auth/**"]


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


def test_infer_tags_typescript_distinct_tag():
    tags = _infer_tags(["src/app.tsx", "src/utils.ts"], "", [])
    assert "typescript" in tags
    assert "javascript" not in tags


def test_infer_tags_javascript_not_matched_for_ts_files():
    tags = _infer_tags(["src/app.ts"], "", [])
    assert "typescript" in tags
    assert "javascript" not in tags


def test_infer_tags_javascript_for_jsx():
    tags = _infer_tags(["src/component.jsx"], "", [])
    assert "javascript" in tags
    assert "typescript" not in tags


def test_infer_tags_python_extension():
    assert "python" in _infer_tags(["plugin/hooks/fm_common.py"], "", [])


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


def test_infer_tags_priority_process_beats_tech_at_cap():
    """With >5 inferences, Process tags must survive over Tech tags."""
    paths = ["tests/test_auth.py", ".github/workflows/ci.yml", "auth.py"]
    msg = "BREAKING: fix security vulnerability with better error handling"
    tags = _infer_tags(paths, msg, [])
    assert len(tags) <= 5
    # Impact + Quality should fill first 4 slots; Process gets slot 5; Tech drops
    assert "tests" in tags or "ci-cd" in tags
    assert "python" not in tags  # Tech displaced


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
