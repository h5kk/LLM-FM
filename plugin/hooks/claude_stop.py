#!/usr/bin/env python3
"""Stop hook: check if touched source files have missing docs updates.

Filters events by current session_id and sorts output by change count.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from fm_common import load_config, match_path_to_features, hook_error_wrapper


def main():
    try:
        hook_input = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        hook_input = {}

    project_dir = Path.cwd()
    events_path = project_dir / ".feature-memory" / "events.jsonl"

    if not events_path.exists():
        return

    current_session = hook_input.get("session_id")

    events = []
    for line in events_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    if not events:
        return

    if current_session:
        events = [e for e in events if e.get("session_id") == current_session]
        if not events:
            return

    touched_paths = set()
    doc_paths_touched = set()

    for event in events:
        if event.get("event_type") == "path_touched":
            path = event.get("path", "")
            if path.startswith("docs/feature-memory/"):
                doc_paths_touched.add(path)
            else:
                touched_paths.add(path)

    if not touched_paths:
        return

    features = load_config(project_dir)
    features_touched = {}
    unmapped_paths = []

    for path in touched_paths:
        matched = match_path_to_features(path, features)
        if matched:
            for fid in matched:
                features_touched.setdefault(fid, []).append(path)
        else:
            unmapped_paths.append(path)

    if not features_touched and not unmapped_paths:
        return

    messages = []
    features_needing_docs = []

    for fid, paths in sorted(features_touched.items(), key=lambda x: len(x[1]), reverse=True):
        doc_path = f"docs/feature-memory/features/{fid}.md"
        if doc_path not in doc_paths_touched:
            features_needing_docs.append((fid, len(paths)))
            messages.append(
                f"- Feature '{fid}': {len(paths)} source file(s) changed "
                f"but {doc_path} was not updated"
            )

    if unmapped_paths:
        messages.append(
            f"- {len(unmapped_paths)} file(s) edited that don't map to any feature: "
            + ", ".join(sorted(unmapped_paths)[:5])
        )

    if messages:
        summary = "[FM] Session documentation check:\n" + "\n".join(messages)
        if features_needing_docs:
            sorted_names = [f"{fid} ({count})" for fid, count in
                           sorted(features_needing_docs, key=lambda x: x[1], reverse=True)]
            summary += "\n\nConsider updating feature docs for: " + ", ".join(sorted_names)

        output = {"result": "continue", "message": summary}
        json.dump(output, sys.stdout)


if __name__ == "__main__":
    hook_error_wrapper("Stop", main)
