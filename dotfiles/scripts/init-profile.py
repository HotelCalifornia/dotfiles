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


def ask_review_action(hostname, config_path):
    if questionary:
        ans = safe_ask(questionary.select(
            "Review profile definition:",
            choices=[
                questionary.Choice("✔ Save profile to config.yaml and continue", value="save"),
                questionary.Choice("✎ Edit capabilities checklist", value="edit_mixins"),
                questionary.Choice("✎ Edit AI agent integrations", value="edit_agents"),
                questionary.Choice("✎ Change starting preset", value="edit_preset"),
                questionary.Choice("✎ Change device hostname", value="edit_hostname"),
                questionary.Choice("✖ Cancel and abort", value="abort"),
            ],
            default="save",
        ))
        if ans is None:
            return "abort"
        return ans
    else:
        print("\nReview actions:")
        print("  [1] Save profile to config.yaml and continue [Default]")
        print("  [2] Edit capabilities checklist")
        print("  [3] Edit AI agent integrations")
        print("  [4] Change starting preset")
        print("  [5] Change device hostname")
        print("  [6] Cancel and abort")
        try:
            choice = input("Select [1-6]: ").strip() or "1"
        except (EOFError, KeyboardInterrupt):
            return "abort"
        mapping = {
            "1": "save",
            "2": "edit_mixins",
            "3": "edit_agents",
            "4": "edit_preset",
            "5": "edit_hostname",
            "6": "abort",
        }
        return mapping.get(choice, "save")


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


def run_interactive_wizard(config_path, default_host, args):
    hostname = args.hostname or default_host
    preset_choice = "1"
    include_list = list(PRESETS["1"]["include"])
    suggest_mac_rc = PRESETS["1"].get("suggest_mac_rc", False)
    selected_agents = []
    mac_rc_enabled = False

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
            step = "mac_hooks" if (platform.system() == "Darwin" and suggest_mac_rc) else "review"

        elif step == "mac_hooks":
            mac_rc_enabled, nav = ask_mac_hooks()
            if nav == "back":
                step = "agents"
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

            action = ask_review_action(hostname, config_path)
            if action == "save":
                return hostname, full_includes, extra_dfs
            elif action == "edit_mixins":
                step = "mixins"
            elif action == "edit_agents":
                step = "agents"
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
    args = parser.parse_args()

    if not sys.stdin.isatty():
        # Non-TTY environment (e.g. redirected stdin, pipes, background tools)
        args.non_interactive = True

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
        if args.install:
            subprocess.run(["dotdrop", "install", "-a", "-f"])
        return

    # Interactive Wizard branch
    hostname, include_list, extra_dotfiles = run_interactive_wizard(config_path, default_host, args)

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

    # Offer to install
    do_install = args.install
    if not do_install:
        do_install = ask_run_install()

    if do_install:
        print("\n\033[36mRunning dotdrop install -a -f...\033[0m\n")
        subprocess.run(["dotdrop", "install", "-a", "-f"])


if __name__ == "__main__":
    main()
