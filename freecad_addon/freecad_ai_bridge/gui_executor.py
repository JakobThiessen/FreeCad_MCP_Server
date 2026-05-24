"""GUI Thread Executor - dispatches operations to FreeCAD's main thread.

FreeCAD's GUI is Qt-based and single-threaded. All document/GUI operations
must run on the main thread. This module uses a queue + QTimer pattern to
safely dispatch operations from the RPC thread to the GUI thread.
"""

import json
import queue
import threading
import traceback
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
        self.result = None
        self.error = None
        self.done = threading.Event()


class GuiExecutor:
    """Executes operations on the FreeCAD GUI thread via QTimer dispatch."""

    def __init__(self):
        self._task_queue: queue.Queue[_Task] = queue.Queue()
        self._timer = None
        self._running = False

    def start(self):
        """Start the QTimer-based processing loop."""
        self._running = True
        self._schedule_next()

    def stop(self):
        """Stop processing."""
        self._running = False

    def _schedule_next(self):
        """Schedule the next queue check on the GUI thread."""
        if self._running:
            QtCore.QTimer.singleShot(50, self._process_queue)

    def _process_queue(self):
        """Process all pending tasks (runs on GUI thread)."""
        processed = 0
        while not self._task_queue.empty() and processed < 10:
            try:
                task = self._task_queue.get_nowait()
            except queue.Empty:
                break

            try:
                if task.code is not None:
                    task.result = self._execute_code(task.code)
                elif task.module is not None:
                    task.result = self._execute_function(task.module, task.function, task.args_json)
            except Exception as e:
                task.error = f"{type(e).__name__}: {e}\n{traceback.format_exc()}"
            finally:
                task.done.set()
                processed += 1

        self._schedule_next()

    def _execute_code(self, code: str) -> Any:
        """Execute arbitrary Python code and return result."""
        import FreeCAD
        import FreeCADGui
        global_ns = {"__builtins__": __builtins__, "FreeCAD": FreeCAD, "FreeCADGui": FreeCADGui}
        local_ns = {}
        exec(code, global_ns, local_ns)

        # Recompute and update GUI
        if FreeCAD.ActiveDocument:
            FreeCAD.ActiveDocument.recompute()
        if FreeCAD.GuiUp:
            FreeCADGui.updateGui()

        return local_ns.get("result", local_ns.get("__result__", None))

    def _execute_function(self, module: str, function: str, args_json: str) -> Any:
        """Execute a specific function from a module."""
        import importlib

        mod = importlib.import_module(module)
        func = getattr(mod, function)
        args = json.loads(args_json) if args_json else []

        if isinstance(args, dict):
            result = func(**args)
        elif isinstance(args, list):
            result = func(*args)
        else:
            result = func(args)

        # Recompute and update GUI
        if FreeCAD.ActiveDocument:
            FreeCAD.ActiveDocument.recompute()
        if FreeCAD.GuiUp:
            FreeCADGui.updateGui()

        return result

    def run(self, code: str, timeout: float = 30.0) -> Any:
        """Submit code for execution on GUI thread and wait for result."""
        task = _Task(code=code)
        self._task_queue.put(task)

        if not task.done.wait(timeout):
            raise TimeoutError(f"GUI thread execution timed out after {timeout}s")

        if task.error:
            raise RuntimeError(task.error)
        return task.result

    def run_function(self, module: str, function: str, args_json: str, timeout: float = 30.0) -> Any:
        """Submit a function call for execution on GUI thread and wait for result."""
        task = _Task(module=module, function=function, args_json=args_json)
        self._task_queue.put(task)

        if not task.done.wait(timeout):
            raise TimeoutError(f"GUI thread execution timed out after {timeout}s")

        if task.error:
            raise RuntimeError(task.error)
        return task.result
