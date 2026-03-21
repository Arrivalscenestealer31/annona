"""
Filesystem Tool

Tool per operazioni sul filesystem locale.
"""
from pathlib import Path
from typing import Dict, Any, List
from loguru import logger

from .base import Tool


class FilesystemTool(Tool):
    """Tool per operazioni filesystem"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(
            name="filesystem",
            description="Perform filesystem operations (read, write, list files)",
            parameters={
                "type": "object",
                "properties": {
                    "operation": {
                        "type": "string",
                        "enum": ["read", "write", "list", "exists", "delete"],
                        "description": "Operation to perform"
                    },
                    "path": {
                        "type": "string",
                        "description": "File or directory path"
                    },
                    "content": {
                        "type": "string",
                        "description": "Content to write (for write operation)"
                    }
                },
                "required": ["operation", "path"]
            }
        )
        self.config = config
    
    def execute(self, operation: str, path: str, content: str = None, **kwargs) -> Any:
        """Esegue un'operazione filesystem"""
        target_path = Path(path).expanduser().resolve()
        
        logger.info(f"Filesystem operation: {operation} on {target_path}")
        
        if operation == "read":
            return self._read_file(target_path)
        
        elif operation == "write":
            if content is None:
                raise ValueError("Content required for write operation")
            return self._write_file(target_path, content)
        
        elif operation == "list":
            return self._list_directory(target_path)
        
        elif operation == "exists":
            return self._check_exists(target_path)
        
        elif operation == "delete":
            return self._delete_path(target_path)
        
        else:
            raise ValueError(f"Unknown operation: {operation}")
    
    def _read_file(self, path: Path) -> str:
        """Leggi un file"""
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        
        if not path.is_file():
            raise ValueError(f"Not a file: {path}")
        
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    
    def _write_file(self, path: Path, content: str) -> Dict[str, Any]:
        """Scrivi un file"""
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return {
            "success": True,
            "path": str(path),
            "size": len(content)
        }
    
    def _list_directory(self, path: Path) -> List[Dict[str, Any]]:
        """Lista contenuto directory"""
        if not path.exists():
            raise FileNotFoundError(f"Directory not found: {path}")
        
        if not path.is_dir():
            raise ValueError(f"Not a directory: {path}")
        
        items = []
        for item in path.iterdir():
            items.append({
                "name": item.name,
                "path": str(item),
                "type": "file" if item.is_file() else "directory",
                "size": item.stat().st_size if item.is_file() else None
            })
        
        return items
    
    def _check_exists(self, path: Path) -> bool:
        """Controlla se esiste"""
        return path.exists()
    
    def _delete_path(self, path: Path) -> Dict[str, Any]:
        """Elimina file o directory"""
        if not path.exists():
            raise FileNotFoundError(f"Path not found: {path}")
        
        if path.is_file():
            path.unlink()
        elif path.is_dir():
            import shutil
            shutil.rmtree(path)
        
        return {
            "success": True,
            "path": str(path)
        }
