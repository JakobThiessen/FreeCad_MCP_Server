"""XML-RPC Server running inside FreeCAD.

This server runs in a daemon thread and dispatches all FreeCAD operations
to the GUI thread via a queue + QTimer pattern for thread safety.
"""

import json
import queue
import threading
import traceback
from xmlrpc.server import SimpleXMLRPCServer, SimpleXMLRPCRequestHandler

import FreeCAD

from freecad_ai_bridge.gui_executor import GuiExecutor
from freecad_ai_bridge.security import check_command

_server = None
_server_thread = None
_executor = None


class RequestHandler(SimpleXMLRPCRequestHandler):
    rpc_paths = ("/RPC2",)


class FreecadRPCService:
    """XML-RPC service exposed to the MCP server."""

    def ping(self) -> str:
        return "pong"

    def get_version(self) -> str:
        return FreeCAD.Version()[0] + "." + FreeCAD.Version()[1]

    def execute(self, code: str) -> str:
        """Execute Python code on the GUI thread and return the result as JSON."""
        if not check_command(code):
            return json.dumps({"error": "Command blocked by security filter"})

        try:
            result = _executor.run(code)
            return json.dumps({"result": result})
        except Exception as e:
            return json.dumps({"error": str(e), "traceback": traceback.format_exc()})

    def execute_function(self, module: str, function: str, args_json: str) -> str:
        """Execute a specific function with arguments on the GUI thread.

        This is the primary method used by MCP tools - safer than raw code execution.
        """
        if not check_command(f"{module}.{function}"):
            return json.dumps({"error": "Command blocked by security filter"})

        try:
            result = _executor.run_function(module, function, args_json)
            return json.dumps({"result": result})
        except Exception as e:
            return json.dumps({"error": str(e), "traceback": traceback.format_exc()})

    def get_document_state(self) -> str:
        """Get current document and objects state."""
        try:
            result = _executor.run_function(
                "freecad_ai_bridge.operations", "get_document_state", "[]"
            )
            return json.dumps({"result": result})
        except Exception as e:
            return json.dumps({"error": str(e)})


def start_server(host: str = "127.0.0.1", port: int = 9875):
    """Start the XML-RPC server in a daemon thread."""
    global _server, _server_thread, _executor

    if _server is not None:
        FreeCAD.Console.PrintWarning("AI Bridge RPC server already running.\n")
        return

    _executor = GuiExecutor()
    _executor.start()

    try:
        _server = SimpleXMLRPCServer(
            (host, port),
            requestHandler=RequestHandler,
            allow_none=True,
            logRequests=False,
        )
        _server.register_instance(FreecadRPCService())

        _server_thread = threading.Thread(target=_server.serve_forever, daemon=True)
        _server_thread.start()

        FreeCAD.Console.PrintMessage(
            f"AI Bridge RPC server started on {host}:{port}\n"
        )
    except OSError as e:
        FreeCAD.Console.PrintError(f"AI Bridge RPC server failed to start: {e}\n")
        _server = None


def stop_server():
    """Stop the XML-RPC server."""
    global _server, _server_thread, _executor

    if _server is not None:
        _server.shutdown()
        _server = None
        _server_thread = None

    if _executor is not None:
        _executor.stop()
        _executor = None

    FreeCAD.Console.PrintMessage("AI Bridge RPC server stopped.\n")
