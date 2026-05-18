#!/usr/bin/env python3
"""Stop hook: check for missing doc updates and compile changelog.json.

Filters events by current session_id. Captures git info once (15s budget).
Handles both flat (features/{id}.md) and split (features/{id}/index.md) layouts.
"""
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from fm_common import (
    load_config, match_path_to_features, hook_error_wrapper,
    get_feature_doc_path, get_git_info, _infer_tags, _check_viewer_update,
)


def _compile_changelog(project_dir, events, features, git_info):
    """Compile changelogs/changelog.json from session JSONL events.

    Appends new entries, deduplicates by event_id, keeps newest-first.
    Updates inline JSON data in changelog-viewer.html if it exists.
    """
    docs_root = project_dir / "docs" / "feature-memory"
    changelogs_dir = docs_root / "changelogs"
    changelog_path = changelogs_dir / "changelog.json"

    if not docs_root.exists():
        return

    try:
        changelogs_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        return

    # Load existing entries (keyed by event_id for dedup)
    existing = {}
    if changelog_path.exists():
        try:
            old = json.loads(changelog_path.read_text(encoding="utf-8"))
            for entry in old.get("entries", []):
                existing[entry["event_id"]] = entry
        except Exception:
            pass

    # Build new entries from session path-touched events (developer audience)
    added = 0
    for event in events:
        if event.get("event_type") != "path_touched":
            continue
        eid = event.get("event_id", "")
        if not eid or eid in existing:
            continue
        path = event.get("path", "")
        if path.startswith("docs/feature-memory/"):
            continue
        if path.endswith(".md"):
            continue
        matched = match_path_to_features(path, features)
        entry = {
            "event_id": eid,
            "date": event.get("created_at", "")[:10],
            "feature_id": matched[0] if matched else None,
            "feature_title": matched[0] if matched else "unmapped",
            "audience": "developer",
            "summary": f"Modified {path}",
            "kind": ["path_touched"],
            "tags": _infer_tags([path], "", ["path_touched"]),
            "topic_tags": [],
            "topic_pending": True,
            "paths": [path],
            "git_author": git_info.get("git_author") if git_info else None,
            "git_email": git_info.get("git_email") if git_info else None,
            "git_message": git_info.get("git_message") if git_info else None,
            "git_hash": git_info.get("git_hash") if git_info else None,
            "confidence": "high",
            "review_status": "auto",
            "source": "hook",
        }
        existing[eid] = entry
        added += 1

    all_entries = sorted(existing.values(), key=lambda x: x.get("date", ""), reverse=True)
    output_data = {
        "schema_version": 2,
        "generated": datetime.now(timezone.utc).isoformat(),
        "entries": all_entries,
    }

    if added > 0 or not changelog_path.exists():
        try:
            changelog_path.write_text(json.dumps(output_data, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass

    _update_viewer_data(docs_root, output_data)


def _find_viewer_template():
    """Locate the changelog-viewer.html template.

    Search order:
      1. <hooks_dir>/../../assets/changelog-viewer.html
         (works when running from the plugin's installed hooks/ directory)
      2. plugin/assets/changelog-viewer.html relative to cwd
         (works when running directly from the project root)
    Returns a Path if found, else None.
    """
    hooks_dir = Path(__file__).parent
    candidates = [
        hooks_dir / ".." / ".." / "assets" / "changelog-viewer.html",
        Path.cwd() / "plugin" / "assets" / "changelog-viewer.html",
    ]
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved.exists():
            return resolved
    return None


def _update_viewer_data(docs_root, data):
    """Update the inline JSON data block in changelog-viewer.html.

    If the viewer does not yet exist, attempt to copy it from the template
    found via _find_viewer_template() before injecting data.  If no template
    is found, silently skip (same behaviour as before).
    """
    viewer_path = docs_root / "changelog-viewer.html"
    if not viewer_path.exists():
        template = _find_viewer_template()
        if template is None:
            return
        try:
            shutil.copy2(str(template), str(viewer_path))
        except Exception:
            return
    else:
        _check_viewer_update(docs_root)
    try:
        content = viewer_path.read_text(encoding="utf-8")
        json_str = json.dumps(data, indent=2, ensure_ascii=False)
        new_content = re.sub(
            r'(<script id="changelog-data"[^>]*>)([\s\S]*?)(</script>)',
            lambda m: m.group(1) + "\n" + json_str + "\n" + m.group(3),
            content,
            count=1,
        )
        if new_content != content:
            viewer_path.write_text(new_content, encoding="utf-8")
    except Exception:
        pass


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

    # Capture git info once — cheaper here (15s budget) than in PostToolUse (3s)
    git_info = get_git_info(project_dir)

    touched_paths = set()
    doc_paths_touched = set()

    for event in events:
        if event.get("event_type") == "path_touched":
            path = event.get("path", "")
            if path.startswith("docs/feature-memory/"):
                doc_paths_touched.add(path)
            elif not path.endswith(".md"):
                touched_paths.add(path)

    features = load_config(project_dir)

    # Compile changelog.json from session events
    _compile_changelog(project_dir, events, features, git_info)

    if not touched_paths:
        return

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
    docs_root = project_dir / "docs" / "feature-memory"

    for fid, paths in sorted(features_touched.items(), key=lambda x: len(x[1]), reverse=True):
        # Handle both flat and split layouts
        expected_doc = get_feature_doc_path(fid, docs_root)
        try:
            expected_doc_rel = expected_doc.relative_to(project_dir).as_posix()
        except ValueError:
            expected_doc_rel = f"docs/feature-memory/features/{fid}.md"

        feature_dir_prefix = f"docs/feature-memory/features/{fid}/"
        doc_updated = (
            expected_doc_rel in doc_paths_touched
            or any(p.startswith(feature_dir_prefix) for p in doc_paths_touched)
        )

        if not doc_updated:
            features_needing_docs.append((fid, len(paths)))
            messages.append(
                f"- Feature '{fid}': {len(paths)} source file(s) changed "
                f"but {expected_doc_rel} was not updated"
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
