"""XML-RPC Server running inside FreeCAD.

This server runs in a daemon thread and dispatches all FreeCAD operations
to the GUI thread via a queue + QTimer pattern for thread safety.
"""

import json
import ipaddress
import queue
import threading
import traceback
import uuid
from collections import OrderedDict
from datetime import datetime, timezone
from xmlrpc.server import SimpleXMLRPCServer, SimpleXMLRPCRequestHandler

import FreeCAD

from freecad_ai_bridge.gui_executor import GuiExecutor
from freecad_ai_bridge.contracts import BridgeError, error_response
from freecad_ai_bridge.security import check_command, check_module

_server = None
_server_thread = None
_executor = None
_jobs = OrderedDict()
_jobs_lock = threading.Lock()
_MAX_JOBS = 256


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
        if not check_module(module) or function.startswith("_") or not function.isidentifier():
            return json.dumps(error_response(BridgeError("rpc_not_allowed", "Command blocked by security filter")))

        try:
            result = _executor.run_function(module, function, args_json)
            return json.dumps({"result": result})
        except Exception as e:
            return json.dumps(error_response(e))

    def start_job(self, module: str, function: str, args_json: str) -> str:
        """Queue an allowlisted structured operation and return a durable process-local ID."""
        if (module, function) != ("freecad_ai_bridge.operations", "execute_batch"):
            return json.dumps(error_response(BridgeError(
                "job_operation_not_allowed", "Only structured execute_batch jobs are supported")))
        try:
            arguments = json.loads(args_json)
            if not isinstance(arguments, dict):
                raise BridgeError("invalid_arguments", "Job arguments must be an object")
            normalized = json.dumps(arguments, allow_nan=False)
            future = _executor.submit_function(module, function, normalized)
            job_id = str(uuid.uuid4())
            with _jobs_lock:
                while len(_jobs) >= _MAX_JOBS:
                    removable = next((key for key, value in _jobs.items() if value["future"].done()), None)
                    if removable is None:
                        future.cancel()
                        raise BridgeError("job_capacity", "All job slots are occupied")
                    del _jobs[removable]
                _jobs[job_id] = {
                    "future": future,
                    "submitted_at": datetime.now(timezone.utc).isoformat(),
                }
            return json.dumps({"result": _job_result(job_id)})
        except Exception as e:
            return json.dumps(error_response(e))

    def get_job(self, job_id: str) -> str:
        """Read job state or its cached result without executing it again."""
        return json.dumps({"result": _job_result(job_id)})

    def cancel_job(self, job_id: str) -> str:
        """Cancel a queued job; running GUI/kernel work cannot be interrupted safely."""
        with _jobs_lock:
            record = _jobs.get(job_id)
            if record is None:
                return json.dumps({"result": _unknown_job(job_id)})
            future = record["future"]
            if future.cancel():
                cancellation = "cancelled"
            elif future.running():
                cancellation = "cancel_not_supported"
            else:
                cancellation = "already_finished"
        result = _job_result(job_id)
        result["cancellation"] = cancellation
        return json.dumps({"result": result})

    def get_document_state(self) -> str:
        """Get current document and objects state."""
        try:
            result = _executor.run_function(
                "freecad_ai_bridge.operations", "get_document_state", "[]"
            )
            return json.dumps({"result": result})
        except Exception as e:
            return json.dumps({"error": str(e)})


def _unknown_job(job_id: str) -> dict:
    return {
        "job_id": job_id,
        "status": "unknown",
        "progress": None,
        "result": None,
        "error": None,
        "submitted_at": None,
        "warnings": ["The job is not known to this FreeCAD process; inspect document state before retrying."],
    }


def _job_result(job_id: str) -> dict:
    with _jobs_lock:
        record = _jobs.get(job_id)
        if record is None:
            return _unknown_job(job_id)
        future = record["future"]
        submitted_at = record["submitted_at"]
    result = {
        "job_id": job_id,
        "status": "queued",
        "progress": None,
        "result": None,
        "error": None,
        "submitted_at": submitted_at,
        "warnings": [],
    }
    if future.cancelled():
        result["status"] = "cancelled"
    elif future.running():
        result["status"] = "running"
    elif future.done():
        error = future.exception()
        if error is None:
            outcome = future.result()
            result["result"] = outcome
            if isinstance(outcome, dict) and outcome.get("status") not in {None, "succeeded", "preview"}:
                result["status"] = "failed"
                result["error"] = outcome.get("error") or {
                    "code": "operation_failed",
                    "message": f"Batch finished with status {outcome.get('status')}",
                    "state": "unknown",
                }
            else:
                result["status"] = "succeeded"
        else:
            details = error_response(error)
            result["status"] = "failed"
            result["error"] = details.get("error_details", {
                "code": "operation_failed", "message": str(error), "state": "unknown"})
    return result


def start_server(host: str = "127.0.0.1", port: int = 9875):
    """Start the XML-RPC server in a daemon thread."""
    global _server, _server_thread, _executor

    if host != "localhost" and not ipaddress.ip_address(host).is_loopback:
        raise ValueError("The unauthenticated AI Bridge must bind to a loopback address")

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
        _executor.stop()
        _executor = None


def stop_server():
    """Stop the XML-RPC server."""
    global _server, _server_thread, _executor

    if _server is not None:
        _server.shutdown()
        _server.server_close()
        _server = None
        _server_thread = None

    if _executor is not None:
        _executor.stop()
        _executor = None

    with _jobs_lock:
        _jobs.clear()

    FreeCAD.Console.PrintMessage("AI Bridge RPC server stopped.\n")
