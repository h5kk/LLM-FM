# Migration Notes

## v0.8.0 — Generated changelog artifacts become build outputs

**What changed.** Feature Memory used to commit two files that its hooks
*regenerate every session*:

- `docs/feature-memory/changelogs/changelog.json`
- `docs/feature-memory/changelog-viewer.html`

Because they were rewritten on every Stop (fresh `generated` timestamp + the full
data re-injected into the HTML), they constantly dirtied the working tree —
tripping clean-tree / pre-commit checks — and, when two branches both touched
them, produced recurring merge conflicts. The same problem applied to per-session
runtime state that was never ignored: `.feature-memory/events-*.jsonl` archives
and `.feature-memory/errors.log`.

Both changelog files are **fully derivable from git history** (`fm_backfill --all`
reconstructs `changelog.json`, and the viewer is rendered from it), so as of
v0.8.0 they are treated as **build outputs and are no longer tracked**.

**How it works now.** On every SessionStart the plugin writes two self-contained
`.gitignore` drop-ins (idempotent, never overwriting a customized one):

- `.feature-memory/.gitignore` — ignores `events.jsonl`, `events-*.jsonl`,
  `errors.log`, `state.sqlite*`, `reports/`
- `docs/feature-memory/.gitignore` — ignores `changelog-viewer.html` and
  `changelogs/changelog.json`

Patterns are explicit (never a blanket `*`) so hook scripts that some installs
copy into `.feature-memory/hooks/` are never accidentally ignored.

### Upgrading an existing repo

No data is lost — the changelog rebuilds from commits.

1. **Pull v0.8.0 and start one Claude Code session.** SessionStart creates the
   two `.gitignore` drop-ins automatically. (Or run them in by hand:
   `python plugin/hooks/fm_backfill.py --all` after the files exist.)
2. **Stop tracking the now-generated artifacts** (keeps your local copies):

   ```bash
   git rm --cached docs/feature-memory/changelogs/changelog.json \
                   docs/feature-memory/changelog-viewer.html
   ```

3. **Commit the drop-in `.gitignore` files** so the whole team is protected:

   ```bash
   git add .feature-memory/.gitignore docs/feature-memory/.gitignore
   git commit -m "chore: untrack generated Feature Memory artifacts"
   ```

4. **Rebuild any time** with `/feature-memory-changelog-refresh` or
   `python plugin/hooks/fm_backfill.py --all`.

> The committed, human-maintained `docs/feature-memory/changelog.md` and the
> feature `*.md` docs are unaffected — only the machine-generated viewer/JSON and
> the runtime event logs are now ignored.

No `changelog.json` `schema_version` change is required by this migration
(it remains `2`).
