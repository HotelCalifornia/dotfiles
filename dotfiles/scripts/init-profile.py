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
and AI agent integrations via a streamlined TUI (powered by questionary & uv),
and updates config.yaml so that subsequent `dotdrop install` commands
automatically resolve to this device.
"""

import argparse
import os
import platform
import re
import shutil
import socket
import subprocess
import sys

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
]

AVAILABLE_AGENTS = [
    ("gemini", "Antigravity / Gemini CLI", "Symlinks ~/.gemini/config/{skills,rules}"),
    ("claude", "Claude Code", "Symlinks ~/.claude/{skills,rules}"),
]

PRESETS = {
    "1": {
        "name": "Workstation",
        "description": "wezterm, neovim, user (Full terminal, editor & modern CLI tools)",
        "include": ["wezterm", "neovim", "user"],
        "suggest_mac_rc": True,
    },
    "2": {
        "name": "WSL Workstation",
        "description": "wsl, neovim, user (Windows Subsystem for Linux, editor & CLI tools)",
        "include": ["wsl", "neovim", "user"],
        "suggest_mac_rc": False,
    },
    "3": {
        "name": "Headless / Server",
        "description": "neovim, user (Editor & modern CLI tools)",
        "include": ["neovim", "user"],
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
    "f_0-mac.sh",
    "f_1-pyenv.sh",
    "f_2-direnv.sh",
    "f_vcpkg.sh",
]


def find_config_yaml(custom_path=None):
    if custom_path and os.path.isfile(custom_path):
        return os.path.abspath(custom_path)

    script_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = [
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


# --- Interactive TUI Prompts (using questionary if available) ---

def ask_hostname(default_host):
    if questionary:
        ans = questionary.text(
            "Device hostname for Dotdrop profile:",
            default=default_host,
        ).ask()
        if ans is None:
            sys.exit(0)
        return ans.strip() or default_host
    else:
        resp = input(f"Detected hostname [\033[32m{default_host}\033[0m]. Use this name? [Y/n/custom]: ").strip()
        if resp.lower() in ("n", "no"):
            custom = input("Enter custom hostname: ").strip()
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

        default_preset = "2" if "microsoft" in platform.uname().release.lower() else "1"
        ans = questionary.select(
            "Select starting preset (populates capabilities checklist next):",
            choices=choices,
            default=default_preset,
        ).ask()
        if ans is None:
            sys.exit(0)
        return ans
    else:
        print("\nChoose starting preset:")
        for k, p in PRESETS.items():
            print(f"  [{k}] {p['name']:<20} - {p['description']}")
        print("  [5] Custom (Start with empty checklist)")
        return input("\nSelect preset [default: 1]: ").strip() or "1"


def ask_mixins(preselected=None):
    selected_set = set(preselected or [])

    if questionary:
        choices = [
            questionary.Choice(
                title=f"{name:<10} - {desc}",
                value=name,
                checked=(name in selected_set),
            )
            for name, desc in STANDARD_MIXINS
        ]
        ans = questionary.checkbox(
            "Review & toggle capabilities (Space to toggle, Enter to confirm):",
            choices=choices,
        ).ask()
        if ans is None:
            sys.exit(0)
        return ans
    else:
        print("\nReview capabilities (toggle numbers separated by spaces or commas):")
        selected = set(selected_set)
        keys = [item[0] for item in STANDARD_MIXINS]
        while True:
            print()
            for idx, (k, desc) in enumerate(STANDARD_MIXINS, 1):
                mark = "[x]" if k in selected else "[ ]"
                print(f"  {mark} {idx}. {k:<10} - {desc}")
            print("\nEnter numbers to toggle, 'a' for all, or press Enter to confirm:")
            choice = input("Toggle > ").strip()
            if not choice:
                break
            if choice.lower() == "a":
                selected = set(keys)
                continue
            for p in re.split(r"[\s,]+", choice):
                if p.isdigit():
                    val = int(p)
                    if 1 <= val <= len(keys):
                        target = keys[val - 1]
                        if target in selected:
                            selected.remove(target)
                        else:
                            selected.add(target)
        return [k for k in keys if k in selected]


def ask_ai_agents():
    if questionary:
        choices = [
            questionary.Choice(
                title=f"{label:<26} - {desc}",
                value=key,
                checked=False,  # Unchecked by default
            )
            for key, label, desc in AVAILABLE_AGENTS
        ]
        ans = questionary.checkbox(
            "Select AI agent integrations (Space to toggle, Enter to confirm/skip):",
            choices=choices,
        ).ask()
        if ans is None:
            sys.exit(0)
        return ans
    else:
        keys = [item[0] for item in AVAILABLE_AGENTS]
        print("\n\033[1;36mAI Tool Integrations\033[0m")
        print("Select AI agents to configure with canonical rules & skills:")
        for idx, (k, label, desc) in enumerate(AVAILABLE_AGENTS, 1):
            print(f"  [{idx}] {label:<26} - {desc}")
        print("  [a] All agents")
        print("  [n] None / Skip [Default]")

        choice = input("\nSelect agents to integrate (e.g. '1', '1, 2', 'a', or Enter to skip): ").strip()
        if not choice or choice.lower() in ("n", "none", "skip"):
            return []
        if choice.lower() == "a":
            return list(keys)

        chosen = set()
        for p in re.split(r"[\s,]+", choice):
            if p.isdigit():
                val = int(p)
                if 1 <= val <= len(keys):
                    chosen.add(keys[val - 1])
            elif p.lower() in keys:
                chosen.add(p.lower())
        return [k for k in keys if k in chosen]


def ask_mac_hooks():
    if questionary:
        ans = questionary.confirm(
            "Include macOS shell environment hooks (pyenv, direnv, vcpkg)?",
            default=False,
        ).ask()
        if ans is None:
            sys.exit(0)
        return ans
    else:
        resp = input("\nInclude macOS shell environment hooks (pyenv, direnv, vcpkg)? [y/N]: ").strip().lower()
        return resp in ("y", "yes")


def ask_write_confirm(hostname, config_path):
    if questionary:
        ans = questionary.confirm(
            f"Write profile '{hostname}' to {config_path}?",
            default=True,
        ).ask()
        if ans is None:
            sys.exit(0)
        return ans
    else:
        confirm = input(f"\nWrite this profile to \033[34m{config_path}\033[0m? [Y/n]: ").strip().lower()
        return confirm not in ("n", "no")


def ask_run_install():
    if questionary:
        ans = questionary.confirm(
            "Run 'dotdrop install -a -f' now to apply dotfiles?",
            default=True,
        ).ask()
        if ans is None:
            return False
        return ans
    else:
        run_now = input("\nRun 'dotdrop install -a -f' now to apply dotfiles? [Y/n]: ").strip().lower()
        return run_now not in ("n", "no")


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
    args = parser.parse_args()

    config_path = find_config_yaml(args.config)
    if not config_path:
        print("Error: Could not locate config.yaml. Please specify --config <path>.", file=sys.stderr)
        sys.exit(1)

    print(f"\033[1;36mDotdrop Host Profile Generator\033[0m")
    print(f"Configuration: \033[34m{config_path}\033[0m\n")

    default_host = get_default_hostname()
    hostname = args.hostname or (ask_hostname(default_host) if not args.non_interactive else default_host)

    profiles, _ = read_config_profiles(config_path)
    if hostname in profiles and not args.force:
        print(f"\n\033[33mNotice:\033[0m Profile '\033[1m{hostname}\033[0m' already exists in config.yaml.")
        if args.non_interactive:
            print("To overwrite, pass --force.", file=sys.stderr)
            sys.exit(1)
        if questionary:
            overwrite = questionary.confirm(f"Overwrite / reconfigure profile '{hostname}'?", default=False).ask()
            if not overwrite:
                print("Aborted.")
                sys.exit(0)
        else:
            resp = input("Overwrite / reconfigure this profile? [y/N]: ").strip().lower()
            if resp not in ("y", "yes"):
                print("Aborted.")
                sys.exit(0)

    # Base mixin selection
    include_list = []
    suggest_mac_rc = False

    if args.include:
        include_list = [x.strip() for x in args.include.split(",") if x.strip()]
    elif args.preset:
        preset = PRESETS[args.preset]
        include_list = list(preset["include"])
        suggest_mac_rc = preset.get("suggest_mac_rc", False)
    elif args.non_interactive:
        is_wsl = "microsoft" in platform.uname().release.lower()
        preset = PRESETS["2"] if is_wsl else PRESETS["1"]
        include_list = list(preset["include"])
        suggest_mac_rc = preset.get("suggest_mac_rc", False)
    else:
        choice = ask_preset()
        if choice in PRESETS:
            initial_mixins = list(PRESETS[choice]["include"])
            suggest_mac_rc = PRESETS[choice].get("suggest_mac_rc", False)
        else:
            initial_mixins = []
            suggest_mac_rc = True

        # Pre-populate capabilities checklist from the selected preset:
        include_list = ask_mixins(initial_mixins)

    # AI Agents selection step
    selected_agents = []
    if args.agents is not None:
        if args.agents.lower() not in ("none", "no", "false", ""):
            selected_agents = [x.strip() for x in args.agents.split(",") if x.strip()]
    elif not args.non_interactive:
        selected_agents = ask_ai_agents()

    for ag in selected_agents:
        if ag not in include_list:
            include_list.append(ag)

    # Extra dotfiles (e.g. macOS rc hooks)
    extra_dotfiles = []
    if args.mac_rc:
        extra_dotfiles = list(MAC_RC_DOTFILES)
    elif not args.non_interactive and platform.system() == "Darwin" and suggest_mac_rc:
        if ask_mac_hooks():
            extra_dotfiles = list(MAC_RC_DOTFILES)

    # Display preview
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

    if not args.non_interactive:
        if not ask_write_confirm(hostname, config_path):
            print("Aborted.")
            sys.exit(0)

    write_profile_to_config(config_path, hostname, include_list, extra_dotfiles)
    print(f"\n\033[32mSuccessfully updated profile '{hostname}' in config.yaml!\033[0m")

    # Ask to install
    do_install = args.install
    if not do_install and not args.non_interactive:
        do_install = ask_run_install()

    if do_install:
        print("\n\033[36mRunning dotdrop install -a -f...\033[0m\n")
        cmd = ["dotdrop", "install", "-a", "-f"]
        subprocess.run(cmd)


if __name__ == "__main__":
    main()
