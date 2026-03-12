---
summary: "Logging surfaces, file logs, and console formatting"
read_when:
  - Changing logging output or formats
  - Debugging CLI or gateway output
title: "Logging"
---

# Logging

OpenClaw has two log "surfaces":

- **Console output** (what you see in the terminal).
- **File logs** (JSON lines) written by the gateway logger.

## File-based logger

- Default rolling log file is under `/tmp/openclaw/` (one file per day):
  `openclaw-YYYY-MM-DD.log`
- The log file path and level can be configured via `~/.openclaw/openclaw.json`:
  - `logging.file` — path override
  - `logging.level` — `debug`, `info`, `warn`, `error`, `trace`

The file format is one JSON object per line.

CLI tail:

```bash
openclaw logs --follow
```

### Console vs file log levels

- **File logs** are controlled exclusively by `logging.level`.
- `--verbose` only affects **console verbosity**; it does **not** raise the file log level.
- To capture verbose-only details in file logs, set `logging.level` to `debug` or `trace`.

### Console level

- `logging.consoleLevel` (default: `info`)
- `logging.consoleStyle` — `pretty` | `compact` | `json`

## Tool summary redaction

Verbose tool summaries can mask sensitive tokens before they hit the console stream.

- `logging.redactSensitive`: `off` | `tools` (default: `tools`)
- `logging.redactPatterns`: array of regex strings (overrides defaults)
  - Matches are masked by keeping the first 6 + last 4 chars (length >= 18), otherwise `***`.
  - Defaults cover common key assignments, CLI flags, JSON fields, bearer headers, PEM blocks, and popular token prefixes.

## Gateway WebSocket logs

- **Normal mode (no `--verbose`)**: only "interesting" RPC results are printed.
- **Verbose mode (`--verbose`)**: prints all WS request/response traffic.

### WS log style

- `--ws-log auto` (default)
- `--ws-log compact`: compact output (paired request/response)
- `--ws-log full`: full per-frame output

## Console formatting

The console formatter is **TTY-aware** and prints consistent, prefixed lines.

Behavior:

- **Subsystem prefixes** on every line (e.g. `[gateway]`, `[channels]`)
- **Color when output is a TTY**, respects `NO_COLOR`
- **Shortened subsystem prefixes**: drops leading `gateway/` + `channels/`

## Python implementation

- `openclaw/monitoring/logger.py` — `JsonFileHandler`, `setup_logging()`
- Configuration via `logging` section of `~/.openclaw/openclaw.json`

## Related docs

- [Configuration reference](/gateway/configuration-reference)
- [CLI logs command](/cli/logs)
