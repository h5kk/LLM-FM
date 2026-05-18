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
    load_skip_patterns, should_skip_path, _infer_audience, _infer_kind,
    rotate_events_if_oversized, load_tag_strategy, _keyword_tags_for_entry,
)


def _compile_changelog(project_dir, events, features, git_info):
    """Compile changelogs/changelog.json from session JSONL events.

    Groups events by (git_hash, feature_id) when a commit hash is available,
    creating one entry per (commit, feature) pair with the real commit message
    as summary. Falls back to one WIP entry per feature for uncommitted work.

    Deduplicates by event_id (for WIP) and by (git_hash[:12], feature_id)
    for committed work. Updates inline JSON in changelog-viewer.html.
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

    # Load existing entries — primary key is event_id; secondary is (hash12, feature_id)
    existing = {}
    existing_pairs: set = set()
    if changelog_path.exists():
        try:
            old = json.loads(changelog_path.read_text(encoding="utf-8"))
            for entry in old.get("entries", []):
                eid = entry.get("event_id", "")
                if eid:
                    existing[eid] = entry
                h = entry.get("git_hash", "")
                if h:
                    existing_pairs.add((h[:12], entry.get("feature_id")))
        except Exception:
            pass

    # Collect all relevant path_touched events for this session
    git_hash = git_info.get("git_hash") if git_info else None
    git_message = git_info.get("git_message") if git_info else None
    git_author = git_info.get("git_author") if git_info else None
    git_email = git_info.get("git_email") if git_info else None

    # Determine tagging strategy for this project
    tag_strategy = load_tag_strategy(project_dir)

    # Extract session_id for stable WIP entry IDs
    session_id = next((e.get("session_id", "") for e in events if e.get("session_id")), "")

    # Bucket paths by feature_id
    feature_paths: dict = {}
    unmapped_paths = []
    session_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    for event in events:
        if event.get("event_type") != "path_touched":
            continue
        path = event.get("path", "")
        if not path:
            continue
        if path.startswith("docs/feature-memory/"):
            continue
        if path.endswith(".md"):
            continue
        date_str = event.get("created_at", "")[:10] or session_date
        matched = match_path_to_features(path, features)
        if matched:
            for fid in matched:
                feature_paths.setdefault(fid, {"paths": [], "date": date_str})
                if path not in feature_paths[fid]["paths"]:
                    feature_paths[fid]["paths"].append(path)
        else:
            if path not in unmapped_paths:
                unmapped_paths.append(path)

    added = 0

    def _make_entry(eid, fid, paths, date, committed):
        if isinstance(features.get(fid), dict):
            f_title = features[fid].get("title") or fid
        else:
            f_title = fid
        kinds = _infer_kind(paths, git_message or "")
        audience = _infer_audience(paths, git_message or "", kinds)
        if committed and git_message:
            summary = git_message
            commit_state = "committed"
            review_status = "auto"
        else:
            summary = f"WIP: {len(paths)} file(s) touched in {fid or 'unmapped'}"
            commit_state = "uncommitted"
            review_status = "wip"
        entry = {
            "event_id": eid,
            "date": date,
            "feature_id": fid,
            "feature_title": f_title,
            "audience": audience,
            "summary": summary,
            "kind": kinds,
            "tags": _infer_tags(paths, git_message or "", kinds),
            "topic_tags": [],
            "topic_pending": True,
            "paths": paths,
            "git_author": git_author,
            "git_email": git_email,
            "git_message": git_message,
            "git_hash": git_hash,
            "commit_state": commit_state,
            "confidence": "high",
            "review_status": review_status,
            "source": "hook",
        }
        # Honor tagging strategy: keyword = immediate heuristic tags; none = skip tagging
        if tag_strategy == "keyword":
            entry["topic_tags"] = _keyword_tags_for_entry(entry)
            entry["topic_pending"] = False
        elif tag_strategy == "none":
            entry["topic_pending"] = False
        # "cli" keeps topic_pending: True — tags are applied later via --drain-pending
        return entry

    if feature_paths or unmapped_paths:
        committed = bool(git_hash and git_message)

        for fid, meta in feature_paths.items():
            paths = meta["paths"]
            date = meta["date"]
            if committed:
                pair_key = (git_hash[:12], fid)
                if pair_key in existing_pairs:
                    continue
                eid = f"{git_hash[:12]}-{fid}"
            else:
                # For WIP, use session_id for a stable per-(feature, session) eid
                sid_short = (session_id or "unknown")[:12].replace("-", "")
                eid = f"wip-{fid}-{sid_short}"

            if eid in existing:
                continue
            entry = _make_entry(eid, fid, paths, date, committed)
            existing[eid] = entry
            if committed:
                existing_pairs.add((git_hash[:12], fid))
            added += 1

        if unmapped_paths:
            date = session_date
            if committed:
                pair_key = (git_hash[:12], None)
                if pair_key not in existing_pairs:
                    eid = f"{git_hash[:12]}-unmapped"
                    if eid not in existing:
                        entry = _make_entry(eid, None, unmapped_paths, date, committed)
                        existing[eid] = entry
                        existing_pairs.add(pair_key)
                        added += 1
            else:
                sid_short = (session_id or "unknown")[:12].replace("-", "")
                eid = f"wip-unmapped-{sid_short}"
                if eid not in existing:
                    entry = _make_entry(eid, None, unmapped_paths, date, committed)
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
        if len(json_str) > 500_000:
            from fm_common import log_error
            log_error(
                f"changelog-viewer.html inline JSON is {len(json_str)//1024}KB "
                "(>500KB). Consider switching to an external changelog.json fetch in v0.8.0."
            )
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

    features = load_config(project_dir)
    skip_patterns = load_skip_patterns(project_dir)

    touched_paths = set()
    doc_paths_touched = set()

    for event in events:
        if event.get("event_type") == "path_touched":
            path = event.get("path", "")
            if path.startswith("docs/feature-memory/"):
                doc_paths_touched.add(path)
            elif not path.endswith(".md") and not should_skip_path(path, skip_patterns):
                touched_paths.add(path)

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
        # Handle both flat and split layouts; pass feature meta for explicit mode override
        expected_doc = get_feature_doc_path(fid, docs_root, features.get(fid))
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
