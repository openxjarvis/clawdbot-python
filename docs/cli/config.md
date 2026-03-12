---
summary: "CLI reference for `openclaw config` (get/set/unset config values)"
read_when:
  - You want to read or edit config non-interactively
title: "config"
---

# `openclaw config`

Config helpers: get/set/unset values by path.

## Examples

```bash
openclaw config get browser.executablePath
openclaw config set browser.executablePath "/usr/bin/google-chrome"
openclaw config unset tools.web.search.apiKey
openclaw config list
```

## Python implementation

- `openclaw/cli/config_cmd.py`
