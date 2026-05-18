---
description: >
  Refreshes an existing Feature Memory changelog — re-infers tags for all entries
  that predate the tag system, and regenerates the changelog viewer. Safe to run
  multiple times (skips entries that already have tags). Use when the user says
  "refresh changelog", "add tags to existing changelog", "retag changelog",
  "update changelog entries", or "/changelog-refresh".
allowed-tools: Bash, Read
---

# Feature Memory Changelog Refresh

## When to activate

- User says "refresh changelog", "retag changelog", "add tags to existing entries"
- User says "update my changelog", "my changelog entries don't have tags"
- User says "I installed before tags were added" or asks how to get tags on old entries
- User types `/changelog-refresh`

## Pre-check

Verify the changelog exists before running:

```bash
ls docs/feature-memory/changelogs/changelog.json
```

If it does not exist, stop and tell the user to run backfill first:

> No changelog found. Run "backfill changelog" (or `/backfill`) first to generate it from git history, then `/changelog-refresh` to tag the entries.

## What this does

The refresh command re-infers tags for every existing changelog entry that does not
yet have tags (entries created before tag support was added in v0.4.0). It uses the
stored `paths` and `git_message` fields already in the JSON — no git re-scan needed.

- Entries that already have tags are left untouched.
- The changelog viewer HTML is regenerated with the updated data.
- Safe to run multiple times.

## Step 1: Run the retag pass

```bash
python plugin/hooks/fm_backfill.py --retag
```

The script prints:
- `Re-tagged N entries (of M total).`
- `Done.` if anything changed, or `Nothing to update — all entries already have tags.`

## Step 2: Report to the user

Parse the output and report:

- How many entries were re-tagged
- Total entries in the changelog
- Whether the viewer was refreshed

Example report:

> Changelog refresh complete:
>
> - Re-tagged 23 entries that were missing tags (of 31 total)
> - 8 entries already had tags — untouched
> - Changelog viewer refreshed at `docs/feature-memory/changelog-viewer.html`
>
> Open the viewer to explore entries by tag. Run `/backfill` to pull in any commits not yet in the changelog.

If nothing was updated, tell the user their changelog is already up to date.

## Notes

- Tags are inferred from file paths (tech layer) and commit messages (impact/quality/process).
- Entries from `source: hook` (session-end events) typically get 0–1 tags because they
  record one path at a time without a full commit message.
- For richer tags on hook entries, run `/backfill` to merge the git commit context
  for those files — the cross-source dedup keeps it clean.
