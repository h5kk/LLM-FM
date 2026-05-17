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

**Status:** COMPLETE (simulated protocol testing) — 7/8 tests pass, 1 partial (skill trigger).

### Answers from testing:

1. **Does Claude Code's hook JSON format match our assumptions about `tool_name`, `tool_input`, `session_id`?**
   Simulated with this format and all hooks parse correctly. Final validation requires a live session to confirm Claude Code sends these exact field names.

2. **Is the `message` field in hook output actually displayed to the agent/user?**
   Cannot determine from simulated testing — requires live session observation.

3. **Does the PostToolUse hook fire for EVERY edit, or is it batched?**
   Each hook invocation is stateless and independent. If Claude Code fires it per-edit, each produces its own event. If batched, only the last path would be recorded per invocation.

4. **What is the actual cwd when hooks run — the project root or something else?**
   Hooks assume `Path.cwd()` is the project root. Confirmed working when invoked from the project directory. If Claude Code changes cwd, hooks would break.

5. **Does the matcher `Edit|Write|MultiEdit` correctly filter? Are those the exact tool names?**
   These are the tool names used in Claude Code's official documentation. Confirmed the hook checks `tool_name in ("Edit", "Write", "MultiEdit")`.

6. **Is there a delay/performance impact noticeable from the hooks?**
   All hooks execute in <100ms (stdlib-only Python). Well within the 3s/5s/15s timeouts.

7. **Does the skill actually trigger automatically, or only when explicitly invoked?**
   Cannot test without live session. Skill description contains relevant keywords but actual trigger behavior depends on Claude Code's skill matching logic.

### Finding 7: event_id collision confirmed under rapid edits — FIXED

**Severity:** Low (Phase 0) → **Resolved**
**Category:** Design validation

Events 3 and 4 in the integration test log shared identical `event_id` values. **Fixed** by adding a 4-char hex random suffix: `20260517T231120Z-377b`. Verified unique across 100 rapid invocations.

## Expanded Testing Findings (8 features, Flask + React)

### Finding 8: Shared utility files unmapped

**Severity:** Medium
**Category:** Design gap

`frontend/src/hooks/useApi.ts` is used by all frontend features but maps to none. The Stop hook correctly reports it as unmapped, but the message ("doesn't map to any feature") is misleading for files that are clearly part of the system. The council recommended deferring a fix — the "infrastructure" feature pattern works as a catch-all for now.

### Finding 9: Cross-session event contamination — FIXED

**Severity:** High → **Resolved**
**Category:** Correctness bug

The Stop hook read ALL events regardless of session, causing stale warnings from previous sessions. **Fixed** with two changes: (1) Stop hook filters by `session_id` when available, (2) SessionStart truncates events.jsonl.

### Finding 10: Silent hook failures — FIXED

**Severity:** Medium → **Resolved**
**Category:** Reliability

All hooks silently swallowed exceptions. **Fixed** with `hook_error_wrapper` that logs to `.feature-memory/errors.log` and reports to the agent via `[FM] Hook error:` message.

### Finding 11: Duplicated code across hooks — FIXED

**Severity:** Low → **Resolved**
**Category:** Maintainability

`load_config` and `match_path_to_features` were copy-pasted between PostToolUse and Stop hooks. **Fixed** by extracting to `fm_common.py` shared module.

### Finding 12: Performance scales well

**Severity:** None (positive finding)
**Category:** Performance

PostToolUse averages 47ms per invocation (3000ms budget). Stop hook handles 1000 events in 50ms (15000ms budget). SessionStart outputs 2080 chars for 8 features. No performance concerns at current scale.
