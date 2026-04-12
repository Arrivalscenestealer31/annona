"""
Cloud Client

Client per comunicare con i backend Akaion cloud.
Supporta tutti e 4 i backend principali:
- Main Backend (orchestrazione, utenti, system)
- AI Backend (LLM, skills, reasoning)
- Calendar Backend (eventi, scheduling)
- CoT Backend (chain-of-thought, workflows)
"""
import httpx
from typing import Optional, Dict, Any, List
from loguru import logger
import os


class AkaionBackendClient:
    """Client base per comunicare con i backend Akaion"""
    
    def __init__(
        self,
        api_key: str,
        base_url: str,
        runner_id: Optional[str] = None,
        timeout: int = 30
    ):
        self.api_key = api_key
        self.base_url = base_url
        self.runner_id = runner_id
        self.timeout = timeout
        
        self.client = httpx.Client(
            base_url=self.base_url,
            timeout=timeout,
            headers={
                "Authorization": f"Bearer {api_key}",
                "X-Runner-ID": runner_id or "unknown",
                "Content-Type": "application/json"
            }
        )
    
    def verify_auth(self) -> bool:
        """Verifica che l'autenticazione sia valida"""
        try:
            response = self.client.get("/api/v1/users/me")
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Auth verification failed: {e}")
            return False
    
    def health_check(self) -> bool:
        """Health check del cloud"""
        try:
            response = self.client.get("/health")
            return response.status_code == 200
        except Exception:
            return False
    
    def poll_tasks(self) -> List[Dict[str, Any]]:
        """
        Recupera i task in pending dal cloud (nuovo endpoint /api/v1/runner/tasks/poll)
        
        Returns:
            List di task da eseguire
        """
        try:
            response = self.client.get("/api/v1/runner/tasks/poll")
            
            if response.status_code == 200:
                data = response.json()
                return data.get("tasks", [])
            
            return []
        
        except Exception as e:
            logger.error(f"Error polling tasks: {e}")
            return []
    
    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Recupera un task specifico"""
        try:
            response = self.client.get(f"/v1/runner/tasks/{task_id}")
            
            if response.status_code == 200:
                return response.json()
            
            return None
        
        except Exception as e:
            logger.error(f"Error getting task {task_id}: {e}")
            return None
    
    def update_task_status(
        self,
        task_id: str,
        status: str,
        progress: Optional[int] = None,
        message: Optional[str] = None
    ) -> bool:
        """
        Aggiorna lo stato di un task
        
        Args:
            task_id: ID del task
            status: Nuovo stato (pending, running, completed, failed)
            progress: Progresso 0-100
            message: Messaggio opzionale
        """
        try:
            payload = {
                "status": status,
                "runner_id": self.runner_id
            }
            
            if progress is not None:
                payload["progress"] = progress
            
            if message:
                payload["message"] = message
            
            response = self.client.put(
                f"/v1/runner/tasks/{task_id}/status",
                json=payload
            )
            
            return response.status_code == 200
        
        except Exception as e:
            logger.error(f"Error updating task status: {e}")
            return False
    
    def submit_task_result(
        self,
        task_id: str,
        result: Any,
        success: bool = True,
        error: Optional[str] = None,
        output: Optional[str] = None,
        files_created: Optional[List[str]] = None,
        execution_time: Optional[float] = None
    ) -> bool:
        """
        Invia il risultato di un task completato (nuovo endpoint /api/v1/runner/tasks/result)
        
        Args:
            task_id: ID del task
            result: Risultato dell'esecuzione (deprecato, usa output)
            success: Se l'esecuzione è stata successful
            error: Errore eventuale
            output: Output dell'esecuzione
            files_created: Lista di file creati
            execution_time: Tempo di esecuzione in secondi
        """
        try:
            payload = {
                "task_id": task_id,
                "success": success,
                "output": output or str(result)
            }
            
            if error:
                payload["error"] = error
            if files_created:
                payload["files_created"] = files_created
            if execution_time is not None:
                payload["execution_time"] = execution_time
            
            response = self.client.post(
                "/api/v1/runner/tasks/result",
                json=payload
            )
            
            return response.status_code == 200
        
        except Exception as e:
            logger.error(f"Error submitting task result: {e}")
            return False
    
    def send_heartbeat(self, status: Dict[str, Any], metrics: Optional[Dict[str, Any]] = None) -> bool:
        """Invia heartbeat al cloud (nuovo endpoint /api/v1/runner/heartbeat)"""
        try:
            payload = {
                "runner_id": self.runner_id,
                "status": status
            }
            if metrics:
                payload["metrics"] = metrics
            
            response = self.client.post(
                "/api/v1/runner/heartbeat",
                json=payload
            )
            
            return response.status_code == 200
        
        except Exception as e:
            logger.debug(f"Heartbeat failed: {e}")
            return False
    
    def get_runner_config(self) -> Optional[Dict[str, Any]]:
        """Recupera la configurazione dal cloud"""
        try:
            response = self.client.get(f"/v1/runner/config")
            
            if response.status_code == 200:
                return response.json()
            
            return None
        
        except Exception as e:
            logger.error(f"Error getting runner config: {e}")
            return None
    
    def close(self):
        """Chiudi la connessione"""
        self.client.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# Client specifici per ogni backend -----------------------------------------------

class MainBackendClient(AkaionBackendClient):
    """
    Client per il Main Backend
    Gestisce: utenti, autenticazione, orchestrazione, system
    """
    
    def __init__(self, api_key: str, runner_id: Optional[str] = None, base_url: Optional[str] = None, timeout: int = 30):
        super().__init__(
            api_key=api_key,
            base_url=base_url or os.getenv("AKAION_MAIN_URL", "https://api.akaion.com"),
            runner_id=runner_id,
            timeout=timeout
        )
    
    def get_user_info(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Recupera info utente"""
        try:
            response = self.client.get(f"/v1/users/{user_id}")
            return response.json() if response.status_code == 200 else None
        except Exception as e:
            logger.error(f"Error getting user info: {e}")
            return None
    
    def create_notification(self, user_id: str, message: str, notification_type: str = "info") -> bool:
        """Crea una notifica per l'utente"""
        try:
            response = self.client.post(
                "/v1/notifications",
                json={
                    "user_id": user_id,
                    "message": message,
                    "type": notification_type
                }
            )
            return response.status_code == 201
        except Exception as e:
            logger.error(f"Error creating notification: {e}")
            return False


class AIBackendClient(AkaionBackendClient):
    """
    Client per il AI Backend
    Gestisce: LLM calls, skills, reasoning, AI tasks
    """
    
    def __init__(self, api_key: str, runner_id: Optional[str] = None, base_url: Optional[str] = None, timeout: int = 30):
        super().__init__(
            api_key=api_key,
            base_url=base_url or os.getenv("AKAION_AI_URL", "https://ai.akaion.com"),
            runner_id=runner_id,
            timeout=timeout
        )
    
    def register_runner(
        self,
        runner_name: str,
        machine_id: str,
        capabilities: List[str],
        system_info: Optional[Dict[str, Any]] = None,
        callback_url: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Register runner with the AI backend
        
        Args:
            runner_name: Name of this runner
            machine_id: Unique machine identifier
            capabilities: List of capabilities (e.g., ["python", "powerpoint", "filesystem"])
            system_info: System information (OS, version, etc.)
            callback_url: Optional callback URL for async notifications
            
        Returns:
            Registration response with runner_id and polling info
        """
        try:
            response = self.client.post(
                "/api/v1/runner/register",
                json={
                    "runner_name": runner_name,
                    "machine_id": machine_id,
                    "capabilities": capabilities,
                    "system_info": system_info or {},
                    "callback_url": callback_url
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                # Update runner_id for future requests
                self.runner_id = data.get("runner_id")
                self.client.headers["X-Runner-ID"] = self.runner_id
                return data
            else:
                logger.error(f"Runner registration failed: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Error registering runner: {e}")
            return None
    
    def runner_agent_turn(
        self,
        runner_id: str,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> Optional[Dict[str, Any]]:
        """
        One turn of the agentic loop via the backend's /runner/agent/turn endpoint.

        Sends the full conversation history + tool schemas.
        Returns { content: [...], stop_reason, model, tokens_used } or None on error.

        content blocks:
          - { type: "text",     text: "..." }
          - { type: "tool_use", id: "...", name: "...", input: {...} }
        """
        try:
            payload: Dict[str, Any] = {
                "runner_id": runner_id,
                "messages": messages,
                "tools": tools or [],
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            if system_prompt:
                payload["system_prompt"] = system_prompt
            if model:
                payload["model"] = model

            response = self.client.post(
                "/api/v1/runner/agent/turn",
                json=payload,
                headers={
                    **dict(self.client.headers),
                    "X-Runner-ID": runner_id,
                },
            )

            if response.status_code == 200:
                return response.json()
            else:
                logger.error(
                    f"runner_agent_turn failed: {response.status_code} — {response.text}"
                )
                return None

        except Exception as e:
            logger.error(f"runner_agent_turn error: {e}")
            return None

    def runner_execute(
        self,
        command: str,
        working_directory: Optional[str] = None,
        available_tools: Optional[List[str]] = None,
        permissions: Optional[Dict[str, Any]] = None,
        environment: Optional[Dict[str, str]] = None,
        temperature: float = 0.7,
        max_tokens: int = 4000
    ) -> Optional[Dict[str, Any]]:
        """
        Esegue un comando via AI (endpoint specifico per runner)
        
        Args:
            command: Comando da eseguire
            working_directory: Directory corrente
            available_tools: Tools disponibili
            permissions: Permissions del runner
            environment: Environment variables
            temperature: LLM temperature
            max_tokens: Max tokens
            
        Returns:
            Response con risultato AI
        """
        try:
            response = self.client.post(
                "/api/v1/kai/runner/execute",
                json={
                    "command": command,
                    "runner_id": self.runner_id,
                    "working_directory": working_directory,
                    "available_tools": available_tools or [],
                    "permissions": permissions or {},
                    "environment": environment or {},
                    "temperature": temperature,
                    "max_tokens": max_tokens
                },
                headers={
                    **self.client.headers,
                    "X-Runner-ID": self.runner_id or "unknown"
                }
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Runner execute failed: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Error in runner execute: {e}")
            return None
    
    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: str = "gpt-4",
        temperature: float = 0.7,
        stream: bool = False
    ) -> Optional[Dict[str, Any]]:
        """Esegue una chat completion"""
        try:
            response = self.client.post(
                "/v1/kai/chat",
                json={
                    "messages": messages,
                    "model": model,
                    "temperature": temperature,
                    "stream": stream
                }
            )
            return response.json() if response.status_code == 200 else None
        except Exception as e:
            logger.error(f"Error in chat completion: {e}")
            return None
    
    def execute_skill(self, skill_name: str, parameters: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Esegue una skill AI"""
        try:
            response = self.client.post(
                f"/v1/skills/{skill_name}/execute",
                json={"parameters": parameters}
            )
            return response.json() if response.status_code == 200 else None
        except Exception as e:
            logger.error(f"Error executing skill: {e}")
            return None
    
    def get_available_skills(self) -> List[Dict[str, Any]]:
        """Recupera la lista delle skills disponibili"""
        try:
            response = self.client.get("/v1/skills")
            return response.json().get("skills", []) if response.status_code == 200 else []
        except Exception as e:
            logger.error(f"Error getting skills: {e}")
            return []


class CalendarBackendClient(AkaionBackendClient):
    """
    Client per il Calendar Backend
    Gestisce: eventi, scheduling, calendar operations
    """
    
    def __init__(self, api_key: str, runner_id: Optional[str] = None, base_url: Optional[str] = None):
        super().__init__(
            api_key=api_key,
            base_url=base_url or os.getenv("AKAION_CALENDAR_URL", "https://calendar.akaion.com"),
            runner_id=runner_id
        )
    
    def get_events(
        self,
        user_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Recupera gli eventi del calendario"""
        try:
            params = {"user_id": user_id}
            if start_date:
                params["start_date"] = start_date
            if end_date:
                params["end_date"] = end_date
            
            response = self.client.get("/v1/events", params=params)
            return response.json().get("events", []) if response.status_code == 200 else []
        except Exception as e:
            logger.error(f"Error getting events: {e}")
            return []
    
    def create_event(self, event_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Crea un nuovo evento"""
        try:
            response = self.client.post("/v1/events", json=event_data)
            return response.json() if response.status_code == 201 else None
        except Exception as e:
            logger.error(f"Error creating event: {e}")
            return None
    
    def update_event(self, event_id: str, event_data: Dict[str, Any]) -> bool:
        """Aggiorna un evento esistente"""
        try:
            response = self.client.put(f"/v1/events/{event_id}", json=event_data)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Error updating event: {e}")
            return False


class CoTBackendClient(AkaionBackendClient):
    """
    Client per il CoT (Chain-of-Thought) Backend
    Gestisce: workflows, chain-of-thought, multi-step reasoning
    """
    
    def __init__(self, api_key: str, runner_id: Optional[str] = None, base_url: Optional[str] = None):
        super().__init__(
            api_key=api_key,
            base_url=base_url or os.getenv("AKAION_COT_URL", "https://cot.akaion.com"),
            runner_id=runner_id
        )
    
    def execute_workflow(self, workflow_id: str, input_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Esegue un workflow"""
        try:
            response = self.client.post(
                f"/v1/workflows/{workflow_id}/execute",
                json={"input": input_data}
            )
            return response.json() if response.status_code == 200 else None
        except Exception as e:
            logger.error(f"Error executing workflow: {e}")
            return None
    
    def get_workflow_status(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """Recupera lo stato di un'esecuzione workflow"""
        try:
            response = self.client.get(f"/v1/workflows/executions/{execution_id}")
            return response.json() if response.status_code == 200 else None
        except Exception as e:
            logger.error(f"Error getting workflow status: {e}")
            return None
    
    def create_chain_of_thought(self, prompt: str, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Crea una chain-of-thought reasoning"""
        try:
            response = self.client.post(
                "/v1/cot/create",
                json={
                    "prompt": prompt,
                    "context": context
                }
            )
            return response.json() if response.status_code == 200 else None
        except Exception as e:
            logger.error(f"Error creating CoT: {e}")
            return None


# Alias per backward compatibility
CloudClient = MainBackendClient
