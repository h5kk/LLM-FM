# Spec 09 — Examples and User Documentation

> Arch plan refs: none (new content)

## Objective

Create example repos, a quickstart tutorial, the project README, and a user guide outline so new users can adopt Feature Memory quickly.

---

## 1. Quickstart tutorial

Write as `docs/guide/quickstart.md`. Target: a developer who has never seen FM, going from zero to a working setup in 10 minutes.

### Steps

```markdown
# Quickstart

## 1. Install

```bash
pip install feature-memory
```

Verify:

```bash
fm --version
```

## 2. Initialize

Navigate to your project root and run:

```bash
fm init --project-name my-app
```

This creates:
- `docs/feature-memory/` — your compiled feature docs
- `.feature-memory/` — config, cache, and metadata

## 3. Write your first feature page

Create `docs/feature-memory/features/auth.md`:

```markdown
---
type: feature
schema_version: 1
feature_id: auth
slug: auth
title: Auth
status: active
created: 2026-05-17
updated: 2026-05-17
confidence: medium
review_status: needs_review
source_paths:
  - src/auth/
---

# Auth

## One-sentence summary

Handles user sign-in, sign-out, and session management.

## Product / business summary

Auth is the gate into the product. Users sign in with email/password.

## Engineering summary

Login form at `src/auth/LoginForm.tsx` calls the API at `src/routes/auth.ts`.

## Source map

| Path | Kind | Role | Confidence | Last verified |
|------|------|------|------------|---------------|
| src/auth/LoginForm.tsx | ui-component | Login UI | high | 2026-05-17 |
| src/routes/auth.ts | api-route | Auth API | high | 2026-05-17 |

## Recent changes

- 2026-05-17 — Initial feature page created.
```

## 4. Detect and map changes

Make a code change, commit it, then:

```bash
fm detect --diff HEAD~1..HEAD --json
fm map --paths src/auth/LoginForm.tsx --json
```

## 5. Run lint

```bash
fm lint
```

Fix any findings.

## 6. Set up the skill (Claude Code)

The `feature-memory` skill is included. When you ask about features or make changes, Claude will use it to maintain your docs.

## 7. Set up hooks (optional)

```bash
fm hooks install --method lefthook
```

This adds git hooks to run lint on commit and draft-ingest on post-commit.

## 8. Next steps

- Add more feature pages for your project's main features
- Run `fm ingest --diff HEAD~5..HEAD --no-llm` to backfill recent changes
- Read the [configuration reference](config-reference.md) to customize mapping rules
```

---

## 2. Example repo: simple-app

### Purpose

A minimal example showing FM working with a small project (3 features, 10 files).

### Location

`examples/simple-app/`

### Structure

```
examples/simple-app/
  README.md                            # how to use this example
  src/
    auth/
      login.py                         # simple login function
      logout.py                        # simple logout function
    billing/
      checkout.py                      # checkout flow
      invoice.py                       # invoice generation
    profile/
      settings.py                      # user settings
  tests/
    test_auth.py
    test_billing.py
  routes/
    auth.py                            # auth API route
    billing.py                         # billing API route

  docs/feature-memory/
    index.md                           # populated index with 3 features
    recent.md                          # recent activity
    changelog.md                       # sample changelog entries
    features/
      auth.md                          # complete auth feature page
      billing.md                       # complete billing feature page
      profile.md                       # complete profile feature page

  .feature-memory/
    config.yaml                        # configured with globs and route patterns
```

### Example README

```markdown
# Simple App — Feature Memory Example

This is a minimal example showing Feature Memory in action.

## Setup

```bash
cd examples/simple-app
pip install feature-memory
```

## Try it

```bash
# See the feature index
cat docs/feature-memory/index.md

# Read a feature page
cat docs/feature-memory/features/auth.md

# Detect changes (make a change first)
echo "# modified" >> src/auth/login.py
git add . && git commit -m "modify auth"
fm detect --diff HEAD~1..HEAD --json

# Map changed paths to features
fm map --paths src/auth/login.py --json

# Run lint
fm lint

# Ingest changes
fm ingest --diff HEAD~1..HEAD --no-llm
```
```

### Config

```yaml
schema_version: 1
project_name: simple-app
docs_root: docs/feature-memory
mode: small

features:
  auth:
    title: Auth
    globs:
      - src/auth/**
      - routes/auth.py
  billing:
    title: Billing
    globs:
      - src/billing/**
      - routes/billing.py
  profile:
    title: Profile
    globs:
      - src/profile/**

mapping:
  default_confidence: medium
  unmapped_policy: report
  route_patterns:
    - routes/{feature}.py
  test_patterns:
    - tests/test_*.py
```

---

## 3. Example repo: monorepo

### Purpose

Show how FM handles a multi-app project with shared packages.

### Location

`examples/monorepo/`

### Structure

```
examples/monorepo/
  README.md
  apps/
    web/
      src/
        auth/
          LoginForm.tsx
          RegisterForm.tsx
        billing/
          Checkout.tsx
          PricingTable.tsx
    api/
      src/
        routes/
          auth.ts
          billing.ts
        middleware/
          session.ts
  packages/
    shared/
      src/
        types/
          user.ts
          billing.ts
        utils/
          validation.ts

  docs/feature-memory/
    index.md
    recent.md
    changelog.md
    features/
      auth/
        index.md                       # split mode: full feature with sub-pages
        product.md
        engineering.md
        source-map.md
      billing.md                       # small mode: single file

  .feature-memory/
    config.yaml
```

### Config

```yaml
schema_version: 1
project_name: monorepo-example
docs_root: docs/feature-memory
mode: mixed

features:
  auth:
    title: Auth
    globs:
      - apps/web/src/auth/**
      - apps/api/src/routes/auth.ts
      - apps/api/src/middleware/session.ts
  billing:
    title: Billing
    globs:
      - apps/web/src/billing/**
      - apps/api/src/routes/billing.ts
      - packages/shared/src/types/billing.ts

mapping:
  default_confidence: medium
  unmapped_policy: create_draft
  route_patterns:
    - apps/api/src/routes/{feature}.ts
    - apps/web/src/app/{feature}/**
  test_patterns:
    - "**/*.test.ts"
    - "**/*.test.tsx"
    - "**/*.spec.ts"
```

---

## 4. Project README

### Location

`README.md` at repo root.

### Structure

```markdown
# Feature Memory

A documentation compiler that maintains feature-level memory for software projects.

Feature Memory watches project activity, maps changed files to product features, and maintains a persistent markdown memory layer with product summaries, engineering summaries, source maps, changelogs, and review reports.

## Install

```bash
pip install feature-memory
```

## Quick start

```bash
# Initialize in your project
fm init

# Write a feature page (or let the agent do it)
# ... edit docs/feature-memory/features/auth.md

# After making code changes
fm detect --diff HEAD~1..HEAD
fm ingest --diff HEAD~1..HEAD --no-llm
fm lint
```

## What it does

For every meaningful feature in your project, FM maintains:

- A **product summary** (for PMs, designers, new engineers)
- An **engineering summary** (for developers, with file paths and routes)
- A **source map** linking code files to features
- A **changelog** of what changed and when
- **Relationship notes** connecting features to each other
- **Review status** and confidence scores

## Agent integration

FM includes skills and hooks for [Claude Code](https://claude.com/claude-code) and [Codex](https://platform.openai.com/codex):

- **Skills** teach the agent how to maintain feature docs
- **Hooks** trigger updates near the moment of code change
- **Plugins** package everything for easy installation

## CLI commands

| Command | Description |
|---------|-------------|
| `fm init` | Initialize Feature Memory in a project |
| `fm detect` | Detect changed files from a diff |
| `fm map` | Map file paths to features |
| `fm ingest` | Update feature docs from changes |
| `fm lint` | Check docs for issues |
| `fm review` | Review docs for accuracy |
| `fm context` | Print context for agent injection |
| `fm query` | Search feature docs |

## Documentation

- [Quickstart](docs/guide/quickstart.md)
- [Configuration Reference](docs/guide/config-reference.md)
- [CLI Reference](docs/guide/cli-reference.md)
- [Implementation Specs](docs/specs/README.md)

## License

MIT
```

---

## 5. User guide outline

### Location

`docs/guide/`

### Documents

| Document | Content |
|----------|---------|
| `quickstart.md` | 10-minute setup tutorial (section 1 above) |
| `concepts.md` | What is Feature Memory, how it works, key terms |
| `config-reference.md` | Every config.yaml field, with examples |
| `cli-reference.md` | Every fm command with all flags, examples, exit codes |
| `skill-setup.md` | How to set up the Claude/Codex skill |
| `hook-setup.md` | How to set up lifecycle and git hooks |
| `plugin-install.md` | How to install the plugin from marketplace or local |
| `writing-feature-pages.md` | Guide to writing good feature pages |
| `faq.md` | Common questions and troubleshooting |

### Each guide page format

```markdown
# {Title}

{1-2 sentence overview}

## Prerequisites

{what you need before this guide}

## Steps

{numbered steps with code examples}

## Verification

{how to confirm it worked}

## Troubleshooting

{common issues and fixes}
```

---

## 6. API documentation

Generate CLI reference automatically:

```python
# scripts/generate_cli_docs.py
"""Generate CLI reference docs from click commands."""
import click
from fm.cli import main

def generate_docs(group, prefix="fm"):
    for name, cmd in group.commands.items():
        full_name = f"{prefix} {name}"
        print(f"## `{full_name}`\n")
        print(f"{cmd.help or ''}\n")
        for param in cmd.params:
            if isinstance(param, click.Option):
                print(f"- `{param.opts[0]}`: {param.help or ''}")
        print()
```

---

## Key deliverables

- [ ] Quickstart tutorial (`docs/guide/quickstart.md`)
- [ ] Simple-app example (`examples/simple-app/`) with 3 features, config, and populated docs
- [ ] Monorepo example (`examples/monorepo/`) with multi-app structure and mixed mode
- [ ] Project README.md
- [ ] User guide outline with 9 guide documents defined
- [ ] CLI reference generation script
- [ ] Both examples are self-contained and runnable
