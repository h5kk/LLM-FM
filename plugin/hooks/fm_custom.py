#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Custom changelog / wiki doc ingestion (stdlib only).

User-authored markdown files under the configured custom-docs dir (default
``docs/feature-memory/custom/``) are surfaced in the changelog viewer:

  * ``doc_type: entry`` -> a manual timeline entry (a "custom" badge).
  * ``doc_type: wiki``  -> a long-form reference doc in the viewer's Wiki tab.

Council decision (blocker ii): these are NOT merged into
``claude_stop._compile_changelog`` (which is append-only and reloads from the
persisted changelog.json every run, so it has no delete path). Instead this
module rebuilds a SEPARATE data slot from scratch on every Stop, giving true
re-scan / delete semantics — removing a file simply drops its doc next compile.

CLI (also exposed as the /feature-memory-changelog-custom skill):
    python plugin/hooks/fm_custom.py --list
    python plugin/hooks/fm_custom.py --validate [--json]

Never raises into a hook: all parsing failures are collected and reported.
"""
import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from fm_common import load_changelog_config, _yaml_scalar, log_error

_VALID_DOC_TYPES = ("entry", "wiki")
_VALID_AUDIENCES = ("product", "developer", "both")
_VALID_VERBOSITY = ("terse", "normal", "detailed")
_SLOT_SCHEMA = 2


def _slug(text):
    return re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-") or "doc"


def _parse_inline_list(raw):
    """Parse a flow list ``[a, b, "c d"]`` into a list of strings."""
    inner = raw.strip()
    if inner.startswith("[") and inner.endswith("]"):
        inner = inner[1:-1]
    out = []
    for part in inner.split(","):
        v = _yaml_scalar(part)
        if v:
            out.append(v)
    return out


def parse_frontmatter(text):
    """Return ``(meta: dict, body: str)`` from a markdown string.

    A leading ``---`` fenced block is parsed as ``key: value`` pairs (inline
    ``[..]`` lists and quoted scalars supported, reusing fm_common's scalar
    rules). No frontmatter -> ``({}, full_text)``. Never raises.
    """
    meta = {}
    if not text.startswith("---"):
        return meta, text
    lines = text.splitlines()
    # First line must be exactly the opening fence.
    if lines[0].strip() != "---":
        return meta, text
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return meta, text  # unterminated fence: treat all as body
    for line in lines[1:end]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if ":" not in line:
            continue
        key, _, rawval = line.partition(":")
        key = key.strip()
        rawval = rawval.strip()
        if not key:
            continue
        if rawval.startswith("["):
            meta[key] = _parse_inline_list(rawval)
        else:
            meta[key] = _yaml_scalar(rawval)
    body = "\n".join(lines[end + 1:]).strip("\n")
    return meta, body


def _coerce_bool(val, default):
    s = str(val).strip().lower()
    if s in ("true", "yes", "on", "1"):
        return True
    if s in ("false", "no", "off", "0"):
        return False
    return default


def _doc_from_file(path, rel, changelog_cfg, today):
    """Build one doc dict + a list of human-readable issues for --validate."""
    issues = []
    try:
        text = path.read_text(encoding="utf-8")
    except Exception as e:
        return None, ["%s: unreadable (%s)" % (rel, e)]

    meta, body = parse_frontmatter(text)

    doc_type = str(meta.get("doc_type", "wiki")).strip().lower()
    if doc_type not in _VALID_DOC_TYPES:
        if "doc_type" in meta:
            issues.append("%s: invalid doc_type %r -> defaulting to 'wiki'" % (rel, meta.get("doc_type")))
        doc_type = "wiki"

    audience = str(meta.get("audience", "both")).strip().lower()
    if audience not in _VALID_AUDIENCES:
        if "audience" in meta:
            issues.append("%s: invalid audience %r -> 'both'" % (rel, meta.get("audience")))
        audience = "both"

    verbosity = str(meta.get("verbosity", changelog_cfg.get("verbosity", "normal"))).strip().lower()
    if verbosity not in _VALID_VERBOSITY:
        issues.append("%s: invalid verbosity %r -> 'normal'" % (rel, meta.get("verbosity")))
        verbosity = "normal"

    date = str(meta.get("date", "")).strip() or today
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", date):
        issues.append("%s: invalid/absent date %r -> %s" % (rel, meta.get("date"), today))
        date = today

    title = str(meta.get("title", "")).strip() or path.stem.replace("-", " ").replace("_", " ").title()

    global_tagging = changelog_cfg.get("tagging", True)
    doc_tagging = _coerce_bool(meta.get("tagging", global_tagging), global_tagging) and global_tagging

    raw_tags = meta.get("tags", [])
    if isinstance(raw_tags, str):
        raw_tags = [t.strip() for t in raw_tags.split(",") if t.strip()]
    tags = [str(t).strip() for t in (raw_tags or []) if str(t).strip()]

    feature_id = str(meta.get("feature_id", "")).strip() or None
    feature_title = str(meta.get("feature_title", "")).strip() or (feature_id or None)

    if not body.strip():
        issues.append("%s: empty body" % rel)

    doc = {
        "event_id": "custom-" + _slug(rel),
        "source": "custom",
        "doc_type": doc_type,
        "date": date,
        "title": title,
        "feature_id": feature_id,
        "feature_title": feature_title,
        "audience": audience,
        "verbosity": verbosity,
        "tagging": doc_tagging,
        "tags": tags,
        "topic_tags": [],
        "summary": title,
        "body_md": body,
        "path": rel,
        "confidence": "manual",
        "review_status": "manual",
        "kind": ["custom"],
    }
    return doc, issues


def load_custom_docs(project_dir, changelog_cfg=None):
    """Scan the custom-docs dir fresh and return ``(slot_dict, issues)``.

    ``slot_dict`` is the JSON object embedded as the viewer's
    ``<script id="custom-docs-data">`` block. Always returns a valid slot
    (possibly empty); never raises.
    """
    if changelog_cfg is None:
        changelog_cfg = load_changelog_config(project_dir)

    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")
    slot = {
        "schema_version": _SLOT_SCHEMA,
        "generated": now.isoformat(),
        "enabled": bool(changelog_cfg.get("custom_docs", {}).get("enabled", True)),
        "entries": [],
        "wiki": [],
    }
    issues = []

    if not slot["enabled"]:
        return slot, issues

    rel_dir = changelog_cfg.get("custom_docs", {}).get("dir", "docs/feature-memory/custom")
    custom_dir = (project_dir / rel_dir.replace("\\", "/")).resolve()
    try:
        proj_resolved = project_dir.resolve()
        # Keep the dir inside the project (defensive).
        if proj_resolved not in custom_dir.parents and custom_dir != proj_resolved:
            issues.append("custom_docs.dir %r is outside the project; ignored" % rel_dir)
            return slot, issues
    except Exception:
        pass

    if not custom_dir.is_dir():
        return slot, issues  # not set up yet — not an error

    try:
        files = sorted(p for p in custom_dir.rglob("*.md") if p.is_file())
    except Exception as e:
        log_error("fm_custom: rglob failed: %s" % e)
        return slot, issues

    seen = set()
    for path in files:
        try:
            rel = path.relative_to(project_dir).as_posix()
        except ValueError:
            rel = path.name
        doc, doc_issues = _doc_from_file(path, rel, changelog_cfg, today)
        issues.extend(doc_issues)
        if doc is None:
            continue
        if doc["event_id"] in seen:
            issues.append("%s: duplicate slug %s (skipped)" % (rel, doc["event_id"]))
            continue
        seen.add(doc["event_id"])
        (slot["entries"] if doc["doc_type"] == "entry" else slot["wiki"]).append(doc)

    slot["entries"].sort(key=lambda d: d.get("date", ""), reverse=True)
    slot["wiki"].sort(key=lambda d: d.get("title", "").lower())
    return slot, issues


# ── CLI ──────────────────────────────────────────────────────────────────────

def _cli(argv=None):
    parser = argparse.ArgumentParser(description="Feature Memory custom-doc tool")
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--list", action="store_true", help="list discovered custom docs")
    g.add_argument("--validate", action="store_true", help="validate custom docs")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args(argv)

    project_dir = Path.cwd()
    cfg = load_changelog_config(project_dir)
    slot, issues = load_custom_docs(project_dir, cfg)
    docs = slot["entries"] + slot["wiki"]

    if args.list:
        if args.json:
            print(json.dumps(slot, indent=2, ensure_ascii=False))
        else:
            if not slot["enabled"]:
                print("custom docs disabled (changelog.custom_docs.enabled: false)")
            elif not docs:
                print("No custom docs found in %s" % cfg["custom_docs"]["dir"])
            else:
                for d in docs:
                    print("[%s] %-7s %s  (%s)" % (
                        d["date"], d["doc_type"], d["title"], d["path"]))
        return 0

    # --validate
    if args.json:
        print(json.dumps({"ok": not issues, "count": len(docs),
                          "issues": issues}, indent=2))
    else:
        print("Scanned %d custom doc(s)." % len(docs))
        if issues:
            print("Issues:")
            for i in issues:
                print("  - " + i)
        else:
            print("All custom docs valid.")
    return 1 if issues else 0


if __name__ == "__main__":
    try:
        sys.exit(_cli())
    except SystemExit:
        raise
    except Exception as exc:  # never crash hard
        sys.stderr.write("[FM] fm_custom error: %s\n" % exc)
        sys.exit(0)
