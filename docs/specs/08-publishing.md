# Spec 08 — Publishing and Distribution

> Arch plan refs: section 23 (implementation phases)

## Objective

Define how Feature Memory reaches users: PyPI package, GitHub Releases, Claude marketplace, Codex marketplace, and versioning policy.

---

## 1. PyPI publishing

### Package metadata

Already defined in spec 00 (`pyproject.toml`). Key fields:

- **Package name**: `feature-memory`
- **Console script**: `fm = fm.cli:main`
- **License**: MIT
- **Python**: >=3.11

### Installation

```bash
pip install feature-memory
# or
uv pip install feature-memory
# or
pipx install feature-memory
```

### Release workflow

`.github/workflows/release.yml`:

```yaml
name: Release

on:
  push:
    tags: ["v*"]

permissions:
  contents: write
  id-token: write

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - name: Set up Python
        run: uv python install 3.12
      - name: Install build deps
        run: uv pip install build --system
      - name: Build
        run: python -m build
      - name: Upload artifacts
        uses: actions/upload-artifact@v4
        with:
          name: dist
          path: dist/

  pypi-publish:
    needs: build
    runs-on: ubuntu-latest
    environment: pypi
    permissions:
      id-token: write
    steps:
      - uses: actions/download-artifact@v4
        with:
          name: dist
          path: dist/
      - name: Publish to PyPI
        uses: pypa/gh-action-pypi-publish@release/v1

  github-release:
    needs: build
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - uses: actions/download-artifact@v4
        with:
          name: dist
          path: dist/
      - name: Generate release notes
        id: notes
        run: |
          # Extract version from tag
          VERSION=${GITHUB_REF#refs/tags/v}
          echo "version=$VERSION" >> $GITHUB_OUTPUT
          # Generate changelog from git log since last tag
          PREV_TAG=$(git describe --tags --abbrev=0 HEAD^ 2>/dev/null || echo "")
          if [ -n "$PREV_TAG" ]; then
            git log --pretty=format:"- %s" "$PREV_TAG"..HEAD > release_notes.md
          else
            git log --pretty=format:"- %s" > release_notes.md
          fi
      - name: Create GitHub Release
        uses: softprops/action-gh-release@v2
        with:
          name: "v${{ steps.notes.outputs.version }}"
          body_path: release_notes.md
          files: dist/*
          generate_release_notes: true
```

### Release process

```bash
# 1. Update version in src/fm/__init__.py and pyproject.toml
# 2. Commit the version bump
git add -A && git commit -m "release: v0.1.0"
# 3. Tag
git tag v0.1.0
# 4. Push
git push origin main --tags
# 5. CI builds and publishes to PyPI + creates GitHub Release
```

---

## 2. GitHub Releases

### Tag format

`v{major}.{minor}.{patch}` — e.g., `v0.1.0`, `v0.2.0`, `v1.0.0`.

### Release notes template

```markdown
# Feature Memory v{version}

## What's new

- {bullet points from changelog}

## Installation

```bash
pip install feature-memory=={version}
```

## Upgrading

{migration notes if breaking changes}

## Full changelog

{link to compare view}
```

### Release assets

- Source distribution (`.tar.gz`)
- Wheel (`.whl`)
- Standalone binaries (future, if built with PyInstaller)

---

## 3. Claude marketplace publishing

### Prerequisites

- [ ] Plugin directory assembled (spec 06)
- [ ] `plugin.json` with all required fields
- [ ] SKILL.md tested and working
- [ ] Hooks tested and non-destructive
- [ ] README with clear description and screenshots
- [ ] LICENSE file (MIT)

### Submission checklist

| Item | Status | Notes |
|------|--------|-------|
| Plugin name | `feature-memory` | Must be unique in marketplace |
| Version | `0.1.0` | Semantic versioning |
| Description | <=200 chars | From plugin.json |
| Long description | README.md | Detailed usage guide |
| Keywords | documentation, feature-memory, knowledge-base | For search |
| Icon | 128x128 PNG | Simple, recognizable |
| Screenshots | 2-3 | Showing skill in action, lint output, feature page |
| Author | h5k | GitHub username |
| Repository | github.com/h5k/LLM-FM | Public repo |
| License | MIT | Permissive |
| Trust notes | Clear description of what hooks do | Required for hook-using plugins |

### Submission process

1. Run plugin validator: `claude plugin validate ./feature-memory-plugin`
2. Test locally: `claude plugin install ./feature-memory-plugin`
3. Submit via Claude Code marketplace portal (follow Anthropic's current submission process).
4. Address reviewer feedback.
5. Publish.

### Post-publish maintenance

- Monitor for user issues on GitHub.
- Test new Claude Code versions against the plugin.
- Update plugin version when CLI updates.

---

## 4. Codex marketplace publishing

### Prerequisites

Same as Claude, adapted for Codex plugin structure.

### Submission checklist

| Item | Status | Notes |
|------|--------|-------|
| Plugin name | `feature-memory` | |
| Version | `0.1.0` | |
| Description | | |
| Trust notes | Required | Hooks run local commands |
| Repository | | Public repo |
| License | MIT | |

### Submission process

1. Validate: `codex plugin validate ./feature-memory-codex-plugin`
2. Test locally: `codex plugin install ./feature-memory-codex-plugin`
3. Submit via Codex marketplace portal (follow OpenAI's current submission process).
4. Address feedback.
5. Publish.

---

## 5. Versioning policy

### Semantic versioning

```
MAJOR.MINOR.PATCH

MAJOR: breaking changes (schema_version bump, config format change, CLI arg removal)
MINOR: new features, new commands, new lint checks (backwards compatible)
PATCH: bug fixes, doc improvements (backwards compatible)
```

### What constitutes a breaking change

- `schema_version` increment in data model
- Removing or renaming a CLI command or required argument
- Changing the JSON output envelope structure
- Changing config.yaml required field names
- Removing a lint check ID (renumbering)
- Changing SQLite schema in a non-additive way

### What is NOT a breaking change

- Adding new CLI commands or optional arguments
- Adding new lint checks
- Adding new frontmatter fields with defaults
- Adding new config fields with defaults
- Adding new event types
- Performance improvements

### Version synchronization

Keep these in sync:
- `src/fm/__init__.py` (`__version__`)
- `pyproject.toml` (`version`)
- `plugin.json` (`version`) — both Claude and Codex plugins
- Git tag

Use a version bump script:

```bash
#!/usr/bin/env bash
# scripts/bump-version.sh
VERSION=$1
sed -i "s/__version__ = .*/__version__ = \"$VERSION\"/" src/fm/__init__.py
sed -i "s/^version = .*/version = \"$VERSION\"/" pyproject.toml
# Update plugin.json files
find plugins/ -name plugin.json -exec sed -i "s/\"version\": .*/\"version\": \"$VERSION\",/" {} \;
echo "Bumped to $VERSION"
```

---

## 6. Changelog

Maintain `CHANGELOG.md` at the repo root following Keep a Changelog format:

```markdown
# Changelog

All notable changes to Feature Memory will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- ...

### Changed
- ...

### Fixed
- ...

## [0.1.0] - 2026-XX-XX

### Added
- Initial release
- CLI commands: init, detect, map, ingest, lint, review
- Claude Code skill and hooks
- Codex skill and hooks
```

---

## 7. Distribution matrix

| Channel | Format | Audience | When |
|---------|--------|----------|------|
| PyPI | Python package | CLI users | Every release |
| GitHub Releases | Source + wheel + notes | Developers | Every release |
| Claude marketplace | Plugin bundle | Claude Code users | After plugin stabilizes |
| Codex marketplace | Plugin bundle | Codex users | After plugin stabilizes |
| npm | Node wrapper (future) | Node ecosystem | If MCP server needs it |

---

## Key deliverables

- [ ] PyPI release workflow (`.github/workflows/release.yml`)
- [ ] GitHub Release with auto-generated notes
- [ ] Claude marketplace submission checklist completed
- [ ] Codex marketplace submission checklist completed
- [ ] Semantic versioning policy documented
- [ ] Version bump script
- [ ] CHANGELOG.md format established
- [ ] All version references synchronized
