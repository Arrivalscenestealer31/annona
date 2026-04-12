"""
AI Client

Client AI multi-provider con supporto per:
- Akaion AI Backend
- OpenAI
- Anthropic (Claude)
- Google (Gemini)
- Local (Ollama)
"""
from typing import Dict, Any, List, Optional, Union
from loguru import logger
import os

from .cloud_client import AIBackendClient


class AIClient:
    """Client AI che supporta multiple providers"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.ai_config = config.get("ai", {})
        
        self.provider = self.ai_config.get("provider", "akaion")
        self.model = self.ai_config.get("model", "gpt-4")
        self.temperature = self.ai_config.get("temperature", 0.7)
        self.max_tokens = self.ai_config.get("max_tokens", 4000)
        
        # Client typed as Any to avoid complex union types
        self.client: Any = None
        
        # Inizializza il provider
        self._init_provider()
    
    def _init_provider(self):
        """Inizializza il provider AI"""
        if self.provider == "akaion":
            self._init_akaion()
        elif self.provider == "openai":
            self._init_openai()
        elif self.provider == "anthropic":
            self._init_anthropic()
        elif self.provider == "google":
            self._init_google()
        elif self.provider == "local":
            self._init_local()
        else:
            raise ValueError(f"Unknown AI provider: {self.provider}")
    
    def _init_akaion(self):
        """Inizializza Akaion AI"""
        from .auth import AuthManager
        auth = AuthManager()
        
        api_key = auth.get_api_key()
        if not api_key:
            raise ValueError("Akaion API key not available")
        
        self.client = AIBackendClient(
            api_key=api_key,
            runner_id=auth.get_runner_id()
        )
        logger.info("Using Akaion AI Backend")
    
    def _init_openai(self):
        """Inizializza OpenAI"""
        from openai import OpenAI
        
        api_key = self.ai_config.get("openai", {}).get("api_key") or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OpenAI API key not configured")
        
        self.client = OpenAI(api_key=api_key)
        logger.info("Using OpenAI")
    
    def _init_anthropic(self):
        """Inizializza Anthropic"""
        from anthropic import Anthropic
        
        api_key = self.ai_config.get("anthropic", {}).get("api_key") or os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("Anthropic API key not configured")
        
        self.client = Anthropic(api_key=api_key)
        logger.info("Using Anthropic Claude")
    
    def _init_google(self):
        """Inizializza Google"""
        try:
            import google.generativeai as genai
            
            api_key = self.ai_config.get("google", {}).get("api_key") or os.getenv("GOOGLE_API_KEY")
            if not api_key:
                raise ValueError("Google API key not configured")
            
            genai.configure(api_key=api_key)  # type: ignore
            self.client = genai
            logger.info("Using Google Gemini")
        except ImportError:
            raise ValueError("google-generativeai package not installed")
    
    def _init_local(self):
        """Inizializza Local (Ollama)"""
        import httpx
        
        endpoint = self.ai_config.get("local", {}).get("endpoint", "http://localhost:11434")
        self.client = httpx.Client(base_url=endpoint)
        logger.info(f"Using Local LLM at {endpoint}")
    
    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> str:
        """
        Esegue una chat completion
        
        Args:
            messages: Lista di messaggi [{role: "user/assistant/system", content: "..."}]
            temperature: Override temperature
            max_tokens: Override max_tokens
            
        Returns:
            Risposta del modello
        """
        temp = temperature if temperature is not None else self.temperature
        max_tok = max_tokens if max_tokens is not None else self.max_tokens
        
        if self.provider == "akaion":
            return self._chat_akaion(messages, temp, max_tok)
        elif self.provider == "openai":
            return self._chat_openai(messages, temp, max_tok)
        elif self.provider == "anthropic":
            return self._chat_anthropic(messages, temp, max_tok)
        elif self.provider == "google":
            return self._chat_google(messages, temp, max_tok)
        elif self.provider == "local":
            return self._chat_local(messages, temp, max_tok)
        else:
            return ""
    
    def _chat_akaion(self, messages: List[Dict[str, str]], temp: float, max_tok: int) -> str:
        """Chat con Akaion AI"""
        result = self.client.chat_completion(  # type: ignore
            messages=messages,
            model=self.model,
            temperature=temp
        )
        return result.get("message", {}).get("content", "") if result else ""
    
    def _chat_openai(self, messages: List[Dict[str, str]], temp: float, max_tok: int) -> str:
        """Chat con OpenAI"""
        response = self.client.chat.completions.create(  # type: ignore
            model=self.model,
            messages=messages,  # type: ignore
            temperature=temp,
            max_tokens=max_tok
        )
        return response.choices[0].message.content or ""
    
    def _chat_anthropic(self, messages: List[Dict[str, str]], temp: float, max_tok: int) -> str:
        """Chat con Anthropic"""
        # Anthropic richiede system message separato
        system_msg = next((m["content"] for m in messages if m["role"] == "system"), None)
        user_messages = [m for m in messages if m["role"] != "system"]
        
        response = self.client.messages.create(  # type: ignore
            model=self.model,
            system=system_msg or "",
            messages=user_messages,  # type: ignore
            temperature=temp,
            max_tokens=max_tok
        )
        # Handle different content block types
        if response.content and len(response.content) > 0:
            block = response.content[0]
            if hasattr(block, 'text'):
                return block.text  # type: ignore
        return ""
    
    def _chat_google(self, messages: List[Dict[str, str]], temp: float, max_tok: int) -> str:
        """Chat con Google"""
        model = self.client.GenerativeModel(self.model)  # type: ignore
        
        # Converti messages in formato Google
        chat = model.start_chat(history=[])  # type: ignore
        for msg in messages[:-1]:  # Tutti tranne l'ultimo
            chat.send_message(msg["content"])  # type: ignore
        
        # Invia ultimo messaggio
        response = chat.send_message(messages[-1]["content"])  # type: ignore
        return response.text or ""  # type: ignore
    
    def _chat_local(self, messages: List[Dict[str, str]], temp: float, max_tok: int) -> str:
        """Chat con Ollama locale"""
        response = self.client.post(  # type: ignore
            "/api/chat",
            json={
                "model": self.model,
                "messages": messages,
                "temperature": temp,
                "stream": False
            }
        )
        return response.json().get("message", {}).get("content", "")
    
    def execute_command(self, command: str, tools) -> Any:
        """
        Esegue un comando usando l'AI
        
        Args:
            command: Comando da eseguire
            tools: ToolRegistry disponibili
            
        Returns:
            Risultato dell'esecuzione
        """
        # Se il provider è Akaion, usa l'endpoint specifico per runner
        if self.provider == "akaion":
            return self._execute_command_akaion(command, tools)
        
        # Altrimenti usa il metodo generico con chat completion
        return self._execute_command_generic(command, tools)
    
    def _execute_command_akaion(self, command: str, tools) -> Any:
        """Esegue un comando via Akaion AI Backend (endpoint runner)"""
        try:
            import os
            import subprocess
            from pathlib import Path
            
            # Prepara il contesto per il runner
            working_dir = os.getcwd()
            available_tools = tools.list_tools() if tools else []
            
            # Chiama l'endpoint specifico per runner
            result = self.client.runner_execute(  # type: ignore
                command=command,
                working_directory=working_dir,
                available_tools=available_tools,
                permissions=self.config.get("permissions", {}),
                environment=dict(os.environ),
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )
            
            if result and result.get("success"):
                response_text = result.get("response", "")
                actions = result.get("actions", [])
                
                # Execute shell commands from actions
                command_results = []
                for action in actions:
                    if action.get("type") == "shell_command":
                        cmd = action.get("payload", {}).get("command")
                        if cmd:
                            try:
                                logger.info(f"Executing shell command: {cmd}")
                                proc_result = subprocess.run(
                                    cmd,
                                    shell=True,
                                    capture_output=True,
                                    text=True,
                                    timeout=30,
                                    cwd=working_dir
                                )
                                
                                command_output = proc_result.stdout.strip()
                                if proc_result.returncode == 0:
                                    logger.success(f"Command executed successfully: {command_output}")
                                    command_results.append({
                                        "command": cmd,
                                        "output": command_output,
                                        "success": True
                                    })
                                else:
                                    error_output = proc_result.stderr.strip()
                                    logger.error(f"Command failed: {error_output}")
                                    command_results.append({
                                        "command": cmd,
                                        "output": error_output,
                                        "success": False
                                    })
                            except subprocess.TimeoutExpired:
                                logger.error(f"Command timed out: {cmd}")
                                command_results.append({
                                    "command": cmd,
                                    "output": "Command timed out after 30 seconds",
                                    "success": False
                                })
                            except Exception as e:
                                logger.error(f"Error executing command: {e}")
                                command_results.append({
                                    "command": cmd,
                                    "output": str(e),
                                    "success": False
                                })
                
                # Build final response with command results
                final_response = response_text
                if command_results:
                    final_response += "\n\n**Execution Results:**\n"
                    for cmd_result in command_results:
                        if cmd_result["success"]:
                            final_response += f"\n✅ `{cmd_result['command']}`\n"
                            final_response += f"Output: {cmd_result['output']}\n"
                        else:
                            final_response += f"\n❌ `{cmd_result['command']}`\n"
                            final_response += f"Error: {cmd_result['output']}\n"
                
                return {
                    "response": final_response,
                    "actions": actions,
                    "command_results": command_results,
                    "reasoning": result.get("reasoning"),
                }
            else:
                error_msg = result.get("error", "Unknown error") if result else "No response from AI"
                logger.error(f"AI command execution failed: {error_msg}")
                return {
                    "response": f"Error: {error_msg}",
                    "actions": [],
                }
        
        except Exception as e:
            logger.error(f"Error executing command via Akaion: {e}")
            return {
                "response": f"Execution error: {str(e)}",
                "actions": [],
            }
    
    def _execute_command_generic(self, command: str, tools) -> Any:
        """Esegue un comando via provider generico (OpenAI, Anthropic, etc)"""
        # Costruisci il prompt per l'AI
        system_prompt = """You are a helpful AI assistant that can execute commands using available tools.
        
Available tools:
{tools}

When given a command, analyze it and use the appropriate tools to execute it.
Return the result in a structured format.""".format(
            tools="\n".join([f"- {t}" for t in tools.list_tools()]) if tools else "None"
        )
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Execute this command: {command}"}
        ]
        
        response = self.chat_completion(messages)
        
        # TODO: Parse response e chiamata tools per provider non-Akaion
        return {"response": response, "actions": []}
    
    def reason_and_execute(
        self,
        prompt: str,
        context: Dict[str, Any],
        tools,
        permissions,
        max_iterations: int = 10
    ) -> Any:
        """
        Agentic loop: ragiona sul task ed esegue tools iterativamente.

        - Per provider 'akaion':    usa il backend /runner/agent/turn (LLM cloud, tool exec locale)
        - Per provider 'anthropic': usa il native tool-use di Claude direttamente
        - Per altri provider:       fallback a chat completion senza tool use
        """
        if self.provider == "akaion":
            return self._agentic_loop_akaion(prompt, context, tools, permissions, max_iterations)
        elif self.provider == "anthropic":
            return self._agentic_loop_anthropic(prompt, context, tools, permissions, max_iterations)
        else:
            return self._agentic_loop_generic(prompt, context, tools)

    def _agentic_loop_akaion(
        self,
        prompt: str,
        context: Dict[str, Any],
        tools,
        permissions,
        max_iterations: int,
    ) -> Any:
        """
        Agentic loop che usa il backend Akaion come LLM proxy.

        Il runner mantiene lo stato (messages array).
        Ad ogni iterazione:
          1. Invia messages + tool schemas → POST /api/v1/runner/agent/turn
          2. Backend chiama Claude con tool use nativo
          3. Se stop_reason == "tool_use": esegui i tool localmente, aggiungi risultati, ripeti
          4. Se stop_reason == "end_turn": restituisci la risposta finale
        """
        import json

        # Build tool schemas for the backend (Anthropic format)
        tool_schemas: List[Dict[str, Any]] = []
        if tools:
            for schema in tools.get_all_schemas():
                tool_schemas.append({
                    "name": schema["name"],
                    "description": schema["description"],
                    "input_schema": schema["parameters"],
                })

        # System prompt with context
        system_prompt = (
            "You are an advanced local agent running on the user's machine. "
            "You have access to tools to explore the filesystem, read documents of any format "
            "(PDF, DOCX, XLSX, CSV, code files), execute shell commands, and analyze content. "
            "When given a task, think step by step and use the appropriate tools. "
            "Be thorough: explore before reading, read before summarizing. "
            f"Context: {json.dumps(context) if context else 'none'}"
        )

        # Initial user message
        messages: List[Dict[str, Any]] = [
            {
                "role": "user",
                "content": [{"type": "text", "text": prompt}],
            }
        ]

        runner_id = self.client.runner_id or "unknown"  # type: ignore
        tool_call_log: List[Dict[str, Any]] = []
        final_response = ""

        for iteration in range(max_iterations):
            logger.info(f"Akaion agent turn {iteration + 1}/{max_iterations}")

            turn_result = self.client.runner_agent_turn(  # type: ignore
                runner_id=runner_id,
                messages=messages,
                tools=tool_schemas,
                system_prompt=system_prompt,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )

            if not turn_result:
                logger.error("runner_agent_turn returned None — aborting loop")
                break

            stop_reason = turn_result.get("stop_reason", "end_turn")
            content_blocks = turn_result.get("content", [])

            # Collect text and tool_use blocks
            tool_use_blocks = []
            for block in content_blocks:
                if block.get("type") == "text":
                    final_response = block.get("text", "")
                elif block.get("type") == "tool_use":
                    tool_use_blocks.append(block)

            if stop_reason == "end_turn" or not tool_use_blocks:
                break

            # Execute tool calls locally
            tool_results = []
            for tu in tool_use_blocks:
                tool_name = tu.get("name")
                tool_input = tu.get("input") or {}
                tu_id = tu.get("id")

                logger.info(f"Executing tool: {tool_name} {tool_input}")

                if permissions and not permissions.check_tool_permission(tool_name, tool_input):
                    result_content = {"error": f"Permission denied for tool: {tool_name}"}
                    is_error = True
                else:
                    try:
                        tool_obj = tools.get_tool(tool_name)
                        result_content = tool_obj.execute(**tool_input)
                        is_error = False
                    except Exception as e:
                        result_content = {"error": str(e)}
                        is_error = True

                tool_call_log.append({
                    "tool": tool_name,
                    "input": tool_input,
                    "result": result_content,
                    "error": is_error,
                })

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tu_id,
                    "content": json.dumps(result_content),
                    "is_error": is_error,
                })

            # Append assistant turn (with tool_use blocks) + user turn (with tool results)
            messages.append({"role": "assistant", "content": content_blocks})
            messages.append({"role": "user", "content": tool_results})

        return {
            "response": final_response,
            "iterations": iteration + 1,
            "tool_calls": tool_call_log,
        }

    def _agentic_loop_anthropic(
        self,
        prompt: str,
        context: Dict[str, Any],
        tools,
        permissions,
        max_iterations: int
    ) -> Any:
        """
        Agentic loop con Anthropic tool use nativo.
        Ciclo: send → ricevi tool_use → esegui → send results → ripeti.
        """
        import json

        # Build tool schemas for Claude
        tool_schemas = tools.get_all_schemas() if tools else []
        anthropic_tools = [
            {
                "name": t["name"],
                "description": t["description"],
                "input_schema": t["parameters"]
            }
            for t in tool_schemas
        ]

        system_prompt = (
            "You are an advanced local agent running on the user's machine. "
            "You have access to tools to explore the filesystem, read documents of any format "
            "(PDF, DOCX, XLSX, CSV, code files), execute shell commands, and analyze content. "
            "When given a task, think step by step and use the appropriate tools. "
            "Be thorough: explore before reading, read before summarizing. "
            f"Context: {json.dumps(context) if context else 'none'}"
        )

        messages = [{"role": "user", "content": prompt}]
        tool_call_log = []
        final_response = ""

        for iteration in range(max_iterations):
            logger.info(f"Agent iteration {iteration + 1}/{max_iterations}")

            kwargs: Dict[str, Any] = {
                "model": self.model,
                "system": system_prompt,
                "messages": messages,
                "max_tokens": self.max_tokens,
                "temperature": self.temperature,
            }
            if anthropic_tools:
                kwargs["tools"] = anthropic_tools

            response = self.client.messages.create(**kwargs)  # type: ignore

            # Check stop reason
            stop_reason = response.stop_reason

            # Collect text and tool use blocks
            tool_use_blocks = []
            text_parts = []
            for block in response.content:
                if block.type == "text":
                    text_parts.append(block.text)
                elif block.type == "tool_use":
                    tool_use_blocks.append(block)

            if text_parts:
                final_response = " ".join(text_parts)

            if stop_reason == "end_turn" or not tool_use_blocks:
                # Done
                break

            # Execute tool calls
            tool_results = []
            for tu in tool_use_blocks:
                tool_name = tu.name
                tool_input = tu.input if hasattr(tu, "input") else {}

                logger.info(f"Calling tool: {tool_name} with {tool_input}")

                # Permission check
                if permissions and not permissions.check_tool_permission(tool_name, tool_input):
                    result_content = {"error": f"Permission denied for tool: {tool_name}"}
                    is_error = True
                else:
                    try:
                        tool_obj = tools.get_tool(tool_name)
                        result_content = tool_obj.execute(**tool_input)
                        is_error = False
                    except Exception as e:
                        result_content = {"error": str(e)}
                        is_error = True

                tool_call_log.append({
                    "tool": tool_name,
                    "input": tool_input,
                    "result": result_content,
                    "error": is_error,
                })

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tu.id,
                    "content": json.dumps(result_content),
                    "is_error": is_error,
                })

            # Append assistant turn + tool results
            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})

        return {
            "response": final_response,
            "iterations": iteration + 1,
            "tool_calls": tool_call_log,
        }

    def _agentic_loop_generic(
        self,
        prompt: str,
        context: Dict[str, Any],
        tools
    ) -> Any:
        """Fallback per provider senza tool use nativo"""
        system_prompt = (
            f"You are an advanced AI agent.\n"
            f"Available tools: {', '.join(tools.list_tools()) if tools else 'none'}\n"
            f"Context: {context}\n\n"
            "Think step by step and describe what you would do to accomplish the task."
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ]
        response = self.chat_completion(messages)
        return {"response": response, "tool_calls": []}
