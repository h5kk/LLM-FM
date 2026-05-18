---
description: >
  Removes changelog entries whose every path is a .md file (documentation-only
  commits that don't represent feature behavior changes). Use when the user says
  "purge md entries", "remove doc-only entries", "clean up md changelog entries",
  or "/changelog-purge-md".
allowed-tools: Bash, Read
---

# Feature Memory Changelog Purge MD

## When to activate

- User says "purge .md entries", "remove doc-only entries", "clean up markdown entries"
- User says "my changelog has too many doc changes"
- User types `/changelog-purge-md`

## What this does

Scans all entries in `changelog.json` and deletes any where **every** stored path
is a `.md` file. Entries with a mix of `.md` and code paths are kept.

Future backfills and session hooks already skip `.md`-only changes automatically
(as of v0.5.0). This command cleans up older entries from before that fix.

## Step 1: Run purge

```bash
python plugin/hooks/fm_backfill.py --purge-md-only
```

## Step 2: Report to user

Parse output and report:
- How many entries were removed
- How many remain

Example:
> Purged 12 entries with only .md paths (of 47 total). 35 entries remain.
>
> Future backfills will skip .md-only commits automatically.
