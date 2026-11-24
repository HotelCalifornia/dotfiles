#!/usr/bin/env python3
"""
Interactive host profile generator for Dotdrop.

Detects the current device hostname, prompts for desired profile mixins
(or common presets), and writes the host profile into config.yaml so that
subsequent `dotdrop install` commands automatically resolve to this device.
"""

import argparse
import os
import platform
import re
import socket
import subprocess
import sys

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
    """
    Parses existing profile names and their lines from config.yaml.
    Returns (profiles_dict, full_lines)
    """
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
            # Check for another top-level key (0 indentation)
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

    # Format YAML block for the profile
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
        # Append before next section or at end of profiles
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


def prompt_custom_mixins():
    print("\nSelect mixins to include (toggle numbers separated by spaces or commas):")
    selected = set(["wezterm", "neovim", "user"])
    if "microsoft" in platform.uname().release.lower():
        selected.discard("wezterm")
        selected.add("wsl")

    keys = [item[0] for item in STANDARD_MIXINS]

    while True:
        print()
        for idx, (k, desc) in enumerate(STANDARD_MIXINS, 1):
            mark = "[x]" if k in selected else "[ ]"
            print(f"  {mark} {idx}. {k:<10} - {desc}")
        print("\nEnter numbers to toggle, 'a' for all, or press Enter when done:")
        choice = input("Toggle > ").strip()
        if not choice:
            break
        if choice.lower() == "a":
            selected = set(keys)
            continue
        parts = re.split(r"[\s,]+", choice)
        for p in parts:
            if p.isdigit():
                val = int(p)
                if 1 <= val <= len(keys):
                    target = keys[val - 1]
                    if target in selected:
                        selected.remove(target)
                    else:
                        selected.add(target)
    return [k for k in keys if k in selected]


def prompt_ai_agents(current_selected=None):
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
    parts = re.split(r"[\s,]+", choice)
    for p in parts:
        if p.isdigit():
            val = int(p)
            if 1 <= val <= len(keys):
                chosen.add(keys[val - 1])
        elif p.lower() in keys:
            chosen.add(p.lower())
    return [k for k in keys if k in chosen]


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
    hostname = args.hostname or default_host

    if not args.non_interactive and not args.hostname:
        resp = input(f"Detected hostname [\033[32m{default_host}\033[0m]. Use this name? [Y/n/custom]: ").strip()
        if resp.lower() in ("n", "no") or (resp and resp.lower() not in ("y", "yes")):
            if resp.lower() in ("n", "no"):
                custom = input("Enter custom hostname: ").strip()
                if custom:
                    hostname = custom
            else:
                hostname = resp

    profiles, _ = read_config_profiles(config_path)
    if hostname in profiles and not args.force:
        print(f"\n\033[33mNotice:\033[0m Profile '\033[1m{hostname}\033[0m' already exists in config.yaml.")
        if args.non_interactive:
            print("To overwrite, pass --force.", file=sys.stderr)
            sys.exit(1)
        resp = input("Overwrite / reconfigure this profile? [y/N]: ").strip().lower()
        if resp not in ("y", "yes"):
            print("Aborted.")
            sys.exit(0)

    # Determine mixins
    include_list = []
    suggest_mac_rc = False

    if args.include:
        include_list = [x.strip() for x in args.include.split(",") if x.strip()]
    elif args.preset:
        preset = PRESETS[args.preset]
        include_list = list(preset["include"])
        suggest_mac_rc = preset.get("suggest_mac_rc", False)
    elif args.non_interactive:
        # Default non-interactive preset: Workstation (or WSL Workstation on WSL)
        is_wsl = "microsoft" in platform.uname().release.lower()
        preset = PRESETS["2"] if is_wsl else PRESETS["1"]
        include_list = list(preset["include"])
        suggest_mac_rc = preset.get("suggest_mac_rc", False)
    else:
        print("\nChoose a profile preset:")
        for k, p in PRESETS.items():
            print(f"  [{k}] {p['name']:<25} - {p['description']}")
        print("  [5] Custom mixin selection...")

        choice = input("\nSelect preset [default: 1]: ").strip() or "1"
        if choice in PRESETS:
            include_list = list(PRESETS[choice]["include"])
            suggest_mac_rc = PRESETS[choice].get("suggest_mac_rc", False)
        elif choice == "5":
            include_list = prompt_custom_mixins()
        else:
            print("Invalid choice, defaulting to preset 1.")
            include_list = list(PRESETS["1"]["include"])
            suggest_mac_rc = True

    # AI Agents selection step
    selected_agents = []
    if args.agents is not None:
        if args.agents.lower() not in ("none", "no", "false", ""):
            selected_agents = [x.strip() for x in args.agents.split(",") if x.strip()]
    elif not args.non_interactive:
        selected_agents = prompt_ai_agents()

    for ag in selected_agents:
        if ag not in include_list:
            include_list.append(ag)

    # Extra dotfiles (e.g. macOS rc hooks)
    extra_dotfiles = []
    if args.mac_rc:
        extra_dotfiles = list(MAC_RC_DOTFILES)
    elif not args.non_interactive and platform.system() == "Darwin" and suggest_mac_rc:
        resp = input("\nInclude macOS shell environment hooks (pyenv, direnv, vcpkg)? [y/N]: ").strip().lower()
        if resp in ("y", "yes"):
            extra_dotfiles = list(MAC_RC_DOTFILES)

    # Display preview
    print("\n\033[1;32mGenerated Profile Definition:\033[0m")
    print(f"  \033[1m{hostname}\033[0m:")
    if include_list:
        print(f"    include: [{', '.join(include_list)}]")
    if extra_dotfiles:
        print("    dotfiles:")
        for df in extra_dotfiles:
            print(f"    - {df}")

    if args.dry_run:
        print("\n[--dry-run specified; config.yaml not modified]")
        sys.exit(0)

    if not args.non_interactive:
        confirm = input(f"\nWrite this profile to \033[34m{config_path}\033[0m? [Y/n]: ").strip().lower()
        if confirm in ("n", "no"):
            print("Aborted.")
            sys.exit(0)

    write_profile_to_config(config_path, hostname, include_list, extra_dotfiles)
    print(f"\n\033[32mSuccessfully updated profile '{hostname}' in config.yaml!\033[0m")

    # Ask to install
    do_install = args.install
    if not do_install and not args.non_interactive:
        run_now = input("\nRun 'dotdrop install -a -f' now to apply dotfiles? [Y/n]: ").strip().lower()
        if run_now not in ("n", "no"):
            do_install = True

    if do_install:
        print("\n\033[36mRunning dotdrop install -a -f...\033[0m\n")
        cmd = ["dotdrop", "install", "-a", "-f"]
        subprocess.run(cmd)


if __name__ == "__main__":
    main()
