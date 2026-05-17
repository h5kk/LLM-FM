# Spec 00 — Project Bootstrap

> Arch plan refs: sections 4 (repository layout), 23 (implementation phases)

## Objective

Set up a buildable, testable, installable Python project skeleton so that `fm --version` works and CI runs green on an empty test suite.

## 1. Language and toolchain

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Language | Python 3.11+ | Best stdlib support for YAML, SQLite, filesystem, subprocess. Arch plan section 23 recommends Python. |
| Package manager | uv (primary), pip fallback | Fast resolver, lockfile support, virtualenv management. |
| Build system | hatchling via pyproject.toml | Modern, no setup.py needed. |
| Linter | ruff | Replaces flake8 + isort + pyupgrade. |
| Type checker | mypy (strict mode) | Catch type errors early. |
| Test runner | pytest | Standard, good plugin ecosystem. |
| Task runner | Makefile | Simple, no extra deps. |

## 2. Repository directory structure

```
LLM-FM/
  .gitignore
  .gitattributes
  LICENSE                              # MIT
  README.md                            # Project README (see spec 09)
  Makefile                             # dev tasks: lint, test, fmt, install
  pyproject.toml                       # package metadata, deps, tool config
  uv.lock                             # lockfile (committed)

  src/
    fm/
      __init__.py                      # version string
      __main__.py                      # `python -m fm` entry
      cli.py                           # click app, global options, command registration
      config.py                        # config discovery and loading
      models.py                        # pydantic models for data structures
      db.py                            # SQLite operations
      detect.py                        # fm detect logic
      mapping.py                       # fm map logic
      ingest.py                        # fm ingest orchestrator
      lint.py                          # fm lint checks
      review.py                        # fm review logic
      proposal.py                      # fm propose-reorg / apply-proposal
      templates.py                     # markdown template rendering
      output.py                        # JSON/human output formatting
      events.py                        # event log writing
      llm.py                           # LLM provider abstraction
      utils.py                         # shared utilities
      commands/                        # click command modules (see spec 01)
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

  tests/
    __init__.py
    conftest.py                        # shared fixtures
    unit/
      __init__.py
      test_config.py
      test_detect.py
      test_mapping.py
      test_lint.py
      test_models.py
      test_db.py
      test_output.py
    integration/
      __init__.py
      test_cli.py
      test_init.py
      test_ingest.py
    fixtures/
      README.md
    golden/
      README.md

  docs/
    specs/                             # this directory
    guide/                             # user-facing docs (spec 09)

  .github/
    workflows/
      ci.yml                           # lint + type check + test
      release.yml                      # tag-triggered PyPI publish
```

## 3. `pyproject.toml`

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "feature-memory"
version = "0.1.0"
description = "A documentation compiler that maintains feature-level memory for software projects."
readme = "README.md"
license = "MIT"
requires-python = ">=3.11"
authors = [
    { name = "h5k", email = "resostudios@gmail.com" },
]
keywords = ["documentation", "feature-memory", "llm", "developer-tools"]
classifiers = [
    "Development Status :: 3 - Alpha",
    "Environment :: Console",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Programming Language :: Python :: 3.13",
    "Topic :: Software Development :: Documentation",
]
dependencies = [
    "click>=8.1",
    "pyyaml>=6.0",
    "pydantic>=2.0",
    "rich>=13.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-cov>=5.0",
    "syrupy>=4.0",
    "mypy>=1.10",
    "ruff>=0.4",
    "pre-commit>=3.7",
]
llm = [
    "anthropic>=0.30",
    "openai>=1.30",
]

[project.scripts]
fm = "fm.cli:main"

[project.urls]
Homepage = "https://github.com/h5k/LLM-FM"
Repository = "https://github.com/h5k/LLM-FM"
Issues = "https://github.com/h5k/LLM-FM/issues"

[tool.hatch.build.targets.wheel]
packages = ["src/fm"]

[tool.ruff]
target-version = "py311"
line-length = 100
src = ["src", "tests"]

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM", "RUF"]

[tool.mypy]
python_version = "3.11"
strict = true
warn_return_any = true
warn_unused_configs = true

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-ra -q"
```

## 4. `Makefile`

```makefile
.PHONY: install dev lint type-check test fmt clean

install:
	uv pip install -e .

dev:
	uv pip install -e ".[dev]"

lint:
	ruff check src/ tests/

fmt:
	ruff format src/ tests/
	ruff check --fix src/ tests/

type-check:
	mypy src/fm/

test:
	pytest

clean:
	rm -rf dist/ build/ *.egg-info .pytest_cache .mypy_cache .ruff_cache htmlcov
	find . -type d -name __pycache__ -exec rm -rf {} +
```

## 5. CI workflow

`.github/workflows/ci.yml`:

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  lint-and-test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.11", "3.12", "3.13"]
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - name: Set up Python ${{ matrix.python-version }}
        run: uv python install ${{ matrix.python-version }}
      - name: Install dependencies
        run: uv pip install -e ".[dev]" --system
      - name: Lint
        run: ruff check src/ tests/
      - name: Type check
        run: mypy src/fm/
      - name: Test
        run: pytest --cov=fm --cov-report=term-missing
```

## 6. Minimal entry points

`src/fm/__init__.py`:

```python
__version__ = "0.1.0"
```

`src/fm/__main__.py`:

```python
from fm.cli import main

main()
```

`src/fm/cli.py` (skeleton):

```python
import click

from fm import __version__


@click.group()
@click.version_option(version=__version__, prog_name="fm")
@click.option("--json", "json_output", is_flag=True, help="Machine-readable JSON output.")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output.")
@click.option("--quiet", "-q", is_flag=True, help="Suppress non-essential output.")
@click.option("--docs-root", type=click.Path(), help="Override docs root directory.")
@click.option("--config", "config_path", type=click.Path(), help="Override config file path.")
@click.pass_context
def main(ctx: click.Context, json_output: bool, verbose: bool, quiet: bool,
         docs_root: str | None, config_path: str | None) -> None:
    ctx.ensure_object(dict)
    ctx.obj["json_output"] = json_output
    ctx.obj["verbose"] = verbose
    ctx.obj["quiet"] = quiet
    ctx.obj["docs_root"] = docs_root
    ctx.obj["config_path"] = config_path
```

## 7. Pre-commit config

`.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.4.8
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.10.0
    hooks:
      - id: mypy
        additional_dependencies: [pydantic, click, pyyaml, rich]
        args: [--strict]
```

## Key deliverables

- [ ] `fm --version` prints `0.1.0`
- [ ] `fm --help` shows the top-level group with global options
- [ ] `ruff check` passes on empty project
- [ ] `mypy` passes on skeleton
- [ ] `pytest` runs (0 tests, no failures)
- [ ] CI workflow runs green on push to main
- [ ] `pip install -e .` or `uv pip install -e .` installs the `fm` command
