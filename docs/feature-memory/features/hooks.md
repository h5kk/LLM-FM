---
title: Hooks
id: hooks
status: active
confidence: high
review_status: needs_review
updated: "2026-05-18"
source_count: 5
test_count: 0
---

# Hooks

## Product summary

Three lifecycle hooks that wire Feature Memory into a Claude Code session automatically: one injects feature context at the start of every session, one logs edits as they happen, and one flags missing doc updates when the session ends.

## Engineering summary

All hooks are Python scripts under `plugin/hooks/`, using stdlib only (plus `subprocess` for git in the Stop hook), compatible with Python 3.6+. Shared utilities live in `fm_common.py`: config loading (manual YAML parsing), glob matching, event ID generation, `get_feature_doc_path()` (handles flat and split layouts), `get_git_info()` (calls `git log -1` with 2s timeout, fails gracefully).

`claude_session_start.py`: archives the previous session's `events.jsonl` to `events-{session_id}.jsonl` before clearing, then injects the feature list and recent activity into agent context.

`claude_post_tool.py`: logs path-touched events to `events.jsonl`; uses `get_feature_doc_path()` in the reminder message so split-mode features get the correct path.

`claude_stop.py`: (1) captures `get_git_info()` once (15s budget allows this); (2) compiles `changelogs/changelog.json` from current JSONL events enriched with git author — compiles from events, not markdown, to stay O(events) not O(feature files); (3) updates the inline JSON data block in `changelog-viewer.html` via regex; (4) runs coverage check using `get_feature_doc_path()` so split-mode features are correctly detected as updated.

## Source map

| Path | Role | Notes |
|------|------|-------|
| `plugin/hooks/fm_common.py` | Shared utilities | Config load, glob match, event ID, `get_feature_doc_path()`, `get_git_info()` |
| `plugin/hooks/claude_session_start.py` | SessionStart hook | Injects FM context + clears event log |
| `plugin/hooks/claude_post_tool.py` | PostToolUse hook | Logs edits to events.jsonl |
| `plugin/hooks/claude_stop.py` | Stop hook | Reports source changes with no doc update |
| `plugin/hooks/hooks.json` | Hook registration | Maps event types to scripts |

## Relationships

- [[plugin-core]] — Bundled into the plugin package
- [[skills]] — Skills invoke the same config/path logic
- [[cli]] — Planned CLI will replace inline logic currently in hooks

## Changelog

### Developer

- 2026-05-18: Initial documentation created
- 2026-05-18: Added `get_feature_doc_path()` and `get_git_info()` to fm_common.py
- 2026-05-18: SessionStart now archives events before clearing; PostToolUse uses split-mode-aware paths; Stop captures git info and compiles changelog.json from JSONL events

### Product

- 2026-05-18: Hooks now track git author on every session change; changelog viewer updated automatically at session end
