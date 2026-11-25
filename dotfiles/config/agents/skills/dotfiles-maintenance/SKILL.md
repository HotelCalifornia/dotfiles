---
name: dotfiles-maintenance
description: >-
  Safely inspect, change, or apply the dotfiles repository managed by dotdrop. Use when
  the user asks to change a managed config, add or remove a dotfile, edit config.yaml
  profiles or actions, explain why a live file differs from the repo, or when an agent is
  about to edit anything under ~/.config that dotdrop deploys.
---

# Dotfiles Maintenance

This repository is the **source of truth**; the live files under `$HOME` are
copies deployed by [dotdrop](https://github.com/deadc0de6/dotdrop). Every change
follows the same shape: edit the source in the repo, make sure it belongs to the
active profile, install, then verify with `compare`.

## Golden rules

1. **Never edit a deployed file.** `config.yaml` sets `link_dotfile_default: nolink`,
   so `~/.bash_aliases`, `~/.config/wezterm/dotfiles.lua`, etc. are copies. Edit
   `dotfiles/...` in the repo and reinstall. Editing the destination creates drift
   that the next install overwrites.
2. **A profile is a set of mixins, not a machine manifest.** The default profile is
   the hostname (`hotel-laptop-2.local` here). `config.yaml` profiles live in git;
   adding a host profile is a repo change that should be committed.
3. **Machine-local state never goes in the repo.** Git identities, keys, tokens,
   and `~/.config/rc/pre/00-dotfiles.sh` are generated/recorded per machine.
4. **Preview before writing.** `dotdrop compare` is read-only; `dotdrop install -d`
   is a dry run; `-D` shows diffs before overwriting.
5. **Commits are signed and carry a trailer.** Use `git commit -S` and end the
   message with `Assisted-by: <Harness>/<Model>` per
   `~/.config/agents/rules/git-commit-trailers.md`.

## Orientation

```bash
# run from the repo root (or add -c <repo>/config.yaml after the subcommand)
dotdrop profiles                 # available mixins/profiles
dotdrop detail -p <profile>      # dotfiles + actions a profile resolves to
dotdrop files   -p <profile>     # destination paths it manages
dotdrop compare -L               # only list differing files (default profile)
dotdrop compare                  # full diff, read-only
```

Non-interactive shells (scripts, agents) do **not** get the `dotdrop` alias or
`$DOTFILES_DIR`; those come from `bash_aliases` + `00-dotfiles.sh` in interactive
bash. Run from the repo root, or pass `-c <repo>/config.yaml` after the subcommand.

## Change workflow

1. **Inspect** the current drift: `dotdrop compare` or `dotdrop compare -L`.
2. **Edit the source** under `dotfiles/` (never the destination).
3. **Check profile membership.** A dotfile that is not in the active profile is
   invisible to install/compare. Add it to the narrowest sensible mixin.
4. **Apply:**

   ```bash
   dotdrop install -f                 # all dotfiles in the default profile
   dotdrop install -f f_bash_aliases  # one dotfile by key
   dotdrop install -a -f              # also force profile actions to run
   ```

   Actions normally run when at least one dotfile is installed; `-a` forces them
   even when nothing changed. Actions may install software from the network, so
   avoid `-a` when you only need a file updated.
5. **Verify:** `dotdrop compare` must be clean. If a backup appeared as
   `<dst>.dotdropbak`, that's expected (`backup: true`) and worth mentioning.

## Adding or removing a dotfile

Add an entry under `dotfiles:` in `config.yaml`:

```yaml
  d_skill_git_signing:                 # d_ = directory, f_ = file
    src: config/agents/skills/git-signing   # relative to dotpath: dotfiles
    dst: ~/.config/agents/skills/git-signing
```

Then add the key to one or more profiles (or a mixin they include). Files that
must be executable take `chmod: '755'`. Directories can use
`ignore_missing_in_dotdrop: true` when local-only files are expected inside them.

**Removal is not symmetric.** If a dotfile is deleted or renamed in the repo,
dotdrop leaves the old destination behind. Delete the stale destination by hand
after confirming it is the same file. Example: `rc/pre/0-mac.sh` became
`0-bash.sh` + `1-mac.sh`, and the old `~/.config/rc/pre/0-mac.sh` kept being
sourced until it was removed.

Directory dotfiles deploy their files but do not prune extra files already in
the destination. This is deliberate: `d_wezterm` manages `dotfiles.lua` while
`~/.config/wezterm/wezterm.lua` stays machine-local and unmanaged.

## Actions

Actions are defined under `actions:` and referenced by profiles. They run after
dotfiles are installed.

- Templates receive `_dotdrop_dotpath` and `_dotdrop_cfgpath` as variables.
- They are not automatically idempotent: `persist-dotfiles-dir.sh` skips if its
  output exists, and `seed-wezterm-local.sh` exits if the file already requires
  the shared module. Preserve that style when adding one.
- Avoid destructive or broad actions; they execute on every install that changes
  a dotfile, and on every `-a` install.
- `install-tools.py`, `ensure-toolchains.sh`, and the WezTerm actions touch the
  network or install software. Know that `dotdrop install -a -f` can be slow and
  side-effecting.

## Dangerous commands

| Command | Effect | Use only when |
| --- | --- | --- |
| `dotdrop update` | Copies **destination → repo**, overwriting sources with live files | You intentionally want to adopt local edits |
| `dotdrop remove` | Removes deployed files from the system | The user asked to uninstall a profile |
| `dotdrop install -p <other>` | Installs another host's profile here | Explicitly requested; profiles are host-specific |

`dotdrop import` similarly pulls a live file into the repo; prefer hand-editing
and `compare` so changes stay reviewable.

## Verification checklist

- `dotdrop compare` clean for the active profile.
- `dotdrop detail -p <profile>` contains the expected keys.
- Newly added shell scripts are executable in the repo (`chmod 755`) and have a
  matching `chmod:` in `config.yaml`.
- `git status` shows only intended repo changes; no generated identities,
  backups, or `*.dotdropbak` files staged.
