---
title: Specs
id: specs
status: active
confidence: high
review_status: needs_review
updated: "2026-05-18"
source_count: 12
test_count: 0
---

# Specs

## Product summary

Twelve implementation specification documents that define every planned aspect of Feature Memory — from CLI commands and data models to hooks, testing, publishing, and roadmap. These are the source of truth for what gets built.

## Engineering summary

Specs live under `docs/specs/` (00–11). They cover: project bootstrap (00), CLI foundation (01), data model (02), core commands (03), hooks and triggers (04), skills (05), plugins (06), testing (07), publishing (08), examples and docs (09), roadmap (10), and what's new generator (11). The architecture plan (`feature-memory-architecture-plan.md` at repo root) is the master design document referenced by the specs.

## Source map

| Path | Role | Notes |
|------|------|-------|
| `docs/specs/00-project-bootstrap.md` | Bootstrap spec | Repo structure, Python toolchain, CI |
| `docs/specs/01-cli-foundation.md` | CLI foundation spec | CLI framework, config loading |
| `docs/specs/02-data-model.md` | Data model spec | Markdown templates, schemas, SQLite DDL |
| `docs/specs/03-core-commands.md` | Core commands spec | Every `fm` subcommand |
| `docs/specs/04-hooks-and-triggers.md` | Hooks spec | Claude/git/CI hooks |
| `docs/specs/05-skills.md` | Skills spec | SKILL.md for Claude + Codex |
| `docs/specs/06-plugins.md` | Plugins spec | Claude/Codex plugin packaging |
| `docs/specs/07-testing.md` | Testing spec | Unit tests, fixtures, golden tests |
| `docs/specs/08-publishing.md` | Publishing spec | PyPI, GitHub Releases |
| `docs/specs/09-examples-and-docs.md` | Examples spec | Quickstart, user guide |
| `docs/specs/10-roadmap.md` | Roadmap spec | Phased milestones |
| `docs/specs/11-whats-new.md` | What's new spec | Release notes generation |
| `feature-memory-architecture-plan.md` | Master architecture plan | Full design with 29 sections |

## Relationships

- [[plugin-core]] — Specs define the plugin packaging
- [[cli]] — Core commands spec defines the `fm` CLI
- [[hooks]] — Hooks spec covers all trigger types
- [[skills]] — Skills spec covers SKILL.md design

## Changelog

- 2026-05-18: Initial documentation created
