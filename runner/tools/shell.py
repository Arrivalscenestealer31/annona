"""
Shell Tool

Tool per eseguire comandi shell.
"""
import subprocess
from typing import Dict, Any
from loguru import logger

from .base import Tool


class ShellTool(Tool):
    """Tool per eseguire comandi shell"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(
            name="shell",
            description="Execute shell commands",
            parameters={
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "Shell command to execute"
                    },
                    "timeout": {
                        "type": "number",
                        "description": "Timeout in seconds (default: 60)"
                    },
                    "cwd": {
                        "type": "string",
                        "description": "Working directory"
                    }
                },
                "required": ["command"]
            }
        )
        self.config = config
        self.default_timeout = config.get("tools", {}).get("shell", {}).get("timeout", 60)
    
    def execute(self, command: str, timeout: int = None, cwd: str = None, **kwargs) -> Dict[str, Any]:
        """Esegue un comando shell"""
        logger.info(f"Executing shell command: {command}")
        
        timeout = timeout or self.default_timeout
        
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=cwd
            )
            
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode
            }
        
        except subprocess.TimeoutExpired:
            logger.error(f"Command timeout after {timeout}s: {command}")
            return {
                "success": False,
                "error": f"Command timeout after {timeout}s",
                "returncode": -1
            }
        
        except Exception as e:
            logger.error(f"Command execution error: {e}")
            return {
                "success": False,
                "error": str(e),
                "returncode": -1
            }
