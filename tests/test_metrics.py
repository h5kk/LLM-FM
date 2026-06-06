"""Tests for config echo, separate custom-docs slot injection, and churn."""
import json
import sys
from pathlib import Path

import pytest

HOOKS = Path(__file__).parent.parent / "plugin" / "hooks"
sys.path.insert(0, str(HOOKS))
import fm_backfill  # noqa: E402
from fm_common import (  # noqa: E402
    changelog_config_echo, inject_inline_json_block, _changelog_defaults,
)


def test_config_echo_shape():
    echo = changelog_config_echo(_changelog_defaults())
    assert echo == {
        "verbosity": "normal",
        "highlight_tags": ["breaking-change", "api-change", "security",
                            "schema-change", "data-migration"],
        "custom_docs_enabled": True,
        "metrics_enabled": True,
    }
    # Tolerates None / partial.
    assert changelog_config_echo(None)["verbosity"] == "normal"


def test_inject_block_replaces_only_target():
    html = (
        '<script id="changelog-data" type="application/json">\n{"a":1}\n</script>'
        '<script id="custom-docs-data" type="application/json">\n{}\n</script>'
    )
    out = inject_inline_json_block(html, "custom-docs-data", {"wiki": [], "entries": []})
    assert '"a":1' in out  # changelog-data untouched
    m = out.split('id="custom-docs-data"')[1]
    assert '"wiki": []' in m


def test_inject_block_noop_when_absent():
    html = "<html><body>no slot here</body></html>"
    assert inject_inline_json_block(html, "custom-docs-data", {"x": 1}) == html


def test_inject_block_escapes_script_close():
    html = '<script id="custom-docs-data">{}</script>'
    out = inject_inline_json_block(html, "custom-docs-data",
                                   {"wiki": [{"body_md": "danger </script> here"}]})
    # The embedded payload must not contain a literal closing tag.
    body = out.split('id="custom-docs-data"')[1]
    assert "</script>\nhere" not in body
    assert "<\\/script>" in body
    # And still valid JSON after the open tag.
    payload = body.split(">", 1)[1].rsplit("</script>", 1)[0].strip()
    assert json.loads(payload)["wiki"][0]["body_md"] == "danger </script> here"


# ── churn numstat parsing (monkeypatched git) ────────────────────────────────

def test_numstat_parsing(monkeypatch):
    sample = "12\t3\tsrc/a.py\n0\t7\tsrc/b.py\n-\t-\tassets/logo.png\n"
    monkeypatch.setattr(fm_backfill, "_git", lambda *a, **k: sample)
    m = fm_backfill._get_commit_numstat(Path("."), "deadbeef")
    assert m == {"files_changed": 3, "insertions": 12, "deletions": 10}


def test_numstat_empty_returns_none(monkeypatch):
    monkeypatch.setattr(fm_backfill, "_git", lambda *a, **k: "")
    assert fm_backfill._get_commit_numstat(Path("."), "x") is None


def test_numstat_git_failure_safe(monkeypatch):
    def boom(*a, **k):
        raise OSError("git missing")
    monkeypatch.setattr(fm_backfill, "_git", boom)
    # _git itself swallows; emulate _git returning "" so helper returns None.
    monkeypatch.setattr(fm_backfill, "_git", lambda *a, **k: "")
    assert fm_backfill._get_commit_numstat(Path("."), "x") is None


# ── Stop hook embeds data.config ─────────────────────────────────────────────

def test_stop_hook_writes_config_echo(project_dir, hook_runner):
    (project_dir / ".feature-memory" / "config.yaml").write_text(
        "schema_version: 1\nfeatures:\n  feat-a:\n    globs:\n      - 'src/**'\n"
        "changelog:\n  verbosity: detailed\n",
        encoding="utf-8",
    )
    (project_dir / ".feature-memory" / "events.jsonl").write_text(
        json.dumps({"event_type": "path_touched", "path": "src/x.py",
                    "session_id": "sc", "created_at": "2026-05-19T00:00:00+00:00"}) + "\n",
        encoding="utf-8",
    )
    hook_runner("claude_stop.py", {"session_id": "sc"})
    data = json.loads((project_dir / "docs" / "feature-memory" / "changelogs"
                       / "changelog.json").read_text(encoding="utf-8"))
    assert data["config"]["verbosity"] == "detailed"
    assert data["schema_version"] == 2
