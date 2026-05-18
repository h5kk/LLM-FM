# Feature Memory (LLM-FM)

A documentation compiler for software repos. Maintains feature-level memory so AI coding agents don't rediscover the project from scratch every session.

## The Problem

Every project has two codebases. The real one (files, tests, routes, configs). And the remembered one (what it does, why, which files matter, what's dead). The second one is more useful and decays fastest.

Feature Memory makes it explicit: a structured layer of feature documentation that lives alongside your code, stays current through hooks and skills, and gives agents immediate context when they start a session.

![The Evolution — from Traditional RAG to LLM Wiki to Feature Memory](images/v2_TheEvolution.png)

## Install (Claude Code Plugin)

```bash
claude plugin marketplace add h5kk/LLM-FM
claude plugin install feature-memory@h5kk-plugins
```

Then open a Claude Code session in your project and say:

> Initialize feature memory

The agent scaffolds the docs structure, scans your codebase, proposes features, and creates initial feature pages. No scripts to run — the plugin handles everything through skills.

## How It Works

```
docs/feature-memory/
  index.md              # feature table: title, status, one-liner
  recent.md             # last 5 days of activity
  changelog.md          # append-only global log
  features/
    auth.md             # one page per feature
    billing.md

.feature-memory/
  config.yaml           # globs, route patterns, policies
  events.jsonl          # hook event log
```

Three hooks wire into Claude Code's lifecycle:

| Hook | When | What it does |
|------|------|--------------|
| **SessionStart** | Agent opens a session | Injects feature list, recent activity, and FM rules into context |
| **PostToolUse** | After every Edit/Write | Logs the edit, reminds agent which feature docs to update |
| **Stop** | Session ends | Reports features with source changes but no doc updates |

A companion **skill** (`feature-memory`) gives the agent a structured workflow for reading and updating feature pages, changelogs, and the index.

![The Pipeline — two agent roles consume and maintain compiled docs](images/v2_ThePipeline.png)

## Quick Start

1. Install the plugin (see above)
2. Open Claude Code in your project
3. Say **"initialize feature memory"** — the init skill walks you through setup
4. Say **"update feature memory"** after making code changes — the maintainer skill keeps docs current

### What the plugin includes

| Component | Purpose |
|-----------|---------|
| **Init skill** | One-time setup: scaffolds docs, scans codebase, creates feature pages |
| **Maintainer skill** | Ongoing: updates feature pages, changelogs, source maps after code changes |
| **Reviewer agent** | Read-only audit: checks docs for stale claims, broken links, missing sources |
| **SessionStart hook** | Injects feature list and recent activity into agent context |
| **PostToolUse hook** | Logs edits, reminds which feature docs to update |
| **Stop hook** | Reports features with source changes but no doc updates |

### Phase 1 (planned): `fm` CLI

```bash
pip install feature-memory
fm init
fm scan
fm status
fm report proposal "Refactor auth to OAuth2"
```

## Architecture

![Who Benefits — different roles, same compiled knowledge](images/v2_whoBenefits.png)

Feature Memory is designed in layers:

1. **Markdown docs** (`docs/feature-memory/`) — human-readable, git-tracked feature pages with YAML frontmatter
2. **Config** (`.feature-memory/config.yaml`) — maps source file globs to features
3. **Hooks** — Python scripts that integrate with Claude Code's lifecycle events
4. **Skill** — structured instructions that teach the agent how to maintain FM docs
5. **CLI** (Phase 1) — `fm` command for scanning, status checks, and reports

## Specs

Full implementation specifications live in [`docs/specs/`](docs/specs/README.md):

| # | Spec | Scope |
|---|------|-------|
| 00 | [Project Bootstrap](docs/specs/00-project-bootstrap.md) | Repo structure, Python toolchain, CI |
| 01 | [CLI Foundation](docs/specs/01-cli-foundation.md) | CLI framework, config loading |
| 02 | [Data Model](docs/specs/02-data-model.md) | Markdown templates, schemas, SQLite DDL |
| 03 | [Core Commands](docs/specs/03-core-commands.md) | Every `fm` subcommand |
| 04 | [Hooks and Triggers](docs/specs/04-hooks-and-triggers.md) | Claude Code hooks, git hooks, CI |
| 05 | [Skills](docs/specs/05-skills.md) | SKILL.md for Claude + Codex |
| 06 | [Plugins](docs/specs/06-plugins.md) | Claude/Codex plugin packaging |
| 07 | [Testing](docs/specs/07-testing.md) | Unit tests, fixtures, golden tests |
| 08 | [Publishing](docs/specs/08-publishing.md) | PyPI, GitHub Releases |
| 09 | [Examples and Docs](docs/specs/09-examples-and-docs.md) | Quickstart, user guide |
| 10 | [Roadmap](docs/specs/10-roadmap.md) | Phased milestones |
| 11 | [What's New Generator](docs/specs/11-whats-new.md) | Optional release notes generation |

## Test Results

The Phase 0 design was validated with a real Claude Code integration test against a sample project (Flask + React, 8 features, 30+ source files). Results in [`docs/RepoTest_Iteration1/`](docs/RepoTest_Iteration1/):

- **All hooks fire correctly** with <100ms latency (3s budget)
- **Path matching**: 100% accuracy on a 16-path test battery (8 features)
- **Cross-platform**: Tested on Windows, validated for macOS/Linux compatibility
- **12 findings** documented, 4 fixed in-place, 16 prioritized recommendations

Key numbers:
- PostToolUse: 47ms average per invocation
- Stop hook: 50ms for 1000 events
- SessionStart context: ~2KB for 8 features

## Project Structure

```
plugin/                             # Claude Code plugin
  .claude-plugin/plugin.json        # Plugin manifest
  hooks/                            # Lifecycle hook scripts
  skills/                           # Init and maintainer skills
  agents/                           # Reviewer agent
images/                             # Architectural diagrams and value-prop visuals
docs/
  specs/                            # Implementation specifications (00-11)
  RepoTest_Iteration1/              # Phase 0 test results and findings
  image-catalog.md                  # Image descriptions and alt text
```

## License

Not yet specified.
