# Spec 04 — Hooks and Triggers

> Arch plan refs: sections 8 (trigger plan), 19 (CI and PR workflow)

## Objective

Implement all lifecycle hooks for Claude Code, Codex, git, and CI. Every hook calls the `fm` CLI — hooks do not reimplement logic.

---

## 1. Trigger matrix

| Trigger | Action | Latency budget | Failure mode |
|---------|--------|---------------|-------------|
| File save | None (optionally dirty-path cache) | — | — |
| Agent PostToolUse (Edit/Write) | Record touched path, optional reminder | <2s | Advisory (never block) |
| Agent PreToolUse (destructive ops) | Block edits to protected docs/changelogs | <1s | Block with message |
| Agent SessionStart | Inject Feature Memory context | <3s | Advisory |
| Agent Stop | Check for missing docs updates | <10s | Advisory or blocking |
| Git pre-commit | `fm lint --changed-only --fail-on blocking` | <5s | Block commit |
| Git post-commit | `fm ingest --diff HEAD~1..HEAD --draft-only` | <15s | Non-blocking (best effort) |
| PR open/update | Generate docs impact report | <30s | Non-blocking |
| Merge to main | Promote reviewed docs, update index | <30s | Non-blocking |
| Nightly/manual | Full lint, review, reorg proposals | unbounded | Report only |

---

## 2. Claude Code hooks

> **Implementation note:** The hook configuration JSON field names below (`SessionStart`, `PostToolUse`, `Stop`, `matcher`, `type`, `command`, `timeout`) must match the Claude Code hooks API at implementation time. Verify against the current Claude Code documentation before implementing — field names may evolve between Claude Code versions.

### Hook configuration

`.claude/settings.json` (project-local):

```json
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "python .feature-memory/hooks/claude_session_start.py",
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
            "command": "python .feature-memory/hooks/claude_post_tool.py",
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
            "command": "python .feature-memory/hooks/claude_stop.py",
            "timeout": 15000
          }
        ]
      }
    ]
  }
}
```

### PreToolUse hook (deferred to post-MVP)

The trigger matrix includes a PreToolUse hook to block edits to protected docs and changelogs. This is deferred to post-MVP because:

1. It requires maintaining a list of protected paths that evolves with the project.
2. The write policy (arch plan section 14) already prevents unauthorized changes via the skill rules.
3. The Stop hook catches missing updates, which is sufficient for MVP.

When implemented, it should check whether the target path is under `docs/feature-memory/` and block direct edits to `changelog.md`, `index.md`, and `recent.md` (these should only be updated via `fm ingest`).

### `claude_session_start.py`

```python
#!/usr/bin/env python3
"""SessionStart hook: inject Feature Memory context including staleness warnings."""
import json
import subprocess
import sys

def main():
    # Read hook input from stdin
    hook_input = json.load(sys.stdin)

    # Run fm context (now includes staleness warnings for stale features)
    result = subprocess.run(
        ["fm", "context", "--for-agent"],
        capture_output=True, text=True, timeout=3
    )

    if result.returncode == 0 and result.stdout.strip():
        # Return context as a system message
        # The output includes staleness warnings when features have
        # hash mismatches, dead paths, or 90+ day silence.
        # This tells the agent which feature pages to verify before trusting.
        output = {
            "result": "continue",
            "message": result.stdout.strip()
        }
        json.dump(output, sys.stdout)

if __name__ == "__main__":
    main()
```

### `claude_post_tool.py`

```python
#!/usr/bin/env python3
"""PostToolUse hook: record edited paths and optionally remind about docs."""
import json
import sys
from datetime import datetime, timezone

def main():
    hook_input = json.load(sys.stdin)
    tool_name = hook_input.get("tool_name", "")
    tool_input = hook_input.get("tool_input", {})

    # Extract the edited file path
    file_path = None
    if tool_name in ("Edit", "Write"):
        file_path = tool_input.get("file_path")
    elif tool_name == "MultiEdit":
        file_path = tool_input.get("file_path")

    if not file_path:
        return

    # Append to events log
    event = {
        "event_id": f"{datetime.now(timezone.utc).isoformat()}-path-touched",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "event_type": "path_touched",
        "source": "claude-hook",
        "path": file_path,
        "session_id": hook_input.get("session_id", ""),
    }

    events_path = ".feature-memory/events.jsonl"
    try:
        with open(events_path, "a") as f:
            f.write(json.dumps(event) + "\n")
    except FileNotFoundError:
        pass  # FM not initialized, skip silently

    # Check if the path maps to a known feature
    # If so, print a brief reminder (goes to agent as system message)
    import subprocess
    result = subprocess.run(
        ["fm", "map", "--paths", file_path, "--json"],
        capture_output=True, text=True, timeout=2
    )
    if result.returncode == 0:
        try:
            map_data = json.loads(result.stdout)
            mappings = map_data.get("data", {}).get("mappings", [])
            if mappings:
                feature_ids = [m["feature_id"] for m in mappings]
                output = {
                    "result": "continue",
                    "message": f"[FM] Edited file maps to feature(s): {', '.join(feature_ids)}. Consider updating docs after your changes."
                }
                json.dump(output, sys.stdout)
        except (json.JSONDecodeError, KeyError):
            pass

if __name__ == "__main__":
    main()
```

### `claude_stop.py`

```python
#!/usr/bin/env python3
"""Stop hook: check if touched source files have missing docs updates."""
import json
import subprocess
import sys

def main():
    hook_input = json.load(sys.stdin)

    # Run detect on session-touched paths
    result = subprocess.run(
        ["fm", "detect", "--since-session", "--json"],
        capture_output=True, text=True, timeout=5
    )
    if result.returncode != 0:
        return

    # Run lint on changed features only
    lint_result = subprocess.run(
        ["fm", "lint", "--changed-only", "--json"],
        capture_output=True, text=True, timeout=10
    )

    if lint_result.returncode == 0:
        try:
            lint_data = json.loads(lint_result.stdout)
            findings = lint_data.get("data", {}).get("findings", [])
            if findings:
                messages = [f"- {f['id']}: {f['message']}" for f in findings[:5]]
                output = {
                    "result": "continue",
                    "message": "[FM] Documentation findings after this session:\n" + "\n".join(messages)
                }
                json.dump(output, sys.stdout)
        except (json.JSONDecodeError, KeyError):
            pass

if __name__ == "__main__":
    main()
```

---

## 3. Codex hooks

> **Implementation note:** The Codex hook configuration format below (`PostToolUse`, `UserPromptSubmit`, `Stop`, `matcher`) must match the Codex hooks API at implementation time. Verify against the current OpenAI Codex documentation before implementing — Codex is in active development and its plugin/hook APIs may change.

### Hook configuration

`.codex/hooks.json`:

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "apply_patch|Bash",
        "hooks": [
          {
            "type": "command",
            "command": "python .feature-memory/hooks/codex_post_tool.py"
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

### `codex_post_tool.py`

Similar to `claude_post_tool.py` but adapted for Codex hook input format. Key difference: Codex hooks should be deterministic (no LLM calls). The hook:

1. Reads the tool event from stdin.
2. Extracts changed file paths.
3. Appends to `events.jsonl`.
4. Does NOT call `fm map` (too slow for a deterministic hook). Instead, just logs the path.

### AGENTS.md integration

Add to `AGENTS.md`:

```markdown
## Feature Memory

This repo uses Feature Memory under `docs/feature-memory/`. Before changing a major feature, read the relevant feature page if it exists. After changing user-facing behavior, APIs, routes, data models, components, or tests, update the affected feature docs or run the `feature-memory` skill. Do not reorganize feature hierarchy automatically; write a proposal under `docs/feature-memory/reports/`.
```

---

## 4. Git hooks

### Recommended setup: lefthook

`lefthook.yml`:

```yaml
pre-commit:
  commands:
    fm-lint:
      run: fm lint --changed-only --fail-on blocking
      skip:
        - merge
        - rebase

post-commit:
  commands:
    fm-ingest:
      run: fm ingest --diff HEAD~1..HEAD --draft-only --no-llm || true
```

### Alternative: raw git hooks

`.git/hooks/pre-commit`:

```bash
#!/usr/bin/env bash
set -euo pipefail
if command -v fm &>/dev/null; then
    fm lint --changed-only --fail-on blocking
fi
```

`.git/hooks/post-commit`:

```bash
#!/usr/bin/env bash
set -euo pipefail
if command -v fm &>/dev/null; then
    fm ingest --diff HEAD~1..HEAD --draft-only --no-llm || true
fi
```

### Installation

`fm init` should offer to set up lefthook or copy raw hooks. Add a `fm hooks install` subcommand:

```
fm hooks install [--method lefthook|raw] [--force]
```

---

## 5. CI workflows

### PR impact report

`.github/workflows/fm-pr-report.yml`:

```yaml
name: Feature Memory PR Report

on:
  pull_request:
    types: [opened, synchronize]

jobs:
  fm-report:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - uses: astral-sh/setup-uv@v3
      - name: Install FM
        run: uv pip install feature-memory --system
      - name: Detect changes
        run: fm detect --diff origin/${{ github.base_ref }}...HEAD --json > .feature-memory/reports/detect.json
      - name: Lint
        run: fm lint --changed-only --json > .feature-memory/reports/lint.json || true
      - name: Review
        run: fm review --diff origin/${{ github.base_ref }}...HEAD --write-report --json > .feature-memory/reports/review.json || true
      - name: Post PR comment
        uses: actions/github-script@v7
        with:
          script: |
            const fs = require('fs');
            let body = '## Feature Memory Impact Report\n\n';
            try {
              const detect = JSON.parse(fs.readFileSync('.feature-memory/reports/detect.json', 'utf8'));
              const paths = detect.data?.changed_paths || [];
              body += `**Changed paths:** ${paths.length}\n\n`;
            } catch {}
            try {
              const lint = JSON.parse(fs.readFileSync('.feature-memory/reports/lint.json', 'utf8'));
              const findings = lint.data?.findings || [];
              body += `**Lint findings:** ${findings.length}\n\n`;
              for (const f of findings.slice(0, 10)) {
                body += `- \`${f.id}\` ${f.message}\n`;
              }
            } catch {}
            await github.rest.issues.createComment({
              owner: context.repo.owner,
              repo: context.repo.repo,
              issue_number: context.issue.number,
              body: body
            });
      - name: Upload artifacts
        uses: actions/upload-artifact@v4
        with:
          name: feature-memory-report
          path: .feature-memory/reports/
```

### Merge-to-main promotion

`.github/workflows/fm-merge.yml`:

```yaml
name: Feature Memory Merge

on:
  push:
    branches: [main]

jobs:
  fm-update:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 2
      - uses: astral-sh/setup-uv@v3
      - name: Install FM
        run: uv pip install feature-memory --system
      - name: Ingest changes
        run: fm ingest --diff HEAD~1..HEAD --no-llm
      - name: Commit docs updates
        run: |
          git config user.name "Feature Memory Bot"
          git config user.email "fm-bot@users.noreply.github.com"
          git add docs/feature-memory/
          git diff --staged --quiet || git commit -m "docs(fm): update feature memory for $(git log -1 --format=%h)"
          git push
```

---

## 6. Cross-platform compatibility

### Windows support

All hook scripts use Python (`python script.py`), not bash, ensuring Windows compatibility. Specific considerations:

- **Shebangs**: `#!/usr/bin/env python3` is ignored on Windows but harmless. The hook configs invoke `python` directly so shebangs are not relied upon.
- **Path separators**: hook scripts must use `pathlib.Path` or forward slashes in all path operations. The events.jsonl paths are always stored with forward slashes regardless of OS.
- **Git hooks on Windows**: raw git hooks (`.git/hooks/pre-commit`) need no shebang when using the `#!/usr/bin/env bash` form with Git for Windows' bundled bash. Lefthook handles this transparently.
- **fm CLI invocation**: hooks call `fm` which is installed as a console script entry point by pip/uv — this works on Windows without modification.
- **Line endings**: events.jsonl is always written with `\n` (not `\r\n`). Use `open(path, "a", newline="")` on Windows.

---

## 7. Hook testing

### Unit testing hooks

Each hook script should be testable standalone:

```python
# tests/unit/test_hooks.py
def test_post_tool_records_event(tmp_path):
    """Simulate PostToolUse hook input and verify event is logged."""
    events_file = tmp_path / ".feature-memory" / "events.jsonl"
    events_file.parent.mkdir(parents=True)
    events_file.touch()

    hook_input = {
        "tool_name": "Edit",
        "tool_input": {"file_path": "src/auth/login.py"},
        "session_id": "test-session"
    }
    # Run hook with mocked stdin and cwd
    ...
```

### Integration testing hooks

Test the full hook -> CLI -> docs pipeline:

1. Create a fixture repo with `fm init`.
2. Simulate a tool event (write hook input JSON to stdin).
3. Run the hook script.
4. Verify events.jsonl was appended.
5. Verify lint findings (if applicable).

---

## Key deliverables

- [ ] Claude Code hooks: `claude_session_start.py`, `claude_post_tool.py`, `claude_stop.py`
- [ ] Claude settings.json hook configuration
- [ ] Codex hooks: `codex_post_tool.py` + `hooks.json` configuration
- [ ] Git hooks via lefthook.yml + raw hook fallback
- [ ] `fm hooks install` subcommand
- [ ] CI workflow: PR impact report with PR comment
- [ ] CI workflow: merge-to-main docs promotion
- [ ] Hook unit tests and integration tests
- [ ] All hooks respect the latency budgets in the trigger matrix
