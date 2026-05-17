# Spec 06 — Plugins

> Arch plan refs: sections 10 (plugin packaging), 11 (optional MCP server)

## Objective

Package Feature Memory as installable plugins for Claude Code and Codex, including MCP server definitions and reviewer agent configuration.

---

## 1. Claude Code plugin

### Directory structure

```
feature-memory-plugin/
  .claude-plugin/
    plugin.json
  skills/
    feature-memory/
      SKILL.md                         # same as spec 05, section 1
  agents/
    feature-memory-reviewer.md
  hooks/
    hooks.json
    claude_session_start.py
    claude_post_tool.py
    claude_stop.py
  bin/
    fm                                 # CLI binary or wrapper script
  .mcp.json                           # MCP server config (optional)
  README.md
  LICENSE
```

### `plugin.json`

```json
{
  "name": "feature-memory",
  "version": "0.1.0",
  "description": "Maintains product and engineering memory for software features. Compiles project knowledge into persistent, interlinked markdown docs with source maps, changelogs, and review reports.",
  "author": "h5k",
  "homepage": "https://github.com/h5k/LLM-FM",
  "repository": "https://github.com/h5k/LLM-FM",
  "license": "MIT",
  "keywords": ["documentation", "feature-memory", "knowledge-base"],
  "engines": {
    "claude-code": ">=1.0.0"
  },
  "capabilities": {
    "skills": true,
    "hooks": true,
    "agents": true,
    "mcp": true
  }
}
```

### `hooks/hooks.json`

Plugin hooks use `${CLAUDE_PLUGIN_ROOT}` to reference plugin-relative paths:

```json
{
  "description": "Feature Memory lifecycle hooks",
  "hooks": {
    "SessionStart": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "python",
            "args": ["${CLAUDE_PLUGIN_ROOT}/hooks/claude_session_start.py"],
            "timeout": 5000
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Edit|Write|MultiEdit",
        "hooks": [
          {
            "type": "command",
            "command": "python",
            "args": ["${CLAUDE_PLUGIN_ROOT}/hooks/claude_post_tool.py"],
            "timeout": 3000
          }
        ]
      }
    ],
    "Stop": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "python",
            "args": ["${CLAUDE_PLUGIN_ROOT}/hooks/claude_stop.py"],
            "timeout": 15000
          }
        ]
      }
    ]
  }
}
```

### Reviewer agent

`agents/feature-memory-reviewer.md`:

```markdown
---
name: Feature Memory Reviewer
description: Reviews feature documentation for completeness, source grounding, stale claims, and privacy risk. Produces structured findings without editing canonical docs.
allowed-tools: Bash, Read, Grep, Glob
---

# Feature Memory Reviewer

You review Feature Memory documentation updates. You do NOT directly edit canonical docs.

## Your responsibilities

1. Verify source paths exist on disk.
2. Compare claims in product and engineering summaries against code, diffs, and tests.
3. Flag unsupported current-behavior claims.
4. Flag stale claims (old source, removed behavior described as current).
5. Verify changed files are mapped to features.
6. Verify docs changed only where necessary (minimal update principle).
7. Check broken wikilinks and missing backlinks.
8. Check product vs engineering audience separation.
9. Check for privacy or roadmap leakage.

## Output format

Report findings as structured JSON:

```json
{
  "summary": "Brief summary of review",
  "decision": "pass | needs_review | block",
  "findings": [
    {
      "severity": "info | low | medium | high | blocking",
      "category": "stale-claim | missing-source | broken-link | unsupported-claim | hierarchy-risk | privacy-risk",
      "feature_id": "feature-id",
      "claim": "The specific claim being questioned",
      "evidence": ["path or reference"],
      "recommendation": "What to do about it"
    }
  ]
}
```

## Workflow

1. Run `fm lint --changed-only --json` for deterministic checks.
2. Read the feature pages that were updated.
3. For each claim in the product and engineering summaries, verify against source files.
4. Report findings. Do not fix them directly.
```

### CLI binary distribution

The `bin/fm` file can be:

**Option A: Wrapper script** (requires Python installed)

```bash
#!/usr/bin/env bash
exec python -m fm "$@"
```

**Option B: Standalone binary** (no Python required)

Build with PyInstaller:

```bash
pyinstaller --onefile --name fm src/fm/__main__.py
```

Or with Nuitka:

```bash
nuitka --standalone --onefile --output-filename=fm src/fm/__main__.py
```

**Recommendation**: Start with Option A. Move to Option B for marketplace distribution if user feedback requests it.

---

## 2. Codex plugin

### Directory structure

```
feature-memory-codex-plugin/
  .codex-plugin/
    plugin.json
  skills/
    feature-memory/
      SKILL.md                         # same as spec 05, section 2
  hooks/
    hooks.json
    codex_post_tool.py
  .mcp.json
  assets/
    README.md
  LICENSE
```

### `plugin.json`

```json
{
  "name": "feature-memory",
  "version": "0.1.0",
  "description": "Maintains product and engineering memory for software features.",
  "author": "h5k",
  "homepage": "https://github.com/h5k/LLM-FM",
  "repository": "https://github.com/h5k/LLM-FM",
  "license": "MIT",
  "trust_notes": "This plugin runs deterministic CLI commands and Python scripts for documentation maintenance. Hook scripts read tool event data from stdin and write to .feature-memory/events.jsonl. No network requests are made by hooks."
}
```

### `hooks/hooks.json`

```json
{
  "description": "Feature Memory lifecycle hooks (deterministic only)",
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "apply_patch|Bash",
        "hooks": [
          {
            "type": "command",
            "command": "python ${CODEX_PLUGIN_ROOT}/hooks/codex_post_tool.py"
          }
        ]
      }
    ],
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "fm context --for-agent"
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "fm lint --changed-only --json"
          }
        ]
      }
    ]
  }
}
```

### Trust and opt-in

Codex plugin hooks require explicit user opt-in. The plugin README should include:

1. What each hook does (exact commands).
2. What data the hooks read (tool events from stdin).
3. What data the hooks write (events.jsonl, stdout messages).
4. That no network requests are made.
5. How to disable specific hooks.

---

## 3. MCP server

### Overview

Optional. The CLI is sufficient for MVP. MCP becomes useful when agents need structured interactive tools during long sessions.

### `.mcp.json`

```json
{
  "mcpServers": {
    "feature-memory": {
      "command": "fm",
      "args": ["mcp", "serve"],
      "env": {}
    }
  }
}
```

### MCP tool definitions

| Tool | Description | Read/Write | Approval required |
|------|-------------|-----------|-------------------|
| `feature_memory.search` | Search feature docs by query | Read | No |
| `feature_memory.read_feature` | Read a feature page by ID | Read | No |
| `feature_memory.list_recent` | List recent changes | Read | No |
| `feature_memory.map_paths` | Map file paths to features | Read | No |
| `feature_memory.validate` | Run lint checks | Read | No |
| `feature_memory.create_update_proposal` | Create a docs update proposal | Write (proposals only) | No |
| `feature_memory.propose_reorg` | Propose a reorganization | Write (proposals only) | No |
| `feature_memory.apply_proposal` | Apply a reviewed proposal | Write (canonical docs) | Yes |

### MCP server implementation

`src/fm/mcp_server.py`:

```python
"""Feature Memory MCP server using stdio transport.

Implementation approach:
1. Use the `mcp` Python SDK (pip install mcp) for stdio transport and tool registration.
2. Each MCP tool delegates to the same internal function used by the corresponding CLI command.
3. Tool parameters map to CLI arguments; tool results return the same JSON structure as --json output.
4. Error responses use the MCP error format with FM error codes.

Post-MVP enhancements:
- Resource endpoints for feature pages (mcp resources)
- Streaming progress for long-running operations (review, ingest --llm)
- Subscription to events.jsonl for real-time notifications
"""

from mcp.server import Server
from mcp.server.stdio import stdio_server

def serve():
    """Start the MCP server on stdin/stdout."""
    server = Server("feature-memory")

    @server.tool()
    async def feature_memory_search(query: str, limit: int = 10) -> str:
        # Delegates to fm.query logic
        ...

    @server.tool()
    async def feature_memory_read_feature(feature_id: str) -> str:
        # Reads and returns feature page content
        ...

    @server.tool()
    async def feature_memory_list_recent(days: int = 5) -> str:
        # Delegates to fm.recent logic
        ...

    @server.tool()
    async def feature_memory_map_paths(paths: list[str]) -> str:
        # Delegates to fm.mapping logic
        ...

    @server.tool()
    async def feature_memory_validate() -> str:
        # Delegates to fm.lint logic
        ...

    # Write tools require explicit approval (tool annotations)
    @server.tool()
    async def feature_memory_apply_proposal(proposal_path: str) -> str:
        # Delegates to fm.proposal.apply logic
        ...

    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream)
```

The MCP server reuses the same internal functions as the CLI commands. It does not duplicate logic.

### Tool policies

- Read tools: broadly available, no confirmation needed.
- Proposal tools: write only to `.feature-memory/proposals/` (the canonical proposal directory).
- Canonical write tools (`apply_proposal`): require explicit user approval. Writes to `docs/feature-memory/`.
- No delete tools in v0.1.

---

## 4. Plugin local testing

### Claude plugin testing

```bash
# Install plugin from local path
claude plugin install ./feature-memory-plugin

# Verify plugin is loaded
claude plugin list

# Test in a project with fm initialized
cd /path/to/test-project
fm init
# Start a Claude Code session and verify:
# 1. SessionStart hook injects FM context
# 2. Edit a file -> PostToolUse hook logs the event
# 3. End session -> Stop hook reports findings
# 4. Ask about features -> skill activates
```

### Codex plugin testing

```bash
# Install plugin from local path
codex plugin install ./feature-memory-codex-plugin

# Verify plugin is loaded
codex plugin list

# Test similarly in a project with fm initialized
```

### Plugin validation checklist

- [ ] `plugin.json` has valid name, version, description
- [ ] All referenced files exist in the plugin directory
- [ ] Hook scripts are executable and handle missing FM gracefully
- [ ] Skill SKILL.md has valid frontmatter
- [ ] MCP server starts and responds to tool calls (if included)
- [ ] Plugin installs without errors
- [ ] Plugin uninstalls cleanly

---

## 5. Monorepo vs separate repos

### Recommended: monorepo with plugin build targets

Keep everything in the `LLM-FM` repo. Use build scripts to assemble plugin directories:

```
LLM-FM/
  src/fm/                    # CLI source
  plugins/
    claude/                  # Claude plugin assembly directory
      build.sh               # Script to assemble plugin from src/
    codex/                   # Codex plugin assembly directory
      build.sh
```

`plugins/claude/build.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail
DIST=dist/feature-memory-plugin
rm -rf "$DIST"
mkdir -p "$DIST/.claude-plugin" "$DIST/skills/feature-memory" "$DIST/hooks" "$DIST/agents" "$DIST/bin"

cp plugin.json "$DIST/.claude-plugin/"
cp ../../.claude/skills/feature-memory/SKILL.md "$DIST/skills/feature-memory/"
cp ../../.feature-memory/hooks/claude_*.py "$DIST/hooks/"
cp hooks.json "$DIST/hooks/"
cp agents/*.md "$DIST/agents/"
cp ../../.mcp.json "$DIST/" 2>/dev/null || true

# Build CLI binary or copy wrapper
cp fm-wrapper.sh "$DIST/bin/fm"
chmod +x "$DIST/bin/fm"

echo "Plugin assembled at $DIST"
```

---

## Key deliverables

- [ ] Claude plugin directory structure with all required files
- [ ] Codex plugin directory structure with all required files
- [ ] `plugin.json` for both plugins with correct metadata
- [ ] Plugin hook configurations using plugin-relative paths
- [ ] Reviewer agent definition
- [ ] MCP server tool definitions and implementation plan
- [ ] Plugin build scripts for monorepo assembly
- [ ] Local testing procedure documented
- [ ] Plugin validation checklist completed
