"""Tests for fm_common.load_changelog_config (independent nested parser)."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "plugin" / "hooks"))
from fm_common import load_changelog_config, _changelog_defaults  # noqa: E402


def _write(tmp_path, body):
    fm = tmp_path / ".feature-memory"
    fm.mkdir(exist_ok=True)
    (fm / "config.yaml").write_text(body, encoding="utf-8")
    return tmp_path


def test_missing_config_returns_defaults(tmp_path):
    assert load_changelog_config(tmp_path) == _changelog_defaults()


def test_no_changelog_block_returns_defaults(tmp_path):
    _write(tmp_path, "schema_version: 1\nfeatures: {}\n")
    assert load_changelog_config(tmp_path) == _changelog_defaults()


def test_full_block_parsed(tmp_path):
    _write(tmp_path, (
        "project_name: x\n"
        "changelog:\n"
        "  verbosity: detailed\n"
        '  summary_rule: "Prefer domain names: billing, auth"\n'
        "  tagging: false\n"
        "  highlight_tags:\n"
        "    - breaking-change\n"
        "    - security\n"
        "  metrics:\n"
        "    enabled: true\n"
        "    code_churn: true\n"
        "  custom_docs:\n"
        "    enabled: false\n"
        "    dir: docs\\fm\\custom\n"
        "skip_patterns: []\n"
    ))
    cfg = load_changelog_config(tmp_path)
    assert cfg["verbosity"] == "detailed"
    assert cfg["summary_rule"] == "Prefer domain names: billing, auth"
    assert cfg["tagging"] is False
    assert cfg["highlight_tags"] == ["breaking-change", "security"]
    assert cfg["metrics"] == {"enabled": True, "code_churn": True}
    assert cfg["custom_docs"] == {"enabled": False, "dir": "docs/fm/custom"}


def test_partial_block_keeps_defaults_for_missing(tmp_path):
    _write(tmp_path, "changelog:\n  verbosity: terse\n")
    cfg = load_changelog_config(tmp_path)
    d = _changelog_defaults()
    assert cfg["verbosity"] == "terse"
    assert cfg["tagging"] == d["tagging"]
    assert cfg["highlight_tags"] == d["highlight_tags"]
    assert cfg["metrics"] == d["metrics"]


def test_invalid_verbosity_falls_back_to_normal(tmp_path):
    _write(tmp_path, "changelog:\n  verbosity: loud\n")
    assert load_changelog_config(tmp_path)["verbosity"] == "normal"


def test_block_ends_at_next_column0_key(tmp_path):
    _write(tmp_path, (
        "changelog:\n"
        "  verbosity: terse\n"
        "tagging:\n"            # this is the OTHER top-level tagging block
        "  strategy: cli\n"
    ))
    cfg = load_changelog_config(tmp_path)
    assert cfg["verbosity"] == "terse"
    assert cfg["tagging"] is True  # default — not bled from tagging.strategy


def test_inline_comment_stripped_for_unquoted_value(tmp_path):
    _write(tmp_path, (
        "changelog:\n"
        "  verbosity: normal   # the default\n"
        "  summary_rule: just text # this is a comment\n"
    ))
    cfg = load_changelog_config(tmp_path)
    assert cfg["verbosity"] == "normal"
    assert cfg["summary_rule"] == "just text"


def test_quoted_summary_rule_preserves_hash_and_colon(tmp_path):
    _write(tmp_path, (
        "changelog:\n"
        '  summary_rule: "ticket #5: prefer billing, auth"\n'
    ))
    assert load_changelog_config(tmp_path)["summary_rule"] == "ticket #5: prefer billing, auth"


def test_tab_indentation_rejected_to_defaults(tmp_path):
    _write(tmp_path, "changelog:\n\tverbosity: detailed\n")
    assert load_changelog_config(tmp_path) == _changelog_defaults()


def test_empty_highlight_tags_keeps_defaults(tmp_path):
    _write(tmp_path, "changelog:\n  highlight_tags:\n  verbosity: terse\n")
    cfg = load_changelog_config(tmp_path)
    assert cfg["highlight_tags"] == _changelog_defaults()["highlight_tags"]
    assert cfg["verbosity"] == "terse"


def test_summary_rule_length_capped(tmp_path):
    _write(tmp_path, "changelog:\n  summary_rule: " + ("x" * 800) + "\n")
    assert len(load_changelog_config(tmp_path)["summary_rule"]) == 500


def test_garbage_file_returns_defaults(tmp_path):
    _write(tmp_path, "::: not yaml :::\n\x00\x01\nchangelog:\n  verbosity: terse\n")
    cfg = load_changelog_config(tmp_path)
    # Still recovers the well-formed line; never raises.
    assert cfg["verbosity"] in ("terse", "normal")
