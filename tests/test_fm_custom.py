"""Tests for fm_custom: frontmatter parsing + separate-slot custom docs."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

HOOKS = Path(__file__).parent.parent / "plugin" / "hooks"
sys.path.insert(0, str(HOOKS))
from fm_custom import parse_frontmatter, load_custom_docs  # noqa: E402
from fm_common import load_changelog_config  # noqa: E402


def _proj(tmp_path, cfg_body="changelog:\n  custom_docs:\n    enabled: true\n"):
    fm = tmp_path / ".feature-memory"
    fm.mkdir()
    (fm / "config.yaml").write_text("schema_version: 1\n" + cfg_body, encoding="utf-8")
    return tmp_path


def _add(tmp_path, name, content, sub="docs/feature-memory/custom"):
    d = tmp_path / sub
    d.mkdir(parents=True, exist_ok=True)
    (d / name).write_text(content, encoding="utf-8")
    return d / name


# ── parse_frontmatter ────────────────────────────────────────────────────────

def test_frontmatter_basic():
    meta, body = parse_frontmatter('---\ntitle: Hi\ntags: [a, "b c"]\n---\nBody\nmore')
    assert meta["title"] == "Hi"
    assert meta["tags"] == ["a", "b c"]
    assert body == "Body\nmore"


def test_frontmatter_absent():
    meta, body = parse_frontmatter("# Just markdown\ntext")
    assert meta == {} and body == "# Just markdown\ntext"


def test_frontmatter_unterminated_is_all_body():
    meta, body = parse_frontmatter("---\ntitle: x\nno closing fence")
    assert meta == {}
    assert "no closing fence" in body


def test_frontmatter_comment_and_quotes():
    meta, _ = parse_frontmatter('---\n# c\ntitle: "a: b"\naudience: both\n---\nx')
    assert meta["title"] == "a: b"
    assert meta["audience"] == "both"


# ── load_custom_docs ─────────────────────────────────────────────────────────

def test_disabled_returns_empty_slot(tmp_path):
    _proj(tmp_path, "changelog:\n  custom_docs:\n    enabled: false\n")
    _add(tmp_path, "a.md", "---\ndoc_type: wiki\ntitle: A\n---\nbody")
    slot, issues = load_custom_docs(tmp_path)
    assert slot["enabled"] is False
    assert slot["entries"] == [] and slot["wiki"] == []


def test_entry_vs_wiki_routing(tmp_path):
    _proj(tmp_path)
    _add(tmp_path, "rel.md", "---\ndoc_type: entry\ntitle: Rel\ndate: 2026-05-19\n---\nshipped")
    _add(tmp_path, "guide.md", "---\ndoc_type: wiki\ntitle: Guide\n---\nhow to")
    slot, issues = load_custom_docs(tmp_path)
    assert [e["title"] for e in slot["entries"]] == ["Rel"]
    assert [w["title"] for w in slot["wiki"]] == ["Guide"]
    assert issues == []
    assert slot["entries"][0]["event_id"].startswith("custom-")
    assert slot["entries"][0]["source"] == "custom"


def test_delete_then_rescan_drops_doc(tmp_path):
    _proj(tmp_path)
    f = _add(tmp_path, "tmp.md", "---\ndoc_type: wiki\ntitle: Temp\n---\nx")
    slot, _ = load_custom_docs(tmp_path)
    assert len(slot["wiki"]) == 1
    f.unlink()
    slot2, _ = load_custom_docs(tmp_path)
    assert slot2["wiki"] == []  # true re-scan, not append-only


def test_stable_event_id_is_idempotent(tmp_path):
    _proj(tmp_path)
    _add(tmp_path, "notes.md", "---\ntitle: N\n---\nv1")
    a, _ = load_custom_docs(tmp_path)
    _add(tmp_path, "notes.md", "---\ntitle: N\n---\nv2 updated")
    b, _ = load_custom_docs(tmp_path)
    assert a["wiki"][0]["event_id"] == b["wiki"][0]["event_id"]
    assert b["wiki"][0]["body_md"] == "v2 updated"


def test_invalid_fields_coerced_with_issues(tmp_path):
    _proj(tmp_path)
    _add(tmp_path, "bad.md",
         "---\ndoc_type: blog\naudience: martians\nverbosity: loud\ndate: yesterday\ntitle: B\n---\nbody")
    slot, issues = load_custom_docs(tmp_path)
    d = (slot["wiki"] + slot["entries"])[0]
    assert d["doc_type"] == "wiki"
    assert d["audience"] == "both"
    assert d["verbosity"] == "normal"
    assert len(issues) >= 4


def test_per_doc_tagging_and_global_switch(tmp_path):
    _proj(tmp_path, "changelog:\n  tagging: false\n  custom_docs:\n    enabled: true\n")
    _add(tmp_path, "x.md", "---\ntitle: X\ntagging: true\ntags: [keep-me]\n---\nb")
    slot, _ = load_custom_docs(tmp_path)
    d = slot["wiki"][0]
    # Global tagging off forces doc tagging off, but explicit tags are kept.
    assert d["tagging"] is False
    assert d["tags"] == ["keep-me"]


def test_script_tag_in_body_preserved_raw(tmp_path):
    _proj(tmp_path)
    _add(tmp_path, "danger.md", "---\ntitle: D\n---\nText with </script><b>raw</b>")
    slot, _ = load_custom_docs(tmp_path)
    # Stored raw; the viewer renderer is responsible for escaping.
    assert "</script>" in slot["wiki"][0]["body_md"]


def test_nested_dirs_scanned(tmp_path):
    _proj(tmp_path)
    _add(tmp_path, "deep.md", "---\ndoc_type: entry\ntitle: Deep\n---\nb",
         sub="docs/feature-memory/custom/2026")
    slot, _ = load_custom_docs(tmp_path)
    assert slot["entries"][0]["title"] == "Deep"


def test_custom_dir_outside_project_ignored(tmp_path):
    _proj(tmp_path, "changelog:\n  custom_docs:\n    enabled: true\n    dir: ../../etc\n")
    slot, issues = load_custom_docs(tmp_path)
    assert slot["entries"] == [] and slot["wiki"] == []
    assert any("outside the project" in i for i in issues)


# ── CLI ──────────────────────────────────────────────────────────────────────

def test_cli_validate_exit_codes(tmp_path):
    _proj(tmp_path)
    _add(tmp_path, "ok.md", "---\ndoc_type: wiki\ntitle: OK\n---\nbody")
    r = subprocess.run([sys.executable, str(HOOKS / "fm_custom.py"), "--validate"],
                        cwd=str(tmp_path), capture_output=True, text=True)
    assert r.returncode == 0
    _add(tmp_path, "bad.md", "---\ndoc_type: nope\ntitle: B\n---\nbody")
    r2 = subprocess.run([sys.executable, str(HOOKS / "fm_custom.py"), "--validate"],
                         cwd=str(tmp_path), capture_output=True, text=True)
    assert r2.returncode == 1


def test_cli_list_json(tmp_path):
    _proj(tmp_path)
    _add(tmp_path, "ok.md", "---\ndoc_type: entry\ntitle: OK\ndate: 2026-05-19\n---\nb")
    r = subprocess.run([sys.executable, str(HOOKS / "fm_custom.py"), "--list", "--json"],
                        cwd=str(tmp_path), capture_output=True, text=True)
    assert r.returncode == 0
    slot = json.loads(r.stdout)
    assert slot["entries"][0]["title"] == "OK"
