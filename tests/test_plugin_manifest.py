"""Regression tests for the Claude Code plugin manifest schema.

Guards against the v0.7.0 install failure where `.claude-plugin/plugin.json`
declared `skills` as an array of objects ({name, path, description}). The
Claude Code plugin manifest schema requires `skills` to be a string or an
array of strings (custom skill directory paths); the object-array shape
fails `claude plugin install` with: Validation errors: skills: Invalid input.

Skills are auto-discovered from the default `plugin/skills/<name>/SKILL.md`
layout, so the manifest should not redeclare them as objects.
"""
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
PLUGIN_DIR = REPO_ROOT / "plugin"
PLUGIN_MANIFEST = PLUGIN_DIR / ".claude-plugin" / "plugin.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_plugin_manifest_exists_and_parses():
    assert PLUGIN_MANIFEST.is_file(), f"missing manifest: {PLUGIN_MANIFEST}"
    manifest = _load(PLUGIN_MANIFEST)
    assert manifest.get("name") == "feature-memory"
    assert isinstance(manifest.get("version"), str) and manifest["version"]


def test_skills_field_is_not_object_array():
    """The exact regression: `skills` must never be a list of dicts."""
    manifest = _load(PLUGIN_MANIFEST)
    skills = manifest.get("skills")
    if skills is None:
        # Preferred state: skills auto-discovered from plugin/skills/, no key.
        return
    if isinstance(skills, str):
        return
    assert isinstance(skills, list), (
        f"`skills` must be a string or list of strings, got {type(skills).__name__}"
    )
    bad = [s for s in skills if not isinstance(s, str)]
    assert not bad, (
        "`skills` must be a list of path STRINGS, not objects. "
        f"Offending entries: {bad}. This shape fails `claude plugin install` "
        "with 'Validation errors: skills: Invalid input'."
    )


def test_skills_autodiscoverable_from_default_dir():
    """Every skill dir has a SKILL.md with frontmatter so basename discovery works."""
    skills_root = PLUGIN_DIR / "skills"
    assert skills_root.is_dir(), "plugin/skills/ directory must exist"
    skill_dirs = [d for d in skills_root.iterdir() if d.is_dir()]
    assert skill_dirs, "expected at least one skill directory"
    for d in skill_dirs:
        skill_md = d / "SKILL.md"
        assert skill_md.is_file(), f"{d.name}: missing SKILL.md"
        head = skill_md.read_text(encoding="utf-8").lstrip()
        assert head.startswith("---"), f"{d.name}: SKILL.md missing YAML frontmatter"
        assert "description:" in head.split("---", 2)[1], (
            f"{d.name}: SKILL.md frontmatter missing description"
        )


@pytest.mark.parametrize(
    "manifest_path",
    [
        REPO_ROOT / ".claude-plugin" / "marketplace.json",
        REPO_ROOT / "marketplace.json",
    ],
)
def test_marketplace_manifests_parse(manifest_path):
    if not manifest_path.is_file():
        pytest.skip(f"{manifest_path} not present")
    mkt = _load(manifest_path)
    assert mkt.get("name"), f"{manifest_path}: marketplace name required"
    plugins = mkt.get("plugins")
    assert isinstance(plugins, list) and plugins, (
        f"{manifest_path}: must declare at least one plugin"
    )
    fm = next((p for p in plugins if p.get("name") == "feature-memory"), None)
    assert fm is not None, f"{manifest_path}: feature-memory plugin entry missing"


def test_canonical_marketplace_name_matches_registered_name():
    """`.claude-plugin/marketplace.json` is canonical; its name is the one
    users reference as `feature-memory@<name>`. Keep it stable at h5kk-plugins.
    """
    canonical = REPO_ROOT / ".claude-plugin" / "marketplace.json"
    assert canonical.is_file(), "canonical .claude-plugin/marketplace.json required"
    assert _load(canonical)["name"] == "h5kk-plugins"
