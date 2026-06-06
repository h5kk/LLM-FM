"""Verbosity / summary_rule / tagging-master-switch wiring tests."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "plugin" / "hooks"))
from fm_common import (  # noqa: E402
    _build_topic_prompt, _parse_topic_tags, generate_topic_tags_batch,
    verbosity_tag_cap,
)


def test_verbosity_tag_cap_levels():
    assert verbosity_tag_cap("terse") == 1
    assert verbosity_tag_cap("normal") == 3
    assert verbosity_tag_cap("detailed") == 5
    assert verbosity_tag_cap("bogus") == 3


def test_summary_rule_injected_and_sanitized():
    p = _build_topic_prompt(
        [{"feature_id": "a", "paths": ["x"], "git_message": "m"}],
        summary_rule="line one\nline two   with   spaces",
        max_tags=5,
    )
    assert "ADDITIONAL PROJECT RULE: line one line two with spaces" in p
    assert "1-5 semantic topic tags" in p
    assert "1 to 5 tags per entry" in p


def test_no_rule_line_when_empty():
    p = _build_topic_prompt([{"feature_id": "a"}], summary_rule="", max_tags=1)
    assert "ADDITIONAL PROJECT RULE" not in p
    assert "1 to 1 tags per entry" in p


def test_parse_topic_tags_respects_cap():
    out = _parse_topic_tags("0: alpha, beta, gamma, delta", 1, max_tags=2)
    assert out == [["alpha", "beta"]]


def test_generate_none_strategy_returns_empty():
    entries = [{"feature_id": "a"}, {"feature_id": "b"}]
    assert generate_topic_tags_batch(entries, strategy="none") == [[], []]


def test_generate_keyword_strategy_capped():
    entries = [{"paths": ["src/auth/login/handler.py"]}]
    out = generate_topic_tags_batch(entries, strategy="keyword", max_tags=1)
    assert len(out) == 1 and len(out[0]) <= 1


def _cfg(project_dir, body):
    (project_dir / ".feature-memory" / "config.yaml").write_text(body, encoding="utf-8")


def test_stop_hook_tagging_master_switch_off(project_dir, hook_runner):
    """changelog.tagging:false forces topic_pending False even with keyword strategy."""
    _cfg(project_dir, (
        "schema_version: 1\nfeatures:\n  feat-a:\n    globs:\n      - 'src/**'\n"
        "tagging:\n  strategy: keyword\n"
        "changelog:\n  tagging: false\n"
    ))
    events = project_dir / ".feature-memory" / "events.jsonl"
    events.write_text(json.dumps({
        "event_type": "path_touched", "path": "src/app.py",
        "session_id": "s1", "created_at": "2026-05-19T00:00:00+00:00",
    }) + "\n", encoding="utf-8")
    hook_runner("claude_stop.py", {"session_id": "s1"})
    cl = project_dir / "docs" / "feature-memory" / "changelogs" / "changelog.json"
    data = json.loads(cl.read_text(encoding="utf-8"))
    e = next(e for e in data["entries"] if e["feature_id"] == "feat-a")
    assert e["topic_tags"] == []
    assert e["topic_pending"] is False  # master switch => 'none' behavior


def test_stop_hook_verbosity_caps_keyword_tags(project_dir, hook_runner):
    _cfg(project_dir, (
        "schema_version: 1\nfeatures:\n  feat-a:\n    globs:\n      - 'src/**'\n"
        "tagging:\n  strategy: keyword\n"
        "changelog:\n  verbosity: terse\n"
    ))
    events = project_dir / ".feature-memory" / "events.jsonl"
    events.write_text(json.dumps({
        "event_type": "path_touched", "path": "src/auth/login/handler.py",
        "session_id": "s2", "created_at": "2026-05-19T00:00:00+00:00",
    }) + "\n", encoding="utf-8")
    hook_runner("claude_stop.py", {"session_id": "s2"})
    cl = project_dir / "docs" / "feature-memory" / "changelogs" / "changelog.json"
    data = json.loads(cl.read_text(encoding="utf-8"))
    e = next(e for e in data["entries"] if e["feature_id"] == "feat-a")
    assert len(e["topic_tags"]) <= 1  # terse => cap 1
