"""
Base Tool Class
"""
from typing import Dict, Any


class Tool:
    """Base class per un tool"""
    
    def __init__(self, name: str, description: str, parameters: Dict[str, Any]):
        self.name = name
        self.description = description
        self.parameters = parameters
    
    def execute(self, **kwargs) -> Any:
        """Esegue il tool"""
        raise NotImplementedError
