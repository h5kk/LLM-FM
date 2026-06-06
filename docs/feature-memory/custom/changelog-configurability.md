---
type: changelog_custom
doc_type: wiki
feature_id: hooks
audience: both
verbosity: normal
tagging: true
tags: [configurability, custom-docs, metrics]
title: "Changelog configurability, custom docs & metrics (v0.8.0)"
---

# What's new in v0.8.0

Feature Memory now lets you **shape the changelog**, add your **own docs**, and
see **metrics** — all offline, all in the single-file viewer.

## 1. Configurability

Add an optional `changelog:` block to `.feature-memory/config.yaml`:

- `verbosity`: `terse` | `normal` | `detailed` — controls topic-tag count,
  header tag chips, and the Dev Sync catch-up default.
- `summary_rule`: a free-text steering instruction passed to topic tagging
  (e.g. *prefer business-domain names*).
- `tagging`: a master on/off switch (overrides `tagging.strategy`).
- `highlight_tags`: which tags raise the Dev Sync "Watch out" callout.

## 2. Custom changelog & wiki docs

Drop markdown files in `docs/feature-memory/custom/`:

- `doc_type: entry` → a dated item in the **Timeline** with a `CUSTOM` badge.
- `doc_type: wiki` → a reference page in the **Wiki** tab (this page!).

These are re-scanned fresh every Stop — editing updates, deleting removes —
and they **never** touch `changelog.json`. Use the
`/feature-memory-changelog-custom` skill to author them.

## 3. Metrics

The **Metrics** tab shows activity over time, by feature, by change kind, and
top contributors — rendered as zero-dependency inline bars. Enable per-commit
code churn with:

```
python plugin/hooks/fm_backfill.py --code-churn
```

or `changelog.metrics.code_churn: true` (backfill-only, so the Stop hook stays
within its time budget).
