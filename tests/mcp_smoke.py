"""End-to-end MCP stdio test against tests/start_bridge.FCMacro (port 9876)."""

import asyncio
import base64
import ctypes
import hashlib
import json
import math
import os
import platform
from pathlib import Path
import sys
import struct
import tempfile

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


ROOT = Path(__file__).resolve().parents[1]


async def check_contracts(session, call):
    response = await call("get_capabilities")
    capabilities = response.structuredContent
    assert capabilities["status"] == "success", capabilities
    assert capabilities["data"]["contract_version"] == "1.0"
    assert capabilities["data"]["bridge_api_version"] == "0.6.0"
    assert capabilities["data"]["features"]["atomic_batch"] is True
    assert capabilities["data"]["features"]["explicit_reference_resolution"] is True
    assert json.loads(response.content[0].text) == capabilities
    initial = json.loads((await call("get_status")).content[0].text)
    assert not initial["documents"], "Contract live test requires an empty isolated FreeCAD instance"
    documents = []
    try:
        for name, length in [("MCP_Contract_First", 10), ("MCP_Contract_Second", 20)]:
            created = json.loads((await call("create_document", name=name)).content[0].text)
            documents.append(created["name"])
            created_box = json.loads((await call("part_box", name="SameBox", length=length,
                                                width=10, height=10, doc_name=documents[-1])).content[0].text)
            assert created_box["name"] == "SameBox"
        before = json.loads((await call("get_status")).content[0].text)
        measurements = []
        for document, volume in zip(documents, [1000, 2000]):
            resolved = (await call("resolve_reference", doc_name=document, obj_name="SameBox")).structuredContent
            assert resolved["status"] == "success", resolved
            assert resolved["data"]["reference"] == {"document": document, "object": "SameBox"}
            measurements.append(json.loads((await call("measure", obj_name="SameBox", doc_name=document)).content[0].text))
            assert abs(measurements[-1]["volume"] - volume) < 1e-6
        document_result = (await call("resolve_reference", doc_name=documents[0])).structuredContent
        assert document_result["data"]["reference"] == {"document": documents[0]}
        for arguments, code in [({"doc_name": "MCP_Missing_Document"}, "document_not_found"),
                                ({"doc_name": documents[0], "obj_name": "MissingBox"}, "object_not_found")]:
            response = await call("resolve_reference", **arguments)
            assert response.structuredContent["status"] == "error"
            assert response.structuredContent["error"]["code"] == code
            assert response.structuredContent["error"]["state"] == "unchanged"
            assert response.structuredContent["error"]["retryable"] is False
        for arguments in [{}, {"doc_name": ""}, {"doc_name": " "}, {"doc_name": 42},
                          {"doc_name": documents[0], "obj_name": ""}]:
            response = await session.call_tool("resolve_reference", arguments)
            assert response.isError, response
        after = json.loads((await call("get_status")).content[0].text)
        assert before == after
        for document, expected in zip(documents, measurements):
            actual = json.loads((await call("measure", obj_name="SameBox", doc_name=document)).content[0].text)
            assert actual == expected
        await check_batches(session, call, documents)
        return capabilities["data"]
    finally:
        for document in reversed(documents):
            await call("close_document", name=document)
        final = json.loads((await call("get_status")).content[0].text)
        assert final["documents"] == initial["documents"]


async def check_batches(session, call, documents):
    first, second = documents

    def step(identifier, operation, document=first, **arguments):
        return {"id": identifier, "operation": operation, "doc_name": document, "arguments": arguments}

    async def batch(steps, **options):
        response = await call("execute_batch", steps=steps, **options)
        return response.structuredContent

    async def snapshot():
        return [sorted(json.loads((await call("list_objects", doc_name=document)).content[0].text),
                       key=lambda obj: obj["name"]) for document in documents]

    before = await snapshot()
    steps = [step("box", "part_box", length=4, width=5, height=6, name="BatchBox"),
             step("move", "move_object", obj_name={"$ref": "box"}, dx=7)]
    preview = await batch(steps, preview=True)
    assert preview["data"]["status"] == "preview", preview
    assert before == await snapshot()
    result = await batch(steps)
    assert result["status"] == "success", result
    assert [entry["status"] for entry in result["data"]["steps"]] == ["succeeded", "succeeded"]
    box_name = result["data"]["steps"][0]["data"]["name"]
    measured = json.loads((await call("measure", obj_name=box_name, doc_name=first)).content[0].text)
    assert abs(measured["volume"] - 120) < 1e-6 and abs(measured["bounding_box"]["min"]["x"] - 7) < 1e-6
    after = await snapshot()
    assert after[1] == before[1]
    await call("undo", doc_name=first)
    assert before == await snapshot(), "Atomic batch must have one Undo record"
    await call("redo", doc_name=first)
    assert after == await snapshot()

    failure_steps = [step("move", "move_object", obj_name="SameBox", dx=100),
                     step("bad", "part_fillet", obj_name="SameBox", edges=["Edge999"], radius=1, name="BadFillet"),
                     step("skip", "part_box", length=1, width=1, height=1, name="Skipped")]
    result = await batch(failure_steps)
    assert result["status"] == "error" and result["data"]["status"] == "rolled_back", result
    assert [entry["status"] for entry in result["data"]["steps"]] == ["rolled_back", "failed", "not_executed"], result
    assert after == await snapshot(), "Rollback must restore geometry, visibility and object set"

    invalid_batches = [
        [step("a", "part_box", length=1, width=1, height=1), step("b", "part_box", second, length=1, width=1, height=1)],
        [step("move", "move_object", obj_name={"$ref": "later"}), step("later", "part_box", length=1, width=1, height=1)],
        [step("first", "move_object", obj_name={"$ref": "second"}), step("second", "move_object", obj_name={"$ref": "first"})],
        [step("a", "part_box", length=1, width=1, height=1), step("b", "part_box", length=-1, width=1, height=1)],
        [step("a", "part_box", length=True, width=1, height=1)],
    ]
    for invalid in invalid_batches:
        result = await batch(invalid)
        assert result["status"] == "error", result
        assert after == await snapshot()
    for invalid in [[], steps * 51, [step("file", "export_step", path="must_not_exist.step")],
                    [step("code", "execute_python", code="result=42")]]:
        response = await session.call_tool("execute_batch", {"steps": invalid})
        assert response.isError, response
        assert after == await snapshot()

    multi = [step("one", "part_box", length=2, width=2, height=2, name="MultiFirst"),
             step("two", "part_box", second, length=3, width=3, height=3, name="MultiSecond")]
    result = await batch(multi, atomic=False)
    assert result["status"] == "success", result
    before_partial = await snapshot()
    partial = [step("keep", "part_box", length=2, width=2, height=2, name="KeepSuccess"),
               step("bad", "part_fillet", second, obj_name="SameBox", edges=["Edge999"], radius=1),
               step("skip", "move_object", second, obj_name="SameBox", dx=100)]
    result = await batch(partial, atomic=False)
    assert result["data"]["status"] == "partial", result
    assert [entry["status"] for entry in result["data"]["steps"]] == ["succeeded", "failed", "not_executed"]
    current = await snapshot()
    assert current[1] == before_partial[1]
    assert "KeepSuccess" in {entry["name"] for entry in current[0]}
    await call("undo", doc_name=first)
    assert before_partial == await snapshot()

    variants = [
        step("base", "part_box", length=20, width=20, height=20, name="VariantBase"),
        step("cylinder", "part_cylinder", radius=2, height=20, x=10, y=10, name="VariantCylinder"),
        step("sphere", "part_sphere", radius=3, x=50, name="VariantSphere"),
        step("cone", "part_cone", radius1=3, radius2=1, height=6, x=70, name="VariantCone"),
        step("torus", "part_torus", radius1=4, radius2=1, x=90, name="VariantTorus"),
        step("cut", "boolean_cut", base_name={"$ref": "base"}, tool_name={"$ref": "cylinder"}, name="VariantCut"),
        step("fillet", "part_fillet", obj_name={"$ref": "base"}, edges=["Edge1"], radius=0.5, name="VariantFillet"),
        step("chamfer", "part_chamfer", obj_name={"$ref": "base"}, edges=[1], size=0.5, name="VariantChamfer"),
        step("placement", "set_placement", obj_name={"$ref": "sphere"}, x=55, rx=30),
        step("move", "move_object", obj_name={"$ref": "sphere"}, dy=5),
        step("temporary", "part_box", length=1, width=1, height=1, name="VariantTemporary"),
        step("delete", "delete_object", obj_name={"$ref": "temporary"}),
    ]
    result = await batch(variants)
    assert result["status"] == "success", result
    assert all(entry["status"] == "succeeded" for entry in result["data"]["steps"])
    names = {entry["id"]: entry["data"].get("name") for entry in result["data"]["steps"]}
    for identifier in ["base", "cylinder", "sphere", "cone", "torus", "cut", "fillet", "chamfer"]:
        info = json.loads((await call("inspect_object", obj_name=names[identifier], doc_name=first)).content[0].text)
        assert info["shape"]["is_valid"] and info["shape"]["volume"] > 0, info
    import math
    cut = json.loads((await call("measure", obj_name=names["cut"], doc_name=first)).content[0].text)
    assert abs(cut["volume"] - (8000 - math.pi * 4 * 20)) < 1e-6
    variant_state = await snapshot()
    result = await batch([step("protected", "delete_object", obj_name=names["base"])])
    assert result["status"] == "error" and result["error"]["code"] == "dependency_conflict", result
    assert variant_state == await snapshot()
    await call("undo", doc_name=first)
    assert before_partial == await snapshot()
    result = await batch([step("delete", "delete_object", obj_name="SameBox"),
                          step("missing", "move_object", obj_name="DoesNotExist", dx=1)])
    assert result["data"]["status"] == "rolled_back", result
    restored = await snapshot()
    assert before_partial == restored, {"expected": before_partial, "restored": restored}


async def check_stage3(session, call, directory):
    transcript = []
    documents = []

    async def invoke(tool, error=None, **arguments):
        response = await call(tool, **arguments)
        result = (response.structuredContent if response.structuredContent and "contract_version" in response.structuredContent
              else json.loads(response.content[0].text))
        transcript.append({"tool": tool, "arguments": arguments, "result": result})
        if "status" in result and "contract_version" in result:
            assert json.loads(response.content[0].text) == result
            if error:
                assert result["status"] == "error" and result["error"]["code"] == error, result
                assert result["error"]["state"] in ({"unknown"} if error == "file_write_failed" else {"unchanged", "rolled_back"}), result
                return result
            assert result["status"] == "success", result
            return result["data"]
        assert error is None
        return result

    async def volume(document, name, expected):
        measured = await invoke("measure", doc_name=document, obj_name=name)
        assert abs(measured["volume"] - expected) <= max(1e-6, abs(expected) * 1e-6), measured

    initial = await invoke("get_status")
    assert not initial["documents"], "Stage 3 requires an empty isolated instance"
    try:
        for suffix in ["Main", "Other"]:
            documents.append((await invoke("create_document", name="MCP_Stage3_" + suffix))["name"])
        main, other = documents
        await invoke("activate_document", doc_name=main)
        assert (await invoke("inspect_document", doc_name=main))["active"]
        await invoke("activate_document", doc_name=other)
        assert (await invoke("inspect_document", doc_name=other))["active"]
        for document in documents:
            await invoke("part_box", doc_name=document, name="SameBox", length=10, width=10, height=10)
        await invoke("set_properties", doc_name=main, obj_name="SameBox", values={"Length": {"value": 2, "unit": "cm"}})
        await volume(main, "SameBox", 2000)
        await volume(other, "SameBox", 1000)
        await invoke("rename_object", doc_name=main, obj_name="SameBox", label="Renamed display")
        assert (await invoke("resolve_reference", doc_name=main, obj_name="SameBox"))["label"] == "Renamed display"
        for arguments, code in [({"Shape": "not a shape"}, "property_read_only"),
                                ({"Length": {"value": 2, "unit": "deg"}}, "invalid_unit"),
                                ({"Length": True}, "invalid_arguments")]:
            await invoke("set_properties", error=code, doc_name=main, obj_name="SameBox", values=arguments)
        await invoke("get_properties", error="object_not_found", doc_name=main, obj_name="Missing")
        for arguments in [{}, {"doc_name": ""}, {"doc_name": 42}]:
            assert (await session.call_tool("inspect_document", arguments)).isError
        group = (await invoke("create_container", doc_name=main, name="Group"))["name"]
        await invoke("set_container_members", doc_name=main, obj_name=group, members=["SameBox"])
        await invoke("set_container_members", error="dependency_cycle", doc_name=main, obj_name=group, members=[group])
        await invoke("set_container_members", doc_name=main, obj_name=group, members=[])
        body = (await invoke("create_container", doc_name=main, name="Body", kind="body"))["name"]
        sketch = (await invoke("create_sketch", doc_name=main, name="Profile", body_name=body))["name"]
        await invoke("sketch_add_rectangle", doc_name=main, sketch_name=sketch, x1=0, y1=0, x2=10, y2=5)
        pad = (await invoke("partdesign_pad", doc_name=main, sketch_name=sketch, length=3))["name"]
        await invoke("set_body_tip", doc_name=main, obj_name=body, tip_name=None)
        await invoke("set_body_tip", doc_name=main, obj_name=body, tip_name=pad)
        await invoke("set_body_tip", error="invalid_arguments", doc_name=main, obj_name=body, tip_name="SameBox")
        await invoke("set_container_members", doc_name=main, obj_name=body, members=[sketch, pad])
        await invoke("set_container_members", error="dependency_conflict", doc_name=main, obj_name=body, members=[sketch])
        await volume(main, body, 150)
        sheet = (await invoke("create_spreadsheet", doc_name=main, name="Parameters"))["name"]
        await invoke("set_spreadsheet_cells", doc_name=main, obj_name=sheet,
                     cells={"A1": "80 mm", "A2": "50 mm", "A3": "30 mm", "A4": "3 mm", "B1": "=A1*2", "C1": "temporary"})
        for cell, alias in [("A1", "LengthParam"), ("A2", "WidthParam"), ("A3", "HeightParam"), ("A4", "WallParam")]:
            await invoke("set_spreadsheet_alias", doc_name=main, obj_name=sheet, cell=cell, alias=alias)
        await invoke("set_spreadsheet_alias", error="invalid_alias", doc_name=main, obj_name=sheet, cell="B1", alias="LengthParam")
        await invoke("set_spreadsheet_alias", doc_name=main, obj_name=sheet, cell="C1", alias="Temporary")
        await invoke("set_spreadsheet_alias", doc_name=main, obj_name=sheet, cell="C1", alias=None)
        await invoke("set_spreadsheet_cells", doc_name=main, obj_name=sheet, cells={"C1": None})
        outer = (await invoke("part_box", doc_name=main, name="Outer", length=80, width=50, height=30))["name"]
        inner = (await invoke("part_box", doc_name=main, name="Inner", length=74, width=44, height=27, x=3, y=3, z=3))["name"]
        for obj, expressions in [(outer, {"Length": "LengthParam", "Width": "WidthParam", "Height": "HeightParam"}),
                      (inner, {"Length": "LengthParam-2*Parameters.WallParam", "Width": "WidthParam-2*Parameters.WallParam", "Height": "HeightParam-Parameters.WallParam",
                           "Placement.Base.x": "WallParam", "Placement.Base.y": "WallParam", "Placement.Base.z": "WallParam"})]:
            for property_name, expression in expressions.items():
                await invoke("set_expression", doc_name=main, obj_name=obj, property_name=property_name, expression=sheet + "." + expression)
        shell = (await invoke("boolean_cut", doc_name=main, name="Housing", base_name=outer, tool_name=inner))["name"]
        await volume(main, shell, 32088)
        expressions = await invoke("get_expressions", doc_name=main, obj_name=outer)
        assert len(expressions["expressions"]) == 3
        dependencies = await invoke("get_dependencies", doc_name=main, obj_name=sheet)
        assert shell in {ref["object"] for ref in dependencies["affected"]}
        await invoke("set_expression", error="invalid_expression", doc_name=main, obj_name=outer, property_name="Length", expression="Missing.Length")
        await invoke("set_expression", error="invalid_expression", doc_name=main, obj_name=outer, property_name="Length", expression=outer + ".Length")
        await invoke("set_properties", error="expression_driven", doc_name=main, obj_name=outer, values={"Length": {"value": 90, "unit": "mm"}})
        before = await invoke("read_spreadsheet", doc_name=main, obj_name=sheet, cell_range="A1:C4")
        for cells in [{"A1": "=B1"}, {"A1": "=Missing.Length"}, {"A4": "26 mm"}]:
            await invoke("set_spreadsheet_cells", error="invalid_expression", doc_name=main, obj_name=sheet, cells=cells)
            assert await invoke("read_spreadsheet", doc_name=main, obj_name=sheet, cell_range="A1:C4") == before
            await volume(main, shell, 32088)
        await invoke("set_spreadsheet_cells", doc_name=main, obj_name=sheet, cells={"A1": "100 mm"})
        await volume(main, shell, 38328)
        await invoke("undo", doc_name=main)
        await volume(main, shell, 32088)
        await invoke("redo", doc_name=main)
        await volume(main, shell, 38328)
        copied = (await invoke("copy_object", doc_name=main, obj_name="SameBox"))["name"]
        linked = (await invoke("create_link", doc_name=main, name="LocalLink", source_document=main, source_object="SameBox"))["name"]
        await invoke("set_properties", doc_name=main, obj_name="SameBox", values={"Length": {"value": 30, "unit": "mm"}})
        await volume(main, copied, 2000)
        await volume(main, linked, 3000)
        await invoke("close_document_safe", error="unsaved_changes", doc_name=main)
        main_path = str(Path(directory) / "main.FCStd")
        other_path = str(Path(directory) / "other.FCStd")
        await invoke("save_document_safe", doc_name=main, path=main_path)
        original_bytes = Path(main_path).read_bytes()
        await invoke("save_document_safe", error="file_exists", doc_name=main, path=main_path)
        assert Path(main_path).read_bytes() == original_bytes
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.CreateFileW.argtypes = [ctypes.c_wchar_p, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_void_p,
                                      ctypes.c_ulong, ctypes.c_ulong, ctypes.c_void_p]
        kernel.CreateFileW.restype = ctypes.c_void_p
        kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        handle = kernel.CreateFileW(main_path, 0x80000000, 0, None, 3, 0, None)
        assert handle not in (None, ctypes.c_void_p(-1).value), ctypes.get_last_error()
        try:
            await invoke("save_document_safe", error="file_write_failed", doc_name=main, path=main_path, overwrite=True)
        finally:
            kernel.CloseHandle(handle)
        assert Path(main_path).read_bytes() == original_bytes
        await invoke("create_link", error="invalid_reference", doc_name=other, name="ExternalLink", source_document=main, source_object="SameBox")
        await invoke("save_document_safe", doc_name=other, path=other_path)
        await invoke("create_link", doc_name=other, name="ExternalLink", source_document=main, source_object="SameBox")
        await invoke("recompute_document", doc_name=other)
        await volume(other, "ExternalLink", 3000)
        preview = await invoke("preview_delete", doc_name=main, obj_names=["SameBox"])
        assert not preview["can_delete"]
        await invoke("delete_objects", error="dependency_conflict", doc_name=main, obj_names=["SameBox"], confirmed_objects=["SameBox", linked])
        await invoke("save_document_safe", doc_name=other, path=other_path, overwrite=True)
        await invoke("close_document_safe", error="dependency_conflict", doc_name=main, discard_changes=True)
        await invoke("close_document_safe", doc_name=other)
        documents.remove(other)
        await invoke("save_document_safe", doc_name=main, overwrite=True)
        await invoke("close_document_safe", doc_name=main)
        documents.clear()
        reopened = await invoke("open_document", path=main_path)
        main = reopened["name"]
        documents.append(main)
        await volume(main, shell, 38328)
        await invoke("set_spreadsheet_cells", doc_name=main, obj_name=sheet, cells={"A4": "4 mm"})
        await volume(main, shell, 49536)
        await invoke("save_document_safe", doc_name=main, overwrite=True)
        reopened = await invoke("open_document", path=other_path)
        other = reopened["name"]
        documents.append(other)
        await volume(other, "ExternalLink", 3000)
        await invoke("set_properties", doc_name=main, obj_name="SameBox", values={"Length": {"value": 40, "unit": "mm"}})
        await invoke("recompute_document", doc_name=other)
        await volume(other, "ExternalLink", 4000)
        await volume(main, copied, 2000)
        await invoke("close_document_safe", doc_name=other, discard_changes=True)
        documents.remove(other)
        preview = await invoke("preview_delete", doc_name=main, obj_names=["SameBox"])
        assert set(preview["confirmation"]) == {"SameBox", linked}, preview
        await invoke("delete_objects", error="confirmation_required", doc_name=main, obj_names=["SameBox"], confirmed_objects=["SameBox"])
        await invoke("delete_objects", doc_name=main, obj_names=["SameBox"], confirmed_objects=preview["confirmation"])
        await invoke("undo", doc_name=main)
        await volume(main, linked, 4000)
        await invoke("redo", doc_name=main)
        assert "SameBox" not in {obj["name"] for obj in await invoke("list_objects", doc_name=main)}
        await invoke("set_expression", doc_name=main, obj_name=outer, property_name="Width", expression=None)
        await invoke("set_expression", doc_name=main, obj_name=outer, property_name="Width", expression=sheet + ".WidthParam")
        for extension in ["step", "stl"]:
            path = str(Path(directory) / ("housing." + extension))
            await invoke("export_" + extension, doc_name=main, obj_names=[shell], path=path)
            assert Path(path).stat().st_size > 100
        await invoke("save_document_safe", doc_name=main, overwrite=True)
        return {"calls": len(transcript), "volumes": [32088, 38328, 49536], "artifacts": str(directory)}
    finally:
        for document in reversed(documents):
            await invoke("close_document_safe", doc_name=document, discard_changes=True)
        Path(directory, "mcp-transcript.json").write_text(json.dumps(transcript, indent=2), encoding="utf-8")
        assert not (await invoke("get_status"))["documents"]


async def check_stage4(session, call, directory, selection_only=False):
    transcript = []
    documents = []

    async def invoke(tool, error=None, **arguments):
        response = await call(tool, **arguments)
        result = (response.structuredContent if response.structuredContent and "contract_version" in response.structuredContent
                  else json.loads(response.content[0].text))
        for content in response.content:
            if content.type == "image":
                image = base64.b64decode(content.data)
                assert image.startswith(b"\x89PNG\r\n\x1a\n")
                assert struct.unpack(">II", image[16:24]) == (arguments["width"], arguments["height"])
                image_path = directory / ("view-" + arguments["view"] + ".png")
                image_path.write_bytes(image)
                result["data"]["artifact"] = str(image_path)
                result["data"]["sha256"] = hashlib.sha256(image).hexdigest()
        transcript.append({"tool": tool, "arguments": arguments, "result": result})
        if "contract_version" in result:
            if tool != "capture_view":
                assert json.loads(response.content[0].text) == result
            if error:
                assert result["status"] == "error" and result["error"]["code"] == error, result
                assert result["error"]["state"] in {"unchanged", "rolled_back"}, result
                return result
            assert result["status"] == "success", result
            return result["data"]
        assert error is None
        return result

    assert not (await invoke("get_status"))["documents"], "Stage 4 needs an empty isolated instance"
    try:
        for suffix in ["Main", "Other"]:
            documents.append((await invoke("create_document", name="MCP_Stage4_" + suffix))["name"])
            await invoke("part_box", doc_name=documents[-1], name="Box", length=10, width=20, height=30)
        main, other = documents
        async def select(kind, filters, name="Box", document=main):
            return await invoke("select_subelement", doc_name=document, obj_name=name, kind=kind, filters=filters)

        top = await select("face", {"geometry_type": "plane", "normal": [0, 0, 1], "position": [5, 10, 30], "area": {"min": 200, "max": 200}})
        assert top["position"] == [5, 10, 30], top
        other_top = await select("face", {"normal": [0, 0, 1]}, document=other)
        assert top["selection"]["revision"] != other_top["selection"]["revision"]
        first_page = await invoke("list_subelements", doc_name=main, obj_name="Box", kind="edge", limit=5)
        assert first_page["total"] == 12 and len(first_page["items"]) == 5 and first_page["next_offset"] == 5
        last_page = await invoke("list_subelements", doc_name=main, obj_name="Box", kind="edge", offset=10, limit=5)
        assert len(last_page["items"]) == 2 and last_page["next_offset"] is None
        edge = await select("edge", {"geometry_type": "line", "axis": [0, 0, -1], "length": {"min": 30, "max": 30},
                                     "bbox": {"min": [0, 0, 0], "max": [0, 0, 30]}})
        assert edge["position"] == [0, 0, 15], edge
        vertex = await select("vertex", {"position": [10, 20, 30]})
        assert vertex["position"] == [10, 20, 30]
        for filters, code in [({}, "selection_ambiguous"), ({"position": [999, 0, 0]}, "selection_empty"),
                              ({"normal": [0, 0, 0]}, "invalid_arguments"), ({"radius": {"min": 2, "max": 1}}, "invalid_arguments")]:
            await invoke("select_subelement", error=code, doc_name=main, obj_name="Box", kind="face", filters=filters)
        await invoke("set_properties", doc_name=main, obj_name="Box", values={"Height": {"value": 40, "unit": "mm"}})
        await invoke("resolve_subelement", error="stale_selection", selection=top["selection"])
        await invoke("resolve_subelement", selection=other_top["selection"])
        changed = await select("face", {"normal": [0, 0, 1]})
        assert changed["position"] == [5, 10, 40]
        await invoke("undo", doc_name=main)
        await invoke("resolve_subelement", error="stale_selection", selection=changed["selection"])
        assert (await select("face", {"normal": [0, 0, 1]}))["position"] == [5, 10, 30]
        await invoke("redo", doc_name=main)
        assert (await select("face", {"normal": [0, 0, 1]}))["position"] == [5, 10, 40]
        await invoke("part_cylinder", doc_name=main, name="Cylinder", radius=5, height=20, x=40)
        cylinder = await select("face", {"geometry_type": "cylinder", "radius": {"min": 5, "max": 5}, "axis": [0, 0, 1]}, name="Cylinder")
        assert abs(cylinder["area"] - 200 * math.pi) < 1e-6
        circle = await select("edge", {"geometry_type": "circle", "position": [40, 0, 20], "radius": {"min": 5, "max": 5}}, name="Cylinder")
        assert abs(circle["length"] - 10 * math.pi) < 1e-6
        path = str(directory / (main + ".FCStd"))
        before_reopen = await select("face", {"normal": [0, 0, 1]})
        await invoke("save_document_safe", doc_name=main, path=path)
        await invoke("close_document_safe", doc_name=main)
        documents.remove(main)
        main = (await invoke("open_document", path=path))["name"]
        documents.append(main)
        await invoke("resolve_subelement", error="stale_selection", selection=before_reopen["selection"])
        await invoke("set_properties", doc_name=main, obj_name="Box", values={"Height": {"value": 30, "unit": "mm"}})
        if not selection_only:
            first = {"document": main, "object": "Box"}
            await invoke("part_box", doc_name=main, name="MovingBox", length=10, width=20, height=30, x=15)
            second = {"document": main, "object": "MovingBox"}
            measured = await invoke("measure", doc_name=main, obj_name="Box")
            assert abs(measured["volume"] - 6000) < 1e-6 and abs(measured["area"] - 2200) < 1e-6
            assert measured["center_of_mass"] == {"x": 5.0, "y": 10.0, "z": 15.0}
            for position, expected_distance, expected_volume, classification in [(15, 5, 0, "separated"), (10, 0, 0, "contact"), (5, 0, 3000, "interference"), (10.0005, 0.0005, 0, "contact")]:
                await invoke("set_placement", doc_name=main, obj_name="MovingBox", x=position)
                result = await invoke("check_interference", first=first, second=second)
                assert abs(result["distance"] - expected_distance) < 1e-7, result
                assert abs(result["intersection_volume"] - expected_volume) < 1e-6, result
                assert result["classification"] == classification, result
                assert abs((await invoke("measure_distance", first=first, second=second))["distance"] - expected_distance) < 1e-7
            top = (await select("face", {"normal": [0, 0, 1]}))["selection"]
            side = (await select("face", {"normal": [1, 0, 0]}))["selection"]
            edge = (await select("edge", {"position": [0, 0, 15]}))["selection"]
            horizontal = (await select("edge", {"position": [5, 0, 0]}))["selection"]
            vertex = (await select("vertex", {"position": [10, 20, 30]}))["selection"]
            origin = (await select("vertex", {"position": [0, 0, 0]}))["selection"]
            assert abs((await invoke("measure_distance", first=vertex, second=origin))["distance"] - math.sqrt(1400)) < 1e-6
            for pair, expected in [((top, side), 90), ((edge, horizontal), 90), ((edge, top), 90), ((horizontal, top), 0), ((top, top), 0)]:
                assert abs((await invoke("measure_angle", first=pair[0], second=pair[1]))["angle"] - expected) < 1e-6
            await invoke("measure_angle", first=first, second=second, error="unsupported_geometry")
            await invoke("check_interference", first=top, second=side, error="unsupported_geometry")
            await invoke("measure_distance", first=first, second={"document": other, "object": "Box"}, error="coordinate_system_mismatch")
            original = await invoke("get_view_state", doc_name=main, obj_names=["Box"])
            for visible in [False, True]:
                await invoke("set_visibility", doc_name=main, obj_name="Box", visible=visible)
                assert (await invoke("get_view_state", doc_name=main, obj_names=["Box"]))["objects"][0]["visible"] == visible
            await invoke("set_color", doc_name=main, obj_name="Box", r=0.2, g=0.7, b=0.3)
            for value, expected in [(-1, 0), (25, 25), (101, 100)]:
                result = await invoke("set_transparency", doc_name=main, obj_name="Box", transparency=value)
                assert result["transparency"] == expected
                assert (await invoke("get_view_state", doc_name=main, obj_names=["Box"]))["objects"][0]["transparency"] == expected
            appearance = original["objects"][0]
            await invoke("set_color", doc_name=main, obj_name="Box", **dict(zip(["r", "g", "b"], appearance["color"][:3])))
            await invoke("set_transparency", doc_name=main, obj_name="Box", transparency=appearance["transparency"])
            assert (await invoke("get_view_state", doc_name=main, obj_names=["Box"]))["objects"] == original["objects"]
            await invoke("set_placement", doc_name=main, obj_name="MovingBox", x=15)
            top = (await select("face", {"normal": [0, 0, 1]}))["selection"]
            other_top = (await select("face", {"normal": [0, 0, 1]}, document=other))["selection"]
            await invoke("highlight_subelements", doc_name=other, selections=[other_top])
            await invoke("highlight_subelements", doc_name=main, selections=[top])
            await invoke("activate_document", doc_name=other)
            other_state = await invoke("get_view_state", doc_name=other, obj_names=["Box"])
            for preset in ["isometric", "front", "back", "top", "bottom", "left", "right"]:
                await invoke("capture_view", doc_name=main, view=preset, width=800, height=600, selections=[top])
                current_other_state = await invoke("get_view_state", doc_name=other, obj_names=["Box"])
                assert current_other_state == other_state, {"preset": preset, "expected": other_state, "actual": current_other_state}
            assert (await invoke("inspect_document", doc_name=other))["active"]
            await invoke("resolve_subelement", selection=top)
            before_view = await invoke("get_view_state", doc_name=main, obj_names=[])
            await invoke("capture_view", doc_name=main, view="front", width=800, height=600, selections=[dict(top, revision="stale")], error="stale_selection")
            assert (await invoke("get_view_state", doc_name=main, obj_names=[])) == before_view
            await invoke("highlight_subelements", doc_name=main, selections=[])
            edge = (await select("edge", {"position": [0, 0, 15]}))["selection"]
            result = await invoke("part_fillet", doc_name=main, obj_name="Box", edges=[edge], radius=1)
            assert result["shape_valid"]
            await invoke("resolve_subelement", selection=edge, error="stale_selection")
            await invoke("undo", doc_name=main)
            await invoke("resolve_subelement", selection=edge, error="stale_selection")
            await invoke("redo", doc_name=main)
            await invoke("undo", doc_name=main)
        await invoke("save_document_safe", doc_name=main, overwrite=True)
        await invoke("export_step", doc_name=main, obj_names=["Box", "Cylinder"], path=str(directory / "selection.step"))
        return {"calls": len(transcript), "artifacts": str(directory), "selection_only": selection_only}
    finally:
        for document in reversed(documents):
            await invoke("close_document_safe", doc_name=document, discard_changes=True)
        (directory / "mcp-transcript.json").write_text(json.dumps(transcript, indent=2), encoding="utf-8")
        assert not (await invoke("get_status"))["documents"]


async def check_stage5(session, call, directory):
    transcript = []
    documents = []

    async def invoke(tool, **arguments):
        response = await call(tool, **arguments)
        result = (response.structuredContent if response.structuredContent and "contract_version" in response.structuredContent
                  else json.loads(response.content[0].text))
        transcript.append({"tool": tool, "arguments": arguments, "result": result})
        if "contract_version" in result:
            assert result["status"] == "success", result
            return result["data"]
        return result

    assert not json.loads((await call("get_status")).content[0].text)["documents"], "Stage 5 needs an empty isolated instance"
    try:
        main = (await invoke("create_document", name="MCP_Stage5"))["name"]
        documents.append(main)
        await invoke("create_sketch", doc_name=main, name="HousingProfile")
        await invoke("sketch_add_rectangle", doc_name=main, sketch_name="HousingProfile",
                     x1=-40, y1=-25, x2=40, y2=25)
        await invoke("sketch_constrain_lock", doc_name=main, sketch_name="HousingProfile", geo_idx=0, point_idx=1)
        width = (await invoke("sketch_constrain_length", doc_name=main, sketch_name="HousingProfile",
                              geo_idx=0, value=80))["constraint_index"]
        await invoke("sketch_constrain_length", doc_name=main, sketch_name="HousingProfile", geo_idx=1, value=50)
        housing = await invoke("sketch_info", doc_name=main, sketch_name="HousingProfile")
        assert housing["fully_constrained"] and not any(c["type"] == "Block" for c in housing["constraints"])
        await invoke("sketch_set_constraint_value", doc_name=main, sketch_name="HousingProfile",
                     constraint_idx=width, value=100)
        housing = await invoke("sketch_info", doc_name=main, sketch_name="HousingProfile")
        assert abs(housing["geometries"][0]["end"]["x"] - housing["geometries"][0]["start"]["x"] - 100) < 1e-6

        await invoke("create_sketch", doc_name=main, name="FlangeProfile")
        await invoke("sketch_add_polygon", doc_name=main, sketch_name="FlangeProfile",
                     points=[[0, 0], [30, 0], [30, 8], [10, 8], [10, 48], [0, 48]], close=True)
        for index in [0, 2, 4]:
            await invoke("sketch_constrain_horizontal", doc_name=main, sketch_name="FlangeProfile", geo_idx=index)
        for index in [1, 3, 5]:
            await invoke("sketch_constrain_vertical", doc_name=main, sketch_name="FlangeProfile", geo_idx=index)
        await invoke("sketch_constrain_lock", doc_name=main, sketch_name="FlangeProfile", geo_idx=0, point_idx=1)
        for index, value in [(0, 30), (1, 8), (2, 20)]:
            await invoke("sketch_constrain_length", doc_name=main, sketch_name="FlangeProfile", geo_idx=index, value=value)
        shaft = (await invoke("sketch_constrain_length", doc_name=main, sketch_name="FlangeProfile",
                              geo_idx=3, value=40))["constraint_index"]
        flange = await invoke("sketch_info", doc_name=main, sketch_name="FlangeProfile")
        assert flange["fully_constrained"] and not any(c["type"] == "Block" for c in flange["constraints"])
        await invoke("sketch_set_constraint_value", doc_name=main, sketch_name="FlangeProfile",
                     constraint_idx=shaft, value=50)

        await invoke("create_sketch", doc_name=main, name="Rollback")
        await invoke("sketch_add_line", doc_name=main, sketch_name="Rollback", x1=0, y1=0, x2=10, y2=0)
        await invoke("sketch_constrain_horizontal", doc_name=main, sketch_name="Rollback", geo_idx=0)
        before = await invoke("sketch_info", doc_name=main, sketch_name="Rollback")
        failure = await session.call_tool("sketch_constrain_horizontal",
                                          {"doc_name": main, "sketch_name": "Rollback", "geo_idx": 0})
        transcript.append({"tool": "sketch_constrain_horizontal", "arguments": {"duplicate": True},
                           "is_error": failure.isError,
                           "result": [getattr(content, "text", "") for content in failure.content]})
        assert failure.isError
        assert await invoke("sketch_info", doc_name=main, sketch_name="Rollback") == before

        await invoke("part_box", doc_name=main, name="ReferenceBox", length=10, width=10, height=10)
        await invoke("create_sketch", doc_name=main, name="ReferenceSketch")
        edge = (await invoke("list_subelements", doc_name=main, obj_name="ReferenceBox", kind="edge", limit=1))["items"][0]["selection"]
        projected = await invoke("sketch_add_external", doc_name=main, sketch_name="ReferenceSketch", selection=edge)
        assert projected["geometry_index"] == -3
        await invoke("sketch_delete_external", doc_name=main, sketch_name="ReferenceSketch", external_idx=0)
        face = (await invoke("select_subelement", doc_name=main, obj_name="ReferenceBox", kind="face",
                             filters={"normal": [0, 0, 1]}))["selection"]
        await invoke("sketch_set_attachment", doc_name=main, sketch_name="ReferenceSketch",
                     support_selection=face, offset_z=2, rotation_z=15)
        attachment = (await invoke("sketch_info", doc_name=main, sketch_name="ReferenceSketch"))["attachment"]
        assert attachment["map_mode"] == "FlatFace" and attachment["offset"]["position"] == [0, 0, 2]

        await invoke("create_sketch", doc_name=main, name="EditSketch")
        await invoke("sketch_add_line", doc_name=main, sketch_name="EditSketch", x1=0, y1=0, x2=5, y2=0)
        await invoke("sketch_extend", doc_name=main, sketch_name="EditSketch", geo_idx=0, increment=3, point_idx=2)
        await invoke("sketch_copy", doc_name=main, sketch_name="EditSketch", geometry_indices=[0], offset_x=10, offset_y=2)
        await invoke("sketch_mirror", doc_name=main, sketch_name="EditSketch", geometry_indices=[0], reference_geo_idx=-2)
        await invoke("create_sketch", doc_name=main, name="FilletSketch")
        await invoke("sketch_add_line", doc_name=main, sketch_name="FilletSketch", x1=0, y1=0, x2=10, y2=0)
        await invoke("sketch_add_line", doc_name=main, sketch_name="FilletSketch", x1=10, y1=0, x2=10, y2=10)
        await invoke("sketch_fillet", doc_name=main, sketch_name="FilletSketch", geo_idx1=0, geo_idx2=1,
                     near1_x=9, near1_y=0, near2_x=10, near2_y=1, radius=2)
        path = str(directory / "stage5.FCStd")
        await invoke("save_document_safe", doc_name=main, path=path)
        await invoke("close_document_safe", doc_name=main)
        documents.remove(main)
        main = (await invoke("open_document", path=path))["name"]
        documents.append(main)
        assert (await invoke("sketch_info", doc_name=main, sketch_name="HousingProfile"))["fully_constrained"]
        assert (await invoke("sketch_info", doc_name=main, sketch_name="FlangeProfile"))["fully_constrained"]
        return {"calls": len(transcript), "artifact": path}
    finally:
        for document in reversed(documents):
            await invoke("close_document_safe", doc_name=document, discard_changes=True)
        (directory / "mcp-transcript.json").write_text(json.dumps(transcript, indent=2), encoding="utf-8")
        assert not json.loads((await call("get_status")).content[0].text)["documents"]


async def main():
    environment = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
    parameters = StdioServerParameters(command=sys.executable, args=["-m", "freecad_mcp.server"], env=environment)
    async with stdio_client(parameters) as (reader, writer):
        async with ClientSession(reader, writer) as session:
            await session.initialize()
            tools = await session.list_tools()

            async def call(tool_identifier, **arguments):
                response = await session.call_tool(tool_identifier, arguments)
                if response.isError:
                    raise AssertionError(f"{tool_identifier}: {response.content}")
                return response

            connection = await call("connect", port=int(os.environ.get("FREECAD_TEST_PORT", "9876")))
            assert connection.content[0].text.startswith("Connected"), connection
            if "--stage5-only" in sys.argv:
                directory = Path(tempfile.mkdtemp(prefix="freecad-stage5-mcp-"))
                results = []
                for index in range(2):
                    run_directory = directory / str(index + 1)
                    run_directory.mkdir()
                    results.append(await check_stage5(session, call, run_directory))
                report = {"success": True, "registered_tools": len(tools.tools), "runs": results,
                          "host_python": sys.executable, "python_version": sys.version, "os": platform.platform(),
                          "port": int(os.environ.get("FREECAD_TEST_PORT", "9876")),
                          "capabilities": (await call("get_capabilities")).structuredContent["data"]}
                (directory / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
                print(json.dumps(report, indent=2))
                return
            if "--stage4a-only" in sys.argv or "--stage4-only" in sys.argv:
                directory = Path(tempfile.mkdtemp(prefix="freecad-stage4-mcp-"))
                results = []
                for index in range(2):
                    run_directory = directory / str(index + 1)
                    run_directory.mkdir()
                    results.append(await check_stage4(session, call, run_directory, "--stage4a-only" in sys.argv))
                report = {"success": True, "registered_tools": len(tools.tools), "runs": results,
                          "host_python": sys.executable, "python_version": sys.version, "os": platform.platform(),
                          "port": int(os.environ.get("FREECAD_TEST_PORT", "9876")),
                          "capabilities": (await call("get_capabilities")).structuredContent["data"]}
                (directory / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
                print(json.dumps(report, indent=2))
                return
            if "--stage3-only" in sys.argv:
                directory = Path(tempfile.mkdtemp(prefix="freecad-stage3-mcp-"))
                results = []
                for index in range(2):
                    run_directory = directory / str(index + 1)
                    run_directory.mkdir()
                    results.append(await check_stage3(session, call, run_directory))
                capabilities = (await call("get_capabilities")).structuredContent["data"]
                report = {"success": True, "registered_tools": len(tools.tools), "runs": results,
                          "host_python": sys.executable, "python_version": sys.version, "os": platform.platform(),
                          "port": int(os.environ.get("FREECAD_TEST_PORT", "9876")), "capabilities": capabilities}
                (directory / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
                print(json.dumps(report, indent=2))
                return
            if "--contracts-only" in sys.argv:
                capabilities = await check_contracts(session, call)
                print(json.dumps({"success": True, "registered_tools": len(tools.tools),
                                  "host_python": sys.executable, "python_version": sys.version,
                                  "os": platform.platform(), "port": int(os.environ.get("FREECAD_TEST_PORT", "9876")),
                                  "capabilities": capabilities,
                                  "checked": ["MCP stdio schemas", "structuredContent and JSON text", "GUI RPC",
                                              "two documents with same object name", "document and object errors",
                                              "invalid arguments", "unchanged document state and volumes", "batch preview",
                                              "atomic batch success/result refs/undo/redo/rollback", "invalid batches before mutation",
                                              "multi-document success/partial failure", "all 11 batch operations",
                                              "dependency rejection and deletion rollback", "cleanup"]}, indent=2))
                return
            response = await call("create_document", name="MCP_EndToEnd_Test")
            document = json.loads(response.content[0].text)["name"]
            try:
                await call("part_box", length=20, width=20, height=20, name="TestBox", doc_name=document)
                await call("part_fillet", obj_name="TestBox", edges=["Edge1"], radius=1, doc_name=document)
                measured = await call("measure", obj_name="Fillet", doc_name=document)
                assert 7900 < json.loads(measured.content[0].text)["volume"] < 8000
                await call("undo", doc_name=document)
                objects = await call("list_objects", doc_name=document)
                assert "Fillet" not in {obj["name"] for obj in json.loads(objects.content[0].text)}
                await call("redo", doc_name=document)
                with tempfile.TemporaryDirectory() as directory:
                    for extension in ["step", "stl", "obj"]:
                        path = str(Path(directory) / ("smoke." + extension))
                        await call("export_" + extension, path=path, obj_names=["Fillet"], doc_name=document)
                        assert Path(path).stat().st_size > 100
                image = await call("screenshot", width=320, height=240, view="isometric", doc_name=document)
                assert image.content[0].type == "image"
                assert base64.b64decode(image.content[0].data).startswith(b"\x89PNG\r\n\x1a\n")
                scripted = await call("execute_python", code="import math\nradius = 3\ndef area():\n    return math.pi * radius ** 2\nresult = area()")
                assert abs(json.loads(scripted.content[0].text)["result"] - 28.2743338823) < 1e-8
                print(json.dumps({"success": True, "registered_tools": len(tools.tools),
                                  "checked": ["stdio", "RPC", "Part fillet", "measure", "undo", "redo",
                                              "STEP", "STL", "OBJ", "MCP image", "Python namespace"]}, indent=2))
            finally:
                await call("close_document", name=document)


if __name__ == "__main__":
    asyncio.run(main())