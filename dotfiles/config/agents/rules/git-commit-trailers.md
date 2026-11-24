# Git Commit Trailers

When generating or assisting with git commits in this repository and across projects, AI agents must include an `Assisted-by` trailer in the commit message to transparently attribute the agent harness and any models consulted.

### Format Specification

The trailer follows standard RFC 2822 / git trailer formatting and must appear at the end of the commit message body, preceded by an empty line:

```text
<commit summary>

<optional commit description>

Assisted-by: <Harness>/<Model>
```

### Examples

- **Single Model Consultation**:
  ```text
  Assisted-by: Antigravity/Gemini 3.8 Flash
  ```
  ```text
  Assisted-by: Claude Code/Claude 3.7 Sonnet
  ```

- **Multiple Models or Multi-Agent Consultation**:
  If multiple models or subagents contributed to the task, list them separated by commas or on consecutive trailer lines:
  ```text
  Assisted-by: Antigravity/Gemini 3.8 Flash, Antigravity/Gemini 3.5 Pro
  ```
  or:
  ```text
  Assisted-by: Antigravity/Gemini 3.8 Flash
  Assisted-by: Claude Code/Claude 3.7 Sonnet
  ```

### Operational Notes
- Always separate the trailer block from the commit subject and body with a blank line.
- Commits in this repository are GPG-signed; agents should invoke git commits with `git commit -S`.
