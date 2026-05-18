# Feature Memory (LLM-FM)

A documentation compiler for software repos. Maintains feature-level memory so AI coding agents don't rediscover the project from scratch every session.

## The Problem

Every project has two codebases. The real one (files, tests, routes, configs). And the remembered one (what it does, why, which files matter, what's dead). The second one is more useful and decays fastest.

Feature Memory makes it explicit: a structured layer of feature documentation that lives alongside your code, stays current through hooks and skills, and gives agents immediate context when they start a session.

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
  hooks/                # Claude Code lifecycle hooks
```

Three hooks wire into Claude Code's lifecycle:

| Hook | When | What it does |
|------|------|--------------|
| **SessionStart** | Agent opens a session | Injects feature list, recent activity, and FM rules into context |
| **PostToolUse** | After every Edit/Write | Logs the edit, reminds agent which feature docs to update |
| **Stop** | Session ends | Reports features with source changes but no doc updates |

A companion **skill** (`feature-memory`) gives the agent a structured workflow for reading and updating feature pages, changelogs, and the index.

## Quick Start

### Phase 0 (now): Paper prototype with Claude Code hooks

No CLI needed. Run the bootstrapper from your project root:

```bash
python fm_init.py --project-name my-project
```

This creates the full directory structure, hook scripts, Claude Code settings, skill definition, and project instructions. Then ask Claude to scan your project and populate feature pages.

#### Options

```
--project-name NAME   Set the project name in config.yaml (default: directory name)
--dry-run             Show what would be created without writing files
--force               Overwrite existing files
```

#### Requirements

- Python 3.6+
- Claude Code (for hooks and skill)
- No external dependencies (stdlib only)

### Phase 1 (planned): `fm` CLI

```bash
pip install feature-memory
fm init
fm scan
fm status
fm report proposal "Refactor auth to OAuth2"
```

## Architecture

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

## Concept Gists

Three progressively detailed concept documents capture the design thinking:

| File | Audience |
|------|----------|
| `feature-memory-gist-minimal.md` | 2-minute overview |
| `feature-memory-gist.md` | Full concept with examples |
| `feature-memory-gist-ar.md` | Architecture review version |

## Project Structure

```
fm_init.py                          # Zero-dependency bootstrapper
docs/
  specs/                            # Implementation specifications (00-11)
  RepoTest_Iteration1/              # Phase 0 test results and findings
  reviewer-feedback-plan.md         # Review protocol
feature-memory-gist.md              # Concept document (full)
feature-memory-gist-minimal.md      # Concept document (brief)
feature-memory-gist-ar.md           # Concept document (architecture review)
feature-memory-architecture-plan.md # Architecture plan (gitignored, local ref)
```

## License

Not yet specified.
