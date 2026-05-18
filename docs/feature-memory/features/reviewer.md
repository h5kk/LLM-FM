---
title: Reviewer Agent
id: reviewer
status: active
confidence: medium
review_status: needs_review
updated: "2026-05-18"
source_count: 1
test_count: 0
---

# Reviewer Agent

## Product summary

A read-only agent that audits Feature Memory docs for stale claims, broken source links, missing docs, and drift between code and documentation. It produces structured findings without editing the canonical docs directly.

## Engineering summary

The reviewer is a single agent definition at `plugin/agents/feature-memory-reviewer.md`. It is a markdown file with agent instructions following the Claude Code agent spec. It checks: source path existence, claim grounding against current code, broken wikilinks, docs completeness, product/engineering audience separation, and confidence/review_status accuracy. Output is structured findings (severity, category, feature_id, evidence, recommendation) — not direct doc edits.

## Source map

| Path | Role | Notes |
|------|------|-------|
| `plugin/agents/feature-memory-reviewer.md` | Reviewer agent definition | Read-only audit agent |

## Relationships

- [[plugin-core]] — Bundled into the plugin package
- [[skills]] — Reviewer is the audit counterpart to the maintainer skill
- [[specs]] — Reviewer spec covered in architecture plan section 15

## Changelog

- 2026-05-18: Initial documentation created
