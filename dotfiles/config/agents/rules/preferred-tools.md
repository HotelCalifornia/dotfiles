# CLI Tool Preferences

This environment provides modern, high-performance CLI utilities. When running shell 
commands, inspecting files, or searching code, prefer these tools over traditional POSIX utilities:

| Traditional Tool | Preferred Replacement | Key Flags / Conventions |
| :--- | :--- | :--- |
| `grep` / `fgrep` | **`rg`** (ripgrep) | Fast, recursive by default; use `-i` for case-insensitivity, `--hidden` to include hidden files. |
| `cat` / `less` | **`bat`** | Syntax-highlighted; use `bat --paging=never` or `bat --style=plain` for piped outputs. |
| `ls` | **`eza`** | Colorized; use `eza --icons -la` or `eza -T` for directory tree views. |
| `du` | **`dust`** | Visual disk usage; prefer `dust` to summarize directory and disk allocations. |
| `cat` (Markdown) | **`glow`** | Rich terminal markdown rendering; use `glow -p` or pipe output to `glow`. |
| Mermaid diagrams | **`termaid`** | Renders `.mmd` diagrams as Unicode text boxes in the terminal. |

### Operational Notes
- All preferred tools are installed in `$HOME/.cargo/bin` or `$HOME/.local/bin` and are available on `$PATH`.
- When non-interactive scripting requires pure raw POSIX output without ANSI escape codes, standard utilities or `--style=plain` / `--no-icons` flags remain acceptable as fallbacks.
