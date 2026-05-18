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
from fm_common import load_config, match_path_to_features, _infer_tags, _check_viewer_update

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


def _infer_kind(paths, message):
    m = message.lower()
    if any(k in m for k in ("fix", "bug", "patch", "repair", "hotfix")):
        return ["bug-fix"]
    if any(k in m for k in ("add ", "new ", "feat", "implement", "create", "introduce", "initial")):
        return ["new-feature"]
    if any(k in m for k in ("refactor", "cleanup", "clean up", "rename", "reorganize", "move", "extract")):
        return ["refactor"]
    if any(k in m for k in ("update", "bump", "upgrade", "change", "modify", "improve")):
        return ["behavior-change"]
    return ["behavior-change"]


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


def _retag_existing(project_dir, changelog_path, docs_root):
    """Re-infer and replace tags for all entries. No git scan — uses stored paths+message."""
    if not changelog_path.exists():
        print("No changelog.json found. Run backfill first.")
        return

    try:
        data = json.loads(changelog_path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"Error reading changelog: {e}")
        return

    entries = data.get("entries", [])
    updated = 0
    for entry in entries:
        new_tags = _infer_tags(
            entry.get("paths") or [],
            entry.get("git_message") or "",
            entry.get("kind") or [],
        )
        entry["tags"] = new_tags
        updated += 1

    print(f"Re-tagged {updated} entr{'y' if updated == 1 else 'ies'} (of {len(entries)} total).")

    if updated > 0:
        from datetime import datetime, timezone
        data["generated"] = datetime.now(timezone.utc).isoformat()
        changelog_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        _update_viewer(docs_root, data)
        print("Done.")
    else:
        print("Nothing to update — all entries already have tags.")


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
                       help="Re-infer and replace tags for ALL existing entries (no git scan)")
    args = parser.parse_args()

    if not any([args.hours, args.since, args.since_commit, args.all_commits, args.retag]):
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

        # Exclude FM doc files — they are meta-updates, not feature changes
        source_files = [f for f in files if not f.startswith("docs/feature-memory/")]
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
