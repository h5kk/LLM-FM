# RepoTest_Iteration1: Improvement Proposals

## Based on expanded testing (8 features, Flask + React, live sessions)

---

### Proposal 1: Shared/cross-cutting file support

**Problem:** Files like `frontend/src/hooks/useApi.ts`, `frontend/src/types/index.ts`, and `config.py` serve multiple features but currently map to only one (via first glob match) or none.

**Proposed solutions:**

**A) Multi-feature mapping (report all matches):**
Change `match_path_to_features` to continue scanning after first match. Stop hook reports the file under ALL matched features.

**B) "shared" pseudo-feature:**
Add a `shared` feature in config.yaml that captures cross-cutting utilities:
```yaml
shared:
  title: Shared Utilities
  globs:
    - frontend/src/hooks/useApi.ts
    - frontend/src/types/**
    - config.py
```

**C) Glob inheritance / "also-maps-to" directive:**
```yaml
frontend-auth:
  globs:
    - frontend/src/hooks/useAuth.ts
  also-uses:
    - frontend/src/hooks/useApi.ts
    - frontend/src/types/index.ts
```

**Recommendation:** Start with (A) — it's the simplest change and provides the most information. If noise becomes a problem, add (B) as a sink for shared code.

---

### Proposal 2: Smart SessionStart scaling

**Problem:** With 8 features the context message is 2000 chars. At 50+ features it would overwhelm the context window.

**Proposed solutions:**

**A) Truncation with priority:**
Only show features that had recent activity (last 5 days) in full. Others get a one-line count:
```
Documented features (3 recently active):
  | Auth | ... |
  | Billing | ... |  
  | Notifications | ... |
(+5 more features documented)
```

**B) Two-tier output:**
- First 5 lines: recently changed features
- Collapsed: total count + link to index.md

**C) Agent-side filtering (skill-driven):**
Don't change SessionStart. Instead, rely on the skill to read index.md on demand.

**Recommendation:** (A) — keeps the context useful without growing unbounded.

---

### Proposal 3: Event rotation / session filtering

**Problem:** events.jsonl accumulates across sessions. The Stop hook reports ALL events regardless of which session generated them.

**Proposed solutions:**

**A) SessionStart clears events.jsonl:**
On session start, archive (or delete) previous events. Simple, but loses history.

**B) Stop hook filters by session_id:**
Each session gets a UUID. The Stop hook only reports events matching the current session. Requires the Stop hook to receive the session_id (it currently gets `{}`).

**C) Rotation on size threshold:**
When events.jsonl exceeds 100KB, rotate to `events.jsonl.1` (keep last 2 files).

**D) TTL-based filtering:**
Stop hook ignores events older than N hours (configurable in config.yaml).

**Recommendation:** (B) is the correct long-term fix (matches the original spec design with `fm detect --since-session`). For Phase 0, (D) is a pragmatic interim since we know the session_id isn't reliably passed to the Stop hook.

---

### Proposal 4: Deduplicated PostToolUse reminders

**Problem:** If the same file is edited 3 times in a session, the agent sees 3 identical "[FM] Consider updating..." messages.

**Proposed solutions:**

**A) Track reminded files in a temp file:**
PostToolUse writes reminded paths to `.feature-memory/.reminded-this-session`. Before printing, check if already reminded.

**B) Event-based dedup:**
Before printing, read events.jsonl and check if this path was already logged in this session. If so, skip the reminder.

**C) Accept the duplication:**
Reminders are short and harmless. The agent can ignore duplicates. Simpler is better.

**Recommendation:** (C) for Phase 0. The cost of duplicate reminders is trivial compared to the complexity of session-tracking state files. Revisit in Phase 1 when the CLI manages session state.

---

### Proposal 5: Stop hook priority ranking

**Problem:** "Consider updating feature docs for: auth, billing, frontend-auth, frontend-billing, frontend-profile, infrastructure, notifications, profile" is a wall of text when many features are affected.

**Proposed solutions:**

**A) Sort by change count:**
```
Consider updating feature docs for:
  - notifications (4 files changed) ← most impacted
  - infrastructure (3 files changed)
  - auth, billing, frontend-auth, frontend-billing, frontend-profile, profile (1 each)
```

**B) Top-3 only with count:**
```
Top features needing docs: notifications (4 changes), infrastructure (3 changes), and 6 others.
```

**C) Severity-based (heuristic):**
If >3 files changed in one feature, mark as HIGH priority. If 1 file, mark as LOW.

**Recommendation:** (A) — simple sort gives the most actionable output without losing information.

---

### Proposal 6: Relative path in SessionStart

**Problem:** Shows `C:/Users/NTX/Desktop/GitHub/LLM-FM-TEST/docs/feature-memory` instead of `docs/feature-memory`.

**Fix:** Replace line 26 in `claude_session_start.py`:
```python
# Before:
lines.append(f"Docs root: {docs_root.as_posix()}")
# After:
lines.append(f"Docs root: {docs_root.relative_to(project_dir).as_posix()}")
```

**Recommendation:** Implement immediately — trivial fix.

---

### Proposal 7: Config caching (future optimization)

**Problem:** config.yaml is parsed on every PostToolUse invocation (47ms avg includes this). With a 96-line file and 8 features, this is negligible. But at scale (50+ features, deep config), it could matter.

**Proposed solutions:**

**A) JSON cache file:**
On first parse, write `.feature-memory/.config-cache.json`. PostToolUse reads the JSON (faster) and falls back to YAML if cache is older than config.yaml.

**B) Compiled glob patterns:**
Pre-compile glob patterns into a regex and cache it.

**C) Leave it:**
47ms total (parse + match + log) is fine. Python process startup dominates anyway.

**Recommendation:** (C) for Phase 0 and likely Phase 1 too. Python startup is ~30ms; the parse is ~5ms of the 47ms total. Not worth optimizing until proven problematic.

---

### Proposal 8: Hook error visibility

**Problem:** If a hook crashes (e.g., malformed config.yaml), it fails silently. The user never knows.

**Proposed solutions:**

**A) Error log file:**
Wrap all hook logic in try/except, write errors to `.feature-memory/hook-errors.log`:
```python
try:
    main()
except Exception as e:
    error_path = Path.cwd() / ".feature-memory" / "hook-errors.log"
    with open(error_path, "a", encoding="utf-8") as f:
        f.write(f"{datetime.now().isoformat()} PostToolUse ERROR: {e}\n")
```

**B) Error in hook output:**
Return `{"result": "continue", "message": "[FM ERROR] Hook failed: {error}"}` so the agent/user sees it.

**C) Both:**
Log to file AND report to agent.

**Recommendation:** (C) — log for debugging, report to agent for visibility. Implement in Phase 0.

---

## Priority Matrix

| # | Proposal | Impact | Effort | Phase |
|---|----------|--------|--------|-------|
| 6 | Relative path fix | Low | 1 line | Now |
| 8 | Error visibility | Medium | 10 lines | Now |
| 5 | Stop hook priority ranking | Medium | 15 lines | Now |
| 1 | Multi-feature mapping | Medium | 5 lines | Now |
| 4 | Dedup reminders | Low | — | Skip (accept) |
| 3 | Event rotation | High | 20 lines | Phase 0.5 |
| 2 | SessionStart scaling | Medium | 20 lines | Phase 0.5 |
| 7 | Config caching | Low | — | Skip (premature) |

---

## Questions for Council Review

1. Is multi-feature mapping (Proposal 1A) the right default? Or should features be exclusive (first-match wins)?
2. Should the Stop hook's output be structured (JSON with priorities) or human-readable (current format)?
3. Is event rotation (clear on session start) acceptable, or is cross-session history valuable?
4. Should SessionStart output be opinionated about what to show, or should it dump everything and let the agent filter?
5. Are there patterns from other hook-based systems that we should adopt?
