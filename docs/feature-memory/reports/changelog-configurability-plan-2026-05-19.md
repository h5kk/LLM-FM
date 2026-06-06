# Changelog Configurability, Custom Docs & Metrics — Design & Implementation Plan

**Date:** 2026-05-19
**Author:** h5k (via Claude)
**Status:** council-reviewed — corrections applied below (see §12)
**Target version:** 0.8.0 (minor: new skill + new hook module + additive config/schema fields)

---

## 1. Goals (verbatim from request)

1. **Configurability for changelogs** — let users specify verbosity, a custom
   rule/prompt, and anything else useful.
2. **Custom changelog / wiki docs** — let plugin users author their own
   changelog entries and wiki/reference docs that surface in the changelog
   viewer HTML, each configurable with verbosity, whether tagging is enabled,
   what feature/subsystem it belongs to, etc.
3. **Metrics** — when applicable, integrate metrics into the changelog (a
   Metrics tab/doc with tables and basic charts: churn, velocity, kind/feature
   distribution).

## 2. Constraints (from CLAUDE.md + invariants)

- Hooks stay **stdlib-only** (no PyYAML/requests). Nested config parsed by a
  hand-written line parser like the existing `load_tag_strategy()` /
  `load_skip_patterns()`.
- Hooks **never raise** — all new code wrapped/guarded, errors → `errors.log`.
- Windows path normalization (`.replace("\\","/")`).
- Viewer auto-upgrade must preserve inline JSON; **bump `_VIEWER_VERSION` 10 → 11**.
- `changelog.json` `schema_version` stays **2** — all new fields are *additive
  and optional*, so no migration is required (CLAUDE.md: "additive changelog
  schema field" = minor, not major). A `MIGRATION.md` is **not** needed; a
  `docs/specs/02-data-model.md` schema-doc update **is**.
- Skills are SKILL.md only. The new custom-docs tool ships **both** a Python
  module (`fm_custom.py`, importable + CLI) **and** a SKILL.md wrapper so it is
  slash-command invokable (`/feature-memory-changelog-custom`), per CLAUDE.md.
- The viewer must remain a single self-contained offline file — **no external
  JS/CSS/CDN**. Charts are hand-rendered inline SVG.

## 3. Configuration design

New optional `changelog:` block in `.feature-memory/config.yaml`. All keys
optional; omission = current behavior (100% backward compatible).

```yaml
changelog:
  verbosity: normal          # terse | normal | detailed
  summary_rule: ""           # free-text instruction appended to the tagging/summary LLM prompt
  tagging: true              # master on/off; false overrides tagging.strategy → none
  highlight_tags:            # tags that drive Dev Sync "Watch out" highlights
    - breaking-change
    - api-change
    - security
    - schema-change
    - data-migration
  metrics:
    enabled: true            # compute metrics block + show Metrics tab
    code_churn: false        # extra `git show --numstat` per commit for +/- lines
  custom_docs:
    enabled: true            # ingest custom/wiki docs + show Wiki tab
    dir: docs/feature-memory/custom
```

### 3.1 `verbosity`
Controls what the hooks **store** and what the viewer **emphasizes**:

| level | hook behavior | viewer behavior |
|-------|---------------|-----------------|
| `terse` | topic-tag cap 1; no `git_body`; summary first line, ≤80 chars | hide tag chips in header; collapse Dev Sync catch-up by default |
| `normal` | current behavior (cap 3 topic tags) | current |
| `detailed` | topic-tag cap 5; include `git_body` (commit body); full summary | show all tags; expand catch-up; show churn column when present |

The effective verbosity is echoed into the compiled JSON as
`data.config.verbosity` so the offline viewer can adapt without re-reading YAML.

### 3.2 `summary_rule`
Free-text user instruction. Appended as an extra rule line inside
`_build_topic_prompt()` (e.g. *"Prefer business-domain names: billing, auth,
onboarding"*). Also surfaced to the maintainer skill as guidance text. Bounded
to 500 chars and newline-stripped to keep the `claude -p` prompt safe.

### 3.3 `tagging` master switch
`changelog.tagging: false` ⇒ `generate_topic_tags_batch` treated as
`strategy='none'` regardless of `tagging.strategy`. Keeps the existing
`tagging.strategy: cli|keyword|none` for *how*; the new bool is a simple kill
switch usable by non-technical users.

### 3.4 Parsing
Add `load_changelog_config(project_dir) -> dict` to `fm_common.py`:
- Hand parser for the `changelog:` block (2-space indent, nested `metrics:`/
  `custom_docs:` one level deeper, `highlight_tags:` list).
- Returns a fully-defaulted dict; never raises; logs a parse warning only.
- Unit-tested against malformed/missing/partial YAML.

## 4. Custom changelog / wiki docs

### 4.1 Authoring format
Markdown files in `changelog.custom_docs.dir` (default
`docs/feature-memory/custom/`) with stdlib-parsable frontmatter:

```markdown
---
type: changelog_custom
doc_type: entry          # entry | wiki
date: 2026-05-19
feature_id: hooks        # which feature/subsystem (optional)
audience: both           # product | developer | both
tagging: true            # auto-tag this doc?
verbosity: detailed      # per-doc override of global verbosity
tags: [release, manual]  # explicit tags (always kept)
title: "v0.8.0 release notes"
---

Markdown body. Rendered in the viewer (headings, lists, code, links, bold).
```

- `doc_type: entry` → appears in the **timeline** as a normal changelog entry
  with a `custom` badge and `source: "custom"`.
- `doc_type: wiki` → appears in a new **Wiki** tab (reference/long-form docs),
  not the dated timeline.

### 4.2 `fm_custom.py` (new, importable + CLI)
Pure-stdlib module:
- `parse_frontmatter(text) -> (meta: dict, body: str)` — minimal `---` block
  parser (key: value, `[a, b]` inline lists, quoted strings). No PyYAML.
- `load_custom_docs(project_dir, changelog_cfg) -> list[entry-dict]` —
  globs `*.md` under the configured dir, converts each to a changelog-entry
  shaped dict: `source:"custom"`, `doc_type`, `body_md`, `audience`,
  `feature_id`, `tags`, `topic_pending` (honoring per-doc `tagging`),
  deterministic `event_id` = `custom-<slug(path)>`.
- CLI: `python plugin/hooks/fm_custom.py --list | --validate [--json]`.
- Errors are collected and reported, never raised into the hook.

### 4.3 Skill wrapper (slash-invokable)
New `plugin/skills/feature-memory-changelog-custom/SKILL.md`
(`/feature-memory-changelog-custom`): guides the agent to scaffold the
`custom/` dir and write a well-formed entry/wiki file (prompts for doc_type,
feature, audience, verbosity, tagging), then runs `fm_custom.py --validate` and
triggers a changelog recompile.

### 4.4 Ingestion — REVISED per council (blocker ii)
Custom docs are **NOT** merged into `_compile_changelog`'s `existing` dict.
That dict is reloaded from the persisted `changelog.json` every Stop and is
**append-only by design** (WIP/commit entries must outlive their JSONL events;
there is no delete path) — a re-scan/delete merge there would orphan deleted
custom files forever.

Instead, custom docs live in a **separate parallel data slot**:
- A second inline block `<script id="custom-docs-data" type="application/json">`
  in the viewer, rebuilt **fresh on every Stop** by `fm_custom.load_custom_docs()`
  (true re-scan/delete semantics; a removed file simply disappears next compile).
- `_compile_changelog` / `changelog.json` stay **completely untouched**.
- The same `</`→`<\/` JSON-in-HTML escape (§12 blocker i) is applied to this
  block's writer.
- Failure is isolated: a bad custom dir never affects timeline compilation.

## 5. Metrics

### 5.1 Per-entry churn (optional, gated)
When `changelog.metrics.code_churn: true`, the **backfill** path (30s budget;
*not* the 3s PostToolUse, and only opportunistically in the 15s Stop within a
hard commit-count cap) runs `git show --numstat --format= <hash>` and attaches:

```json
"metrics": { "files_changed": 4, "insertions": 120, "deletions": 33 }
```

Hard caps: skip if > 80 commits in the batch; 1 git call per unique hash;
total git-time budget guarded; any failure → omit `metrics`, never crash.

### 5.2 Top-level metrics summary
Compiler writes an optional `data.metrics` block (counts by kind, by feature,
by author, by date, totals) so the viewer has an authoritative summary even if
entries are filtered. Viewer also recomputes live from the filtered set.

### 5.3 Metrics tab in viewer (inline SVG, zero deps)
New **Metrics** view (top-level view switch: `Timeline | Wiki | Metrics`,
independent of the existing audience tabs which stay for Timeline):
- **Activity over time** — area/line chart, entries per date.
- **By feature** — horizontal bar chart (commit count; churn bar if available).
- **By kind** — bar chart (new-feature/bug-fix/behavior-change/refactor).
- **Top contributors** — table (author, commits, +ins/−del when present).
- **Tag distribution** — top tags bar list.
All hand-rendered SVG/HTML, theme-aware, `<title>`/aria labels + a data
`<table>` fallback for accessibility. Respects the active search/tag filter.

## 6. Schema & data flow (additive, schema_version stays 2)

New optional fields on entries: `doc_type`, `body_md`, `metrics`,
`source:"custom"`. New optional top-level: `config` (echo of effective
verbosity + feature flags), `metrics` (summary). Old viewers ignore unknown
fields; new viewer degrades gracefully when they are absent.

```
config.yaml ──load_changelog_config()──┐
git/events ──► claude_stop / fm_backfill├─► compile ─► changelog.json ─► viewer
custom/*.md ──load_custom_docs()────────┘            (config + metrics echo)
```

## 7. Files changed

**New**
- `plugin/hooks/fm_custom.py` — custom-doc parser/loader + CLI
- `plugin/skills/feature-memory-changelog-custom/SKILL.md` — slash wrapper
- `tests/test_changelog_config.py`, `tests/test_fm_custom.py`,
  `tests/test_metrics.py`
- `docs/feature-memory/custom/.gitkeep` + one example wiki doc

**Modified**
- `plugin/hooks/fm_common.py` — `load_changelog_config()`, verbosity +
  `summary_rule` in topic prompt, `tagging` master switch, `_VIEWER_VERSION`→11,
  config-echo helper
- `plugin/hooks/claude_stop.py` — ingest custom docs, optional churn, embed
  `config`/`metrics`
- `plugin/hooks/fm_backfill.py` — same; `--code-churn` flag honoring config
- `plugin/assets/changelog-viewer.html` — Wiki tab, Metrics tab + SVG charts,
  custom badges, verbosity respect, mini markdown renderer; version 10→11
- `plugin/skills/feature-memory-init/SKILL.md` — scaffold `custom/` + new
  `changelog:` config block + example
- `plugin/skills/feature-memory/SKILL.md` — config-aware guidance, custom-doc note
- `.feature-memory/config.yaml` — add `changelog:` block (dogfood)
- `plugin/.claude-plugin/plugin.json` + both `marketplace.json` — 0.7.1→0.8.0
- `README.md`, `docs/specs/02-data-model.md`, `docs/specs/05-skills.md`,
  `docs/specs/11-whats-new.md` — document features

## 8. Implementation order

1. `fm_common.load_changelog_config()` + tests
2. verbosity/`summary_rule`/tagging wired into `_build_topic_prompt` +
   `generate_topic_tags_batch` + tests
3. `fm_custom.py` + tests + SKILL.md
4. `claude_stop.py` / `fm_backfill.py` ingestion + churn + config echo + tests
5. viewer v11: Wiki + Metrics tabs, charts, mini-markdown, verbosity; viewer
   regression test
6. init/maintainer skills, config dogfood, version bumps
7. README + specs
8. Full `pytest`; **live test in `LLM-FM-TEST`** (separate git repo) —
   run hooks/backfill end to end, author a custom + wiki doc, open the viewer,
   verify Wiki/Metrics tabs, churn, verbosity, offline `file://`

## 9. Test plan

- `load_changelog_config`: missing/partial/malformed/nested/list values, defaults
- verbosity: terse caps tags & strips body; detailed includes body; normal unchanged
- `tagging:false` ⇒ no topic tags even with strategy `cli`
- `summary_rule` injected into prompt (assert substring; subprocess mocked)
- `fm_custom`: frontmatter edge cases, entry vs wiki, per-doc tagging/verbosity,
  idempotent event_id, delete-then-recompile reconciliation, bad file skipped
- churn: numstat parse incl. binary `-`/`-`, cap enforced, git failure safe
- viewer regression: v11 markers present, JSON re-inject preserved across
  upgrade, Wiki/Metrics DOM nodes exist, no external URLs
- existing suites still green; coverage targets held
- **Live (LLM-FM-TEST):** init → edit → commit → Stop hook → backfill →
  custom+wiki docs → open `changelog-viewer.html` from `file://` and confirm
  all tabs/charts render with no console errors

## 10. Risks & mitigations

| Risk | Mitigation |
|------|------------|
| Extra `git show` blows Stop 15s budget | churn default **off**; commit-count cap; backfill is the primary path |
| Hand YAML parser misreads nested block | dedicated parser + heavy unit tests; safe defaults on any parse failure |
| Viewer bloat / inline-JSON size | charts computed client-side; no per-entry payload growth except optional small `metrics` obj; existing >500KB warning still applies |
| Custom-doc frontmatter injection into LLM prompt | sanitize/escape, length-cap `summary_rule` & custom titles |
| Markdown renderer XSS in viewer | escape-first renderer, whitelist of inline constructs only, no raw HTML passthrough |
| Schema drift confusion | additive-only; document in 02-data-model; viewer tolerates missing fields |

## 12. Council decisions applied (2026-05-19)

Multi-model council (Claude stage-1, peer-ranked ship-ready). Verdict: proceed
after corrections. Two non-negotiable blockers, three must-fix items.

**Resolved open questions**
1. **Schema:** keep `schema_version: 2`, no MIGRATION.md (additive only; viewer
   reads defensively, never checks schema_version). Custom-doc bodies must NOT
   go in `entries[]`.
2. **Reconciliation:** REJECT re-scan-into-`_compile_changelog`. Use a separate
   `<script id="custom-docs-data">` slot rebuilt fresh each Stop. (§4.4 revised.)
3. **View switch:** confirmed top-level segmented control `Timeline | Wiki |
   Metrics` via a `currentView` var; audience row stays Timeline-only.
4. **Churn:** backfill-only. Never in Stop (15s budget already pressured by
   `get_git_info` + `generate_topic_tags_batch` CLI sleeps/timeouts). Viewer
   degrades gracefully when `metrics` absent.
5. **Charts:** confirmed hand-rolled inline SVG, zero-dep, ≤4 types; every SVG
   `<text>`/`<title>` label through `escHtml`.

**Blockers (must fix before/with code)**
- **(i)** `json.dumps` does not escape `/`; a custom body containing literal
  `</script>` truncates the inline data block and corrupts the regex
  re-injection in `_check_viewer_update` (fm_common ~610) and
  `_update_viewer_data` (claude_stop ~256) → permanent data loss. **Fix first:**
  shared `fm_common` helper doing `.replace("</", "<\\/")` applied at *every*
  inline-JSON writer (existing changelog-data block included — latent bug in
  shipped code). Grep `tests/` for pinned inline-JSON byte strings before
  patching. Add round-trip regression test with a `</script>` payload.
- **(ii)** Custom docs as separate slot, not `_compile_changelog` merge (§4.4).

**Must-fix**
- `load_changelog_config` is an **independent 4th parser** with a `current_sub`
  state for 4-space `metrics:`/`custom_docs:` children; reject tabs→errors.log;
  strip whitespace-preceded `#` comments (cf. `load_tag_strategy` L109); block
  lists only; every path try/except → silent defaults; never raises.
- Wiki markdown renderer: escape-first, tag-whitelist, `href` sanitize
  (`https?:`/`mailto:`/relative only; reject `javascript:`/`data:`/`vbscript:`;
  add `rel="noopener noreferrer"`), code fences stay escaped & never re-parsed,
  no raw HTML passthrough. Ship XSS test corpus:
  `<img src=x onerror=alert(1)>`, `[x](javascript:alert(1))`,
  ` ```<script>alert(1)</script>``` `, `<svg onload=alert(1)>`,
  `[a](data:text/html,...)`, and a body with literal `</script>`.
- `_VIEWER_VERSION` 10→11 once (covers all new tabs).

**Implementation order (council-prioritised):** escape helper+test → custom
slot via fm_custom → 4th parser → backfill-only churn → markdown renderer+XSS
corpus → segmented control → inline-SVG charts → version/docs → full+live test.

---

## 11. Open questions for council (original — now resolved in §12)

1. Schema: confirm additive fields keep `schema_version: 2` (no MIGRATION.md) —
   or bump to 3 defensively?
2. Custom-doc reconciliation: re-scan/replace (a deleted file drops its entry)
   vs append-only like hook entries — chosen re-scan; confirm.
3. View switch UX: top-level `Timeline | Wiki | Metrics` segmented control vs
   adding Wiki/Metrics as extra audience-row tabs — chosen segmented control.
4. Should churn ever run inside the Stop hook (capped) or backfill-only?
5. Metrics charts: inline SVG hand-rolled (chosen, zero-dep) — acceptable vs
   risk of reinventing a charting lib? Scope to ≤4 simple chart types.
