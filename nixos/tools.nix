{ config, lib, pkgs, ... }:

let
  cfg = config.dotfiles.tools;
  manifest = builtins.fromTOML (builtins.readFile ../dotfiles/config/tools.toml);

  useNix = ver: import (builtins.fetchTarball "https://github.com/NixOS/nixpkgs/archive/nixos-${ver}.tar.gz") {
    inherit (pkgs.stdenv.hostPlatform) system;
  };

  matchesGroup = tool:
    let
      single = lib.optional (tool ? group) tool.group;
      multi = if tool ? groups then lib.toList tool.groups else [];
    in
      lib.any (g: lib.elem g cfg.groups) (single ++ multi);

  resolvePkg = name: tool:
    let
      attr = tool.nix or name;
      pkgSet = if tool ? nix_channel then useNix tool.nix_channel else pkgs;
    in
      if attr == false then null else pkgSet.${attr};

  selectedPackages = lib.filter (p: p != null) (
    lib.mapAttrsToList (name: tool:
      if matchesGroup tool then resolvePkg name tool else null
    ) (manifest.tools or {})
  );
in {
  options.dotfiles.tools = {
    groups = lib.mkOption {
      type = lib.types.listOf lib.types.str;
      default = [ "shell" "neovim" "user" "git" ];
      description = "Tool groups from dotfiles/config/tools.toml to install via Nix.";
    };
  };

  config = {
    environment.systemPackages = selectedPackages ++ [
      pkgs.file
      pkgs.python3
      pkgs.uv
    ];

    programs.gnupg.agent = lib.mkIf (lib.elem "git" cfg.groups) {
      enable = lib.mkDefault true;
      pinentryPackage = lib.mkDefault pkgs.pinentry-curses;
    };
  };
}
