# Spec 01 — CLI Foundation

> **Status:** Draft / not implemented in v0.6.0.  
> The plugin uses skills (see [Spec 05](05-skills.md)) as its primary surface.  
> This spec describes a planned `fm` CLI that does not yet ship with the plugin.

> Arch plan refs: sections 6 (CLI design), 7 (configuration)

## Objective

Implement the CLI framework, global option handling, output formatting utilities, and configuration loading so that all future commands have a consistent foundation.

## 1. CLI framework

Use `click` as the CLI framework. The top-level group is `fm` (defined in spec 00). Subcommands are registered via `@main.command()` or `@main.group()` in their respective modules.

### Command registration pattern

Each command module exposes a click command or group. Registration happens in `cli.py`:

```python
# src/fm/cli.py
from fm.commands import (
    init, detect, map, ingest, lint, review, propose,
    context, query, recent, changelog, export, source_map, index, hooks,
)

main.add_command(init.cmd)
main.add_command(detect.cmd)
main.add_command(map.cmd)
main.add_command(ingest.cmd)
main.add_command(lint.cmd)
main.add_command(review.cmd)
main.add_command(propose.cmd)       # fm propose-reorg + fm apply-proposal
main.add_command(context.cmd)
main.add_command(query.cmd)
main.add_command(recent.cmd)
main.add_command(changelog.cmd)
main.add_command(export.cmd)
main.add_command(source_map.cmd)    # fm source-map
main.add_command(index.cmd)         # fm index rebuild
main.add_command(hooks.cmd)         # fm hooks install
```

Command modules live in `src/fm/commands/`:

```
src/fm/commands/
  __init__.py
  init.py
  detect.py
  map.py
  ingest.py
  lint.py
  review.py
  propose.py
  context.py
  query.py
  recent.py
  changelog.py
  export.py
  source_map.py
  index.py
  hooks.py
```

## 2. Global options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--json` | flag | false | Emit structured JSON to stdout |
| `--verbose` / `-v` | flag | false | Extra diagnostic output to stderr |
| `--quiet` / `-q` | flag | false | Suppress non-essential output |
| `--docs-root` | path | auto-discovered | Override Feature Memory docs directory |
| `--config` | path | auto-discovered | Override `.feature-memory/config.yaml` path |
| `--dry-run` | flag | false | Show what would change without writing |

Global options are stored in `click.Context.obj` and accessed by subcommands via `@click.pass_context`.

## 3. Output format contract

### JSON output (`--json`)

All commands that produce structured data support `--json`. The JSON envelope:

```json
{
  "status": "ok",
  "command": "detect",
  "data": { ... },
  "warnings": [],
  "errors": []
}
```

On error:

```json
{
  "status": "error",
  "command": "detect",
  "data": null,
  "errors": [
    { "code": "FM_CONFIG_NOT_FOUND", "message": "No .feature-memory/config.yaml found." }
  ],
  "warnings": []
}
```

### Human output (default)

Use `rich` for formatted terminal output. Structured data renders as tables or trees. Diagnostics go to stderr, data goes to stdout.

### Output utility module

`src/fm/output.py`:

```python
import json
import sys
from dataclasses import dataclass, field
from typing import Any

from rich.console import Console

err_console = Console(stderr=True)
out_console = Console()


@dataclass
class Result:
    status: str = "ok"
    command: str = ""
    data: Any = None
    warnings: list[str] = field(default_factory=list)
    errors: list[dict[str, str]] = field(default_factory=list)

    def emit(self, json_output: bool) -> None:
        if json_output:
            json.dump(
                {
                    "status": self.status,
                    "command": self.command,
                    "data": self.data,
                    "warnings": self.warnings,
                    "errors": self.errors,
                },
                sys.stdout,
                indent=2,
                default=str,
            )
            sys.stdout.write("\n")
        else:
            if self.errors:
                for e in self.errors:
                    err_console.print(f"[red]error:[/red] {e['message']}")
            if self.warnings:
                for w in self.warnings:
                    err_console.print(f"[yellow]warning:[/yellow] {w}")
```

## 4. Configuration loading

### Discovery algorithm

1. If `--config` is provided, use that path exactly.
2. Otherwise, walk up from the current working directory looking for `.feature-memory/config.yaml`.
3. If not found, commands that require config fail with exit code 1 and error `FM_CONFIG_NOT_FOUND`.
4. `fm init` does not require config (it creates it).

### Config model

`src/fm/config.py`:

```python
from pathlib import Path
from pydantic import BaseModel, Field


class FeatureConfig(BaseModel):
    title: str
    globs: list[str] = []
    owner: str = "unknown"
    status: str = "active"


class MappingConfig(BaseModel):
    default_confidence: str = "medium"
    unmapped_policy: str = "create_draft"
    route_patterns: list[str] = []
    test_patterns: list[str] = ["**/*.test.ts", "**/*.spec.ts", "**/*.test.py", "**/*_test.py"]


class PolicyConfig(BaseModel):
    automatic_writes: list[str] = [
        "timestamps", "changelog_entries", "source_maps",
        "index_summaries", "draft_feature_pages", "backlinks",
    ]
    review_required: list[str] = [
        "renames", "moves", "merges", "hierarchy_changes",
        "deprecations", "product_positioning_rewrites",
    ]
    never_automatic: list[str] = [
        "delete_raw_sources", "delete_changelogs", "erase_history",
        "silently_resolve_contradictions",
    ]


class RecentConfig(BaseModel):
    days: int = 5


class LlmConfig(BaseModel):
    provider: str = "auto"
    model: str = "auto"
    summary_max_tokens: int = 800
    reviewer_model: str = "auto"


class PrivacyConfig(BaseModel):
    redact_patterns: list[str] = [
        r"(?i)api[_-]?key",
        r"(?i)secret",
        r"(?i)token",
    ]


class FmConfig(BaseModel):
    schema_version: int = 1
    project_name: str = ""
    docs_root: str = "docs/feature-memory"
    mode: str = "mixed"
    features: dict[str, FeatureConfig] = {}
    mapping: MappingConfig = MappingConfig()
    policy: PolicyConfig = PolicyConfig()
    recent: RecentConfig = RecentConfig()
    llm: LlmConfig = LlmConfig()
    privacy: PrivacyConfig = PrivacyConfig()


def discover_config(start: Path, override: Path | None = None) -> tuple[FmConfig, Path]:
    """Find and load config. Returns (config, config_path).
    Raises FileNotFoundError if not found."""
    ...


def load_config(path: Path) -> FmConfig:
    """Load and validate config from a YAML file."""
    ...
```

### Config validation

Use pydantic validation. Unknown keys are ignored (forward compatibility). Missing keys use defaults. Invalid values raise `ValidationError` which the CLI catches and reports as a structured error.

## 5. Exit codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Error (config not found, invalid args, runtime error) |
| 2 | Lint/review findings at blocking severity |

## 6. Shared context object

The click context object (`ctx.obj`) carries:

```python
@dataclass
class CliContext:
    json_output: bool = False
    verbose: bool = False
    quiet: bool = False
    dry_run: bool = False
    docs_root: Path | None = None
    config_path: Path | None = None
    config: FmConfig | None = None
    project_root: Path | None = None
```

`project_root` is the directory containing `.feature-memory/`. It is set during config discovery.

## Key deliverables

- [ ] Global options propagate to all subcommands via `CliContext`
- [ ] `--json` produces the standard JSON envelope for any command
- [ ] Config discovery walks up from cwd and loads/validates YAML
- [ ] Config validation errors produce structured error output
- [ ] `Result.emit()` handles both JSON and human output
- [ ] Exit codes follow the table above
- [ ] `src/fm/commands/` directory structure is in place with stub modules
