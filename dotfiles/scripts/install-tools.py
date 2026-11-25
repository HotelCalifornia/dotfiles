#!/usr/bin/env python3
"""
Install and manage CLI and application tools declared in tools.toml.

Supports:
- Python tools managed via `uv tool` (standard PyPI and custom forks with editable resolution).
- Rust tools managed via `cargo install` (e.g. dust, eza, bat).
- AppImage / GitHub release binary tools (e.g. neovim, wezterm on Linux; Homebrew/bundle on macOS).
"""

import argparse
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import urllib.error
import urllib.request
import zipfile
from urllib.parse import unquote, urlparse

try:
    import tomllib
except ModuleNotFoundError:
    try:
        import tomli as tomllib
    except ModuleNotFoundError:
        tomllib = None


def parse_toml(path):
    if tomllib is not None:
        with open(path, "rb") as f:
            return tomllib.load(f)

    # Fallback basic TOML parser for two-level tables: [manager.tool_name]
    data = {"uv": {}, "cargo": {}, "appimage": {}, "github-release": {}, "tools": {}}
    current_section = None
    current_tool = None

    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("[") and line.endswith("]"):
                header = line[1:-1].strip()
                parts = header.split(".", 1)
                if len(parts) == 2:
                    current_section, current_tool = parts[0].strip(), parts[1].strip()
                    if current_section not in data:
                        data[current_section] = {}
                    data[current_section][current_tool] = {}
                else:
                    current_section = parts[0].strip()
                    current_tool = None
                    if current_section not in data:
                        data[current_section] = {}
            elif current_section and current_tool and "=" in line:
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip('"\'')
                if v.startswith("[") and v.endswith("]"):
                    items = [x.strip().strip('"\'') for x in v[1:-1].split(",") if x.strip()]
                    data[current_section][current_tool][k] = items
                elif v.lower() in ("true", "false"):
                    data[current_section][current_tool][k] = v.lower() == "true"
                else:
                    data[current_section][current_tool][k] = v
    return data


def find_executable(name, extra_paths=None):
    found = shutil.which(name)
    if found:
        return found
    if extra_paths:
        for path in extra_paths:
            expanded = os.path.expanduser(path)
            if os.path.isfile(expanded) and os.access(expanded, os.X_OK):
                return expanded
    return None


def find_uv():
    uv_path = find_executable(
        "uv",
        [
            "~/.local/bin/uv",
            "/usr/local/bin/uv",
            "/opt/homebrew/bin/uv",
        ],
    )
    if not uv_path:
        print("[toolchains] uv not found; bootstrapping via official installer...")
        try:
            subprocess.run("curl -LsSf https://astral.sh/uv/install.sh | sh", shell=True, check=True)
            candidate = os.path.expanduser("~/.local/bin/uv")
            if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
                return candidate
        except Exception as e:
            print(f"[toolchains] Warning: failed to auto-install uv: {e}", file=sys.stderr)
    return uv_path


def find_cargo():
    cargo_path = find_executable(
        "cargo",
        [
            "~/.cargo/bin/cargo",
            "/usr/local/bin/cargo",
            "/opt/homebrew/bin/cargo",
        ],
    )
    if not cargo_path:
        print("[toolchains] cargo not found; bootstrapping Rust via rustup...")
        try:
            cmd = "curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --default-toolchain stable --profile default"
            subprocess.run(cmd, shell=True, check=True)
            candidate = os.path.expanduser("~/.cargo/bin/cargo")
            if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
                return candidate
        except Exception as e:
            print(f"[toolchains] Warning: failed to auto-install rustup: {e}", file=sys.stderr)
    return cargo_path


# ==============================================================================
# UV / Python Tool Management
# ==============================================================================

def resolve_uv_fork_source(tool_name, config):
    cmd_name = config.get("command", tool_name)
    bin_path = shutil.which(cmd_name)

    if bin_path:
        py_interp = sys.executable
        try:
            with open(bin_path, "rb") as f:
                if f.read(2) == b"#!":
                    first_line = f.readline().decode("utf-8", errors="ignore").strip()
                    interp = first_line.split()[0]
                    if os.path.isfile(interp) and os.access(interp, os.X_OK):
                        py_interp = interp
        except Exception:
            pass

        inspect_code = (
            'import importlib.metadata, json; '
            f'dist = importlib.metadata.distribution("{tool_name}"); '
            'installer = (dist.read_text("INSTALLER") or "").strip(); '
            'raw_url = dist.read_text("direct_url.json") or ""; '
            'print(json.dumps({"installer": installer, "direct_url": raw_url}))'
        )

        try:
            res = subprocess.run([py_interp, "-c", inspect_code], capture_output=True, text=True)
            if res.returncode == 0 and res.stdout.strip():
                data = json.loads(res.stdout.strip())
                installer = data.get("installer", "unknown")
                print(f"[uv:{tool_name}] Found existing '{cmd_name}' via {installer} ({bin_path})")

                raw_url = data.get("direct_url")
                if raw_url:
                    direct_url = json.loads(raw_url)
                    is_editable = direct_url.get("dir_info", {}).get("editable", False)
                    url = direct_url.get("url", "")
                    if is_editable and url.startswith("file:"):
                        source_dir = unquote(urlparse(url).path)
                        if os.path.isdir(source_dir):
                            print(f"[uv:{tool_name}] Resolved editable install at: {source_dir}")
                            return source_dir, None
                    elif url.startswith("git"):
                        return None, url
        except Exception as e:
            print(f"[uv:{tool_name}] Warning while checking metadata: {e}", file=sys.stderr)

    local_paths = config.get("local_paths", [])
    for path_str in local_paths:
        candidate = os.path.expanduser(path_str)
        if os.path.isdir(candidate):
            print(f"[uv:{tool_name}] Resolved local repository at: {candidate}")
            return candidate, None

    fork_url = config.get("fork")
    return None, fork_url


def install_uv_tool(uv_bin, tool_name, config, force=False):
    has_custom_fork = bool(config.get("fork") or config.get("local_paths"))

    if has_custom_fork:
        source_dir, git_url = resolve_uv_fork_source(tool_name, config)
        if source_dir:
            cmd = [uv_bin, "tool", "install", "--force", "--editable", source_dir]
        elif git_url:
            cmd = [uv_bin, "tool", "install", "--force", git_url]
        else:
            print(f"[uv:{tool_name}] Error: could not resolve source or fork URL", file=sys.stderr)
            return False
    else:
        cmd = [uv_bin, "tool", "install"]
        if force:
            cmd.append("--force")
        cmd.append(tool_name)

    print(f"[uv:{tool_name}] Running: {' '.join(cmd)}")
    res = subprocess.run(cmd)
    return res.returncode == 0


# ==============================================================================
# Cargo / Rust Tool Management
# ==============================================================================

def is_cargo_tool_installed(crate_name, config):
    cmd_name = config.get("command", crate_name)
    # Check if executable exists in ~/.cargo/bin specifically
    user_cargo_bin = os.path.expanduser(f"~/.cargo/bin/{cmd_name}")
    if os.path.isfile(user_cargo_bin) and os.access(user_cargo_bin, os.X_OK):
        return True, user_cargo_bin
    return False, None


def install_cargo_tool(cargo_bin, crate_name, config, force=False):
    cmd_name = config.get("command", crate_name)
    is_installed, bin_path = is_cargo_tool_installed(crate_name, config)

    # To avoid long recompilations, skip if already installed unless --force is specified
    if is_installed and not force:
        print(f"[cargo:{crate_name}] '{cmd_name}' is already installed ({bin_path}). Skipping (use --force to recompile).")
        return True

    cmd = [cargo_bin, "install"]
    if force:
        cmd.append("--force")
    if config.get("version"):
        cmd.extend(["--version", str(config["version"])])
    if config.get("locked", True):
        cmd.append("--locked")
    if config.get("git"):
        cmd.extend(["--git", config["git"]])
    if config.get("features"):
        cmd.extend(["--features", config["features"]])
    cmd.append(crate_name)

    print(f"[cargo:{crate_name}] Running: {' '.join(cmd)}")
    res = subprocess.run(cmd)
    return res.returncode == 0


# ==============================================================================
# AppImage / Binary Tool Management (Linux AppImages, macOS Homebrew/Bundles)
# ==============================================================================

def is_wsl():
    if platform.system() != "Linux":
        return False
    try:
        with open("/proc/version", "r", encoding="utf-8") as f:
            content = f.read().lower()
            if "microsoft" in content or "wsl" in content:
                return True
    except Exception:
        pass
    if os.path.exists("/proc/sys/fs/binfmt_misc/WSLInterop"):
        return True
    return False


def get_system_arch():
    machine = platform.machine().lower()
    if machine in ("x86_64", "amd64"):
        return "x86_64"
    elif machine in ("aarch64", "arm64"):
        return "arm64"
    return machine


def setup_desktop_entry(name, config, target_file, target_symlink):
    if platform.system() != "Linux":
        return

    apps_dir = os.path.expanduser("~/.local/share/applications")
    icons_dir = os.path.expanduser("~/.local/share/icons/hicolor/128x128/apps")
    os.makedirs(apps_dir, exist_ok=True)
    os.makedirs(icons_dir, exist_ok=True)

    cmd_name = config.get("command", name)
    desktop_name = config.get("desktop_name", name.capitalize())
    desktop_comment = config.get("desktop_comment", f"{desktop_name} Application")
    categories = config.get("desktop_categories", "Utility;")
    is_terminal = config.get("desktop_terminal", False)
    icon_name = config.get("icon_name", cmd_name)

    extracted_icon_path = None
    app_dir = os.path.dirname(target_file)

    # Attempt to extract icon from the AppImage
    try:
        extract_res = subprocess.run(
            [target_file, "--appimage-extract", "*.png"],
            cwd=app_dir,
            capture_output=True,
            timeout=10,
        )
        if extract_res.returncode == 0:
            squash_dir = os.path.join(app_dir, "squashfs-root")
            if os.path.isdir(squash_dir):
                for root, _, files in os.walk(squash_dir):
                    for f in files:
                        if f.endswith(".png"):
                            src_icon = os.path.join(root, f)
                            dst_icon = os.path.join(icons_dir, f"{icon_name}.png")
                            shutil.copy2(src_icon, dst_icon)
                            extracted_icon_path = dst_icon
                            break
                    if extracted_icon_path:
                        break
                shutil.rmtree(squash_dir, ignore_errors=True)
    except Exception as e:
        print(f"[appimage:{name}] Notice: icon extraction skipped ({e})", file=sys.stderr)

    desktop_file = os.path.join(apps_dir, f"{cmd_name}.desktop")
    icon_value = extracted_icon_path or icon_name
    terminal_str = "true" if is_terminal else "false"

    content = (
        "[Desktop Entry]\n"
        "Type=Application\n"
        f"Name={desktop_name}\n"
        f"Comment={desktop_comment}\n"
        f"Exec={target_symlink} %F\n"
        f"Icon={icon_value}\n"
        f"Terminal={terminal_str}\n"
        f"Categories={categories}\n"
    )
    with open(desktop_file, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"[appimage:{name}] Installed desktop entry: {desktop_file}")

    if shutil.which("update-desktop-database"):
        try:
            subprocess.run(["update-desktop-database", apps_dir], capture_output=True)
        except Exception:
            pass


def install_release_tool(name, config, force=False, update=False):
    system = platform.system()
    cmd_name = config.get("command", name)
    bin_name = config.get("binary", cmd_name)
    tag_label = "release"

    # Check WSL guard
    if is_wsl() and config.get("skip_wsl", False):
        print(f"[{tag_label}:{name}] Running inside WSL: skipping '{cmd_name}' installation.")
        return True

    existing_bin = shutil.which(cmd_name)

    # On macOS, check existing binary or .app bundle
    if system == "Darwin":
        app_bundle = config.get("app_bundle")
        if app_bundle and os.path.exists(os.path.expanduser(app_bundle)):
            print(f"[{tag_label}:{name}] '{cmd_name}' found at {app_bundle}. Skipping.")
            return True
        if existing_bin:
            print(f"[{tag_label}:{name}] '{cmd_name}' is already installed ({existing_bin}). Skipping.")
            return True

        brew_bin = shutil.which("brew")
        if brew_bin:
            if config.get("brew_cask"):
                cask = config["brew_cask"]
                print(f"[{tag_label}:{name}] Installing cask '{cask}' via Homebrew...")
                res = subprocess.run([brew_bin, "install", "--cask", cask])
                return res.returncode == 0
            elif config.get("brew"):
                formula = config["brew"]
                print(f"[{tag_label}:{name}] Installing formula '{formula}' via Homebrew...")
                res = subprocess.run([brew_bin, "install", formula])
                return res.returncode == 0

        print(f"[{tag_label}:{name}] Neither '{cmd_name}' nor Homebrew was found on macOS.", file=sys.stderr)
        return False

    elif system == "Linux":
        app_dir = os.path.expanduser(f"~/.local/share/{name}")
        bin_dir = os.path.expanduser("~/.local/bin")
        target_symlink = os.path.join(bin_dir, cmd_name)
        version_file = os.path.join(app_dir, ".version")

        current_version = None
        if os.path.isfile(version_file):
            try:
                with open(version_file, "r", encoding="utf-8") as f:
                    current_version = f.read().strip()
            except Exception:
                pass

        is_installed = os.path.exists(target_symlink) or existing_bin

        if is_installed and not force and not update:
            ver_str = f" ({current_version})" if current_version else ""
            loc = target_symlink if os.path.exists(target_symlink) else existing_bin
            print(f"[{tag_label}:{name}] '{cmd_name}'{ver_str} is already installed ({loc}). Skipping.")
            # Ensure desktop entry exists if requested
            if config.get("desktop_entry", False) and os.path.exists(target_symlink):
                desktop_file = os.path.expanduser(f"~/.local/share/applications/{cmd_name}.desktop")
                if not os.path.exists(desktop_file):
                    real_bin = os.path.realpath(target_symlink)
                    setup_desktop_entry(name, config, real_bin, target_symlink)
            return True

        repo = config.get("repo")
        if not repo:
            print(f"[{tag_label}:{name}] Error: no GitHub 'repo' specified in manifest.", file=sys.stderr)
            return False

        api_url = f"https://api.github.com/repos/{repo}/releases/latest"
        headers = {"User-Agent": "dotfiles-tool-installer"}
        gh_token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
        if gh_token:
            headers["Authorization"] = f"Bearer {gh_token}"

        req = urllib.request.Request(api_url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                release_data = json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            if is_installed and not force:
                print(f"[{tag_label}:{name}] Warning: GitHub API check failed ({e}); keeping existing installation.")
                return True
            print(f"[{tag_label}:{name}] Error fetching release metadata from {api_url}: {e}", file=sys.stderr)
            return False

        latest_tag = release_data.get("tag_name", "")
        if current_version and current_version == latest_tag and not force:
            print(f"[{tag_label}:{name}] '{cmd_name}' is already up-to-date ({latest_tag}).")
            return True

        # Resolve asset pattern with architecture replacement
        raw_pattern = config.get("asset", "")
        arch = get_system_arch()
        # Per-tool override for projects that name architectures differently (e.g. amd64)
        arch = config.get("arch_map", {}).get(arch, arch)
        resolved_pattern = raw_pattern.replace("{arch}", arch)

        matching_asset = None
        for asset in release_data.get("assets", []):
            asset_name = asset.get("name", "")
            if re.search(resolved_pattern, asset_name):
                matching_asset = asset
                break

        if not matching_asset:
            print(
                f"[{tag_label}:{name}] Error: no release asset matched pattern '{resolved_pattern}' in release {latest_tag}.",
                file=sys.stderr,
            )
            return False

        download_url = matching_asset.get("browser_download_url")
        asset_filename = matching_asset.get("name")
        os.makedirs(app_dir, exist_ok=True)
        os.makedirs(bin_dir, exist_ok=True)

        target_file = os.path.join(app_dir, asset_filename)
        print(f"[{tag_label}:{name}] Downloading {asset_filename} ({latest_tag})...")

        dl_req = urllib.request.Request(download_url, headers=headers)
        try:
            with urllib.request.urlopen(dl_req, timeout=120) as resp, open(target_file, "wb") as out:
                shutil.copyfileobj(resp, out)
        except Exception as e:
            print(f"[{tag_label}:{name}] Error downloading asset: {e}", file=sys.stderr)
            return False

        executable_file = target_file
        # Handle archive extraction (tar / zip)
        if target_file.endswith((".tar.gz", ".tgz", ".tar.xz", ".tar.bz2", ".tar")):
            extracted_bin = os.path.join(app_dir, bin_name)
            try:
                with tarfile.open(target_file, "r:*") as tar:
                    found_member = None
                    for member in tar.getmembers():
                        if os.path.basename(member.name) == bin_name and member.isfile():
                            found_member = member
                            break
                    if found_member:
                        with tar.extractfile(found_member) as src, open(extracted_bin, "wb") as dst:
                            shutil.copyfileobj(src, dst)
                        executable_file = extracted_bin
                    else:
                        print(f"[{tag_label}:{name}] Warning: binary '{bin_name}' not found inside archive", file=sys.stderr)
            except Exception as e:
                print(f"[{tag_label}:{name}] Error extracting tar archive: {e}", file=sys.stderr)
                return False
        elif target_file.endswith(".zip"):
            extracted_bin = os.path.join(app_dir, bin_name)
            try:
                with zipfile.ZipFile(target_file, "r") as z:
                    found_info = None
                    for zinfo in z.infolist():
                        if os.path.basename(zinfo.filename) == bin_name and not zinfo.is_dir():
                            found_info = zinfo
                            break
                    if found_info:
                        with z.open(found_info) as src, open(extracted_bin, "wb") as dst:
                            shutil.copyfileobj(src, dst)
                        executable_file = extracted_bin
                    else:
                        print(f"[{tag_label}:{name}] Warning: binary '{bin_name}' not found inside zip archive", file=sys.stderr)
            except Exception as e:
                print(f"[{tag_label}:{name}] Error extracting zip archive: {e}", file=sys.stderr)
                return False

        os.chmod(executable_file, 0o755)

        # Update symlink atomically
        temp_symlink = target_symlink + ".tmp"
        if os.path.islink(temp_symlink) or os.path.exists(temp_symlink):
            os.remove(temp_symlink)
        os.symlink(executable_file, temp_symlink)
        os.replace(temp_symlink, target_symlink)

        with open(version_file, "w", encoding="utf-8") as f:
            f.write(latest_tag + "\n")

        print(f"[{tag_label}:{name}] Successfully installed {latest_tag} to {target_symlink}")

        # Set up desktop entry if requested
        if config.get("desktop_entry", False):
            setup_desktop_entry(name, config, target_file, target_symlink)

        return True
    else:
        print(f"[{tag_label}:{name}] Unsupported OS: {system}", file=sys.stderr)
        return False


# Alias for backward compatibility
install_appimage_tool = install_release_tool


# ==============================================================================
# Main Orchestrator
# ==============================================================================

def tool_matches_group(cfg, target_group):
    if not target_group:
        return True
    tool_group = cfg.get("group")
    tool_groups = cfg.get("groups", [])
    if isinstance(tool_groups, str):
        tool_groups = [tool_groups]
    return tool_group == target_group or target_group in tool_groups


def main():
    parser = argparse.ArgumentParser(description="Install tools via uv, cargo, and github-release from tools.toml manifest")
    parser.add_argument("manifest", nargs="?", help="Path to tools.toml (defaults to ~/.config/tools.toml)")
    parser.add_argument("--tool", help="Install a specific tool only")
    parser.add_argument("--group", help="Filter tools by group (e.g. shell, terminal, neovim, user)")
    parser.add_argument(
        "--manager",
        choices=["uv", "cargo", "github-release", "appimage"],
        help="Filter by tool manager",
    )
    parser.add_argument("--update", action="store_true", help="Check and install updates for tools")
    parser.add_argument("--force", action="store_true", help="Force reinstallation of tools")
    args = parser.parse_args()

    manifest_path = args.manifest
    if not manifest_path:
        for candidate in [
            os.path.expanduser("~/.config/tools.toml"),
            os.path.expanduser("~/.config/tools/tools.toml"),
            os.path.join(os.path.dirname(__file__), "../config/tools.toml"),
            os.path.expanduser("~/.config/uv/tools.toml"),
            os.path.join(os.getcwd(), "tools.toml"),
        ]:
            if os.path.isfile(candidate):
                manifest_path = candidate
                break

    if not manifest_path or not os.path.isfile(manifest_path):
        print(f"Error: manifest file not found: {manifest_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Using manifest: {manifest_path}")
    data = parse_toml(manifest_path)

    uv_tools = dict(data.get("uv", {}))
    cargo_tools = dict(data.get("cargo", {}))
    release_tools = dict(data.get("github-release", {}))
    release_tools.update(data.get("appimage", {}))

    # Support [tools.<name>] with manager = "cargo" / "uv" / "github-release" / "appimage"
    generic_tools = data.get("tools", {})
    if isinstance(generic_tools, dict):
        for name, cfg in generic_tools.items():
            if isinstance(cfg, dict):
                mgr = cfg.get("manager", "uv")
                if mgr == "cargo":
                    cargo_tools[name] = cfg
                elif mgr in ("appimage", "github-release", "binary"):
                    release_tools[name] = cfg
                else:
                    uv_tools[name] = cfg

    # Filter tools by tool name and group
    selected_uv_tools = {}
    if args.manager not in ("cargo", "github-release", "appimage"):
        for name, cfg in uv_tools.items():
            if args.tool and name != args.tool:
                continue
            if not isinstance(cfg, dict):
                cfg = {}
            if tool_matches_group(cfg, args.group):
                selected_uv_tools[name] = cfg

    selected_cargo_tools = {}
    if args.manager not in ("uv", "github-release", "appimage"):
        for name, cfg in cargo_tools.items():
            if args.tool and name != args.tool:
                continue
            if not isinstance(cfg, dict):
                cfg = {}
            if tool_matches_group(cfg, args.group):
                selected_cargo_tools[name] = cfg

    selected_release_tools = {}
    if args.manager not in ("uv", "cargo"):
        for name, cfg in release_tools.items():
            if args.tool and name != args.tool:
                continue
            if not isinstance(cfg, dict):
                cfg = {}
            if tool_matches_group(cfg, args.group):
                selected_release_tools[name] = cfg

    total_selected = len(selected_uv_tools) + len(selected_cargo_tools) + len(selected_release_tools)
    if total_selected == 0:
        filter_desc = []
        if args.group:
            filter_desc.append(f"group='{args.group}'")
        if args.tool:
            filter_desc.append(f"tool='{args.tool}'")
        if args.manager:
            filter_desc.append(f"manager='{args.manager}'")
        desc = f" matching {', '.join(filter_desc)}" if filter_desc else ""
        print(f"No tools found{desc}.")
        return

    failed = []

    # Process UV tools
    if selected_uv_tools:
        uv_bin = find_uv()
        if not uv_bin:
            print("Error: 'uv' executable not found on PATH", file=sys.stderr)
            failed.extend(selected_uv_tools.keys())
        else:
            for name, cfg in selected_uv_tools.items():
                ok = install_uv_tool(uv_bin, name, cfg, force=args.force)
                if not ok:
                    failed.append(f"uv:{name}")

    # Process Cargo tools
    if selected_cargo_tools:
        cargo_bin = find_cargo()
        if not cargo_bin:
            print("Error: 'cargo' executable not found on PATH or ~/.cargo/bin", file=sys.stderr)
            failed.extend([f"cargo:{k}" for k in selected_cargo_tools.keys()])
        else:
            for name, cfg in selected_cargo_tools.items():
                ok = install_cargo_tool(cargo_bin, name, cfg, force=args.force)
                if not ok:
                    failed.append(f"cargo:{name}")

    # Process GitHub Release / AppImage tools
    if selected_release_tools:
        for name, cfg in selected_release_tools.items():
            ok = install_release_tool(name, cfg, force=args.force, update=args.update)
            if not ok:
                failed.append(f"release:{name}")

    if failed:
        print(f"\nFailed to install tools: {', '.join(failed)}", file=sys.stderr)
        sys.exit(1)

    print("\nAll tools processed successfully.")


if __name__ == "__main__":
    main()
