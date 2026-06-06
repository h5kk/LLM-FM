# -*- coding: utf-8 -*-
# Polyglot hook bootstrap (Python 2 AND Python 3 safe).
#
# Why this file exists:
#   Claude Code launches plugin hooks with `command: "python"`. On some
#   machines `python` resolves to Python 2.7. The Feature Memory hooks are
#   Python 3.11 code (f-strings, etc.) and cannot even be *parsed* by
#   Python 2, so they fail with a SyntaxError before any error handling can
#   run. This bootstrap is deliberately written in the ASCII, no-f-string,
#   Python 2.6+/3.x common subset so it always parses, then it runs the real
#   hook under a guaranteed Python 3 interpreter.
#
# Contract:
#   argv[1] = hook module name without ".py" (e.g. "claude_stop").
#   stdin / stdout / stderr are passed straight through so the hook's JSON
#   protocol with Claude Code is preserved.
#   It MUST NEVER block the agent session: if no Python 3 can be found it
#   exits 0 (continue) after a single stderr note.
import os
import sys


def _target_path():
    here = os.path.dirname(os.path.abspath(__file__))
    name = sys.argv[1] if len(sys.argv) > 1 else ""
    if not name:
        return None
    # Guard against path traversal in the module name.
    name = os.path.basename(name)
    if not name.endswith(".py"):
        name = name + ".py"
    return os.path.join(here, name)


def main():
    target = _target_path()
    if not target or not os.path.isfile(target):
        sys.stderr.write("[FM] hook bootstrap: unknown target hook; skipping.\n")
        sys.exit(0)

    # Fast path: we are already on Python 3 -> run in-process, no extra spawn.
    if sys.version_info[0] >= 3:
        import runpy
        sys.argv = [target] + sys.argv[2:]
        try:
            runpy.run_path(target, run_name="__main__")
        except SystemExit:
            raise
        except Exception as exc:  # never crash the session
            sys.stderr.write("[FM] hook bootstrap: " + repr(exc) + "\n")
            sys.exit(0)
        return

    # Python 2: locate a Python 3 interpreter and delegate to it.
    import subprocess

    candidates = []
    override = os.environ.get("FM_HOOK_PYTHON")
    if override:
        candidates.append([override])
    candidates += [
        ["python3"],
        ["py", "-3"],
        ["python3.13"], ["python3.12"], ["python3.11"], ["python3.10"],
        ["/usr/bin/python3"],
        ["/usr/local/bin/python3"],
        ["/opt/homebrew/bin/python3"],
    ]
    extra = sys.argv[2:]
    for cand in candidates:
        try:
            # Default stdin/stdout/stderr inherit the parent's, so the
            # hook's stdin JSON and stdout response reach Claude Code.
            rc = subprocess.call(cand + [target] + extra)
        except OSError:
            continue
        sys.exit(rc)

    sys.stderr.write(
        "[FM] Python 3 not found (set FM_HOOK_PYTHON to your python3 path); "
        "skipping Feature Memory hook.\n"
    )
    sys.exit(0)


if __name__ == "__main__":
    main()
