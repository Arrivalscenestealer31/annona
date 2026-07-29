"""
Base Tool Class
"""

from typing import Any, Dict


class Tool:
    """Base class per un tool"""

    def __init__(self, name: str, description: str, parameters: Dict[str, Any]):
        self.name = name
        self.description = description
        self.parameters = parameters

    def execute(self, **kwargs) -> Any:
        """Run the tool."""
        raise NotImplementedError
