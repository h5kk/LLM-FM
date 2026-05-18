---
type: changelog
updated: "2026-05-18"
---

# Feature Memory Changelog

## 2026-05-18

- **system**: Feature Memory initialized for LLM-FM project
- **plugin-core**: Initial documentation created; version bumped to 0.2.0
- **hooks**: Initial documentation created; fm_common extended with get_feature_doc_path() and get_git_info(); SessionStart archives events before clearing; PostToolUse uses split-mode-aware paths; Stop captures git info, compiles changelog.json, uses get_feature_doc_path() for coverage check
- **skills**: Initial documentation created; init skill updated for split mode, Mermaid diagram generation, changelog viewer init; maintainer skill updated for split mode routing, audience-tagged changelog entries, conditional diagram regen
- **reviewer**: Initial documentation created
- **specs**: Initial documentation created
- **cli**: Initial documentation created (draft — planned feature)
- **changelog-viewer**: HTML viewer created at docs/feature-memory/changelog-viewer.html and plugin/assets/changelog-viewer.html (template)
