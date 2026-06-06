---
description: >
  Authors a custom changelog entry or wiki/reference doc that surfaces in the
  changelog viewer (Timeline or Wiki tab). Use when the user says "add a custom
  changelog entry", "add a wiki doc", "write release notes", "document this in
  the changelog manually", or "/changelog-custom".
allowed-tools: Bash, Read, Write, Edit, Glob
---

# Feature Memory Custom Doc

## When to activate

- User says "add a custom changelog entry", "add release notes", "add a wiki
  page", "document X in the changelog viewer", "write a custom changelog doc"
- User types `/changelog-custom`

## What this does

Creates a markdown file under the configured custom-docs directory (default
`docs/feature-memory/custom/`). On the next Stop hook these files are scanned
fresh and embedded into the viewer's **separate custom-docs data slot**:

- `doc_type: entry` → a manual entry in the **Timeline** (with a `custom` badge)
- `doc_type: wiki` → a long-form page in the **Wiki** tab

Editing a file updates its doc; deleting a file removes it on the next compile
(true re-scan — these never pollute `changelog.json`).

## Step 1: Gather inputs

Ask the user (infer sensible defaults; only ask what's ambiguous):

- **doc_type**: `entry` (dated changelog item) or `wiki` (reference page)
- **title**: short title
- **feature_id** / subsystem (optional — must match a feature in
  `.feature-memory/config.yaml` if given)
- **audience**: `product` | `developer` | `both` (default `both`)
- **verbosity**: `terse` | `normal` | `detailed` (default = project config)
- **tagging**: whether to keep explicit tags (`true`/`false`; auto topic-tagging
  is not run on custom docs — list any tags explicitly)
- **tags**: optional explicit tag list
- **body**: the markdown content

## Step 2: Resolve the custom-docs dir

```bash
python plugin/hooks/fm_custom.py --list
```

This prints the configured dir and existing docs. If the dir does not exist,
create it. The dir comes from `changelog.custom_docs.dir` in
`.feature-memory/config.yaml` (default `docs/feature-memory/custom/`).

## Step 3: Write the file

Create `docs/feature-memory/custom/<kebab-title>.md`:

```markdown
---
type: changelog_custom
doc_type: entry            # entry | wiki
date: YYYY-MM-DD
feature_id: hooks          # optional
audience: both             # product | developer | both
verbosity: detailed        # optional override of project verbosity
tagging: true              # keep explicit tags?
tags: [release, manual]
title: "v0.8.0 release notes"
---

Markdown body. Headings, lists, **bold**, `code`, fenced code blocks, and
links are rendered (escaped/sanitized) in the viewer.
```

Rules:
- Frontmatter keys are optional except a sensible `title`. Missing `doc_type`
  defaults to `wiki`; missing `date` defaults to today.
- Do NOT put a literal `</script>` worry on the user — the pipeline escapes it
  safely. Write natural markdown.
- Keep `wiki` docs reference-style (no date needed); keep `entry` docs dated.

## Step 4: Validate

```bash
python plugin/hooks/fm_custom.py --validate
```

Fix any reported issues (invalid `doc_type`/`audience`/`verbosity`/`date`,
empty body, duplicate slug). Re-run until it reports "All custom docs valid."

## Step 5: Refresh the viewer

Trigger a recompile so the slot is rebuilt and embedded:

```bash
python plugin/hooks/fm_backfill.py --drain-pending
```

(Any Stop hook also rebuilds the slot.) Then tell the user where it appears:

> Added a custom **{doc_type}** "{title}". It will show in the
> {Timeline|Wiki} tab of `docs/feature-memory/changelog-viewer.html`.
> Edit or delete the file to update/remove it — it never touches
> `changelog.json`.
