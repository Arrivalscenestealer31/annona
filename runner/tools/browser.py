"""
Browser Tool

Tool per operazioni web/browser (semplificato).
"""

from typing import Any, Dict

import httpx
from loguru import logger

from .base import Tool


class BrowserTool(Tool):
    """Tool per operazioni browser/web"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(
            name="browser",
            description="Fetch web pages and perform HTTP requests",
            parameters={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "URL to fetch"},
                    "method": {
                        "type": "string",
                        "enum": ["GET", "POST"],
                        "description": "HTTP method",
                    },
                    "data": {"type": "object", "description": "Data for POST requests"},
                },
                "required": ["url"],
            },
        )
        self.config = config
        self.timeout = config.get("tools", {}).get("browser", {}).get("timeout", 30)

    def execute(
        self, url: str, method: str = "GET", data: Dict[str, Any] = None, **kwargs
    ) -> Dict[str, Any]:
        """Perform an HTTP request."""
        logger.info(f"HTTP {method} request to {url}")

        try:
            with httpx.Client(timeout=self.timeout) as client:
                if method == "GET":
                    response = client.get(url)
                elif method == "POST":
                    response = client.post(url, json=data)
                else:
                    raise ValueError(f"Unsupported method: {method}")

                return {
                    "success": True,
                    "status_code": response.status_code,
                    "content": response.text,
                    "headers": dict(response.headers),
                }

        except Exception as e:
            logger.error(f"HTTP request error: {e}")
            return {"success": False, "error": str(e)}
