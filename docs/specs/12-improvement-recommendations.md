# Spec 12: Improvement Recommendations (v0.6.0 → v0.7.x)

**Status:** Draft
**Date:** 2026-05-18
**Scope:** Hardening pass on LLM-FM plugin at v0.6.0 — hooks, skills, viewer, data model, tests, packaging.
**Audience:** Maintainers planning the next 2–3 sprints.

---

## Executive Summary

LLM-FM is a working v0.6.0 plugin. The lifecycle hooks (`claude_session_start.py`, `claude_post_tool.py`, `claude_stop.py`) and the changelog pipeline (events.jsonl → `_compile_changelog()` → `changelog.json` → embedded viewer JSON) all function end-to-end, and the regex-tag system is in good shape after the v0.6.0 work (skip patterns, dedup, topic tags).

The most material risks today are:

1. **Quality of hook-generated entries.** Every PostToolUse-derived entry has `summary: "Modified {path}"` and is keyed by `event_id` instead of `git_hash`. After a few sessions the changelog is dominated by low-signal entries that visually drown out backfill entries, and there is no cheap way to merge them later. This is the single biggest user-visible problem.
2. **Tracking surface.** Bash-driven writes (e.g. `python scripts/foo.py`, `npm run build`, `git apply`, `sed -i`) are invisible to PostToolUse, so any agent that prefers Bash silently bypasses Feature Memory. The hook is matched on `Edit|Write|MultiEdit` only.
3. **Test coverage of the lifecycle.** `tests/` covers `fm_common.py` and `fm_backfill.py` but not the three hook entry points, the viewer regex injection, or the SessionStart archiving logic. Each is a single file with stdin JSON and filesystem side effects — perfectly testable, just not tested.
4. **Documentation hygiene.** No root `CLAUDE.md`, the README points to `/changelog-refresh` while the actual skill is `feature-memory-changelog-refresh`, and the draft `01-cli-foundation.md` spec describes a CLI that does not exist in the shipped plugin. New contributors get a misleading first read.
5. **Schema versioning.** `changelog.json` is at `schema_version: 2` but individual feature `.md` docs and the events.jsonl event shape carry no version field. Migrations between releases are ad-hoc.

Nothing in v0.6.0 is broken in a way that loses data. The recommendations below are about **trust** — making sure the changelog feels like real engineering history rather than a noisy file-touch log, making sure the hooks are robust to failure modes, and making sure the project can change shape without breaking installed users.

---

## Priority 1 — Critical (next release, ~1 sprint)

These are the things a new user notices or the things most likely to lose data.

### P1.1 — Enrich hook-generated changelog entries (`_compile_changelog` in `plugin/hooks/claude_stop.py:22`)

**Problem.** Every entry built in `claude_stop.py:_compile_changelog()` uses `summary = f"Modified {path}"` (line 70) and a per-event `event_id`. After 30 sessions you get hundreds of `Modified plugin/hooks/claude_stop.py` entries with identical summaries and no commit grouping.

**Recommendation.**

- Before iterating events in `_compile_changelog()`, call `get_git_info(project_dir)` (already done at `claude_stop.py:190`) and additionally call a new `get_uncommitted_diff_summary(project_dir)` helper that returns:
  - the staged + unstaged file list (`git status --porcelain`)
  - the most recent commit subject if HEAD has moved since session start
- **Group session events by commit.** If `git_hash` and a non-empty `git_message` exist, write **one** entry per `(git_hash, feature_id)` pair instead of one per `path_touched` event. Use `git_hash` as the primary dedup key when available, falling back to `event_id` only for uncommitted work.
- For uncommitted work, set `summary = f"WIP: {N} file(s) touched in {feature_id}"` and `review_status = "wip"` so the viewer can visually distinguish in-progress edits.
- Add a `commit_state: "committed" | "uncommitted" | "amended"` field on each entry so the `feature-memory-changelog-dedup` skill has a clean signal to merge later.

**Files to change.**
- `plugin/hooks/claude_stop.py` — extend `_compile_changelog()` to group by commit.
- `plugin/hooks/fm_common.py` — add `get_uncommitted_diff_summary()` and `group_events_by_commit()` helpers.
- `tests/test_fm_common.py` — add tests for the new helpers.

**Out of scope for P1.** Re-tagging existing low-quality entries (this is what `feature-memory-changelog-dedup` is for; document the recipe in the skill).

---

### P1.2 — Track Bash-driven file writes (PostToolUse matcher)

**Problem.** `plugin/hooks/hooks.json` matches PostToolUse on `Edit|Write|MultiEdit` only. Any agent that uses `Bash` for `python -m build`, `sed -i`, `cp`, `mv`, generated code from `npm run codegen`, etc., never produces a `path_touched` event. The changelog underreports work proportional to how Bash-heavy the agent's strategy is.

**Recommendation.** Add a second PostToolUse matcher for `Bash` that derives touched files from git rather than the tool input:

```python
# plugin/hooks/claude_post_tool_bash.py
# Triggered after every Bash call. Uses `git diff --name-only HEAD` to find
# files that changed during this tool call's window, dedup'd against the last
# Bash invocation's snapshot stored in .feature-memory/state.json.
```

**Tradeoffs.**
- **+** Catches all real edits regardless of tool.
- **+** Free: `git diff --name-only` is fast.
- **−** Misses changes in untracked files unless we also diff `git status --porcelain`.
- **−** Adds latency to every Bash call (target: < 200ms; enforce via the existing `timeout: 3000` budget).
- **−** Noisy for projects with generated artifacts (lockfiles, `dist/`, etc.). Mitigated by the existing `should_skip_path()` in `fm_common.py:373`.

**Files to add/change.**
- `plugin/hooks/claude_post_tool_bash.py` — new hook.
- `plugin/hooks/hooks.json` — register the Bash matcher with `timeout: 3000`.
- `plugin/hooks/fm_common.py` — add `snapshot_git_state(project_dir)` and `diff_git_state(before, after)` helpers; persist `before` in `.feature-memory/state.json`.

**Failure mode to handle explicitly.** If `git` is unavailable or the project is not a git repo, return immediately — never block a Bash call on FM bookkeeping.

---

### P1.3 — Fix the README skill-name mismatch and add `CLAUDE.md`

**Problem.**
- README references `/changelog-refresh` but the registered skill is `feature-memory-changelog-refresh` (see `plugin/.claude-plugin/plugin.json:38`). All five `feature-memory-changelog-*` skills use the long prefix.
- There is no `CLAUDE.md` at the project root. Per the user's global instruction, every project should have one; without it Claude has no project-specific rules at session start.

**Recommendation.**
- Update README to use the full skill names (`feature-memory-changelog-refresh`, etc.) consistently. Add a "Skill name reference" table near the top.
- Create `CLAUDE.md` at the repo root that:
  - Pins Python 3.11 (matches the existing `__pycache__/*.cpython-311.pyc` cache layout) but states the codebase must remain stdlib-only.
  - Documents the "no PyYAML, no external deps in hooks" invariant (already implicit in `fm_common.py:3-5`).
  - Documents the Windows + PowerShell support requirement (paths normalised via `replace("\\", "/")`).
  - Points contributors at `docs/specs/` as the canonical design surface and at `tests/` for the test-first expectation in P3.x.

---

### P1.4 — Harden session archiving (`claude_session_start.py:27-54`)

**Problem.** Three real bugs in one place:
1. `prev_session_id` is taken from "the last event with a session_id" — if the JSONL has events without `session_id` after the last good one, you archive under the wrong ID.
2. If `events.jsonl` is non-empty but only contains malformed lines, `prev_session_id` falls back to `datetime.now()`, which is the *new* session's wall clock — misleading.
3. The truncation (`events_path.write_text("")`) happens after a write that may have silently failed because `archived` was set before the OSError handler. Re-read: actually the code does check `if archived` (line 51), so this part is correct. Leaving the note for future review.

**Recommendation.**
- Use the **first** non-unknown `session_id` in the file, not the last. Sessions don't span events.jsonl files in normal flow — archiving by the first ID is the deterministic choice.
- If no valid `session_id` is found, archive under `unknown-{utc_timestamp}` rather than just the timestamp. Distinguishes "no events" from "events but no id".
- After successful archive, **fsync** before truncate (Windows-safe via `os.replace` on a temp file) so a crash between `write_text` and `write_text("")` cannot lose events.

**Files to change.**
- `plugin/hooks/claude_session_start.py` — refactor the archive block, add `_safe_archive(events_path, archive_path)`.
- `tests/test_session_start.py` — new test file covering: empty events, malformed events, mixed session_ids, archive failure → no truncate.

---

### P1.5 — Cap unbounded growth of `events.jsonl`

**Problem.** SessionStart truncates `events.jsonl` *only on session start*. If Stop hook crashes mid-session (or the user kills the process before Stop fires), the next session's events get appended to the old ones. Over time, in a project with no SessionStart firing (e.g. headless `claude -p` runs), this file grows without bound.

**Recommendation.**
- In `claude_post_tool.py`, before appending, check `events_path.stat().st_size`. If it exceeds 5 MB (configurable via `config.yaml:limits.events_max_mb`), rotate to `events-overflow-{timestamp}.jsonl` and start fresh. Log to `.feature-memory/errors.log` via the existing `log_error()`.
- Document this rotation in `docs/specs/02-data-model.md`.

**Files to change.**
- `plugin/hooks/claude_post_tool.py` — add rotation check before `open(events_path, "a")`.
- `plugin/hooks/fm_common.py` — add `rotate_events_if_oversized()` helper.

---

### P1.6 — Mark CLI as deprecated, remove from default surface

**Problem.** `01-cli-foundation.md` describes a CLI that is not shipped. New contributors read the specs in order and expect `fm` to exist. The `fm_init.py` script at the repo root is 916 lines and is a *script*, not a CLI, but its name suggests otherwise.

**Recommendation.**
- Add a "Status" line to `docs/specs/01-cli-foundation.md`: `**Status:** Draft / not implemented in v0.6.0. The plugin uses skills (see Spec 05) as its primary surface.`
- Rename `fm_init.py` → `fm_init_script.py` to disambiguate, or move it under `scripts/` to physically separate it from any plugin code.
- Update README to not reference any `fm` CLI commands.

---

## Priority 2 — Next Sprint (~2 sprints out)

### P2.1 — External JSON for large changelogs (viewer)

**Problem.** `changelog-viewer.html` is 1427 lines today. The JSON is embedded inline via `<script id="changelog-data">` and rewritten on every Stop hook (`claude_stop.py:_update_viewer_data`). At ~500 entries the inline JSON dominates the file, makes the HTML expensive to diff in git, and slows initial parse.

**Recommendation — threshold-based switch.**
- If `len(entries) >= 200` **or** the JSON payload is `> 100 KB`, write `docs/feature-memory/changelogs/changelog.json` (already exists) and have the viewer `fetch('./changelogs/changelog.json')` on load instead of reading the inline `<script>`.
- The viewer should attempt fetch first, fall back to inline JSON if fetch fails (works for `file://` users who open the HTML directly in a browser without a server).
- Maintain `<!-- fm-viewer-version: 10 -->` bump to trigger the existing `_check_viewer_update()` mechanism.

**Files to change.**
- `plugin/assets/changelog-viewer.html` — add fetch-with-fallback logic.
- `plugin/hooks/claude_stop.py:_update_viewer_data` — write external JSON when threshold exceeded, leave inline empty.
- `plugin/hooks/fm_common.py:_VIEWER_VERSION` → 10.

---

### P2.2 — Real `feature_title` separate from `feature_id`

**Problem.** `claude_stop.py:68` sets `feature_title = matched[0]` (the ID). The viewer therefore shows `session-hooks` instead of "Session Lifecycle Hooks". Slugs read fine in code, but humans read the viewer.

**Recommendation.**
- Add `title:` field to `config.yaml` features section:
  ```yaml
  features:
    session-hooks:
      title: "Session Lifecycle Hooks"
      globs: [...]
  ```
- Extend `load_config()` in `fm_common.py:16` to return `{feature_id: {"title": ..., "globs": [...]}}` instead of `{feature_id: [globs]}`. This is a **breaking change to the load_config return shape**; update all callers (`claude_post_tool.py:63`, `claude_stop.py:192`, `fm_backfill.py`).
- Fall back to title-casing the feature ID if `title:` is absent.
- Compatibility shim: keep the old shape behind a `load_config_legacy()` for one release, then remove.

---

### P2.3 — Per-feature `mode:` override

**Problem.** The current YAML parser only recognises a top-level `mode: small|split`. There is no way to say "the `viewer` feature is split because it has lots of pages, but everything else is small".

**Recommendation.**
- Extend `load_config()` to recognise `mode:` as a per-feature key. Default to the global mode if absent.
- `get_feature_doc_path()` in `fm_common.py:86` already does the right thing at lookup time (checks for `index.md` first), so the only change is during init/backfill, when the layout is *created*.
- Document this in `docs/specs/02-data-model.md`.

**Files to change.**
- `plugin/hooks/fm_common.py:load_config` — extend.
- `plugin/skills/feature-memory-init/SKILL.md` — document the per-feature override.
- `fm_init.py` — respect the override when scaffolding docs.

---

### P2.4 — Robust viewer auto-upgrade regex

**Problem.** `_check_viewer_update()` in `fm_common.py:396` matches the version via `<!--\s*fm-viewer-version:\s*(\d+)\s*-->`. If the template ever moves to an attribute like `<html data-fm-viewer-version="10">` or the comment style changes during a refactor, every installed viewer becomes "version 0" and gets force-overwritten — the user's customisations (rare but possible) are lost.

**Recommendation.**
- Anchor version detection on **two** markers and require both to match a known format before overwriting:
  - The HTML comment `<!-- fm-viewer-version: N -->` (current).
  - A meta tag `<meta name="fm-viewer-version" content="N">` added to the template.
- If neither is parseable, **do not overwrite** — log to `errors.log` instead.
- Stamp `<!-- fm-viewer-checksum: SHA -->` into the template at build time and refuse to overwrite a file whose checksum matches a *newer* known release than what's being installed (prevents downgrades when users mix plugin versions).

---

### P2.5 — Topic-tag fallback for air-gapped environments

**Problem.** `generate_topic_tags_batch()` in `fm_common.py:282` silently returns empty lists if `claude` CLI is unavailable. `topic_pending: true` accumulates forever. There is no surface telling the user "your tags are stuck pending".

**Recommendation.**
- Add a `--strategy {cli, keyword, none}` flag to the batch function:
  - `cli` (default) — current behaviour.
  - `keyword` — heuristic that derives 1–2 tags from the file path's directory components (e.g. `plugin/hooks/claude_stop.py` → `["session-hooks"]`). Crude but air-gap-safe.
  - `none` — skip entirely; leave `topic_pending: true`.
- Surface "N entries with `topic_pending: true`" in the SessionStart context block (`claude_session_start.py`), so the user *knows* and can run `feature-memory-changelog-refresh` interactively.
- Rate-limit `claude` CLI calls: enforce `max_parallel: 1` and a `min_interval_ms: 500` between batches inside `generate_topic_tags_batch()` — prevents hammering the CLI when batch sizes are large.

---

### P2.6 — Stop hook reviewer agent integration (opt-in)

**Problem.** The reviewer agent at `plugin/agents/feature-memory-reviewer.md` is never automatically invoked. Users have to ask for it by name. Effectively dead code from a workflow standpoint.

**Recommendation — opt-in via config.**
- Add `reviewer: { auto: false, threshold: 3 }` to `config.yaml`.
  - `auto: true` makes Stop hook invoke the reviewer agent when ≥ `threshold` features were touched.
  - `auto: false` (default) preserves current behaviour.
- The reviewer runs as a subagent — Stop hook captures its JSON findings and writes them to `.feature-memory/last-review.json` for the next SessionStart to inject.
- **Do not** block Stop on reviewer completion. Spawn as fire-and-forget so the 15s Stop budget is not consumed by an LLM call. If the reviewer hasn't returned by next SessionStart, its findings are surfaced one session late — acceptable.

**Performance.** A reviewer agent invocation costs one LLM call. Making it mandatory would add 5–30s to every Stop. Keep it opt-in.

---

### P2.7 — Fix `_infer_audience()` misclassification

**Problem.** Listed as known issue #11. The current heuristic in `_compile_changelog()` always sets `audience: "developer"` (`claude_stop.py:71`). There is no `_infer_audience()` function in the shipped code yet — the issue is more accurately "audience is hardcoded to developer".

**Recommendation.**
- Add `_infer_audience(paths, message, tags)` to `fm_common.py`:
  - Return `"product"` when paths touch `**/*.md` outside `docs/feature-memory/`, marketing assets, or templates AND no source files are touched.
  - Return `"developer"` for pure code paths.
  - Return `"both"` when both categories are touched in the same commit.
- Add to the changelog entry directly, replacing the hardcoded `"developer"`.
- Document the heuristic in `docs/specs/02-data-model.md`.

---

### P2.8 — Skill name normalisation pass

**Problem.** Five skills share the `feature-memory-changelog-*` prefix. They're verbose at the call site (`/feature-memory-changelog-purge-md`). README and the issue list show contributors expect shorter names.

**Recommendation.** Add aliases (not renames — renames break installed users). In `plugin/.claude-plugin/plugin.json`, add an `aliases:` field per skill:

```json
{
  "name": "feature-memory-changelog-refresh",
  "aliases": ["fm-refresh", "changelog-refresh"],
  "path": "skills/feature-memory-changelog-refresh/SKILL.md"
}
```

If Claude Code's plugin loader doesn't support `aliases:` today, document the actual names prominently in README and leave the rename for a major version bump.

---

## Priority 3 — Nice to Have (backlog)

### P3.1 — Hook test harness

**Problem.** Hooks read stdin JSON and write stdout JSON with filesystem side effects. They're testable but not tested.

**Recommendation.** Create `tests/conftest.py` with a `hook_runner` fixture:

```python
@pytest.fixture
def hook_runner(tmp_path, monkeypatch):
    def run(hook_module, stdin_json):
        monkeypatch.chdir(tmp_path)
        # set up minimal .feature-memory/ + docs/feature-memory/
        ...
        proc = subprocess.run(
            [sys.executable, "-c", f"from plugin.hooks import {hook_module}; {hook_module}.main()"],
            input=json.dumps(stdin_json),
            capture_output=True, text=True,
        )
        return proc.stdout, proc.stderr, list((tmp_path / ".feature-memory").iterdir())
    return run
```

Create `tests/test_post_tool.py`, `tests/test_stop.py`, `tests/test_session_start.py`. Target ≥ 70% line coverage on the three hook files.

**Hard cases to test.**
- Empty stdin / malformed JSON (hook must not raise).
- Non-existent `.feature-memory/` (hook must no-op silently).
- `file_path` outside `project_dir` (Windows-style absolute paths).
- Concurrent writes to `events.jsonl` (multiple PostToolUse firings).
- Stop hook with `session_id` filter excluding all events.

### P3.2 — Schema version on feature `.md` docs

**Problem.** Listed as known issue #17. There's no version field in feature docs' frontmatter.

**Recommendation.** Add `schema_version: 1` to the frontmatter of every feature doc. The `feature-memory` skill ensures it on every update. When the schema changes, a migration skill (`feature-memory-migrate`) bumps versions and rewrites docs.

### P3.3 — `events.jsonl` event-shape versioning

Add `event_schema_version: 1` to every event written by `claude_post_tool.py`. Lets us evolve the event shape without breaking historical files. `_compile_changelog()` checks the version and dispatches to the right parser.

### P3.4 — Replace inline regex YAML parser

`fm_common.py:load_config` is a hand-rolled YAML parser. It works for the documented config shape but fails silently on `tab indents`, anchors, or any non-trivial YAML. Document the supported subset explicitly in a top-of-file docstring and emit a `log_error()` (already exists at line 60) on every detected anomaly, not just empty result. Long-term: optionally use PyYAML when available, fall back to the stdlib parser when not. Keep the "stdlib-only" promise intact.

### P3.5 — Viewer accessibility / keyboard nav

The viewer is 1427 lines of HTML/JS. Run an accessibility audit (`chrome-devtools-mcp:a11y-debugging` skill). Likely findings: missing ARIA labels on filter chips, no keyboard shortcut for the search input, tab-order issues in the dropdown menus added in v9.

### P3.6 — Optional: doc-drift detector

When SessionStart runs, compare `git log --since="14 days ago" --name-only -- src/` against the feature doc `mtime`. If a feature has 10+ commits in the last fortnight but its doc hasn't been touched, inject a "stale doc" warning into the context block. Cheap, high signal for long-lived branches.

---

## Architecture Recommendations

### A.1 — Split `fm_common.py` along the seams

`fm_common.py` is 463 lines doing six things: config parsing, glob matching, git interaction, tag inference, viewer maintenance, error wrapping. Split into:

- `fm_common/config.py` — `load_config`, `load_skip_patterns`, `should_skip_path`.
- `fm_common/paths.py` — `match_path_to_features`, `get_feature_doc_path`.
- `fm_common/git.py` — `get_git_info` and the new `snapshot_git_state`, `get_uncommitted_diff_summary`.
- `fm_common/tags.py` — `_infer_tags`, `generate_topic_tags_batch`, `_build_topic_prompt`, `_parse_topic_tags`.
- `fm_common/viewer.py` — `_check_viewer_update`, `_find_viewer_template`, `_update_viewer_data`.
- `fm_common/errors.py` — `log_error`, `hook_error_wrapper`, `generate_event_id`.

Re-export from `fm_common/__init__.py` for backwards compatibility. Lets each test file target a narrow surface.

### A.2 — Commit-keyed changelog, event-keyed events

Today `changelog.json` is keyed by `event_id` (per-file-touch) and `events.jsonl` is also keyed by event. Two different stores, same granularity, no compression.

Target shape:
- `events.jsonl` stays event-keyed (it's the audit trail).
- `changelog.json` becomes **commit-keyed** (one entry per `(git_hash, feature_id)`), with `paths[]` aggregating all files touched.

This makes the viewer's "one row per commit" experience natural, eliminates the dedup post-step, and aligns hook-generated entries with backfill entries on the same key.

### A.3 — Make the reviewer agent the canonical "drift detector"

Repurpose the reviewer (P2.6) as the **only** component that opines on doc quality. Hooks stay mechanical (record what changed, group by commit, infer tags). Anything that requires semantic judgement — "is this doc stale", "does this claim match the code", "is this audience classification right" — gets routed to the reviewer. Single owner per concern.

### A.4 — Idempotent skills

Every skill in `plugin/skills/feature-memory-changelog-*` should be **idempotent**: running it twice should produce the same result. Document this as an invariant. Add an idempotence test per skill in P3.1's test harness.

---

## Testing Strategy

### Coverage targets per release

| Surface | v0.6.0 | v0.7.0 target | v0.8.0 target |
|---|---|---|---|
| `fm_common.py` | partial | 90% line | 95% line + branch |
| `fm_backfill.py` | partial | 80% | 90% |
| `claude_*.py` hooks | 0% | 70% | 85% |
| `changelog-viewer.html` | 0% | smoke test via Chrome DevTools MCP | a11y + perf audit |
| Skills | 0% | one happy-path test per skill | full matrix |

### Test categories

1. **Pure-function tests** (already exist in `test_fm_common.py`). Continue adding.
2. **Hook integration tests** (P3.1 harness). Spawn the hook as a subprocess with controlled stdin and tmpdir. Assert on stdout JSON, events.jsonl contents, and side-effect files.
3. **End-to-end smoke** (`tests/test_e2e.py`, new). Set up a fake project, simulate `Edit` → `Stop`, verify a complete changelog.json + viewer HTML is produced. Run on CI for every PR.
4. **Cross-platform**. Hook tests must run on Windows runners (the user's environment is Windows + PowerShell). Path normalisation bugs hide there. Add a `windows-latest` job to whatever CI gets set up.
5. **Property tests** for `match_path_to_features` and `should_skip_path`. Hypothesis-style: for any path matching glob `X/**`, `match_path_to_features` must return the feature owning glob `X/**`.

### What not to test

- The `claude` CLI subprocess. Mock it in `generate_topic_tags_batch` via a `subprocess_runner` injection.
- The actual rendering of `changelog-viewer.html` in tests — too brittle. Use Chrome DevTools MCP for occasional manual sweeps.

---

## Versioning Policy

### Semver mapping for LLM-FM

| Change kind | Bump |
|---|---|
| Breaking change to `config.yaml` shape that requires user edits | **major** |
| Breaking change to `events.jsonl` event schema that the next version can't read | **major** |
| Removal of a registered skill name | **major** |
| New skill, new hook, new optional config key | **minor** |
| `changelog.json` `schema_version` bump where a back-compat reader exists | **minor** |
| Viewer template bump (`_VIEWER_VERSION`) with no JSON shape change | **patch** |
| Tag heuristic changes that affect newly written entries | **patch** |
| Bug fix, dependency-free refactor, doc edit | **patch** |

### Concrete near-term version plan

- **v0.6.1** — patch. P1.3 (README + CLAUDE.md), P1.6 (CLI deprecation note), `_VIEWER_VERSION` bump for a minor viewer fix.
- **v0.7.0** — minor. P1.1 (commit-grouped entries — new `commit_state` field on entries, additive), P1.2 (Bash tracking — new optional hook), P1.4 + P1.5 (archiving + rotation), P2.5 (topic-tag fallback), P3.1 (hook test harness).
- **v0.8.0** — minor or major depending on whether `load_config()` return-shape change (P2.2) ships behind a flag. If P2.2 is hard-cutover, **major**.

### Migration policy

Every minor release must include a `MIGRATION.md` section in the release notes if:
- A new config key is read (document the default).
- `schema_version` bumps on any file (document the upgrade path).
- A skill is renamed or removed (provide an alias for one release).

The `feature-memory-init` skill should detect old schemas and offer to migrate on the next session.

---

## Open questions deferred to the next review

1. Should the changelog viewer become a separate package (npm or pip-installable) so it can be embedded in other projects? Today it ships only inside the plugin. (Probably no; the offline single-HTML promise is valuable.)
2. Should we publish a JSON Schema for `changelog.json` entries so external tools can validate? (Yes, after v0.7.0 lands the new shape.)
3. Is `claude` CLI the right LLM dependency for topic tags, or should we accept any OpenAI-compatible endpoint via env var? (Defer — `claude` CLI is the lowest-friction option for the audience.)
4. Should the reviewer agent's findings feed back into tag generation (so "needs_review" entries get a `review-needed` tag automatically)? (Yes, easy win after P2.6 lands.)

---

## Appendix: file-by-file change summary

| File | Priority | Change |
|---|---|---|
| `plugin/hooks/claude_post_tool.py` | P1.5 | Add `events.jsonl` rotation check |
| `plugin/hooks/claude_post_tool_bash.py` | P1.2 | **New** — Bash matcher |
| `plugin/hooks/claude_session_start.py` | P1.4 | Harden archive logic, fix session-id selection |
| `plugin/hooks/claude_stop.py` | P1.1 | Group events by commit; replace `summary = f"Modified {path}"` |
| `plugin/hooks/fm_common.py` | P1.1, P2.2, P2.4, P2.5, P2.7, A.1 | Many — split into package per A.1 |
| `plugin/hooks/hooks.json` | P1.2 | Register Bash matcher |
| `plugin/assets/changelog-viewer.html` | P2.1, P3.5 | External JSON support, a11y pass |
| `plugin/.claude-plugin/plugin.json` | P2.8 | Skill aliases |
| `plugin/agents/feature-memory-reviewer.md` | P2.6 | Opt-in Stop integration |
| `README.md` | P1.3 | Skill name reference table |
| `CLAUDE.md` | P1.3 | **New** — project instructions |
| `docs/specs/01-cli-foundation.md` | P1.6 | Mark draft/not implemented |
| `docs/specs/02-data-model.md` | P1.5, P2.3, P2.7 | Document rotation, per-feature mode, audience inference |
| `tests/test_session_start.py` | P3.1 | **New** |
| `tests/test_post_tool.py` | P3.1 | **New** |
| `tests/test_stop.py` | P3.1 | **New** |
| `tests/test_e2e.py` | P3.1 | **New** |
| `tests/conftest.py` | P3.1 | **New** — `hook_runner` fixture |
| `fm_init.py` | P1.6, P2.3 | Rename/move; respect per-feature mode |

---

*End of Spec 12.*
