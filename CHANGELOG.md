# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.8.2] - 2026-03-04

### Added
- Feishu plugin fully refactored into self-contained `extensions/feishu/src/` structure, aligning with TypeScript `clawdbot-feishu` architecture
- 11 granular Feishu Bitable tools (create/update/delete table, fields, records, views, forms)
- Feishu Calendar, Task (v2), Urgent, Drive, Wiki, Doc tools in Feishu plugin
- `ensure_media_dir()` and `ensure_sandboxes_dir()` bootstrapped on startup, mirroring TS `media/` and `sandboxes/` directory structure

### Fixed
- Feishu typing indicator: `EmojiType` → `Emoji` Python SDK correction (silent `ImportError` resolved)
- Telegram sticker cache: wrong `state/telegram/sticker-cache.json` path fixed to use `STATE_DIR / "telegram"`
- Cron job channel routing: messages now correctly delivered back to the originating channel/account
- Feishu typing indicator now uses `Typing` emoji reactions as a visual progress signal

### Changed
- All hardcoded `Path.home() / ".openclaw"` references replaced with `STATE_DIR` from `openclaw.config.paths`, ensuring `OPENCLAW_STATE_DIR` env-var overrides work everywhere
- `cli/cron_cmd.py` consolidated to use `_CRON_STORE` / `_CRON_HISTORY` constants
- `extensions/feishu/` plugin is now the authoritative location for all Feishu-specific tools (moved from `openclaw/channels/feishu/tools/`)

## [Unreleased]

### Added
- REST API with FastAPI
- CLI with rich interface
- Enhanced configuration with Pydantic Settings
- 5 complete examples
- Connection management for channels
- Health check system
- Metrics collection with Prometheus export
- Enhanced logging with JSON/colored formats
- Production readiness verification (2026-02-10)
- Comprehensive implementation report (PLAN_IMPLEMENTATION_REPORT.md)

### Changed
- Reorganized documentation into docs/ folder
- Updated README to English

### Verified
- ✅ All dependencies installed and verified (179 packages)
- ✅ Gateway server operational on port 18789
- ✅ Web UI running on port 8080
- ✅ Telegram channel fully functional
- ✅ 23 tools registered and operational
- ✅ 56 skills loaded successfully
- ✅ CLI commands working (74+ commands)
- ✅ Bootstrap process completing without errors
- ✅ Architecture alignment with TypeScript version: 90-100%

## [0.3.0] - 2026-01-28

### Added
- Testing framework with pytest
- Context management for agent runtime
- Error handling and recovery system
- Tool permission system
- Rate limiting for tools
- Enhanced Telegram and Discord channels

### Changed
- Improved agent runtime with retry logic
- Better error messages and logging

## [0.2.0] - 2026-01-27

### Added
- Initial Python implementation
- Agent runtime with Claude and OpenAI support
- 24 core tools
- 17 channel plugins (framework)
- 52 skill templates
- Gateway WebSocket server
- Docker support

### Changed
- Ported from TypeScript version

## [0.1.0] - 2026-01-26

### Added
- Project initialization
- Basic structure
- Core dependencies

---

[Unreleased]: https://github.com/zhaoyuong/openclaw-python/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/zhaoyuong/openclaw-python/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/zhaoyuong/openclaw-python/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/zhaoyuong/openclaw-python/releases/tag/v0.1.0
