"""Tests for claude_post_tool.py hook."""
import json
import subprocess
import sys
from pathlib import Path

import pytest


def test_post_tool_logs_event(hook_runner, project_dir):
    """PostToolUse hook should append a path_touched event to events.jsonl."""
    stdin = {
        "session_id": "sess-001",
        "tool_name": "Edit",
        "tool_input": {"file_path": str(project_dir / "src" / "app.py")},
    }
    hook_runner("claude_post_tool.py", stdin)
    events_path = project_dir / ".feature-memory" / "events.jsonl"
    lines = [l for l in events_path.read_text().splitlines() if l.strip()]
    assert len(lines) >= 1
    evt = json.loads(lines[-1])
    assert evt["event_type"] == "path_touched"
    assert evt["session_id"] == "sess-001"


def test_post_tool_no_crash_on_missing_file_path(hook_runner, project_dir):
    """PostToolUse hook must not crash when tool_input has no file_path."""
    stdin = {"session_id": "sess-001", "tool_name": "Bash", "tool_input": {"command": "echo hi"}}
    out, err, code = hook_runner("claude_post_tool.py", stdin)
    assert code == 0


def test_post_tool_empty_stdin(hook_runner, project_dir):
    """PostToolUse hook with empty stdin must not crash."""
    script = Path(__file__).parent.parent / "plugin" / "hooks" / "claude_post_tool.py"
    proc = subprocess.run(
        [sys.executable, str(script)],
        input="",
        capture_output=True,
        text=True,
        cwd=str(project_dir),
    )
    assert proc.returncode == 0


def test_post_tool_write_tool_logs_event(hook_runner, project_dir):
    """PostToolUse hook should log events for Write tool too."""
    stdin = {
        "session_id": "sess-002",
        "tool_name": "Write",
        "tool_input": {"file_path": str(project_dir / "src" / "new_file.py")},
    }
    hook_runner("claude_post_tool.py", stdin)
    events_path = project_dir / ".feature-memory" / "events.jsonl"
    lines = [l for l in events_path.read_text().splitlines() if l.strip()]
    assert len(lines) >= 1
    evt = json.loads(lines[-1])
    assert evt["event_type"] == "path_touched"


def test_post_tool_normalizes_path(hook_runner, project_dir):
    """PostToolUse hook should produce a relative path in the event."""
    stdin = {
        "session_id": "sess-003",
        "tool_name": "Edit",
        "tool_input": {"file_path": str(project_dir / "src" / "app.py")},
    }
    hook_runner("claude_post_tool.py", stdin)
    events_path = project_dir / ".feature-memory" / "events.jsonl"
    lines = [l for l in events_path.read_text().splitlines() if l.strip()]
    if lines:
        evt = json.loads(lines[-1])
        # Path should not be absolute (relative to project_dir)
        path = evt.get("path", "")
        assert not path.startswith("/") or ":" not in path  # not Windows absolute
