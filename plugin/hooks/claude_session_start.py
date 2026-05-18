#!/usr/bin/env python3
"""SessionStart hook: inject Feature Memory context and clear stale events."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from fm_common import hook_error_wrapper


def main():
    try:
        hook_input = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        hook_input = {}

    project_dir = Path.cwd()
    docs_root = project_dir / "docs" / "feature-memory"

    if not docs_root.exists():
        return

    events_path = project_dir / ".feature-memory" / "events.jsonl"
    if events_path.exists():
        events_path.write_text("", encoding="utf-8")

    lines = []
    lines.append("=== Feature Memory ===")
    rel_docs = docs_root.relative_to(project_dir).as_posix()
    lines.append(f"Docs root: {rel_docs}")
    lines.append("")

    index_path = docs_root / "index.md"
    if index_path.exists():
        index_content = index_path.read_text(encoding="utf-8")
        in_table = False
        feature_lines = []
        for line in index_content.splitlines():
            if line.startswith("| Feature"):
                in_table = True
                continue
            if in_table and line.startswith("|---"):
                continue
            if in_table and line.startswith("|"):
                feature_lines.append(line.strip())
            elif in_table:
                in_table = False
        if feature_lines:
            lines.append("Documented features:")
            for fl in feature_lines:
                lines.append(f"  {fl}")
            lines.append("")

    recent_path = docs_root / "recent.md"
    if recent_path.exists():
        recent_content = recent_path.read_text(encoding="utf-8")
        in_frontmatter = False
        content_lines = []
        for line in recent_content.splitlines():
            if line.strip() == "---":
                in_frontmatter = not in_frontmatter
                continue
            if not in_frontmatter:
                content_lines.append(line)
        if content_lines:
            lines.append("Recent activity:")
            for cl in content_lines[:10]:
                if cl.strip():
                    lines.append(f"  {cl}")
            lines.append("")

    lines.append("Rules: Update feature docs after changing user-facing behavior.")
    lines.append("       Do not reorganize hierarchy; write proposals to reports/.")

    output = {"result": "continue", "message": "\n".join(lines)}
    json.dump(output, sys.stdout)


if __name__ == "__main__":
    hook_error_wrapper("SessionStart", main)
