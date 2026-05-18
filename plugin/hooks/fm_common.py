#!/usr/bin/env python3
"""Shared utilities for Feature Memory hooks.

Extracted to avoid code duplication across PostToolUse, Stop, and SessionStart hooks.
Works with Python 3.6+ stdlib only — no external dependencies.
"""
import fnmatch
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def load_config(project_dir):
    """Load feature globs from config.yaml without requiring PyYAML."""
    config_path = project_dir / ".feature-memory" / "config.yaml"
    if not config_path.exists():
        return {}

    features = {}
    current_feature = None
    in_features = False
    in_globs = False

    for line in config_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()

        if stripped == "features:":
            in_features = True
            continue

        if in_features and not line.startswith(" ") and not line.startswith("\t") and line.strip():
            in_features = False
            in_globs = False
            continue

        if in_features:
            if line.startswith("  ") and not line.startswith("    ") and stripped.endswith(":") and not stripped.startswith("-"):
                current_feature = stripped[:-1]
                features[current_feature] = []
                in_globs = False
                continue

            if stripped == "globs:":
                in_globs = True
                continue

            if in_globs and stripped.startswith("- "):
                glob_pattern = stripped[2:].strip().strip('"').strip("'")
                if current_feature:
                    features[current_feature].append(glob_pattern)
                continue

            # Any non-glob key (mode:, owner:, etc.) exits glob parsing
            if not stripped.startswith("- ") and ":" in stripped:
                in_globs = False

    if not features and config_path.stat().st_size > 50:
        log_error("YAML parse warning: config.yaml has content but no features were parsed. "
                  "Check indentation (must use 2-space indent).")

    return features


def match_path_to_features(file_path, features):
    """Match a file path against feature globs. Returns list of ALL matching feature IDs."""
    normalized = file_path.replace("\\", "/")
    matched = []

    for feature_id, globs in features.items():
        for pattern in globs:
            if pattern.endswith("/**"):
                prefix = pattern[:-3]
                if normalized.startswith(prefix + "/") or normalized == prefix:
                    matched.append(feature_id)
                    break
            elif fnmatch.fnmatch(normalized, pattern):
                matched.append(feature_id)
                break

    return matched


def get_feature_doc_path(feature_id, docs_root):
    """Return canonical feature doc path, handling flat and split layouts.

    Checks for features/{id}/index.md (split mode) first, falls back to
    features/{id}.md (small mode). Does not require the file to exist.
    """
    split_path = docs_root / "features" / feature_id / "index.md"
    if split_path.exists():
        return split_path
    return docs_root / "features" / f"{feature_id}.md"


def get_git_info(project_dir=None):
    """Get current HEAD commit info. Returns dict or None on failure.

    Never raises — git unavailability is silently ignored.
    """
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%H%n%an%n%ae%n%s"],
            capture_output=True,
            text=True,
            timeout=2,
            cwd=str(project_dir) if project_dir else None,
        )
        if result.returncode == 0:
            lines = result.stdout.strip().splitlines()
            if len(lines) >= 4:
                return {
                    "git_hash": lines[0],
                    "git_author": lines[1],
                    "git_email": lines[2],
                    "git_message": lines[3],
                }
    except Exception:
        pass
    return None


def generate_event_id():
    """Generate a unique event ID with timestamp and random suffix."""
    import random
    now = datetime.now(timezone.utc)
    suffix = f"{random.randint(0, 0xFFFF):04x}"
    return f"{now.strftime('%Y%m%dT%H%M%SZ')}-{suffix}"


def log_error(message):
    """Log an error to .feature-memory/errors.log."""
    try:
        error_path = Path.cwd() / ".feature-memory" / "errors.log"
        with open(error_path, "a", encoding="utf-8") as f:
            f.write(f"{datetime.now(timezone.utc).isoformat()} {message}\n")
    except Exception:
        pass


_TAGS_IMPACT  = ["breaking-change", "api-change", "schema-change", "config-change", "data-migration"]
_TAGS_QUALITY = ["security", "auth", "performance", "error-handling", "logging", "accessibility", "ux"]
_TAGS_PROCESS = ["tests", "docs", "dependency", "tooling", "ci-cd"]
_TAGS_TECH    = ["typescript", "python", "javascript", "html-css", "shell", "yaml", "sql", "markdown"]
_TAG_PRIORITY = [_TAGS_IMPACT, _TAGS_QUALITY, _TAGS_PROCESS, _TAGS_TECH]
_TAG_LIMIT    = 5


def _infer_tags(paths, message, kind):
    """Return up to 5 canonical tags inferred from file paths, commit message, and kind.

    Priority order: Impact > Quality > Process > Tech.
    Safe with None/empty inputs — never raises.
    """
    msg    = (message or "").lower()
    raw    = message or ""
    tags   = set()
    npaths = [p.replace("\\", "/").lower() for p in (paths or [])]
    bases  = [p.rsplit("/", 1)[-1] for p in npaths]
    exts   = {b.rsplit(".", 1)[-1] for b in bases if "." in b}

    # ── Impact ────────────────────────────────────────────────────────────────
    if re.search(r'\bbreaking\b|\bBREAKING\b|\bincompatible\b|\bdeprecated\b', raw):
        tags.add("breaking-change")
    if re.search(r'\bapi\s*(change|update|break|version|endpoint)\b|\bopenapi\b|\bswagger\b', msg):
        tags.add("api-change")
    if re.search(r'\bschema\b|\balter\s+table\b|\badd\s+column\b|\bdrop\s+column\b', msg):
        tags.add("schema-change")
    if re.search(r'\bdata\s+(migration|backfill)\b|\bmigrate\s+data\b', msg):
        tags.add("data-migration")
    if any(re.search(r'(^|/)(config\.(yaml|json|py|ini|toml)|settings\.(py|json)|\.env(\..+)?$)', p)
           for p in npaths):
        tags.add("config-change")

    # ── Quality ───────────────────────────────────────────────────────────────
    if re.search(r'\bsecur\w*|\bvuln\w*|\bcve[\s\-]?\d|\bxss\b|\bsqli\b|\binjection\b|\bsanitiz\w*', msg):
        tags.add("security")
    if re.search(r'\bauth\w*|\blogin\b|\blogout\b|\bjwt\b|\boauth\b|\bcredential\w*|\bpermission\w*|\brole\b', msg):
        tags.add("auth")
    if re.search(r'\bperf\w*|\boptim\w*|\bspeed\b|\bcach\w*|\blatency\b|\bthroughput\b', msg):
        tags.add("performance")
    if re.search(r'\berror\b|\bexception\w*|\bretry\w*|\bfallback\w*', msg):
        tags.add("error-handling")
    if re.search(r'\blogg\w*|\btracing\b|\bmonitor\w*|\bobserv\w*|\btelemetr\w*', msg):
        tags.add("logging")
    if re.search(r'\baccessib\w*|\baria\b|\bwcag\b|\ba11y\b', msg):
        tags.add("accessibility")
    if re.search(r'\b(?:ui|ux)\b|\binterface\b|\blayout\b|\btheme\b', msg):
        tags.add("ux")

    # ── Process ───────────────────────────────────────────────────────────────
    if any(
        re.search(r'(^|/)tests?/', p) or re.search(r'(_test\.|\.test\.|\.spec\.)', p)
        for p in npaths
    ):
        tags.add("tests")
    if any(
        p.startswith("docs/") or p.startswith("doc/") or
        re.search(r'(^|/)(readme|changelog)(\.|$)', b)
        for p, b in zip(npaths, bases)
    ):
        tags.add("docs")
    if any(
        re.search(
            r'requirements.*\.txt|pipfile|pyproject\.toml|setup\.(cfg|py)|go\.(mod|sum)'
            r'|gemfile(\.lock)?|\.lock$|package(-lock)?\.json|yarn\.lock',
            p,
        )
        for p in npaths
    ):
        tags.add("dependency")
    if any(
        re.search(r'(^|/)\.github/', p) or re.search(r'^(jenkinsfile|\.gitlab-ci)', b)
        for p, b in zip(npaths, bases)
    ):
        tags.add("ci-cd")
    if any(
        re.search(r'(^|/)scripts?/', p) or re.search(r'^(makefile|taskfile)', b)
        for p, b in zip(npaths, bases)
    ):
        tags.add("tooling")

    # ── Tech (file extensions) ────────────────────────────────────────────────
    if exts & {"ts", "tsx"}:                    tags.add("typescript")
    if "py" in exts:                            tags.add("python")
    if exts & {"js", "jsx"}:                   tags.add("javascript")
    if exts & {"html", "css", "scss", "less"}: tags.add("html-css")
    if exts & {"sh", "bash", "zsh"}:           tags.add("shell")
    if exts & {"yaml", "yml"}:                 tags.add("yaml")
    if "sql" in exts:                          tags.add("sql")
    if exts & {"md", "rst"}:                   tags.add("markdown")

    # ── Cap at 5, honouring priority order ───────────────────────────────────
    result = []
    for category in _TAG_PRIORITY:
        for tag in category:
            if tag in tags:
                if len(result) >= _TAG_LIMIT:
                    return result
                result.append(tag)
    return result


_VIEWER_VERSION = 7  # increment when the viewer template gets significant UI changes


def _check_viewer_update(docs_root):
    """Copy updated viewer template to docs_root if the installed version is outdated.

    Preserves existing changelog JSON data by re-injecting it after the copy.
    Silently no-ops if the template cannot be found.
    """
    import re as _re
    import shutil
    viewer_path = docs_root / "changelog-viewer.html"
    if not viewer_path.exists():
        return  # Nothing to update — will be created on next Stop hook run

    try:
        current = viewer_path.read_text(encoding="utf-8")
        m = _re.search(r'<!--\s*fm-viewer-version:\s*(\d+)\s*-->', current)
        installed_ver = int(m.group(1)) if m else 0
        if installed_ver >= _VIEWER_VERSION:
            return  # Already up to date

        # Locate the template — try both installed cache layout (../assets/)
        # and source layout (../../assets/ for plugin/hooks/ → plugin/assets/)
        hooks_dir = Path(__file__).parent
        candidates = [
            hooks_dir / ".." / "assets" / "changelog-viewer.html",
            hooks_dir / ".." / ".." / "assets" / "changelog-viewer.html",
            Path.cwd() / "plugin" / "assets" / "changelog-viewer.html",
        ]
        template = None
        for c in candidates:
            resolved = c.resolve()
            if resolved.exists():
                template = resolved
                break
        if template is None:
            return

        # Extract existing JSON data block before overwriting
        data_match = _re.search(
            r'(<script id="changelog-data"[^>]*>)([\s\S]*?)(</script>)',
            current,
        )
        existing_json = data_match.group(2) if data_match else None

        shutil.copy2(str(template), str(viewer_path))

        # Re-inject the existing data if we extracted it
        if existing_json:
            new_content = viewer_path.read_text(encoding="utf-8")
            patched = _re.sub(
                r'(<script id="changelog-data"[^>]*>)([\s\S]*?)(</script>)',
                lambda m2: m2.group(1) + existing_json + m2.group(3),
                new_content,
                count=1,
            )
            viewer_path.write_text(patched, encoding="utf-8")
    except Exception:
        pass  # Viewer update is best-effort; never fail a session over it


def hook_error_wrapper(hook_name, main_func):
    """Wrap a hook's main function with error handling."""
    try:
        main_func()
    except Exception as e:
        log_error(f"{hook_name} ERROR: {e}")
        output = {"result": "continue", "message": f"[FM] {hook_name} hook error: {e}"}
        json.dump(output, sys.stdout)
