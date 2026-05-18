#!/usr/bin/env python3
"""Backfill changelog.json from git commit history.

Reads git log, maps changed files to features via config, and appends structured
entries to docs/feature-memory/changelogs/changelog.json. Deduplicates by
commit+feature so re-running is safe. Updates changelog-viewer.html inline data.

Usage:
  python plugin/hooks/fm_backfill.py --hours 48
  python plugin/hooks/fm_backfill.py --since 2026-05-01
  python plugin/hooks/fm_backfill.py --since-commit abc1234
  python plugin/hooks/fm_backfill.py --all
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from fm_common import load_config, match_path_to_features, _infer_tags, _check_viewer_update, generate_topic_tags_batch, load_skip_patterns, should_skip_path, _infer_kind

_JIRA_RE = re.compile(r'\b([A-Z][A-Z0-9]{1,9}-\d+)\b')


def _git(*args, cwd=None):
    try:
        result = subprocess.run(
            ["git"] + list(args),
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(cwd) if cwd else None,
        )
        return result.stdout.strip() if result.returncode == 0 else ""
    except Exception:
        return ""


def _get_branch(project_dir):
    return _git("rev-parse", "--abbrev-ref", "HEAD", cwd=project_dir)


def _extract_jira(text):
    """Return first Jira-style ticket found in text, or None."""
    m = _JIRA_RE.search(text or "")
    return m.group(1) if m else None


def _get_commits(project_dir, hours=None, since=None, all_commits=False, since_commit=None):
    args = ["log", "--format=%H|%an|%ae|%ai|%s"]
    if since_commit:
        args.append(f"{since_commit}..HEAD")
    elif hours is not None:
        args.append(f"--since={hours} hours ago")
    elif since:
        args.append(f"--since={since}")
    # all_commits: no filter
    out = _git(*args, cwd=project_dir)
    if not out:
        return []
    commits = []
    for line in out.splitlines():
        parts = line.split("|", 4)
        if len(parts) == 5:
            commits.append({
                "hash": parts[0],
                "author": parts[1],
                "email": parts[2],
                "date": parts[3][:10],
                "message": parts[4],
            })
    return commits


def _get_commit_files(project_dir, commit_hash):
    # --root ensures the root commit's files are included
    out = _git("diff-tree", "--no-commit-id", "-r", "--name-only", "--root", commit_hash, cwd=project_dir)
    return [f for f in out.splitlines() if f.strip()]



def _infer_audience(paths, kinds):
    # Pure refactor/test/config → developer only
    if kinds == ["refactor"]:
        return "developer"
    internal_only = all(
        any(pat in p for pat in ("test", "spec", ".yaml", ".json", ".lock", ".md", "config"))
        for p in paths
    )
    if internal_only:
        return "developer"
    return "both"


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


def _update_viewer(docs_root, data):
    """Update the inline JSON data block in changelog-viewer.html.

    If the viewer does not yet exist, attempt to copy it from the template
    found via _find_viewer_template() before injecting data.  If no template
    is found, silently skip.
    """
    viewer = docs_root / "changelog-viewer.html"
    if not viewer.exists():
        template = _find_viewer_template()
        if template is None:
            return
        try:
            shutil.copy2(str(template), str(viewer))
            print(f"  Created viewer from template: {viewer.relative_to(docs_root.parent.parent)}")
        except Exception as e:
            print(f"  Warning: could not copy viewer template: {e}")
            return
    else:
        _check_viewer_update(docs_root)
    try:
        content = viewer.read_text(encoding="utf-8")
        json_str = json.dumps(data, indent=2, ensure_ascii=False)
        new_content = re.sub(
            r'(<script id="changelog-data"[^>]*>)([\s\S]*?)(</script>)',
            lambda m: m.group(1) + "\n" + json_str + "\n" + m.group(3),
            content,
            count=1,
        )
        if new_content != content:
            viewer.write_text(new_content, encoding="utf-8")
            print(f"  Updated {viewer.relative_to(docs_root.parent.parent)}")
    except Exception as e:
        print(f"  Warning: viewer update failed: {e}")


def _purge_md_only(project_dir, changelog_path, docs_root):
    """Remove entries where every stored path is a .md file."""
    if not changelog_path.exists():
        print("No changelog.json found. Run backfill first.")
        return
    try:
        data = json.loads(changelog_path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"Error reading changelog: {e}")
        return
    entries = data.get("entries", [])
    before = len(entries)
    kept = [e for e in entries
            if not (e.get("paths") and all(p.endswith(".md") for p in e["paths"]))]
    removed = before - len(kept)
    print(f"Removed {removed} entr{'y' if removed == 1 else 'ies'} with only .md paths (of {before} total).")
    if removed > 0:
        from datetime import datetime, timezone
        data["entries"] = kept
        data["generated"] = datetime.now(timezone.utc).isoformat()
        changelog_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        _update_viewer(docs_root, data)
        print("Done.")
    else:
        print("Nothing removed — no .md-only entries found.")


def _clear_changelog(project_dir, changelog_path, docs_root):
    """Clear all entries from changelog.json (does not touch .md docs)."""
    from datetime import datetime, timezone
    data = {
        "schema_version": 2,
        "generated": datetime.now(timezone.utc).isoformat(),
        "entries": [],
    }
    changelog_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    _update_viewer(docs_root, data)
    print("Cleared changelog.json — 0 entries remain.")
    print("Feature .md docs untouched. Run backfill to repopulate.")


def _retag_existing(project_dir, changelog_path, docs_root):
    """Two-phase retag: regex Impact/Quality/Process tags, then LLM semantic topic tags."""
    if not changelog_path.exists():
        print("No changelog.json found. Run backfill first.")
        return

    try:
        data = json.loads(changelog_path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"Error reading changelog: {e}")
        return

    entries = data.get("entries", [])

    # Phase 1 — regex tags (fast, in-process)
    for entry in entries:
        entry["tags"] = _infer_tags(
            entry.get("paths") or [],
            entry.get("git_message") or "",
            entry.get("kind") or [],
        )
        entry.pop("topic_pending", None)

    print(f"Regex tags refreshed for {len(entries)} entries. Generating topic tags via LLM...")

    # Phase 2 — LLM semantic topic tags (batched claude CLI calls)
    topic_lists = generate_topic_tags_batch(entries)
    for entry, topic_tags in zip(entries, topic_lists):
        entry["topic_tags"] = topic_tags

    tagged = sum(1 for tl in topic_lists if tl)
    print(f"Topic tags generated for {tagged} of {len(entries)} entries.")

    from datetime import datetime, timezone
    data["generated"] = datetime.now(timezone.utc).isoformat()
    changelog_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    _update_viewer(docs_root, data)
    print("Done.")


def _drain_pending(changelog_path, docs_root):
    """Generate LLM topic tags for entries marked topic_pending=True."""
    if not changelog_path.exists():
        print("No changelog.json found.")
        return
    try:
        data = json.loads(changelog_path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"Error reading changelog: {e}")
        return

    pending = [e for e in data.get("entries", []) if e.get("topic_pending")]
    if not pending:
        print("No pending entries — all topic tags already generated.")
        return

    print(f"Generating topic tags for {len(pending)} pending entries...")
    topic_lists = generate_topic_tags_batch(pending)
    for entry, topic_tags in zip(pending, topic_lists):
        entry["topic_tags"] = topic_tags
        entry.pop("topic_pending", None)

    tagged = sum(1 for tl in topic_lists if tl)
    print(f"Done. Tagged {tagged} of {len(pending)} entries.")

    from datetime import datetime, timezone
    data["generated"] = datetime.now(timezone.utc).isoformat()
    changelog_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    _update_viewer(docs_root, data)


def _dedup_entries(project_dir, changelog_path, docs_root):
    """Merge entries that share the same (git_hash, feature_id) into one.

    The most common source of duplicates is the Stop hook creating one entry
    per file touched while backfill creates one entry per feature per commit.
    Both end up with the same git_hash + feature_id pair.

    Strategy:
    - Group by (git_hash, feature_id).
    - In each group, prefer the git-backfill entry (better summary) as the base.
    - Union paths, tags, and topic_tags across all group members.
    - Entries with no git_hash are left untouched.
    """
    if not changelog_path.exists():
        print("No changelog.json found. Run backfill first.")
        return
    try:
        data = json.loads(changelog_path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"Error reading changelog: {e}")
        return

    entries = data.get("entries", [])
    before = len(entries)

    hashed: dict = {}
    no_hash = []
    for entry in entries:
        gh = entry.get("git_hash")
        if not gh:
            no_hash.append(entry)
            continue
        key = (gh, entry.get("feature_id"))
        hashed.setdefault(key, []).append(entry)

    merged = []
    merge_count = 0
    for (gh, fid), group in hashed.items():
        if len(group) == 1:
            merged.append(group[0])
            continue
        merge_count += len(group) - 1
        backfill = [e for e in group if e.get("source") == "git-backfill"]
        base = dict(backfill[0] if backfill else group[0])

        seen_p: set = set()
        all_paths = [p for e in group for p in (e.get("paths") or []) if not (p in seen_p or seen_p.add(p))]  # type: ignore[func-returns-value]
        seen_t: set = set()
        all_tags = [t for e in group for t in (e.get("tags") or []) if not (t in seen_t or seen_t.add(t))]  # type: ignore[func-returns-value]
        seen_tp: set = set()
        all_topic = [t for e in group for t in (e.get("topic_tags") or []) if not (t in seen_tp or seen_tp.add(t))]  # type: ignore[func-returns-value]

        base["paths"] = all_paths
        base["tags"] = all_tags[:5]
        base["topic_tags"] = all_topic[:5]
        merged.append(base)

    merged.extend(no_hash)
    merged.sort(key=lambda x: (x.get("date", ""), x.get("git_hash", "")), reverse=True)

    after = len(merged)
    removed = before - after
    print(f"Dedup: {before} entries -> {after} entries ({merge_count} duplicate(s) absorbed).")
    if removed > 0:
        data["entries"] = merged
        data["generated"] = datetime.now(timezone.utc).isoformat()
        changelog_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        _update_viewer(docs_root, data)
        print("Done.")
    else:
        print("No duplicates found — nothing to merge.")


def main():
    parser = argparse.ArgumentParser(
        description="Backfill FM changelog.json from git history",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--hours", type=int, metavar="N",
                       help="Commits from the last N hours (default: 48)")
    group.add_argument("--since", metavar="DATE",
                       help="Commits since date, e.g. 2026-05-01")
    group.add_argument("--since-commit", metavar="HASH",
                       help="Commits after this hash (exclusive)")
    group.add_argument("--all", action="store_true", dest="all_commits",
                       help="All commits in the repo")
    group.add_argument("--retag", action="store_true",
                       help="Regenerate tags for ALL entries: regex pass + LLM topic tags (no git scan)")
    group.add_argument("--drain-pending", action="store_true", dest="drain_pending",
                       help="Generate LLM topic tags for entries marked topic_pending=True")
    group.add_argument("--purge-md-only", action="store_true", dest="purge_md_only",
                       help="Remove entries whose every path is a .md file")
    group.add_argument("--clear", action="store_true",
                       help="Clear ALL entries from changelog.json (feature .md docs untouched)")
    group.add_argument("--dedup", action="store_true",
                       help="Merge duplicate entries sharing the same git commit + feature into one")
    args = parser.parse_args()

    if not any([args.hours, args.since, args.since_commit, args.all_commits,
                args.retag, args.drain_pending, args.purge_md_only, args.clear, args.dedup]):
        args.hours = 48

    project_dir = Path.cwd()
    docs_root = project_dir / "docs" / "feature-memory"
    changelogs_dir = docs_root / "changelogs"
    changelog_path = changelogs_dir / "changelog.json"

    if not docs_root.exists():
        print("Error: docs/feature-memory/ not found. Initialize feature memory first.")
        sys.exit(1)

    changelogs_dir.mkdir(parents=True, exist_ok=True)

    if args.retag:
        _retag_existing(project_dir, changelog_path, docs_root)
        return

    if args.drain_pending:
        _drain_pending(changelog_path, docs_root)
        return

    if args.purge_md_only:
        _purge_md_only(project_dir, changelog_path, docs_root)
        return

    if args.clear:
        _clear_changelog(project_dir, changelog_path, docs_root)
        return

    if args.dedup:
        _dedup_entries(project_dir, changelog_path, docs_root)
        return

    # Primary dedup: event_id. Secondary: (hash12, feature_id) to catch Stop-hook entries
    # which use UUID event_ids but cover the same commit+feature pair.
    existing = {}
    existing_pairs: set[tuple[str, str | None]] = set()
    if changelog_path.exists():
        try:
            old = json.loads(changelog_path.read_text(encoding="utf-8"))
            for entry in old.get("entries", []):
                try:
                    existing[entry["event_id"]] = entry
                    h = entry.get("git_hash", "")
                    fid = entry.get("feature_id")
                    if h:
                        existing_pairs.add((h[:12], fid))
                except (KeyError, TypeError):
                    pass  # skip malformed entries; don't break dedup for the rest
        except Exception as e:
            print(f"Warning: could not load existing changelog: {e}")

    features = load_config(project_dir)
    if not features:
        print("Warning: no features found in config. Files will appear as 'unmapped'.")
    skip_patterns = load_skip_patterns(project_dir)

    branch = _get_branch(project_dir)
    branch_ticket = _extract_jira(branch)
    if branch_ticket:
        print(f"Detected Jira ticket from branch: {branch_ticket}")

    commits = _get_commits(
        project_dir,
        hours=args.hours,
        since=args.since,
        all_commits=args.all_commits,
        since_commit=args.since_commit,
    )

    if not commits:
        print("No commits found in the specified range.")
        return

    label = (
        f"last {args.hours}h" if args.hours else
        f"since {args.since}" if args.since else
        f"since {args.since_commit}" if args.since_commit else
        "all time"
    )
    print(f"Processing {len(commits)} commit(s) ({label})…")

    added = 0
    for commit in commits:
        files = _get_commit_files(project_dir, commit["hash"])
        if not files:
            continue

        # Exclude FM doc files, .md files, and skip-listed paths (generated/cached/lock files etc.)
        source_files = [f for f in files if not f.startswith("docs/feature-memory/")]
        source_files = [f for f in source_files if not f.endswith(".md")]
        source_files = [f for f in source_files if not should_skip_path(f, skip_patterns)]
        if not source_files:
            continue

        feature_files: dict[str, list[str]] = {}
        unmapped_files = []
        for f in source_files:
            matched = match_path_to_features(f, features)
            if matched:
                for fid in matched:
                    feature_files.setdefault(fid, []).append(f)
            else:
                unmapped_files.append(f)

        # Jira ticket: prefer commit message, fall back to branch
        commit_ticket = _extract_jira(commit["message"])
        jira_ticket = commit_ticket or branch_ticket

        if feature_files:
            for fid, fid_files in feature_files.items():
                eid = f"{commit['hash'][:12]}-{fid}"
                if eid in existing or (commit['hash'][:12], fid) in existing_pairs:
                    continue
                kinds = _infer_kind(fid_files, commit["message"])
                audience = _infer_audience(fid_files, kinds)
                entry = {
                    "event_id": eid,
                    "date": commit["date"],
                    "feature_id": fid,
                    "feature_title": fid,
                    "audience": audience,
                    "summary": commit["message"],
                    "kind": kinds,
                    "tags": _infer_tags(fid_files, commit["message"], kinds),
                    "topic_tags": [],
                    "topic_pending": True,
                    "paths": fid_files,
                    "git_author": commit["author"],
                    "git_email": commit["email"],
                    "git_message": commit["message"],
                    "git_hash": commit["hash"],
                    "confidence": "high",
                    "review_status": "auto",
                    "source": "git-backfill",
                }
                if jira_ticket:
                    entry["jira_ticket"] = jira_ticket
                existing[eid] = entry
                existing_pairs.add((commit['hash'][:12], fid))
                added += 1

        elif unmapped_files:
            eid = f"{commit['hash'][:12]}-unmapped"
            if eid in existing or (commit['hash'][:12], None) in existing_pairs:
                continue
            kinds = _infer_kind(unmapped_files, commit["message"])
            audience = _infer_audience(unmapped_files, kinds)
            entry = {
                "event_id": eid,
                "date": commit["date"],
                "feature_id": None,
                "feature_title": "unmapped",
                "audience": audience,
                "summary": commit["message"],
                "kind": kinds,
                "tags": _infer_tags(unmapped_files, commit["message"], kinds),
                "topic_tags": [],
                "topic_pending": True,
                "paths": unmapped_files[:10],
                "git_author": commit["author"],
                "git_email": commit["email"],
                "git_message": commit["message"],
                "git_hash": commit["hash"],
                "confidence": "medium",
                "review_status": "auto",
                "source": "git-backfill",
            }
            if jira_ticket:
                entry["jira_ticket"] = jira_ticket
            existing[eid] = entry
            existing_pairs.add((commit['hash'][:12], None))
            added += 1

    print(f"Added {added} new entr{'y' if added == 1 else 'ies'}.")

    all_entries = sorted(
        existing.values(),
        key=lambda x: (x.get("date", ""), x.get("git_hash", "")),
        reverse=True,
    )
    output_data = {
        "schema_version": 2,
        "generated": datetime.now(timezone.utc).isoformat(),
        "entries": all_entries,
    }

    changelog_path.write_text(json.dumps(output_data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {len(all_entries)} total entr{'y' if len(all_entries) == 1 else 'ies'} -> {changelog_path.relative_to(project_dir)}")

    _update_viewer(docs_root, output_data)
    print("Done.")


if __name__ == "__main__":
    main()
