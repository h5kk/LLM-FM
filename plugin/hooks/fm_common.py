#!/usr/bin/env python3
"""Shared utilities for Feature Memory hooks.

Extracted to avoid code duplication across PostToolUse, Stop, and SessionStart hooks.
Works with Python 3.6+ stdlib only — no external dependencies.
"""
import fnmatch
import json
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
                glob_pattern = stripped[2:].strip()
                if current_feature:
                    features[current_feature].append(glob_pattern)
                continue

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


def hook_error_wrapper(hook_name, main_func):
    """Wrap a hook's main function with error handling."""
    try:
        main_func()
    except Exception as e:
        log_error(f"{hook_name} ERROR: {e}")
        output = {"result": "continue", "message": f"[FM] {hook_name} hook error: {e}"}
        json.dump(output, sys.stdout)
