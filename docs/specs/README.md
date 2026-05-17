# Feature Memory — Implementation Specifications

This directory contains actionable implementation specs for the Feature Memory system. Each spec is a self-contained work order that can be handed to a developer or agent.

## How to read these specs

The **architecture plan** (`feature-memory-architecture-plan.md`, kept locally, gitignored) defines the *what* and *why*. These specs define the *how*. They cross-reference architecture plan sections by number rather than duplicating rationale.

Each spec includes:
- Exact file paths and directory structures
- File contents or templates where applicable
- Acceptance criteria ("Key deliverables")
- Cross-references to the architecture plan

## Spec index

| # | Spec | Scope | Arch plan sections |
|---|------|-------|--------------------|
| 00 | [Project Bootstrap](00-project-bootstrap.md) | Repo structure, Python toolchain, CI skeleton, dev tooling | 4, 23 |
| 01 | [CLI Foundation](01-cli-foundation.md) | CLI framework, global options, output format, config loading | 6, 7 |
| 02 | [Data Model](02-data-model.md) | Markdown templates, frontmatter schemas, SQLite DDL, JSON schemas | 5, 12 |
| 03 | [Core Commands](03-core-commands.md) | Every `fm` subcommand implementation | 6, 13, 14, 17 |
| 04 | [Hooks and Triggers](04-hooks-and-triggers.md) | Claude Code hooks, Codex hooks, git hooks, CI triggers | 8, 19 |
| 05 | [Skills](05-skills.md) | SKILL.md for Claude + Codex, project instruction snippets | 9 |
| 06 | [Plugins](06-plugins.md) | Claude + Codex plugin packaging, MCP server, reviewer agent | 10, 11 |
| 07 | [Testing](07-testing.md) | Unit tests, fixture repos, golden tests, integration tests, evals | 18 |
| 08 | [Publishing](08-publishing.md) | PyPI, GitHub Releases, Claude/Codex marketplace, versioning | 23 |
| 09 | [Examples and Docs](09-examples-and-docs.md) | Quickstart, example repos, README, user guide | — |
| 10 | [Roadmap](10-roadmap.md) | Phased milestones, dependencies, success criteria | 23 |

## Build order

See [10-roadmap.md](10-roadmap.md) for the phased implementation plan. The short version:

```
Phase 0: Paper prototype (no code)
Phase 1: CLI MVP (specs 00, 01, 02, 03-partial)
Phase 2: LLM summaries (spec 03-remainder)
Phase 3: Skills (spec 05)
Phase 4: Hooks (spec 04)
Phase 5: Testing hardening (spec 07)
Phase 6: Plugins (spec 06)
Phase 7: Publishing (spec 08)
Phase 8: Examples and docs (spec 09)
```
