# RepoTest_Iteration1: Test Setup

## Overview

**Date:** 2026-05-17
**Test target:** Feature Memory Phase 0 Paper Prototype
**Test repo:** `C:\Users\NTX\Desktop\GitHub\LLM-FM-TEST`
**Platform:** Windows 11, Python 3.11.9, Git

## What was configured

### Sample project (11 source files)

A fake Python web app with 3 features:

| Feature | Source files | Route | Tests |
|---------|-------------|-------|-------|
| auth | `src/auth/login.py`, `src/auth/logout.py` | `routes/auth.py` | `tests/test_auth.py` |
| billing | `src/billing/checkout.py`, `src/billing/invoice.py` | `routes/billing.py` | `tests/test_billing.py` |
| profile | `src/profile/settings.py` | — | — |

### Feature Memory directory structure

```
docs/feature-memory/
  index.md           # 3-row feature table
  recent.md          # 3 initial entries
  changelog.md       # 3 initial changelog entries
  README.md          # Phase 0 explanation
  features/
    auth.md          # Full feature page (84 lines + frontmatter)
    billing.md       # Full feature page
    profile.md       # Full feature page
  reports/           # Empty (for proposals)
.feature-memory/
  config.yaml        # 3 features with globs
  events.jsonl       # Empty (hooks append here)
  hooks/
    claude_session_start.py
    claude_post_tool.py
    claude_stop.py
  reports/           # Empty
```

### Hook scripts (self-contained, no dependencies)

All hooks use Python stdlib only. No PyYAML — config.yaml is parsed with a custom line-based parser.

| Hook | Event | What it does |
|------|-------|-------------|
| `claude_session_start.py` | SessionStart | Reads index.md and recent.md, outputs context summary |
| `claude_post_tool.py` | PostToolUse (Edit/Write/MultiEdit) | Logs path_touched to events.jsonl, maps path to feature via config globs, prints reminder |
| `claude_stop.py` | Stop | Reads events.jsonl, reports features with source changes but no doc updates |

### Claude Code configuration

**`.claude/settings.json`** — Hooks configured with:
- SessionStart: `python .feature-memory/hooks/claude_session_start.py` (5s timeout)
- PostToolUse matcher `Edit|Write|MultiEdit`: `python .feature-memory/hooks/claude_post_tool.py` (3s timeout)
- Stop: `python .feature-memory/hooks/claude_stop.py` (15s timeout)

**`.claude/skills/feature-memory/SKILL.md`** — Phase 0 skill with:
- Description triggers on: architecture, feature docs, repo memory, changelogs, source map
- 10 rules (source-grounded, append-only, verify-before-trust, etc.)
- 8-step Phase 0 workflow (manual updates since CLI doesn't exist)

**`CLAUDE.md`** — Project instructions with FM snippet.

### Deviations from specs

| Spec reference | Deviation | Reason |
|----------------|-----------|--------|
| Spec 04: hooks call `fm` CLI | Hooks are self-contained Python | CLI doesn't exist yet |
| Spec 04: PostToolUse calls `fm map` | Uses custom glob matching against config.yaml | No CLI available |
| Spec 04: SessionStart calls `fm context --for-agent` | Reads markdown files directly | No CLI available |
| Spec 05: Skill uses `!` live context syntax | Hardcoded Phase 0 note | `fm context` not available |
| Spec 04: Stop hook calls `fm detect --since-session` | Reads events.jsonl directly | No CLI available |

## Pre-flight verification results

All 3 hooks tested standalone via PowerShell pipe before Claude Code testing.

### SessionStart hook: PASS

```powershell
'{}' | python .feature-memory/hooks/claude_session_start.py
```

**Output:** Valid JSON with `result: continue` and a `message` containing:
- Feature list (3 features with summaries from index.md)
- Recent activity (3 entries from recent.md)
- Rules reminder

### PostToolUse hook (mapped file): PASS

```powershell
'{"tool_name":"Edit","tool_input":{"file_path":"C:\\Users\\NTX\\Desktop\\GitHub\\LLM-FM-TEST\\src\\auth\\login.py"},"session_id":"test-preflight"}' | python .feature-memory/hooks/claude_post_tool.py
```

**Output:** `[FM] Edited 'src/auth/login.py' maps to feature(s): auth. Consider updating: docs/feature-memory/features/auth.md`

**Verified:**
- Absolute Windows path correctly converted to relative with forward slashes
- Event logged to events.jsonl with correct format
- Feature `auth` correctly identified from glob `src/auth/**`

### PostToolUse hook (unmapped file): PASS

```powershell
'{"tool_name":"Write","tool_input":{"file_path":"C:\\Users\\NTX\\Desktop\\GitHub\\LLM-FM-TEST\\src\\utils\\helpers.py"},"session_id":"test-preflight"}' | python .feature-memory/hooks/claude_post_tool.py
```

**Output:** None (exit code 0, no stdout)

**Verified:** Unmapped files are handled gracefully — event is still logged but no reminder printed.

### Stop hook: PASS

```powershell
'{}' | python .feature-memory/hooks/claude_stop.py
```

**Output (after PostToolUse tests above):**
```
[FM] Session documentation check:
- Feature 'auth': 1 source file(s) changed but docs/feature-memory/features/auth.md was not updated
- 1 file(s) edited that don't map to any feature: src/utils/helpers.py

Consider updating feature docs for: auth
```

**Verified:** Correctly identified auth as needing docs, correctly identified unmapped file.

## Commit history

```
785a25f Initial project: auth, billing, profile modules with Feature Memory Phase 0 prototype
```

27 files committed. All tests pass. Ready for Claude Code session testing.
