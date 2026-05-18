"""Tests for claude_stop.py hook."""
import json
import subprocess
import sys
from pathlib import Path

import pytest


def test_stop_no_events(hook_runner, project_dir):
    """Stop hook with empty events.jsonl should exit silently."""
    out, err, code = hook_runner("claude_stop.py", {"session_id": "sess-001"})
    assert code == 0


def test_stop_creates_changelog(hook_runner, project_dir):
    """Stop hook should create changelog.json from path_touched events."""
    events_path = project_dir / ".feature-memory" / "events.jsonl"
    events_path.write_text(
        json.dumps({
            "event_id": "20260518T000000Z-0001",
            "event_type": "path_touched",
            "path": "src/app.py",
            "session_id": "sess-001",
            "created_at": "2026-05-18T00:00:00+00:00",
        }) + "\n",
        encoding="utf-8",
    )
    hook_runner("claude_stop.py", {"session_id": "sess-001"})
    changelog = project_dir / "docs" / "feature-memory" / "changelogs" / "changelog.json"
    assert changelog.exists()
    data = json.loads(changelog.read_text())
    assert data["schema_version"] == 2
    assert len(data["entries"]) >= 1


def test_stop_skips_md_paths(hook_runner, project_dir):
    """Stop hook should not create entries for .md files."""
    events_path = project_dir / ".feature-memory" / "events.jsonl"
    events_path.write_text(
        json.dumps({
            "event_id": "20260518T000000Z-0002",
            "event_type": "path_touched",
            "path": "README.md",
            "session_id": "sess-002",
            "created_at": "2026-05-18T00:00:00+00:00",
        }) + "\n",
        encoding="utf-8",
    )
    hook_runner("claude_stop.py", {"session_id": "sess-002"})
    changelog = project_dir / "docs" / "feature-memory" / "changelogs" / "changelog.json"
    # If changelog created, should have 0 entries for md-only session
    if changelog.exists():
        data = json.loads(changelog.read_text())
        assert all(
            e["session_id"] != "sess-002" or not e["paths"][0].endswith(".md")
            for e in data.get("entries", [])
            if e.get("paths")
        )


def test_stop_filters_by_session(hook_runner, project_dir):
    """Stop hook should only process events matching current session_id."""
    events_path = project_dir / ".feature-memory" / "events.jsonl"
    events = [
        {"event_id": "001", "event_type": "path_touched", "path": "src/a.py", "session_id": "sess-A", "created_at": "2026-05-18T00:00:00+00:00"},
        {"event_id": "002", "event_type": "path_touched", "path": "src/b.py", "session_id": "sess-B", "created_at": "2026-05-18T00:00:00+00:00"},
    ]
    events_path.write_text("\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8")
    hook_runner("claude_stop.py", {"session_id": "sess-A"})
    changelog = project_dir / "docs" / "feature-memory" / "changelogs" / "changelog.json"
    if changelog.exists():
        data = json.loads(changelog.read_text())
        paths = [p for e in data.get("entries", []) for p in (e.get("paths") or [])]
        assert "src/b.py" not in paths


def test_stop_malformed_stdin(hook_runner, project_dir):
    """Stop hook with empty stdin should not crash."""
    script = Path(__file__).parent.parent / "plugin" / "hooks" / "claude_stop.py"
    proc = subprocess.run(
        [sys.executable, str(script)],
        input="",
        capture_output=True,
        text=True,
        cwd=str(project_dir),
    )
    assert proc.returncode == 0


def test_stop_entry_has_commit_state(hook_runner, project_dir):
    """Stop hook entries should have commit_state field."""
    events_path = project_dir / ".feature-memory" / "events.jsonl"
    events_path.write_text(
        json.dumps({
            "event_id": "20260518T000000Z-0003",
            "event_type": "path_touched",
            "path": "src/app.py",
            "session_id": "sess-003",
            "created_at": "2026-05-18T00:00:00+00:00",
        }) + "\n",
        encoding="utf-8",
    )
    hook_runner("claude_stop.py", {"session_id": "sess-003"})
    changelog = project_dir / "docs" / "feature-memory" / "changelogs" / "changelog.json"
    if changelog.exists():
        data = json.loads(changelog.read_text())
        for entry in data.get("entries", []):
            assert "commit_state" in entry
            assert entry["commit_state"] in ("committed", "uncommitted")
