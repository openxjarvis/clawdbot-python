"""Reply prefix context builder for channels — mirrors src/channels/reply-prefix.ts"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class ReplyPrefixContextBundle:
    prefix_context: dict
    response_prefix: str | None
    response_prefix_context_provider: Callable[[], dict]
    on_model_selected: Callable[[Any], None]


def create_reply_prefix_context(
    *,
    cfg: Any,
    agent_id: str,
    channel: str | None = None,
    account_id: str | None = None,
) -> ReplyPrefixContextBundle:
    from openclaw.agents.identity import resolve_identity_name, resolve_effective_messages_config
    from openclaw.auto_reply.reply.response_prefix import extract_short_model_name

    prefix_context: dict = {
        "identityName": resolve_identity_name(cfg, agent_id),
    }

    def on_model_selected(ctx: Any) -> None:
        provider = getattr(ctx, "provider", None) if not isinstance(ctx, dict) else ctx.get("provider")
        model = getattr(ctx, "model", None) if not isinstance(ctx, dict) else ctx.get("model")
        think_level = getattr(ctx, "think_level", None) or (ctx.get("thinkLevel") if isinstance(ctx, dict) else None)
        prefix_context["provider"] = provider
        prefix_context["model"] = extract_short_model_name(model or "")
        prefix_context["modelFull"] = f"{provider}/{model}" if provider and model else (model or "")
        prefix_context["thinkingLevel"] = think_level or "off"

    messages_cfg = resolve_effective_messages_config(cfg, agent_id, channel=channel, account_id=account_id)
    response_prefix = (messages_cfg or {}).get("responsePrefix")

    return ReplyPrefixContextBundle(
        prefix_context=prefix_context,
        response_prefix=response_prefix,
        response_prefix_context_provider=lambda: prefix_context,
        on_model_selected=on_model_selected,
    )


def create_reply_prefix_options(
    *,
    cfg: Any,
    agent_id: str,
    channel: str | None = None,
    account_id: str | None = None,
) -> dict:
    bundle = create_reply_prefix_context(cfg=cfg, agent_id=agent_id, channel=channel, account_id=account_id)
    return {
        "responsePrefix": bundle.response_prefix,
        "responsePrefixContextProvider": bundle.response_prefix_context_provider,
        "onModelSelected": bundle.on_model_selected,
    }
