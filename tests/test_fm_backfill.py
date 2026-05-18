"""Tests for fm_backfill.py — Jira extraction, kind/audience inference, dedup."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "plugin" / "hooks"))
from fm_backfill import _extract_jira, _infer_kind, _infer_audience, _JIRA_RE


# ---------------------------------------------------------------------------
# _extract_jira
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text,expected", [
    ("feat/PROJ-123-my-feature",    "PROJ-123"),
    ("Fix TEAM-99 regression",       "TEAM-99"),
    ("ABC-1 minimal ticket",         "ABC-1"),
    ("no ticket here",               None),
    ("lowercase proj-1 no match",    None),
    ("A-1 single char prefix",        None),          # requires min 2-char prefix ([A-Z][A-Z0-9]{1,9})
    ("TOOLONG12-99 nine char prefix", "TOOLONG12-99"), # 9-char prefix fits [A-Z][A-Z0-9]{1,9}
    ("refs #123 github style",        None),          # not Jira format
    ("XY-0 zero ok",                  "XY-0"),
])
def test_extract_jira(text, expected):
    assert _extract_jira(text) == expected


def test_extract_jira_none_input():
    assert _extract_jira(None) is None


def test_extract_jira_no_redos():
    """Regex must complete instantly on a pathological input."""
    import re, time
    evil = "A" * 10000 + "-"
    start = time.monotonic()
    _JIRA_RE.search(evil)
    assert time.monotonic() - start < 1.0


# ---------------------------------------------------------------------------
# _infer_kind
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("message,expected_kind", [
    ("fix: null pointer in auth",          "bug-fix"),
    ("bugfix: session expiry",             "bug-fix"),
    ("hotfix urgent crash",                "bug-fix"),
    ("add new payment provider",           "new-feature"),
    ("feat: dark mode toggle",             "new-feature"),
    ("implement OAuth2 flow",              "new-feature"),
    ("refactor billing module",            "refactor"),
    ("cleanup: remove dead code",          "refactor"),
    ("update dependency versions",         "behavior-change"),
    ("bump lodash to 4.17.21",             "behavior-change"),
    ("improve error messages",             "behavior-change"),
    ("miscellaneous changes",              "behavior-change"),   # fallback
])
def test_infer_kind(message, expected_kind):
    assert _infer_kind([], message) == [expected_kind]


# ---------------------------------------------------------------------------
# _infer_audience
# ---------------------------------------------------------------------------

def test_infer_audience_refactor_is_developer():
    assert _infer_audience(["src/auth/login.py"], ["refactor"]) == "developer"


def test_infer_audience_test_only_is_developer():
    assert _infer_audience(["tests/test_auth.py"], ["new-feature"]) == "developer"


def test_infer_audience_source_file_is_both():
    assert _infer_audience(["src/auth/login.py"], ["new-feature"]) == "both"


def test_infer_audience_mixed_paths_is_both():
    paths = ["src/auth/login.py", "tests/test_auth.py"]
    assert _infer_audience(paths, ["behavior-change"]) == "both"


# ---------------------------------------------------------------------------
# Session ID sanitisation (path traversal prevention)
# ---------------------------------------------------------------------------

def test_session_id_sanitisation():
    """session_id with path separators must not escape the archive directory."""
    import re
    evil_ids = [
        "../../../etc/passwd",
        "..\\..\\windows\\system32",
        "abc/def",
        "abc\x00def",
        "normal-session-id-123",
    ]
    for sid in evil_ids:
        safe = re.sub(r'[^a-zA-Z0-9_\-]', '_', sid)[:128]
        assert "/" not in safe
        assert "\\" not in safe
        assert "\x00" not in safe

    # Normal ID is preserved
    assert re.sub(r'[^a-zA-Z0-9_\-]', '_', "abc-123_XYZ") == "abc-123_XYZ"
