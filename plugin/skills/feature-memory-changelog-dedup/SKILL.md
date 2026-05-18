---
description: >
  Merges duplicate changelog entries that share the same git commit and feature
  into a single entry. Keeps the best-quality summary (git-backfill wins over
  hook-generated), unions file paths, and deduplicates tags. Use when the user
  says "dedup changelog", "remove duplicates", "merge duplicate entries", or "/dedup".
allowed-tools: Bash, Read
---

# Feature Memory Changelog Dedup

## When to activate

- User says "dedup changelog", "deduplicate changelog", "remove duplicates"
- User says "merge duplicate entries", "clean up changelog entries"
- User says "same entry is showing twice", "duplicate changes in changelog"
- User types `/dedup`

## How duplicates happen

The Stop hook records one entry *per file touched* in a session. If three files
belonging to the same feature are edited in one git commit, you get three entries
with the same `git_hash` + `feature_id`. The `--dedup` command collapses these
into a single entry with all paths merged.

## Step 1: Run dedup

```bash
python plugin/hooks/fm_backfill.py --dedup
```

The script prints:
- `Dedup: N entries → M entries (K duplicate(s) absorbed).`
- `Done.` (if anything was merged) or `No duplicates found — nothing to merge.`

## Step 2: Report

Tell the user:
- How many entries were before and after
- How many duplicates were absorbed
- Whether the viewer was updated

Example:
> Dedup complete: 94 entries → 81 entries (13 duplicates merged).
> Viewer updated at `docs/feature-memory/changelog-viewer.html`.

If there were no duplicates, say:
> No duplicates found — your changelog is already clean.

## Notes

- Only entries that share the same `git_hash` **and** `feature_id` are merged.
  Entries for the same commit touching *different* features stay separate (they
  represent genuinely distinct feature impacts).
- Entries without a `git_hash` (uncommitted session work) are left untouched.
- Safe to re-run: idempotent — running twice produces the same result.
- To prevent future duplicates, the skip_patterns config (`.feature-memory/config.yaml`)
  filters out generated/cached files before entries are ever created.
