---
description: >
  Clears all entries from changelog.json without touching any feature .md docs.
  Use when the user says "clear changelog", "reset changelog viewer", "wipe changelog
  entries", "start fresh changelog", or "/changelog-clear".
allowed-tools: Bash, Read
---

# Feature Memory Changelog Clear

## When to activate

- User says "clear changelog", "clear changelog entries", "reset changelog viewer"
- User says "wipe all changelog entries", "start fresh", "empty the changelog"
- User types `/changelog-clear`

## What this does

Resets `changelog.json` to zero entries. Feature documentation (`.md` files) is
**not** touched. Changelog can be repopulated at any time by running backfill.

## Pre-check

Confirm the user understands this is reversible (backfill can repopulate). If the
user is unsure, suggest running `/backfill` after to restore entries.

## Step 1: Clear entries

```bash
python plugin/hooks/fm_backfill.py --clear
```

## Step 2: Report to user

> Changelog viewer cleared — 0 entries remain.
>
> Your feature docs (.md files) are untouched. To repopulate from git history, run:
> ```
> python plugin/hooks/fm_backfill.py --all
> ```
> Or say "backfill changelog" to do this through the skill.
