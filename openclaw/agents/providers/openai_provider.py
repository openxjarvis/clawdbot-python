"""
OpenAI provider implementation — aligned with TS openai-completions.ts

Supports:
- Native OpenAI API
- Any OpenAI-compatible API via base_url (xAI, DeepSeek, Mistral, Zhipu/ZAI, etc.)
- _detect_compat(): mirrors TS detectCompat() / getCompat() logic
"""

import logging
import os
from collections.abc import AsyncIterator

from openai import AsyncOpenAI

from .base import LLMMessage, LLMProvider, LLMResponse

logger = logging.getLogger(__name__)


class OpenAIProvider(LLMProvider):
    """
    OpenAI provider with OpenAI-compatible API support.

    _detect_compat() mirrors TS detectCompat() in openai-completions.ts:
    - Detects xAI, DeepSeek, Mistral, ZAI and adjusts API behavior accordingly.
    - Returned compat dict controls max_tokens field name, store/developer_role support, etc.

    Example:
        # Native OpenAI
        provider = OpenAIProvider("gpt-4o", api_key="sk-...")

        # xAI Grok
        provider = OpenAIProvider("grok-3", api_key="xai-...", base_url="https://api.x.ai/v1",
                                  provider_name_override="xai")

        # DeepSeek
        provider = OpenAIProvider("deepseek-chat", api_key="...",
                                  base_url="https://api.deepseek.com",
                                  provider_name_override="deepseek")
    """

    def __init__(self, *args, provider_name_override: str | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self._provider_name_override = provider_name_override
        self._compat: dict | None = None

    @property
    def provider_name(self) -> str:
        return self._provider_name_override or "openai"

    def _detect_compat(self) -> dict:
        """Mirror TS detectCompat() / getCompat() logic from openai-completions.ts.

        Detects provider-specific API quirks based on provider name and base_url,
        and returns a compat dict that controls how requests are built.

        Returns:
            dict with keys:
                supports_store (bool)           — can use 'store' param
                supports_developer_role (bool)  — can use 'developer' role
                supports_reasoning_effort (bool)— can use 'reasoning_effort' param
                max_tokens_field (str)          — "max_tokens" or "max_completion_tokens"
                requires_tool_result_name (bool)— must include name in tool result
                requires_thinking_as_text (bool)— thinking tokens must be text role
        """
        if self._compat is not None:
            return self._compat

        provider = (self._provider_name_override or "").lower()
        base_url = (self.base_url or "").lower()

        is_xai = provider == "xai" or "api.x.ai" in base_url
        is_deepseek = provider == "deepseek" or "deepseek.com" in base_url
        is_mistral = provider == "mistral" or "mistral.ai" in base_url
        is_zai = provider in ("zai", "zhipu") or "api.z.ai" in base_url or "bigmodel.cn" in base_url
        is_groq = provider == "groq" or "api.groq.com" in base_url
        is_moonshot = provider == "moonshot" or "moonshot.cn" in base_url or "api.moonshot.ai" in base_url
        is_together = provider == "together" or "together.ai" in base_url
        is_openrouter = provider == "openrouter" or "openrouter.ai" in base_url
        is_huggingface = provider == "huggingface" or "huggingface.co" in base_url
        is_cerebras = provider == "cerebras" or "cerebras.ai" in base_url
        is_non_standard = any([
            is_xai, is_deepseek, is_mistral, is_zai, is_groq,
            is_moonshot, is_together, is_openrouter, is_huggingface, is_cerebras,
        ])

        self._compat = {
            "supports_store": not is_non_standard,
            "supports_developer_role": not is_non_standard,
            "supports_reasoning_effort": not is_xai and not is_zai and not is_non_standard,
            "max_tokens_field": "max_tokens" if is_mistral else "max_completion_tokens",
            "requires_tool_result_name": is_mistral,
            "requires_thinking_as_text": is_mistral,
        }
        return self._compat

    def get_client(self) -> AsyncOpenAI:
        """Get OpenAI client"""
        if self._client is None:
            api_key = self.api_key or os.getenv("OPENAI_API_KEY", "not-needed")

            kwargs: dict = {"api_key": api_key}
            if self.base_url:
                kwargs["base_url"] = self.base_url

            self._client = AsyncOpenAI(**kwargs)

        return self._client

    async def stream(
        self,
        messages: list[LLMMessage],
        tools: list[dict] | None = None,
        max_tokens: int = 4096,
        **kwargs,
    ) -> AsyncIterator[LLMResponse]:
        """Stream responses from OpenAI / OpenAI-compatible API"""
        client = self.get_client()
        compat = self._detect_compat()

        # Convert messages to OpenAI format
        openai_messages = []
        for msg in messages:
            openai_messages.append({"role": msg.role, "content": msg.content})

        try:
            # Build request parameters using compat-aware field names
            max_tokens_field = compat.get("max_tokens_field", "max_completion_tokens")
            params: dict = {
                "model": self.model,
                "messages": openai_messages,
                max_tokens_field: max_tokens,
                "stream": True,
                **kwargs,
            }

            # Only add store/developer-role params for standard OpenAI
            if not compat["supports_store"]:
                params.pop("store", None)

            # Add tools if provided
            if tools:
                params["tools"] = tools

            # Start streaming
            stream = await client.chat.completions.create(**params)

            # Track tool calls
            tool_calls_buffer: dict = {}

            async for chunk in stream:
                if not chunk.choices:
                    continue

                choice = chunk.choices[0]
                delta = choice.delta

                # Text content
                if delta.content:
                    yield LLMResponse(type="text_delta", content=delta.content)

                # Tool calls
                if delta.tool_calls:
                    for tool_call in delta.tool_calls:
                        idx = tool_call.index

                        if idx not in tool_calls_buffer:
                            tool_calls_buffer[idx] = {
                                "id": tool_call.id or f"call_{idx}",
                                "name": "",
                                "arguments": "",
                            }

                        if tool_call.function and tool_call.function.name:
                            tool_calls_buffer[idx]["name"] = tool_call.function.name

                        if tool_call.function and tool_call.function.arguments:
                            tool_calls_buffer[idx]["arguments"] += tool_call.function.arguments

                # Check if done
                if choice.finish_reason:
                    if tool_calls_buffer:
                        import json

                        tool_calls = []
                        for tc in tool_calls_buffer.values():
                            try:
                                args = json.loads(tc["arguments"]) if tc["arguments"] else {}
                            except json.JSONDecodeError:
                                args = {}

                            tc_entry: dict = {"id": tc["id"], "name": tc["name"], "arguments": args}
                            # Mistral requires name in tool result messages
                            if compat.get("requires_tool_result_name"):
                                tc_entry["result_name"] = tc["name"]

                            tool_calls.append(tc_entry)

                        yield LLMResponse(type="tool_call", content=None, tool_calls=tool_calls)

                    yield LLMResponse(type="done", content=None, finish_reason=choice.finish_reason)

        except Exception as e:
            logger.error(f"OpenAI streaming error: {e}")
            yield LLMResponse(type="error", content=str(e))
