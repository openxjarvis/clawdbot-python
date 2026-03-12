---
summary: "Telegram Bot API integration via grammY with setup notes"
read_when:
  - Working on Telegram or grammY pathways
title: grammY
---

# grammY Integration (Telegram Bot API)

# Why grammY

- Python-compatible Bot API client path with built-in long-poll + webhook helpers, middleware, error handling, rate limiter.
- Cleaner media helpers than hand-rolling fetch + FormData; supports all Bot API methods.
- Extensible: proxy support via custom fetch, session middleware (optional), type-safe context.

# What we shipped

- **Single client path:** fetch-based implementation removed; grammY is now the sole Telegram client (send + gateway) with the grammY throttler enabled by default.
- **Gateway:** `monitor_telegram_provider` builds a Bot instance, wires mention/allowlist gating, media download via `getFile`/`download`, and delivers replies with `sendMessage/sendPhoto/sendVideo/sendAudio/sendDocument`. Supports long-poll or webhook via `webhookCallback`.
- **Proxy:** optional `channels.telegram.proxy` uses a proxy agent through the client's base fetch.
- **Webhook support:** `webhook_set.py` wraps `setWebhook/deleteWebhook`; `webhook.py` hosts the callback with health + graceful shutdown. Gateway enables webhook mode when `channels.telegram.webhookUrl` + `channels.telegram.webhookSecret` are set (otherwise it long-polls).
- **Sessions:** direct chats collapse into the agent main session (`agent:<agentId>:<mainKey>`); groups use `agent:<agentId>:telegram:group:<chatId>`; replies route back to the same channel.
- **Config knobs:** `channels.telegram.botToken`, `channels.telegram.dmPolicy`, `channels.telegram.groups` (allowlist + mention defaults), `channels.telegram.allowFrom`, `channels.telegram.groupAllowFrom`, `channels.telegram.groupPolicy`, `channels.telegram.mediaMaxMb`, `channels.telegram.linkPreview`, `channels.telegram.proxy`, `channels.telegram.webhookSecret`, `channels.telegram.webhookUrl`, `channels.telegram.webhookHost`.
- **Live stream preview:** optional `channels.telegram.streamMode` sends a temporary message and updates it with `editMessageText`. This is separate from channel block streaming.
- **Tests:** mock covers DM + group mention gating and outbound send; more media/webhook fixtures still welcome.

Open questions

- Optional throttler plugins if we hit Bot API 429s.
- Add more structured media tests (stickers, voice notes).
- Make webhook listen port configurable (currently fixed to 8787 unless wired through the gateway).
