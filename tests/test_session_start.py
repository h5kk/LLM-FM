"""Tests for claude_session_start.py hook."""
import json
import subprocess
import sys
from pathlib import Path

import pytest


def test_session_start_archives_previous(hook_runner, project_dir):
    """SessionStart should archive previous events.jsonl."""
    events_path = project_dir / ".feature-memory" / "events.jsonl"
    events_path.write_text(
        json.dumps({
            "event_id": "old-001",
            "session_id": "prev-sess",
            "event_type": "path_touched",
            "path": "x.py",
            "created_at": "2026-05-01T00:00:00+00:00",
        }) + "\n",
        encoding="utf-8",
    )
    hook_runner("claude_session_start.py", {"session_id": "new-sess"})
    # events.jsonl should be cleared
    assert events_path.read_text().strip() == ""
    # archive file should exist
    fm_dir = project_dir / ".feature-memory"
    archives = list(fm_dir.glob("events-*.jsonl"))
    assert len(archives) >= 1


def test_session_start_empty_events(hook_runner, project_dir):
    """SessionStart with empty events.jsonl should not crash."""
    out, err, code = hook_runner("claude_session_start.py", {"session_id": "new-sess"})
    assert code == 0


def test_session_start_no_events_file(hook_runner, project_dir):
    """SessionStart when events.jsonl doesn't exist should not crash."""
    events_path = project_dir / ".feature-memory" / "events.jsonl"
    if events_path.exists():
        events_path.unlink()
    out, err, code = hook_runner("claude_session_start.py", {"session_id": "new-sess"})
    assert code == 0


def test_session_start_uses_first_session_id(hook_runner, project_dir):
    """SessionStart should archive under the FIRST valid session_id in events."""
    events_path = project_dir / ".feature-memory" / "events.jsonl"
    events = [
        {"event_id": "e1", "session_id": "first-sess", "event_type": "path_touched", "path": "a.py", "created_at": "2026-05-01T00:00:00+00:00"},
        {"event_id": "e2", "session_id": "second-sess", "event_type": "path_touched", "path": "b.py", "created_at": "2026-05-01T00:01:00+00:00"},
    ]
    events_path.write_text("\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8")
    hook_runner("claude_session_start.py", {"session_id": "new-sess"})
    fm_dir = project_dir / ".feature-memory"
    archives = list(fm_dir.glob("events-first*sess*.jsonl"))
    assert len(archives) >= 1, "Should archive under first session_id"


def test_session_start_unknown_session_id(hook_runner, project_dir):
    """SessionStart with only malformed/unknown events should archive under unknown-* name."""
    events_path = project_dir / ".feature-memory" / "events.jsonl"
    events_path.write_text(
        json.dumps({
            "event_id": "e1",
            "session_id": "unknown",
            "event_type": "path_touched",
            "path": "a.py",
            "created_at": "2026-05-01T00:00:00+00:00",
        }) + "\n",
        encoding="utf-8",
    )
    hook_runner("claude_session_start.py", {"session_id": "new-sess"})
    fm_dir = project_dir / ".feature-memory"
    archives = list(fm_dir.glob("events-unknown-*.jsonl"))
    assert len(archives) >= 1, "Should archive under unknown-{timestamp} name"


def test_session_start_malformed_stdin(hook_runner, project_dir):
    """SessionStart with empty stdin should not crash."""
    script = Path(__file__).parent.parent / "plugin" / "hooks" / "claude_session_start.py"
    proc = subprocess.run(
        [sys.executable, str(script)],
        input="",
        capture_output=True,
        text=True,
        cwd=str(project_dir),
    )
    assert proc.returncode == 0
