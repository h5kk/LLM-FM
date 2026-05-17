# RepoTest_Iteration1: Findings

## Pre-flight Findings (Before Claude Code Testing)

### Finding 1: event_id uniqueness
**Severity:** Low
**Category:** Design gap

The event_id format `YYYYMMDDTHHMMSSZ-path-touched` is not unique when multiple events fire within the same second (e.g., multi-file edits). In the real CLI, use a UUID or append a random suffix.

### Finding 2: Stop hook does not filter by session
**Severity:** Medium
**Category:** Design gap

The Stop hook reads ALL events in events.jsonl regardless of session_id. This means:
- If a previous session edited files but the events weren't cleared, the current session's Stop hook will report those old findings too.
- In the real CLI, `fm detect --since-session` would filter by the current session_id.

**Workaround for testing:** Clear events.jsonl between test sessions.

### Finding 3: Absolute path in SessionStart output
**Severity:** Low (cosmetic)
**Category:** Cosmetic

The SessionStart hook reports docs_root as the full absolute path (`C:/Users/NTX/Desktop/GitHub/LLM-FM-TEST/docs/feature-memory`). Should show relative path for cleaner, more portable output.

### Finding 4: Config YAML parser limitations
**Severity:** Low
**Category:** Known limitation

The custom line-based YAML parser works for the specific config.yaml format used here but would break on:
- Quoted strings with colons inside
- Multi-line values
- Nested maps deeper than 2 levels
- Comments with `:` characters

This is acceptable for Phase 0. The real CLI uses PyYAML.

### Finding 5: No .gitattributes for line endings
**Severity:** Low
**Category:** Compatibility

Git shows CRLF warnings for all files on Windows. Should add `.gitattributes` with:
```
* text=auto
*.py text eol=lf
*.jsonl text eol=lf
```

This ensures events.jsonl stays LF-only regardless of platform.

### Finding 6: Hook scripts have no error reporting
**Severity:** Medium
**Category:** Design gap

If a hook script crashes (e.g., permission denied on events.jsonl), it fails silently. The user never knows the hook didn't work. In production, hooks should log errors to a `.feature-memory/hook-errors.log` or similar.

## Claude Code Integration Findings

**Status:** PENDING — to be filled after running test scenarios A-H.

### Questions to answer during testing:
1. Does Claude Code's hook JSON format match our assumptions about `tool_name`, `tool_input`, `session_id`?
2. Is the `message` field in hook output actually displayed to the agent/user?
3. Does the PostToolUse hook fire for EVERY edit, or is it batched?
4. What is the actual cwd when hooks run — the project root or something else?
5. Does the matcher `Edit|Write|MultiEdit` correctly filter? Are those the exact tool names?
6. Is there a delay/performance impact noticeable from the hooks?
7. Does the skill actually trigger automatically, or only when explicitly invoked?
