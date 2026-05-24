"""Connection manager for the FreeCAD XML-RPC bridge.

Handles connection, reconnection, and health checks to the FreeCAD addon.
"""

import json
import time
import xmlrpc.client
from typing import Any


class FreeCADConnection:
    """Manages the XML-RPC connection to the FreeCAD AI Bridge addon."""

    def __init__(self, host: str = "127.0.0.1", port: int = 9875, timeout: float = 30.0):
        self.host = host
        self.port = port
        self.timeout = timeout
        self._proxy = None
        self._connected = False

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}/RPC2"

    def connect(self) -> bool:
        """Establish connection to FreeCAD."""
        try:
            self._proxy = xmlrpc.client.ServerProxy(
                self.url,
                allow_none=True,
            )
            result = self._proxy.ping()
            self._connected = result == "pong"
            return self._connected
        except Exception:
            self._connected = False
            return False

    @property
    def is_connected(self) -> bool:
        """Check if connection is alive."""
        if not self._proxy:
            return False
        try:
            return self._proxy.ping() == "pong"
        except Exception:
            self._connected = False
            return False

    def ensure_connected(self):
        """Ensure connection is established, attempt reconnect if needed."""
        if not self.is_connected:
            if not self.connect():
                raise ConnectionError(
                    f"Cannot connect to FreeCAD AI Bridge at {self.url}. "
                    "Make sure FreeCAD is running with the AI Bridge addon enabled."
                )

    def get_version(self) -> str:
        """Get FreeCAD version."""
        self.ensure_connected()
        return self._proxy.get_version()

    def execute(self, code: str) -> Any:
        """Execute arbitrary Python code in FreeCAD."""
        self.ensure_connected()
        response = self._proxy.execute(code)
        return self._parse_response(response)

    def call_function(self, module: str, function: str, **kwargs) -> Any:
        """Call a specific function in FreeCAD via the RPC bridge.

        This is the primary method for MCP tools - type-safe and validated.
        """
        self.ensure_connected()
        args_json = json.dumps(kwargs)
        response = self._proxy.execute_function(module, function, args_json)
        return self._parse_response(response)

    def get_document_state(self) -> dict:
        """Get current document state."""
        self.ensure_connected()
        response = self._proxy.get_document_state()
        return self._parse_response(response)

    def _parse_response(self, response: str) -> Any:
        """Parse JSON response from RPC server."""
        data = json.loads(response)
        if "error" in data:
            error_msg = data["error"]
            if "traceback" in data:
                error_msg += f"\n{data['traceback']}"
            raise RuntimeError(f"FreeCAD error: {error_msg}")
        return data.get("result")
