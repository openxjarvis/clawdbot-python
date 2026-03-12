---
summary: "CLI reference for `openclaw message` (send messages)"
read_when:
  - You want to send a message to an agent from the CLI
title: "message"
---

# `openclaw message`

Send a message to an agent or channel.

## Examples

```bash
openclaw message "Hello from CLI"
openclaw message --agent work "Summarize tasks"
openclaw message --channel telegram --to @user "Hello"
```

## Python implementation

- `openclaw/cli/message_cmd.py`
