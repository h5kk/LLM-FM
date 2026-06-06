#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PostToolUse hook: record edited paths and remind about feature docs."""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from fm_common import (
    load_config, match_path_to_features, generate_event_id,
    hook_error_wrapper, get_feature_doc_path, rotate_events_if_oversized,
)


def main():
    try:
        hook_input = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        return

    tool_name = hook_input.get("tool_name", "")
    tool_input = hook_input.get("tool_input", {})

    file_path = None
    if tool_name in ("Edit", "Write", "MultiEdit"):
        file_path = tool_input.get("file_path")

    if not file_path:
        return

    project_dir = Path.cwd()

    if not (project_dir / ".feature-memory" / "config.yaml").exists():
        return

    try:
        abs_path = Path(file_path).resolve()
        rel_path = abs_path.relative_to(project_dir.resolve()).as_posix()
    except (ValueError, OSError):
        try:
            rel_path = Path(os.path.relpath(file_path, project_dir)).as_posix()
        except ValueError:
            rel_path = Path(file_path).as_posix()

    now = datetime.now(timezone.utc)
    event = {
        "event_id": generate_event_id(),
        "created_at": now.isoformat(),
        "event_type": "path_touched",
        "source": "claude-hook",
        "path": rel_path,
        "session_id": hook_input.get("session_id", "unknown"),
    }

    events_path = project_dir / ".feature-memory" / "events.jsonl"
    rotate_events_if_oversized(events_path)
    try:
        with open(events_path, "a", encoding="utf-8", newline="") as f:
            f.write(json.dumps(event) + "\n")
    except OSError:
        pass

    features = load_config(project_dir)
    matched_features = match_path_to_features(rel_path, features)

    if matched_features:
        feature_list = ", ".join(matched_features)
        docs_root = project_dir / "docs" / "feature-memory"
        doc_paths = ", ".join(
            get_feature_doc_path(fid, docs_root).relative_to(project_dir).as_posix()
            for fid in matched_features
        )
        output = {
            "result": "continue",
            "message": (
                f"[FM] Edited '{rel_path}' maps to feature(s): {feature_list}. "
                f"Consider updating: {doc_paths}"
            )
        }
        json.dump(output, sys.stdout)


if __name__ == "__main__":
    hook_error_wrapper("PostToolUse", main)
