# RepoTest_Iteration1: Recommendations

## Before Phase 1 CLI Implementation

### Priority 1: Critical for correctness

1. **Add session_id filtering to Stop hook logic**
   The real `fm detect --since-session` command should filter events.jsonl by session_id. This prevents stale findings from previous sessions contaminating the current report.

2. **Use UUIDs or suffixed event_ids**
   Change event_id format from timestamp-only to `{timestamp}-{4-char-hex}` or use `uuid.uuid4()`. Prevents collisions on rapid multi-file edits.

3. **Verify Claude Code hook JSON format**
   Before implementing production hooks, verify the actual field names in the hook input JSON. The specs assume `tool_name`, `tool_input`, `session_id` — these need validation against real hook invocations.

### Priority 2: Important for usability

4. **Add .gitattributes to fm init**
   The `fm init` command should create a `.gitattributes` file ensuring LF line endings for `.jsonl` files across platforms.

5. **Hook error logging**
   Add a try/except wrapper that logs errors to `.feature-memory/hook-errors.log`. Silent hook failures are invisible to users.

6. **Relative path in SessionStart output**
   Show docs root as a relative path (e.g., `docs/feature-memory`) not an absolute path.

7. **Events rotation awareness in Phase 0**
   Even without the full rotation logic, the Stop hook should handle an empty events.jsonl gracefully (it already does) and not crash on malformed JSON lines (it already does via try/except).

### Priority 3: Design improvements for specs

8. **Spec 04 should document hook cwd behavior**
   Document explicitly that hooks run with the project root as cwd. If this differs across Claude Code versions or OSes, hooks will break.

9. **Spec 04 should document hook output protocol more precisely**
   The `{"result": "continue", "message": "..."}` format works in our pre-flight tests. But:
   - What happens if stdout is empty? (Hook is ignored — seems fine.)
   - What happens if `result` is something other than "continue"?
   - Is there a `"result": "block"` option for PreToolUse?
   - Maximum message length before truncation?

10. **Spec 05 skill description should include "how does X work" pattern**
    The skill's `description` field determines triggering. It should explicitly include patterns like "how does [feature] work" and "what does [feature] do" since those are the most common user queries.

11. **Add a "clear events" hook or command**
    Between sessions, events.jsonl accumulates. Either:
    - SessionStart hook should clear (or rotate) events from previous sessions
    - Or `fm init` should document that events.jsonl is ephemeral

### Priority 4: Nice to have

12. **Multi-feature mapping in PostToolUse**
    Currently if a file maps to multiple features (e.g., a shared component), only the first match in the config order is reported. The real CLI should report all matches.

13. **Config hot-reload awareness**
    If config.yaml changes during a session, hooks use the old config until restarted. Not critical but worth noting.

14. **Hook timeout documentation**
    Document that hooks have timeouts (5s, 3s, 15s) and what happens when they're exceeded (killed? ignored? error shown?).

## For the installer/setup script

15. **Single-file distributable init script**
    Create a standalone `fm_init.py` that sets up the entire directory structure, writes hook scripts as embedded templates, and creates default config. This should be downloadable as a single file and runnable with `python fm_init.py`.

16. **Post-init skill workflow**
    After running the init script, the skill should have an "initialization mode" that scans the project and creates initial feature pages. The user says "scan this project and create feature pages" and the agent does the intelligent part.

## Summary of action items

| # | Action | Where | Priority |
|---|--------|-------|----------|
| 1 | Session filtering in Stop hook | Spec 04, CLI | P1 |
| 2 | UUID event_ids | Spec 02, CLI | P1 |
| 3 | Verify hook JSON format | Testing | P1 |
| 4 | .gitattributes in fm init | Spec 03 | P2 |
| 5 | Hook error logging | Spec 04 | P2 |
| 6 | Relative path in context | Spec 04 | P2 |
| 7 | Events rotation | Spec 02 | P2 |
| 8 | Document hook cwd | Spec 04 | P3 |
| 9 | Document output protocol | Spec 04 | P3 |
| 10 | Skill description keywords | Spec 05 | P3 |
| 11 | Events clear mechanism | Spec 04 | P3 |
| 12 | Multi-feature mapping | Spec 03 | P4 |
| 13 | Config hot-reload | Note | P4 |
| 14 | Timeout documentation | Spec 04 | P4 |
| 15 | Single-file init script | New | P2 |
| 16 | Post-init skill workflow | Spec 05 | P2 |
