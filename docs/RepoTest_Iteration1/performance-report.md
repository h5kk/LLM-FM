# RepoTest_Iteration1: Performance & Behavior Report

## Test Environment

- **Date:** 2026-05-17
- **Project:** LLM-FM-TEST (Flask backend + React frontend, 8 features, ~40 source files)
- **Platform:** Windows 11, Python 3.11.9, Claude Code CLI 2.1.143
- **Config:** 8 features with 20+ glob patterns in config.yaml

## Hook Performance

### PostToolUse Hook

| Metric | Value |
|--------|-------|
| Average latency (100 invocations) | 47.3ms |
| Max observed | <100ms |
| Timeout budget | 3000ms |
| Headroom | 98.4% unused |

**Operations per invocation:**
1. JSON parse from stdin
2. Path normalization (absolute → relative)
3. YAML config parse (line-by-line, ~96 lines)
4. Glob matching (8 features × 1-3 patterns each)
5. JSONL append (1 line)
6. JSON output to stdout

### Stop Hook

| Events | Latency |
|--------|---------|
| 7 events | ~50ms |
| 107 events | 54ms |
| 1000 events | 50ms |

The Stop hook is O(n) in events but the constant is tiny — even 1000 events barely register. JSONL parsing + set operations dominate.

### SessionStart Hook

| Features | Events | Latency | Output size |
|----------|--------|---------|-------------|
| 8 features | 0 | <50ms | ~2000 chars |
| 8 features | 1000 | 41ms | ~2080 chars |

Output size scales linearly with feature count (~260 chars/feature in the index table).

## Feature Mapping Accuracy

### Batch Test (16 paths across all features)

| Path | Expected Feature | Actual | Correct? |
|------|-----------------|--------|----------|
| `src/auth/middleware.py` | auth | auth | ✓ |
| `src/billing/stripe_client.py` | billing | billing | ✓ |
| `src/profile/avatar.py` | profile | profile | ✓ |
| `src/notifications/email.py` | notifications | notifications | ✓ |
| `src/notifications/push.py` | notifications | notifications | ✓ |
| `frontend/src/components/LoginForm.tsx` | frontend-auth | frontend-auth | ✓ |
| `frontend/src/components/Dashboard.tsx` | frontend-billing | frontend-billing | ✓ |
| `frontend/src/api/profile.ts` | frontend-profile | frontend-profile | ✓ |
| `app.py` | infrastructure | infrastructure | ✓ |
| `middleware/rate_limit.py` | infrastructure | infrastructure | ✓ |
| `models/__init__.py` | infrastructure | infrastructure | ✓ |
| `routes/notifications.py` | notifications | notifications | ✓ |
| `tests/test_notifications.py` | notifications | notifications | ✓ |
| `README.md` | (unmapped) | NONE | ✓ |
| `.gitignore` | (unmapped) | NONE | ✓ |
| `frontend/src/hooks/useApi.ts` | (unmapped) | NONE | ✓* |

**Accuracy: 16/16 correct** (100%)

*Note: `useApi.ts` is a shared utility used by multiple features. The system correctly reports it as unmapped rather than falsely assigning it. This is a design choice — shared utilities need explicit glob rules or a "shared" feature category.

### Edge Cases Identified

1. **Multi-feature files:** `frontend/src/hooks/useApi.ts` is used by all frontend features but belongs to none. Current behavior (unmapped) is safe but loses context.

2. **Same file edited twice in one session:** `useAuth.ts` got two events. The Stop hook correctly deduplicates (uses sets), so it reports "1 source file" not "2 edits."

3. **Glob pattern types:**
   - `src/auth/**` (directory glob) → works correctly
   - `routes/auth.py` (exact match) → works correctly
   - `frontend/src/components/LoginForm.tsx` (exact file) → works correctly
   - `models/**` (top-level directory glob) → works correctly
   - `app.py` (root-level exact) → works correctly

4. **Doc paths correctly excluded from source counts:** Edits to `docs/feature-memory/features/*.md` are categorized as doc paths and tracked separately for coverage analysis.

## Live Claude Code Session Behavior

### Context Injection Quality

The SessionStart hook's ~2000-char context message provides:
- Full feature list with summaries (useful for routing questions)
- Recent activity (helps agent understand what's been happening)
- Rules reminder (behavioral guardrails)

**Observation:** In `-p` mode, there's a "no stdin data received in 3s" warning. This is cosmetic — the hook handles empty input gracefully.

### Agent Response Quality (with FM context)

| Query | Quality | Grounded in source? | Used feature page? |
|-------|---------|--------------------|--------------------|
| "How does auth work?" | Excellent | Yes — cited exact functions | Likely (mentioned scaffolding nature) |
| "How does notification system work?" | Excellent | Yes — compared email vs push | Read all notification files |
| "Update auth docs for token refresh" | Excellent | Yes — verified actual code | Updated correct section |

### PostToolUse Reminder Effectiveness

When Claude edits a mapped file, the hook prints:
```
[FM] Edited 'src/auth/middleware.py' maps to feature(s): auth. Consider updating: docs/feature-memory/features/auth.md
```

**Observed behavior:** Claude does NOT automatically update docs after seeing this message (correct — it's a reminder, not an instruction). The user must explicitly ask for doc updates.

### Full Pipeline Flow

Tested: edit code → ask to update docs → verify Stop hook clears warning

1. Claude edits `src/auth/middleware.py` → event logged, reminder printed
2. User asks "update auth docs" → Claude reads auth.md, edits engineering summary
3. Stop hook → auth no longer in "needs update" list

**End-to-end latency:** Normal Claude response times. Hooks add negligible overhead.

## Scaling Observations

### Feature Count

With 8 features, the system is responsive and readable. Projected scaling:

| Features | Config parse | SessionStart output | Concern |
|----------|-------------|--------------------|---------| 
| 8 | ~50ms | ~2000 chars | None |
| 20 | ~60ms (est) | ~5000 chars | Output may get long |
| 50 | ~80ms (est) | ~13000 chars | Context window pressure |
| 100+ | ~100ms (est) | ~26000 chars | Too much for SessionStart |

**Recommendation:** For projects with >20 features, SessionStart should summarize (e.g., "42 features documented, 3 recently changed") rather than listing all.

### Events Accumulation

Events.jsonl grows unbounded within a session. At 1000 events the Stop hook still runs in 50ms, but the file size becomes a concern:

| Events | File size (est) | Stop hook time |
|--------|----------------|----------------|
| 100 | ~15 KB | 54ms |
| 1000 | ~150 KB | 50ms |
| 10000 | ~1.5 MB | ~100ms (est) |

**Recommendation:** Implement event rotation — either clear on session start or rotate when file exceeds a threshold.

## Issues Found

### Issue 1: Shared utility files are unmapped (Severity: Medium)

Files like `frontend/src/hooks/useApi.ts`, `frontend/src/types/index.ts`, `config.py` serve multiple features but may only map to one (or none).

**Current behavior:** Reported as "unmapped" by Stop hook.
**Impact:** User gets a "doesn't map to any feature" message for files that are clearly part of the system.

### Issue 2: No feature-level priority in Stop hook output (Severity: Low)

The Stop hook lists ALL features with gaps equally. With 8 features, "Consider updating feature docs for: auth, billing, frontend-auth, frontend-billing, frontend-profile, infrastructure, notifications, profile" is overwhelming.

**Ideal:** Prioritize by number of changes or recency.

### Issue 3: SessionStart shows absolute path (Severity: Low)

Still showing full `C:/Users/NTX/Desktop/GitHub/LLM-FM-TEST/docs/feature-memory` in context.

### Issue 4: No deduplication of PostToolUse reminders (Severity: Low)

If Claude edits `src/auth/login.py` 3 times in a session, the agent sees 3 identical reminders. After the first, subsequent reminders add no information.

### Issue 5: config.yaml parsed on every PostToolUse invocation (Severity: Low)

The YAML parser runs fresh every time a file is edited. For a ~96 line config this is negligible (part of the 47ms), but wasteful.
