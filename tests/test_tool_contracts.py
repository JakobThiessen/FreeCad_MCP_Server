import ast
import asyncio
import importlib
import json
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from freecad_mcp import server
from freecad_mcp.connection import FreeCADRemoteError


class ToolContractTests(unittest.TestCase):
    def test_stage5_schemas_and_forwarding(self):
        for tool, arguments in [
            ("sketch_copy", {"sketch_name": "Sketch", "geometry_indices": [], "offset_x": 1, "offset_y": 2}),
            ("sketch_copy", {"sketch_name": "Sketch", "geometry_indices": list(range(101)), "offset_x": 1, "offset_y": 2}),
            ("sketch_add_external", {"sketch_name": "Sketch", "selection": {"document": "Doc", "object": "Box", "subelement": "Edge1"}}),
        ]:
            with self.subTest(tool=tool), patch.object(server._conn, "call_function") as call:
                with self.assertRaises(Exception):
                    asyncio.run(server.mcp.call_tool(tool, arguments))
                call.assert_not_called()
        selection = {"document": "Doc", "object": "Box", "revision": "session:1", "subelement": "Edge1"}
        with patch.object(server._conn, "call_function", return_value={"geometry_index": -3}) as call:
            result = json.loads(server.sketch_add_external("Sketch", server.SubelementSelection(**selection), doc_name="Doc"))
            self.assertEqual(result["geometry_index"], -3)
            call.assert_called_once_with("freecad_ai_bridge.sketcher_ops", "add_external_geometry",
                                         sketch_name="Sketch", selection=selection,
                                         defining=False, intersection=False, doc_name="Doc")
        with patch.object(server._conn, "call_function", return_value={"constraint_index": 0}) as call:
            server.sketch_set_constraint_mode("Sketch", 0, active=False, doc_name="Doc")
            call.assert_called_once_with("freecad_ai_bridge.sketcher_ops", "set_constraint_mode",
                                         sketch_name="Sketch", constraint_idx=0, active=False, doc_name="Doc")

    def test_stage4_schemas_and_forwarding(self):
        for tool, arguments in [("list_subelements", {"doc_name": "Doc", "obj_name": "Box", "kind": "solid"}),
                                 ("list_subelements", {"doc_name": "Doc", "obj_name": "Box", "kind": "edge", "limit": 257}),
                                 ("select_subelement", {"doc_name": "Doc", "obj_name": "Box", "kind": "face", "filters": {"unknown": 1}}),
                                 ("select_subelement", {"doc_name": "Doc", "obj_name": "Box", "kind": "face", "filters": {"position": [1, 2]}}),
                                 ("resolve_subelement", {"selection": {"document": "Doc", "object": "Box", "subelement": "Face1"}})]:
            with self.subTest(tool=tool, arguments=arguments), patch.object(server._conn, "call_function") as call:
                with self.assertRaises(Exception):
                    asyncio.run(server.mcp.call_tool(tool, arguments))
                call.assert_not_called()
        selection = {"document": "Doc", "object": "Box", "revision": "session:1", "subelement": "Face1"}
        with patch.object(server._conn, "call_function", return_value={"selection": selection}) as call:
            response = server.resolve_subelement(server.SubelementSelection(**selection))
            self.assertEqual(response.status, "success")
            call.assert_called_once_with("freecad_ai_bridge.geometry_ops", "resolve_subelement", selection=selection)
        with patch.object(server._conn, "call_function", side_effect=FreeCADRemoteError("Changed", "stale_selection", {"state": "unchanged"})):
            response = server.resolve_subelement(server.SubelementSelection(**selection))
            self.assertEqual(response.error.code, "stale_selection")

    def test_stage4_image_and_measurement_contracts(self):
        target = {"document": "Doc", "object": "Box"}
        for tool, arguments in [("measure_distance", {"first": target, "second": dict(target, subelement="Edge1")}),
                                 ("check_interference", {"first": target, "second": target, "volume_tolerance": -1}),
                                 ("capture_view", {"doc_name": "Doc", "width": 4096}),
                                 ("capture_view", {"doc_name": "Doc", "view": "unknown"}),
                                 ("highlight_subelements", {"doc_name": "Doc", "selections": [target]})]:
            with self.subTest(tool=tool), patch.object(server._conn, "call_function") as call:
                with self.assertRaises(Exception):
                    asyncio.run(server.mcp.call_tool(tool, arguments))
                call.assert_not_called()
        result = {"reference": {"document": "Doc"}, "width": 320, "height": 240, "image_base64": "aW1hZ2U="}
        with patch.object(server._conn, "call_function", return_value=result):
            contents = asyncio.run(server.mcp.call_tool("capture_view", {"doc_name": "Doc"}))
            self.assertEqual(contents[0].type, "text")
            self.assertEqual(json.loads(contents[0].text)["status"], "success")
            self.assertEqual(contents[1].type, "image")
            self.assertEqual(contents[1].mimeType, "image/png")

    def test_stage3_schemas_and_null_forwarding(self):
        for tool, arguments in [("inspect_document", {}), ("get_properties", {"doc_name": "Doc", "obj_name": ""}),
                                 ("save_document_safe", {"doc_name": "Doc", "overwrite": "yes"}),
                                 ("close_document_safe", {"doc_name": "Doc", "discard_changes": 1}),
                                 ("create_container", {"doc_name": "Doc", "name": "Body", "kind": "arbitrary"}),
                                 ("set_properties", {"doc_name": "Doc", "obj_name": "Box", "values": {}}),
                                 ("set_spreadsheet_cells", {"doc_name": "Doc", "obj_name": "Sheet", "cells": {"A1": 42}})]:
            with self.subTest(tool=tool), patch.object(server._conn, "call_function") as call:
                with self.assertRaises(Exception):
                    asyncio.run(server.mcp.call_tool(tool, arguments))
                call.assert_not_called()
        with patch.object(server._conn, "call_function", return_value={"reference": {"document": "Doc", "object": "Box"}}) as call:
            response = server.set_expression("Doc", "Box", "Length", None)
            self.assertEqual(response.status, "success")
            call.assert_called_once_with("freecad_ai_bridge.document_ops", "set_expression", doc_name="Doc", obj_name="Box",
                                         property_name="Length", expression=None)
        with patch.object(server._conn, "call_function", side_effect=FreeCADRemoteError(
                "Denied", "property_read_only", {"state": "rolled_back"})):
            response = server.set_properties("Doc", "Box", {"Shape": "invalid"})
            self.assertEqual(response.error.code, "property_read_only")
            self.assertEqual(response.error.state, "rolled_back")

    def test_every_parameter_has_metadata_and_units_match_implementation(self):
        tools = {tool.name: tool for tool in asyncio.run(server.mcp.list_tools())}
        for tool in tools.values():
            for name, schema in tool.inputSchema.get("properties", {}).items():
                with self.subTest(tool=tool.name, parameter=name):
                    self.assertTrue(schema.get("description"))
        for tool, parameter, unit in [("sketch_add_arc", "start_angle", "rad"),
                                       ("sketch_add_ellipse", "angle", "rad"),
                                       ("sketch_constrain_angle", "angle", "deg"),
                                       ("part_box", "length", "mm"), ("screenshot", "width", "px")]:
            self.assertEqual(tools[tool].inputSchema["properties"][parameter]["x-unit"], unit)
        self.assertIn("parent_local", tools["move_object"].inputSchema["properties"]["dx"]["x-coordinate-system"])

    def test_contract_schemas_and_validation(self):
        tools = {tool.name: tool for tool in asyncio.run(server.mcp.list_tools())}
        schema = tools["resolve_reference"].inputSchema
        self.assertEqual(schema["required"], ["doc_name"])
        self.assertEqual(schema["properties"]["doc_name"]["minLength"], 1)
        self.assertIn("status", tools["resolve_reference"].outputSchema["properties"])
        for arguments in [{}, {"doc_name": ""}, {"doc_name": " "}, {"doc_name": 42},
                          {"doc_name": "Doc", "obj_name": ""}, {"doc_name": "Doc", "obj_name": 42}]:
            with self.subTest(arguments=arguments), patch.object(server, "_call") as call:
                with self.assertRaises(Exception):
                    asyncio.run(server.mcp.call_tool("resolve_reference", arguments))
                call.assert_not_called()

    def test_contract_results_and_errors(self):
        result = {"reference": {"document": "Doc", "object": "Box"}, "type": "Part::Box", "label": "Box label"}
        with patch.object(server, "_call", return_value=result) as call:
            response = server.resolve_reference("Doc", "Box")
            call.assert_called_once_with("freecad_ai_bridge.operations", "resolve_reference", doc_name="Doc", obj_name="Box")
            self.assertEqual(response.status, "success")
            self.assertEqual(json.loads(response.model_dump_json())["references"][0]["object"], "Box")
        details = {"message": "Missing", "cause": "BridgeError", "state": "unchanged",
                   "references": [{"document": "Missing"}]}
        with patch.object(server, "_call", side_effect=FreeCADRemoteError("Missing", "document_not_found", details)):
            response = server.resolve_reference("Missing")
            self.assertEqual(response.error.code, "document_not_found")
            self.assertEqual(response.error.state, "unchanged")
        with patch.object(server, "_call", side_effect=ConnectionError("Offline")):
            response = server.get_capabilities()
            self.assertEqual(response.error.code, "transport_error")
            self.assertFalse(response.error.retryable)

    def test_batch_schema_rejects_unknown_steps_and_nonboolean_flags(self):
        arguments = {"steps": [{"id": "box", "operation": "part_box", "doc_name": "Doc",
                                "arguments": {"length": 1, "width": 1, "height": 1}}]}
        for override in [{"steps": []}, {"atomic": "false"}, {"preview": 1},
                         {"steps": [dict(arguments["steps"][0], extra="not allowed")]},
                         {"steps": [dict(arguments["steps"][0], operation="execute_python")]}]:
            with self.subTest(override=override), patch.object(server, "_call") as call:
                with self.assertRaises(Exception):
                    asyncio.run(server.mcp.call_tool("execute_batch", dict(arguments, **override)))
                call.assert_not_called()

    def test_exact_references_in_two_documents(self):
        first = Mock(Name="First", Label="Same label")
        second = Mock(Name="Second", Label="Same label")
        first.getObject.side_effect = lambda name: types.SimpleNamespace(Label="First box", TypeId="Part::Box") if name == "Box" else None
        second.getObject.side_effect = lambda name: types.SimpleNamespace(Label="Second box", TypeId="Part::Box") if name == "Box" else None
        freecad = types.SimpleNamespace(ActiveDocument=second, listDocuments=lambda: {"First": first, "Second": second})
        with patch.dict(sys.modules, {"FreeCAD": freecad, "FreeCADGui": types.ModuleType("FreeCADGui")}), \
                patch.object(sys, "path", [str(ROOT / "freecad_addon"), *sys.path]):
            operations = importlib.import_module("freecad_ai_bridge.operations")
            for name, label in [("First", "First box"), ("Second", "Second box")]:
                result = operations.resolve_reference(name, "Box")
                self.assertEqual(result["reference"], {"document": name, "object": "Box"})
                self.assertEqual(result["label"], label)
            for document, obj, code in [("Same label", None, "document_not_found"),
                                        ("First", "First box", "object_not_found"),
                                        ("Missing", "Box", "document_not_found"),
                                        ("", None, "invalid_arguments"), ("First", 42, "invalid_arguments")]:
                with self.subTest(document=document, object=obj), self.assertRaises(ValueError) as caught:
                    operations.resolve_reference(document, obj)
                self.assertEqual(caught.exception.code, code)
            first.recompute.assert_not_called()
            second.recompute.assert_not_called()
            self.assertIs(freecad.ActiveDocument, second)

    def test_all_rpc_targets_exist_and_accept_forwarded_arguments(self):
        tree = ast.parse((ROOT / "src/freecad_mcp/server.py").read_text(encoding="utf-8"))
        checked = 0
        for call in ast.walk(tree):
            if not isinstance(call, ast.Call) or not isinstance(call.func, ast.Name) or call.func.id not in {"_call", "_document_call", "_geometry_call"}:
                continue
            module_name, function_name = ([argument.value for argument in call.args[:2]] if call.func.id == "_call"
                                          else ("freecad_ai_bridge.geometry_ops" if call.func.id == "_geometry_call" else "freecad_ai_bridge.document_ops", call.args[0].value))
            path = ROOT / "freecad_addon" / (module_name.replace(".", "/") + ".py")
            module = ast.parse(path.read_text(encoding="utf-8"))
            functions = {node.name: node for node in module.body if isinstance(node, ast.FunctionDef)}
            with self.subTest(target=f"{module_name}.{function_name}"):
                self.assertIn(function_name, functions)
                target = functions[function_name]
                parameters = [argument.arg for argument in target.args.args]
                forwarded = {keyword.arg for keyword in call.keywords}
                required = set(parameters[:len(parameters) - len(target.args.defaults)])
                self.assertTrue(forwarded <= set(parameters), forwarded - set(parameters))
                self.assertTrue(required <= forwarded, required - forwarded)
            checked += 1
        self.assertGreater(checked, 70)

    def test_all_public_operations_have_tools(self):
        tree = ast.parse((ROOT / "src/freecad_mcp/server.py").read_text(encoding="utf-8"))
        targets = {
            (call.args[0].value, call.args[1].value)
            for call in ast.walk(tree)
            if isinstance(call, ast.Call) and isinstance(call.func, ast.Name) and call.func.id == "_call"
        }
        targets.update(("freecad_ai_bridge.document_ops", call.args[0].value) for call in ast.walk(tree)
                   if isinstance(call, ast.Call) and isinstance(call.func, ast.Name) and call.func.id == "_document_call")
        targets.update(("freecad_ai_bridge.geometry_ops", call.args[0].value) for call in ast.walk(tree)
               if isinstance(call, ast.Call) and isinstance(call.func, ast.Name) and call.func.id == "_geometry_call")
        for path in (ROOT / "freecad_addon/freecad_ai_bridge").glob("*_ops.py"):
            module_name = f"freecad_ai_bridge.{path.stem}"
            module = ast.parse(path.read_text(encoding="utf-8"))
            for node in module.body:
                if isinstance(node, ast.FunctionDef) and not node.name.startswith("_"):
                    with self.subTest(function=node.name):
                        self.assertIn((module_name, node.name), targets)

    def test_new_tools_registered_with_mcp(self):
        tools = asyncio.run(server.mcp.list_tools())
        names = {tool.name for tool in tools}
        self.assertEqual(len(names), len(tools))
        self.assertTrue({"partdesign_subtractive_loft", "partdesign_subtractive_pipe",
                         "part_fillet", "part_chamfer", "export_obj"} <= names)

    def test_screenshot_returns_native_mcp_image(self):
        with patch.object(server, "_call", return_value={"image_base64": "aW1hZ2U="}):
            image = server.screenshot().to_image_content()
            self.assertEqual(image.type, "image")
            self.assertEqual(image.mimeType, "image/png")
            self.assertEqual(image.data, "aW1hZ2U=")


if __name__ == "__main__":
    unittest.main()