"""Regression: inline-JSON-in-HTML must survive a literal </script> payload.

Council blocker (i): json.dumps does not escape '/', so a custom/commit string
containing '</script>' would prematurely close the <script id="changelog-data">
element (breaking JSON.parse) AND the next Stop's non-greedy regex re-injection
would capture only the truncated prefix → permanent data loss.
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "plugin" / "hooks"))
from fm_common import dump_inline_json  # noqa: E402

INJECT_RE = re.compile(r'(<script id="changelog-data"[^>]*>)([\s\S]*?)(</script>)')


def test_escapes_closing_tag_but_stays_valid_json():
    data = {"entries": [{"summary": "Explains the </script> trick and a/b paths"}]}
    out = dump_inline_json(data)
    assert "</script>" not in out
    assert "</" not in out
    assert "<\\/script>" in out
    # Still valid JSON and round-trips to the original object.
    assert json.loads(out) == data


def test_no_op_when_no_slash_sequences():
    data = {"a": 1, "b": "plain text"}
    assert json.loads(dump_inline_json(data)) == data


def test_survives_regex_reinjection_round_trip():
    """Mimic _update_viewer_data then _check_viewer_update extraction."""
    viewer = (
        '<html><body>'
        '<script id="changelog-data" type="application/json">\n{}\n</script>'
        '<script>render()</script></body></html>'
    )
    data = {"entries": [{"summary": "danger: </script><script>alert(1)</script>"}]}
    payload = dump_inline_json(data)

    written = INJECT_RE.sub(
        lambda m: m.group(1) + "\n" + payload + "\n" + m.group(3), viewer, count=1
    )

    # The injected closing tag must not appear inside the data block, so the
    # non-greedy regex still matches the REAL </script> (not an embedded one).
    m = INJECT_RE.search(written)
    assert m is not None
    extracted = m.group(2).strip()
    assert json.loads(extracted) == data

    # And the trailing <script>render()</script> is still intact afterwards.
    assert written.count("<script>render()</script>") == 1
