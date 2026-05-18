---
type: changelog
updated: "2026-05-18"
---

# Feature Memory Changelog

## 2026-05-18 (v0.4.0)

- **plugin-core**: Version bumped to 0.4.0; plugin.json now registers changelog-refresh skill
- **hooks**: `fm_common.py` — added `_infer_tags()` (closed 20-tag vocabulary, 4 categories: Impact/Quality/Process/Tech, capped at 5 with priority ordering); added `_check_viewer_update()` for automatic viewer self-upgrade
- **hooks**: `claude_stop.py` — path_touched events now include auto-inferred tags; viewer auto-upgrades on session end
- **hooks**: `claude_session_start.py` — calls `_check_viewer_update()` so viewer upgrades on session start
- **hooks**: `fm_backfill.py` — all backfill entries tagged at generation time; `--retag` flag added to re-infer and replace tags on all existing entries
- **changelog-viewer**: v4 — tag chips with category colors, tag filter panel (AND-across/OR-within), toolbar (Expand All, Copy JSON, Copy Markdown, Export CSV), consistent author color coding, feature title shown in entry rows
- **skills**: `changelog-refresh` skill added (`/changelog-refresh` command)
- **tests**: 77 tests total (up from 50); 27 new `_infer_tags` tests covering all tag categories, priority ordering, cap behavior, and edge cases

## 2026-05-18

- **system**: Feature Memory initialized for LLM-FM project
- **plugin-core**: Initial documentation created; version bumped to 0.2.0
- **hooks**: Initial documentation created; fm_common extended with get_feature_doc_path() and get_git_info(); SessionStart archives events before clearing; PostToolUse uses split-mode-aware paths; Stop captures git info, compiles changelog.json, uses get_feature_doc_path() for coverage check
- **skills**: Initial documentation created; init skill updated for split mode, Mermaid diagram generation, changelog viewer init; maintainer skill updated for split mode routing, audience-tagged changelog entries, conditional diagram regen
- **reviewer**: Initial documentation created
- **specs**: Initial documentation created
- **cli**: Initial documentation created (draft — planned feature)
- **changelog-viewer**: HTML viewer created at docs/feature-memory/changelog-viewer.html and plugin/assets/changelog-viewer.html (template)
