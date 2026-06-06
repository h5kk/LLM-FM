"""Tests for ensure_artifact_gitignores — the self-contained .gitignore drop-ins
that keep Feature Memory's generated artifacts and runtime state out of git
(preventing clean-tree-hook trips and cross-branch merge conflicts).
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "plugin" / "hooks"))
from fm_common import ensure_artifact_gitignores


def _make_project(tmp_path, with_docs=True):
    (tmp_path / ".feature-memory").mkdir()
    if with_docs:
        (tmp_path / "docs" / "feature-memory" / "changelogs").mkdir(parents=True)
    return tmp_path


def test_creates_both_gitignores(tmp_path):
    _make_project(tmp_path)
    created = ensure_artifact_gitignores(tmp_path)

    assert ".feature-memory/.gitignore" in created
    assert "docs/feature-memory/.gitignore" in created
    assert (tmp_path / ".feature-memory" / ".gitignore").exists()
    assert (tmp_path / "docs" / "feature-memory" / ".gitignore").exists()


def test_runtime_patterns_present(tmp_path):
    _make_project(tmp_path)
    ensure_artifact_gitignores(tmp_path)
    content = (tmp_path / ".feature-memory" / ".gitignore").read_text(encoding="utf-8")

    # The exact artifacts that were tripping the clean-tree hook.
    for pat in ("events.jsonl", "events-*.jsonl", "errors.log", "state.sqlite", "reports/"):
        assert pat in content


def test_does_not_blanket_ignore_hooks(tmp_path):
    """Regression guard: fm_init copies hook scripts into .feature-memory/hooks/.
    A blanket '*' would silently ignore them, so the pattern list must be explicit.
    """
    _make_project(tmp_path)
    ensure_artifact_gitignores(tmp_path)
    content = (tmp_path / ".feature-memory" / ".gitignore").read_text(encoding="utf-8")

    assert content.strip().splitlines().count("*") == 0
    assert "hooks/" not in content


def test_docs_patterns_present(tmp_path):
    _make_project(tmp_path)
    ensure_artifact_gitignores(tmp_path)
    content = (tmp_path / "docs" / "feature-memory" / ".gitignore").read_text(encoding="utf-8")

    assert "changelog-viewer.html" in content
    assert "changelogs/changelog.json" in content


def test_idempotent_and_non_clobbering(tmp_path):
    _make_project(tmp_path)
    ensure_artifact_gitignores(tmp_path)

    # User customizes the drop-in; a second run must not overwrite it.
    custom = tmp_path / ".feature-memory" / ".gitignore"
    custom.write_text("# my custom rules\n*.tmp\n", encoding="utf-8")

    created = ensure_artifact_gitignores(tmp_path)
    assert created == []  # nothing (re)created
    assert custom.read_text(encoding="utf-8") == "# my custom rules\n*.tmp\n"


def test_skips_missing_parent_dirs(tmp_path):
    """Only .feature-memory/ exists — the docs drop-in must not be created
    (and no docs/ tree fabricated)."""
    _make_project(tmp_path, with_docs=False)
    created = ensure_artifact_gitignores(tmp_path)

    assert created == [".feature-memory/.gitignore"]
    assert not (tmp_path / "docs").exists()


def test_never_raises_on_bad_input(tmp_path):
    # A non-existent project dir must be swallowed, not raised.
    assert ensure_artifact_gitignores(tmp_path / "does-not-exist") == []
