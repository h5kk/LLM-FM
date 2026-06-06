#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SessionStart hook: inject Feature Memory context and archive stale events."""
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from fm_common import hook_error_wrapper, _check_viewer_update


def _safe_archive(events_path, archive_path):
    """Write events to archive atomically, then truncate original."""
    content = events_path.read_bytes()
    tmp = events_path.parent / f".events_archive_tmp_{os.getpid()}"
    try:
        tmp.write_bytes(content)
        tmp.replace(archive_path)
        # Truncate original only after successful archive
        events_path.write_text("", encoding="utf-8")
    except Exception:
        try:
            tmp.unlink(missing_ok=True)
        except Exception:
            pass
        raise


def main():
    try:
        hook_input = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        hook_input = {}

    project_dir = Path.cwd()
    docs_root = project_dir / "docs" / "feature-memory"

    if not docs_root.exists():
        return

    # Archive previous session's events before clearing.
    # Use the session_id embedded in the events themselves (not the new session's ID).
    events_path = project_dir / ".feature-memory" / "events.jsonl"
    if events_path.exists():
        content = events_path.read_text(encoding="utf-8")
        if content.strip():
            # Extract session_id from the FIRST event that has a valid one
            # (sessions don't span events.jsonl files in normal flow)
            prev_session_id = None
            for raw_line in content.strip().splitlines():
                try:
                    ev = json.loads(raw_line)
                    sid = ev.get("session_id", "")
                    if sid and sid != "unknown":
                        prev_session_id = sid
                        break  # Use the first valid session_id
                except Exception:
                    pass
            if not prev_session_id:
                ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
                prev_session_id = f"unknown-{ts}-{os.getpid()}"
            # Sanitize to prevent path traversal via a crafted session_id
            safe_id = re.sub(r'[^a-zA-Z0-9_\-]', '_', prev_session_id)[:128]
            archive_path = project_dir / ".feature-memory" / f"events-{safe_id}.jsonl"
            try:
                _safe_archive(events_path, archive_path)
            except Exception as e:
                print(f"[FM] Warning: could not archive events to {archive_path.name}: {e}", file=sys.stderr)
        else:
            events_path.write_text("", encoding="utf-8")

    # Silently upgrade viewer if template is newer than what's installed in the project
    _check_viewer_update(docs_root)

    lines = []
    lines.append("=== Feature Memory ===")
    rel_docs = docs_root.relative_to(project_dir).as_posix()
    lines.append(f"Docs root: {rel_docs}")
    lines.append("")

    index_path = docs_root / "index.md"
    if index_path.exists():
        index_content = index_path.read_text(encoding="utf-8")
        in_table = False
        feature_lines = []
        for line in index_content.splitlines():
            if line.startswith("| Feature"):
                in_table = True
                continue
            if in_table and line.startswith("|---"):
                continue
            if in_table and line.startswith("|"):
                feature_lines.append(line.strip())
            elif in_table:
                in_table = False
        if feature_lines:
            lines.append("Documented features:")
            for fl in feature_lines:
                lines.append(f"  {fl}")
            lines.append("")

    recent_path = docs_root / "recent.md"
    if recent_path.exists():
        recent_content = recent_path.read_text(encoding="utf-8")
        in_frontmatter = False
        content_lines = []
        for line in recent_content.splitlines():
            if line.strip() == "---":
                in_frontmatter = not in_frontmatter
                continue
            if not in_frontmatter:
                content_lines.append(line)
        if content_lines:
            lines.append("Recent activity:")
            for cl in content_lines[:10]:
                if cl.strip():
                    lines.append(f"  {cl}")
            lines.append("")

    lines.append("Rules: Update feature docs after changing user-facing behavior.")
    lines.append("       Do not reorganize hierarchy; write proposals to reports/.")

    output = {"result": "continue", "message": "\n".join(lines)}
    json.dump(output, sys.stdout)


if __name__ == "__main__":
    hook_error_wrapper("SessionStart", main)
