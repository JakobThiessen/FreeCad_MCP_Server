"""GUI Thread Executor - dispatches operations to FreeCAD's main thread.

FreeCAD's GUI is Qt-based and single-threaded. All document/GUI operations
must run on the main thread. This module uses a queue + QTimer pattern to
safely dispatch operations from the RPC thread to the GUI thread.
"""

import json
import inspect
import queue
from contextlib import nullcontext
from concurrent.futures import Future, TimeoutError as FutureTimeoutError
from typing import Any

try:
    from PySide6 import QtCore
except ImportError:
    from PySide2 import QtCore

import FreeCAD
import FreeCADGui


class _Task:
    """A single operation to execute on the GUI thread."""

    def __init__(self, code: str = None, module: str = None, function: str = None, args_json: str = None):
        self.code = code
        self.module = module
        self.function = function
        self.args_json = args_json
        self.future = Future()


class GuiExecutor:
    """Executes operations on the FreeCAD GUI thread via QTimer dispatch."""

    def __init__(self):
        self._task_queue: queue.Queue[_Task] = queue.Queue()
        self._timer = None
        self._running = False
        self._transaction_owner = None

    def start(self):
        """Start the QTimer-based processing loop."""
        self._running = True
        self._schedule_next()

    def stop(self):
        """Stop processing."""
        self._running = False
        while True:
            try:
                task = self._task_queue.get_nowait()
            except queue.Empty:
                break
            if not task.future.done():
                task.future.set_exception(RuntimeError("GUI executor stopped"))

    def _schedule_next(self):
        """Schedule the next queue check on the GUI thread."""
        if self._running:
            QtCore.QTimer.singleShot(50, self._process_queue)

    def _process_queue(self):
        """Process all pending tasks (runs on GUI thread)."""
        if not self._running:
            return
        processed = 0
        while not self._task_queue.empty() and processed < 10:
            try:
                task = self._task_queue.get_nowait()
            except queue.Empty:
                break

            processed += 1
            if not task.future.set_running_or_notify_cancel():
                continue
            try:
                if task.code is not None:
                    result = self._execute_code(task.code)
                elif task.module is not None:
                    result = self._execute_function(task.module, task.function, task.args_json)
                else:
                    raise ValueError("Task has no code or function")
                task.future.set_result(result)
            except Exception as e:
                task.future.set_exception(e)

        self._schedule_next()

    def _execute_code(self, code: str) -> Any:
        """Execute arbitrary Python code and return result."""
        import FreeCAD
        import FreeCADGui
        global_ns = {"__builtins__": __builtins__, "FreeCAD": FreeCAD, "FreeCADGui": FreeCADGui}
        exec(code, global_ns, global_ns)

        # Recompute and update GUI
        if FreeCAD.ActiveDocument:
            FreeCAD.ActiveDocument.recompute()
        if FreeCAD.GuiUp:
            FreeCADGui.updateGui()

        return global_ns.get("result", global_ns.get("__result__", None))

    def _execute_function(self, module: str, function: str, args_json: str) -> Any:
        """Execute a specific function from a module."""
        from freecad_ai_bridge.security import resolve_function
        from freecad_ai_bridge.contracts import BridgeError
        from freecad_ai_bridge.transactions import document_transaction

        func = resolve_function(module, function)
        args = json.loads(args_json) if args_json else []

        if module == "freecad_ai_bridge.operations" and function in {"get_capabilities", "resolve_reference", "execute_batch"}:
            if not isinstance(args, dict):
                raise ValueError("Contract operation arguments must be an object")
            return func(**args)

        if isinstance(args, dict):
            bound = inspect.signature(func).bind(**args)
        elif isinstance(args, list):
            bound = inspect.signature(func).bind(*args)
        else:
            raise BridgeError("invalid_arguments", "Function arguments must be an object or array")
        doc_name = bound.arguments.get("doc_name")
        if function in {"save_document", "close_document"}:
            doc_name = bound.arguments.get("name")
        doc = FreeCAD.listDocuments().get(doc_name) if doc_name is not None else FreeCAD.ActiveDocument
        if doc_name is not None and doc is None:
            raise BridgeError("document_not_found", f"Document '{doc_name}' is not open", [{"document": doc_name}])
        mutates = (
            module in {"freecad_ai_bridge.part_ops", "freecad_ai_bridge.partdesign_ops", "freecad_ai_bridge.sketcher_ops"}
            and function != "get_sketch_info"
        ) or function in {"delete_object", "set_visibility", "set_color", "set_transparency", "import_step", "import_stl"}
        if module == "freecad_ai_bridge.document_ops":
            mutates = function not in {"inspect_document", "activate_document", "get_properties",
                                       "save_document_safe", "close_document_safe", "get_expressions",
                                       "read_spreadsheet", "get_dependencies", "preview_delete"}
            if doc_name is None:
                raise BridgeError("invalid_arguments", "An explicit document Name is required")
            if doc and function in {"save_document_safe", "close_document_safe", "activate_document"} and doc.HasPendingTransaction:
                raise BridgeError("transaction_conflict", "Document has an open transaction owned by another caller",
                                  [{"document": doc.Name}])
        if doc and function in {"undo", "redo", "save_document", "close_document"} and doc.HasPendingTransaction:
            raise BridgeError("transaction_conflict", "Document has an open transaction owned by another caller",
                              [{"document": doc.Name}])
        if mutates and doc is None:
            raise BridgeError("document_not_found", "No active or explicit document")
        if doc:
            for key in ("obj_name", "base_name", "tool_name", "sketch_name", "feature_name", "spine_name", "body_name"):
                name = bound.arguments.get(key)
                if name is not None and doc.getObject(name) is None:
                    raise BridgeError("object_not_found", f"Object '{name}' is not in '{doc.Name}'",
                                      [{"document": doc.Name, "object": name}])
        context = document_transaction(doc, f"MCP: {function}", self._transaction_owner is doc) if mutates else nullcontext()
        with context:
            result = func(*bound.args, **bound.kwargs)
            if mutates:
                doc.recompute()
                if module == "freecad_ai_bridge.document_ops":
                    from freecad_ai_bridge.document_ops import _validate_document

                    _validate_document(doc)
                if isinstance(result, dict) and result.get("shape_valid") is False:
                    raise RuntimeError("Operation produced invalid geometry")
                json.dumps(result, allow_nan=False)
        if mutates and FreeCAD.GuiUp:
            FreeCADGui.updateGui()
        return result

    def run(self, code: str, timeout: float = 30.0) -> Any:
        """Submit code for execution on GUI thread and wait for result."""
        return self._submit(_Task(code=code), timeout)

    def run_function(self, module: str, function: str, args_json: str, timeout: float = 30.0) -> Any:
        """Submit a function call for execution on GUI thread and wait for result."""
        return self._submit(_Task(module=module, function=function, args_json=args_json), timeout)

    def _submit(self, task, timeout):
        if not self._running:
            raise RuntimeError("GUI executor is not running")
        self._task_queue.put(task)
        try:
            return task.future.result(timeout)
        except FutureTimeoutError as error:
            cancelled = task.future.cancel()
            status = "cancelled before execution" if cancelled else "already running; it may still complete"
            raise TimeoutError(f"GUI execution timed out after {timeout}s ({status})") from error
