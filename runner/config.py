"""
Configuration Manager

Gestisce la configurazione del runner.
"""
import yaml
from pathlib import Path
from typing import Optional, Dict, Any
import shutil


class ConfigManager:
    """Gestisce la configurazione del runner"""
    
    def __init__(self, config_dir: Optional[Path] = None):
        self.config_dir = config_dir or Path.home() / ".akaion"
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        self.config_path = self.config_dir / "config.yaml"
        self.default_config_path = Path(__file__).parent.parent / "config.yaml"
    
    def config_exists(self) -> bool:
        """Verifica se esiste una configurazione"""
        return self.config_path.exists()
    
    def create_default_config(self):
        """Crea una configurazione di default"""
        if self.default_config_path.exists():
            shutil.copy(self.default_config_path, self.config_path)
        else:
            # Fallback se il file template non esiste
            default = self._get_minimal_config()
            self.save_config(default)
    
    def create_config(self, config_data: Dict[str, Any]):
        """Crea una configurazione custom"""
        # Carica default e merge con custom
        if self.default_config_path.exists():
            with open(self.default_config_path) as f:
                config = yaml.safe_load(f)
        else:
            config = self._get_minimal_config()
        
        # Merge ricorsivo
        self._deep_merge(config, config_data)
        self.save_config(config)
    
    def load_config(self) -> Dict[str, Any]:
        """Carica la configurazione"""
        if not self.config_path.exists():
            raise FileNotFoundError("Configuration file not found. Run 'akaion init' first.")
        
        with open(self.config_path) as f:
            return yaml.safe_load(f)
    
    def save_config(self, config: Dict[str, Any]):
        """Salva la configurazione"""
        with open(self.config_path, "w") as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)
    
    def reset_config(self):
        """Reset alla configurazione di default"""
        if self.config_path.exists():
            self.config_path.unlink()
        self.create_default_config()
    
    def get(self, key: str, default: Any = None) -> Any:
        """Recupera un valore dalla config (supporta dot notation)"""
        config = self.load_config()
        
        keys = key.split(".")
        value = config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def set(self, key: str, value: Any):
        """Imposta un valore nella config (supporta dot notation)"""
        config = self.load_config()
        
        keys = key.split(".")
        current = config
        
        for k in keys[:-1]:
            if k not in current:
                current[k] = {}
            current = current[k]
        
        current[keys[-1]] = value
        self.save_config(config)
    
    @staticmethod
    def _deep_merge(base: Dict, update: Dict) -> Dict:
        """Merge ricorsivo di due dict"""
        for key, value in update.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                ConfigManager._deep_merge(base[key], value)
            else:
                base[key] = value
        return base
    
    @staticmethod
    def _get_minimal_config() -> Dict[str, Any]:
        """Configurazione minimale di fallback"""
        return {
            "cloud": {
                "api_url": "https://api.akaion.com",
                "polling_interval": 5,
                "timeout": 30
            },
            "ai": {
                "provider": "akaion",
                "temperature": 0.7,
                "max_tokens": 4000
            },
            "permissions": {
                "filesystem": {
                    "allowed_paths": ["~/Documents", "~/Downloads"],
                    "denied_paths": ["~/.ssh"],
                    "max_file_size_mb": 100
                },
                "shell": {
                    "enabled": True,
                    "allowed_commands": ["ls", "cat", "grep", "find", "git"]
                },
                "network": {
                    "enabled": True
                }
            },
            "tools": {
                "enabled": ["filesystem", "shell", "document_reader", "explorer"]
            },
            "logging": {
                "level": "INFO",
                "file": "logs/runner.log"
            },
            "runner": {
                "mode": "daemon",
                "max_concurrent_tasks": 3,
                "retry_attempts": 3
            }
        }
