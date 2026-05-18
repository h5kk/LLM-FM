---
title: CLI
id: cli
status: draft
confidence: low
review_status: needs_review
updated: "2026-05-18"
source_count: 1
test_count: 0
---

# CLI

## Product summary

A planned `fm` command-line tool that lets developers run Feature Memory operations without an AI agent: `fm init`, `fm scan`, `fm status`, `fm ingest`, `fm lint`, `fm review`, and `fm report`. Phase 1 of the roadmap.

## Engineering summary

Currently only `fm_init.py` exists at repo root as a prototype (replaced in practice by the init skill per commit `73cd33c`). The planned CLI is a Python package (`pip install feature-memory`) with subcommands mapped to the architecture plan's section 6. The CLI is intended to be the layer that hooks and skills call, so logic is not duplicated. Current hook logic in `fm_common.py` is the seed of what becomes CLI modules.

## Source map

| Path | Role | Notes |
|------|------|-------|
| `fm_init.py` | Init prototype | Superseded by init skill; kept for reference |
| `docs/specs/01-cli-foundation.md` | CLI foundation spec | Framework and config loading design |
| `docs/specs/03-core-commands.md` | Commands spec | All planned subcommands |

## Relationships

- [[hooks]] — Hooks will delegate to CLI once built
- [[specs]] — CLI design defined in specs 01 and 03
- [[plugin-core]] — CLI will be bundled as `bin/fm` in plugin

## Changelog

- 2026-05-18: Initial documentation created (draft — CLI not yet implemented)
