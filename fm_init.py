#!/usr/bin/env python3
"""Feature Memory Phase 0 Initializer.

Single-file, zero-dependency script that bootstraps the Feature Memory system
in any project. Run from the project root:

    python fm_init.py [--project-name NAME] [--dry-run] [--force]

Creates:
  docs/feature-memory/       Feature documentation pages
  .feature-memory/           Config, events log, and hook scripts
  .claude/settings.json      Claude Code hook wiring
  .claude/skills/feature-memory/SKILL.md   FM skill definition
  CLAUDE.md                  Project instructions (appended if exists)
"""
import argparse
import json
import shutil
import sys
from datetime import date
from pathlib import Path

TODAY = date.today().isoformat()

# =============================================================================
# TEMPLATES
# =============================================================================

CLAUDE_MD_SNIPPET = f"""\

## Feature Memory

This repo uses Feature Memory under `docs/feature-memory/`. The `feature-memory` skill is available for maintaining feature documentation.

Before changing a major feature, read the relevant feature page if it exists under `docs/feature-memory/features/`.

After changing user-facing behavior, APIs, routes, data models, components, or tests, update the affected feature docs or invoke the `feature-memory` skill.

Do not reorganize feature hierarchy automatically. Write a proposal under `docs/feature-memory/reports/` instead.

**Phase 0 note:** The `fm` CLI is not yet available. Update feature docs manually.
"""

CONFIG_YAML_TEMPLATE = """\
schema_version: 1
project_name: {project_name}
docs_root: docs/feature-memory
mode: small

# Features are populated during initialization.
# Run "scan this project and create feature pages" in Claude to auto-populate.
features: {{}}

mapping:
  default_confidence: medium
  unmapped_policy: report
  route_patterns:
    - "routes/{{feature}}.py"
    - "src/routes/{{feature}}.ts"
  test_patterns:
    - "tests/test_*.py"
    - "**/*_test.*"
    - "**/*.test.*"

policy:
  automatic_writes:
    - timestamps
    - changelog_entries
    - source_maps
  review_required:
    - renames
    - moves
    - merges
    - hierarchy_changes
  never_automatic:
    - delete_raw_sources
    - delete_changelogs
    - erase_history

recent:
  days: 5
"""

INDEX_MD_TEMPLATE = f"""\
---
type: index
schema_version: 1
updated: "{TODAY}"
---

# Feature Memory Index

| Feature | Summary | Status | Review | Updated |
|---------|---------|--------|--------|---------|

<!-- Feature rows are added during initialization. -->
<!-- Run "scan this project and create feature pages" to populate. -->
"""

RECENT_MD_TEMPLATE = f"""\
---
type: recent
updated: "{TODAY}"
---

# Recent Activity

- {TODAY}: Feature Memory initialized (Phase 0 paper prototype)
"""

CHANGELOG_MD_TEMPLATE = f"""\
---
type: changelog
updated: "{TODAY}"
---

# Feature Memory Changelog

## {TODAY}

- **system**: Feature Memory initialized for this project (Phase 0 paper prototype)
"""

README_MD_TEMPLATE = """\
# Feature Memory

This directory contains compiled feature documentation maintained by the Feature Memory system.

## How it works

Feature Memory tracks which source files map to which product features. When code changes,
the system reminds the developer to update the relevant feature documentation.

## Phase 0 (Paper Prototype)

The `fm` CLI does not exist yet. Instead:
- Claude Code hooks track file edits and print reminders
- A skill (`.claude/skills/feature-memory/SKILL.md`) guides doc updates
- Feature docs are updated manually via Claude Code

## Directory structure

```
docs/feature-memory/
  index.md         Feature table (the "spine")
  recent.md        Recent activity log
  changelog.md     Append-only changelog
  README.md        This file
  features/        One page per feature
  reports/         Proposals for hierarchy changes
```

## Getting started

After running `fm_init.py`, open a Claude Code session and say:

> Scan this project and create feature pages

Claude will analyze your codebase, identify features, and write initial documentation.
"""

FM_COMMON = '''\
#!/usr/bin/env python3
"""Shared utilities for Feature Memory hooks.

Extracted to avoid code duplication across PostToolUse, Stop, and SessionStart hooks.
"""
import fnmatch
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def load_config(project_dir):
    """Load feature globs from config.yaml without requiring PyYAML."""
    config_path = project_dir / ".feature-memory" / "config.yaml"
    if not config_path.exists():
        return {}

    features = {}
    current_feature = None
    in_features = False
    in_globs = False

    for line in config_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()

        if stripped == "features:":
            in_features = True
            continue

        if in_features and not line.startswith(" ") and not line.startswith("\\t") and line.strip():
            in_features = False
            in_globs = False
            continue

        if in_features:
            if line.startswith("  ") and not line.startswith("    ") and stripped.endswith(":") and not stripped.startswith("-"):
                current_feature = stripped[:-1]
                features[current_feature] = []
                in_globs = False
                continue

            if stripped == "globs:":
                in_globs = True
                continue

            if in_globs and stripped.startswith("- "):
                glob_pattern = stripped[2:].strip()
                if current_feature:
                    features[current_feature].append(glob_pattern)
                continue

            if not stripped.startswith("- ") and ":" in stripped:
                in_globs = False

    if not features and config_path.stat().st_size > 50:
        log_error("YAML parse warning: config.yaml has content but no features were parsed. "
                  "Check indentation (must use 2-space indent).")

    return features


def match_path_to_features(file_path, features):
    """Match a file path against feature globs. Returns list of ALL matching feature IDs."""
    normalized = file_path.replace("\\\\", "/")
    matched = []

    for feature_id, globs in features.items():
        for pattern in globs:
            if pattern.endswith("/**"):
                prefix = pattern[:-3]
                if normalized.startswith(prefix + "/") or normalized == prefix:
                    matched.append(feature_id)
                    break
            elif fnmatch.fnmatch(normalized, pattern):
                matched.append(feature_id)
                break

    return matched


def generate_event_id():
    """Generate a unique event ID with timestamp and random suffix."""
    import random
    now = datetime.now(timezone.utc)
    suffix = f"{random.randint(0, 0xFFFF):04x}"
    return f"{now.strftime(\'%Y%m%dT%H%M%SZ\')}-{suffix}"


def log_error(message):
    """Log an error to .feature-memory/errors.log."""
    try:
        error_path = Path.cwd() / ".feature-memory" / "errors.log"
        with open(error_path, "a", encoding="utf-8") as f:
            f.write(f"{datetime.now(timezone.utc).isoformat()} {message}\\n")
    except Exception:
        pass


def hook_error_wrapper(hook_name, main_func):
    """Wrap a hook\'s main function with error handling."""
    try:
        main_func()
    except Exception as e:
        log_error(f"{hook_name} ERROR: {e}")
        output = {"result": "continue", "message": f"[FM] {hook_name} hook error: {e}"}
        json.dump(output, sys.stdout)
'''

SESSION_START_HOOK = '''\
#!/usr/bin/env python3
"""SessionStart hook (Phase 0): inject Feature Memory context and clear stale events."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from fm_common import hook_error_wrapper


def main():
    try:
        hook_input = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        hook_input = {}

    project_dir = Path.cwd()
    docs_root = project_dir / "docs" / "feature-memory"

    if not docs_root.exists():
        return

    # Truncate events from previous sessions
    events_path = project_dir / ".feature-memory" / "events.jsonl"
    if events_path.exists():
        events_path.write_text("", encoding="utf-8")

    lines = []
    lines.append("=== Feature Memory (Phase 0 - paper prototype) ===")
    rel_docs = docs_root.relative_to(project_dir).as_posix()
    lines.append(f"Docs root: {rel_docs}")
    lines.append("")

    index_path = docs_root / "index.md"
    if index_path.exists():
        index_content = index_path.read_text(encoding="utf-8")
        in_table = False
        feature_lines = []
        for line in index_content.splitlines():
            if line.startswith("| Feature"):
                in_table = True
                continue
            if in_table and line.startswith("|---"):
                continue
            if in_table and line.startswith("|"):
                feature_lines.append(line.strip())
            elif in_table:
                in_table = False
        if feature_lines:
            lines.append("Documented features:")
            for fl in feature_lines:
                lines.append(f"  {fl}")
            lines.append("")

    recent_path = docs_root / "recent.md"
    if recent_path.exists():
        recent_content = recent_path.read_text(encoding="utf-8")
        in_frontmatter = False
        content_lines = []
        for line in recent_content.splitlines():
            if line.strip() == "---":
                in_frontmatter = not in_frontmatter
                continue
            if not in_frontmatter:
                content_lines.append(line)
        if content_lines:
            lines.append("Recent activity:")
            for cl in content_lines[:10]:
                if cl.strip():
                    lines.append(f"  {cl}")
            lines.append("")

    lines.append("Rules: Update feature docs after changing user-facing behavior.")
    lines.append("       Do not reorganize hierarchy; write proposals to reports/.")
    lines.append("       The fm CLI is not yet available. Update docs manually.")

    output = {"result": "continue", "message": "\\n".join(lines)}
    json.dump(output, sys.stdout)


if __name__ == "__main__":
    hook_error_wrapper("SessionStart", main)
'''

POST_TOOL_HOOK = '''\
#!/usr/bin/env python3
"""PostToolUse hook (Phase 0): record edited paths and remind about feature docs."""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from fm_common import load_config, match_path_to_features, generate_event_id, hook_error_wrapper


def main():
    try:
        hook_input = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        return

    tool_name = hook_input.get("tool_name", "")
    tool_input = hook_input.get("tool_input", {})

    file_path = None
    if tool_name in ("Edit", "Write", "MultiEdit"):
        file_path = tool_input.get("file_path")

    if not file_path:
        return

    project_dir = Path.cwd()

    try:
        abs_path = Path(file_path).resolve()
        rel_path = abs_path.relative_to(project_dir.resolve()).as_posix()
    except (ValueError, OSError):
        try:
            rel_path = Path(os.path.relpath(file_path, project_dir)).as_posix()
        except ValueError:
            rel_path = Path(file_path).as_posix()

    now = datetime.now(timezone.utc)
    event = {
        "event_id": generate_event_id(),
        "created_at": now.isoformat(),
        "event_type": "path_touched",
        "source": "claude-hook",
        "path": rel_path,
        "session_id": hook_input.get("session_id", "unknown"),
    }

    events_path = project_dir / ".feature-memory" / "events.jsonl"
    try:
        with open(events_path, "a", encoding="utf-8", newline="") as f:
            f.write(json.dumps(event) + "\\n")
    except FileNotFoundError:
        pass

    features = load_config(project_dir)
    matched_features = match_path_to_features(rel_path, features)

    if matched_features:
        feature_list = ", ".join(matched_features)
        doc_paths = ", ".join(
            f"docs/feature-memory/features/{fid}.md" for fid in matched_features
        )
        output = {
            "result": "continue",
            "message": (
                f"[FM] Edited \'{rel_path}\' maps to feature(s): {feature_list}. "
                f"Consider updating: {doc_paths}"
            )
        }
        json.dump(output, sys.stdout)


if __name__ == "__main__":
    hook_error_wrapper("PostToolUse", main)
'''

STOP_HOOK = '''\
#!/usr/bin/env python3
"""Stop hook (Phase 0): check if touched source files have missing docs updates.

Filters events by current session_id and sorts output by change count.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from fm_common import load_config, match_path_to_features, hook_error_wrapper


def main():
    try:
        hook_input = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        hook_input = {}

    project_dir = Path.cwd()
    events_path = project_dir / ".feature-memory" / "events.jsonl"

    if not events_path.exists():
        return

    current_session = hook_input.get("session_id")

    events = []
    for line in events_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    if not events:
        return

    # Filter to current session if session_id is available
    if current_session:
        events = [e for e in events if e.get("session_id") == current_session]
        if not events:
            return

    touched_paths = set()
    doc_paths_touched = set()

    for event in events:
        if event.get("event_type") == "path_touched":
            path = event.get("path", "")
            if path.startswith("docs/feature-memory/"):
                doc_paths_touched.add(path)
            else:
                touched_paths.add(path)

    if not touched_paths:
        return

    features = load_config(project_dir)
    features_touched = {}
    unmapped_paths = []

    for path in touched_paths:
        matched = match_path_to_features(path, features)
        if matched:
            for fid in matched:
                features_touched.setdefault(fid, []).append(path)
        else:
            unmapped_paths.append(path)

    if not features_touched and not unmapped_paths:
        return

    messages = []
    features_needing_docs = []

    # Sort by change count (most impacted first)
    for fid, paths in sorted(features_touched.items(), key=lambda x: len(x[1]), reverse=True):
        doc_path = f"docs/feature-memory/features/{fid}.md"
        if doc_path not in doc_paths_touched:
            features_needing_docs.append((fid, len(paths)))
            messages.append(
                f"- Feature \'{fid}\': {len(paths)} source file(s) changed "
                f"but {doc_path} was not updated"
            )

    if unmapped_paths:
        messages.append(
            f"- {len(unmapped_paths)} file(s) edited that don\'t map to any feature: "
            + ", ".join(sorted(unmapped_paths)[:5])
        )

    if messages:
        summary = "[FM] Session documentation check:\\n" + "\\n".join(messages)
        if features_needing_docs:
            sorted_names = [f"{fid} ({count})" for fid, count in
                           sorted(features_needing_docs, key=lambda x: x[1], reverse=True)]
            summary += "\\n\\nConsider updating feature docs for: " + ", ".join(sorted_names)

        output = {"result": "continue", "message": summary}
        json.dump(output, sys.stdout)


if __name__ == "__main__":
    hook_error_wrapper("Stop", main)
'''

def get_python_command():
    """Determine the correct python command for this platform."""
    if sys.platform == "win32":
        return "python"
    if shutil.which("python3"):
        return "python3"
    if shutil.which("python"):
        return "python"
    return "python3"


def build_settings_json(python_cmd: str) -> str:
    """Generate settings.json content with the platform-appropriate python command."""
    return json.dumps({
        "hooks": {
            "SessionStart": [{
                "matcher": "",
                "hooks": [{
                    "type": "command",
                    "command": f"{python_cmd} .feature-memory/hooks/claude_session_start.py",
                    "timeout": 5000
                }]
            }],
            "PostToolUse": [{
                "matcher": "Edit|Write|MultiEdit",
                "hooks": [{
                    "type": "command",
                    "command": f"{python_cmd} .feature-memory/hooks/claude_post_tool.py",
                    "timeout": 3000
                }]
            }],
            "Stop": [{
                "matcher": "",
                "hooks": [{
                    "type": "command",
                    "command": f"{python_cmd} .feature-memory/hooks/claude_stop.py",
                    "timeout": 15000
                }]
            }]
        }
    }, indent=2)

SKILL_MD = """\
---
description: >
  Maintains Feature Memory docs for changed source files. Keeps product summaries,
  engineering summaries, source maps, relationships, and changelogs current.
  Use when the user asks about architecture, feature docs, repo memory, changelogs,
  or when code changes may affect docs.
allowed-tools: Bash, Read, Grep, Glob, Edit, Write
---

# Feature Memory Maintainer (Phase 0 - Paper Prototype)

## Live context

Feature Memory docs are at `docs/feature-memory/`. The `fm` CLI is not yet available.

## When to activate

- User asks about project architecture, features, or how something works
- User asks to update docs after a change
- Code changes affect user-facing behavior, APIs, routes, data models, or tests
- User mentions "feature memory", "docs update", "changelog", or "source map"
- After significant code changes that touch multiple files

## Instructions

You maintain `docs/feature-memory/` as a compiled memory layer for this repository.

### Phase 0 constraints

The `fm` CLI does not exist yet. Instead of running CLI commands:
- Read feature pages directly from `docs/feature-memory/features/`
- Check `.feature-memory/config.yaml` for feature-to-path mappings
- Update feature pages manually using Edit/Write tools
- Append to `docs/feature-memory/changelog.md` (never overwrite existing entries)

### Rules

1. Raw code and project sources are the source of truth. Never fabricate behavior claims.
2. Update only docs that are affected by the current change.
3. Keep product summaries short, direct, and useful to non-engineers.
4. Keep engineering summaries concise but source-grounded. Name files, routes, components, and tests.
5. Add or update source maps when files move or features change.
6. Append changelog entries. Never erase history.
7. Mark uncertain claims with `confidence: low` or `review_status: needs_review`.
8. Propose renames, moves, merges, and hierarchy changes in `docs/feature-memory/reports/`. Do not apply them automatically.
9. Cite source paths for every factual claim about code behavior.
10. **Verify before trusting**: If a feature page has `review_status: needs_review` or `stale`, or `confidence: low`, verify key claims against source files before relying on them.

### Suggested workflow (Phase 0)

1. Identify which files changed (read the diff or ask the user).
2. Check `.feature-memory/config.yaml` to map changed paths to features.
3. Read the affected feature pages under `docs/feature-memory/features/`.
4. Verify key claims against the current source code.
5. Update product summary, engineering summary, source map, and changelog only where needed.
6. Update `docs/feature-memory/index.md` if a feature's summary or status changed.
7. Update `docs/feature-memory/recent.md` with today's changes.
8. Summarize what changed and what could not be verified.

### Initialization mode (run after fm_init.py)

When the user says "initialize feature memory", "scan this project and create feature pages",
or "set up feature memory docs", follow this workflow:

1. **Inventory the project** using Glob:
   - Find top-level source directories: `src/*`, `app/*`, `lib/*`, `packages/*`
   - Find route/controller files: `**/routes/**`, `**/controllers/**`, `**/api/**`
   - Find test directories: `tests/**`, `__tests__/**`, `*.test.*`, `*_test.*`
   - Find config files: `package.json`, `pyproject.toml`, `Cargo.toml`, `go.mod`

2. **Identify features** by heuristic:
   - Each immediate subdirectory of `src/` (or equivalent) is likely a feature
   - Each route file that groups endpoints under a namespace is likely a feature
   - Group related test files with their source directories
   - Read README.md or similar docs for feature names mentioned by humans

3. **Propose features to the user** before writing anything:
   - List each proposed feature with: id (slug), title, source globs
   - Ask "Should I create feature pages for these? Add or remove any?"
   - Wait for confirmation

4. **For each confirmed feature**, create `docs/feature-memory/features/{id}.md`:
   - Read the key source files (limit to first 100 lines each for efficiency)
   - Write frontmatter matching the schema (title, status, confidence, updated, etc.)
   - Write one-sentence summary, product summary, engineering summary
   - Build source map table from actual files found
   - Mark `confidence: medium`, `review_status: needs_review`
   - Add placeholder sections for relationships, gaps, questions

5. **Update config.yaml**: Add each feature to the `features:` section with its globs.

6. **Update index.md**: Add a row per feature to the table.

7. **Update recent.md**: Add today's initialization entries.

8. **Update changelog.md**: Add "Initial documentation" entries per feature.

9. **Report completion**: Summarize what was created and suggest next steps
   (e.g., "Review the feature pages and update confidence to 'high' after verification").
"""

GITATTRIBUTES = """\
# Feature Memory: ensure consistent line endings for event logs
*.jsonl text eol=lf
*.py text eol=lf
*.yaml text eol=lf
*.yml text eol=lf
*.md text eol=lf
"""

# =============================================================================
# FILE MAP
# =============================================================================

TEMPLATES = {
    "docs/feature-memory/index.md": INDEX_MD_TEMPLATE,
    "docs/feature-memory/recent.md": RECENT_MD_TEMPLATE,
    "docs/feature-memory/changelog.md": CHANGELOG_MD_TEMPLATE,
    "docs/feature-memory/README.md": README_MD_TEMPLATE,
    "docs/feature-memory/features/.gitkeep": "",
    "docs/feature-memory/reports/.gitkeep": "",
    ".feature-memory/events.jsonl": "",
    ".feature-memory/reports/.gitkeep": "",
    ".feature-memory/hooks/fm_common.py": FM_COMMON,
    ".feature-memory/hooks/claude_session_start.py": SESSION_START_HOOK,
    ".feature-memory/hooks/claude_post_tool.py": POST_TOOL_HOOK,
    ".feature-memory/hooks/claude_stop.py": STOP_HOOK,
    ".claude/skills/feature-memory/SKILL.md": SKILL_MD,
}


# =============================================================================
# LOGIC
# =============================================================================

def merge_settings_json(project_dir: Path, python_cmd: str, dry_run: bool = False, force: bool = False) -> tuple:
    """Merge FM hooks into existing settings.json. Returns (path, action)."""
    settings_path = project_dir / ".claude" / "settings.json"
    new_settings = json.loads(build_settings_json(python_cmd))

    if not settings_path.exists():
        if not dry_run:
            settings_path.parent.mkdir(parents=True, exist_ok=True)
            settings_path.write_text(json.dumps(new_settings, indent=2) + "\n", encoding="utf-8")
        return ".claude/settings.json", "created"

    if force:
        if not dry_run:
            settings_path.write_text(json.dumps(new_settings, indent=2) + "\n", encoding="utf-8")
        return ".claude/settings.json", "overwritten"

    existing = json.loads(settings_path.read_text(encoding="utf-8"))
    added_any = False

    if "hooks" not in existing:
        existing["hooks"] = new_settings["hooks"]
        added_any = True
    else:
        for hook_type, hook_entries in new_settings["hooks"].items():
            if hook_type not in existing["hooks"]:
                existing["hooks"][hook_type] = hook_entries
                added_any = True
            else:
                existing_commands = set()
                for entry in existing["hooks"][hook_type]:
                    for h in entry.get("hooks", []):
                        existing_commands.add(h.get("command", ""))
                for entry in hook_entries:
                    cmd = entry["hooks"][0]["command"]
                    if cmd not in existing_commands:
                        existing["hooks"][hook_type].append(entry)
                        added_any = True

    if not added_any:
        return ".claude/settings.json", "skipped (hooks already present)"

    if not dry_run:
        settings_path.write_text(json.dumps(existing, indent=2) + "\n", encoding="utf-8")
    return ".claude/settings.json", "merged"


def handle_claude_md(project_dir: Path, dry_run: bool = False, force: bool = False) -> tuple:
    """Handle CLAUDE.md: append FM section if not present, create if missing."""
    claude_md = project_dir / "CLAUDE.md"

    if claude_md.exists():
        existing = claude_md.read_text(encoding="utf-8")
        if "Feature Memory" in existing and not force:
            return "CLAUDE.md", "skipped (already has FM section)"
        if not dry_run:
            if force or "Feature Memory" not in existing:
                new_content = existing.rstrip() + "\n" + CLAUDE_MD_SNIPPET
                claude_md.write_text(new_content, encoding="utf-8")
        return "CLAUDE.md", "appended FM section"
    else:
        content = "# Project Instructions\n" + CLAUDE_MD_SNIPPET
        if not dry_run:
            claude_md.write_text(content, encoding="utf-8")
        return "CLAUDE.md", "created"


def handle_gitattributes(project_dir: Path, dry_run: bool = False, force: bool = False) -> tuple:
    """Handle .gitattributes: append FM entries if not present."""
    ga_path = project_dir / ".gitattributes"

    if ga_path.exists():
        existing = ga_path.read_text(encoding="utf-8")
        if "*.jsonl" in existing and not force:
            return ".gitattributes", "skipped (already has JSONL rule)"
        if not dry_run:
            new_content = existing.rstrip() + "\n\n" + GITATTRIBUTES
            ga_path.write_text(new_content, encoding="utf-8")
        return ".gitattributes", "appended FM rules"
    else:
        if not dry_run:
            ga_path.write_text(GITATTRIBUTES, encoding="utf-8")
        return ".gitattributes", "created"


def handle_config_yaml(project_dir: Path, project_name: str, dry_run: bool = False, force: bool = False) -> tuple:
    """Handle config.yaml with project name substitution."""
    config_path = project_dir / ".feature-memory" / "config.yaml"
    existed = config_path.exists()

    if existed and not force:
        return ".feature-memory/config.yaml", "skipped (already exists)"

    content = CONFIG_YAML_TEMPLATE.replace("{project_name}", project_name)
    # Unescape the double braces used to protect {feature} from .format()
    content = content.replace("{{", "{").replace("}}", "}")

    if not dry_run:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(content, encoding="utf-8")
    return ".feature-memory/config.yaml", "overwritten" if existed else "created"


def main():
    parser = argparse.ArgumentParser(
        description="Initialize Feature Memory Phase 0 in a project.",
        epilog="After running, open Claude Code and say: 'Scan this project and create feature pages'",
    )
    parser.add_argument(
        "--project-name",
        default=None,
        help="Project name slug (defaults to directory basename)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be created without writing anything",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing files (normally they are skipped)",
    )
    args = parser.parse_args()

    project_dir = Path.cwd()
    project_name = args.project_name or project_dir.name.lower().replace(" ", "-")
    python_cmd = get_python_command()

    print(f"Feature Memory Init — project: {project_name}")
    print(f"Python command: {python_cmd}")
    if args.dry_run:
        print("(DRY RUN — no files will be written)\n")
    else:
        print()

    results = []

    # 1. Create template files
    for rel_path, content in TEMPLATES.items():
        abs_path = project_dir / rel_path
        existed = abs_path.exists()
        if existed and not args.force:
            results.append((rel_path, "skipped"))
        else:
            if not args.dry_run:
                abs_path.parent.mkdir(parents=True, exist_ok=True)
                with open(abs_path, "w", encoding="utf-8", newline="\n" if rel_path.endswith(".jsonl") else None) as f:
                    f.write(content)
            action = "overwritten" if existed else "created"
            results.append((rel_path, action))

    # 2. Handle config.yaml (needs project_name substitution)
    results.append(handle_config_yaml(project_dir, project_name, args.dry_run, args.force))

    # 3. Handle settings.json (merge logic, platform-aware python command)
    results.append(merge_settings_json(project_dir, python_cmd, args.dry_run, args.force))

    # 4. Handle CLAUDE.md (append logic)
    results.append(handle_claude_md(project_dir, args.dry_run, args.force))

    # 5. Handle .gitattributes
    results.append(handle_gitattributes(project_dir, args.dry_run, args.force))

    # Print summary
    created = [(p, a) for p, a in results if a not in ("skipped", ) and "skipped" not in a]
    skipped = [(p, a) for p, a in results if a == "skipped" or "skipped" in a]

    if created:
        print("Created/Modified:")
        for path, action in created:
            print(f"  {path} ({action})")
    print()

    if skipped:
        print("Skipped (already exist):")
        for path, action in skipped:
            print(f"  {path}")
    print()

    print("=" * 50)
    print("Next steps:")
    print("  1. Open a Claude Code session in this project")
    print('  2. Say: "Scan this project and create feature pages"')
    print("  3. Claude will identify features and write initial docs")
    print("  4. Review generated pages and update confidence levels")
    print()
    if args.dry_run:
        print("(No files were written — run without --dry-run to apply)")
    else:
        print("Done! Feature Memory Phase 0 is ready.")


if __name__ == "__main__":
    main()
