#!/usr/bin/env python3
# -*- coding: utf-8 -*-
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
    """Load feature metadata from config.yaml without requiring PyYAML.

    Returns {feature_id: {"title": str, "globs": [str], "mode": str|None}}.
    Falls back to title-casing the feature_id if 'title:' is absent.
    """
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
                features[current_feature] = {
                    "title": current_feature.replace("-", " ").title(),
                    "globs": [],
                    "mode": None,
                }
                in_globs = False
                continue

            if current_feature and stripped.startswith("title:"):
                title_val = stripped[6:].strip().strip('"').strip("'")
                if title_val:
                    features[current_feature]["title"] = title_val
                continue

            if current_feature and stripped.startswith("mode:"):
                mode_val = stripped[5:].strip().strip('"').strip("'")
                if mode_val:
                    features[current_feature]["mode"] = mode_val
                continue

            if stripped == "globs:":
                in_globs = True
                continue

            if in_globs and stripped.startswith("- "):
                glob_pattern = stripped[2:].strip().strip('"').strip("'")
                if current_feature:
                    features[current_feature]["globs"].append(glob_pattern)
                continue

            # Any non-glob key (owner:, etc.) exits glob parsing
            if not stripped.startswith("- ") and ":" in stripped:
                in_globs = False

    if not features and config_path.stat().st_size > 50:
        log_error("YAML parse warning: config.yaml has content but no features were parsed. "
                  "Check indentation (must use 2-space indent).")

    return features


def get_feature_globs(features):
    """Extract flat {feature_id: [globs]} from the rich load_config() output."""
    return {fid: val.get("globs", []) for fid, val in features.items()}


def load_tag_strategy(project_dir):
    """Read tagging.strategy from config.yaml. Returns 'cli', 'keyword', or 'none'."""
    config_path = project_dir / ".feature-memory" / "config.yaml"
    if not config_path.exists():
        return "cli"
    try:
        in_tagging = False
        for line in config_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped == "tagging:":
                in_tagging = True
                continue
            if in_tagging and not line.startswith(" ") and not line.startswith("\t") and stripped:
                in_tagging = False
                continue
            if in_tagging and stripped.startswith("strategy:"):
                val = stripped[9:].strip().strip('"').strip("'").split("#")[0].strip()
                if val in ("cli", "keyword", "none"):
                    return val
    except Exception:
        pass
    return "cli"


def _changelog_defaults():
    """Fresh default changelog-config dict (never share mutable defaults)."""
    return {
        "verbosity": "normal",  # terse | normal | detailed
        "summary_rule": "",
        "tagging": True,
        "highlight_tags": [
            "breaking-change", "api-change", "security",
            "schema-change", "data-migration",
        ],
        "metrics": {"enabled": True, "code_churn": False},
        "custom_docs": {"enabled": True, "dir": "docs/feature-memory/custom"},
    }


def _yaml_scalar(raw):
    """Resolve a YAML scalar value.

    Quoted values are taken verbatim (``#`` inside quotes is preserved). For
    unquoted values a whitespace-preceded ``#`` begins a comment and is
    dropped (standard YAML). To keep a literal ``#`` in ``summary_rule``,
    quote the value.
    """
    s = raw.strip()
    if s[:1] in ('"', "'"):
        q = s[0]
        end = s.find(q, 1)
        return s[1:end] if end != -1 else s[1:]
    m = re.search(r"\s#", s)
    if m:
        s = s[:m.start()]
    return s.strip()


def _yaml_bool(raw, default):
    v = _yaml_scalar(raw).lower()
    if v in ("true", "yes", "on", "1"):
        return True
    if v in ("false", "no", "off", "0"):
        return False
    return default


def load_changelog_config(project_dir):
    """Parse the optional nested ``changelog:`` block from config.yaml.

    Independent of the flat single-level parsers (``load_config``,
    ``load_tag_strategy``, ``load_skip_patterns``) because it needs a
    two-level state machine (``metrics:`` / ``custom_docs:`` grandchildren and
    a ``highlight_tags:`` block list). Tab indentation is rejected (YAML
    forbids it) and any failure falls back to full defaults. Never raises.

    Returns a fully-defaulted dict so callers can index it unconditionally.
    """
    cfg = _changelog_defaults()
    config_path = project_dir / ".feature-memory" / "config.yaml"
    if not config_path.exists():
        return cfg
    try:
        in_block = False
        current_sub = None       # None | 'metrics' | 'custom_docs' | 'highlight_tags'
        hl = None                # collected highlight tags once the key is seen
        for line in config_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            stripped = line.strip()

            if not in_block:
                if stripped == "changelog:":
                    in_block = True
                continue

            indent_str = line[:len(line) - len(line.lstrip(" \t"))]
            if "\t" in indent_str:
                log_error(
                    "load_changelog_config: tab indentation in changelog "
                    "block (YAML forbids tabs); using defaults"
                )
                return _changelog_defaults()
            indent = len(indent_str)

            if indent == 0:
                break  # a column-0 key ends the changelog block

            if indent < 4:
                # Level-1 key: scalar, mapping header, or list header.
                current_sub = None
                if stripped.endswith(":") and " " not in stripped[:-1]:
                    key = stripped[:-1]
                    if key in ("metrics", "custom_docs"):
                        current_sub = key
                    elif key == "highlight_tags":
                        current_sub = "highlight_tags"
                        hl = []
                    continue
                key, _, rawval = stripped.partition(":")
                key = key.strip()
                if key == "verbosity":
                    v = _yaml_scalar(rawval)
                    cfg["verbosity"] = v if v in ("terse", "normal", "detailed") else "normal"
                elif key == "summary_rule":
                    cfg["summary_rule"] = _yaml_scalar(rawval).replace("\n", " ")[:500]
                elif key == "tagging":
                    cfg["tagging"] = _yaml_bool(rawval, True)
                continue

            # indent >= 4: grandchild of metrics/custom_docs or a list item.
            if current_sub == "highlight_tags" and stripped.startswith("- "):
                tag = _yaml_scalar(stripped[2:])
                if tag and hl is not None:
                    hl.append(tag)
                continue
            if current_sub in ("metrics", "custom_docs") and ":" in stripped:
                key, _, rawval = stripped.partition(":")
                key = key.strip()
                sub = cfg[current_sub]
                if current_sub == "metrics" and key in ("enabled", "code_churn"):
                    sub[key] = _yaml_bool(rawval, sub[key])
                elif current_sub == "custom_docs" and key == "enabled":
                    sub["enabled"] = _yaml_bool(rawval, sub["enabled"])
                elif current_sub == "custom_docs" and key == "dir":
                    d = _yaml_scalar(rawval)
                    if d:
                        sub["dir"] = d.replace("\\", "/")
                continue

        if hl is not None and hl:
            cfg["highlight_tags"] = hl
        return cfg
    except Exception as e:
        log_error("load_changelog_config error: %s" % e)
        return _changelog_defaults()


def match_path_to_features(file_path, features):
    """Match a file path against feature globs. Returns list of ALL matching feature IDs.

    Accepts both old {id: [globs]} and new {id: {"globs": [...], ...}} shapes.
    """
    normalized = file_path.replace("\\", "/")
    matched = []

    for feature_id, globs_or_meta in features.items():
        globs = globs_or_meta.get("globs", []) if isinstance(globs_or_meta, dict) else globs_or_meta
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


def get_feature_doc_path(feature_id, docs_root, feature_meta=None):
    """Return canonical feature doc path, handling flat and split layouts.

    If feature_meta contains an explicit 'mode' key ('split'|'small'), it is
    honoured. Otherwise falls back to existence-check heuristic.
    """
    if isinstance(feature_meta, dict):
        mode = feature_meta.get("mode")
        if mode == "split":
            return docs_root / "features" / feature_id / "index.md"
        if mode == "small":
            return docs_root / "features" / f"{feature_id}.md"
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
_TAG_PRIORITY = [_TAGS_IMPACT, _TAGS_QUALITY, _TAGS_PROCESS]
_TAG_LIMIT    = 5


def _infer_tags(paths, message, kind):
    """Return up to 5 canonical Impact/Quality/Process tags inferred from paths and message.

    Tech/language tags removed — use generate_topic_tags_batch() for semantic topic tags.
    Safe with None/empty inputs — never raises.
    """
    msg    = (message or "").lower()
    raw    = message or ""
    tags   = set()
    npaths = [p.replace("\\", "/").lower() for p in (paths or [])]
    bases  = [p.rsplit("/", 1)[-1] for p in npaths]

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

    # ── Cap at 5, honouring priority order ───────────────────────────────────
    result = []
    for category in _TAG_PRIORITY:
        for tag in category:
            if tag in tags:
                if len(result) >= _TAG_LIMIT:
                    return result
                result.append(tag)
    return result


def _infer_audience(paths, message, tags):
    """Infer entry audience from file paths, commit message, and tags.

    Returns 'product', 'developer', or 'both'.
    - 'developer': pure internal paths (tests, config, infra, docs)
    - 'product': paths touching user-facing surfaces only
    - 'both': mixed, or any path that could affect user behavior
    """
    npaths = [p.replace("\\", "/").lower() for p in (paths or [])]
    msg = (message or "").lower()

    internal_indicators = [
        lambda p: re.search(r'(^|/)tests?/', p) or re.search(r'(_test\.|\.test\.|\.spec\.)', p),
        lambda p: re.search(r'\.(yaml|yml|json|lock|toml|cfg|ini)$', p),
        lambda p: p.startswith('.') or '/.github/' in p or '/ci/' in p,
        lambda p: re.search(r'(makefile|dockerfile|\.sh$)', p),
    ]
    product_indicators = [
        lambda p: re.search(r'\.(html|css|jsx?|tsx?)$', p) and 'test' not in p,
        lambda p: re.search(r'/(views?|templates?|components?|pages?|ui)/', p),
        lambda p: re.search(r'/(api|routes?|endpoints?)/', p),
    ]

    internal_count = sum(1 for p in npaths if any(fn(p) for fn in internal_indicators))
    product_count  = sum(1 for p in npaths if any(fn(p) for fn in product_indicators))

    if re.search(r'\bbreaking\b|\bapi\b', msg) or (tags and "breaking-change" in tags):
        return "both"
    if not npaths:
        return "both"
    if internal_count == len(npaths):
        return "developer"
    if product_count > 0 and internal_count == 0:
        return "product"
    return "both"


def _infer_kind(paths, message):
    """Infer change kind from commit message."""
    m = (message or "").lower()
    if any(k in m for k in ("fix", "bug", "patch", "repair", "hotfix")):
        return ["bug-fix"]
    if any(k in m for k in ("add ", "new ", "feat", "implement", "create", "introduce", "initial")):
        return ["new-feature"]
    if any(k in m for k in ("refactor", "cleanup", "clean up", "rename", "reorganize", "move", "extract")):
        return ["refactor"]
    return ["behavior-change"]


def _keyword_tags_for_entry(entry):
    """Derive 1-2 topic tags from file paths heuristically (air-gap fallback)."""
    paths = entry.get("paths") or []
    tags = []
    _generic = {'src', 'lib', 'app', 'plugin', 'hooks', 'the', 'and'}
    for path in paths[:3]:
        parts = path.replace("\\", "/").split("/")
        # Take the most-specific non-generic directory component
        for part in reversed(parts[:-1]):  # skip filename
            slug = re.sub(r'[^a-z0-9]+', '-', part.lower()).strip('-')
            if len(slug) >= 3 and slug not in _generic:
                if slug not in tags:
                    tags.append(slug)
                    break
        if len(tags) >= 2:
            break
    return tags[:2]


def rotate_events_if_oversized(events_path, max_mb=5):
    """Rotate events.jsonl to events-overflow-{timestamp}.jsonl if it exceeds max_mb."""
    try:
        if not events_path.exists():
            return
        size_mb = events_path.stat().st_size / (1024 * 1024)
        if size_mb < max_mb:
            return
        ts = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        overflow = events_path.parent / f"events-overflow-{ts}.jsonl"
        events_path.rename(overflow)
        log_error(f"events.jsonl exceeded {max_mb}MB, rotated to {overflow.name}")
    except Exception as e:
        log_error(f"rotate_events_if_oversized error: {e}")


_TOPIC_TAG_RE = re.compile(r'^[a-z][a-z0-9-]{0,29}$')


_VERBOSITY_TAG_CAP = {"terse": 1, "normal": 3, "detailed": 5}


def verbosity_tag_cap(verbosity):
    """Map a configured verbosity level to a topic-tag count cap."""
    return _VERBOSITY_TAG_CAP.get(verbosity, 3)


def _sanitize_rule(rule):
    """Make a user ``summary_rule`` safe to splice into the LLM prompt.

    Collapse newlines (prevents breaking the strict one-line-per-entry
    output contract) and length-cap. The value is already trusted-ish (the
    user's own config) but bounding it keeps the prompt well-formed.
    """
    return " ".join(str(rule or "").split())[:500]


def _build_topic_prompt(entries, summary_rule="", max_tags=3):
    """Build a batched prompt for generating semantic topic tags.

    Uses numeric indices (0, 1, 2 ...) to avoid event_id format issues.
    Each entry needs: feature_id, paths, git_message.
    ``max_tags`` reflects the configured verbosity (terse=1/normal=3/detailed=5).
    ``summary_rule`` is an optional project-specific steering instruction.
    """
    n = max(1, int(max_tags))
    lines = [
        "You are tagging software changelog entries with 1-%d semantic topic tags." % n,
        "Rules:",
        "- 1 to %d tags per entry, lowercase kebab-case, 1-3 words each" % n,
        "- Tags describe the SUBSYSTEM or CONCEPT being worked on",
        "  (e.g. session-hooks, changelog-viewer, tag-system, plugin-init, config-parser)",
        "- NO language/tech tags (no python, typescript, html, yaml, shell, etc.)",
        "- NO generic verbs (no update, fix, refactor, change, add)",
        "- Output EXACTLY one line per entry: <index>: tag-one, tag-two",
        "- Only output those lines, nothing else",
    ]
    rule = _sanitize_rule(summary_rule)
    if rule:
        lines.append("- ADDITIONAL PROJECT RULE: " + rule)
    lines.append("")
    for i, e in enumerate(entries):
        fid = e.get("feature_id") or "unmapped"
        msg = (e.get("git_message") or "").strip()[:120]
        paths_str = ", ".join((e.get("paths") or [])[:5])
        lines.append(f"---")
        lines.append(f"{i}: feature={fid} | files={paths_str} | msg={msg}")
    return "\n".join(lines)


def _parse_topic_tags(text, count, max_tags=3):
    """Parse lines like '0: tag-one, tag-two' from LLM output.

    Returns a list of tag lists indexed 0..count-1, each capped at max_tags.
    """
    cap = max(1, int(max_tags))
    result = [[] for _ in range(count)]
    for line in (text or "").splitlines():
        m = re.match(r'^(\d+):\s*(.+)$', line.strip())
        if not m:
            continue
        idx = int(m.group(1))
        if idx >= count:
            continue
        parts = [p.strip().lower() for p in m.group(2).split(",")]
        result[idx] = [p for p in parts if _TOPIC_TAG_RE.match(p)][:cap]
    return result


def generate_topic_tags_batch(entries, batch_size=15, timeout=45, strategy='cli',
                               min_interval_s=0.5, summary_rule="", max_tags=3):
    """Generate semantic topic tags for a list of changelog entries.

    strategy:
      'cli'     — use claude CLI (default); degrades to empty lists if unavailable.
      'keyword' — heuristic from file path directory components (air-gap safe).
      'none'    — skip entirely; leave topic_tags as empty lists.

    Returns a list of tag lists aligned with the input entries list.
    Never raises.
    """
    import shutil
    import time
    result = [[] for _ in entries]

    if strategy == 'none':
        return result

    cap = max(1, int(max_tags))

    if strategy == 'keyword':
        return [_keyword_tags_for_entry(e)[:cap] for e in entries]

    # strategy == 'cli'
    if not shutil.which("claude"):
        return result

    def _chunks(lst, n):
        for i in range(0, len(lst), n):
            yield lst[i:i + n]

    offset = 0
    first_batch = True
    for batch in _chunks(entries, batch_size):
        if not first_batch and min_interval_s > 0:
            time.sleep(min_interval_s)
        first_batch = False
        prompt = _build_topic_prompt(batch, summary_rule=summary_rule, max_tags=cap)
        try:
            r = subprocess.run(
                ["claude", "-p", prompt, "--output-format", "text"],
                capture_output=True, text=True, timeout=timeout,
            )
            if r.returncode == 0:
                parsed = _parse_topic_tags(r.stdout, len(batch), max_tags=cap)
                for j, tags in enumerate(parsed):
                    result[offset + j] = tags
        except (subprocess.TimeoutExpired, OSError, Exception):
            pass
        offset += len(batch)
    return result


_VIEWER_VERSION = 11  # increment when the viewer template gets significant UI changes

# Paths matching these globs are never recorded as changelog entries.
# Covers generated/compiled artifacts, caches, lock files, and IDE state.
DEFAULT_SKIP_PATTERNS = [
    "*.pyc", "*.pyo", "*.pyd", "*.pdb",
    "__pycache__/**",
    "*.min.js", "*.min.css",
    "node_modules/**",
    "dist/**", "build/**",
    ".mypy_cache/**", ".pytest_cache/**", ".ruff_cache/**", ".cache/**",
    "*.lock", "package-lock.json",
    ".DS_Store", "Thumbs.db",
    "*.egg-info/**",
    ".venv/**", "venv/**", "env/**",
    ".coverage", "coverage/**", "htmlcov/**",
    ".git/**",
]


def load_skip_patterns(project_dir):
    """Return the effective skip-pattern list for a project.

    Reads the optional ``skip_patterns:`` section from .feature-memory/config.yaml
    and merges it with DEFAULT_SKIP_PATTERNS (user additions extend, not replace).
    Never raises.
    """
    config_path = project_dir / ".feature-memory" / "config.yaml"
    user_patterns = []

    if config_path.exists():
        try:
            in_skip = False
            for line in config_path.read_text(encoding="utf-8").splitlines():
                stripped = line.strip()
                if stripped == "skip_patterns:":
                    in_skip = True
                    continue
                if in_skip and not line.startswith((" ", "\t")) and stripped:
                    in_skip = False
                    continue
                if in_skip and stripped.startswith("- "):
                    pat = stripped[2:].strip().strip('"').strip("'")
                    if pat:
                        user_patterns.append(pat)
        except Exception:
            pass

    seen = set()
    combined = []
    for p in DEFAULT_SKIP_PATTERNS + user_patterns:
        if p not in seen:
            combined.append(p)
            seen.add(p)
    return combined


def should_skip_path(file_path, skip_patterns):
    """Return True if file_path matches any skip pattern.

    Patterns without a slash are matched against the basename only;
    patterns with a trailing ``/**`` match directory prefixes;
    all others use standard fnmatch glob matching on the full path.
    """
    normalized = file_path.replace("\\", "/")
    basename = normalized.rsplit("/", 1)[-1]
    for pattern in skip_patterns:
        if pattern.endswith("/**"):
            prefix = pattern[:-3]
            if normalized.startswith(prefix + "/") or normalized == prefix:
                return True
        elif "/" not in pattern:
            if fnmatch.fnmatch(basename, pattern):
                return True
        else:
            if fnmatch.fnmatch(normalized, pattern):
                return True
    return False


def dump_inline_json(data):
    """Serialize ``data`` for embedding inside an HTML <script> element.

    ``json.dumps`` does not escape ``/``, so a string value containing the
    literal ``</script>`` (entirely plausible in a user-authored custom doc
    that talks about HTML/CSP/the viewer) would prematurely close the data
    element — breaking ``JSON.parse`` in the viewer AND corrupting the
    regex-based re-injection on the next Stop (permanent data loss).

    Escaping ``</`` as ``<\\/`` is JSON-safe: ``\\/`` is a valid JSON escape
    for ``/`` so ``JSON.parse`` decodes it back to ``/`` in the browser, while
    the HTML tokenizer never sees a closing tag. Used by every writer that
    injects JSON into changelog-viewer.html.
    """
    return json.dumps(data, indent=2, ensure_ascii=False).replace("</", "<\\/")


def changelog_config_echo(cfg):
    """Slim, viewer-facing echo of the effective changelog config.

    Embedded as ``data.config`` so the offline viewer can adapt (verbosity,
    highlight tags, which tabs to show) without re-reading YAML. Additive and
    optional — old viewers ignore it, new viewers default it when absent.
    """
    cfg = cfg or {}
    return {
        "verbosity": cfg.get("verbosity", "normal"),
        "highlight_tags": list(cfg.get("highlight_tags", [])),
        "custom_docs_enabled": bool(cfg.get("custom_docs", {}).get("enabled", True)),
        "metrics_enabled": bool(cfg.get("metrics", {}).get("enabled", True)),
    }


def inject_inline_json_block(viewer_text, block_id, data):
    """Replace a ``<script id="{block_id}" ...>...</script>`` body with ``data``.

    JSON-in-HTML safe (uses :func:`dump_inline_json`). Returns the new text, or
    the unchanged text if the block is absent (older viewer/template). Never
    raises. Used for the separate ``custom-docs-data`` slot so custom docs stay
    isolated from the append-only changelog-data block.
    """
    try:
        pat = r'(<script id="%s"[^>]*>)([\s\S]*?)(</script>)' % re.escape(block_id)
        payload = dump_inline_json(data)
        return re.sub(
            pat,
            lambda m: m.group(1) + "\n" + payload + "\n" + m.group(3),
            viewer_text,
            count=1,
        )
    except Exception as e:
        log_error("inject_inline_json_block(%s) error: %s" % (block_id, e))
        return viewer_text


def _check_viewer_update(docs_root):
    """Copy updated viewer template to docs_root if the installed version is outdated.

    Preserves existing changelog JSON data by re-injecting it after the copy.
    Silently no-ops if the template cannot be found.

    Version detection requires at least ONE of two markers:
      - HTML comment: <!-- fm-viewer-version: N -->
      - Meta tag:     <meta name="fm-viewer-version" content="N">
    If neither is parseable, logs to errors.log and skips the upgrade.
    """
    import re as _re
    import shutil
    viewer_path = docs_root / "changelog-viewer.html"
    if not viewer_path.exists():
        return  # Nothing to update — will be created on next Stop hook run

    try:
        current = viewer_path.read_text(encoding="utf-8")

        # Try HTML comment marker
        m_comment = _re.search(r'<!--\s*fm-viewer-version:\s*(\d+)\s*-->', current)
        # Try meta tag marker
        m_meta = _re.search(r'<meta\s+name="fm-viewer-version"\s+content="(\d+)"', current)

        if m_comment is None and m_meta is None:
            log_error("_check_viewer_update: neither version comment nor meta tag found in "
                      f"{viewer_path.name}; skipping upgrade to avoid overwriting custom viewer.")
            return

        installed_ver = int((m_comment or m_meta).group(1))
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
