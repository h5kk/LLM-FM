"""Regression tests for the _run.py polyglot hook bootstrap and PEP 263.

Root cause being guarded:
  Hooks were launched via `python` which on some machines is Python 2. The
  hook files contained non-ASCII (em dashes) with no encoding declaration, so
  Python 2 raised `SyntaxError: Non-ASCII character ... no encoding declared`
  before any error handling could run. The fix: PEP 263 declarations on every
  hook file + a polyglot bootstrap that runs the hooks under Python 3.
"""
import ast
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).parent.parent / "plugin" / "hooks"
REPO_ROOT = Path(__file__).parent.parent
BOOTSTRAP = HOOKS_DIR / "_run.py"

HOOK_SOURCES = sorted(HOOKS_DIR.glob("*.py")) + [REPO_ROOT / "fm_init.py"]


def _load_bootstrap_module():
    spec = importlib.util.spec_from_file_location("_fm_run", BOOTSTRAP)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.parametrize("src", HOOK_SOURCES, ids=lambda p: p.name)
def test_every_hook_file_has_encoding_declaration(src):
    """Any file containing non-ASCII bytes MUST declare an encoding (PEP 263)."""
    raw = src.read_bytes()
    has_non_ascii = any(b > 127 for b in raw)
    head = raw.split(b"\n")[:2]
    has_decl = any(b"coding:" in line or b"coding=" in line for line in head)
    if has_non_ascii:
        assert has_decl, f"{src.name} has non-ASCII but no PEP 263 declaration"
    # The declaration is harmless when present regardless; we require it on all
    # hook files so the original bug cannot regress as comments change.
    assert has_decl, f"{src.name} is missing the encoding declaration"


@pytest.mark.parametrize("src", HOOK_SOURCES, ids=lambda p: p.name)
def test_hook_files_compile(src):
    """Every hook file must at least parse under the running Python 3."""
    ast.parse(src.read_text(encoding="utf-8"))


def test_bootstrap_is_ascii_only_and_py2_safe():
    """The bootstrap itself must be ASCII (Python 2 parses it) and f-string free."""
    raw = BOOTSTRAP.read_bytes()
    assert all(b <= 127 for b in raw), "_run.py must be pure ASCII"
    tree = ast.parse(raw.decode("ascii"))
    # No JoinedStr (f-string) nodes anywhere — f-strings break Python 2 parse.
    assert not any(isinstance(n, ast.JoinedStr) for n in ast.walk(tree)), (
        "_run.py must not use f-strings (Python 2 must be able to parse it)"
    )


def test_target_path_resolves_and_blocks_traversal(monkeypatch):
    mod = _load_bootstrap_module()
    monkeypatch.setattr(sys, "argv", ["_run.py", "claude_stop"])
    assert mod._target_path() == str((HOOKS_DIR / "claude_stop.py"))
    # Path traversal in the module name is stripped to a basename.
    monkeypatch.setattr(sys, "argv", ["_run.py", "../../etc/passwd"])
    assert mod._target_path() == str((HOOKS_DIR / "passwd.py"))


def test_bootstrap_runs_hook_fast_path(project_dir):
    """Invoking a hook via the bootstrap under Python 3 behaves like running it
    directly: valid JSON-or-empty stdout and a non-blocking exit code."""
    proc = subprocess.run(
        [sys.executable, str(BOOTSTRAP), "claude_session_start"],
        input=json.dumps({"session_id": "s-boot"}),
        capture_output=True,
        text=True,
        cwd=str(project_dir),
    )
    assert proc.returncode == 0, proc.stderr
    if proc.stdout.strip():
        json.loads(proc.stdout)  # must be valid JSON when non-empty


def test_bootstrap_unknown_target_is_non_blocking(project_dir):
    proc = subprocess.run(
        [sys.executable, str(BOOTSTRAP), "does_not_exist"],
        input="{}",
        capture_output=True,
        text=True,
        cwd=str(project_dir),
    )
    assert proc.returncode == 0
    assert "skipping" in proc.stderr.lower()


def test_bootstrap_stop_hook_compiles_changelog(project_dir):
    """End-to-end: the Stop hook still compiles via the bootstrap entry point."""
    events = project_dir / ".feature-memory" / "events.jsonl"
    events.write_text(
        json.dumps(
            {
                "event_type": "path_touched",
                "path": "src/app.py",
                "session_id": "s-boot",
                "created_at": "2026-05-19T00:00:00+00:00",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    proc = subprocess.run(
        [sys.executable, str(BOOTSTRAP), "claude_stop"],
        input=json.dumps({"session_id": "s-boot"}),
        capture_output=True,
        text=True,
        cwd=str(project_dir),
    )
    assert proc.returncode == 0, proc.stderr
    changelog = project_dir / "docs" / "feature-memory" / "changelogs" / "changelog.json"
    assert changelog.exists()
    data = json.loads(changelog.read_text(encoding="utf-8"))
    assert any(e.get("feature_id") == "feat-a" for e in data.get("entries", []))
