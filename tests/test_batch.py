import importlib
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "freecad_addon"))


def step(identifier="box", operation="part_box", document="First", **arguments):
    return {"id": identifier, "operation": operation, "doc_name": document,
            "arguments": arguments or {"length": 10, "width": 10, "height": 10}}


def make_box(length: float, width: float, height: float, name: str = "Box", doc_name: str = None):
    return {"name": name}


def move_object(obj_name: str, dx: float = 0, doc_name: str = None):
    return {"name": obj_name}


class BatchTests(unittest.TestCase):
    def test_empty_or_invalid_part_features_are_not_successful(self):
        modules = {"FreeCAD": Mock(), "FreeCADGui": Mock(), "Part": Mock()}
        with patch.dict(sys.modules, modules):
            sys.modules.pop("freecad_ai_bridge.part_ops", None)
            part = importlib.import_module("freecad_ai_bridge.part_ops")
            for empty, valid in [(True, False), (False, False)]:
                obj = Mock(Name="BadFillet")
                obj.Shape.isNull.return_value = empty
                obj.Shape.isValid.return_value = valid
                with self.subTest(empty=empty, valid=valid), self.assertRaisesRegex(RuntimeError, "empty or invalid"):
                    part._shape_result(obj)

    def setUp(self):
        self.documents = {name: Mock(Name=name, HasPendingTransaction=False, Objects=[])
                          for name in ["First", "Second"]}
        modules = {"FreeCAD": types.SimpleNamespace(listDocuments=lambda: self.documents)}
        self.modules = patch.dict(sys.modules, modules)
        self.modules.start()
        sys.modules.pop("freecad_ai_bridge.batch", None)
        self.batch = importlib.import_module("freecad_ai_bridge.batch")
        self.resolve = patch.object(self.batch, "resolve_function", side_effect=lambda module, function:
                                    move_object if function == "move_object" else make_box)
        self.resolve.start()

    def tearDown(self):
        self.resolve.stop()
        self.modules.stop()

    def test_preview_validates_backward_refs_without_mutations(self):
        result = self.batch.run_batch([step(), step("move", "move_object", obj_name={"$ref": "box"}, dx=2)], preview=True)
        self.assertEqual(result["status"], "preview")
        self.assertEqual([entry["status"] for entry in result["steps"]], ["planned", "planned"])
        for doc in self.documents.values():
            doc.openTransaction.assert_not_called()
            doc.recompute.assert_not_called()

    def test_exact_limit_and_payload_limit(self):
        result = self.batch.run_batch([step(f"box{index}") for index in range(100)], preview=True)
        self.assertEqual(len(result["steps"]), 100)
        with self.assertRaises(ValueError):
            self.batch.run_batch([step(name="large" * 15000, length=1, width=1, height=1)], preview=True)
        for options in [{"atomic": "false"}, {"preview": "true"}]:
            with self.subTest(options=options), self.assertRaises(ValueError):
                self.batch.run_batch([step()], **options)

    def test_success_resolves_names_and_commits_once(self):
        executor = Mock()
        executor._execute_function.side_effect = [{"name": "Box001"}, {"name": "Box001", "position": {"x": 2}}]
        module = types.SimpleNamespace(GuiExecutor=lambda: executor)
        with patch.dict(sys.modules, {"freecad_ai_bridge.gui_executor": module}):
            result = self.batch.run_batch([step(), step("move", "move_object", obj_name={"$ref": "box"}, dx=2)])
        self.assertEqual(result["status"], "succeeded")
        self.assertIn('"obj_name": "Box001"', executor._execute_function.call_args.args[2])
        self.documents["First"].commitTransaction.assert_called_once()
        self.documents["First"].openTransaction.assert_called_once()
        self.assertEqual(result["steps"][1]["references"], [{"document": "First", "object": "Box001"}])
        self.assertIsNone(executor._transaction_owner)

    def test_invalid_batches_fail_before_any_mutation(self):
        cases = [[], [step()] * 101, [step(), step()], [step(operation="execute_python")],
                 [step(operation="export_step")], [step(length=-1, width=1, height=1)],
                 [step(length=True, width=1, height=1)], [step(length="1", width=1, height=1)],
                 [step(length=1, width=1, height=1, unknown=2)],
                 [step("move", "move_object", obj_name={"$ref": "later"}), step("later")],
                 [step(), step("move", "move_object", "Second", obj_name={"$ref": "box"})],
                 [step(), step("other", document="Second")]]
        for steps in cases:
            with self.subTest(steps=steps), self.assertRaises(ValueError):
                self.batch.run_batch(steps)
        for doc in self.documents.values():
            doc.openTransaction.assert_not_called()

    def test_foreign_transaction_and_missing_document_rejected(self):
        self.documents["Second"].HasPendingTransaction = True
        with self.assertRaises(ValueError) as caught:
            self.batch.run_batch([step(), step("other", document="Second")], atomic=False)
        self.assertEqual(caught.exception.code, "transaction_conflict")
        with self.assertRaises(ValueError) as caught:
            self.batch.run_batch([step(document="Missing")])
        self.assertEqual(caught.exception.code, "document_not_found")
        self.documents["First"].openTransaction.assert_not_called()

    def test_atomic_rollback_and_nonatomic_partial_status(self):
        executor = Mock()
        executor._execute_function.side_effect = [{"name": "Box"}, ValueError("bad edge")]
        module = types.SimpleNamespace(GuiExecutor=lambda: executor)
        steps = [step(), step("other"), step("last")]
        with patch.dict(sys.modules, {"freecad_ai_bridge.gui_executor": module}):
            result = self.batch.run_batch(steps)
        self.assertEqual(result["status"], "rolled_back")
        self.assertEqual([entry["status"] for entry in result["steps"]], ["rolled_back", "failed", "not_executed"])
        self.assertIsNone(result["steps"][0]["data"])
        self.documents["First"].abortTransaction.assert_called_once()
        self.documents["First"].commitTransaction.assert_not_called()
        executor._execute_function.side_effect = [{"name": "Box"}, ValueError("bad edge")]
        with patch.dict(sys.modules, {"freecad_ai_bridge.gui_executor": module}):
            result = self.batch.run_batch([step(), step("other", document="Second"), step("last")], atomic=False)
        self.assertEqual(result["status"], "partial")
        self.assertEqual([entry["status"] for entry in result["steps"]], ["succeeded", "failed", "not_executed"])


if __name__ == "__main__":
    unittest.main()
