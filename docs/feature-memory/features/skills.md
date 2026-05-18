---
title: Skills
id: skills
status: active
confidence: high
review_status: needs_review
updated: "2026-05-18"
source_count: 2
test_count: 0
---

# Skills

## Product summary

Two skills that teach Claude how to set up and maintain Feature Memory docs. The init skill walks you through first-time setup (scanning the codebase, proposing features, creating pages). The maintainer skill runs after code changes to keep docs current.

## Engineering summary

Both skills are SKILL.md files with YAML frontmatter (`description`, `allowed-tools`) and structured instructions. `plugin/skills/feature-memory-init/SKILL.md` covers a 6-step init flow: scaffold directories, scan project, propose features (with user confirmation gate), create feature pages, update config/index/logs, and report. `plugin/skills/feature-memory/SKILL.md` covers an 8-step maintain flow: identify changed files, check config mapping, read affected pages, verify claims against source, update summaries/source map/changelog, update index/recent, and summarize. Both use `allowed-tools: Bash, Read, Grep, Glob, Edit, Write`.

## Source map

| Path | Role | Notes |
|------|------|-------|
| `plugin/skills/feature-memory-init/SKILL.md` | Init skill | One-time setup flow |
| `plugin/skills/feature-memory/SKILL.md` | Maintainer skill | Ongoing update workflow |

## Relationships

- [[plugin-core]] — Bundled into the plugin package
- [[hooks]] — Skills share config format with hooks
- [[reviewer]] — Reviewer agent is the read-only counterpart to maintainer skill
- [[specs]] — Skill design spec in docs/specs/05-skills.md

## Changelog

- 2026-05-18: Initial documentation created
