---
title: Plugin Core
id: plugin-core
status: active
confidence: high
review_status: needs_review
updated: "2026-05-18"
source_count: 1
test_count: 0
---

# Plugin Core

## Product summary

The installable Claude Code plugin that users add to their projects with `claude plugin install feature-memory@h5kk-plugins`. It bundles all hooks, skills, and agents into a single distributable package.

## Engineering summary

The plugin manifest lives at `plugin/.claude-plugin/plugin.json`. It declares name (`feature-memory`), version (`0.1.0`), description, author (`Hanny Noueilaty / h5kk`), homepage, and license (`MIT`). The plugin directory structure follows the Claude Code plugin spec: hooks under `plugin/hooks/`, skills under `plugin/skills/`, and agents under `plugin/agents/`.

## Source map

| Path | Role | Notes |
|------|------|-------|
| `plugin/.claude-plugin/plugin.json` | Plugin manifest | Name, version, author, keywords |
| `plugin/hooks/` | Hook scripts directory | Python scripts + hooks.json |
| `plugin/skills/` | Skill definitions | Init + maintainer SKILL.md |
| `plugin/agents/` | Agent definitions | Reviewer agent markdown |

## Relationships

- [[hooks]] — Hook scripts bundled into this plugin
- [[skills]] — Skills bundled into this plugin
- [[reviewer]] — Reviewer agent bundled into this plugin
- [[specs]] — Architecture and plugin spec in docs/specs/06-plugins.md

## Changelog

- 2026-05-18: Initial documentation created
