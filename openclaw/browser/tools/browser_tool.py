"""Browser tool - agent interface to browser control server.

Aligned with TypeScript openclaw/src/agents/tools/browser-tool.ts

Provides comprehensive browser control:
- Profile management (profiles, create-profile, delete-profile, reset-profile)
- Tab management (tabs, open, focus, close)
- Snapshot (aria/ai formats with refs support)
- Screenshot (with ref/element support)
- Actions (act with multiple kinds)
- File upload and dialog handling
- Console message capture
- Node routing (sandbox/host/node)
"""
from __future__ import annotations

import json
import logging
from typing import Any, Literal

from openclaw.agents.tools.base import AgentTool, ToolResult

logger = logging.getLogger(__name__)


# Action types matching TS browser-tool.schema.ts lines 18-35
BROWSER_TOOL_ACTIONS = [
    "status",
    "start",
    "stop",
    "profiles",
    "tabs",
    "open",
    "focus",
    "close",
    "snapshot",
    "screenshot",
    "navigate",
    "console",
    "pdf",
    "upload",
    "dialog",
    "act",
]

BROWSER_TARGETS = ["sandbox", "host", "node"]
BROWSER_SNAPSHOT_FORMATS = ["aria", "ai"]
BROWSER_SNAPSHOT_MODES = ["efficient"]
BROWSER_SNAPSHOT_REFS = ["role", "aria"]
BROWSER_IMAGE_TYPES = ["png", "jpeg"]

# Act kinds matching TS lines 4-16
BROWSER_ACT_KINDS = [
    "click",
    "type",
    "press",
    "hover",
    "drag",
    "select",
    "fill",
    "resize",
    "wait",
    "evaluate",
    "close",
]


class UnifiedBrowserTool(AgentTool):
    """
    Browser tool fully aligned with TypeScript implementation.

    Matches openclaw/src/agents/tools/browser-tool.ts
    """

    def __init__(
        self,
        sandbox_bridge_url: str | None = None,
        allow_host_control: bool | None = None,
        # Legacy param — kept for backwards compatibility
        headless: bool = True,
    ):
        super().__init__()
        self.name = "browser"
        self.sandbox_bridge_url = sandbox_bridge_url
        self.allow_host_control = allow_host_control

        # Build description matching TS lines 231-242
        target_default = "sandbox" if sandbox_bridge_url else "host"
        host_hint = (
            "Host target blocked by policy."
            if allow_host_control is False
            else "Host target allowed."
        )

        self.description = " ".join([
            "Control the browser via OpenClaw's browser control server (status/start/stop/profiles/tabs/open/snapshot/screenshot/actions).",
            'Profiles: use profile="chrome" for Chrome extension relay takeover (your existing Chrome tabs). Use profile="openclaw" for the isolated openclaw-managed browser.',
            'If the user mentions the Chrome extension / Browser Relay / toolbar button / "attach tab", ALWAYS use profile="chrome" (do not ask which profile).',
            'When a node-hosted browser proxy is available, the tool may auto-route to it. Pin a node with node=<id|name> or target="node".',
            "Chrome extension relay needs an attached tab: user must click the OpenClaw Browser Relay toolbar icon on the tab (badge ON). If no tab is connected, ask them to attach it.",
            "When using refs from snapshot (e.g. e12), keep the same tab: prefer passing targetId from the snapshot response into subsequent actions (act/click/type/etc).",
            'For stable, self-resolving refs across calls, use snapshot with refs="aria" (Playwright aria-ref ids). Default refs="role" are role+name-based.',
            "Use snapshot+act for UI automation. Avoid act:wait by default; use only in exceptional cases when no reliable UI state exists.",
            f"target selects browser location (sandbox|host|node). Default: {target_default}.",
            host_hint,
        ])

    def get_schema(self) -> dict[str, Any]:
        """Get tool schema matching TS BrowserToolSchema (browser-tool.schema.ts lines 83-112)"""
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": BROWSER_TOOL_ACTIONS,
                    "description": "Browser action to perform",
                },
                "target": {
                    "type": "string",
                    "enum": BROWSER_TARGETS,
                    "description": "Browser target location (sandbox/host/node)",
                },
                "node": {
                    "type": "string",
                    "description": "Node id or name (for target=node)",
                },
                "profile": {
                    "type": "string",
                    "description": "Browser profile name",
                },
                "targetUrl": {
                    "type": "string",
                    "description": "URL to navigate/open",
                },
                "targetId": {
                    "type": "string",
                    "description": "Tab target ID",
                },
                "limit": {
                    "type": "number",
                    "description": "Limit for results",
                },
                "maxChars": {
                    "type": "number",
                    "description": "Maximum characters for snapshot",
                },
                "mode": {
                    "type": "string",
                    "enum": BROWSER_SNAPSHOT_MODES,
                    "description": "Snapshot mode",
                },
                "snapshotFormat": {
                    "type": "string",
                    "enum": BROWSER_SNAPSHOT_FORMATS,
                    "description": "Snapshot format (aria/ai)",
                },
                "refs": {
                    "type": "string",
                    "enum": BROWSER_SNAPSHOT_REFS,
                    "description": "Reference type for snapshot (role/aria)",
                },
                "interactive": {
                    "type": "boolean",
                    "description": "Include interactive elements only",
                },
                "compact": {
                    "type": "boolean",
                    "description": "Compact snapshot output",
                },
                "depth": {
                    "type": "number",
                    "description": "Maximum depth for aria tree",
                },
                "selector": {
                    "type": "string",
                    "description": "CSS selector for scoping snapshot",
                },
                "frame": {
                    "type": "string",
                    "description": "Frame selector",
                },
                "labels": {
                    "type": "boolean",
                    "description": "Generate labels for AI snapshot",
                },
                "fullPage": {
                    "type": "boolean",
                    "description": "Full page screenshot",
                },
                "ref": {
                    "type": "string",
                    "description": "Element ref from snapshot",
                },
                "element": {
                    "type": "string",
                    "description": "CSS selector for element",
                },
                "type": {
                    "type": "string",
                    "enum": BROWSER_IMAGE_TYPES,
                    "description": "Image type (png/jpeg)",
                },
                "level": {
                    "type": "string",
                    "description": "Console message level filter",
                },
                "paths": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "File paths for upload",
                },
                "inputRef": {
                    "type": "string",
                    "description": "Input element ref for upload",
                },
                "timeoutMs": {
                    "type": "number",
                    "description": "Timeout in milliseconds",
                },
                "accept": {
                    "type": "boolean",
                    "description": "Accept dialog (true) or dismiss (false)",
                },
                "promptText": {
                    "type": "string",
                    "description": "Text to enter in dialog prompt",
                },
                "request": {
                    "type": "object",
                    "description": "Browser act request object",
                    "properties": {
                        "kind": {
                            "type": "string",
                            "enum": BROWSER_ACT_KINDS,
                            "description": "Action kind",
                        },
                        "targetId": {"type": "string"},
                        "ref": {"type": "string"},
                        "doubleClick": {"type": "boolean"},
                        "button": {"type": "string"},
                        "modifiers": {"type": "array", "items": {"type": "string"}},
                        "text": {"type": "string"},
                        "submit": {"type": "boolean"},
                        "slowly": {"type": "boolean"},
                        "key": {"type": "string"},
                        "startRef": {"type": "string"},
                        "endRef": {"type": "string"},
                        "values": {"type": "array", "items": {"type": "string"}},
                        "fields": {"type": "array", "items": {"type": "string"}},
                        "width": {"type": "number"},
                        "height": {"type": "number"},
                        "timeMs": {"type": "number"},
                        "textGone": {"type": "string"},
                        "fn": {"type": "string"},
                    },
                },
            },
            "required": ["action"],
        }

    async def execute(self, params: dict[str, Any]) -> ToolResult:
        """Execute browser action. Matches TypeScript browser-tool.ts execute logic."""
        action = params.get("action", "")

        if not action:
            return ToolResult(success=False, content="", error="action required")

        try:
            # Resolve target and routing (matching TS lines 246-296)
            profile = params.get("profile")
            requested_node = params.get("node")
            target = params.get("target")

            if requested_node and target and target != "node":
                return ToolResult(
                    success=False,
                    content="",
                    error='node is only supported with target="node".',
                )

            # Auto-select host for chrome profile (TS lines 255-258)
            if not target and not requested_node and profile == "chrome":
                target = "host"

            # Resolve node target
            node_target = await self._resolve_browser_node_target(
                requested_node=requested_node,
                target=target,
                sandbox_bridge_url=self.sandbox_bridge_url,
            )

            # Resolve base URL
            resolved_target = None if target == "node" else target
            base_url = (
                None
                if node_target
                else self._resolve_browser_base_url(
                    target=resolved_target,
                    sandbox_bridge_url=self.sandbox_bridge_url,
                    allow_host_control=self.allow_host_control,
                )
            )

            # Route to proxy if node target exists
            if node_target:
                return await self._execute_via_proxy(
                    action=action,
                    params=params,
                    node_target=node_target,
                    profile=profile,
                )

            # Execute locally
            return await self._execute_local(
                action=action,
                params=params,
                base_url=base_url,
                profile=profile,
            )

        except Exception as e:
            logger.error(f"Browser tool error: {e}", exc_info=True)
            return ToolResult(success=False, content="", error=str(e))

    async def _resolve_browser_node_target(
        self,
        requested_node: str | None,
        target: str | None,
        sandbox_bridge_url: str | None,
    ) -> dict[str, str] | None:
        """Resolve browser node target. Matches TS resolveBrowserNodeTarget() lines 81-140"""
        from openclaw.config.loader import load_config

        cfg = load_config(as_dict=True)
        policy = cfg.get("gateway", {}).get("nodes", {}).get("browser", {})
        mode = policy.get("mode", "auto")

        if mode == "off":
            if target == "node" or requested_node:
                raise RuntimeError(
                    "Node browser proxy is disabled (gateway.nodes.browser.mode=off)."
                )
            return None

        if sandbox_bridge_url and target != "node" and not requested_node:
            return None

        if target and target != "node":
            return None

        if mode == "manual" and target != "node" and not requested_node:
            return None

        nodes = await self._list_nodes()
        browser_nodes = [
            node for node in nodes
            if node.get("connected") and self._is_browser_node(node)
        ]

        if not browser_nodes:
            if target == "node" or requested_node:
                raise RuntimeError("No connected browser-capable nodes.")
            return None

        requested = requested_node or policy.get("node")
        if requested:
            node_id = self._resolve_node_id_from_list(browser_nodes, requested)
            node = next((n for n in browser_nodes if n.get("nodeId") == node_id), None)
            label = (
                node.get("displayName") or node.get("remoteIp") or node_id
                if node else node_id
            )
            return {"nodeId": node_id, "label": label}

        if target == "node":
            if len(browser_nodes) == 1:
                node = browser_nodes[0]
                return {
                    "nodeId": node["nodeId"],
                    "label": node.get("displayName") or node.get("remoteIp") or node["nodeId"],
                }
            raise RuntimeError(
                f"Multiple browser-capable nodes connected ({len(browser_nodes)}). "
                "Set gateway.nodes.browser.node or pass node=<id>."
            )

        if mode == "manual":
            return None

        if len(browser_nodes) == 1:
            node = browser_nodes[0]
            return {
                "nodeId": node["nodeId"],
                "label": node.get("displayName") or node.get("remoteIp") or node["nodeId"],
            }

        return None

    def _is_browser_node(self, node: dict[str, Any]) -> bool:
        """Check if node has browser capability (TS lines 75-79)"""
        caps = node.get("caps", [])
        commands = node.get("commands", [])
        return "browser" in caps or "browser.proxy" in commands

    def _resolve_node_id_from_list(
        self,
        nodes: list[dict[str, Any]],
        requested: str,
    ) -> str:
        """Resolve node ID from list"""
        for node in nodes:
            if node.get("nodeId") == requested:
                return node["nodeId"]
        for node in nodes:
            if node.get("displayName") == requested:
                return node["nodeId"]
        if nodes:
            return nodes[0]["nodeId"]
        raise RuntimeError(f"Node not found: {requested}")

    async def _list_nodes(self) -> list[dict[str, Any]]:
        """List nodes via gateway RPC. Mirrors TS listNodes() from nodes-utils.ts."""
        from openclaw.agents.tools.nodes_utils import list_nodes
        return await list_nodes({})

    def _resolve_browser_base_url(
        self,
        target: Literal["sandbox", "host"] | None,
        sandbox_bridge_url: str | None,
        allow_host_control: bool | None,
    ) -> str | None:
        """Resolve browser base URL. Matches TS resolveBrowserBaseUrl() lines 191-219"""
        from openclaw.config.loader import load_config

        cfg = load_config(as_dict=True)
        browser_config = cfg.get("browser", {})
        enabled = browser_config.get("enabled", False)

        normalized_sandbox = (sandbox_bridge_url or "").strip().rstrip("/")
        resolved_target = target or ("sandbox" if normalized_sandbox else "host")

        if resolved_target == "sandbox":
            if not normalized_sandbox:
                raise RuntimeError(
                    'Sandbox browser is unavailable. Enable agents.defaults.sandbox.browser.enabled '
                    'or use target="host" if allowed.'
                )
            return normalized_sandbox

        if allow_host_control is False:
            raise RuntimeError("Host browser control is disabled by sandbox policy.")

        if not enabled:
            raise RuntimeError(
                "Browser control is disabled. Set browser.enabled=true in ~/.openclaw/openclaw.json."
            )

        return None

    async def _execute_local(
        self,
        action: str,
        params: dict[str, Any],
        base_url: str | None,
        profile: str | None,
    ) -> ToolResult:
        """Execute browser action locally (host or sandbox)."""
        try:
            from openclaw.browser import client
        except ImportError:
            return ToolResult(success=False, content="", error="Browser client not available")

        if action == "status":
            status = await client.browser_status(base_url, profile=profile)
            return ToolResult(success=True, content=json.dumps(status, indent=2), metadata=status)

        elif action == "start":
            await client.browser_start(base_url, profile=profile)
            status = await client.browser_status(base_url, profile=profile)
            return ToolResult(success=True, content=json.dumps(status, indent=2), metadata=status)

        elif action == "stop":
            await client.browser_stop(base_url, profile=profile)
            status = await client.browser_status(base_url, profile=profile)
            return ToolResult(success=True, content=json.dumps(status, indent=2), metadata=status)

        elif action == "profiles":
            profiles = await client.browser_profiles(base_url)
            return ToolResult(
                success=True,
                content=json.dumps({"profiles": profiles}, indent=2),
                metadata={"profiles": profiles},
            )

        elif action == "tabs":
            tabs = await client.browser_tabs(base_url, profile=profile)
            wrapped = self._wrap_browser_external_json(kind="tabs", payload={"tabs": tabs}, include_warning=False)
            return ToolResult(
                success=True,
                content=wrapped["wrapped_text"],
                metadata={**wrapped["safe_details"], "tabCount": len(tabs)},
            )

        elif action == "open":
            target_url = params.get("targetUrl")
            if not target_url:
                return ToolResult(success=False, content="", error="targetUrl required")
            result = await client.browser_open_tab(base_url, target_url, profile=profile)
            return ToolResult(success=True, content=json.dumps(result, indent=2), metadata=result)

        elif action == "focus":
            target_id = params.get("targetId")
            if not target_id:
                return ToolResult(success=False, content="", error="targetId required")
            await client.browser_focus_tab(base_url, target_id, profile=profile)
            return ToolResult(success=True, content=json.dumps({"ok": True}, indent=2), metadata={"ok": True})

        elif action == "close":
            target_id = params.get("targetId")
            if target_id:
                await client.browser_close_tab(base_url, target_id, profile=profile)
            else:
                await client.browser_act(base_url, {"kind": "close"}, profile=profile)
            return ToolResult(success=True, content=json.dumps({"ok": True}, indent=2), metadata={"ok": True})

        elif action == "snapshot":
            return await self._handle_snapshot(params, base_url, profile)

        elif action == "screenshot":
            return await self._handle_screenshot(params, base_url, profile)

        elif action == "navigate":
            target_url = params.get("targetUrl")
            if not target_url:
                return ToolResult(success=False, content="", error="targetUrl required")
            target_id = params.get("targetId")
            result = await client.browser_navigate(base_url, url=target_url, target_id=target_id, profile=profile)
            return ToolResult(success=True, content=json.dumps(result, indent=2), metadata=result)

        elif action == "console":
            level = params.get("level")
            target_id = params.get("targetId")
            result = await client.browser_console_messages(base_url, level=level, target_id=target_id, profile=profile)
            wrapped = self._wrap_browser_external_json(kind="console", payload=result, include_warning=False)
            return ToolResult(
                success=True,
                content=wrapped["wrapped_text"],
                metadata={
                    **wrapped["safe_details"],
                    "targetId": result.get("targetId"),
                    "messageCount": len(result.get("messages", [])),
                },
            )

        elif action == "pdf":
            target_id = params.get("targetId")
            result = await client.browser_pdf_save(base_url, target_id=target_id, profile=profile)
            return ToolResult(success=True, content=f"FILE:{result['path']}", metadata=result)

        elif action == "upload":
            raw_paths = params.get("paths", [])
            if not raw_paths:
                return ToolResult(success=False, content="", error="paths required")
            # Validate paths are within upload dir (mirrors TS resolvePathsWithinRoot)
            from openclaw.browser.paths import DEFAULT_UPLOAD_DIR, resolve_paths_within_root
            DEFAULT_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
            path_result = resolve_paths_within_root(
                root_dir=DEFAULT_UPLOAD_DIR,
                requested_paths=[str(p) for p in raw_paths],
                scope_label=f"uploads directory ({DEFAULT_UPLOAD_DIR})",
            )
            if not path_result["ok"]:
                return ToolResult(success=False, content="", error=path_result["error"])  # type: ignore[index]
            normalized_paths = path_result["paths"]  # type: ignore[index]
            result = await client.browser_arm_file_chooser(
                base_url,
                paths=normalized_paths,
                ref=params.get("ref"),
                input_ref=params.get("inputRef"),
                element=params.get("element"),
                target_id=params.get("targetId"),
                timeout_ms=params.get("timeoutMs"),
                profile=profile,
            )
            return ToolResult(success=True, content=json.dumps(result, indent=2), metadata=result)

        elif action == "dialog":
            result = await client.browser_arm_dialog(
                base_url,
                accept=params.get("accept", False),
                prompt_text=params.get("promptText"),
                target_id=params.get("targetId"),
                timeout_ms=params.get("timeoutMs"),
                profile=profile,
            )
            return ToolResult(success=True, content=json.dumps(result, indent=2), metadata=result)

        elif action == "act":
            request = params.get("request")
            if not request or not isinstance(request, dict):
                return ToolResult(success=False, content="", error="request required")
            try:
                result = await client.browser_act(base_url, request, profile=profile)
                return ToolResult(success=True, content=json.dumps(result, indent=2), metadata=result)
            except Exception as err:
                msg = str(err)
                if "404:" in msg and "tab not found" in msg and profile == "chrome":
                    # Fetch tabs to give a better error (mirrors TS lines 787-805)
                    try:
                        tabs = await client.browser_tabs(base_url, profile=profile)
                    except Exception:
                        tabs = []
                    if not tabs:
                        return ToolResult(
                            success=False,
                            content="",
                            error=(
                                "No Chrome tabs are attached via the OpenClaw Browser Relay extension. "
                                "Click the toolbar icon on the tab you want to control (badge ON), then retry."
                            ),
                        )
                    return ToolResult(
                        success=False,
                        content="",
                        error=(
                            "Chrome tab not found (stale targetId?). "
                            'Run action=tabs profile="chrome" and use one of the returned targetIds.'
                        ),
                    )
                raise

        else:
            return ToolResult(success=False, content="", error=f"Unknown action: {action}")

    async def _execute_via_proxy(
        self,
        action: str,
        params: dict[str, Any],
        node_target: dict[str, str],
        profile: str | None,
    ) -> ToolResult:
        """Execute browser action via node proxy."""
        method = "GET"
        path = "/"
        query: dict[str, Any] = {}
        body: dict[str, Any] | None = None

        if action == "status":
            path = "/"
        elif action == "start":
            method, path = "POST", "/start"
        elif action == "stop":
            method, path = "POST", "/stop"
        elif action == "profiles":
            path = "/profiles"
        elif action == "tabs":
            path = "/tabs"
        elif action == "open":
            method, path = "POST", "/tabs/open"
            body = {"url": params.get("targetUrl")}
        elif action == "focus":
            method, path = "POST", "/tabs/focus"
            body = {"targetId": params.get("targetId")}
        elif action == "close":
            target_id = params.get("targetId")
            if target_id:
                method, path = "DELETE", f"/tabs/{target_id}"
            else:
                method, path = "POST", "/act"
                body = {"kind": "close"}
        elif action == "snapshot":
            path = "/snapshot"
            query = self._build_snapshot_query(params)
        elif action == "screenshot":
            method, path = "POST", "/screenshot"
            body = {
                "targetId": params.get("targetId"),
                "fullPage": params.get("fullPage", False),
                "ref": params.get("ref"),
                "element": params.get("element"),
                "type": params.get("type", "png"),
            }
        elif action == "navigate":
            method, path = "POST", "/navigate"
            body = {"url": params.get("targetUrl"), "targetId": params.get("targetId")}
        elif action == "console":
            path = "/console"
            query = {"level": params.get("level"), "targetId": params.get("targetId")}
        elif action == "pdf":
            method, path = "POST", "/pdf"
            body = {"targetId": params.get("targetId")}
        elif action == "upload":
            method, path = "POST", "/hooks/file-chooser"
            body = {
                "paths": params.get("paths", []),
                "ref": params.get("ref"),
                "inputRef": params.get("inputRef"),
                "element": params.get("element"),
                "targetId": params.get("targetId"),
                "timeoutMs": params.get("timeoutMs"),
            }
        elif action == "dialog":
            method, path = "POST", "/hooks/dialog"
            body = {
                "accept": params.get("accept", False),
                "promptText": params.get("promptText"),
                "targetId": params.get("targetId"),
                "timeoutMs": params.get("timeoutMs"),
            }
        elif action == "act":
            method, path = "POST", "/act"
            body = params.get("request", {})
        else:
            return ToolResult(success=False, content="", error=f"Unknown action: {action}")

        result, _files = await self._call_browser_proxy(
            node_id=node_target["nodeId"],
            method=method,
            path=path,
            query=query,
            body=body,
            timeout_ms=params.get("timeoutMs"),
            profile=profile,
        )

        if action in ["tabs", "console"]:
            wrapped = self._wrap_browser_external_json(kind=action, payload=result, include_warning=False)  # type: ignore[arg-type]
            return ToolResult(success=True, content=wrapped["wrapped_text"], metadata=wrapped["safe_details"])
        elif action == "snapshot":
            return self._format_snapshot_result(result)
        elif action == "screenshot":
            # Use imageResultFromFile so the LLM gets the image block
            # (proxy files already persisted in _call_browser_proxy)
            from openclaw.agents.tools.common_results import image_result_from_file
            path_val = result.get("path", "") if isinstance(result, dict) else ""
            if path_val:
                agent_result = await image_result_from_file(
                    label="browser:screenshot",
                    path=path_val,
                    details=result,
                )
                text_parts = [c.text for c in agent_result.content if hasattr(c, "text")]
                return ToolResult(
                    success=True,
                    content="\n".join(text_parts),
                    metadata=agent_result.details if isinstance(agent_result.details, dict) else result,
                )
            return ToolResult(success=True, content=f"MEDIA:{path_val}", metadata=result)
        else:
            return ToolResult(success=True, content=json.dumps(result, indent=2), metadata=result)

    async def _call_browser_proxy(
        self,
        node_id: str,
        method: str,
        path: str,
        query: dict[str, Any] | None = None,
        body: Any | None = None,
        timeout_ms: int | None = None,
        profile: str | None = None,
    ) -> tuple[Any, list[dict[str, Any]]]:
        """Call browser proxy via gateway node.invoke.

        Mirrors TS callBrowserProxy() from browser-tool.ts.
        Returns (result, files) where files is a list of BrowserProxyFile dicts
        that need to be saved locally via persist_browser_proxy_files().
        """
        from openclaw.browser.proxy_files import (
            persist_browser_proxy_files,
            apply_browser_proxy_paths,
        )

        gateway_timeout_ms = max(1, int(timeout_ms)) if timeout_ms and timeout_ms > 0 else 20000

        payload = await self._call_gateway_tool(
            "node.invoke",
            {
                "nodeId": node_id,
                "command": "browser.proxy",
                "params": {
                    "method": method,
                    "path": path,
                    "query": query,
                    "body": body,
                    "timeoutMs": timeout_ms,
                    "profile": profile,
                },
            },
            timeout_ms=gateway_timeout_ms,
        )

        parsed = payload.get("payload") or (
            json.loads(payload["payloadJSON"]) if payload.get("payloadJSON") else None
        )

        if not parsed or not isinstance(parsed, dict) or "result" not in parsed:
            raise RuntimeError("browser proxy failed")

        result = parsed["result"]
        files: list[dict[str, Any]] = parsed.get("files") or []

        # Persist proxy files and apply path mapping
        mapping = await persist_browser_proxy_files(files)
        if mapping:
            apply_browser_proxy_paths(result, mapping)

        return result, files

    async def _call_gateway_tool(
        self,
        method: str,
        params: dict[str, Any],
        timeout_ms: int = 20000,
    ) -> dict[str, Any]:
        """Call gateway RPC method via WebSocket client.

        Mirrors TS callGatewayTool() from tools/gateway.ts.
        """
        from openclaw.gateway.rpc_client import create_client
        client = await create_client()
        result = await client.call(method, params)
        return result if isinstance(result, dict) else {"payload": result}

    async def _handle_snapshot(
        self,
        params: dict[str, Any],
        base_url: str | None,
        profile: str | None,
    ) -> ToolResult:
        """Handle snapshot action. Matches TS snapshot case lines 439-579"""
        from openclaw.browser import client
        from openclaw.config.loader import load_config

        cfg = load_config(as_dict=True)
        snapshot_defaults = cfg.get("browser", {}).get("snapshotDefaults", {})

        snapshot_format = params.get("snapshotFormat", "ai")
        if snapshot_format not in ["ai", "aria"]:
            snapshot_format = "ai"

        mode_param = params.get("mode")
        mode = (
            "efficient"
            if mode_param == "efficient"
            else (
                "efficient"
                if snapshot_format == "ai" and snapshot_defaults.get("mode") == "efficient"
                else None
            )
        )

        labels = params.get("labels") if isinstance(params.get("labels"), bool) else None
        refs = params.get("refs") if params.get("refs") in ["aria", "role"] else None
        has_max_chars = "maxChars" in params
        target_id = params.get("targetId", "").strip() if params.get("targetId") else None
        limit = params.get("limit") if isinstance(params.get("limit"), (int, float)) else None

        max_chars_param = params.get("maxChars")
        max_chars = (
            int(max_chars_param)
            if isinstance(max_chars_param, (int, float)) and max_chars_param > 0
            else None
        )

        DEFAULT_AI_SNAPSHOT_MAX_CHARS = 50000
        resolved_max_chars = (
            max_chars
            if snapshot_format == "ai" and has_max_chars
            else (
                None
                if snapshot_format == "ai" and mode == "efficient"
                else (DEFAULT_AI_SNAPSHOT_MAX_CHARS if snapshot_format == "ai" else None)
            )
        )

        interactive = params.get("interactive") if isinstance(params.get("interactive"), bool) else None
        compact = params.get("compact") if isinstance(params.get("compact"), bool) else None
        depth = params.get("depth") if isinstance(params.get("depth"), (int, float)) else None
        selector = params.get("selector", "").strip() if params.get("selector") else None
        frame = params.get("frame", "").strip() if params.get("frame") else None

        snapshot = await client.browser_snapshot(
            base_url,
            format=snapshot_format,
            target_id=target_id,
            limit=limit,
            max_chars=resolved_max_chars,
            refs=refs,
            interactive=interactive,
            compact=compact,
            depth=depth,
            selector=selector,
            frame=frame,
            labels=labels,
            mode=mode,
            profile=profile,
        )

        return self._format_snapshot_result(snapshot)

    def _format_snapshot_result(self, snapshot: dict[str, Any]) -> ToolResult:
        """Format snapshot result (TS lines 517-579)"""
        if snapshot.get("format") == "ai":
            extracted_text = snapshot.get("snapshot", "")
            wrapped_snapshot = self._wrap_external_content(extracted_text, source="browser", include_warning=True)

            safe_details = {
                "ok": True,
                "format": snapshot["format"],
                "targetId": snapshot.get("targetId"),
                "url": snapshot.get("url"),
                "truncated": snapshot.get("truncated"),
                "stats": snapshot.get("stats"),
                "refs": len(snapshot.get("refs", {})),
                "labels": snapshot.get("labels"),
                "labelsCount": snapshot.get("labelsCount"),
                "labelsSkipped": snapshot.get("labelsSkipped"),
                "imagePath": snapshot.get("imagePath"),
                "imageType": snapshot.get("imageType"),
                "externalContent": {
                    "untrusted": True,
                    "source": "browser",
                    "kind": "snapshot",
                    "format": "ai",
                    "wrapped": True,
                },
            }

            if snapshot.get("labels") and snapshot.get("imagePath"):
                return ToolResult(
                    success=True,
                    content=f"MEDIA:{snapshot['imagePath']}\n\n{wrapped_snapshot}",
                    metadata=safe_details,
                )

            return ToolResult(success=True, content=wrapped_snapshot, metadata=safe_details)
        else:
            wrapped = self._wrap_browser_external_json(kind="snapshot", payload=snapshot, include_warning=True)
            return ToolResult(
                success=True,
                content=wrapped["wrapped_text"],
                metadata={
                    **wrapped["safe_details"],
                    "format": "aria",
                    "targetId": snapshot.get("targetId"),
                    "url": snapshot.get("url"),
                    "nodeCount": len(snapshot.get("nodes", [])),
                    "externalContent": {
                        "untrusted": True,
                        "source": "browser",
                        "kind": "snapshot",
                        "format": "aria",
                        "wrapped": True,
                    },
                },
            )

    def _build_snapshot_query(self, params: dict[str, Any]) -> dict[str, Any]:
        """Build snapshot query parameters"""
        keys = ["snapshotFormat", "targetId", "limit", "maxChars", "refs", "interactive",
                "compact", "depth", "selector", "frame", "labels", "mode"]
        remap = {"snapshotFormat": "format"}
        return {remap.get(k, k): params[k] for k in keys if k in params}

    async def _handle_screenshot(
        self,
        params: dict[str, Any],
        base_url: str | None,
        profile: str | None,
    ) -> ToolResult:
        """Handle screenshot action. Matches TS screenshot case (browser-tool.ts lines 581-613).

        Uses imageResultFromFile() so the LLM gets the actual image content block
        and channel delivery sends the photo to Telegram/Discord/etc.
        """
        from openclaw.browser import client
        from openclaw.agents.tools.common_results import image_result_from_file

        img_type = "jpeg" if params.get("type") == "jpeg" else "png"
        result = await client.browser_screenshot_action(
            base_url,
            target_id=params.get("targetId"),
            full_page=bool(params.get("fullPage", False)),
            ref=params.get("ref"),
            element=params.get("element"),
            type=img_type,
            profile=profile,
        )

        path = result.get("path", "")
        if path:
            agent_result = await image_result_from_file(
                label="browser:screenshot",
                path=path,
                details=result,
            )
            text_parts = [c.text for c in agent_result.content if hasattr(c, "text")]
            return ToolResult(
                success=True,
                content="\n".join(text_parts),
                metadata=agent_result.details if isinstance(agent_result.details, dict) else result,
            )
        return ToolResult(success=True, content=f"MEDIA:{path}", metadata=result)

    def _wrap_browser_external_json(
        self,
        kind: Literal["snapshot", "console", "tabs"],
        payload: Any,
        include_warning: bool = True,
    ) -> dict[str, Any]:
        """Wrap browser external JSON content. Matches TS wrapBrowserExternalJson()"""
        extracted_text = json.dumps(payload, indent=2)
        wrapped_text = self._wrap_external_content(extracted_text, source="browser", include_warning=include_warning)

        return {
            "wrapped_text": wrapped_text,
            "safe_details": {
                "ok": True,
                "externalContent": {
                    "untrusted": True,
                    "source": "browser",
                    "kind": kind,
                    "wrapped": True,
                },
            },
        }

    def _wrap_external_content(
        self,
        content: str,
        source: str,
        include_warning: bool = True,
    ) -> str:
        """Wrap external content with security markers."""
        if include_warning:
            return (
                f"<<<EXTERNAL_UNTRUSTED_CONTENT>>>\n"
                f"Source: {source}\n\n"
                f"{content}\n\n"
                f"<<<END_EXTERNAL_UNTRUSTED_CONTENT>>>"
            )
        return content

    async def cleanup(self) -> None:
        """Cleanup browser resources"""
        pass


def create_browser_tool(
    sandbox_bridge_url: str | None = None,
    allow_host_control: bool | None = None,
) -> "UnifiedBrowserTool":
    """Create browser tool instance. Matches TS createBrowserTool()"""
    return UnifiedBrowserTool(
        sandbox_bridge_url=sandbox_bridge_url,
        allow_host_control=allow_host_control,
    )
