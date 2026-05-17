# Spec 10 — Implementation Roadmap

> Arch plan refs: section 23 (implementation phases)

## Objective

Sequence all work into phased milestones with dependencies, deliverables, success criteria, and time estimates.

---

## Phase overview

```
Phase 0  Paper Prototype        1-2 days     no code
Phase 1  CLI MVP                2-3 weeks    specs 00, 01, 02, 03 (partial)
Phase 2  LLM Summaries          1 week       spec 03 (remainder)
Phase 3  Skills                  2-3 days     spec 05
Phase 4  Hooks                   3-5 days     spec 04
Phase 5  Testing & Hardening     1 week       spec 07
Phase 6  Plugins                 3-5 days     spec 06
Phase 7  Publishing              2-3 days     spec 08
Phase 8  Examples & Docs         2-3 days     spec 09
```

**Total estimated calendar time**: 6-9 weeks.

---

## Dependency graph

```
Phase 0 ─────► Phase 1 ─────► Phase 2
                 │               │
                 ├──► Phase 3 ◄──┤
                 │       │       │
                 │       ▼       │
                 ├──► Phase 4    │
                 │       │       │
                 ▼       ▼       │
              Phase 5 ◄──────────┘
                 │
                 ▼
              Phase 6 ──► Phase 7
                             │
              Phase 8 ◄──────┘
```

### Parallelism opportunities

- Phase 3 (Skills) can start as soon as Phase 1 is done (CLI must work for skills to call it).
- Phase 8 (Examples) can start in parallel with Phase 5/6/7 since it only needs the CLI.
- Phase 2 (LLM Summaries) is independent of Phases 3 and 4.

---

## Phase 0 — Paper Prototype

**Duration**: 1-2 days
**Specs**: none (manual work)
**Dependencies**: none

### Work

1. Create `docs/feature-memory/` manually in an existing project.
2. Write 3 feature pages by hand (auth, billing, one more).
3. Write `index.md`, `recent.md`, `changelog.md`.
4. Add CLAUDE.md / AGENTS.md instruction snippet.
5. Use an agent (Claude Code or Codex) manually to update docs after a real diff.

### Success criteria

- [ ] The 3 feature pages are useful to read before making a code change.
- [ ] The agent can follow the instructions to update docs.
- [ ] The workflow feels natural, not forced.

### Output

Validated that the document structure and update workflow work before writing code.

---

## Phase 1 — CLI MVP

**Duration**: 2-3 weeks
**Specs**: 00 (bootstrap), 01 (CLI foundation), 02 (data model), 03 (core commands — `--no-llm` parts only)
**Dependencies**: Phase 0

> **Note:** This phase covers the largest spec (03) with 15+ subcommands and the 8-step mapping algorithm. The extended estimate accounts for the mapping algorithm complexity and the breadth of CLI commands.

### Work

1. Set up the Python project (spec 00):
   - `pyproject.toml`, `Makefile`, CI workflow
   - `src/fm/` package skeleton
   - `fm --version` and `fm --help` working
2. Implement CLI foundation (spec 01):
   - Global options, output formatting, config loading
   - `CliContext` and `Result` classes
3. Implement data model (spec 02):
   - Pydantic models for all schemas
   - Markdown templates
   - SQLite DDL and `FmDatabase` class
   - JSON Schema export
4. Implement core commands (spec 03, `--no-llm` only):
   - `fm init`
   - `fm detect --diff` and `fm detect --paths`
   - `fm map --paths`
   - `fm ingest --no-llm`
   - `fm lint` (all 15 deterministic checks)
   - `fm recent`
   - `fm context --for-agent`
   - `fm changelog`
   - `fm index rebuild`

### Success criteria

- [ ] `fm init` creates the full directory tree and valid config
- [ ] `fm detect --diff HEAD~1..HEAD` correctly classifies changed files
- [ ] `fm map` maps paths to features using steps 1-4, 6, 8
- [ ] `fm ingest --no-llm` updates timestamps, source maps, changelogs, index, recent
- [ ] `fm lint` catches all 15 deterministic issues
- [ ] All commands produce correct JSON output with `--json`
- [ ] Basic unit tests pass
- [ ] CI runs green

### Milestone

**v0.1.0-alpha**: deterministic CLI that works without an LLM.

---

## Phase 2 — LLM Summaries

**Duration**: 1 week
**Specs**: 03 (core commands — LLM parts)
**Dependencies**: Phase 1

### Work

1. Implement `fm ingest --llm`:
   - LLM provider abstraction (Anthropic + OpenAI)
   - Maintainer prompt (arch plan section 25)
   - Structured response parsing
   - Summary patch generation and application
2. Implement `fm update feature`:
   - Read feature page + relevant source files
   - Generate updated product and engineering summaries
3. Implement `fm review`:
   - Reviewer prompt (arch plan section 26)
   - LLM-assisted checks FM101-FM109
   - Structured findings output
4. Implement `fm propose-reorg` and `fm apply-proposal`:
   - Proposal YAML generation
   - Proposal application with validation

### Success criteria

- [ ] `fm ingest --llm` generates accurate summaries from diffs
- [ ] `fm review` catches unsupported claims and stale descriptions
- [ ] `fm propose-reorg` creates valid, reviewable proposals
- [ ] `fm apply-proposal` applies proposals safely and runs lint
- [ ] LLM provider is configurable (Anthropic, OpenAI, auto)
- [ ] Token cost per update is reasonable (<$0.05 for a typical feature update)

### Milestone

**v0.1.0-beta**: full CLI with LLM-assisted summaries and review.

---

## Phase 3 — Skills

**Duration**: 2-3 days
**Specs**: 05 (skills)
**Dependencies**: Phase 1 (CLI must work)

### Work

1. Write Claude SKILL.md with frontmatter, live context, rules, workflow.
2. Write Codex SKILL.md with compatible format.
3. Write CLAUDE.md snippet.
4. Write AGENTS.md snippet.
5. Test all 7 manual test scenarios.

### Success criteria

- [ ] Claude skill activates when user asks about features or docs
- [ ] Codex skill activates on relevant prompts
- [ ] Skills correctly invoke `fm` CLI commands
- [ ] Live context shows current FM status
- [ ] All manual test scenarios pass

### Milestone

Skills ready for local use.

---

## Phase 4 — Hooks

**Duration**: 3-5 days
**Specs**: 04 (hooks and triggers)
**Dependencies**: Phase 1 (CLI), Phase 3 (skills)

### Work

1. Write Claude hook scripts: `claude_session_start.py`, `claude_post_tool.py`, `claude_stop.py`.
2. Write Claude `.claude/settings.json` hook configuration.
3. Write Codex hook script: `codex_post_tool.py`.
4. Write Codex `.codex/hooks.json` configuration.
5. Write git hooks via lefthook.yml.
6. Implement `fm hooks install` subcommand.
7. Write hook unit tests.

### Success criteria

- [ ] Claude SessionStart hook injects FM context
- [ ] Claude PostToolUse hook logs edited paths to events.jsonl
- [ ] Claude Stop hook reports lint findings
- [ ] Codex hooks work analogously
- [ ] Git pre-commit runs lint and blocks on blocking findings
- [ ] Git post-commit runs draft ingest
- [ ] All hooks respect latency budgets
- [ ] Hook tests pass

### Milestone

Full lifecycle integration working locally.

---

## Phase 5 — Testing & Hardening

**Duration**: 1 week
**Specs**: 07 (testing)
**Dependencies**: Phases 1-4

### Work

1. Implement all 10 fixture repos as pytest fixtures.
2. Write golden test snapshots for all fixtures.
3. Write remaining unit tests (target: >80% coverage).
4. Write integration tests for full pipeline.
5. Write hook tests.
6. Write evaluation metric scripts.
7. Fix bugs found during testing.
8. Performance profiling and optimization (latency budgets).

### Success criteria

- [ ] >80% code coverage
- [ ] All 10 fixture scenarios pass
- [ ] Golden tests match expected outputs
- [ ] Mapping precision >90%, recall >85% on fixtures
- [ ] No lint check produces false positives on well-formed docs
- [ ] All hooks complete within latency budgets
- [ ] CI runs all tests green

### Milestone

**v0.1.0-rc**: release candidate with comprehensive test coverage.

---

## Phase 6 — Plugins

**Duration**: 3-5 days
**Specs**: 06 (plugins)
**Dependencies**: Phase 3 (skills), Phase 4 (hooks), Phase 5 (tests pass)

### Work

1. Assemble Claude plugin directory from project files.
2. Assemble Codex plugin directory.
3. Write plugin.json for both.
4. Write plugin hooks.json with `${PLUGIN_ROOT}` paths.
5. Write reviewer agent definition.
6. Implement MCP server (basic read tools).
7. Write plugin build scripts.
8. Test plugins locally.
9. Run plugin validation.

### Success criteria

- [ ] `claude plugin install ./feature-memory-plugin` succeeds
- [ ] `codex plugin install ./feature-memory-codex-plugin` succeeds
- [ ] Plugin hooks work through plugin paths
- [ ] Plugin skills activate correctly
- [ ] MCP server responds to tool calls
- [ ] Plugin validation passes
- [ ] Plugin uninstalls cleanly

### Milestone

Installable plugins ready for marketplace submission.

---

## Phase 7 — Publishing

**Duration**: 2-3 days
**Specs**: 08 (publishing)
**Dependencies**: Phase 5 (tests), Phase 6 (plugins)

### Work

1. Finalize `pyproject.toml` metadata.
2. Set up PyPI trusted publishing (GitHub Actions OIDC).
3. Create release workflow (`.github/workflows/release.yml`).
4. Write version bump script.
5. Create CHANGELOG.md.
6. Tag v0.1.0 and publish to PyPI.
7. Create GitHub Release.
8. Submit Claude plugin to marketplace.
9. Submit Codex plugin to marketplace.

### Success criteria

- [ ] `pip install feature-memory` works from PyPI
- [ ] GitHub Release has notes and assets
- [ ] Claude plugin is live on marketplace (or submitted for review)
- [ ] Codex plugin is live on marketplace (or submitted for review)
- [ ] Version numbers are synchronized across all files

### Milestone

**v0.1.0**: first public release.

---

## Phase 8 — Examples & Docs

**Duration**: 2-3 days
**Specs**: 09 (examples and docs)
**Dependencies**: Phase 1 (CLI)

### Work

1. Create `examples/simple-app/` with populated feature docs.
2. Create `examples/monorepo/` with multi-app structure.
3. Write quickstart tutorial.
4. Write project README.md.
5. Create user guide outline and write initial guides.
6. Set up CLI reference generation.

### Success criteria

- [ ] Both examples are self-contained and runnable
- [ ] Quickstart takes <10 minutes to follow
- [ ] README clearly explains what FM is and how to start
- [ ] At least quickstart, config-reference, and cli-reference guides are written
- [ ] CLI reference is auto-generated from click commands

### Milestone

User-facing documentation complete.

---

## Post-v0.1.0 priorities

After the initial release, the next priorities are:

1. **User feedback integration**: gather feedback, fix pain points.
2. **Import graph support**: implement mapping step 5 (import analysis).
3. **Embedding support**: implement mapping step 7 for large codebases.
4. **Graph export**: `fm export --format graph-json` for visualization.
5. **CI workflow templates**: reusable GitHub Actions for FM.
6. **Multi-language support**: better symbol extraction for Go, Rust, Java.
7. **Standalone binaries**: PyInstaller/Nuitka builds for plugin distribution.
8. **Documentation site**: deploy user guide as a static site.

---

## Risk register

| Risk | Impact | Mitigation |
|------|--------|------------|
| LLM summaries hallucinate claims | High — trust erosion | Source path requirement, reviewer agent, `needs_review` defaults |
| Hooks slow down development | Medium — user disables FM | Strict latency budgets, advisory-only defaults |
| Plugin marketplace rejection | Medium — delays distribution | Follow submission checklists, test thoroughly |
| Schema changes break existing docs | High — data loss | schema_version field, migration scripts, backward compat |
| Mapping algorithm has low precision | Medium — noise | Config globs as primary strategy, low-confidence marked for review |
| Scope creep during implementation | High — delays | Strict phase boundaries, MVP-first mentality |

---

## Key deliverables

- [ ] All 9 phases defined with work items, success criteria, and milestones
- [ ] Dependency graph shows parallelism opportunities
- [ ] Time estimates are realistic and account for testing
- [ ] Risk register covers the top concerns
- [ ] Post-v0.1.0 priorities are documented
- [ ] Every spec (00-09) is referenced from at least one phase
