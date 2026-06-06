"""Viewer v11 regression + XSS corpus for the shipped mini-markdown renderer.

Structural checks run always. The XSS corpus extracts the REAL escHtml /
sanitizeUrl / mdToHtml from the shipped HTML and executes them in Node, so the
test pins the actual code that ships, not a copy.
"""
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
VIEWER = ROOT / "plugin" / "assets" / "changelog-viewer.html"
HTML = VIEWER.read_text(encoding="utf-8")


# ── Structural regression ────────────────────────────────────────────────────

def test_no_nul_bytes():
    assert VIEWER.read_bytes().count(b"\x00") == 0


def test_version_markers_consistent():
    assert "<!-- fm-viewer-version: 11 -->" in HTML
    assert 'content="11"' in HTML
    fm_common = (ROOT / "plugin" / "hooks" / "fm_common.py").read_text(encoding="utf-8")
    assert "_VIEWER_VERSION = 11" in fm_common


def test_new_blocks_and_views_present():
    for tok in ('id="custom-docs-data"', 'id="changelog-data"', 'class="view-switch"',
                'id="wiki-view"', 'id="metrics-view"', 'data-view="timeline"',
                'data-view="wiki"', 'data-view="metrics"'):
        assert tok in HTML, tok


def test_changelog_data_block_still_first_and_parseable():
    m = re.search(r'<script id="changelog-data"[^>]*>([\s\S]*?)</script>', HTML)
    assert m and json.loads(m.group(1))
    m2 = re.search(r'<script id="custom-docs-data"[^>]*>([\s\S]*?)</script>', HTML)
    assert m2 and json.loads(m2.group(1))["enabled"] is True


def test_no_external_resources():
    # Offline single-file invariant: no CDN/script/link to the network.
    assert not re.search(r'<script[^>]+src=', HTML)
    assert not re.search(r'<link[^>]+href="https?:', HTML)


# ── XSS corpus against the real renderer (Node) ──────────────────────────────

def _extract_fn(name):
    """Brace-match a `function <name>(` definition out of the HTML."""
    i = HTML.index("function " + name + "(")
    depth = 0
    started = False
    for j in range(i, len(HTML)):
        c = HTML[j]
        if c == "{":
            depth += 1
            started = True
        elif c == "}":
            depth -= 1
            if started and depth == 0:
                return HTML[i:j + 1]
    raise AssertionError("function %s not found" % name)


@pytest.mark.skipif(not shutil.which("node"), reason="node not available")
def test_markdown_renderer_xss_corpus(tmp_path):
    harness = "\n".join([
        _extract_fn("escHtml"),
        _extract_fn("sanitizeUrl"),
        _extract_fn("mdToHtml"),
        "const cases = " + json.dumps([
            "<img src=x onerror=alert(1)>",
            "[click](javascript:alert(1))",
            "```\n<script>alert(1)</script>\n```",
            "<svg onload=alert(1)>",
            "[a](data:text/html,<script>alert(1)</script>)",
            "plain </script> text and **bold**",
            "[ok](https://example.com) and `code`\n# Heading",
            "<iframe src=javascript:alert(1)></iframe>",
        ]) + ";",
        "console.log(JSON.stringify(cases.map(mdToHtml)));",
    ])
    script = tmp_path / "h.js"
    script.write_text(harness, encoding="utf-8")
    out = subprocess.run(["node", str(script)], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    rendered = json.loads(out.stdout)
    joined = "\n".join(rendered).lower()

    # No executable HTML element survives (all < > became &lt; &gt;).
    assert "<script" not in joined
    assert "<img" not in joined
    assert "<svg" not in joined
    assert "<iframe" not in joined
    # Dangerous payloads are present ONLY as escaped, inert text.
    assert "&lt;img src=x onerror=alert(1)&gt;" in rendered[0]
    assert "&lt;svg onload=alert(1)&gt;" in rendered[3]
    # Dangerous URL schemes never become a live href.
    assert 'href="javascript:' not in joined
    assert 'href="data:' not in joined
    # Safe constructs still render.
    safe = rendered[6]
    assert '<a href="https://example.com"' in safe
    assert "rel=\"noopener noreferrer\"" in safe
    assert "<code>code</code>" in safe
    assert "<h1>Heading</h1>" in safe
    # Literal </script> in prose is escaped, not a tag.
    assert "&lt;/script&gt;" in rendered[5]
    # Fenced code keeps the script escaped (shown as text, not executed).
    assert "<pre><code>" in rendered[2] and "&lt;script&gt;" in rendered[2]
