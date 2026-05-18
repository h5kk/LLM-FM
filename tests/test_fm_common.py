"""Tests for fm_common.py — load_config, match_path_to_features, get_feature_doc_path."""
import sys
import textwrap
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "plugin" / "hooks"))
from fm_common import load_config, match_path_to_features, get_feature_doc_path


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
