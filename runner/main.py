"""
Runner Daemon

Main daemon che fa polling dal cloud ed esegue i task.
Avvia anche un server FastAPI locale su :port per la UI Tauri.
"""
import asyncio
import os
import time
import signal
from typing import Dict, Any, Optional
from loguru import logger
from pathlib import Path

from .auth import AuthManager
from .config import ConfigManager
from .cloud_client import CloudClient
from .executor import TaskExecutor
from .banner import print_runner_banner, print_startup_info
from .brain.manager import BrainManager
from .sync.engine import SyncEngine
from .local_api import LocalAPIServer

DEFAULT_BRAIN_DIR = Path.home() / "akaion-brain"
DEFAULT_LOCAL_PORT = 7070


class RunnerDaemon:
    """Daemon principale del runner"""

    def __init__(
        self,
        config: Dict[str, Any],
        dev_mode: bool = False,
        brain_dir: Optional[Path] = None,
        local_port: int = DEFAULT_LOCAL_PORT,
    ):
        self.config = config
        self.dev_mode = dev_mode
        self.running = False
        self.tasks_executed = 0
        self.local_port = local_port

        # Setup logging
        self._setup_logging()
        
        # Managers
        self.auth_manager = AuthManager()
        self.config_manager = ConfigManager()
        
        # Cloud client
        self.cloud_client = CloudClient(
            api_key=self.auth_manager.get_api_key(),
            base_url=os.getenv("AKAION_MAIN_URL"),
            runner_id=self.auth_manager.get_runner_id(),
            timeout=config.get("cloud", {}).get("timeout", 30)
        )
        
        # Executor
        self.executor = TaskExecutor(config)

        # Polling config
        self.polling_interval = config.get("cloud", {}).get("polling_interval", 5)
        self.max_concurrent = config.get("runner", {}).get("max_concurrent_tasks", 3)

        # Brain + Sync
        _brain_dir = brain_dir or Path(
            config.get("brain", {}).get("dir", str(DEFAULT_BRAIN_DIR))
        )
        self.brain = BrainManager(_brain_dir)
        self.sync = SyncEngine(
            brain=self.brain,
            cot_url=os.getenv("AKAION_COT_URL", "https://cot.akaion.com"),
            auth=self.auth_manager,
        )

        # Local API server (Tauri UI)
        self.local_api = LocalAPIServer(self.brain, self.sync, auth=self.auth_manager, port=local_port)

        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _setup_logging(self):
        """Setup del logging system"""
        log_config = self.config.get("logging", {})
        log_level = log_config.get("level", "INFO")
        log_file = log_config.get("file", "logs/runner.log")
        
        # Crea directory logs
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        
        # Configure loguru
        logger.remove()  # Rimuovi handler default
        
        # Console handler
        logger.add(
            lambda msg: print(msg, end=""),
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
            level=log_level
        )
        
        # File handler
        logger.add(
            log_file,
            rotation="1 day",
            retention="7 days",
            level=log_level,
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function} - {message}"
        )
        
        if self.dev_mode:
            logger.info("🔧 Development mode enabled")
    
    def _signal_handler(self, signum, frame):
        """Handler per SIGINT e SIGTERM"""
        logger.info(f"Received signal {signum}, shutting down...")
        self.stop()
    
    def start_daemon(self):
        """Avvia il daemon in modalità persistente"""
        self.running = True

        # Avvia local API server in background thread
        self.local_api.start()

        # Print beautiful banner
        print_runner_banner()
        
        logger.info("🚀 Akaion Runner started")
        
        # Print startup info
        print_startup_info(
            runner_id=self.auth_manager.get_runner_id(),
            cloud_url=self.cloud_client.base_url,
            polling_interval=self.polling_interval
        )
        
        logger.info("👂 Listening for tasks...")
        logger.info("Press Ctrl+C to stop")
        
        # Verifica connessione
        if not self.cloud_client.health_check():
            logger.warning("⚠️  Cloud health check failed, but continuing...")
        
        last_heartbeat = 0
        heartbeat_interval = 30  # Heartbeat ogni 30s
        
        try:
            while self.running:
                # Heartbeat
                current_time = time.time()
                if current_time - last_heartbeat > heartbeat_interval:
                    self._send_heartbeat()
                    last_heartbeat = current_time
                
                # Poll per task
                self._poll_and_execute()
                
                # Sleep
                time.sleep(self.polling_interval)
        
        except KeyboardInterrupt:
            logger.info("Interrupted by user")
        except Exception as e:
            logger.error(f"Daemon error: {e}", exc_info=True)
        finally:
            self.stop()
    
    def poll_once(self):
        """Esegue un singolo polling cycle"""
        logger.info("🔄 Polling for tasks...")
        self._poll_and_execute()
    
    def execute_once(self, task_description: str) -> Any:
        """
        Esegue un task specifico una volta
        
        Args:
            task_description: Descrizione del task da eseguire
        """
        logger.info(f"🎯 Executing task: {task_description}")
        
        # Crea un task object
        task = {
            "id": "local-" + str(int(time.time())),
            "type": "command",
            "description": task_description,
            "payload": {
                "command": task_description
            }
        }
        
        return self._execute_task(task)
    
    def _poll_and_execute(self):
        """Poll dal cloud ed esegui i task"""
        try:
            tasks = self.cloud_client.poll_tasks()
            
            if not tasks:
                logger.debug("No tasks available")
                return
            
            logger.info(f"📥 Received {len(tasks)} task(s)")
            
            for task in tasks[:self.max_concurrent]:
                self._execute_task(task)
        
        except Exception as e:
            logger.error(f"Error during polling: {e}", exc_info=True)
    
    def _execute_task(self, task: Dict[str, Any]) -> Any:
        """
        Esegue un task
        
        Args:
            task: Task object dal cloud
        """
        task_id = task.get("id")
        logger.info(f"⚙️  Executing task {task_id}")
        
        try:
            # Update status: running
            if "id" in task and task["id"].startswith("task-"):
                self.cloud_client.update_task_status(task_id, "running")
            
            # Esegui il task
            result = self.executor.execute(task)
            
            logger.info(f"✅ Task {task_id} completed successfully")
            
            # Update status: completed
            if "id" in task and task["id"].startswith("task-"):
                self.cloud_client.submit_task_result(
                    task_id,
                    result=result,
                    success=True
                )
            
            self.tasks_executed += 1
            return result
        
        except Exception as e:
            logger.error(f"❌ Task {task_id} failed: {e}", exc_info=True)
            
            # Update status: failed
            if "id" in task and task["id"].startswith("task-"):
                self.cloud_client.submit_task_result(
                    task_id,
                    result=None,
                    success=False,
                    error=str(e)
                )
            
            raise
    
    def _send_heartbeat(self):
        """Invia heartbeat al cloud"""
        try:
            status = {
                "running": self.running,
                "tasks_executed": self.tasks_executed,
                "uptime": int(time.time()),  # Simplified
            }
            
            self.cloud_client.send_heartbeat(status)
            logger.debug("💓 Heartbeat sent")
        
        except Exception as e:
            logger.debug(f"Heartbeat error: {e}")
    
    def stop(self):
        """Ferma il daemon"""
        if not self.running:
            return
        
        self.running = False
        logger.info("🛑 Runner stopped")

        # Cleanup
        self.local_api.stop()
        self.brain.close()
        self.cloud_client.close()
        
        logger.info(f"📊 Total tasks executed: {self.tasks_executed}")
