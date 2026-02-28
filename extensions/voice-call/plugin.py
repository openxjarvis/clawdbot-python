"""Voice call extension — Twilio-backed voice call integration.

Mirrors TypeScript: openclaw/extensions/voice-call/index.ts

Registers:
- Voice call HTTP handler (Twilio webhooks)
- Voice call CLI commands
- Voice call service
"""
from __future__ import annotations



def register(api) -> None:
    # TODO: implement voice-call runtime, config schema, CLI commands, and HTTP
    # handler — see openclaw/extensions/voice-call/src/ for reference
    pass

plugin = {
    "id": "voice-call",
    "name": "Voice Call",
    "description": "Voice call functionality via Twilio/Telnyx — inbound/outbound call handling.",
    "register": register,
}
