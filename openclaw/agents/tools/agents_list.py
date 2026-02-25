"""
Agents list tool for discovering available agents for spawning.

Aligned with TypeScript openclaw/src/agents/tools/agents-list-tool.ts
"""
from __future__ import annotations

import json
import logging
from typing import Any

from .base import AgentTool, ToolResult

logger = logging.getLogger(__name__)


class AgentsListTool(AgentTool):
    """
    List agent ids allowed for sessions_spawn.
    
    Matches TypeScript createAgentsListTool() from agents-list-tool.ts
    """
    
    def __init__(
        self,
        agent_id: str | None = None,
        config: dict[str, Any] | None = None,
    ):
        """
        Initialize agents list tool.
        
        Args:
            agent_id: Current agent ID
            config: OpenClaw configuration
        """
        super().__init__()
        self.name = "agents_list"
        self.description = "List agent ids allowed for sessions_spawn"
        self.agent_id = agent_id or "main"
        self.config = config or {}
    
    def get_schema(self) -> dict[str, Any]:
        """Get tool schema (no parameters needed)"""
        return {
            "type": "object",
            "properties": {},
        }
    
    async def execute(self, params: dict[str, Any]) -> ToolResult:
        """
        Execute agents list action.
        
        Returns list of agent IDs that can be spawned from current agent.
        """
        try:
            # Get subagents allowlist for current agent
            agents_config = self.config.get("agents", {})
            agents_list = agents_config.get("list", [])
            
            # Find current agent config
            current_agent_config = None
            for agent_entry in agents_list:
                if agent_entry.get("id") == self.agent_id:
                    current_agent_config = agent_entry
                    break
            
            # Get allowlist
            allow_agents = []
            allow_any = False
            
            if current_agent_config:
                subagents_config = current_agent_config.get("subagents", {})
                allow_agents = subagents_config.get("allowAgents", [])
                
                # Check for wildcard
                if "*" in allow_agents:
                    allow_any = True
                    # List all configured agents
                    allow_agents = [
                        agent_entry.get("id")
                        for agent_entry in agents_list
                        if agent_entry.get("id")
                    ]
            else:
                # Default: allow spawning all configured agents
                allow_any = True
                allow_agents = [
                    agent_entry.get("id")
                    for agent_entry in agents_list
                    if agent_entry.get("id")
                ]
            
            result = {
                "agents": allow_agents,
                "allowAny": allow_any,
            }
            
            return ToolResult(
                success=True,
                content=json.dumps(result, indent=2),
                metadata=result,
            )
        
        except Exception as e:
            logger.error(f"Agents list tool error: {e}", exc_info=True)
            return ToolResult(
                success=False,
                content="",
                error=str(e),
            )


def create_agents_list_tool(
    agent_id: str | None = None,
    config: dict[str, Any] | None = None,
) -> AgentsListTool:
    """
    Create agents list tool instance.
    
    Matches TS createAgentsListTool() from agents-list-tool.ts
    
    Args:
        agent_id: Current agent ID
        config: OpenClaw configuration
        
    Returns:
        AgentsListTool instance
    """
    return AgentsListTool(agent_id=agent_id, config=config)
