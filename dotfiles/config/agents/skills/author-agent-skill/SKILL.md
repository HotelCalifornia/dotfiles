---
name: author-agent-skill
description: >-
  Create, edit, or wire up an agent skill or rule in this repository. Use when the user
  asks to add a skill, turn a workflow into a skill, write rules for AI harnesses, fix a
  skill that isn't discovered, or choose between a rule, a skill, and documentation.
---

# Authoring Agent Skills

Skills are **on-demand procedures**; rules are **always-on constraints**. Both live
under `dotfiles/config/agents/` and are symlinked into harnesses.

## Rule or skill?

- **Rule** (`agents/rules/*.md`): short, invariant, must apply to every task —
  commit trailers, preferred tools, security constraints.
- **Skill** (`agents/skills/<name>/SKILL.md`): a multi-step workflow with
  repo-specific knowledge, commands, and failure modes. Loaded only when the
  description matches.
- **README**: user-facing reference. Skills may point to it, but should not
  duplicate it.

If it can be stated in two sentences and applies universally, make it a rule.

## Layout

```text
dotfiles/config/agents/skills/<name>/
├── SKILL.md            # required; frontmatter + instructions
├── references/         # optional deep material loaded on demand
├── scripts/            # optional helpers, executable
└── assets/             # optional templates/images
```

Deployed to `~/.config/agents/skills/<name>/`; `link-agent-skills.sh` links the
whole parent directory into the harness, so individual skills are not relinked.

## Frontmatter

```markdown
---
name: wezterm-local-config
description: >-
  Change WezTerm settings on this machine without breaking the dotdrop split ...
  Use whenever the user asks to change their terminal theme, background, or config.
---
```

- `name`: lowercase, hyphenated; match the directory name.
- `description`: this is the entire routing signal. State **what** it does and
  **when to use it** ("Use when / whenever the user asks to …"). Include the
  words a user would actually say.
- Keep the description to a few lines; keep `SKILL.md` to roughly one screen of
  orientation, with details in sections or `references/`.

## Content that earns a skill

- Golden rules and invariants that are easy to violate.
- A minimal workflow with copy-pasteable commands.
- Repo-specific paths, ownership boundaries, and precedence rules.
- Failure modes and a symptom → cause → fix table.
- A "done means" / verification checklist.

Avoid: restating `--help`, generic advice, or duplicating the README.

## Wire it up

1. Create the directory and `SKILL.md` under
   `dotfiles/config/agents/skills/<name>/`.
2. Add a dotfile entry to `config.yaml`:

   ```yaml
     d_skill_<underscored_name>:
       src: config/agents/skills/<name>
       dst: ~/.config/agents/skills/<name>
   ```

3. Attach it to the right mixin:
   - **General** → `ai` (shared rules, shared skills, link script).
   - **Tool-specific** (needs WezTerm, rclone, etc.) → that tool's profile, so
     machines without the tool don't advertise the skill.
4. Deploy and link:

   ```bash
   dotdrop install -f d_skill_<underscored_name>
   ~/.local/bin/link-agent-skills.sh gemini    # or claude
   ```

5. Verify: `dotdrop compare`, then confirm the file appears through the harness
   symlink (e.g. `ls ~/.gemini/config/skills/<name>`).

New skills are picked up by harnesses that scan the skills directory at session
start; an already-running session may need a restart. Confirm how each harness
(Claude, Gemini, OpenCode) discovers skills before promising availability.

## Gotchas

- **dotdrop templates any file containing its action-template delimiters.**
  Literal examples of that syntax in a skill will be rendered on install. Refer
  to `_dotdrop_dotpath` / `_dotdrop_cfgpath` in prose instead.
- Directory dotfiles do not prune extra files in the destination; do not rely on
  that for canonical content.
- Scripts need to be executable in the repo (`chmod 755`) and, if deployed
  directly, a `chmod: '755'` entry.
- No machine-specific absolute paths, secrets, tokens, or personal data. Use
  `~`/`$HOME`; label OS-specific commands (macOS vs Linux).
- Do not make a skill depend on a tool that no profile installs; reference the
  `manage-tools` skill if the tool is missing.
- Rules are always loaded: keep them short or they cost every session.

## Review checklist

- [ ] Frontmatter is valid YAML; `name` matches the directory.
- [ ] Description contains realistic trigger phrases.
- [ ] Commands were actually run, or are clearly marked as examples.
- [ ] Guardrails cover the destructive paths.
- [ ] No dotdrop template delimiters, secrets, or machine-specific paths.
- [ ] Added to `config.yaml` and the correct mixin; `dotdrop compare` clean.
- [ ] Harness symlink shows the skill.
