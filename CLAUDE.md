# LLM-FM — Feature Memory Plugin

## Language & Runtime
- Python 3.11 (hooks must remain stdlib-only — no PyYAML, no requests, no third-party packages)
- Windows + PowerShell is the primary dev environment; all path handling must use `.replace("\\", "/")` for normalization
- `claude` CLI is an *optional* external dependency (topic-tag generation degrades gracefully when unavailable)

## Architecture
- `plugin/hooks/` — lifecycle hooks (SessionStart, PostToolUse, Stop) + shared utilities in `fm_common.py`
- `plugin/skills/` — Claude Code skill SKILL.md files (conversational wrappers around the hooks/scripts)
- `plugin/assets/` — changelog-viewer.html template (embedded JSON SPA, auto-upgraded via _VIEWER_VERSION)
- `docs/feature-memory/` — the actual generated docs that live in a user's project (index, features, viewer)
- `docs/specs/` — canonical design specifications; read before implementing new features

## Invariants
- Hooks must NEVER raise exceptions that crash the agent session — always catch and log to `.feature-memory/errors.log`
- `fm_common.py` is shared by all hooks — keep it pure stdlib, keep functions short, test in `tests/`
- Viewer auto-upgrade (`_VIEWER_VERSION`) must preserve inline JSON data across template replacements
- `changelog.json` schema_version is currently 2; bump requires a migration path documented in MIGRATION.md
- Skills are SKILL.md files only — no Python in skills, just instructions for the LLM agent

## Testing
- Run `python -m pytest tests/ -v` from the repo root
- Hook tests use a subprocess fixture that runs the hook with controlled stdin + tmpdir
- All hook tests must pass on Windows (paths, line endings)
- Coverage target: 70% on hook files, 90% on fm_common.py

## Versioning (semver)
- patch: viewer bump, bug fix, tag heuristic change, doc edit
- minor: new skill/hook, new optional config key, additive changelog schema field
- major: breaking config.yaml shape change, removal of a registered skill name
