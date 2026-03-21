"""
Tool Registry

Registry di tutti i tools disponibili per il runner.
"""
from typing import Dict, Any, List, Callable
from loguru import logger

from .base import Tool
from .filesystem import FilesystemTool
from .shell import ShellTool
from .browser import BrowserTool


class ToolRegistry:
    """Registry di tools"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.tools: Dict[str, Tool] = {}
        
        # Registra i tools abilitati
        enabled_tools = config.get("tools", {}).get("enabled", [])
        self._register_builtin_tools(enabled_tools)
    
    def _register_builtin_tools(self, enabled: List[str]):
        """Registra i tools built-in"""
        if "filesystem" in enabled:
            self.register(FilesystemTool(self.config))
        
        if "shell" in enabled:
            self.register(ShellTool(self.config))
        
        if "browser" in enabled:
            self.register(BrowserTool(self.config))
    
    def register(self, tool: Tool):
        """Registra un nuovo tool"""
        self.tools[tool.name] = tool
        logger.debug(f"Registered tool: {tool.name}")
    
    def get_tool(self, name: str) -> Tool:
        """Recupera un tool per nome"""
        if name not in self.tools:
            raise ValueError(f"Tool not found: {name}")
        return self.tools[name]
    
    def list_tools(self) -> List[str]:
        """Lista tutti i tools disponibili"""
        return list(self.tools.keys())
    
    def get_tool_schema(self, name: str) -> Dict[str, Any]:
        """Recupera lo schema di un tool per l'AI"""
        tool = self.get_tool(name)
        return {
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.parameters
        }
    
    def get_all_schemas(self) -> List[Dict[str, Any]]:
        """Recupera gli schemi di tutti i tools"""
        return [self.get_tool_schema(name) for name in self.tools.keys()]
