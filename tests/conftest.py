"""Shared pytest fixtures for Feature Memory hook tests."""
import json
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.fixture
def project_dir(tmp_path):
    """Set up a minimal Feature Memory project in a temp directory."""
    fm = tmp_path / ".feature-memory"
    fm.mkdir()
    (fm / "config.yaml").write_text(
        "schema_version: 1\nproject_name: test\ndocs_root: docs/feature-memory\nmode: small\nfeatures:\n  feat-a:\n    globs:\n      - 'src/**'\nskip_patterns: []\n",
        encoding="utf-8",
    )
    (fm / "events.jsonl").write_text("", encoding="utf-8")
    docs = tmp_path / "docs" / "feature-memory"
    docs.mkdir(parents=True)
    (docs / "changelogs").mkdir()
    return tmp_path


@pytest.fixture
def hook_runner(project_dir):
    """Run a hook script with controlled stdin JSON, returning (stdout_parsed, stderr, exit_code)."""
    hooks_dir = Path(__file__).parent.parent / "plugin" / "hooks"

    def run(hook_name, stdin_data=None, cwd=None):
        script = hooks_dir / hook_name
        proc = subprocess.run(
            [sys.executable, str(script)],
            input=json.dumps(stdin_data or {}),
            capture_output=True,
            text=True,
            cwd=str(cwd or project_dir),
        )
        try:
            out = json.loads(proc.stdout) if proc.stdout.strip() else {}
        except json.JSONDecodeError:
            out = {"raw": proc.stdout}
        return out, proc.stderr, proc.returncode

    return run
