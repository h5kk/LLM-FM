# Spec 11: What's New Generator (Optional)

## Overview

An optional FM extension that generates user-friendly "What's New" / release notes entries when feature docs are updated. Disabled by default. When enabled, the Stop hook or skill suggests a What's New entry after detecting user-facing changes.

## Design

### Principle

Feature Memory already knows *what* changed (feature pages, changelogs). The What's New generator is a **view layer** on top of that — it transforms internal engineering changelogs into user-facing release notes following configurable editorial guidelines.

### Architecture

```
                    ┌──────────────────────┐
                    │  Feature Change      │
                    │  (code edit + docs)  │
                    └──────┬───────────────┘
                           │
                    ┌──────▼───────────────┐
                    │  FM Changelog Entry   │ ← already exists
                    │  (engineering-facing) │
                    └──────┬───────────────┘
                           │
              ┌────────────▼────────────────┐
              │  What's New Filter          │
              │  (editorial guidelines)     │
              │                             │
              │  Include? Y/N               │
              │  Category: new|improved|fix │
              │  Featured? Y/N              │
              │  Needs demo? Y/N            │
              └────────────┬────────────────┘
                           │
              ┌────────────▼────────────────┐
              │  What's New Entry           │
              │  (user-facing, marketing)   │
              │                             │
              │  Title, description,        │
              │  category, expanded body,   │
              │  highlights, action link    │
              └─────────────────────────────┘
```

### Config Extension

In `.feature-memory/config.yaml`:

```yaml
whats_new:
  enabled: false                          # opt-in, disabled by default
  output: docs/feature-memory/whats-new.md  # or .json/.ts for app integration
  format: markdown                        # markdown | json | typescript
  max_entries: 40                         # prune when exceeding this
  archive: docs/feature-memory/whats-new-archive.md
  
  editorial:
    include:
      - new user-facing features
      - meaningful redesigns
      - bugs users would actually hit
      - core flow improvements
    exclude:
      - admin/developer-only changes
      - edge cases affecting <5% of users
      - invisible polish (padding, colors, tooltips)
      - infrastructure that signals unreliability
      - vague backend improvements users can't see
    featured_ratio: 0.2                   # ~20% of entries
    
  entry_template:                         # fields per entry
    id: "{date}-{slug}"
    date: "{date}"
    title: "Short user-facing title"
    description: "One sentence, user perspective, no jargon."
    category: "new | improved | fixed"
    featured: false
    expanded:
      body: "Longer explanation (optional)"
      highlights: []
      action_label: ""
      action_url: ""
```

### Output Formats

#### Markdown (default)

```markdown
# What's New

## 2026-05-17 — Token Refresh ⭐
**Category:** improved

Login sessions now automatically refresh before expiring, so you won't get logged out mid-workflow.

<details>
<summary>More details</summary>

- Backend validates and reissues JWT tokens 5 minutes before expiry
- Frontend auto-refreshes in the background — no user action needed
- Failed refreshes gracefully redirect to login

[Try it →](/login)
</details>

---

## 2026-05-16 — Push Notifications
**Category:** new

Get real-time order updates on your phone. Supports iOS, Android, and web push.
```

#### JSON (for app integration)

```json
[
  {
    "id": "2026-05-17-token-refresh",
    "date": "2026-05-17",
    "title": "Token Refresh",
    "description": "Login sessions now automatically refresh before expiring.",
    "category": "improved",
    "featured": true,
    "expanded": {
      "body": "Backend validates and reissues JWT tokens...",
      "highlights": [
        "Auto-refresh 5 min before expiry",
        "Background refresh, no user action"
      ],
      "actionLabel": "Try it",
      "actionUrl": "/login"
    }
  }
]
```

#### TypeScript (for React apps)

```typescript
import type { ChangelogEntry } from './changelog-types'

export const entries: ChangelogEntry[] = [
  {
    id: "2026-05-17-token-refresh",
    date: "2026-05-17",
    title: "Token Refresh",
    description: "Login sessions now automatically refresh before expiring.",
    category: "improved",
    featured: true,
    expanded: {
      body: "Backend validates and reissues JWT tokens...",
      highlights: [
        "Auto-refresh 5 min before expiry",
        "Background refresh, no user action",
      ],
      actionLabel: "Try it",
      actionUrl: "/login",
    },
  },
]
```

### Skill Integration

Add to SKILL.md workflow:

```markdown
### What's New (optional, when enabled in config.yaml)

After updating feature docs, if `whats_new.enabled` is true in config.yaml:

1. **Apply editorial filter**: Does this change pass the include/exclude criteria?
   - New user-facing feature → yes
   - Bug fix users would notice → yes
   - Internal refactor → no (skip)
   - CSS padding tweak → no (skip)

2. **If yes**, draft a What's New entry:
   - **Title**: 3-6 words, user perspective ("Faster Checkout", not "Refactored billing pipeline")
   - **Description**: One sentence, no jargon, answers "what changed for me?"
   - **Category**: `new` (didn't exist before), `improved` (existing feature got better), `fixed` (broken thing works now)
   - **Featured?**: Only if it's a headline-worthy change (~20% of entries)
   - **Expanded** (optional): highlights list, action link to try it

3. **Append** to the What's New file (markdown/JSON/TS per config)

4. **Prune** if exceeding max_entries: move oldest non-featured entries to archive
```

### Hook Integration

The Stop hook can suggest What's New entries:

```
[FM] Session documentation check:
- Feature 'auth': 2 source file(s) changed, docs updated ✓
  💡 What's New candidate: token refresh is user-facing (auto-refresh before expiry)
```

This is a hint, not automatic generation. The user or skill decides whether to write the entry.

### Phase 0 Implementation

Since the `fm` CLI doesn't exist, the What's New generator is purely skill-driven:

1. Add `whats_new` section to config.yaml (disabled by default)
2. Add What's New workflow section to SKILL.md
3. Create empty `docs/feature-memory/whats-new.md` template
4. When user says "generate what's new" or "write release notes", the skill:
   - Reads recent changelog entries from `docs/feature-memory/changelog.md`
   - Applies editorial filter from config
   - Drafts entries and appends to what's-new file
   - Asks user to confirm/edit before finalizing

### Phase 1 (CLI) Implementation

```bash
fm whats-new                    # generate from recent changes
fm whats-new --since v1.2.0     # since a git tag
fm whats-new --format json      # override output format
fm whats-new --prune            # archive entries past max_entries
fm whats-new --review           # show draft without writing
```

### Editorial Guidelines (Embedded)

The skill carries these guidelines in its instructions:

**INCLUDE** when:
- New user-facing feature (new segment type, new import format, new panel)
- Meaningful redesign of existing surface
- Bug fix users would actually notice (wrong data, broken workflow, crash)
- Core flow improvement (email parsing accuracy, calendar sync reliability)

**DO NOT INCLUDE** when:
- Admin/developer-only change (API internals, worker config, DI wiring)
- Edge case affecting <5% of users (specific device quirks, settings layout)
- Invisible polish (padding, border-radius, tooltip wording, color tweaks)
- Redundant — if a newer entry covers the same thing, remove the older one
- Infrastructure that signals unreliability (outage banners, error handling)
- Vague backend improvements users can't see ("smarter AI", "faster parsing")

**FEATURED** (~20% of entries):
- New platforms, headline features, major redesigns
- Shows emphasis (star icon, gradient border, etc.)
- If everything is featured, nothing is

**ENTRY QUALITY**:
- Title: user's perspective, not engineer's ("Faster Checkout" not "Optimized billing pipeline")
- Description: one sentence, no jargon, answers "what changed for me?"
- Highlights: 2-4 bullet points of key improvements
- Action: link to where the user can try the feature

### Questions for Future Design

1. Should What's New entries link back to feature pages? (Yes — for teams that want internal traceability)
2. Should there be a "preview" mode that generates entries without writing? (Yes — via `--review` flag or skill confirmation step)
3. Should the Stop hook auto-detect user-facing changes? (Heuristic: if routes/components changed, it's likely user-facing. If only models/middleware, probably not.)
4. Should entries support i18n? (Defer — not Phase 0/1 scope)
