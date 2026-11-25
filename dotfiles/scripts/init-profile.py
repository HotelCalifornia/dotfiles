#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "questionary>=2.0.0",
# ]
# ///
"""
Interactive host profile generator for Dotdrop.

Detects the current device hostname, prompts for desired profile mixins
and AI agent integrations via a streamlined TUI (powered by questionary & uv)
with full navigation, review, and back-step support, then updates config.yaml.

When the `git` capability is selected (or with --identities), it also manages
machine-local git identities: a default identity plus any number of extra
identities applied by remote URL, each with an optional GPG signing key and
SSH key (picked from existing keys or generated on the fly). These are written
to ~/.config/git/ and never to the shared config.yaml.
"""

import argparse
import glob
import os
import platform
import re
import shlex
import shutil
import socket
import subprocess
import sys
from dataclasses import dataclass, field, replace

# Try importing questionary, or re-exec with uv if run under raw python3
try:
    import questionary
except ImportError:
    if shutil.which("uv"):
        os.execvp("uv", ["uv", "run", "--script", sys.argv[0]] + sys.argv[1:])
    questionary = None

STANDARD_MIXINS = [
    ("wezterm", "WezTerm GUI, completions, Pokemon-terminal, terminal-pane-display (includes bash)"),
    ("neovim", "Neovim editor environment, init.lua, plugins (nvim release)"),
    ("user", "Modern CLI tools (rg, bat, eza, dust, glow, termaid), rules & tools.toml"),
    ("bash", "Core shell & Powerline prompt (standalone; automatically included by wezterm)"),
    ("wsl", "WSL environment (includes bash, neovim, user; configures Windows Terminal)"),
    ("wayland", "Wayland display server mixin (wayland.lua)"),
    ("git", "Git config + machine-local identities (set up interactively next)"),
    ("rclone", "rclone + systemd user unit mounting Google Drive at ~/GoogleDrive (Linux)"),
]

AVAILABLE_AGENTS = [
    ("gemini", "Antigravity / Gemini CLI", "Symlinks ~/.gemini/config/{skills,rules}"),
    ("claude", "Claude Code", "Symlinks ~/.claude/{skills,rules}"),
]

PRESETS = {
    "1": {
        "name": "Workstation",
        "description": "wezterm, neovim, user, git (Full terminal, editor, CLI tools & git identities)",
        "include": ["wezterm", "neovim", "user", "git"],
        "suggest_mac_rc": True,
    },
    "2": {
        "name": "WSL Workstation",
        "description": "wsl, neovim, user, git (Windows Subsystem for Linux, editor, CLI tools & git identities)",
        "include": ["wsl", "neovim", "user", "git"],
        "suggest_mac_rc": False,
    },
    "3": {
        "name": "Headless / Server",
        "description": "neovim, user, git (Editor, modern CLI tools & git identities)",
        "include": ["neovim", "user", "git"],
        "suggest_mac_rc": False,
    },
    "4": {
        "name": "Minimal Shell",
        "description": "bash, user (Core shell prompt & CLI tools)",
        "include": ["bash", "user"],
        "suggest_mac_rc": False,
    },
}

MAC_RC_DOTFILES = [
    "f_most.sh",
    "f_1-mac.sh",
    "f_1-pyenv.sh",
    "f_2-direnv.sh",
    "f_vcpkg.sh",
]


def find_config_yaml(custom_path=None):
    if custom_path and os.path.isfile(custom_path):
        return os.path.abspath(custom_path)

    script_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(os.environ["DOTFILES_DIR"], "config.yaml") if os.environ.get("DOTFILES_DIR") else "",
        os.path.join(os.getcwd(), "config.yaml"),
        os.path.join(script_dir, "..", "..", "config.yaml"),
        os.path.join(script_dir, "..", "config.yaml"),
        os.path.expanduser("~/dotfiles/config.yaml"),
    ]
    for c in candidates:
        norm = os.path.abspath(c)
        if os.path.isfile(norm):
            return norm
    return None


def get_default_hostname():
    try:
        out = subprocess.check_output(["hostname"], text=True).strip()
        if out:
            return out
    except Exception:
        pass
    return socket.gethostname() or "unknown-host.local"


def read_config_profiles(config_path):
    with open(config_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    profiles = {}
    in_profiles = False
    current_profile = None
    start_line = 0

    for i, line in enumerate(lines):
        if re.match(r"^profiles:\s*$", line):
            in_profiles = True
            continue

        if in_profiles:
            if line and not line.startswith(" ") and not line.startswith("\t") and not line.startswith("#") and ":" in line:
                if current_profile is not None:
                    profiles[current_profile] = (start_line, i)
                in_profiles = False
                break

            m = re.match(r"^  ([a-zA-Z0-9_.-]+):\s*$", line)
            if m:
                if current_profile is not None:
                    profiles[current_profile] = (start_line, i)
                current_profile = m.group(1)
                start_line = i

    if in_profiles and current_profile is not None:
        profiles[current_profile] = (start_line, len(lines))

    return profiles, lines


def write_profile_to_config(config_path, hostname, include_list, extra_dotfiles=None):
    profiles, lines = read_config_profiles(config_path)

    block_lines = [f"  {hostname}:\n"]
    if include_list:
        inc_str = ", ".join(include_list)
        block_lines.append(f"    include: [{inc_str}]\n")
    if extra_dotfiles:
        block_lines.append("    dotfiles:\n")
        for df in extra_dotfiles:
            block_lines.append(f"      - {df}\n")

    if hostname in profiles:
        start_idx, end_idx = profiles[hostname]
        new_lines = lines[:start_idx] + block_lines + lines[end_idx:]
    else:
        in_profiles = False
        insert_idx = len(lines)
        for i, line in enumerate(lines):
            if re.match(r"^profiles:\s*$", line):
                in_profiles = True
                continue
            if in_profiles and line and not line.startswith(" ") and not line.startswith("\t") and not line.startswith("#") and ":" in line:
                insert_idx = i
                break
        new_lines = lines[:insert_idx] + block_lines + lines[insert_idx:]

    with open(config_path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)


# --- Interactive TUI Prompts with Navigation & Back Support ---

def safe_ask(prompt_obj):
    if not prompt_obj:
        return None
    try:
        return prompt_obj.ask()
    except (EOFError, KeyboardInterrupt):
        return None


def ask_hostname(default_host):
    if questionary:
        ans = safe_ask(questionary.text(
            "Device hostname for Dotdrop profile:",
            default=default_host,
        ))
        if ans is None:
            print("\nOperation cancelled.")
            sys.exit(0)
        return ans.strip() or default_host
    else:
        try:
            resp = input(f"Detected hostname [\033[32m{default_host}\033[0m]. Use this name? [Y/n/custom]: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nOperation cancelled.")
            sys.exit(0)
        if resp.lower() in ("n", "no"):
            try:
                custom = input("Enter custom hostname: ").strip()
            except (EOFError, KeyboardInterrupt):
                sys.exit(0)
            return custom or default_host
        elif resp and resp.lower() not in ("y", "yes"):
            return resp
        return default_host


def ask_preset():
    if questionary:
        choices = [
            questionary.Choice(f"{p['name']:<18} ({p['description']})", value=k)
            for k, p in PRESETS.items()
        ]
        choices.append(questionary.Choice("Custom (Start with empty checklist)", value="custom"))
        choices.append(questionary.Choice("« Back (Change device hostname)", value="__back__"))

        default_preset = "2" if "microsoft" in platform.uname().release.lower() else "1"
        ans = safe_ask(questionary.select(
            "Select starting preset (populates capabilities checklist next):",
            choices=choices,
            default=default_preset,
        ))
        if ans is None:
            print("\nOperation cancelled.")
            sys.exit(0)
        return ans
    else:
        print("\nChoose starting preset:")
        for k, p in PRESETS.items():
            print(f"  [{k}] {p['name']:<20} - {p['description']}")
        print("  [5] Custom (Start with empty checklist)")
        print("  [b] Back (Change device hostname)")
        try:
            choice = input("\nSelect preset [default: 1]: ").strip() or "1"
        except (EOFError, KeyboardInterrupt):
            print("\nOperation cancelled.")
            sys.exit(0)
        if choice.lower() in ("b", "back"):
            return "__back__"
        return choice


def ask_mixins(preselected=None):
    selected_set = set(preselected or [])

    while True:
        if questionary:
            choices = [
                questionary.Choice(
                    title=f"{name:<10} - {desc}",
                    value=name,
                    checked=(name in selected_set),
                )
                for name, desc in STANDARD_MIXINS
            ]
            ans = safe_ask(questionary.checkbox(
                "Review & toggle capabilities (Space to toggle, Enter to proceed):",
                choices=choices,
            ))
            if ans is None:
                print("\nOperation cancelled.")
                sys.exit(0)
            selected_set = set(ans)

            # Navigation confirmation step
            nav = safe_ask(questionary.select(
                f"Capabilities selected: [{', '.join(ans) or 'None'}]",
                choices=[
                    questionary.Choice("Proceed to AI agents →", value="next"),
                    questionary.Choice("Re-open capabilities checklist ⟲", value="retry"),
                    questionary.Choice("« Back to starting presets", value="back"),
                ],
                default="next",
            ))
            if nav is None or nav == "next":
                return list(ans), "next"
            elif nav == "retry":
                continue
            elif nav == "back":
                return list(ans), "back"
        else:
            print("\nReview capabilities (toggle numbers separated by spaces or commas):")
            selected = set(selected_set)
            keys = [item[0] for item in STANDARD_MIXINS]
            while True:
                print()
                for idx, (k, desc) in enumerate(STANDARD_MIXINS, 1):
                    mark = "[x]" if k in selected else "[ ]"
                    print(f"  {mark} {idx}. {k:<10} - {desc}")
                print("\nEnter numbers to toggle, 'a' for all, 'b' for back, or Enter to proceed:")
                try:
                    choice = input("Toggle > ").strip()
                except (EOFError, KeyboardInterrupt):
                    print("\nOperation cancelled.")
                    sys.exit(0)
                if not choice:
                    break
                if choice.lower() == "a":
                    selected = set(keys)
                    continue
                if choice.lower() in ("b", "back"):
                    return list(selected), "back"
                for p in re.split(r"[\s,]+", choice):
                    if p.isdigit():
                        val = int(p)
                        if 1 <= val <= len(keys):
                            target = keys[val - 1]
                            if target in selected:
                                selected.remove(target)
                            else:
                                selected.add(target)
            return [k for k in keys if k in selected], "next"


def ask_ai_agents(preselected=None):
    selected_set = set(preselected or [])

    while True:
        if questionary:
            choices = [
                questionary.Choice(
                    title=f"{label:<26} - {desc}",
                    value=key,
                    checked=(key in selected_set),
                )
                for key, label, desc in AVAILABLE_AGENTS
            ]
            ans = safe_ask(questionary.checkbox(
                "Select AI agent integrations (Space to toggle, Enter to proceed):",
                choices=choices,
            ))
            if ans is None:
                print("\nOperation cancelled.")
                sys.exit(0)
            selected_set = set(ans)

            # Navigation confirmation step
            nav = safe_ask(questionary.select(
                f"AI agents selected: [{', '.join(ans) or 'None'}]",
                choices=[
                    questionary.Choice("Proceed to review →", value="next"),
                    questionary.Choice("Re-open AI agents checklist ⟲", value="retry"),
                    questionary.Choice("« Back to capabilities", value="back"),
                ],
                default="next",
            ))
            if nav is None or nav == "next":
                return list(ans), "next"
            elif nav == "retry":
                continue
            elif nav == "back":
                return list(ans), "back"
        else:
            keys = [item[0] for item in AVAILABLE_AGENTS]
            print("\n\033[1;36mAI Tool Integrations\033[0m")
            print("Select AI agents to configure with canonical rules & skills:")
            for idx, (k, label, desc) in enumerate(AVAILABLE_AGENTS, 1):
                mark = "[x]" if k in selected_set else "[ ]"
                print(f"  {mark} [{idx}] {label:<26} - {desc}")
            print("  [a] All agents")
            print("  [b] Back to capabilities")
            print("  [n] None / Skip [Default]")

            try:
                choice = input("\nSelect agents (e.g. '1', '1, 2', 'a', 'b', or Enter to skip): ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nOperation cancelled.")
                sys.exit(0)
            if not choice or choice.lower() in ("n", "none", "skip"):
                return [], "next"
            if choice.lower() in ("b", "back"):
                return list(selected_set), "back"
            if choice.lower() == "a":
                return list(keys), "next"

            chosen = set()
            for p in re.split(r"[\s,]+", choice):
                if p.isdigit():
                    val = int(p)
                    if 1 <= val <= len(keys):
                        chosen.add(keys[val - 1])
                elif p.lower() in keys:
                    chosen.add(p.lower())
            return [k for k in keys if k in chosen], "next"


def ask_mac_hooks():
    if questionary:
        choices = [
            questionary.Choice("Skip macOS shell environment hooks [Default]", value=False),
            questionary.Choice("Include pyenv, direnv, vcpkg hooks", value=True),
            questionary.Choice("« Back to AI agent integrations", value="__back__"),
        ]
        ans = safe_ask(questionary.select(
            "macOS Environment Hooks:",
            choices=choices,
            default=False,
        ))
        if ans == "__back__":
            return False, "back"
        return bool(ans), "next"
    else:
        try:
            resp = input("\nInclude macOS shell environment hooks (pyenv, direnv, vcpkg)? [y/N/back]: ").strip().lower()
            if resp in ("b", "back"):
                return False, "back"
            return resp in ("y", "yes"), "next"
        except (EOFError, KeyboardInterrupt):
            return False, "next"


def ask_review_action(hostname, config_path, git_enabled=False):
    choices = [
        ("✔ Save profile to config.yaml and continue", "save"),
        ("✎ Edit capabilities checklist", "edit_mixins"),
        ("✎ Edit AI agent integrations", "edit_agents"),
    ]
    if git_enabled:
        choices.append(("✎ Edit git identities", "edit_identities"))
    choices += [
        ("✎ Change starting preset", "edit_preset"),
        ("✎ Change device hostname", "edit_hostname"),
        ("✖ Cancel and abort", "abort"),
    ]
    ans = ask_select("Review profile definition:", choices, default="save")
    return ans or "abort"


def ask_run_install():
    if questionary:
        ans = safe_ask(questionary.confirm(
            "Run 'dotdrop install -a -f' now to apply dotfiles?",
            default=True,
        ))
        return bool(ans)
    else:
        try:
            run_now = input("\nRun 'dotdrop install -a -f' now to apply dotfiles? [Y/n]: ").strip().lower()
            return run_now not in ("n", "no")
        except (EOFError, KeyboardInterrupt):
            return False


# --- Git Identities -----------------------------------------------------------
#
# ~/.gitconfig (dotdrop-managed, shared) includes ~/.config/git/identities.gitconfig.
# That file, written here, holds the machine's default identity plus one
# includeIf per extra identity, pointing at ~/.config/git/identities/<id>.gitconfig.
# These files are also the source of truth: load_identities() reads them back.

GIT_CONFIG_DIR = os.path.expanduser("~/.config/git")
IDENTITIES_FILE = os.path.join(GIT_CONFIG_DIR, "identities.gitconfig")
IDENTITIES_DIR = os.path.join(GIT_CONFIG_DIR, "identities")
IDENTITIES_DIR_DISPLAY = "~/.config/git/identities"
GENERATED_MARKER = "# Generated by init-profile.py --identities"
REMOTE_COND_PREFIX = "hasconfig:remote.*.url:"
IDENTITY_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
GITHUB_OWNER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]*$")


@dataclass
class Identity:
    id: str                      # "default" for the machine's main identity
    name: str = ""               # user.name ("" on extras = inherit the default's)
    email: str = ""
    signingkey: str = ""         # GPG fingerprint/key ID; "" = don't sign
    sshkey: str = ""             # private key path; "" = ssh defaults
    match: list = field(default_factory=list)  # remote URL globs (extras only)


def _contract_home(path):
    home = os.path.expanduser("~")
    return "~" + path[len(home):] if path == home or path.startswith(home + os.sep) else path


def _gitcfg_quote(value):
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _git_get(path, key):
    r = subprocess.run(["git", "config", "--file", path, "--get", key], capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ""


def _sshkey_from_command(cmd):
    try:
        parts = shlex.split(cmd)
    except ValueError:
        return ""
    for i, part in enumerate(parts[:-1]):
        if part == "-i":
            return parts[i + 1]
    return ""


def _read_identity_fields(ident, path):
    ident.name = _git_get(path, "user.name")
    ident.email = _git_get(path, "user.email")
    ident.signingkey = _git_get(path, "user.signingkey")
    ident.sshkey = _sshkey_from_command(_git_get(path, "core.sshCommand"))


def load_identities():
    default = Identity("default")
    extras = []
    if not os.path.isfile(IDENTITIES_FILE) or not shutil.which("git"):
        return default, extras

    _read_identity_fields(default, IDENTITIES_FILE)

    r = subprocess.run(
        ["git", "config", "--file", IDENTITIES_FILE, "--get-regexp", r"^includeif\."],
        capture_output=True, text=True,
    )
    patterns_by_path = {}
    for line in r.stdout.splitlines():
        key, _, value = line.partition(" ")
        if not key.endswith(".path"):
            continue
        cond = key[len("includeif."):-len(".path")]
        if cond.startswith(REMOTE_COND_PREFIX):
            patterns_by_path.setdefault(value, []).append(cond[len(REMOTE_COND_PREFIX):])

    for path, patterns in patterns_by_path.items():
        full = os.path.expanduser(path)
        ident = Identity(os.path.splitext(os.path.basename(full))[0], match=patterns)
        if os.path.isfile(full):
            _read_identity_fields(ident, full)
            if ident.signingkey == ident.email:
                ident.signingkey = ""  # placeholder written by render_identities, not a real key
        extras.append(ident)
    return default, extras


def _ssh_command(keypath):
    return f"ssh -i {shlex.quote(keypath) if ' ' in keypath else keypath} -o IdentitiesOnly=yes"


def render_identities(default, extras):
    """Return {absolute path: file contents} for every identity file."""
    files = {}

    lines = [GENERATED_MARKER, "# Machine-local default identity; extra identities apply by remote URL.", "[user]"]
    if default.name:
        lines.append(f"    name = {_gitcfg_quote(default.name)}")
    if default.email:
        lines.append(f"    email = {_gitcfg_quote(default.email)}")
    if default.signingkey:
        lines.append(f"    signingkey = {default.signingkey}")
        lines += ["[commit]", "    gpgsign = true", "[tag]", "    gpgsign = true"]
    if default.sshkey:
        lines += ["[core]", f"    sshCommand = {_gitcfg_quote(_ssh_command(default.sshkey))}"]
    for ident in extras:
        for pattern in ident.match:
            cond = _gitcfg_quote(REMOTE_COND_PREFIX + pattern)
            lines += ["", f"[includeIf {cond}]", f"    path = {IDENTITIES_DIR_DISPLAY}/{ident.id}.gitconfig"]
    files[IDENTITIES_FILE] = "\n".join(lines) + "\n"

    for ident in extras:
        lines = [GENERATED_MARKER, f"# Identity '{ident.id}' for remotes: {', '.join(ident.match)}", "[user]"]
        if ident.name:
            lines.append(f"    name = {_gitcfg_quote(ident.name)}")
        if ident.email:
            lines.append(f"    email = {_gitcfg_quote(ident.email)}")
        if ident.signingkey:
            lines.append(f"    signingkey = {ident.signingkey}")
        elif default.signingkey and ident.email:
            # don't inherit the default's key: `git commit -S` would sign as the wrong person.
            # gpg looks this up by email and fails clearly if no such key exists.
            lines.append(f"    signingkey = {_gitcfg_quote(ident.email)}")
        # always explicit, so an unsigned identity never signs with the default's key
        sign = "true" if ident.signingkey else "false"
        lines += ["[commit]", f"    gpgsign = {sign}", "[tag]", f"    gpgsign = {sign}"]
        if ident.sshkey:
            lines += ["[core]", f"    sshCommand = {_gitcfg_quote(_ssh_command(ident.sshkey))}"]
        elif default.sshkey:
            # don't inherit the default identity's key
            lines += ["[core]", "    sshCommand = ssh"]
        files[os.path.join(IDENTITIES_DIR, f"{ident.id}.gitconfig")] = "\n".join(lines) + "\n"
    return files


def save_identities(default, extras):
    files = render_identities(default, extras)
    os.makedirs(IDENTITIES_DIR, exist_ok=True)
    for path, content in files.items():
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"  wrote {_contract_home(path)}")
    # remove identity files this script generated that no longer exist
    for path in glob.glob(os.path.join(IDENTITIES_DIR, "*.gitconfig")):
        if path in files:
            continue
        try:
            with open(path, encoding="utf-8") as f:
                generated = f.readline().strip() == GENERATED_MARKER
        except OSError:
            generated = False
        if generated:
            os.remove(path)
            print(f"  removed {_contract_home(path)}")


def patterns_to_text(patterns):
    """Collapse paired GitHub https/ssh patterns back to the owner name for display."""
    out, seen = [], set()
    for p in patterns:
        m = re.fullmatch(r"(?:https://github\.com/|git@github\.com:)([A-Za-z0-9-]+)/\*\*", p)
        if m:
            owner = m.group(1)
            pair = {f"https://github.com/{owner}/**", f"git@github.com:{owner}/**"}
            if pair <= set(patterns):
                if owner not in seen:
                    seen.add(owner)
                    out.append(owner)
                continue
        out.append(p)
    return ", ".join(out)


def text_to_patterns(text):
    """'owner, git@host:org/**' -> remote URL globs; bare names mean GitHub users/orgs."""
    patterns = []
    for item in (x.strip() for x in text.split(",")):
        if not item:
            continue
        if GITHUB_OWNER_RE.fullmatch(item):
            patterns += [f"https://github.com/{item}/**", f"git@github.com:{item}/**"]
        else:
            patterns.append(item)
    return patterns


def identity_summary(ident, default=None):
    who = ident.name or (f"({default.name})" if default and default.name else "")
    email = f"<{ident.email}>" if ident.email else "<no email>"
    parts = [f"{ident.id:<12} {who} {email}".replace("  ", " ")]
    if ident.match:
        parts.append(f"for {patterns_to_text(ident.match)}")
    parts.append(f"gpg {ident.signingkey[-16:]}" if ident.signingkey else "unsigned")
    parts.append(f"ssh {_contract_home(os.path.expanduser(ident.sshkey))}" if ident.sshkey else "ssh default")
    return " · ".join(parts)


def print_identities(default, extras):
    print("\n\033[1;36mGit identities\033[0m")
    print(f"  {identity_summary(default)}")
    for ident in extras:
        print(f"  {identity_summary(ident, default)}")
    if not extras:
        print("  (no extra identities)")


# Generic prompts that fall back to input() when questionary is unavailable.
# They return None when cancelled (Ctrl+C / EOF).

def ask_text(message, default="", validate=None):
    if questionary:
        return safe_ask(questionary.text(message, default=default, validate=validate or (lambda _: True)))
    while True:
        try:
            resp = input(f"{message} [{default}]: ").strip() if default else input(f"{message}: ").strip()
        except (EOFError, KeyboardInterrupt):
            return None
        resp = resp or default
        check = validate(resp) if validate else True
        if check is True:
            return resp
        print(f"  {check}")


def ask_select(message, choices, default=None):
    """choices: list of (label, value)."""
    if questionary:
        q_choices = [questionary.Choice(label, value=value) for label, value in choices]
        default_choice = next((c for c in q_choices if c.value == default), None)
        return safe_ask(questionary.select(message, choices=q_choices, default=default_choice))
    print(f"\n{message}")
    default_idx = 1
    for idx, (label, value) in enumerate(choices, 1):
        if value == default:
            default_idx = idx
        print(f"  [{idx}] {label}")
    while True:
        try:
            resp = input(f"Select [default: {default_idx}]: ").strip()
        except (EOFError, KeyboardInterrupt):
            return None
        if not resp:
            return choices[default_idx - 1][1]
        if resp.isdigit() and 1 <= int(resp) <= len(choices):
            return choices[int(resp) - 1][1]


def ask_confirm(message, default=True):
    if questionary:
        return safe_ask(questionary.confirm(message, default=default))
    try:
        resp = input(f"{message} [{'Y/n' if default else 'y/N'}]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return None
    return default if not resp else resp in ("y", "yes")


def _ensure_gpg_tty():
    if "GPG_TTY" not in os.environ:
        try:
            os.environ["GPG_TTY"] = os.ttyname(sys.stdin.fileno())
        except OSError:
            pass


def list_gpg_signing_keys():
    """Usable secret keys with signing capability, newest first."""
    if not shutil.which("gpg"):
        return []
    r = subprocess.run(["gpg", "--list-secret-keys", "--with-colons"], capture_output=True, text=True)
    keys, cur = [], None
    for line in r.stdout.splitlines():
        f = line.split(":")
        if f[0] == "sec":
            usable = f[1] not in ("r", "e", "d", "i") and "S" in (f[11] if len(f) > 11 else "")
            cur = {"keyid": f[4], "created": int(f[5] or 0), "fpr": "", "uids": []} if usable else None
            if cur:
                keys.append(cur)
        elif cur and f[0] == "fpr" and not cur["fpr"]:
            cur["fpr"] = f[9]  # first fpr after sec is the primary's; later ones are subkeys
        elif cur and f[0] == "uid":
            cur["uids"].append(f[9])
    return sorted(keys, key=lambda k: k["created"], reverse=True)


def generate_gpg_key(name, email):
    if not shutil.which("gpg"):
        print("  gpg is not installed; skipping key generation.")
        return ""
    expiry = ask_text("Signing key expiry (e.g. 1y, 2y, never):", default="2y")
    if expiry is None:
        return ""
    _ensure_gpg_tty()
    uid = f"{name} <{email}>" if name else f"<{email}>"
    print(f"\n\033[36mGenerating ed25519 signing key for {uid} (gpg will ask for a passphrase)...\033[0m")
    r = subprocess.run(["gpg", "--quick-generate-key", uid, "ed25519", "sign", "0" if expiry == "never" else expiry])
    if r.returncode != 0:
        print("  gpg key generation failed.")
        return ""
    matches = [k for k in list_gpg_signing_keys() if any(f"<{email}>" in u for u in k["uids"])]
    if not matches:
        print("  Could not find the generated key.")
        return ""
    fpr = matches[0]["fpr"]
    print(f"  Created {fpr}. Add it to your Git host's GPG keys (export with: gpg --armor --export {fpr})")
    return fpr


def choose_gpg_key(current, name, email):
    keys = list_gpg_signing_keys()
    if email:
        keys.sort(key=lambda k: not any(f"<{email}>" in u for u in k["uids"]))
    choices = [("None (don't sign commits)", "")]
    known = set()
    for k in keys:
        known.update({k["fpr"], k["keyid"]})
        choices.append((f"{k['keyid']}  {', '.join(k['uids'])}", k["fpr"]))
    if current and current not in known and not any(c.endswith(current) or current.endswith(c) for c in known if c):
        choices.insert(1, (f"Keep {current} (not found in local keyring)", current))
    if shutil.which("gpg") and email:
        choices.append((f"Generate a new signing key for <{email}>", "__generate__"))
    default = next((v for _, v in choices if current and v and (v == current or v.endswith(current) or current.endswith(v))), "")
    ans = ask_select("GPG signing key:", choices, default=default)
    if ans is None:
        return current
    if ans == "__generate__":
        return generate_gpg_key(name, email) or current
    return ans


def list_ssh_keys():
    keys = []
    for pub in sorted(glob.glob(os.path.expanduser("~/.ssh/*.pub"))):
        priv = pub[:-4]
        if os.path.isfile(priv):
            try:
                with open(pub, encoding="utf-8") as f:
                    comment = " ".join(f.read().split()[2:])
            except OSError:
                comment = ""
            keys.append((_contract_home(priv), comment))
    return keys


def generate_ssh_key(email, ident_id):
    if not shutil.which("ssh-keygen"):
        print("  ssh-keygen is not installed; skipping key generation.")
        return ""
    suggested = f"~/.ssh/id_ed25519_{ident_id}" if ident_id != "default" else "~/.ssh/id_ed25519"
    path = ask_text(
        "Path for the new SSH key:",
        default=suggested,
        validate=lambda p: True if not os.path.exists(os.path.expanduser(p.strip())) else "That file already exists",
    )
    if not path:
        return ""
    full = os.path.expanduser(path.strip())
    os.makedirs(os.path.dirname(full), mode=0o700, exist_ok=True)
    print("\n\033[36mGenerating ed25519 SSH key (ssh-keygen will ask for a passphrase)...\033[0m")
    r = subprocess.run(["ssh-keygen", "-t", "ed25519", "-C", email or ident_id, "-f", full])
    if r.returncode != 0:
        print("  ssh-keygen failed.")
        return ""
    with open(full + ".pub", encoding="utf-8") as f:
        print(f"  Add this public key to your Git host account:\n    {f.read().strip()}")
    return _contract_home(full)


def choose_ssh_key(current, email, ident_id, is_default):
    none_label = "None (use ssh defaults)" if is_default else "None (use the default identity's SSH setup)"
    choices = [(none_label, "")]
    paths = []
    for path, comment in list_ssh_keys():
        paths.append(path)
        choices.append((f"{path}  {comment}".rstrip(), path))
    if current and _contract_home(os.path.expanduser(current)) not in paths:
        choices.insert(1, (f"Keep {current} (file not found)", current))
    choices.append(("Generate a new ed25519 key", "__generate__"))
    default = _contract_home(os.path.expanduser(current)) if current else ""
    ans = ask_select("SSH key for this identity's remotes:", choices, default=default)
    if ans is None:
        return current
    if ans == "__generate__":
        return generate_ssh_key(email, ident_id) or current
    return ans


def edit_identity(ident, default, taken_ids):
    """Prompt for an identity's fields. Returns an updated copy, or None if cancelled."""
    ident = replace(ident, match=list(ident.match))
    is_default = ident.id == "default"

    if not is_default:
        def valid_id(v):
            v = v.strip()
            if not IDENTITY_ID_RE.fullmatch(v):
                return "Use lowercase letters, digits, '-' or '_'"
            if v == "default" or v in taken_ids:
                return f"'{v}' is already used"
            return True
        new_id = ask_text("Identity name (used for its file name):", default=ident.id, validate=valid_id)
        if new_id is None:
            return None
        ident.id = new_id.strip()

    name_prompt = "Full name (user.name):" if is_default else "Full name (leave blank to use the default identity's):"
    name = ask_text(name_prompt, default=ident.name)
    if name is None:
        return None
    ident.name = name.strip()

    email = ask_text(
        "Email (user.email):",
        default=ident.email,
        validate=lambda v: True if re.fullmatch(r"[^@\s]+@[^@\s]+", v.strip()) else "Enter an email address",
    )
    if email is None:
        return None
    ident.email = email.strip()

    if not is_default:
        match = ask_text(
            "Applies to remotes of (GitHub users/orgs, or URL globs like git@gitlab.com:group/**; comma-separated):",
            default=patterns_to_text(ident.match),
            validate=lambda v: True if text_to_patterns(v) else "Enter at least one user/org or pattern",
        )
        if match is None:
            return None
        ident.match = text_to_patterns(match)

    ident.signingkey = choose_gpg_key(ident.signingkey, ident.name or default.name, ident.email)
    ident.sshkey = choose_ssh_key(ident.sshkey, ident.email, ident.id, is_default)
    return ident


def _next_identity_id(extras):
    taken = {e.id for e in extras}
    if "additional" not in taken:
        return "additional"
    n = 2
    while f"additional-{n}" in taken:
        n += 1
    return f"additional-{n}"


def manage_identities(default, extras, back_label=None):
    """Interactive identity editor. Returns (default, extras, nav) with nav 'next' or 'back'."""
    extras = list(extras)
    while True:
        print_identities(default, extras)
        choices = [("Continue →", "__next__"), ("✎ Edit default identity", "default")]
        choices += [(f"✎ Edit '{e.id}'", f"edit:{e.id}") for e in extras]
        choices.append(("＋ Add an identity", "__add__"))
        choices += [(f"✖ Remove '{e.id}'", f"remove:{e.id}") for e in extras]
        if back_label:
            choices.append((f"« {back_label}", "__back__"))
        ans = ask_select("Manage git identities:", choices, default="__next__" if default.email else "default")
        if ans is None or ans == "__next__":
            return default, extras, "next"
        if ans == "__back__":
            return default, extras, "back"
        if ans == "default":
            updated = edit_identity(default, default, set())
            if updated:
                default = updated
        elif ans == "__add__":
            new = edit_identity(Identity(_next_identity_id(extras)), default, {e.id for e in extras})
            if new:
                extras.append(new)
        elif ans.startswith("edit:"):
            idx = next(i for i, e in enumerate(extras) if e.id == ans[5:])
            updated = edit_identity(extras[idx], default, {e.id for e in extras} - {extras[idx].id})
            if updated:
                extras[idx] = updated
        elif ans.startswith("remove:"):
            if ask_confirm(f"Remove identity '{ans[7:]}'? (keys are kept)", default=False):
                extras = [e for e in extras if e.id != ans[7:]]


def identities_included():
    """True if the global git config (~/.gitconfig or ~/.config/git/config) includes IDENTITIES_FILE."""
    r = subprocess.run(["git", "config", "--global", "--get-all", "include.path"], capture_output=True, text=True)
    return any(os.path.expanduser(p.strip()) == IDENTITIES_FILE for p in r.stdout.splitlines())


def ensure_identities_included(config_path, offer_deploy=True):
    """Make sure git actually reads the identities file; offer to deploy ~/.gitconfig via dotdrop if not."""
    if not os.path.isfile(IDENTITIES_FILE) or identities_included():
        return
    print("\n\033[33m~/.gitconfig doesn't include the identities file yet, so git won't use these identities.\033[0m")
    hostname = get_default_hostname()
    deploy_cmd = ["dotdrop", "install", "-f", "-p", hostname, "f_gitconfig"]
    if config_path:
        deploy_cmd[3:3] = ["-c", config_path]
    manual = " ".join(shlex.quote(a) for a in deploy_cmd)
    if not offer_deploy or not shutil.which("dotdrop") or not config_path:
        print(f"Deploy it with: {manual}")
        return
    note = " (the existing file is backed up)" if os.path.exists(os.path.expanduser("~/.gitconfig")) else ""
    if not ask_confirm(f"Deploy ~/.gitconfig now with dotdrop{note}?", default=True):
        print(f"Skipped. Deploy it later with: {manual}")
        return
    subprocess.run(deploy_cmd)
    if not identities_included():
        print(f"\033[31m~/.gitconfig still doesn't include the identities file.\033[0m "
              f"Check that profile '{hostname}' includes the `git` profile in config.yaml.")


def show_current_identity():
    """If run inside a git repo, show which identity it resolves to."""
    inside = subprocess.run(["git", "rev-parse", "--is-inside-work-tree"], capture_output=True, text=True)
    if inside.stdout.strip() != "true":
        return
    r = subprocess.run(["git", "config", "--show-origin", "user.email"], capture_output=True, text=True)
    origin, _, email = r.stdout.strip().partition("\t")
    if email:
        print(f"\nThis repo commits as {email} (from {_contract_home(origin.removeprefix('file:'))})")
    else:
        print("\nThis repo has no identity yet (user.email is unset).")


def run_identities_only(config_path=None):
    if not shutil.which("git"):
        print("Error: git is not installed.", file=sys.stderr)
        sys.exit(1)
    default, extras = load_identities()
    default, extras, _ = manage_identities(default, extras)
    if render_identities(default, extras) == render_identities(*load_identities()) and os.path.isfile(IDENTITIES_FILE):
        print("\nNo changes.")
    elif ask_confirm(f"Write identities to {_contract_home(GIT_CONFIG_DIR)}?", default=True):
        save_identities(default, extras)
    # checked even without changes: the files may exist while ~/.gitconfig was never deployed
    ensure_identities_included(config_path)
    show_current_identity()


def run_interactive_wizard(config_path, default_host, args):
    hostname = args.hostname or default_host
    preset_choice = "1"
    include_list = list(PRESETS["1"]["include"])
    suggest_mac_rc = PRESETS["1"].get("suggest_mac_rc", False)
    selected_agents = []
    mac_rc_enabled = False
    id_default, id_extras = load_identities()
    identities_visited = False

    step = "hostname"
    if args.hostname:
        step = "preset"

    while True:
        if step == "hostname":
            hostname = ask_hostname(default_host)
            step = "preset"

        elif step == "preset":
            p_ans = ask_preset()
            if p_ans == "__back__":
                step = "hostname"
                continue
            preset_choice = p_ans
            if preset_choice in PRESETS:
                include_list = list(PRESETS[preset_choice]["include"])
                suggest_mac_rc = PRESETS[preset_choice].get("suggest_mac_rc", False)
            else:
                include_list = []
                suggest_mac_rc = True
            step = "mixins"

        elif step == "mixins":
            mixins_ans, nav = ask_mixins(include_list)
            if nav == "back":
                step = "preset"
                continue
            include_list = mixins_ans
            step = "agents"

        elif step == "agents":
            agents_ans, nav = ask_ai_agents(selected_agents)
            if nav == "back":
                step = "mixins"
                continue
            selected_agents = agents_ans
            step = "identities" if "git" in include_list else "after_identities"

        elif step == "identities":
            id_default, id_extras, nav = manage_identities(id_default, id_extras, back_label="Back to AI agent integrations")
            identities_visited = True
            step = "agents" if nav == "back" else "after_identities"

        elif step == "after_identities":
            step = "mac_hooks" if (platform.system() == "Darwin" and suggest_mac_rc) else "review"

        elif step == "mac_hooks":
            mac_rc_enabled, nav = ask_mac_hooks()
            if nav == "back":
                step = "identities" if "git" in include_list else "agents"
                continue
            step = "review"

        elif step == "review":
            full_includes = list(include_list)
            for ag in selected_agents:
                if ag not in full_includes:
                    full_includes.append(ag)
            extra_dfs = list(MAC_RC_DOTFILES) if mac_rc_enabled else []

            print("\n\033[1;32mGenerated Profile Definition:\033[0m")
            print(f"  \033[1m{hostname}\033[0m:")
            if full_includes:
                print(f"    include: [{', '.join(full_includes)}]")
            if extra_dfs:
                print("    dotfiles:")
                for df in extra_dfs:
                    print(f"      - {df}")
            git_enabled = "git" in full_includes
            if git_enabled:
                print_identities(id_default, id_extras)
                print(f"  (written to {_contract_home(GIT_CONFIG_DIR)}, not config.yaml)")

            action = ask_review_action(hostname, config_path, git_enabled)
            if action == "save":
                identities = (id_default, id_extras) if git_enabled and identities_visited else None
                return hostname, full_includes, extra_dfs, identities
            elif action == "edit_mixins":
                step = "mixins"
            elif action == "edit_agents":
                step = "agents"
            elif action == "edit_identities":
                step = "identities"
            elif action == "edit_preset":
                step = "preset"
            elif action == "edit_hostname":
                step = "hostname"
            elif action == "abort":
                print("Aborted.")
                sys.exit(0)


def main():
    parser = argparse.ArgumentParser(description="Interactively generate a host profile in config.yaml.")
    parser.add_argument("--hostname", help="Hostname for the profile (defaults to current system hostname).")
    parser.add_argument("--include", help="Comma-separated mixin list (e.g. wezterm,neovim,user).")
    parser.add_argument("--preset", choices=["1", "2", "3", "4"], help="Use a predefined preset (1-4).")
    parser.add_argument("--agents", help="Comma-separated AI agents to integrate (e.g. 'gemini,claude', 'gemini', or 'none').")
    parser.add_argument("--mac-rc", action="store_true", help="Include macOS environment hooks (pyenv, direnv, etc.).")
    parser.add_argument("--config", help="Path to config.yaml.")
    parser.add_argument("--dry-run", action="store_true", help="Print YAML snippet without modifying config.yaml.")
    parser.add_argument("--install", action="store_true", help="Automatically run 'dotdrop install -a -f' after writing.")
    parser.add_argument("-f", "--force", action="store_true", help="Overwrite existing profile without prompting.")
    parser.add_argument("--non-interactive", action="store_true", help="Run without interactive prompts.")
    parser.add_argument("--identities", action="store_true", help="Only manage this machine's git identities (~/.config/git), then exit.")
    args = parser.parse_args()

    if not sys.stdin.isatty():
        # Non-TTY environment (e.g. redirected stdin, pipes, background tools)
        args.non_interactive = True

    if args.identities:
        if args.non_interactive:
            print("Error: --identities needs an interactive terminal.", file=sys.stderr)
            sys.exit(1)
        print("\033[1;36mGit Identity Manager\033[0m")
        run_identities_only(find_config_yaml(args.config))
        return

    config_path = find_config_yaml(args.config)
    if not config_path:
        print("Error: Could not locate config.yaml. Please specify --config <path>.", file=sys.stderr)
        sys.exit(1)

    print(f"\033[1;36mDotdrop Host Profile Generator\033[0m")
    print(f"Configuration: \033[34m{config_path}\033[0m\n")

    default_host = get_default_hostname()

    # Non-interactive execution branch
    if args.non_interactive:
        hostname = args.hostname or default_host
        profiles, _ = read_config_profiles(config_path)
        if hostname in profiles and not args.force:
            print(f"Notice: Profile '{hostname}' already exists in config.yaml. Pass --force to overwrite.", file=sys.stderr)
            sys.exit(1)

        include_list = []
        if args.include:
            include_list = [x.strip() for x in args.include.split(",") if x.strip()]
        elif args.preset:
            include_list = list(PRESETS[args.preset]["include"])
        else:
            is_wsl = "microsoft" in platform.uname().release.lower()
            preset = PRESETS["2"] if is_wsl else PRESETS["1"]
            include_list = list(preset["include"])

        if args.agents and args.agents.lower() not in ("none", "no", "false", ""):
            for ag in [x.strip() for x in args.agents.split(",") if x.strip()]:
                if ag not in include_list:
                    include_list.append(ag)

        extra_dotfiles = list(MAC_RC_DOTFILES) if args.mac_rc else []

        print("\n\033[1;32mGenerated Profile Definition:\033[0m")
        print(f"  \033[1m{hostname}\033[0m:")
        if include_list:
            print(f"    include: [{', '.join(include_list)}]")
        if extra_dotfiles:
            print("    dotfiles:")
            for df in extra_dotfiles:
                print(f"      - {df}")

        if args.dry_run:
            print("\n[--dry-run specified; config.yaml not modified]")
            sys.exit(0)

        write_profile_to_config(config_path, hostname, include_list, extra_dotfiles)
        print(f"\n\033[32mSuccessfully updated profile '{hostname}' in config.yaml!\033[0m")
        if "git" in include_list and not os.path.isfile(IDENTITIES_FILE):
            print("Note: no git identities on this machine yet. Run init-profile.py --identities in a terminal.")
        if args.install:
            subprocess.run(["dotdrop", "install", "-a", "-f"])
        return

    # Interactive Wizard branch
    hostname, include_list, extra_dotfiles, identities = run_interactive_wizard(config_path, default_host, args)

    profiles, _ = read_config_profiles(config_path)
    if hostname in profiles and not args.force:
        if questionary:
            overwrite = safe_ask(questionary.confirm(f"Profile '{hostname}' already exists. Overwrite in config.yaml?", default=True))
            if not overwrite:
                print("Aborted.")
                sys.exit(0)
        else:
            try:
                resp = input(f"Profile '{hostname}' already exists. Overwrite? [Y/n]: ").strip().lower()
                if resp in ("n", "no"):
                    print("Aborted.")
                    sys.exit(0)
            except (EOFError, KeyboardInterrupt):
                sys.exit(0)

    if args.dry_run:
        print("\n[--dry-run specified; config.yaml not modified]")
        sys.exit(0)

    write_profile_to_config(config_path, hostname, include_list, extra_dotfiles)
    print(f"\n\033[32mSuccessfully updated profile '{hostname}' in config.yaml!\033[0m")

    if identities:
        print("\n\033[36mWriting git identities...\033[0m")
        save_identities(*identities)

    # Offer to install
    do_install = args.install
    if not do_install:
        do_install = ask_run_install()

    if do_install:
        print("\n\033[36mRunning dotdrop install -a -f...\033[0m\n")
        subprocess.run(["dotdrop", "install", "-a", "-f"])

    if "git" in include_list and shutil.which("git"):
        # the full install was already offered above, so only point out what's missing
        ensure_identities_included(config_path, offer_deploy=False)
        show_current_identity()


if __name__ == "__main__":
    main()
