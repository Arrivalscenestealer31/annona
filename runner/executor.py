"""
Task Executor

Esegue i task usando tools e AI.
"""
from typing import Dict, Any, Optional
from loguru import logger

from .tools.registry import ToolRegistry
from .permissions.manager import PermissionManager
from .ai_client import AIClient


class TaskExecutor:
    """Executor per i task"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        
        # Tool registry
        self.tools = ToolRegistry(config)
        
        # Permission manager
        self.permissions = PermissionManager(config)
        
        # AI client
        self.ai_client = AIClient(config)
    
    def execute(self, task: Dict[str, Any]) -> Any:
        """
        Esegue un task
        
        Args:
            task: Task object con tipo, payload, etc.
            
        Returns:
            Risultato dell'esecuzione
        """
        task_type = task.get("type", "command")
        payload = task.get("payload", {})
        
        logger.info(f"Executing task type: {task_type}")
        
        # Routing per tipo di task
        if task_type == "command":
            return self._execute_command(payload)
        
        elif task_type == "tool":
            return self._execute_tool(payload)
        
        elif task_type == "ai_task":
            return self._execute_ai_task(payload)
        
        elif task_type == "workflow":
            return self._execute_workflow(payload)
        
        else:
            raise ValueError(f"Unknown task type: {task_type}")
    
    def _execute_command(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Esegue un comando semplice"""
        command = payload.get("command")
        
        if not command:
            raise ValueError("No command provided")
        
        logger.info(f"Executing command: {command}")
        
        # Usa AI per interpretare e eseguire il comando
        result = self.ai_client.execute_command(command, self.tools)
        
        return {
            "type": "command_result",
            "command": command,
            "result": result
        }
    
    def _execute_tool(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Esegue un tool specifico"""
        tool_name = payload.get("tool")
        tool_args = payload.get("args", {})
        
        if not tool_name:
            raise ValueError("No tool specified")
        
        # Verifica permessi
        if not self.permissions.check_tool_permission(tool_name, tool_args):
            raise PermissionError(f"Permission denied for tool: {tool_name}")
        
        # Esegui il tool
        tool = self.tools.get_tool(tool_name)
        result = tool.execute(**tool_args)
        
        return {
            "type": "tool_result",
            "tool": tool_name,
            "result": result
        }
    
    def _execute_ai_task(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Esegue un task che richiede ragionamento AI"""
        prompt = payload.get("prompt")
        context = payload.get("context", {})
        
        if not prompt:
            raise ValueError("No prompt provided")
        
        logger.info(f"Executing AI task: {prompt}")
        
        # Usa AI per ragionare ed eseguire
        result = self.ai_client.reason_and_execute(
            prompt=prompt,
            context=context,
            tools=self.tools,
            permissions=self.permissions
        )
        
        return {
            "type": "ai_result",
            "prompt": prompt,
            "result": result
        }
    
    def _execute_workflow(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Esegue un workflow multi-step"""
        steps = payload.get("steps", [])
        
        if not steps:
            raise ValueError("No workflow steps provided")
        
        logger.info(f"Executing workflow with {len(steps)} steps")
        
        results = []
        context = {}
        
        for i, step in enumerate(steps):
            logger.info(f"Executing step {i+1}/{len(steps)}")
            
            # Ogni step è un task
            step_result = self.execute(step)
            results.append(step_result)
            
            # Passa il risultato come context al prossimo step
            context[f"step_{i}_result"] = step_result
            
            # Opzionale: permetti allo step di aggiornare il context
            if "context_update" in step:
                context.update(step["context_update"])
        
        return {
            "type": "workflow_result",
            "steps": len(steps),
            "results": results
        }
