import importlib
import inspect
import json
from pathlib import Path
import sys
import types
import unittest
from concurrent.futures import Future
from unittest.mock import Mock, patch


ADDON_PATH = str(Path(__file__).resolve().parents[1] / "freecad_addon")


class GuiExecutorTests(unittest.TestCase):
    def test_document_validation_detects_failed_recompute(self):
        obj = Mock(Name="Pad", State=["Invalid"])
        obj.Document.Name = "Doc"
        obj.getStatusString.return_value = "Broken expression"
        document = Mock(Name="Doc", HasPendingTransaction=False, Objects=[obj])
        document.getObject.return_value = obj
        with patch.dict(sys.modules, {"FreeCAD": types.SimpleNamespace(), "FreeCADGui": types.SimpleNamespace()}), \
                patch.object(sys, "path", [ADDON_PATH, *sys.path]):
            operations = importlib.import_module("freecad_ai_bridge.document_ops")
            transactions = importlib.import_module("freecad_ai_bridge.transactions")
            with self.assertRaises(ValueError) as caught:
                with transactions.document_transaction(document, "edit"):
                    document.recompute()
                    operations._validate_document(document)
            self.assertEqual(caught.exception.code, "recompute_failed")
            self.assertEqual(caught.exception.bridge_state, "rolled_back")
            document.abortTransaction.assert_called_once()
            document.commitTransaction.assert_not_called()
            obj.State = ["Up-to-date"]
            operations._validate_document(document)

    def test_foreign_transaction_is_never_adopted(self):
        document = Mock(Name="Doc", HasPendingTransaction=True)
        freecad = types.SimpleNamespace(ActiveDocument=document, listDocuments=lambda: {"Doc": document})
        modules = {"FreeCAD": freecad, "FreeCADGui": Mock(),
                   "PySide6": types.SimpleNamespace(QtCore=types.SimpleNamespace())}
        with patch.dict(sys.modules, modules), patch.object(sys, "path", [ADDON_PATH, *sys.path]):
            sys.modules.pop("freecad_ai_bridge.gui_executor", None)
            executor_module = importlib.import_module("freecad_ai_bridge.gui_executor")
            with patch("freecad_ai_bridge.security.resolve_function") as resolve:
                resolve.return_value.__signature__ = inspect.Signature([
                    inspect.Parameter("doc_name", inspect.Parameter.KEYWORD_ONLY)])
                with self.assertRaises(ValueError) as caught:
                    executor_module.GuiExecutor()._execute_function(
                        "freecad_ai_bridge.part_ops", "make_box", '{"doc_name": "Doc"}')
                self.assertEqual(caught.exception.code, "transaction_conflict")
                resolve.return_value.assert_not_called()
                document.openTransaction.assert_not_called()
                document.commitTransaction.assert_not_called()
                document.abortTransaction.assert_not_called()

    def test_owned_transaction_rolls_back_geometry_and_visibility(self):
        with patch.object(sys, "path", [ADDON_PATH, *sys.path]):
            transaction_module = importlib.import_module("freecad_ai_bridge.transactions")
        obj = Mock(Name="Box")
        obj.ViewObject.Visibility = True
        document = Mock(Name="Doc", HasPendingTransaction=False, Objects=[obj])
        document.getObject.return_value = obj
        document.abortTransaction.side_effect = lambda: self.assertTrue(obj.ViewObject.Visibility)
        with self.assertRaisesRegex(RuntimeError, "failed") as caught:
            with transaction_module.document_transaction(document, "test"):
                obj.ViewObject.Visibility = False
                raise RuntimeError("failed")
        document.openTransaction.assert_called_once_with("test")
        document.abortTransaction.assert_called_once()
        document.commitTransaction.assert_not_called()
        self.assertTrue(obj.ViewObject.Visibility)
        self.assertEqual(caught.exception.bridge_state, "rolled_back")

    def test_contract_reads_preserve_document_state_and_error_identity(self):
        document = Mock(Name="Doc", Label="Document")
        document.getObject.return_value = None
        freecad = types.SimpleNamespace(
            ActiveDocument=document, GuiUp=True,
            listDocuments=lambda: {"Doc": document}, Version=lambda: ["1", "1", "0", "build"],
        )
        gui = Mock()
        gui.listWorkbenches.return_value = {"PartWorkbench": object()}
        modules = {
            "FreeCAD": freecad, "FreeCADGui": gui,
            "PySide6": types.SimpleNamespace(QtCore=types.SimpleNamespace()),
        }
        with patch.dict(sys.modules, modules), patch.object(sys, "path", [ADDON_PATH, *sys.path]):
            executor_module = importlib.import_module("freecad_ai_bridge.gui_executor")
            rpc_module = importlib.import_module("freecad_ai_bridge.rpc_server")
            executor = executor_module.GuiExecutor()
            result = executor._execute_function("freecad_ai_bridge.operations", "get_capabilities", "{}")
            self.assertEqual(result["freecad_version"], ["1", "1", "0", "build"])
            self.assertTrue(result["features"]["atomic_batch"])
            result = executor._execute_function("freecad_ai_bridge.operations", "resolve_reference", '{"doc_name": "Doc"}')
            self.assertEqual(result["reference"], {"document": "Doc"})
            document.recompute.assert_not_called()
            document.openTransaction.assert_not_called()
            gui.updateGui.assert_not_called()
            executor._running = True
            task = executor_module._Task(module="freecad_ai_bridge.operations", function="resolve_reference",
                                         args_json='{"doc_name": "Doc", "obj_name": "Missing"}')
            executor._task_queue.put(task)
            with patch.object(executor, "_schedule_next"):
                executor._process_queue()
            error = task.future.exception()
            self.assertEqual(error.code, "object_not_found")
            with patch.object(rpc_module, "_executor") as rpc_executor:
                rpc_executor.run_function.side_effect = error
                response = json.loads(rpc_module.FreecadRPCService().execute_function(
                    "freecad_ai_bridge.operations", "resolve_reference", task.args_json))
            self.assertIsInstance(response["error"], str)
            self.assertEqual(response["error_details"]["code"], "object_not_found")
            self.assertEqual(response["error_details"]["references"], [{"document": "Doc", "object": "Missing"}])

    def test_expired_queued_task_never_runs(self):
        freecad = types.SimpleNamespace(ActiveDocument=None, GuiUp=False)
        modules = {
            "FreeCAD": freecad,
            "FreeCADGui": types.ModuleType("FreeCADGui"),
            "PySide6": types.SimpleNamespace(QtCore=types.SimpleNamespace()),
        }
        with patch.dict(sys.modules, modules), patch.object(sys, "path", [ADDON_PATH, *sys.path]):
            sys.modules.pop("freecad_ai_bridge.gui_executor", None)
            executor_module = importlib.import_module("freecad_ai_bridge.gui_executor")
            try:
                executor = executor_module.GuiExecutor()
                executor._running = True
                with self.assertRaisesRegex(TimeoutError, "cancelled before execution"):
                    executor.run("result = 42", timeout=0)
                with patch.object(executor, "_execute_code") as execute, patch.object(executor, "_schedule_next"):
                    executor._process_queue()
                    execute.assert_not_called()
                executor.stop()
                with self.assertRaisesRegex(RuntimeError, "not running"):
                    executor.run("pass")
            finally:
                sys.modules.pop("freecad_ai_bridge.gui_executor", None)

    def test_structured_jobs_are_idempotent_and_cancel_only_queued_work(self):
        freecad = types.SimpleNamespace(ActiveDocument=None, GuiUp=False)
        modules = {
            "FreeCAD": freecad,
            "FreeCADGui": types.ModuleType("FreeCADGui"),
            "PySide6": types.SimpleNamespace(QtCore=types.SimpleNamespace()),
        }
        with patch.dict(sys.modules, modules), patch.object(sys, "path", [ADDON_PATH, *sys.path]):
            for name in ("freecad_ai_bridge.gui_executor", "freecad_ai_bridge.rpc_server"):
                sys.modules.pop(name, None)
            executor_module = importlib.import_module("freecad_ai_bridge.gui_executor")
            rpc_module = importlib.import_module("freecad_ai_bridge.rpc_server")
            executor = executor_module.GuiExecutor()
            executor._running = True
            rpc_module._executor = executor
            rpc_module._jobs.clear()
            service = rpc_module.FreecadRPCService()
            arguments = json.dumps({"steps": [{"id": "box"}], "atomic": True, "preview": False})

            queued = json.loads(service.start_job(
                "freecad_ai_bridge.operations", "execute_batch", arguments))["result"]
            self.assertEqual(queued["status"], "queued")
            cancelled = json.loads(service.cancel_job(queued["job_id"]))["result"]
            self.assertEqual(cancelled["status"], "cancelled")
            self.assertEqual(cancelled["cancellation"], "cancelled")
            with patch.object(executor, "_execute_function") as execute, patch.object(executor, "_schedule_next"):
                executor._process_queue()
                execute.assert_not_called()

            with patch.object(executor, "_execute_function", return_value={"status": "succeeded"}) as execute, \
                    patch.object(executor, "_schedule_next"):
                succeeded = json.loads(service.start_job(
                    "freecad_ai_bridge.operations", "execute_batch", arguments))["result"]
                executor._process_queue()
                first = json.loads(service.get_job(succeeded["job_id"]))["result"]
                second = json.loads(service.get_job(succeeded["job_id"]))["result"]
            self.assertEqual(first, second)
            self.assertEqual(first["status"], "succeeded")
            self.assertEqual(first["result"], {"status": "succeeded"})
            execute.assert_called_once()

            rolled_back_future = Future()
            rolled_back_future.set_result({"status": "rolled_back", "error": {"code": "operation_failed"}})
            rolled_back_id = "00000000-0000-4000-8000-000000000004"
            with rpc_module._jobs_lock:
                rpc_module._jobs[rolled_back_id] = {"future": rolled_back_future, "submitted_at": "now"}
            rolled_back = json.loads(service.get_job(rolled_back_id))["result"]
            self.assertEqual(rolled_back["status"], "failed")
            self.assertEqual(rolled_back["result"]["status"], "rolled_back")

            failed_future = Future()
            failed_future.set_exception(RuntimeError("kernel failed"))
            running_future = Future()
            running_future.set_running_or_notify_cancel()
            failed_id = "00000000-0000-4000-8000-000000000001"
            running_id = "00000000-0000-4000-8000-000000000002"
            with rpc_module._jobs_lock:
                rpc_module._jobs[failed_id] = {"future": failed_future, "submitted_at": "now"}
                rpc_module._jobs[running_id] = {"future": running_future, "submitted_at": "now"}
            failed = json.loads(service.get_job(failed_id))["result"]
            running = json.loads(service.cancel_job(running_id))["result"]
            unknown = json.loads(service.get_job("00000000-0000-4000-8000-000000000003"))["result"]
            self.assertEqual(failed["status"], "failed")
            self.assertEqual(failed["error"]["code"], "operation_failed")
            self.assertEqual(running["status"], "running")
            self.assertEqual(running["cancellation"], "cancel_not_supported")
            self.assertEqual(unknown["status"], "unknown")
            self.assertIsNone(unknown["progress"])

            executor.stop()
            rpc_module._jobs.clear()
            rpc_module._executor = None

    def test_script_functions_and_comprehensions_share_script_namespace(self):
        freecad = types.ModuleType("FreeCAD")
        freecad.ActiveDocument = None
        freecad.GuiUp = False
        modules = {
            "FreeCAD": freecad,
            "FreeCADGui": types.ModuleType("FreeCADGui"),
            "PySide6": types.SimpleNamespace(QtCore=types.SimpleNamespace()),
        }
        with patch.dict(sys.modules, modules), patch.object(sys, "path", [ADDON_PATH, *sys.path]):
            sys.modules.pop("freecad_ai_bridge.gui_executor", None)
            executor_module = importlib.import_module("freecad_ai_bridge.gui_executor")
            try:
                executor = executor_module.GuiExecutor()
                result = executor._execute_code(
                    "import math\n"
                    "radius = 3\n"
                    "def area():\n"
                    "    return math.pi * radius ** 2\n"
                    "result = [area() for index in range(2)]\n"
                )
                self.assertEqual(result, [28.274333882308138] * 2)
                self.assertIsNone(executor._execute_code("pass"))
                self.assertEqual(executor._execute_code("__result__ = 42"), 42)
            finally:
                sys.modules.pop("freecad_ai_bridge.gui_executor", None)


if __name__ == "__main__":
    unittest.main()