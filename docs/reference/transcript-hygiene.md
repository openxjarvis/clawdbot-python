---
summary: "Reference: provider-specific transcript sanitization and repair rules"
read_when:
  - You are debugging provider request rejections tied to transcript shape
  - You are changing transcript sanitization or tool-call repair logic
  - You are investigating tool-call id mismatches across providers
title: "Transcript Hygiene"
---

# Transcript Hygiene (Provider Fixups)

This document describes **provider-specific fixes** applied to transcripts before a run
(building model context). These are **in-memory** adjustments used to satisfy strict
provider requirements. These hygiene steps do **not** rewrite the stored JSONL transcript
on disk.

Scope includes:

- Tool call id sanitization
- Tool result pairing repair
- Turn validation / ordering (Google/Gemini)
- Thought signature cleanup (OpenRouter + Gemini)
- Image payload sanitization
- Antigravity Claude (Google-hosted) thinking block normalization

If you need transcript storage details, see:

- [/reference/session-management-compaction](/reference/session-management-compaction)

---

## Where this runs

All transcript hygiene is centralized in:

- **Policy selection**: `openclaw/agents/history_utils.py` — `resolve_transcript_policy()`
- **Application**: `sanitize_session_history()` in `history_utils.py`

The policy uses `provider`, `model_api`, and `model_id` to decide what to apply.

---

## `TranscriptPolicy` fields

```python
@dataclass
class TranscriptPolicy:
    sanitize_mode: Literal["full", "images-only"] = "images-only"
    sanitize_tool_call_ids: bool = False
    tool_call_id_mode: Literal["strict", "strict9"] | None = None
    repair_tool_use_result_pairing: bool = False
    preserve_signatures: bool = False
    sanitize_thought_signatures: SanitizeThoughtSignaturesConfig | None = None
    normalize_antigravity_thinking_blocks: bool = False
    apply_google_turn_ordering: bool = False
    validate_gemini_turns: bool = False
    validate_anthropic_turns: bool = False
    allow_synthetic_tool_results: bool = False
```

---

## Per-provider policies

### Google / Gemini (`google-ai-studio`, `google-vertex`, `gemini`)

- `sanitize_mode = "full"` — strip non-text content types not supported by Google
- `sanitize_tool_call_ids = True`, `tool_call_id_mode = "strict"` — normalize tool call IDs
- `repair_tool_use_result_pairing = True` — ensure every tool call has a matching tool result
- `apply_google_turn_ordering = True` — enforce strict turn alternation
- `validate_gemini_turns = True` — validate Gemini-specific turn requirements

### Mistral (`mistral`, `mixtral`, `codestral`, etc.)

- `sanitize_tool_call_ids = True`, `tool_call_id_mode = "strict9"` — normalize IDs to max 9 chars
- `sanitize_mode = "full"`

### Anthropic (`anthropic-messages` API or `anthropic` provider)

- `sanitize_mode = "full"`
- `sanitize_tool_call_ids = True`, `tool_call_id_mode = "strict"`
- `repair_tool_use_result_pairing = True`
- `validate_anthropic_turns = True`

### OpenRouter + Gemini models

- `sanitize_thought_signatures = { allow_base64_only: True, include_camel_case: True }`
  — strip leaked thought signatures from OpenRouter-proxied Gemini responses
- `sanitize_mode = "full"`

### Antigravity Claude (Google Vertex-hosted Anthropic models)

- `preserve_signatures = True` — preserve thinking blocks
- `normalize_antigravity_thinking_blocks = True`

### OpenAI (`openai`, `openai-codex`)

- `sanitize_mode = "images-only"` — minimal sanitization
- All other fixups disabled

---

## `resolve_transcript_policy()` usage

```python
from openclaw.agents.history_utils import resolve_transcript_policy

policy = resolve_transcript_policy(
    model_api="google-ai-studio",
    provider="google",
    model_id="gemini-2.0-flash",
)
# policy.apply_google_turn_ordering == True
# policy.sanitize_tool_call_ids == True
```

---

## Python implementation

- `openclaw/agents/history_utils.py`:
  - `TranscriptPolicy` dataclass
  - `SanitizeThoughtSignaturesConfig` dataclass
  - `resolve_transcript_policy(model_api, provider, model_id) -> TranscriptPolicy`
  - `sanitize_session_history(messages, policy=None) -> list`
