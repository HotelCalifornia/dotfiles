---
name: jbcontext-search
description: >-
  Semantic code search using the jbcontext CLI (JetBrains Air Context) for discovering
  unfamiliar code by meaning rather than keywords. Use when exploring a large or
  unfamiliar codebase where exact filenames or symbols are unknown; skip for small
  repos, known files/symbols, or CUI/restricted repositories.
---

# Semantic Code Search (`jbcontext`)

`jbcontext` indexes a repository and searches code by natural-language intent,
returning ranked `file:line` matches and snippets so you don't spend turns running
broad `grep`/`glob` scans over unfamiliar codebases.

## When NOT to use it

1. **CUI, ITAR, or restricted/proprietary repositories:** Even in "local storage"
   mode, `jbcontext` sends code chunks and queries to `api.jetbrains.ai` unless
   on-device inference is explicitly configured and approved. Never run `jbcontext`
   in a restricted repo.
2. **Small repositories** (such as `dotfiles`): `glob`, `grep`, and `read` are
   faster, exact, and work on uncommitted edits.
3. **Known file, class, or symbol:** Open it or `grep` directly.
4. **Non-discovery tasks:** git operations, builds, tests, config edits, or
   reviewing a diff already in hand.

## Workflow

1. **Check index status first** (do not assume a repo is indexed):

   ```bash
   jbcontext status
   ```

   If the repo is not indexed and the user wants semantic search on it (and it is
   not restricted), index it explicitly:

   ```bash
   jbcontext index
   ```

2. **Run one focused natural-language search:**

   ```bash
   jbcontext search "<clear description of behavior or concept>"
   jbcontext search -p <subpath> --limit 10 "<focused query>"
   jbcontext search --json-output "<query>"
   ```

   Write intent-based phrases (e.g. `"function that validates user email addresses"`),
   not concatenated keywords. Use `-p <subpath>` when large docs or unrelated
   directories crowd out source files.

3. **Inspect locally before searching again:** Read at least one returned file
   and check neighboring files in that directory/subsystem. Only issue a second
   search if needed, narrowed with `-p <subpath>`.

## Caveats & troubleshooting

- **Uncommitted edits:** `jbcontext` searches the indexed git revision; brand-new
  uncommitted changes won't appear until committed and re-indexed.
- **`401` / not authenticated:** Hand off to the user to run `jbcontext login`
  (requires an interactive browser/JetBrains AI login, including AI Free).
- **`404` / no index:** Run `jbcontext index` in the repo root if approved.
- **Keep CLI current:** `jbcontext upgrade` updates in place.
