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
import xmlrpc.client

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


ROOT = Path(__file__).resolve().parents[1]


async def check_contracts(session, call):
    response = await call("get_capabilities")
    capabilities = response.structuredContent
    assert capabilities["status"] == "success", capabilities
    assert capabilities["data"]["contract_version"] == "1.0"
    assert capabilities["data"]["bridge_api_version"] == "0.11.0"
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
        await check_jobs(session, call, documents[0])
        return capabilities["data"]
    finally:
        for document in reversed(documents):
            await call("close_document", name=document)
        final = json.loads((await call("get_status")).content[0].text)
        assert final["documents"] == initial["documents"]


async def check_jobs(session, call, document):
    step = {"id": "job_box", "operation": "part_box", "doc_name": document,
            "arguments": {"length": 7, "width": 8, "height": 9, "name": "JobBox"}}
    started = (await call("start_batch_job", steps=[step])).structuredContent
    assert started["status"] == "success" and started["data"]["status"] in {"queued", "running", "succeeded"}
    job_id = started["data"]["job_id"]
    reconnect = await call("connect", port=int(os.environ.get("FREECAD_TEST_PORT", "9876")))
    assert reconnect.content[0].text.startswith("Connected"), reconnect
    for _ in range(200):
        job = (await call("get_job", job_id=job_id)).structuredContent["data"]
        if job["status"] not in {"queued", "running"}:
            break
        await asyncio.sleep(0.01)
    assert job["status"] == "succeeded", job
    repeated = (await call("get_job", job_id=job_id)).structuredContent["data"]
    assert repeated == job
    page = (await call("list_objects_page", doc_name=document, offset=0, limit=256)).structuredContent["data"]
    assert page["total"] >= len(page["objects"]) and page["has_more"] is False
    assert sum(item["name"] == "JobBox" for item in page["objects"]) == 1

    failed_step = {"id": "bad", "operation": "part_fillet", "doc_name": document,
                   "arguments": {"obj_name": "JobBox", "edges": ["Edge999"], "radius": 1}}
    failed_id = (await call("start_batch_job", steps=[failed_step])).structuredContent["data"]["job_id"]
    for _ in range(200):
        failed = (await call("get_job", job_id=failed_id)).structuredContent["data"]
        if failed["status"] not in {"queued", "running"}:
            break
        await asyncio.sleep(0.01)
    assert failed["status"] == "failed", failed
    assert failed["result"]["status"] == "rolled_back", failed

    unknown = (await call("get_job", job_id="00000000-0000-4000-8000-000000000000")).structuredContent
    assert unknown["data"]["status"] == "unknown"
    assert unknown["warnings"], unknown


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
                captured = await invoke("capture_view", doc_name=main, view=preset, width=800, height=600, selections=[top])
                assert captured["active_document"] == captured["active_document_before"] is not None, {
                    "preset": preset, "before": captured["active_document_before"], "after": captured["active_document"]}
                current_other_state = await invoke("get_view_state", doc_name=other, obj_names=["Box"])
                assert current_other_state == other_state, {"preset": preset, "expected": other_state, "actual": current_other_state}
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


async def check_stage6(session, call, directory):
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

    assert not json.loads((await call("get_status")).content[0].text)["documents"], "Stage 6 needs an empty isolated instance"
    try:
        main = (await invoke("create_document", name="MCP_Stage6"))["name"]
        documents.append(main)
        housing_body = (await invoke("partdesign_body", doc_name=main, name="HousingBody"))["name"]
        await invoke("partdesign_datum", doc_name=main, body_name=housing_body,
                     kind="plane", name="HousingDatum", z=5, rotation_z=15)
        await invoke("create_sketch", doc_name=main, name="HousingProfile", body_name=housing_body)
        await invoke("sketch_add_rectangle", doc_name=main, sketch_name="HousingProfile",
                     x1=-20, y1=-10, x2=20, y2=10)
        pad = await invoke("partdesign_pad", doc_name=main, sketch_name="HousingProfile", length=10)
        assert abs(pad["volume"] - 8000) < 1e-6
        await invoke("create_sketch", doc_name=main, name="HousingHole", body_name=housing_body, offset=10)
        await invoke("sketch_add_circle", doc_name=main, sketch_name="HousingHole", cx=-15, cy=5, radius=2)
        hole = await invoke("partdesign_hole", doc_name=main, sketch_name="HousingHole",
                            diameter=4, depth=10, cut_type="counterbore",
                            cut_diameter=8, cut_depth=2)
        transformed = await invoke(
            "partdesign_multi_transform", doc_name=main, feature_names=[hole["name"]],
            transformations=[{"type": "mirrored", "plane": "XZ"},
                             {"type": "linear", "direction": "X", "length": 30.0, "occurrences": 4}],
        )
        expected_housing = 8000 - 8 * math.pi * (4 * 10 + 12 * 2)
        assert abs(transformed["volume"] - expected_housing) < 1e-4, transformed
        before_edit = (await invoke("measure", doc_name=main, obj_name=housing_body))["volume"]
        edited = await invoke("partdesign_edit_feature", doc_name=main, feature_name=hole["name"],
                              parameters={"depth": 8})
        assert edited["tip"] == transformed["name"]
        after_edit = (await invoke("measure", doc_name=main, obj_name=housing_body))["volume"]
        assert after_edit > before_edit

        before_failure = await invoke("inspect_document", doc_name=main)
        failure = await session.call_tool(
            "partdesign_multi_transform",
            {"doc_name": main, "feature_names": [hole["name"]],
             "transformations": [{"type": "linear", "direction": "X", "length": 0, "occurrences": 2}]},
        )
        transcript.append({"tool": "partdesign_multi_transform", "arguments": {"invalid_length": 0},
                           "is_error": failure.isError,
                           "result": [getattr(content, "text", "") for content in failure.content]})
        assert failure.isError
        after_failure = await invoke("inspect_document", doc_name=main)
        assert [item["reference"]["object"] for item in after_failure["objects"]] == [
            item["reference"]["object"] for item in before_failure["objects"]]

        flange_body = (await invoke("partdesign_body", doc_name=main, name="FlangeBody"))["name"]
        await invoke("create_sketch", doc_name=main, name="FlangeProfile", body_name=flange_body)
        await invoke("sketch_add_polygon", doc_name=main, sketch_name="FlangeProfile",
                     points=[[0, 0], [30, 0], [30, 8], [10, 8], [10, 48], [0, 48]], close=True)
        flange = await invoke("partdesign_revolution", doc_name=main, sketch_name="FlangeProfile", angle=360)
        assert abs(flange["volume"] - 11200 * math.pi) < 1e-4
        edited_flange = await invoke("partdesign_edit_feature", doc_name=main, feature_name=flange["name"],
                                     parameters={"angle": 180})
        assert abs(edited_flange["volume"] - 5600 * math.pi) < 1e-4
        await invoke("partdesign_edit_feature", doc_name=main, feature_name=flange["name"],
                     parameters={"angle": 360})

        path = str(directory / "stage6.FCStd")
        await invoke("save_document_safe", doc_name=main, path=path)
        await invoke("export_step", doc_name=main, obj_names=[housing_body, flange_body],
                     path=str(directory / "stage6.step"))
        await invoke("close_document_safe", doc_name=main)
        documents.remove(main)
        main = (await invoke("open_document", path=path))["name"]
        documents.append(main)
        restored = await invoke("inspect_document", doc_name=main)
        restored_names = {item["reference"]["object"] for item in restored["objects"]}
        assert {housing_body, flange_body, transformed["name"], flange["name"]} <= restored_names
        housing_tip = await invoke("get_properties", doc_name=main, obj_name=housing_body, properties=["Tip"])
        flange_tip = await invoke("get_properties", doc_name=main, obj_name=flange_body, properties=["Tip"])
        assert housing_tip["properties"][0]["value"]["object"] == transformed["name"]
        assert flange_tip["properties"][0]["value"]["object"] == flange["name"]
        return {"calls": len(transcript), "fcstd": path, "step": str(directory / "stage6.step"),
                "housing_volume": after_edit, "flange_volume": edited_flange["volume"]}
    finally:
        for document in reversed(documents):
            await invoke("close_document_safe", doc_name=document, discard_changes=True)
        (directory / "mcp-transcript.json").write_text(json.dumps(transcript, indent=2), encoding="utf-8")
        assert not json.loads((await call("get_status")).content[0].text)["documents"]


async def check_stage7(session, call, directory):
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

    assert not json.loads((await call("get_status")).content[0].text)["documents"], "Stage 7 needs an empty isolated instance"
    try:
        main = (await invoke("create_document", name="MCP_Stage7"))["name"]
        documents.append(main)
        source = (await invoke("part_cylinder", doc_name=main, name="ProfileSource",
                       radius=2, height=1))["name"]
        source_edges = await invoke("list_subelements", doc_name=main, obj_name=source,
                        kind="edge", filters={"geometry_type": "circle"})
        source_edge = min(source_edges["items"], key=lambda item: item["position"][2])["selection"]
        wire = await invoke("part_wire", doc_name=main, obj_name=source,
                    edges=[source_edge], closed=True, name="ProfileWire")
        face = await invoke("part_face", doc_name=main, outer_wire_name=wire["name"], name="ProfileFace")
        extrusion = await invoke("part_extrude", doc_name=main, obj_name=face["name"],
                                 vector_x=0, vector_y=0, vector_z=10)
        assert abs(extrusion["volume"] - 40 * math.pi) < 1e-6

        second_source = (await invoke("part_cylinder", doc_name=main, name="SecondProfileSource",
                          radius=2, height=1, z=10))["name"]
        second_edges = await invoke("list_subelements", doc_name=main, obj_name=second_source,
                        kind="edge", filters={"geometry_type": "circle"})
        second_edge = min(second_edges["items"], key=lambda item: item["position"][2])["selection"]
        second_wire = await invoke("part_wire", doc_name=main, obj_name=second_source,
                       edges=[second_edge], closed=True, name="SecondWire")
        loft = await invoke("part_loft", doc_name=main,
                            section_names=[wire["name"], second_wire["name"]], solid=True)
        assert abs(loft["volume"] - 40 * math.pi) < 1e-6

        first_box = (await invoke("part_box", doc_name=main, name="BooleanFirst",
                                  length=10, width=10, height=10))["name"]
        second_box = (await invoke("part_box", doc_name=main, name="BooleanSecond",
                                   length=10, width=10, height=10, x=5))["name"]
        fused = await invoke("boolean_fuse", doc_name=main, obj_names=[first_box, second_box], name="BooleanFuse")
        assert abs(fused["volume"] - 1500) < 1e-6
        assert fused["quality"]["output"]["valid"]
        section = await invoke("part_section", doc_name=main, first_name=first_box, second_name=second_box)
        assert section["num_edges"] > 0

        split_source = (await invoke("part_box", doc_name=main, name="SplitSource",
                                     length=10, width=10, height=10))["name"]
        split = await invoke("part_split", doc_name=main, obj_name=split_source,
                             plane_origin=[5, 5, 5], plane_normal=[1, 0, 0])
        assert split["num_parts"] == 2
        assert abs(split["parts_volume"] - 1000) < 1e-6
        offset_2d = await invoke("part_offset_2d", doc_name=main, obj_name=wire["name"], distance=1)
        assert offset_2d["closed"]
        offset_3d = await invoke("part_offset_shape", doc_name=main, obj_name=extrusion["name"], distance=1)
        assert offset_3d["shape_valid"]
        refined = await invoke("part_refine", doc_name=main, obj_name=fused["name"])
        assert abs(refined["before"]["volume"] - refined["after"]["volume"]) < 1e-6
        repaired = await invoke("part_repair", doc_name=main, obj_name=refined["name"])
        validation = await invoke("part_validate", doc_name=main, obj_name=repaired["name"])
        assert validation["quality"]["valid"]

        before_failure = await invoke("inspect_document", doc_name=main)
        failure = await session.call_tool("part_split", {"doc_name": main, "obj_name": split_source,
                                                          "plane_origin": [50, 50, 50],
                                                          "plane_normal": [1, 0, 0],
                                                          "name": "InvalidSplit"})
        transcript.append({"tool": "part_split", "arguments": {"outside_plane": True},
                           "is_error": failure.isError,
                           "result": [getattr(content, "text", "") for content in failure.content]})
        assert failure.isError
        after_failure = await invoke("inspect_document", doc_name=main)
        assert [item["reference"]["object"] for item in before_failure["objects"]] == [
            item["reference"]["object"] for item in after_failure["objects"]]

        path = str(directory / "stage7.FCStd")
        step_path = str(directory / "stage7.step")
        await invoke("save_document_safe", doc_name=main, path=path)
        await invoke("export_step", doc_name=main, obj_names=[extrusion["name"], loft["name"], repaired["name"]],
                     path=step_path)
        await invoke("close_document_safe", doc_name=main)
        documents.remove(main)
        main = (await invoke("open_document", path=path))["name"]
        documents.append(main)
        restored = await invoke("part_validate", doc_name=main, obj_name=repaired["name"])
        assert restored["quality"]["valid"]
        return {"calls": len(transcript), "fcstd": path, "step": step_path,
                "extrusion_volume": extrusion["volume"], "loft_volume": loft["volume"]}
    finally:
        for document in reversed(documents):
            await invoke("close_document_safe", doc_name=document, discard_changes=True)
        (directory / "mcp-transcript.json").write_text(json.dumps(transcript, indent=2), encoding="utf-8")
        assert not json.loads((await call("get_status")).content[0].text)["documents"]


async def check_stage8_a1(session, call, directory):
    transcript = []
    documents = []

    async def invoke(tool, error=None, **arguments):
        response = await session.call_tool(tool, arguments)
        text = [getattr(content, "text", "") for content in response.content]
        result = (response.structuredContent if response.structuredContent and "contract_version" in response.structuredContent
                  else (None if response.isError else json.loads(response.content[0].text)))
        transcript.append({"tool": tool, "arguments": arguments, "is_error": response.isError,
                           "result": result or text})
        if error:
            assert response.isError or (result and result.get("status") == "error"), (tool, text)
            if result and "contract_version" in result:
                assert result["error"]["code"] == error, result
            return None
        assert not response.isError, (tool, text)
        if "contract_version" in result:
            assert result["status"] == "success", result
            return result["data"]
        return result

    async def volume(document, obj_name, expected):
        measurement = await invoke("measure", doc_name=document, obj_name=obj_name)
        assert abs(measurement["volume"] - expected) < 1e-5, measurement
        return measurement

    async def constrain_rectangle(document, sketch, values):
        constraints = []
        for tool, arguments in [
            ("sketch_constrain_distance_x", {"geo_idx": 0, "point_idx": 1, "value": values[0]}),
            ("sketch_constrain_distance_y", {"geo_idx": 0, "point_idx": 1, "value": values[1]}),
            ("sketch_constrain_length", {"geo_idx": 0, "value": values[2]}),
            ("sketch_constrain_length", {"geo_idx": 1, "value": values[3]}),
        ]:
            result = await invoke(tool, doc_name=document, sketch_name=sketch, **arguments)
            constraints.append(result["constraint_index"])
        info = await invoke("sketch_info", doc_name=document, sketch_name=sketch)
        assert info["fully_constrained"] and info["degrees_of_freedom"] == 0, info
        return constraints

    assert not json.loads((await call("get_status")).content[0].text)["documents"], "A1 needs an empty isolated instance"
    try:
        document = (await invoke("create_document", name="MCP_Stage8_A1"))["name"]
        documents.append(document)
        sheet = (await invoke("create_spreadsheet", doc_name=document, name="Parameters"))["name"]
        await invoke("set_spreadsheet_cells", doc_name=document, obj_name=sheet,
                     cells={"A1": "80 mm", "A2": "50 mm", "A3": "30 mm", "A4": "3 mm"})
        for cell, alias in [("A1", "LengthParam"), ("A2", "WidthParam"),
                            ("A3", "HeightParam"), ("A4", "WallParam")]:
            await invoke("set_spreadsheet_alias", doc_name=document, obj_name=sheet, cell=cell, alias=alias)

        body = (await invoke("partdesign_body", doc_name=document, name="HousingBody"))["name"]
        outer = (await invoke("create_sketch", doc_name=document, name="OuterProfile", body_name=body))["name"]
        await invoke("sketch_add_rectangle", doc_name=document, sketch_name=outer,
                     x1=0, y1=0, x2=80, y2=50)
        outer_constraints = await constrain_rectangle(document, outer, (0, 0, 80, 50))
        for index, expression in zip(outer_constraints,
                                     ["0 mm", "0 mm", "Parameters.LengthParam", "Parameters.WidthParam"]):
            await invoke("set_expression", doc_name=document, obj_name=outer,
                         property_name=f"Constraints[{index}]", expression=expression)
        pad = (await invoke("partdesign_pad", doc_name=document, sketch_name=outer,
                            length=30, name="HousingPad"))["name"]
        await invoke("set_expression", doc_name=document, obj_name=pad,
                     property_name="Length", expression="Parameters.HeightParam")

        inner = (await invoke("create_sketch", doc_name=document, name="InnerProfile",
                              body_name=body, offset=30))["name"]
        await invoke("sketch_add_rectangle", doc_name=document, sketch_name=inner,
                     x1=3, y1=3, x2=77, y2=47)
        inner_constraints = await constrain_rectangle(document, inner, (3, 3, 74, 44))
        for index, expression in zip(inner_constraints,
                                     ["Parameters.WallParam", "Parameters.WallParam",
                                      "Parameters.LengthParam-2*Parameters.WallParam",
                                      "Parameters.WidthParam-2*Parameters.WallParam"]):
            await invoke("set_expression", doc_name=document, obj_name=inner,
                         property_name=f"Constraints[{index}]", expression=expression)
        await invoke("set_expression", doc_name=document, obj_name=inner,
                     property_name="Placement.Base.z", expression="Parameters.HeightParam")
        pocket = (await invoke("partdesign_pocket", doc_name=document, sketch_name=inner,
                               length=27, name="HousingPocket"))["name"]
        await invoke("set_expression", doc_name=document, obj_name=pocket,
                     property_name="Length", expression="Parameters.HeightParam-Parameters.WallParam")
        initial = await volume(document, body, 32088)
        assert initial["bounding_box"]["min"] == {"x": 0.0, "y": 0.0, "z": 0.0}, initial
        assert initial["bounding_box"]["max"] == {"x": 80.0, "y": 50.0, "z": 30.0}, initial

        before = await invoke("inspect_document", doc_name=document)
        await invoke("set_spreadsheet_cells", error="invalid_expression", doc_name=document,
                     obj_name=sheet, cells={"A4": "26 mm"})
        await volume(document, body, 32088)
        await invoke("set_spreadsheet_cells", error="invalid_expression", doc_name=document,
                     obj_name=sheet, cells={"A1": "=A1"})
        after = await invoke("inspect_document", doc_name=document)
        assert [item["reference"] for item in before["objects"]] == [item["reference"] for item in after["objects"]]

        await invoke("set_spreadsheet_cells", doc_name=document, obj_name=sheet, cells={"A1": "100 mm"})
        await volume(document, body, 38328)
        await invoke("undo", doc_name=document)
        await volume(document, body, 32088)
        await invoke("redo", doc_name=document)
        await volume(document, body, 38328)

        path = str(directory / "housing.FCStd")
        await invoke("save_document_safe", doc_name=document, path=path)
        await invoke("close_document_safe", doc_name=document)
        documents.remove(document)
        document = (await invoke("open_document", path=path))["name"]
        documents.append(document)
        await volume(document, body, 38328)
        await invoke("set_spreadsheet_cells", doc_name=document, obj_name=sheet, cells={"A4": "4 mm"})
        final = await volume(document, body, 49536)
        assert final["bounding_box"]["min"] == {"x": 0.0, "y": 0.0, "z": 0.0}, final
        assert final["bounding_box"]["max"] == {"x": 100.0, "y": 50.0, "z": 30.0}, final
        await invoke("save_document_safe", doc_name=document, overwrite=True)
        step_path = str(directory / "housing.step")
        stl_path = str(directory / "housing.stl")
        await invoke("export_step", doc_name=document, obj_names=[body], path=step_path)
        await invoke("export_stl", doc_name=document, obj_names=[body], path=stl_path)
        assert Path(step_path).stat().st_size > 0 and Path(stl_path).stat().st_size > 0
        step_check = (await invoke("create_document", name="MCP_A1_STEP_Check"))["name"]
        documents.append(step_check)
        await invoke("import_step", doc_name=step_check, path=step_path)
        step_objects = await invoke("list_objects", doc_name=step_check)
        assert len(step_objects) == 1
        step_quality = await invoke("part_validate", doc_name=step_check, obj_name=step_objects[0]["name"])
        assert step_quality["quality"]["num_solids"] == 1
        await volume(step_check, step_objects[0]["name"], 49536)
        stl_check = (await invoke("create_document", name="MCP_A1_STL_Check"))["name"]
        documents.append(stl_check)
        await invoke("import_stl", doc_name=stl_check, path=stl_path)
        assert len(await invoke("list_objects", doc_name=stl_check)) == 1
        return {"calls": len(transcript), "fcstd": path, "step": step_path, "stl": stl_path,
                "initial_volume": initial["volume"], "final_volume": final["volume"]}
    finally:
        for document in reversed(documents):
            await invoke("close_document_safe", doc_name=document, discard_changes=True)
        (directory / "mcp-transcript.json").write_text(json.dumps(transcript, indent=2), encoding="utf-8")
        assert not json.loads((await call("get_status")).content[0].text)["documents"]


async def check_stage8_a2(session, call, directory):
    transcript = []
    documents = []

    async def invoke(tool, error=None, **arguments):
        response = await session.call_tool(tool, arguments)
        text = [getattr(content, "text", "") for content in response.content]
        result = (response.structuredContent if response.structuredContent and "contract_version" in response.structuredContent
                  else (None if response.isError else json.loads(response.content[0].text)))
        transcript.append({"tool": tool, "arguments": arguments, "is_error": response.isError,
                           "result": result or text})
        if error:
            assert response.isError or (result and result.get("status") == "error"), (tool, text)
            return None
        assert not response.isError, (tool, text)
        if "contract_version" in result:
            assert result["status"] == "success", result
            return result["data"]
        return result

    async def volume(document, obj_name, expected):
        measurement = await invoke("measure", doc_name=document, obj_name=obj_name)
        assert abs(measurement["volume"] - expected) < 1e-4, measurement
        return measurement

    assert not json.loads((await call("get_status")).content[0].text)["documents"], "A2 needs an empty isolated instance"
    try:
        document = (await invoke("create_document", name="MCP_Stage8_A2"))["name"]
        documents.append(document)
        sheet = (await invoke("create_spreadsheet", doc_name=document, name="Parameters"))["name"]
        await invoke("set_spreadsheet_cells", doc_name=document, obj_name=sheet,
                     cells={"A1": "40 mm", "A2": "22 mm"})
        await invoke("set_spreadsheet_alias", doc_name=document, obj_name=sheet,
                     cell="A1", alias="ShaftLength")
        await invoke("set_spreadsheet_alias", doc_name=document, obj_name=sheet,
                     cell="A2", alias="PitchRadius")
        body = (await invoke("partdesign_body", doc_name=document, name="FlangeBody"))["name"]
        profile = (await invoke("create_sketch", doc_name=document, name="RevolutionProfile",
                                body_name=body))["name"]
        await invoke("sketch_add_polygon", doc_name=document, sketch_name=profile,
                     points=[[0, 0], [30, 0], [30, 8], [10, 8], [10, 48], [0, 48]], close=True)
        for index in [0, 2, 4]:
            await invoke("sketch_constrain_horizontal", doc_name=document, sketch_name=profile, geo_idx=index)
        for index in [1, 3, 5]:
            await invoke("sketch_constrain_vertical", doc_name=document, sketch_name=profile, geo_idx=index)
        await invoke("sketch_constrain_lock", doc_name=document, sketch_name=profile, geo_idx=0, point_idx=1)
        for index, value in [(0, 30), (1, 8), (2, 20)]:
            await invoke("sketch_constrain_length", doc_name=document, sketch_name=profile,
                         geo_idx=index, value=value)
        shaft_constraint = (await invoke("sketch_constrain_length", doc_name=document,
                                          sketch_name=profile, geo_idx=3, value=40))["constraint_index"]
        await invoke("set_expression", doc_name=document, obj_name=profile,
                     property_name=f"Constraints[{shaft_constraint}]", expression="Parameters.ShaftLength")
        profile_info = await invoke("sketch_info", doc_name=document, sketch_name=profile)
        assert profile_info["fully_constrained"] and not any(
            constraint["type"] == "Block" for constraint in profile_info["constraints"]), profile_info
        await invoke("partdesign_revolution", doc_name=document, sketch_name=profile,
                     angle=360, axis="V", name="FlangeRevolution")

        axial = (await invoke("create_sketch", doc_name=document, name="AxialHoleProfile",
                              body_name=body, plane="XZ", offset=48))["name"]
        await invoke("sketch_add_circle", doc_name=document, sketch_name=axial, cx=0, cy=0, radius=4)
        await invoke("sketch_constrain_lock", doc_name=document, sketch_name=axial, geo_idx=0, point_idx=3)
        await invoke("sketch_constrain_radius", doc_name=document, sketch_name=axial, geo_idx=0, radius=4)
        await invoke("set_expression", doc_name=document, obj_name=axial,
                     property_name="Placement.Base.y", expression="8 mm+Parameters.ShaftLength")
        await invoke("partdesign_hole", doc_name=document, sketch_name=axial, diameter=8,
                     depth=48, through_all=True, name="AxialHole")

        flange_hole = (await invoke("create_sketch", doc_name=document, name="FlangeHoleProfile",
                                    body_name=body, plane="XZ", offset=48))["name"]
        await invoke("sketch_add_circle", doc_name=document, sketch_name=flange_hole, cx=22, cy=0, radius=3)
        pitch_constraint = (await invoke("sketch_constrain_distance_x", doc_name=document,
                                         sketch_name=flange_hole, geo_idx=0, point_idx=3,
                                         value=22))["constraint_index"]
        await invoke("sketch_constrain_distance_y", doc_name=document, sketch_name=flange_hole,
                     geo_idx=0, point_idx=3, value=0)
        await invoke("sketch_constrain_radius", doc_name=document, sketch_name=flange_hole, geo_idx=0, radius=3)
        await invoke("set_expression", doc_name=document, obj_name=flange_hole,
                     property_name=f"Constraints[{pitch_constraint}]", expression="Parameters.PitchRadius")
        await invoke("set_expression", doc_name=document, obj_name=flange_hole,
                     property_name="Placement.Base.y", expression="8 mm+Parameters.ShaftLength")
        first_hole = await invoke("partdesign_hole", doc_name=document, sketch_name=flange_hole,
                                  diameter=6, depth=8, through_all=True, name="FlangeHole")
        pattern = await invoke("partdesign_polar_pattern", doc_name=document,
                               feature_name=first_hole["name"], axis="Y", angle=360,
                               occurrences=4, name="FlangeHolePattern")
        initial = await volume(document, body, 10144 * math.pi)
        assert initial["bounding_box"]["max"]["y"] == 48.0, initial

        await invoke("partdesign_polar_pattern", error="invalid_arguments", doc_name=document,
                     feature_name=first_hole["name"], axis="Y", angle=360,
                     occurrences=0, name="InvalidPattern")
        await volume(document, body, 10144 * math.pi)
        stale = {"object": pattern["name"], "subelement": "Face999", "expected_type": "face"}
        await invoke("partdesign_fillet", error="invalid_arguments", doc_name=document,
                     base_name=pattern["name"], edges=[stale], radius=1, name="StaleReference")
        await volume(document, body, 10144 * math.pi)

        await invoke("set_spreadsheet_cells", doc_name=document, obj_name=sheet, cells={"A1": "50 mm"})
        await volume(document, body, 10984 * math.pi)
        await invoke("undo", doc_name=document)
        await volume(document, body, 10144 * math.pi)
        await invoke("redo", doc_name=document)
        edited = await volume(document, body, 10984 * math.pi)
        assert edited["bounding_box"]["max"]["y"] == 58.0, edited

        path = str(directory / "flange.FCStd")
        await invoke("save_document_safe", doc_name=document, path=path)
        await invoke("close_document_safe", doc_name=document)
        documents.remove(document)
        document = (await invoke("open_document", path=path))["name"]
        documents.append(document)
        await volume(document, body, 10984 * math.pi)
        await invoke("set_spreadsheet_cells", doc_name=document, obj_name=sheet, cells={"A2": "23 mm"})
        final = await volume(document, body, 10984 * math.pi)
        await invoke("save_document_safe", doc_name=document, overwrite=True)
        step_path = str(directory / "flange.step")
        stl_path = str(directory / "flange.stl")
        await invoke("export_step", doc_name=document, obj_names=[body], path=step_path)
        await invoke("export_stl", doc_name=document, obj_names=[body], path=stl_path)
        step_check = (await invoke("create_document", name="MCP_A2_STEP_Check"))["name"]
        documents.append(step_check)
        await invoke("import_step", doc_name=step_check, path=step_path)
        step_objects = await invoke("list_objects", doc_name=step_check)
        assert len(step_objects) == 1
        step_quality = await invoke("part_validate", doc_name=step_check, obj_name=step_objects[0]["name"])
        assert step_quality["quality"]["num_solids"] == 1
        await volume(step_check, step_objects[0]["name"], 10984 * math.pi)
        stl_check = (await invoke("create_document", name="MCP_A2_STL_Check"))["name"]
        documents.append(stl_check)
        await invoke("import_stl", doc_name=stl_check, path=stl_path)
        assert len(await invoke("list_objects", doc_name=stl_check)) == 1
        return {"calls": len(transcript), "fcstd": path, "step": step_path, "stl": stl_path,
                "initial_volume": initial["volume"], "final_volume": final["volume"]}
    finally:
        for document in reversed(documents):
            await invoke("close_document_safe", doc_name=document, discard_changes=True)
        (directory / "mcp-transcript.json").write_text(json.dumps(transcript, indent=2), encoding="utf-8")
        assert not json.loads((await call("get_status")).content[0].text)["documents"]


async def check_stage8_a3(session, call, directory):
    transcript = []
    documents = []

    async def invoke(tool, error=None, **arguments):
        response = await session.call_tool(tool, arguments)
        text = [getattr(content, "text", "") for content in response.content]
        result = (response.structuredContent if response.structuredContent and "contract_version" in response.structuredContent
                  else (None if response.isError else json.loads(response.content[0].text)))
        transcript.append({"tool": tool, "arguments": arguments, "is_error": response.isError,
                           "result": result or text})
        if error:
            assert response.isError or (result and result.get("status") == "error"), (tool, text)
            return None
        assert not response.isError, (tool, text)
        if "contract_version" in result:
            assert result["status"] == "success", result
            return result["data"]
        return result

    async def measurement(document, obj_name, expected):
        result = await invoke("measure", doc_name=document, obj_name=obj_name)
        assert abs(result["volume"] - expected) < 1e-4, result
        return result

    async def interference(document, first, second, classification, volume=0):
        result = await invoke("check_interference",
                              first={"document": document, "object": first},
                              second={"document": document, "object": second})
        assert result["classification"] == classification, result
        assert abs(result["intersection_volume"] - volume) < 1e-5, result
        return result

    assert not json.loads((await call("get_status")).content[0].text)["documents"], "A3 needs an empty isolated instance"
    try:
        document = (await invoke("create_document", name="MCP_Stage8_A3"))["name"]
        documents.append(document)
        sheet = (await invoke("create_spreadsheet", doc_name=document, name="Parameters"))["name"]
        await invoke("set_spreadsheet_cells", doc_name=document, obj_name=sheet, cells={"A1": "30 mm"})
        await invoke("set_spreadsheet_alias", doc_name=document, obj_name=sheet, cell="A1", alias="GapParam")

        base = (await invoke("part_box", doc_name=document, name="Base",
                             length=120, width=60, height=10))["name"]
        fixed_blank = (await invoke("part_box", doc_name=document, name="FixedJawBlank",
                                    length=15, width=60, height=25, z=10))["name"]
        fixed_bore = (await invoke("part_cylinder", doc_name=document, name="FixedJawBore",
                                   radius=4.5, height=15))["name"]
        await invoke("set_placement", doc_name=document, obj_name=fixed_bore,
                     x=0, y=30, z=22.5, ry=90)
        fixed = (await invoke("boolean_cut", doc_name=document, name="FixedJaw",
                              base_name=fixed_blank, tool_name=fixed_bore))["name"]

        moving_blank = (await invoke("part_box", doc_name=document, name="MovingJawBlank",
                         length=45, width=60, height=25, x=45, z=10))["name"]
        moving_excess = (await invoke("part_box", doc_name=document, name="MovingJawExcess",
                          length=30, width=60, height=25, x=60, z=10))["name"]
        moving_bore = (await invoke("part_cylinder", doc_name=document, name="MovingJawBore",
                        radius=4.5, height=15))["name"]
        await invoke("set_placement", doc_name=document, obj_name=moving_bore,
                 x=45, y=30, z=22.5, ry=90)
        await invoke("set_expression", doc_name=document, obj_name=moving_blank,
                 property_name="Placement.Base.x", expression="15 mm+Parameters.GapParam")
        await invoke("set_expression", doc_name=document, obj_name=moving_blank,
                 property_name="Length", expression="15 mm+Parameters.GapParam")
        await invoke("set_expression", doc_name=document, obj_name=moving_excess,
                 property_name="Placement.Base.x", expression="30 mm+Parameters.GapParam")
        await invoke("set_expression", doc_name=document, obj_name=moving_excess,
                 property_name="Length", expression="Parameters.GapParam")
        await invoke("set_expression", doc_name=document, obj_name=moving_bore,
                 property_name="Placement.Base.x", expression="15 mm+Parameters.GapParam")
        moving_sized = (await invoke("boolean_cut", doc_name=document, name="MovingJawSized",
                         base_name=moving_blank, tool_name=moving_excess))["name"]
        moving = (await invoke("boolean_cut", doc_name=document, name="MovingJaw",
                       base_name=moving_sized, tool_name=moving_bore))["name"]

        spindle = (await invoke("part_cylinder", doc_name=document, name="Spindle",
                                radius=4, height=70))["name"]
        await invoke("set_placement", doc_name=document, obj_name=spindle,
                     x=15, y=30, z=22.5, ry=90)
        handle = (await invoke("part_cylinder", doc_name=document, name="Handle",
                               radius=2, height=40))["name"]
        await invoke("set_placement", doc_name=document, obj_name=handle,
                     x=90, y=10, z=22.5, rx=-90)

        finals = [base, fixed, moving, spindle, handle]
        expected = {base: 72000, fixed: 22500 - 303.75 * math.pi,
                    moving: 22500 - 303.75 * math.pi,
                    spindle: 1120 * math.pi, handle: 160 * math.pi}
        for name, expected_volume in expected.items():
            await measurement(document, name, expected_volume)
        assert abs(sum(expected.values()) - (117000 + 672.5 * math.pi)) < 1e-8
        await interference(document, base, fixed, "contact")
        await interference(document, base, moving, "contact")
        await interference(document, fixed, moving, "separated")
        fixed_clearance = await interference(document, fixed, spindle, "separated")
        moving_clearance = await interference(document, moving, spindle, "separated")
        assert abs(fixed_clearance["distance"] - 0.5) < 1e-6
        assert abs(moving_clearance["distance"] - 0.5) < 1e-6

        await invoke("set_spreadsheet_cells", doc_name=document, obj_name=sheet, cells={"A1": "45 mm"})
        distance = await invoke("measure_distance",
                                first={"document": document, "object": fixed},
                                second={"document": document, "object": moving})
        assert abs(distance["distance"] - 45) < 1e-6, distance
        await invoke("undo", doc_name=document)
        assert abs((await invoke("measure_distance",
                                 first={"document": document, "object": fixed},
                                 second={"document": document, "object": moving}))["distance"] - 30) < 1e-6
        await invoke("redo", doc_name=document)
        assert abs((await invoke("measure_distance",
                                 first={"document": document, "object": fixed},
                                 second={"document": document, "object": moving}))["distance"] - 45) < 1e-6
        await invoke("set_spreadsheet_cells", error="invalid_expression", doc_name=document,
                     obj_name=sheet, cells={"A1": "-1 mm"})
        await measurement(document, moving, expected[moving])
        await invoke("measure", error="document_not_found", doc_name="MCP_Missing_A3", obj_name=base)

        before_job = await invoke("list_objects_page", doc_name=document, offset=0, limit=256)
        step = {"id": "place_spindle", "operation": "set_placement", "doc_name": document,
                "arguments": {"obj_name": spindle, "x": 15, "y": 30, "z": 22.5, "ry": 90}}
        job_id = (await invoke("start_batch_job", steps=[step]))["job_id"]
        reconnect = await call("connect", port=int(os.environ.get("FREECAD_TEST_PORT", "9876")))
        assert reconnect.content[0].text.startswith("Connected"), reconnect
        transcript.append({"tool": "connect", "arguments": {"same_process": True},
                   "result": reconnect.content[0].text})
        for _ in range(200):
            job = await invoke("get_job", job_id=job_id)
            if job["status"] not in {"queued", "running"}:
                break
            await asyncio.sleep(0.01)
        assert job["status"] == "succeeded", job
        assert await invoke("get_job", job_id=job_id) == job
        after_job = await invoke("list_objects_page", doc_name=document, offset=0, limit=256)
        assert before_job["total"] == after_job["total"]
        assert sum(item["name"] in finals for item in after_job["objects"]) == 5

        for name, color in zip(finals, [(0.55, 0.55, 0.58), (0.8, 0.25, 0.2),
                                        (0.2, 0.45, 0.8), (0.75, 0.75, 0.78), (0.95, 0.7, 0.15)]):
            await invoke("set_color", doc_name=document, obj_name=name,
                         r=color[0], g=color[1], b=color[2])
            await invoke("set_visibility", doc_name=document, obj_name=name, visible=True)
        image = await session.call_tool("screenshot", {"doc_name": document, "width": 800,
                                                        "height": 600, "view": "isometric"})
        image_data = next(content.data for content in image.content if content.type == "image")
        screenshot_path = directory / "vise.png"
        screenshot_path.write_bytes(base64.b64decode(image_data))
        assert screenshot_path.stat().st_size > 1000

        path = str(directory / "vise.FCStd")
        await invoke("save_document_safe", doc_name=document, path=path)
        await invoke("close_document_safe", doc_name=document)
        documents.remove(document)
        document = (await invoke("open_document", path=path))["name"]
        documents.append(document)
        await invoke("set_spreadsheet_cells", doc_name=document, obj_name=sheet, cells={"A1": "35 mm"})
        assert abs((await invoke("measure_distance",
                                 first={"document": document, "object": fixed},
                                 second={"document": document, "object": moving}))["distance"] - 35) < 1e-6
        await invoke("save_document_safe", doc_name=document, overwrite=True)
        step_path = str(directory / "vise.step")
        await invoke("export_step", doc_name=document, obj_names=finals, path=step_path)
        stl_paths = []
        for name in finals:
            stl_path = str(directory / f"{name}.stl")
            await invoke("export_stl", doc_name=document, obj_names=[name], path=stl_path)
            stl_paths.append(stl_path)
        step_check = (await invoke("create_document", name="MCP_A3_STEP_Check"))["name"]
        documents.append(step_check)
        await invoke("import_step", doc_name=step_check, path=step_path)
        step_objects = await invoke("list_objects", doc_name=step_check)
        aggregates = []
        for obj in step_objects:
            quality = await invoke("part_validate", doc_name=step_check, obj_name=obj["name"])
            if quality["quality"].get("num_solids") == 5:
                aggregates.append(await invoke("measure", doc_name=step_check, obj_name=obj["name"]))
        assert len(aggregates) == 1
        assert abs(aggregates[0]["volume"] - sum(expected.values())) < 1e-3
        for index, stl_path in enumerate(stl_paths):
            stl_check = (await invoke("create_document", name=f"MCP_A3_STL_Check_{index}"))["name"]
            documents.append(stl_check)
            await invoke("import_stl", doc_name=stl_check, path=stl_path)
            assert len(await invoke("list_objects", doc_name=stl_check)) == 1
        return {"calls": len(transcript), "fcstd": path, "step": step_path,
                "stl": stl_paths, "screenshot": str(screenshot_path),
                "total_volume": sum(expected.values())}
    finally:
        for document in reversed(documents):
            await invoke("close_document_safe", doc_name=document, discard_changes=True)
        (directory / "mcp-transcript.json").write_text(json.dumps(transcript, indent=2), encoding="utf-8")
        assert not json.loads((await call("get_status")).content[0].text)["documents"]


async def check_stage9(session, call, directory):
    transcript = []
    documents = []
    arm_path = directory / "arm.FCStd"

    async def invoke(tool, error=None, **arguments):
        response = await call(tool, **arguments)
        result = (response.structuredContent if response.structuredContent and "contract_version" in response.structuredContent
                  else json.loads(response.content[0].text))
        transcript.append({"tool": tool, "arguments": arguments, "result": result})
        if "contract_version" in result:
            if error is None:
                assert result["status"] == "success", result
                return result["data"]
            assert result["status"] == "error" and result["error"]["code"] == error, result
            return result
        assert error is None, result
        return result

    def rotate_x(quaternion, length):
        x, y, z, w = quaternion
        return [length * (1 - 2 * (y * y + z * z)),
                length * 2 * (x * y + w * z),
                length * 2 * (x * z - w * y)]

    async def set_state(assembly_doc, assembly, arm, slider, angle, travel, solve=True):
        radians = math.radians(angle)
        arm_position = [0, 0, 0]
        slider_position = [travel * math.cos(radians), travel * math.sin(radians), 0]
        if solve:
            await invoke("assembly_set_component_pose", doc_name=assembly_doc, assembly_name=assembly,
                         component_name=arm, position=arm_position, rotation=[0, 0, angle])
            await invoke("assembly_set_component_pose", doc_name=assembly_doc, assembly_name=assembly,
                         component_name=slider, position=slider_position, rotation=[0, 0, angle])
        await invoke("assembly_set_component_pose", doc_name=assembly_doc, assembly_name=assembly,
                     component_name=arm, position=arm_position, rotation=[0, 0, angle], solve=False)
        await invoke("assembly_set_component_pose", doc_name=assembly_doc, assembly_name=assembly,
                     component_name=slider, position=slider_position, rotation=[0, 0, angle], solve=False)
        inspected = await invoke("assembly_inspect", doc_name=assembly_doc, assembly_name=assembly)
        placements = {item["name"]: item["placement"] for item in inspected["components"]}
        endpoint = rotate_x(placements[arm]["quaternion"], 70 if angle == 90 and travel == 15 else 60)
        expected = [60 * math.cos(radians), 60 * math.sin(radians), 0]
        if angle == 90 and travel == 15:
            expected = [0, 70, 0]
        assert max(abs(actual - wanted) for actual, wanted in zip(endpoint, expected)) <= 0.001
        assert max(abs(actual - wanted) for actual, wanted in zip(
            placements[slider]["position"], slider_position)) <= 0.001
        return inspected

    assert not json.loads((await call("get_status")).content[0].text)["documents"], "Stage 9 needs an empty isolated instance"
    paths = {"base": directory / "base.FCStd", "arm": arm_path,
             "slider": directory / "slider.FCStd", "assembly": directory / "assembly.FCStd"}
    missing_path = arm_path.with_suffix(".missing")
    try:
        sources = {}
        for key, name in [("base", "MCP_A4_Base"), ("arm", "MCP_A4_Arm"), ("slider", "MCP_A4_Slider")]:
            sources[key] = (await invoke("create_document", name=name))["name"]
            documents.append(sources[key])
        source_objects = {
            "base": (await invoke("part_box", doc_name=sources["base"], name="BaseSource",
                                  length=20, width=20, height=5, x=-10, y=-10, z=-5))["name"],
            "arm": (await invoke("part_box", doc_name=sources["arm"], name="ArmSource",
                                 length=60, width=4, height=4, y=-2, z=1))["name"],
            "slider": (await invoke("part_box", doc_name=sources["slider"], name="SliderSource",
                                    length=6, width=6, height=6, x=-3, y=-3, z=10))["name"],
        }
        for key in sources:
            await invoke("save_document_safe", doc_name=sources[key], path=str(paths[key]))

        assembly_doc = (await invoke("create_document", name="MCP_A4_Assembly"))["name"]
        documents.append(assembly_doc)
        await invoke("save_document_safe", doc_name=assembly_doc, path=str(paths["assembly"]))
        assembly = (await invoke("assembly_create", doc_name=assembly_doc, name="MotionAssembly"))["name"]
        components = {}
        for key, name in [("base", "Base"), ("arm", "Arm"), ("slider", "Slider")]:
            components[key] = (await invoke(
                "assembly_add_component", doc_name=assembly_doc, assembly_name=assembly,
                source_document=sources[key], source_object=source_objects[key], name=name))["name"]
        await invoke("assembly_set_grounded", doc_name=assembly_doc, assembly_name=assembly,
                     component_name=components["base"])
        revolute = (await invoke(
            "assembly_create_joint", doc_name=assembly_doc, assembly_name=assembly,
            joint_type="revolute", component1=components["base"], component2=components["arm"],
            angle_min=-90, angle_max=90, name="ArmRevolute"))["name"]
        slider_joint = (await invoke(
            "assembly_create_joint", doc_name=assembly_doc, assembly_name=assembly,
            joint_type="slider", component1=components["arm"], component2=components["slider"],
            offset1_rotation=[0, 90, 0], offset2_rotation=[0, 90, 0],
            length_min=0, length_max=20, name="ArmSlider"))["name"]
        initial = await invoke("assembly_inspect", doc_name=assembly_doc, assembly_name=assembly)
        assert initial["dof_exact"] and initial["independent_dof"] == 2
        assert {item["joint_type"] for item in initial["joints"]} == {"Revolute", "Slider"}
        assert all(item["reference1"] and item["reference2"] for item in initial["joints"])

        states = []
        for angle, travel in [(0, 0), (45, 10), (90, 20)]:
            states.append(await set_state(assembly_doc, assembly, components["arm"], components["slider"],
                                          angle, travel))
            collisions = await invoke("assembly_check_collisions", doc_name=assembly_doc,
                                      assembly_name=assembly)
            assert not collisions["interferences"], (angle, travel, collisions)

        before_ground = await invoke("assembly_inspect", doc_name=assembly_doc, assembly_name=assembly)
        failed_ground = await invoke("assembly_set_grounded", error="assembly_unsolved", doc_name=assembly_doc,
                                     assembly_name=assembly, component_name=components["arm"])
        assert failed_ground["error"]["state"] == "rolled_back"
        after_ground = await invoke("assembly_inspect", doc_name=assembly_doc, assembly_name=assembly)
        compared = json.loads(json.dumps(after_ground))
        for before_component, after_component in zip(before_ground["components"], compared["components"]):
            for field in ["position", "quaternion"]:
                assert len(before_component["placement"][field]) == len(after_component["placement"][field])
                assert all(math.isclose(actual, expected, rel_tol=0, abs_tol=1e-12)
                           for actual, expected in zip(after_component["placement"][field], before_component["placement"][field])), after_ground
            after_component["placement"] = before_component["placement"]
        assert compared == before_ground, (before_ground, after_ground)

        await invoke("assembly_set_component_pose", doc_name=assembly_doc, assembly_name=assembly,
                     component_name=components["slider"], position=[0, 30, -9], rotation=[0, 0, 90], solve=False)
        collision = await invoke("assembly_check_collisions", doc_name=assembly_doc, assembly_name=assembly)
        assert any(pair["intersection_volume"] > 0.000001 and
                   components["arm"] in {pair["first"], pair["second"]} and
                   components["slider"] in {pair["first"], pair["second"]}
                   for pair in collision["interferences"]), collision
        await set_state(assembly_doc, assembly, components["arm"], components["slider"], 90, 20)

        await invoke("set_properties", doc_name=sources["arm"], obj_name=source_objects["arm"],
                     values={"Length": {"value": 70, "unit": "mm"}})
        await invoke("recompute_document", doc_name=assembly_doc)
        assert abs((await invoke("measure", doc_name=assembly_doc, obj_name=components["arm"]))["volume"] - 1120) < 1e-6
        await invoke("undo", doc_name=sources["arm"])
        await invoke("recompute_document", doc_name=assembly_doc)
        assert abs((await invoke("measure", doc_name=assembly_doc, obj_name=components["arm"]))["volume"] - 960) < 1e-6
        await invoke("redo", doc_name=sources["arm"])
        await invoke("recompute_document", doc_name=assembly_doc)
        assert abs((await invoke("measure", doc_name=assembly_doc, obj_name=components["arm"]))["volume"] - 1120) < 1e-6

        for key in sources:
            await invoke("save_document_safe", doc_name=sources[key], overwrite=True)
        await invoke("save_document_safe", doc_name=assembly_doc, overwrite=True)
        await invoke("close_document_safe", doc_name=assembly_doc)
        documents.remove(assembly_doc)
        for key in reversed(list(sources)):
            await invoke("close_document_safe", doc_name=sources[key])
            documents.remove(sources[key])

        for key in sources:
            sources[key] = (await invoke("open_document", path=str(paths[key])))["name"]
            documents.append(sources[key])
        assembly_doc = (await invoke("open_document", path=str(paths["assembly"])))["name"]
        documents.append(assembly_doc)
        reopened = await invoke("assembly_inspect", doc_name=assembly_doc, assembly_name=assembly)
        assert reopened["independent_dof"] == 2 and reopened["dof_exact"]
        joint_map = {item["name"]: item for item in reopened["joints"]}
        assert joint_map[revolute]["limits"] == {"length_min": None, "length_max": None,
                                                   "angle_min": -90.0, "angle_max": 90.0}
        assert joint_map[slider_joint]["limits"] == {"length_min": 0.0, "length_max": 20.0,
                                                       "angle_min": None, "angle_max": None}
        assert all(item["resolved"] for item in reopened["components"])
        await set_state(assembly_doc, assembly, components["arm"], components["slider"], 90, 15)
        await invoke("save_document_safe", doc_name=assembly_doc, overwrite=True)

        step_path = directory / "assembly.step"
        exported = await invoke("export_step", doc_name=assembly_doc,
                                obj_names=[components["base"], components["arm"], components["slider"]],
                                path=str(step_path))
        assert exported["objects_exported"] == 3 and exported["losses"]
        assert any("joints" in warning.lower() for warning in exported["warnings"])
        step_doc = (await invoke("create_document", name="MCP_A4_STEP_Check"))["name"]
        documents.append(step_doc)
        await invoke("import_step", doc_name=step_doc, path=str(step_path))
        step_objects = await invoke("list_objects", doc_name=step_doc)
        qualities = [await invoke("part_validate", doc_name=step_doc, obj_name=obj["name"])
                     for obj in step_objects if obj["type"] != "App::Part"]
        solid_qualities = [item["quality"] for item in qualities if item["quality"].get("num_solids", 0)]
        assert sum(item["num_solids"] for item in solid_qualities) == 3
        assert all(item["valid"] for item in solid_qualities)
        await invoke("close_document_safe", doc_name=step_doc, discard_changes=True)
        documents.remove(step_doc)

        await invoke("close_document_safe", doc_name=assembly_doc)
        documents.remove(assembly_doc)
        for key in reversed(list(sources)):
            await invoke("close_document_safe", doc_name=sources[key], discard_changes=True)
            documents.remove(sources[key])
        arm_path.replace(missing_path)
        missing_doc = (await invoke("open_document", path=str(paths["assembly"])))["name"]
        documents.append(missing_doc)
        unresolved = await invoke("assembly_inspect", doc_name=missing_doc, assembly_name=assembly)
        assert any(item["name"] == components["arm"] and not item["resolved"]
                   for item in unresolved["components"]), unresolved
        joint_fixtures = []
        for joint_type, expected_dof in {"fixed": 0, "revolute": 1, "slider": 1,
                                         "cylindrical": 2, "ball": 3}.items():
            fixture_doc = (await invoke("create_document", name=f"MCP_V_Joint_{joint_type}"))["name"]
            documents.append(fixture_doc)
            for source in ["SourceA", "SourceB"]:
                await invoke("part_box", doc_name=fixture_doc, name=source, length=5, width=5, height=5)
            fixture_assembly = (await invoke("assembly_create", doc_name=fixture_doc, name="Fixture"))["name"]
            fixture_components = []
            for source, position in [("SourceA", [0, 0, 0]), ("SourceB", [20, 0, 0])]:
                fixture_components.append((await invoke(
                    "assembly_add_component", doc_name=fixture_doc, assembly_name=fixture_assembly,
                    source_document=fixture_doc, source_object=source,
                    name=f"Component{source}", position=position))["name"])
            await invoke("assembly_set_grounded", doc_name=fixture_doc, assembly_name=fixture_assembly,
                         component_name=fixture_components[0], grounded=True)
            limits = {}
            if joint_type in {"slider", "cylindrical"}:
                limits.update(length_min=-10, length_max=10)
            if joint_type in {"revolute", "cylindrical"}:
                limits.update(angle_min=-90, angle_max=90)
            connectors = []
            for component, position in zip(fixture_components, [[0, 0, 0], [20, 0, 0]]):
                face = (await invoke("select_subelement", doc_name=fixture_doc, obj_name=component,
                                     kind="face", filters={"normal": [-1, 0, 0]}))["selection"]
                vertex = (await invoke("select_subelement", doc_name=fixture_doc, obj_name=component,
                                       kind="vertex", filters={"position": position}))["selection"]
                connectors.append((face["subelement"], vertex["subelement"]))
            joint = await invoke("assembly_create_joint", doc_name=fixture_doc, assembly_name=fixture_assembly,
                                 joint_type=joint_type, component1=fixture_components[0],
                                 component2=fixture_components[1], subelement1=connectors[0][0],
                                 vertex1=connectors[0][1], subelement2=connectors[1][0],
                                 vertex2=connectors[1][1], **limits)
            assert joint["solver_code"] == 0, joint
            baseline = await invoke("assembly_inspect", doc_name=fixture_doc, assembly_name=fixture_assembly)
            assert baseline["dof_exact"] and baseline["independent_dof"] == expected_dof, baseline
            assert baseline["joints"][0]["joint_type"].lower() == joint_type
            assert baseline["joints"][0]["reference1"]["component"] == fixture_components[0]
            assert baseline["joints"][0]["reference2"]["component"] == fixture_components[1]
            collisions = await invoke("assembly_check_collisions", doc_name=fixture_doc,
                                      assembly_name=fixture_assembly)
            assert len(collisions["pairs"]) == 1, collisions
            await invoke("assembly_set_joint", doc_name=fixture_doc, assembly_name=fixture_assembly,
                         joint_name=joint["name"], suppressed=True)
            assert (await invoke("assembly_inspect", doc_name=fixture_doc,
                                 assembly_name=fixture_assembly))["joints"][0]["suppressed"]
            await invoke("undo", doc_name=fixture_doc)
            assert not (await invoke("assembly_inspect", doc_name=fixture_doc,
                                     assembly_name=fixture_assembly))["joints"][0]["suppressed"]
            await invoke("redo", doc_name=fixture_doc)
            assert (await invoke("assembly_inspect", doc_name=fixture_doc,
                                 assembly_name=fixture_assembly))["joints"][0]["suppressed"]
            before_error = await invoke("assembly_inspect", doc_name=fixture_doc, assembly_name=fixture_assembly)
            await invoke("assembly_set_joint", doc_name=fixture_doc, assembly_name=fixture_assembly,
                         joint_name=joint["name"], length_min=20, length_max=-20, error="invalid_arguments")
            assert await invoke("assembly_inspect", doc_name=fixture_doc,
                                assembly_name=fixture_assembly) == before_error
            await invoke("assembly_create_joint", doc_name=fixture_doc, assembly_name=fixture_assembly,
                         joint_type=joint_type, component1=fixture_components[0],
                         component2=fixture_components[0], error="invalid_arguments")
            assert await invoke("assembly_inspect", doc_name=fixture_doc,
                                assembly_name=fixture_assembly) == before_error
            fixture_path = directory / f"joint-{joint_type}.FCStd"
            await invoke("save_document_safe", doc_name=fixture_doc, path=str(fixture_path))
            await invoke("close_document_safe", doc_name=fixture_doc)
            documents.remove(fixture_doc)
            fixture_doc = (await invoke("open_document", path=str(fixture_path)))["name"]
            documents.append(fixture_doc)
            restored = await invoke("assembly_inspect", doc_name=fixture_doc, assembly_name=fixture_assembly)
            assert restored["joints"][0]["suppressed"] and all(item["resolved"] for item in restored["components"])
            for limit, value in limits.items():
                assert restored["joints"][0]["limits"][limit] == value
            await invoke("assembly_set_joint", doc_name=fixture_doc, assembly_name=fixture_assembly,
                         joint_name=joint["name"], suppressed=False)
            await invoke("recompute_document", doc_name=fixture_doc)
            edited = await invoke("assembly_inspect", doc_name=fixture_doc, assembly_name=fixture_assembly)
            assert edited["dof_exact"] and edited["independent_dof"] == expected_dof, edited
            await invoke("save_document_safe", doc_name=fixture_doc, overwrite=True)
            await invoke("close_document_safe", doc_name=fixture_doc)
            documents.remove(fixture_doc)
            joint_fixtures.append({"type": joint_type, "dof": expected_dof, "fcstd": str(fixture_path),
                                   "reopen_second_edit": True, "invalid_mutation_unchanged": True})
        return {"calls": len(transcript), "fcstd": {key: str(path) for key, path in paths.items()},
                "step": str(step_path), "states": [(0, 0), (45, 10), (90, 20), (90, 15)],
                "joint_fixtures": joint_fixtures,
                "step_losses": exported["losses"]}
    finally:
        for document in reversed(documents):
            response = await session.call_tool("close_document_safe", {"doc_name": document, "discard_changes": True})
            transcript.append({"tool": "close_document_safe", "arguments": {"doc_name": document},
                               "is_error": response.isError})
        if missing_path.exists() and not arm_path.exists():
            missing_path.replace(arm_path)
        (directory / "mcp-transcript.json").write_text(json.dumps(transcript, indent=2), encoding="utf-8")
        assert not json.loads((await call("get_status")).content[0].text)["documents"]


async def check_stage12_security(session, call, directory):
    capabilities = (await call("get_capabilities")).structuredContent["data"]
    assert not capabilities["features"]["raw_python_enabled"], capabilities
    assert capabilities["options"]["normal_mode"]["raw_python_disabled"], capabilities
    transcript = []
    port = int(os.environ.get("FREECAD_TEST_PORT", "9876"))
    modules = ["operations", "document_ops", "geometry_ops", "sketcher_ops", "partdesign_ops",
               "part_ops", "assembly_ops", "techdraw_ops", "draft_ops", "mesh_ops", "exchange_ops", "view_ops"]
    with xmlrpc.client.ServerProxy(f"http://127.0.0.1:{port}/RPC2", allow_none=True) as proxy:
        blocked = json.loads(proxy.execute("raise RuntimeError('RAW_CODE_EXECUTED')"))
        assert blocked["error_details"]["code"] == "raw_python_disabled", blocked
        transcript.append({"rpc": "execute", "response": blocked})
        for module in modules:
            for function in ["exec", "eval", "compile", "__import__", "_execute_code", "FreeCAD", "importlib"]:
                target = "freecad_ai_bridge." + module
                blocked = json.loads(proxy.execute_function(target, function, "{}"))
                assert blocked["error_details"]["code"] == "rpc_not_allowed", blocked
                transcript.append({"rpc": "execute_function", "module": target, "function": function, "response": blocked})
        for module, function in [("freecad_ai_bridge.gui_executor", "_execute_code"),
                                 ("freecad_ai_bridge.security", "resolve_function"),
                                 ("os", "system"), ("builtins", "exec"),
                                 ("freecad_ai_bridge.operations", "FreeCAD.openDocument")]:
            blocked = json.loads(proxy.execute_function(module, function, "{}"))
            assert blocked["error_details"]["code"] == "rpc_not_allowed", blocked
            transcript.append({"rpc": "execute_function", "module": module, "function": function, "response": blocked})
        for module, function in [("freecad_ai_bridge.operations", "execute"), ("builtins", "exec")]:
            blocked = json.loads(proxy.start_job(module, function, '{"code":"result=42"}'))
            assert blocked["error_details"]["code"] == "job_operation_not_allowed", blocked
            transcript.append({"rpc": "start_job", "module": module, "function": function, "response": blocked})
    rejected = await session.call_tool("execute_python", {"code": "raise RuntimeError('RAW_CODE_EXECUTED')"})
    assert rejected.isError and "Raw Python is disabled" in str(rejected.content), rejected
    transcript.append({"mcp": "execute_python", "response": rejected.model_dump(mode="json")})
    document = json.loads((await call("create_document", name="MCP_NormalMode")).content[0].text)["name"]
    try:
        box = json.loads((await call("part_box", length=10, width=10, height=10, doc_name=document)).content[0].text)["name"]
        sheet = (await call("create_spreadsheet", doc_name=document)).structuredContent["data"]["reference"]["object"]
        before = json.loads((await call("list_objects", doc_name=document)).content[0].text)
        for expression in ["eval(1)", "exec(1)", "__import__(1)", "1; result=42", "open(1)", "import os"]:
            for tool, arguments in [("set_expression", {"obj_name": box, "property_name": "Length", "expression": expression}),
                                    ("set_spreadsheet_cells", {"obj_name": sheet, "cells": {"A1": "=" + expression}})]:
                response = await call(tool, doc_name=document, **arguments)
                result = response.structuredContent
                if tool == "set_spreadsheet_cells" and expression == "import os":
                    assert result["status"] == "success" and result["data"]["cells"][0]["value"] == "=import os", result
                    cleared = await call("set_spreadsheet_cells", doc_name=document, obj_name=sheet, cells={"A1": None})
                    assert cleared.structuredContent["status"] == "success", cleared
                else:
                    assert result["status"] == "error" and result["error"]["code"] == "invalid_expression", result
                transcript.append({"mcp": tool, "arguments": arguments, "response": result})
        for tool in ["execute_batch", "start_batch_job"]:
            for operation in ["execute_python", "execute", "eval", "set_expression"]:
                steps = [{"id": "code", "operation": operation, "doc_name": document, "arguments": {"code": "result=42"}}]
                response = await session.call_tool(tool, {"steps": steps})
                assert response.isError or response.structuredContent["status"] == "error", response
                transcript.append({"mcp": tool, "arguments": {"steps": steps}, "response": response.model_dump(mode="json")})
        assert json.loads((await call("list_objects", doc_name=document)).content[0].text) == before
        measured = json.loads((await call("measure", doc_name=document, obj_name=box)).content[0].text)
        assert abs(measured["volume"] - 1000) < 1e-6, measured
        state = (await call("inspect_document", doc_name=document)).structuredContent
        assert state["status"] == "success", state
        return {"negative_checks": len(transcript), "capabilities": capabilities}
    finally:
        (directory / "security-transcript.json").write_text(json.dumps(transcript, indent=2), encoding="utf-8")
        closed = (await call("close_document_safe", doc_name=document, discard_changes=True)).structuredContent
        assert closed["status"] == "success", closed


async def check_audit(session, call, directory):
    capabilities = (await call("get_capabilities")).structuredContent["data"]
    assert capabilities["bridge_api_version"] == "0.11.0"
    assert not capabilities["features"]["raw_python_enabled"]
    assert capabilities["options"]["normal_mode"]["raw_python_disabled"]
    assert not capabilities["features"]["techdraw_drawings"]
    port = int(os.environ.get("FREECAD_TEST_PORT", "9876"))
    with xmlrpc.client.ServerProxy(f"http://127.0.0.1:{port}/RPC2", allow_none=True) as proxy:
        assert proxy.get_version() == ".".join(capabilities["freecad_version"][:3])
        blocked = json.loads(proxy.execute("result = 42"))
        assert blocked["error_details"]["code"] == "raw_python_disabled", blocked
        for module, function in [("freecad_ai_bridge.gui_executor", "_execute_code"),
                                 ("freecad_ai_bridge.operations", "__import__"),
                                 ("freecad_ai_bridge.operations", "json")]:
            blocked = json.loads(proxy.execute_function(module, function, "{}"))
            assert blocked["error_details"]["code"] == "rpc_not_allowed", blocked
    rejected = await session.call_tool("execute_python", {"code": "result = 42"})
    assert rejected.isError and "Raw Python is disabled" in str(rejected.content), rejected
    assert not json.loads((await call("get_status")).content[0].text)["documents"]
    document = json.loads((await call("create_document", name="MCP_Audit_Edges")).content[0].text)["name"]
    other_document = None
    checks = ["patch version", "direct RPC raw-code rejection", "indirect RPC rejection", "MCP raw-code rejection"]
    try:
        for name, height_offset in [("First", 0), ("Second", 5)]:
            await call("part_box", length=10, width=10, height=10, z=height_offset, name=name, doc_name=document)

        async def edge(name, center_z):
            response = await call("select_subelement", doc_name=document, obj_name=name, kind="edge",
                                  filters={"position": [0, 0, center_z], "axis": [0, 0, 1]})
            assert response.structuredContent["status"] == "success", response
            return response.structuredContent["data"]["selection"]

        selection = await edge("First", 5)
        if not capabilities["features"]["techdraw_scrub_edges"]:
            response = await call("techdraw_scrub_edges", doc_name=document, edges=[selection])
            assert response.structuredContent["error"]["code"] == "unsupported_feature", response
            checks.append("older-runtime unsupported_feature")
            return {"checks": checks, "capabilities": capabilities}
        perimeter = []
        for position in ([5, 0, 10], [10, 5, 10], [5, 10, 10], [0, 5, 10]):
            response = await call("select_subelement", doc_name=document, obj_name="First", kind="edge",
                                  filters={"position": position})
            perimeter.append(response.structuredContent["data"]["selection"])
        selection = perimeter[0]
        response = await call("techdraw_scrub_edges", doc_name=document, edges=perimeter + [selection], name="Unique")
        result = response.structuredContent
        assert result["status"] == "success" and result["data"]["output_edges"] == 4, result
        assert result["warnings"] and "not a geometric union" in result["warnings"][0], result
        stale = await call("techdraw_scrub_edges", doc_name=document, edges=[selection], name="Stale")
        assert stale.structuredContent["error"]["code"] == "stale_selection", stale
        selections = [await edge("First", 5), await edge("Second", 10)]
        response = await call("techdraw_scrub_edges", doc_name=document, edges=selections, name="Cleaned")
        result = response.structuredContent
        assert result["status"] == "success" and result["data"]["output_edges"] == 1, result
        edges = (await call("list_subelements", doc_name=document, obj_name="Cleaned", kind="edge")).structuredContent["data"]
        assert abs(sum(item["length"] for item in edges["items"]) - 5) < 1e-6, edges
        await call("undo", doc_name=document)
        missing = (await call("resolve_reference", doc_name=document, obj_name="Cleaned")).structuredContent
        assert missing["error"]["code"] == "object_not_found", missing
        await call("redo", doc_name=document)
        assert (await call("resolve_reference", doc_name=document, obj_name="Cleaned")).structuredContent["status"] == "success"
        selections = [await edge("First", 5)]
        other_document = json.loads((await call("create_document", name="MCP_Audit_Other")).content[0].text)["name"]
        foreign = await call("techdraw_scrub_edges", doc_name=other_document, edges=selections)
        assert foreign.structuredContent["error"]["code"] == "invalid_reference", foreign
        await call("close_document_safe", doc_name=other_document, discard_changes=True)
        other_document = None
        path = str(directory / (document + ".FCStd"))
        saved = (await call("save_document_safe", doc_name=document, path=path)).structuredContent
        assert saved["status"] == "success", saved
        closed = (await call("close_document_safe", doc_name=document)).structuredContent
        assert closed["status"] == "success", closed
        document = None
        document = json.loads((await call("open_document", path=path)).content[0].text)["name"]
        edges = (await call("list_subelements", doc_name=document, obj_name="Cleaned", kind="edge")).structuredContent["data"]
        assert abs(sum(item["length"] for item in edges["items"]) - 5) < 1e-6, edges
        checks.extend(["native duplicate removal on closed boundary", "native open-end pruning: 5 mm / 1 edge",
                       "stale and cross-document selection rejection", "undo/redo", "FCStd roundtrip"])
        return {"checks": checks, "capabilities": capabilities}
    finally:
        for remaining in (other_document, document):
            if remaining:
                closed = (await call("close_document_safe", doc_name=remaining, discard_changes=True)).structuredContent
                assert closed["status"] == "success", closed
        assert not json.loads((await call("get_status")).content[0].text)["documents"]


def verify_stage10b_exports(directory, drawing):
    import pymupdf
    import xml.etree.ElementTree as ET

    svg = directory / "drawing.svg"
    assert ET.parse(svg).getroot().tag == "{http://www.w3.org/2000/svg}svg"
    reports = []
    for format in ("pdf", "svg"):
        with pymupdf.open(directory / ("drawing." + format)) as document:
            assert len(document) == 1
            page = document[0]
            factor = 72 / 25.4
            assert abs(page.rect.width / factor - 297) < 0.15
            assert abs(page.rect.height / factor - 210) < 0.15
            pixmap = page.get_pixmap(matrix=pymupdf.Matrix(2, 2), alpha=False)
            pixmap.save(directory / ("drawing-" + format + ".png"))
            assert sum(value < 200 for value in pixmap.samples) > 10000
            contours = [item for item in page.get_drawings() if abs((item.get("width") or 0) / factor - 0.7) < 0.01]
            checked = []
            for view in drawing["views"]:
                width, height = [value * view["scale"] for value in view["projected_bbox_mm"]]
                center_x, center_y = view["position_mm"]
                region = pymupdf.Rect((center_x - width / 2 - 0.5) * factor,
                                     (210 - center_y - height / 2 - 0.5) * factor,
                                     (center_x + width / 2 + 0.5) * factor,
                                     (210 - center_y + height / 2 + 0.5) * factor)
                assert region.x0 > 10 * factor and region.x1 < 287 * factor, (view, region)
                assert region.y0 > 10 * factor and region.y1 < 200 * factor, (view, region)
                paths = [item["rect"] for item in contours if region.contains(item["rect"])]
                assert paths, view
                actual = pymupdf.Rect(min(rectangle.x0 for rectangle in paths), min(rectangle.y0 for rectangle in paths),
                                     max(rectangle.x1 for rectangle in paths), max(rectangle.y1 for rectangle in paths))
                assert abs(actual.width / factor - width) < 0.5, (view, actual)
                assert abs(actual.height / factor - height) < 0.5, (view, actual)
                checked.append({"view": view["name"], "width_mm": actual.width / factor,
                                "height_mm": actual.height / factor, "scale": view["scale"]})
            if format == "svg":
                text = page.get_text()
                for required in ("1:1", "A2 Flange - A5", "4 holes diameter 6", "Detail 2:1", "Section A-A"):
                    assert required in text, (required, text)
            reports.append({"format": format, "pages": len(document), "views": checked,
                            "paper_mm": [page.rect.width / factor, page.rect.height / factor]})
    (directory / "render-report.json").write_text(json.dumps(reports, indent=2), encoding="utf-8")
    return reports


async def check_stage11bc(session, call, directory):
    transcript = []
    documents = []

    async def invoke(tool, error=None, schema_error=False, **arguments):
        response = await session.call_tool(tool, arguments)
        result = (response.structuredContent if response.structuredContent and "contract_version" in response.structuredContent
                  else (None if response.isError else json.loads(response.content[0].text)))
        transcript.append({"tool": tool, "arguments": arguments, "is_error": response.isError,
                           "result": result or [getattr(content, "text", "") for content in response.content]})
        if schema_error:
            assert response.isError, response
            return
        if error:
            assert result and result["status"] == "error" and result["error"]["code"] == error, result
            return result
        assert not response.isError, response
        if "contract_version" in result:
            assert result["status"] == "success", result
            return result["data"]
        return result

    async def inspect(name):
        return await invoke("mesh_inspect", doc_name=document, obj_name=name)

    async def create_document(name):
        name = (await invoke("create_document", name=name))["name"]
        documents.append(name)
        return name

    def same(actual, expected):
        if isinstance(actual, dict) and isinstance(expected, dict):
            return actual.keys() == expected.keys() and all(same(actual[key], expected[key]) for key in actual)
        if isinstance(actual, list) and isinstance(expected, list):
            return len(actual) == len(expected) and all(same(left, right) for left, right in zip(actual, expected))
        if type(actual) is float or type(expected) is float:
            return math.isclose(actual, expected, rel_tol=1e-6, abs_tol=1e-6)
        return actual == expected

    quads = [[[0, 0, 0], [0, 20, 0], [40, 20, 0], [40, 0, 0]],
             [[0, 0, 10], [40, 0, 10], [40, 20, 10], [0, 20, 10]],
             [[0, 0, 0], [40, 0, 0], [40, 0, 10], [0, 0, 10]],
             [[40, 0, 0], [40, 20, 0], [40, 20, 10], [40, 0, 10]],
             [[40, 20, 0], [0, 20, 0], [0, 20, 10], [40, 20, 10]],
             [[0, 20, 0], [0, 0, 0], [0, 0, 10], [0, 20, 10]]]
    facets = [triangle for points in quads for triangle in ([points[0], points[1], points[2]], [points[0], points[2], points[3]])]
    assert not json.loads((await call("get_status")).content[0].text)["documents"], "11b/c requires an empty isolated instance"
    try:
        document = await create_document("MCP_Stage11bc")
        other = await create_document("MCP_Stage11bc_Other")
        opened = await invoke("mesh_create", doc_name=document, facets=facets[1:], name="OpenBox")
        open_name = opened["name"]
        assert opened["facets"] == 11 and not opened["closed"], opened
        rejected = await invoke("mesh_to_shape", doc_name=document, obj_name=open_name, error="mesh_not_solid")
        assert rejected["error"]["diagnostics"]["closed"] is False, rejected
        before = await inspect(open_name)
        await invoke("mesh_repair", doc_name=document, obj_name=open_name, max_hole_edges=2,
                     require_closed=True, error="mesh_not_repairable")
        assert same(await inspect(open_name), before)
        repaired = await invoke("mesh_repair", doc_name=document, obj_name=open_name, max_hole_edges=3, require_closed=True)
        assert repaired["before"]["facets"] == 11 and repaired["after"]["closed"], repaired
        assert math.isclose(repaired["after"]["volume_mm3"], 8000, rel_tol=1e-6), repaired
        after = await inspect(open_name)
        await invoke("undo", doc_name=document)
        assert same(await inspect(open_name), before)
        await invoke("redo", doc_name=document)
        assert same(await inspect(open_name), after)
        solid = await invoke("mesh_to_shape", doc_name=document, obj_name=open_name, target="solid", tolerance=0.01)
        assert solid["shape_valid"] and math.isclose(solid["volume_mm3"], 8000, rel_tol=1e-6), solid
        triangulated = await invoke("mesh_from_shape", doc_name=document, obj_name=solid["name"], linear_deflection=0.05, angular_deflection=0.3)
        assert triangulated["closed"] and triangulated["linear_deflection_mm"] == 0.05 and not triangulated["relative"], triangulated
        await invoke("mesh_to_shape", doc_name=document, obj_name=open_name, target="shape", name="FacetedShell")
        wall = await invoke("mesh_create", doc_name=document, facets=facets[2:], name="MissingWall")
        wall_before = await inspect(wall["name"])
        await invoke("mesh_repair", doc_name=document, obj_name=wall["name"], max_hole_edges=3,
                 require_closed=True, error="mesh_not_repairable")
        assert same(await inspect(wall["name"]), wall_before)
        wall_repaired = await invoke("mesh_repair", doc_name=document, obj_name=wall["name"], max_hole_edges=4, require_closed=True)
        assert wall_repaired["after"]["closed"] and math.isclose(wall_repaired["after"]["volume_mm3"], 8000, rel_tol=1e-6), wall_repaired
        disconnected = facets + [[[point[0] + 60, point[1], point[2]] for point in facet] for facet in facets]
        components = await invoke("mesh_create", doc_name=document, facets=disconnected, name="TwoComponents")
        assert components["components"] == 2, components
        await invoke("mesh_to_shape", doc_name=document, obj_name=components["name"], error="mesh_not_solid")
        sphere = await invoke("part_sphere", doc_name=document, name="ToleranceSphere", radius=10)
        coarse = await invoke("mesh_from_shape", doc_name=document, obj_name=sphere["name"], linear_deflection=1, angular_deflection=1)
        fine = await invoke("mesh_from_shape", doc_name=document, obj_name=sphere["name"], linear_deflection=0.01, angular_deflection=0.1)
        assert fine["facets"] > coarse["facets"] and fine["closed"], (coarse, fine)
        assert math.isclose(fine["volume_mm3"], 4 * math.pi * 1000 / 3, rel_tol=0.005), fine
        for name, triangles in (("DuplicateDegenerate", facets + [facets[0], [[0, 0, 0], [1, 0, 0], [2, 0, 0]]]),
                                ("Inverted", [list(reversed(facet)) for facet in facets]),
                                ("Inconsistent", [list(reversed(facets[0]))] + facets[1:])):
            mesh = await invoke("mesh_create", doc_name=document, facets=triangles, name=name)
            snapshot = await inspect(mesh["name"])
            fixed = await invoke("mesh_repair", doc_name=document, obj_name=mesh["name"], require_closed=True)
            assert fixed["after"]["orientation"] == "outward" and fixed["after"]["closed"], fixed
            if name == "DuplicateDegenerate":
                assert fixed["removed_facets"] == 2, fixed
            await invoke("undo", doc_name=document)
            assert same(await inspect(mesh["name"]), snapshot)
            await invoke("redo", doc_name=document)
        nonmanifold = await invoke("mesh_create", doc_name=document, name="Nonmanifold",
            facets=[[[0, 0, 0], [10, 0, 0], point] for point in ([0, 10, 0], [0, 0, 10], [0, -10, 0])])
        snapshot = await inspect(nonmanifold["name"])
        await invoke("mesh_repair", doc_name=document, obj_name=nonmanifold["name"], error="mesh_not_repairable")
        assert same(await inspect(nonmanifold["name"]), snapshot)
        await invoke("mesh_inspect", doc_name=document, obj_name="MissingMesh", error="object_not_found")
        await invoke("mesh_from_shape", doc_name=document, obj_name=solid["name"], linear_deflection=True, schema_error=True)
        await invoke("mesh_create", doc_name=document, facets=[], schema_error=True)
        await invoke("set_placement", doc_name=document, obj_name=open_name, x=3, y=4, z=5)
        moved = await inspect(open_name)
        assert moved["bbox_mm"] == {"min": [3, 4, 5], "max": [43, 24, 15]}, moved
        await invoke("undo", doc_name=document)
        await invoke("redo", doc_name=document)

        group = await invoke("create_container", doc_name=document, name="ColoredAssembly", kind="group")
        links = []
        for label, position, color in (("RedComponent", 0, [0.9, 0.1, 0.1]), ("GreenComponent", 60, [0.1, 0.8, 0.2])):
            source = await invoke("part_box", doc_name=document, name="Source" + label, length=40, width=20, height=10)
            await invoke("set_color", doc_name=document, obj_name=source["name"], r=color[0], g=color[1], b=color[2])
            await invoke("set_visibility", doc_name=document, obj_name=source["name"], visible=False)
            link = await invoke("create_link", doc_name=document, name=label, source_document=document, source_object=source["name"])
            await invoke("set_placement", doc_name=document, obj_name=link["name"], x=position)
            links.append(link["name"])
        await invoke("set_container_members", doc_name=document, obj_name=group["name"], members=links)
        step_files = []
        for schema in ("AP214", "AP242"):
            path = directory / (schema + ".step")
            await invoke("exchange_export", doc_name=document, obj_names=[group["name"]], path=str(path), options={"format": "step", "step_schema": schema})
            step_files.append(str(path))
            content = path.read_bytes()
            assert (b"AUTOMOTIVE_DESIGN" if schema == "AP214" else b"AP242_MANAGED_MODEL_BASED_3D_ENGINEERING") in content
            await invoke("exchange_export", doc_name=document, obj_names=[group["name"]], path=str(path), options={"format": "step", "step_schema": schema}, error="file_exists")
            assert path.read_bytes() == content
            await invoke("exchange_export", doc_name=document, obj_names=[group["name"]], path=str(path),
                         options={"format": "step", "step_schema": schema}, overwrite=True)
            assert (b"AUTOMOTIVE_DESIGN" if schema == "AP214" else b"AP242_MANAGED_MODEL_BASED_3D_ENGINEERING") in path.read_bytes()
            target = await create_document("MCP_" + schema)
            imported = await invoke("exchange_import", doc_name=target, path=str(path), format="step")
            shapes = [obj for obj in imported["objects"] if "solids" in obj]
            assert sorted(obj["label"] for obj in shapes) == ["GreenComponent", "RedComponent"], imported
            groups = [obj for obj in imported["objects"] if "children" in obj]
            assert len(groups) == 1 and len(groups[0]["children"]) == 2, imported
            for obj in shapes:
                expected = [0.9, 0.1, 0.1] if obj["label"] == "RedComponent" else [0.1, 0.8, 0.2]
                assert all(abs(actual - value) <= 1e-6 for actual, value in zip(obj["color"], expected)), obj
                assert math.isclose(obj["volume_mm3"], 8000, rel_tol=1e-5), obj
                offset = 0 if obj["label"] == "RedComponent" else 60
                assert same(obj["bbox_mm"], {"min": [offset, 0, 0], "max": [offset + 40, 20, 10]}), obj
            first = imported["references"][0]["object"]
            await invoke("undo", doc_name=target)
            objects = await invoke("list_objects", doc_name=target)
            assert not objects, objects
            await invoke("redo", doc_name=target)
            await invoke("set_placement", doc_name=target, obj_name=first, x=7)

        source_name = solid["name"]
        for options in ({"format": "stl", "encoding": "ascii", "linear_deflection": 0.05, "angular_deflection": 0.3},
                        {"format": "stl", "encoding": "binary", "linear_deflection": 0.05, "angular_deflection": 0.3},
                        {"format": "obj", "linear_deflection": 0.05, "angular_deflection": 0.3}):
            format = options["format"]
            path = directory / (options.get("encoding", "mesh") + "." + format)
            exported = await invoke("exchange_export", doc_name=document, obj_names=[source_name], path=str(path), options=options)
            assert exported["options"]["linear_deflection"] == 0.05 and exported["warnings"], exported
            content = path.read_bytes()
            if format == "stl":
                if options["encoding"] == "ascii":
                    assert content.lstrip().startswith(b"solid") and b"facet normal" in content
                else:
                    assert len(content) == 84 + 50 * struct.unpack_from("<I", content, 80)[0]
            target = await create_document("MCP_MeshImport")
            imported = await invoke("exchange_import", doc_name=target, path=str(path), format=format)
            mesh = imported["objects"][0]
            assert mesh["closed"] and mesh["orientation"] == "outward", mesh
            assert math.isclose(mesh["volume_mm3"], 8000, rel_tol=0.005), mesh
            assert same(mesh["bbox_mm"], {"min": [0, 0, 0], "max": [40, 20, 10]}), mesh
            await invoke("undo", doc_name=target)
            assert not (await invoke("list_objects", doc_name=target))
            await invoke("redo", doc_name=target)

        planar = []
        for spec in ({"kind": "rectangle", "length": 40, "width": 20},
                     {"kind": "circle", "radius": 5, "position": [10, 10, 0]},
                     {"kind": "line", "points": [[0, 0, 0], [10, 0, 0]], "position": [55, 0, 0]},
                     {"kind": "wire", "points": [[55, 5, 0], [65, 5, 0], [65, 10, 0]]},
                     {"kind": "arc", "radius": 5, "start_angle": 0, "end_angle": 90, "position": [55, 10, 0]}):
            planar.append((await invoke("draft_create_element", doc_name=document, spec=spec))["name"])
        for format in ("dxf", "svg"):
            path = directory / ("planar." + format)
            await invoke("exchange_export", doc_name=document, obj_names=planar, path=str(path), options={"format": format})
            target = await create_document("MCP_PlanarImport")
            imported = await invoke("exchange_import", doc_name=target, path=str(path), format=format)
            shapes = [obj for obj in imported["objects"] if "curves" in obj]
            assert abs(sum(obj["length_mm"] for obj in shapes) - (145 + 12.5 * math.pi)) <= 0.001, imported
            circles = [curve for obj in shapes for curve in obj["curves"] if curve["type"] == "circle"]
            assert len(circles) == 2 and sum(curve["closed"] for curve in circles) == 1, imported
            assert all(abs(curve["radius_mm"] - 5) <= 0.001 for curve in circles), imported
            assert sum(obj["closed_wires"] for obj in shapes) == 2, imported
            minimum = [min(obj["bbox_mm"]["min"][axis] for obj in shapes) for axis in range(3)]
            maximum = [max(obj["bbox_mm"]["max"][axis] for obj in shapes) for axis in range(3)]
            assert all(abs(actual - expected) <= 0.001 for actual, expected in zip(minimum + maximum, [0, 0, 0, 65, 20, 0])), imported
            await invoke("undo", doc_name=target)
            assert not (await invoke("list_objects", doc_name=target))
            await invoke("redo", doc_name=target)
            await invoke("exchange_export", doc_name=document, obj_names=[source_name], path=str(directory / ("notplanar." + format)),
                         options={"format": format}, error="unsupported_geometry")
            assert not (directory / ("notplanar." + format)).exists()

        malformed = directory / "malformed.svg"
        malformed.write_text("<svg><broken>", encoding="utf-8")
        target = await create_document("MCP_BadImport")
        response = await session.call_tool("exchange_import", dict(doc_name=target, path=str(malformed), format="svg"))
        transcript.append({"tool": "exchange_import", "malformed": True, "result": response.structuredContent})
        assert response.structuredContent["status"] == "error", response
        assert not (await invoke("list_objects", doc_name=target))
        await invoke("exchange_export", doc_name=document, obj_names=[], path=str(directory / "empty.step"),
                     options={"format": "step", "step_schema": "AP214"}, schema_error=True)
        await invoke("exchange_export", doc_name=document, obj_names=[source_name], path=str(directory / "bad.step"),
                     options={"format": "step", "step_schema": "AP203"}, schema_error=True)
        await invoke("exchange_import", doc_name=document, path=str(directory / "missing.obj"), format="obj", error="invalid_arguments")
        assert not (await invoke("list_objects", doc_name=other))

        snapshot = await inspect(open_name)
        path = directory / "MCP_Stage11bc.FCStd"
        await invoke("save_document_safe", doc_name=document, path=str(path))
        await invoke("close_document_safe", doc_name=document)
        documents.remove(document)
        document = (await invoke("open_document", path=str(path)))["name"]
        documents.append(document)
        assert same(await inspect(open_name), snapshot)
        await invoke("set_placement", doc_name=document, obj_name=open_name, x=9, y=10, z=11)
        second = await inspect(open_name)
        assert second["bbox_mm"] == {"min": [9, 10, 11], "max": [49, 30, 21]}, second
        await invoke("mesh_repair", doc_name=document, obj_name=open_name, require_closed=True)
        assert same(await inspect(open_name), second)
        await invoke("save_document_safe", doc_name=document, path=str(path), overwrite=True)
        edited_path = directory / "edited-reopened.stl"
        await invoke("exchange_export", doc_name=document, obj_names=[open_name], path=str(edited_path), options={"format": "stl", "encoding": "binary"})
        target = await create_document("MCP_EditedReimport")
        edited_import = await invoke("exchange_import", doc_name=target, path=str(edited_path), format="stl")
        assert same(edited_import["objects"][0]["bbox_mm"], second["bbox_mm"]), edited_import
        report = {"calls": len(transcript), "step_schemas": ["AP214", "AP242"], "mesh_encodings": ["ascii", "binary", "obj"],
                  "planar_formats": ["dxf", "svg"], "mesh_undo_redo": True, "reopen_verified": True, "fcstd": str(path)}
        return report
    except BaseException as error:
        transcript.append({"failure": type(error).__name__, "message": str(error)})
        raise
    finally:
        for document_name in reversed(documents):
            try:
                await invoke("close_document_safe", doc_name=document_name, discard_changes=True)
            except BaseException as cleanup_error:
                transcript.append({"cleanup_failure": type(cleanup_error).__name__, "document": document_name, "message": str(cleanup_error)})
        (directory / "transcript.json").write_text(json.dumps(transcript, indent=2), encoding="utf-8")


async def check_stage11a(session, call, directory):
    transcript = []
    documents = []

    def same(actual, expected):
        if isinstance(actual, dict) and isinstance(expected, dict):
            return actual.keys() == expected.keys() and all(same(actual[key], expected[key]) for key in actual)
        if isinstance(actual, list) and isinstance(expected, list):
            return len(actual) == len(expected) and all(same(left, right) for left, right in zip(actual, expected))
        if type(actual) is float and type(expected) is float:
            return math.isclose(actual, expected, rel_tol=1e-6, abs_tol=1e-6)
        return actual == expected

    async def invoke(tool, error=None, schema_error=False, **arguments):
        response = await session.call_tool(tool, arguments)
        result = (response.structuredContent if response.structuredContent and "contract_version" in response.structuredContent
                  else (None if response.isError else json.loads(response.content[0].text)))
        transcript.append({"tool": tool, "arguments": arguments, "is_error": response.isError,
                           "result": result or [getattr(content, "text", "") for content in response.content]})
        if schema_error:
            assert response.isError, response
            return
        if error:
            assert result and result["status"] == "error" and result["error"]["code"] == error, result
            return result
        assert not response.isError, response
        if "contract_version" in result:
            assert result["status"] == "success", result
            return result["data"]
        return result

    async def inspect(name):
        return await invoke("draft_inspect", doc_name=document, obj_name=name)

    async def edit_cycle(tool, name, spec, expected):
        before = await inspect(name)
        changed = await invoke(tool, doc_name=document, obj_name=name, spec=spec)
        assert expected(changed) is not False, changed
        await invoke("undo", doc_name=document)
        assert same(await inspect(name), before), (name, before, await inspect(name))
        await invoke("redo", doc_name=document)
        assert same(await inspect(name), changed), name
        return changed

    assert not json.loads((await call("get_status")).content[0].text)["documents"], "Draft requires an empty isolated instance"
    try:
        document = (await invoke("create_document", name="MCP_Stage11a"))["name"]
        documents.append(document)
        other = (await invoke("create_document", name="MCP_Stage11a_Other"))["name"]
        documents.append(other)
        await invoke("activate_document", doc_name=other)
        other_before = await invoke("inspect_document", doc_name=other)
        fixtures = [
            ({"kind": "line", "points": [[0, 0, 0], [10, 0, 0]]}, 10, False),
            ({"kind": "wire", "points": [[0, 0, 0], [10, 0, 0], [10, 5, 0]]}, 15, False),
            ({"kind": "wire", "closed": True, "points": [[0, 0, 0], [10, 0, 0], [10, 5, 0]]}, 15 + math.sqrt(125), True),
            ({"kind": "rectangle", "length": 40, "width": 20}, 120, True),
            ({"kind": "circle", "radius": 5}, 10 * math.pi, True),
            ({"kind": "arc", "radius": 5, "start_angle": 0, "end_angle": 90}, 2.5 * math.pi, False),
            ({"kind": "text", "text": ["Draft text"], "size": 3.5}, None, None),
            ({"kind": "label", "text": ["Draft label"], "size": 3.5, "target_point": [0, 0, 0]}, None, None)]
        elements = []
        changed_specs = []
        for index, (spec, length, closed) in enumerate(fixtures):
            spec = dict(spec, position=[3, 4, 5])
            initial = await invoke("draft_create_element", doc_name=document, spec=spec, name="Fixture" + str(index))
            name = initial["name"]
            elements.append(name)
            assert initial["placement"]["position"] == [3, 4, 5], initial
            if length is not None:
                assert abs(initial["length_mm"] - length) <= 0.001 and initial["closed"] == closed, initial
            else:
                assert initial["text"] == spec["text"] and initial["size_mm"] == 3.5, initial
            gui_owned = {"active"}
            current_other = await invoke("inspect_document", doc_name=other)
            assert {k: v for k, v in current_other.items() if k not in gui_owned} == {
                k: v for k, v in other_before.items() if k not in gui_owned}
            edit = dict(spec, position=[6, 7, 8])
            if "radius" in edit:
                edit["radius"] = 6
            if "text" in edit:
                edit.update(text=["Edited annotation"], size=4)
            if edit["kind"] == "rectangle":
                edit["length"] = 45
            if "points" in edit:
                edit["points"] = [[0, 0, 0], [12, 0, 0]] + ([[12, 5, 0]] if edit["kind"] == "wire" else [])

            def expected(result):
                assert result["placement"]["position"] == [6, 7, 8], result
                if "text" in edit:
                    assert result["text"] == edit["text"] and result["size_mm"] == 4, result

            await edit_cycle("draft_edit_element", name, edit, expected)
            snapshot = await inspect(name)
            bad = dict(edit)
            if "radius" in bad:
                bad["radius"] = 0
            elif "points" in bad:
                bad["points"] = [[0, 0, 0], [0, 0, 0]]
                bad["closed"] = False if bad["kind"] == "wire" else None
                if bad["kind"] == "line":
                    del bad["closed"]
            elif "text" in bad:
                bad["text"] = [" "]
            else:
                bad["length"] = 0
            schema_error = "radius" in bad or "length" in bad
            failure = await invoke("draft_edit_element", doc_name=document, obj_name=name, spec=bad,
                                  schema_error=schema_error, error=None if schema_error else "invalid_arguments")
            if failure:
                assert failure["error"]["state"] == "rolled_back", failure
            assert same(await inspect(name), snapshot)
            changed_specs.append(edit)
        rectangle = elements[3]
        ortho_spec = {"kind": "ortho_array", "counts": [2, 3, 1], "spacing": [50, 30, 0]}
        ortho = await invoke("draft_create_array", doc_name=document, base_name=rectangle, spec=ortho_spec)
        assert ortho["instances"] == 6 and abs(ortho["length_mm"] - 780) < 0.001, ortho
        assert ortho["bbox_mm"] == {"min": [6, 7, 8], "max": [101, 87, 8]}, ortho
        polar_spec = {"kind": "polar_array", "count": 4, "angle": 360, "center": [0, 0, 8], "axis": [0, 0, 1]}
        polar = await invoke("draft_create_array", doc_name=document, base_name=elements[4], spec=polar_spec)
        assert polar["instances"] == 4 and abs(polar["length_mm"] - 48 * math.pi) < 0.001, polar
        for actual, expected_value in zip(polar["bbox_mm"]["min"] + polar["bbox_mm"]["max"], [-13, -13, 8, 13, 13, 8]):
            assert abs(actual - expected_value) <= 0.001, polar
        for array, spec in [(ortho, dict(ortho_spec, counts=[3, 3, 1])), (polar, dict(polar_spec, count=3, angle=180))]:
            changed = await edit_cycle("draft_edit_array", array["name"], spec,
                lambda result: result["instances"] == (9 if spec["kind"] == "ortho_array" else 3))
            invalid = dict(spec, spacing=[0, 0, 0]) if spec["kind"] == "ortho_array" else dict(spec, axis=[0, 0, 0])
            await invoke("draft_edit_array", doc_name=document, obj_name=array["name"], spec=invalid, error="invalid_arguments")
            assert same(await inspect(array["name"]), changed)
        await invoke("draft_create_array", doc_name=document, base_name=rectangle,
                     spec=dict(ortho_spec, counts=[0, 3, 1]), schema_error=True)
        await invoke("draft_create_array", doc_name=document, base_name="Missing", spec=ortho_spec, error="object_not_found")
        await invoke("draft_create_array", doc_name=document, base_name=elements[6], spec=ortho_spec, error="invalid_geometry")
        await invoke("draft_create_element", doc_name=document,
                     spec={"kind": "arc", "radius": 5, "start_angle": 90, "end_angle": 45}, error="invalid_arguments")
        await invoke("draft_create_element", doc_name=document,
                     spec={"kind": "circle", "radius": 5, "quaternion": [0, 0, 0, 2]}, error="invalid_arguments")
        await invoke("draft_inspect", doc_name="Missing", obj_name=rectangle, error="document_not_found")
        rotated = await invoke("draft_create_element", doc_name=document, spec={"kind": "line", "points": [[1, 0, 0], [11, 0, 0]],
            "position": [3, 4, 5], "quaternion": [0, 0, math.sqrt(0.5), math.sqrt(0.5)]})
        for actual, expected_value in zip(rotated["bbox_mm"]["min"] + rotated["bbox_mm"]["max"], [3, 5, 5, 3, 15, 5]):
            assert abs(actual - expected_value) < 0.001, rotated
        await invoke("delete_object", doc_name=document, obj_name=rotated["name"])
        await invoke("draft_inspect", doc_name=document, obj_name=rotated["name"], error="object_not_found")
        await invoke("undo", doc_name=document)
        assert same(await inspect(rotated["name"]), rotated)
        await invoke("redo", doc_name=document)
        await invoke("delete_object", doc_name=document, obj_name=rectangle, schema_error=True)
        assert "preview_delete/delete_objects" in transcript[-1]["result"][0], transcript[-1]
        source_before = await inspect(rectangle)
        before_array = await inspect(ortho["name"])
        changed_specs[3]["length"] = 50
        await invoke("draft_edit_element", doc_name=document, obj_name=rectangle, spec=changed_specs[3])
        assert abs((await inspect(ortho["name"]))["length_mm"] - 1260) < 0.001
        await invoke("undo", doc_name=document)
        assert same(await inspect(rectangle), source_before) and same(await inspect(ortho["name"]), before_array)
        await invoke("redo", doc_name=document)
        await invoke("set_properties", doc_name=document, obj_name=polar["name"], values={"Base": None})
        await invoke("draft_inspect", doc_name=document, obj_name=polar["name"], error="draft_reference_lost")
        await invoke("draft_edit_array", doc_name=document, obj_name=polar["name"], spec=polar_spec, error="draft_reference_lost")
        await invoke("undo", doc_name=document)
        await inspect(polar["name"])
        assert not (await invoke("inspect_document", doc_name=document))["pending_transaction"]
        saved = {name: await inspect(name) for name in elements + [ortho["name"], polar["name"]]}
        path = str(directory / "MCP_Stage11a.FCStd")
        await invoke("save_document_safe", doc_name=document, path=path)
        await invoke("close_document_safe", doc_name=document)
        documents.remove(document)
        document = (await invoke("open_document", path=path))["name"]
        documents.append(document)
        for name, snapshot in saved.items():
            assert same(await inspect(name), snapshot), (name, snapshot, await inspect(name))
        for name, spec in zip(elements, changed_specs):
            spec = dict(spec, position=[9, 10, 11])
            if "text" in spec:
                spec["text"] = ["After reopen"]
            await invoke("draft_edit_element", doc_name=document, obj_name=name, spec=spec)
            assert (await inspect(name))["placement"]["position"] == [9, 10, 11]
        await invoke("draft_edit_array", doc_name=document, obj_name=ortho["name"], spec=ortho_spec)
        await invoke("draft_edit_array", doc_name=document, obj_name=polar["name"], spec=polar_spec)
        assert (await inspect(ortho["name"]))["instances"] == 6
        assert (await inspect(polar["name"]))["instances"] == 4
        await invoke("save_document_safe", doc_name=document, overwrite=True)
        assert (await invoke("inspect_document", doc_name=other))["objects"] == other_before["objects"]
        return {"scope": "11a Draft only; Mesh and X-format gates remain open", "calls": len(transcript),
                "fcstd": path, "elements": len(elements), "array_instances": [6, 4], "reopen_verified": True}
    finally:
        original_error = sys.exc_info()[1]
        cleanup_errors = []
        for document in reversed(documents):
            try:
                await invoke("close_document_safe", doc_name=document, discard_changes=True)
            except Exception as error:
                cleanup_errors.append({"document": document, "error": str(error)})
        (directory / "mcp-transcript.json").write_text(json.dumps(transcript, indent=2), encoding="utf-8")
        if original_error or cleanup_errors:
            (directory / "failure.json").write_text(json.dumps({"error": str(original_error), "cleanup_errors": cleanup_errors}, indent=2), encoding="utf-8")
            print("11a failure artifacts: " + str(directory), file=sys.stderr)
        if cleanup_errors and original_error is None:
            raise AssertionError(cleanup_errors)


async def check_stage10b(session, call, directory):
    transcript = []
    documents = []

    async def invoke(tool, error=None, **arguments):
        response = await session.call_tool(tool, arguments)
        result = (response.structuredContent if response.structuredContent and "contract_version" in response.structuredContent
                  else (None if response.isError else json.loads(response.content[0].text)))
        transcript.append({"tool": tool, "arguments": arguments, "is_error": response.isError,
                           "result": result or [getattr(content, "text", "") for content in response.content]})
        if error:
            assert result and result["status"] == "error" and result["error"]["code"] == error, result
            return result
        assert not response.isError, response
        if "contract_version" in result:
            assert result["status"] == "success", result
            return result["data"]
        return result

    async def geometry(view):
        return await invoke("techdraw_list_geometry", doc_name=document, page_name=page, view_name=view)

    async def dimension(view, kind, select, name, position, expected):
        queried = await geometry(view)
        selected = select(queried)
        result = await invoke("techdraw_create_dimension", doc_name=document, page_name=page,
                             kind=kind, selections=selected, x=position[0], y=position[1], name=name)
        assert result["model_bound"] and abs(result["value"] - expected) < 0.001, result
        return result

    async def verify(length, thickness):
        result = await invoke("techdraw_update_page", doc_name=document, page_name=page)
        assert result["paper_mm"] == [297, 210] and result["scale"] == 1 and len(result["views"]) == 5, result
        expected = dict(FlangeDiameter=60, FlangeThickness=thickness, ShaftDiameter=20,
                        BoreDiameter=8, OverallLength=length, PitchDiameter=44)
        actual = {item["name"]: item for item in result["dimensions"]}
        for name, value in expected.items():
            assert actual[name]["model_bound"] and actual[name]["references_2d"], actual[name]
            assert abs(actual[name]["value"] - value) < 0.001, (name, actual[name], value)
        measurement = await invoke("measure", doc_name=document, obj_name=body)
        assert abs(measurement["bounding_box"]["max"]["y"] - length) < 0.001, measurement
        return result

    assert not json.loads((await call("get_status")).content[0].text)["documents"], "A5 needs an empty isolated instance"
    try:
        document = (await invoke("create_document", name="MCP_Stage10b"))["name"]
        documents.append(document)
        sheet = (await invoke("create_spreadsheet", doc_name=document, name="Parameters"))["name"]
        await invoke("set_spreadsheet_cells", doc_name=document, obj_name=sheet,
                     cells={"A1": "40 mm", "A2": "8 mm", "A3": "22 mm"})
        for cell, alias in (("A1", "ShaftLength"), ("A2", "FlangeThickness"), ("A3", "PitchRadius")):
            await invoke("set_spreadsheet_alias", doc_name=document, obj_name=sheet, cell=cell, alias=alias)
        body = (await invoke("partdesign_body", doc_name=document, name="FlangeBody"))["name"]
        profile = (await invoke("create_sketch", doc_name=document, name="RevolutionProfile", body_name=body))["name"]
        await invoke("sketch_add_polygon", doc_name=document, sketch_name=profile,
                     points=[[0, 0], [30, 0], [30, 8], [10, 8], [10, 48], [0, 48]], close=True)
        for index in (0, 2, 4):
            await invoke("sketch_constrain_horizontal", doc_name=document, sketch_name=profile, geo_idx=index)
        for index in (1, 3, 5):
            await invoke("sketch_constrain_vertical", doc_name=document, sketch_name=profile, geo_idx=index)
        await invoke("sketch_constrain_lock", doc_name=document, sketch_name=profile, geo_idx=0, point_idx=1)
        for index, value in ((0, 30), (1, 8), (2, 20), (3, 40)):
            constraint = (await invoke("sketch_constrain_length", doc_name=document, sketch_name=profile,
                                      geo_idx=index, value=value))["constraint_index"]
            if index in (1, 3):
                await invoke("set_expression", doc_name=document, obj_name=profile,
                    property_name=f"Constraints[{constraint}]",
                    expression="Parameters." + ("FlangeThickness" if index == 1 else "ShaftLength"))
        assert (await invoke("sketch_info", doc_name=document, sketch_name=profile))["fully_constrained"]
        await invoke("partdesign_revolution", doc_name=document, sketch_name=profile, angle=360, axis="V", name="Revolution")
        for name, center, radius in (("AxialHole", 0, 4), ("FlangeHole", 22, 3)):
            sketch = (await invoke("create_sketch", doc_name=document, name=name + "Profile", body_name=body,
                                   plane="XZ", offset=48))["name"]
            await invoke("sketch_add_circle", doc_name=document, sketch_name=sketch, cx=center, cy=0, radius=radius)
            await invoke("sketch_constrain_lock", doc_name=document, sketch_name=sketch, geo_idx=0, point_idx=3)
            await invoke("sketch_constrain_radius", doc_name=document, sketch_name=sketch, geo_idx=0, radius=radius)
            await invoke("set_expression", doc_name=document, obj_name=sketch, property_name="Placement.Base.y",
                         expression="Parameters.FlangeThickness+Parameters.ShaftLength")
            hole = await invoke("partdesign_hole", doc_name=document, sketch_name=sketch,
                                diameter=radius * 2, depth=48, through_all=True, name=name)
        pattern = (await invoke("partdesign_polar_pattern", doc_name=document, feature_name=hole["name"],
                                axis="Y", angle=360, occurrences=4, name="HolePattern"))["name"]
        measured = await invoke("measure", doc_name=document, obj_name=body)
        assert abs(measured["volume"] - 10144 * math.pi) < 1e-4, measured
        page_data = await invoke("techdraw_create_page", doc_name=document, template="ISO/A4_Landscape_TD.svg")
        page = page_data["name"]
        title_key = next(key for key in page_data["editable_texts"] if "title" in key.lower())
        fields = {title_key: "A2 Flange - A5", "FC-SC": "1:1", "Designed_by_Name": "MCP verification",
              "Drawing_number": "A2-A5-001", "FC-SH": "1 / 1", "Subtitle": "Flange", "Weight": "-"}
        await invoke("techdraw_set_layout", doc_name=document, page_name=page, texts=fields)
        group = await invoke("techdraw_create_projection_group", doc_name=document, page_name=page,
                             source_names=[body], direction=[0, 0, 1], x=115, y=145)
        front = group["views"][0]["name"]
        circular = next(item["name"] for item in group["views"] if abs(item["direction"][1]) > 0.99)
        side = next(item["name"] for item in group["views"] if abs(item["direction"][0]) > 0.99)
        await invoke("techdraw_set_layout", doc_name=document, page_name=page, view_name=side, x=45, y=145)
        await invoke("techdraw_set_layout", doc_name=document, page_name=page, view_name=circular, x=115, y=65)
        await invoke("techdraw_create_section", doc_name=document, page_name=page, base_view=circular,
                     origin=[0, 0, 0], normal=[0, 0, -1], x=200, y=140, name="AxialSection")
        circles = (await geometry(circular))["edges"]
        flange_hole = next(edge for edge in circles if abs(edge.get("radius_mm", 0) - 3) < 0.001)
        await invoke("techdraw_create_detail", doc_name=document, page_name=page, base_view=circular,
                     anchor=flange_hole["center_mm"][:2], radius=7, x=205, y=75, scale=2, name="HoleDetail")
        for name, radius, position in (("FlangeDiameter", 30, [145, 100]), ("ShaftDiameter", 10, [100, 35]),
                                       ("BoreDiameter", 4, [70, 35])):
            await dimension(circular, "diameter", lambda data, radius=radius: [next(edge["selection"]
                for edge in data["edges"] if abs(edge.get("radius_mm", 0) - radius) < 0.001)], name, position, radius * 2)
        await dimension(front, "length", lambda data: [next(edge["selection"] for edge in data["edges"]
            if abs(edge["length_mm"] - 8) < 0.001)], "FlangeThickness", [150, 125], 8)
        def endpoints(data):
            vertices = data["vertices"]
            return [min(vertices, key=lambda item: item["point_mm"][1])["selection"],
                    max(vertices, key=lambda item: item["point_mm"][1])["selection"]]
        await dimension(front, "distance_y", endpoints, "OverallLength", [165, 150], 48)
        def opposite_holes(data):
            edges = [edge for edge in data["edges"] if abs(edge.get("radius_mm", 0) - 3) < 0.001]
            centers = [min(edges, key=lambda item: item["center_mm"][0])["center_mm"],
                       max(edges, key=lambda item: item["center_mm"][0])["center_mm"]]
            selected = []
            for center in centers:
                vertex = min(data["vertices"], key=lambda item: math.dist(item["point_mm"], center))
                assert math.dist(vertex["point_mm"], center) < 0.001, vertex
                selected.append(vertex["selection"])
            return selected
        pitch = await dimension(circular, "distance_x", opposite_holes, "PitchDiameter", [115, 105], 44)
        await invoke("set_properties", doc_name=document, obj_name=pitch["name"], values={"FormatSpec": "PCD \u2300%.2f"})
        annotation = await invoke("techdraw_create_annotation", doc_name=document, page_name=page,
                     text=["4 holes diameter 6", "Detail 2:1", "Section A-A"], x=205, y=100, size=3)
        leader = await invoke("techdraw_create_leader", doc_name=document, page_name=page, view_name=circular,
                     points=[flange_hole["center_mm"][:2], [45, 25]])
        await invoke("set_properties", doc_name=document, obj_name=annotation["name"],
                 values={"Text": ["4 holes diameter 6", "Detail 2:1", "Section A-A"], "TextSize": {"value": 3, "unit": "mm"}})
        await invoke("set_properties", doc_name=document, obj_name=leader["name"],
                 values={"WayPoints": [[*flange_hole["center_mm"][:2], 0], [40, 20, 0]]})
        initial = await verify(48, 8)
        stale = (await geometry(front))["edges"][0]["selection"]
        await invoke("techdraw_set_layout", doc_name=document, page_name=page, view_name="HoleDetail", x=210)
        before = await invoke("inspect_document", doc_name=document)
        await invoke("techdraw_create_dimension", error="stale_selection", doc_name=document, page_name=page,
                     kind="length", selections=[stale], x=100, y=100)
        await invoke("techdraw_create_section", error="invalid_arguments", doc_name=document, page_name=page,
                     base_view=circular, origin=[0, 0, 0], normal=[0, 1, 0], x=200, y=130)
        await invoke("techdraw_create_page", error="template_not_found", doc_name=document, template="Missing.svg")
        after = await invoke("inspect_document", doc_name=document)
        assert before["objects"] == after["objects"] and not after["pending_transaction"]
        await invoke("set_spreadsheet_cells", doc_name=document, obj_name=sheet, cells={"A1": "50 mm"})
        edited = await verify(58, 8)
        await invoke("undo", doc_name=document)
        await verify(48, 8)
        await invoke("redo", doc_name=document)
        await verify(58, 8)
        path = str(directory / "MCP_Stage10b.FCStd")
        await invoke("save_document_safe", doc_name=document, path=path)
        await invoke("close_document_safe", doc_name=document)
        documents.remove(document)
        document = (await invoke("open_document", path=path))["name"]
        documents.append(document)
        await verify(58, 8)
        await invoke("set_spreadsheet_cells", doc_name=document, obj_name=sheet, cells={"A2": "9 mm"})
        final = await verify(59, 9)
        await invoke("save_document_safe", doc_name=document, overwrite=True)
        for format in ("pdf", "svg"):
            output = str(directory / ("drawing." + format))
            exported = await invoke("techdraw_export_page", doc_name=document, page_name=page, path=output, format=format)
            assert exported["bytes"] > 500
            digest = hashlib.sha256(Path(output).read_bytes()).hexdigest()
            await invoke("techdraw_export_page", error="file_exists", doc_name=document, page_name=page, path=output, format=format)
            assert hashlib.sha256(Path(output).read_bytes()).hexdigest() == digest
        await invoke("set_properties", doc_name=document, obj_name=front, values={"Source": []})
        await invoke("techdraw_inspect_page", error="drawing_reference_lost", doc_name=document, page_name=page)
        await invoke("undo", doc_name=document)
        await verify(59, 9)
        await invoke("set_properties", doc_name=document, obj_name=pattern, values={"Occurrences": 3})
        await invoke("techdraw_inspect_page", error="drawing_reference_stale", doc_name=document, page_name=page)
        await invoke("undo", doc_name=document)
        await verify(59, 9)
        rendered = verify_stage10b_exports(directory, final)
        fixture = (await invoke("create_document", name="MCP_Stage10b_Dimensions"))["name"]
        documents.append(fixture)
        cylinder = (await invoke("part_cylinder", doc_name=fixture, radius=5, height=20, name="Cylinder"))["name"]
        fixture_page = (await invoke("techdraw_create_page", doc_name=fixture, template="ISO/A4_Landscape_TD.svg"))["name"]
        fixture_top = (await invoke("techdraw_create_view", doc_name=fixture, page_name=fixture_page,
                 source_names=[cylinder], direction=[0, 0, 1], x=80, y=130))["name"]
        fixture_side = (await invoke("techdraw_create_view", doc_name=fixture, page_name=fixture_page,
                 source_names=[cylinder], direction=[0, -1, 0], x=160, y=130))["name"]
        geometry_top = await invoke("techdraw_list_geometry", doc_name=fixture, page_name=fixture_page, view_name=fixture_top)
        circle = next(edge["selection"] for edge in geometry_top["edges"] if "radius_mm" in edge)
        radius = await invoke("techdraw_create_dimension", doc_name=fixture, page_name=fixture_page,
                      kind="radius", selections=[circle], x=100, y=150)
        assert abs(radius["value"] - 5) < 0.001 and radius["model_bound"]
        geometry_side = await invoke("techdraw_list_geometry", doc_name=fixture, page_name=fixture_page, view_name=fixture_side)
        lines = [next(edge["selection"] for edge in geometry_side["edges"] if abs(edge["length_mm"] - length) < 0.001)
             for length in (20, 10)]
        angle = await invoke("techdraw_create_dimension", doc_name=fixture, page_name=fixture_page,
                     kind="angle", selections=lines, x=185, y=145)
        assert abs(angle["value"] - 90) < 0.001 and angle["model_bound"]
        geometry_side = await invoke("techdraw_list_geometry", doc_name=fixture, page_name=fixture_page, view_name=fixture_side)
        await invoke("techdraw_create_dimension", error="invalid_arguments", doc_name=fixture, page_name=fixture_page,
                 kind="radius", selections=[geometry_side["edges"][0]["selection"]], x=100, y=100)
        for values in ({"Arbitrary": True}, {"Type": "Diameter"}, {"MeasureType": "True"}):
            await invoke("set_properties", doc_name=fixture, obj_name=radius["name"], values=values)
            await invoke("techdraw_inspect_page", error="drawing_reference_lost", doc_name=fixture, page_name=fixture_page)
            await invoke("undo", doc_name=fixture)
        fixture_restored = await invoke("techdraw_inspect_page", doc_name=fixture, page_name=fixture_page)
        assert len(fixture_restored["dimensions"]) == 2
        return {"calls": len(transcript), "initial": initial, "edited": edited, "final": final, "rendered": rendered,
            "dimension_fixture": {"radius": radius, "angle": angle},
                "fcstd": path, "directory": str(directory)}
    finally:
        original_error = sys.exc_info()[1]
        cleanup_errors = []
        for document in reversed(documents):
            try:
                await invoke("close_document_safe", doc_name=document, discard_changes=True)
            except Exception as error:
                cleanup_errors.append(str(error))
        (directory / "mcp-transcript.json").write_text(json.dumps(transcript, indent=2), encoding="utf-8")
        if original_error or cleanup_errors:
            (directory / "failure.json").write_text(json.dumps({"error": str(original_error), "cleanup_errors": cleanup_errors}, indent=2), encoding="utf-8")
            print("A5 failure artifacts: " + str(directory), file=sys.stderr)
        if cleanup_errors and original_error is None:
            raise AssertionError(cleanup_errors)


async def check_stage10a(session, call, directory, verify_undo=True):
    import xml.etree.ElementTree as ET

    transcript = []
    documents = []

    async def invoke(tool, error=None, **arguments):
        response = await session.call_tool(tool, arguments)
        result = (response.structuredContent if response.structuredContent and "contract_version" in response.structuredContent
                  else (None if response.isError else json.loads(response.content[0].text)))
        transcript.append({"tool": tool, "arguments": arguments, "is_error": response.isError,
                           "result": result or [getattr(content, "text", "") for content in response.content]})
        if error:
            assert result and result["status"] == "error" and result["error"]["code"] == error, result
            return result
        assert not response.isError, response
        if "contract_version" in result:
            assert result["status"] == "success", result
            return result["data"]
        return result

    async def dimensions(document, page, expected):
        result = await invoke("techdraw_update_page", doc_name=document, page_name=page)
        assert result["current"] and result["paper_mm"] == [297, 210] and len(result["views"]) == 3, result
        top = next(view for view in result["views"] if view["name"] == "Top")
        assert all(abs(actual - value) <= 0.001 for actual, value in zip(top["projected_bbox_mm"], expected)), top
        return result

    assert not json.loads((await call("get_status")).content[0].text)["documents"], "10a needs an empty isolated instance"
    try:
        document = (await invoke("create_document", name="MCP_Stage10a"))["name"]
        documents.append(document)
        source = (await invoke("part_box", doc_name=document, name="Source", length=60, width=40, height=20))["name"]
        templates = await invoke("techdraw_list_templates")
        assert "ISO/A4_Landscape_TD.svg" in templates["templates"]
        page_data = await invoke("techdraw_create_page", doc_name=document, template="ISO/A4_Landscape_TD.svg")
        page = page_data["name"]
        for name, direction, x, y in [("Top", [0, 0, 1], 80, 140), ("Front", [0, -1, 0], 80, 70),
                                       ("Side", [1, 0, 0], 190, 140)]:
            await invoke("techdraw_create_view", doc_name=document, page_name=page, source_names=[source],
                         direction=direction, x=x, y=y, name=name)
        texts = page_data["editable_texts"]
        title_key = next((key for key in texts if "title" in key.lower()), None)
        assert title_key, texts
        await invoke("techdraw_set_layout", doc_name=document, page_name=page, texts={title_key: "Stage 10a drawing"})
        initial = await dimensions(document, page, [60, 40])
        before = await invoke("inspect_document", doc_name=document)
        await invoke("techdraw_create_page", error="template_not_found", doc_name=document, template="Missing.svg")
        await invoke("techdraw_create_view", error="invalid_arguments", doc_name=document, page_name=page,
                     source_names=[source], direction=[0, 0, 0], x=10, y=10)
        await invoke("techdraw_set_layout", error="invalid_arguments", doc_name=document, page_name=page,
                     view_name="Top", x=400)
        await invoke("techdraw_set_layout", error="invalid_arguments", doc_name=document, page_name=page,
                     texts={"missing-key": "Not a field"})
        after = await invoke("inspect_document", doc_name=document)
        assert before["objects"] == after["objects"] and not after["pending_transaction"], (before, after)
        original_svg = str(directory / "before.svg")
        await invoke("techdraw_export_page", doc_name=document, page_name=page, path=original_svg, format="svg")
        await invoke("set_properties", doc_name=document, obj_name=source, values={"Length": {"value": 70, "unit": "mm"}})
        await dimensions(document, page, [70, 40])
        if verify_undo:
            await invoke("undo", doc_name=document)
            await dimensions(document, page, [60, 40])
            await invoke("redo", doc_name=document)
            await dimensions(document, page, [70, 40])
        edited_svg = str(directory / "edited.svg")
        await invoke("techdraw_export_page", doc_name=document, page_name=page, path=edited_svg, format="svg")
        assert Path(original_svg).read_bytes() != Path(edited_svg).read_bytes()
        await invoke("techdraw_set_layout", doc_name=document, page_name=page, view_name="Side", x=200)
        if verify_undo:
            await invoke("undo", doc_name=document)
            layout = await invoke("techdraw_update_page", doc_name=document, page_name=page)
            assert next(view for view in layout["views"] if view["name"] == "Side")["position_mm"][0] == 190
            await invoke("redo", doc_name=document)
        await invoke("techdraw_update_page", doc_name=document, page_name=page)
        path = str(directory / "MCP_Stage10a.FCStd")
        await invoke("save_document_safe", doc_name=document, path=path)
        await invoke("close_document_safe", doc_name=document)
        documents.remove(document)
        document = (await invoke("open_document", path=path))["name"]
        documents.append(document)
        reopened = await dimensions(document, page, [70, 40])
        assert reopened["editable_texts"][title_key] == "Stage 10a drawing"
        assert all(view["sources"][0]["object"] == source for view in reopened["views"])
        await invoke("set_properties", doc_name=document, obj_name=source, values={"Width": {"value": 45, "unit": "mm"}})
        final = await dimensions(document, page, [70, 45])
        await invoke("save_document_safe", doc_name=document, overwrite=True)
        for format in ("pdf", "svg"):
            output = str(directory / ("drawing." + format))
            exported = await invoke("techdraw_export_page", doc_name=document, page_name=page, path=output, format=format)
            assert exported["bytes"] > 500 and exported["scale"] == 1
            digest = hashlib.sha256(Path(output).read_bytes()).hexdigest()
            await invoke("techdraw_export_page", error="file_exists", doc_name=document, page_name=page,
                         path=output, format=format)
            assert hashlib.sha256(Path(output).read_bytes()).hexdigest() == digest
            await invoke("techdraw_export_page", doc_name=document, page_name=page, path=output, format=format, overwrite=True)
            if format == "svg":
                assert ET.parse(output).getroot().tag == "{http://www.w3.org/2000/svg}svg"
        if verify_undo:
            await invoke("set_properties", doc_name=document, obj_name="Top", values={"Source": []})
            await invoke("techdraw_inspect_page", error="drawing_reference_lost", doc_name=document, page_name=page)
            await invoke("techdraw_export_page", error="drawing_reference_lost", doc_name=document, page_name=page,
                 path=str(directory / "invalid.svg"), format="svg")
            assert not (directory / "invalid.svg").exists()
            await invoke("undo", doc_name=document)
            await dimensions(document, page, [70, 45])
        return {"calls": len(transcript), "scope": "10a only; not A5", "undo_verified": verify_undo,
            "initial": initial, "final": final,
                "fcstd": path, "directory": str(directory)}
    finally:
        original_error = sys.exc_info()[1]
        cleanup_errors = []
        for document in reversed(documents):
            try:
                await invoke("close_document_safe", doc_name=document, discard_changes=True)
            except Exception as error:
                cleanup_errors.append({"document": document, "error": str(error)})
        (directory / "mcp-transcript.json").write_text(json.dumps(transcript, indent=2), encoding="utf-8")
        if original_error or cleanup_errors:
            (directory / "failure.json").write_text(json.dumps({"success": False,
                "scope": "10a full" if verify_undo else "10a basic; Undo omitted",
                "error": str(original_error), "cleanup_errors": cleanup_errors,
                "remaining_test_documents": documents, "directory": str(directory)}, indent=2), encoding="utf-8")
            print("10a failure artifacts: " + str(directory), file=sys.stderr)
        if cleanup_errors and original_error is None:
            raise AssertionError(cleanup_errors)


def check_stage10a_exports(directory, views):
    import pymupdf

    result = {"renderer": pymupdf.VersionBind, "formats": {}}
    for format in ("pdf", "svg"):
        with pymupdf.open(directory / ("drawing." + format)) as exported:
            assert len(exported) == 1, "Drawing export must have one page"
            page = exported[0]
            paper_mm = [page.rect.width * 25.4 / 72, page.rect.height * 25.4 / 72]
            assert all(abs(actual - expected) < 0.15 for actual, expected in zip(paper_mm, [297, 210]))
            if format == "svg":
                assert "Stage 10a drawing" in page.get_text()
            pixmap = page.get_pixmap(matrix=pymupdf.Matrix(1.5, 1.5), alpha=False)
            assert pixmap.n == 3
            pixels = pixmap.samples
            px_per_mm = [pixmap.width / paper_mm[0], pixmap.height / paper_mm[1]]
            measured = []
            for view in views:
                assert view["rotation_deg"] == 0, "This reference workflow uses unrotated views"
                width, height = [value * view["scale"] for value in view["projected_bbox_mm"]]
                center = [view["position_mm"][0], paper_mm[1] - view["position_mm"][1]]
                bounds = [(max(0, int((coordinate - size / 2 - 2) * factor)),
                           min(limit, int((coordinate + size / 2 + 2) * factor) + 1))
                          for coordinate, size, factor, limit in
                          zip(center, [width, height], px_per_mm, [pixmap.width, pixmap.height])]
                dark = []
                for row in range(*bounds[1]):
                    for column in range(*bounds[0]):
                        offset = row * pixmap.stride + column * pixmap.n
                        if max(pixels[offset:offset + 3]) < 128:
                            dark.append((column, row))
                assert dark, "Missing rendered view: " + view["name"]
                low = [min(point[axis] for point in dark) for axis in (0, 1)]
                high = [max(point[axis] for point in dark) for axis in (0, 1)]
                size_mm = [(end - start) / factor for start, end, factor in zip(low, high, px_per_mm)]
                center_mm = [(end + start) / (2 * factor) for start, end, factor in zip(low, high, px_per_mm)]
                assert all(abs(actual - expected) < 0.8 for actual, expected in zip(size_mm, [width, height])), view
                assert all(abs(actual - expected) < 0.8 for actual, expected in zip(center_mm, center)), view
                measured.append({"name": view["name"], "expected_size_mm": [width, height],
                                 "rendered_size_mm": size_mm, "rendered_center_mm": center_mm})
            image = directory / ("drawing-" + format + ".png")
            pixmap.save(str(image))
            result["formats"][format] = {"pages": len(exported), "paper_mm": paper_mm,
                                          "views": measured, "image": str(image)}
    return result


async def check_stage12b_sketcher(session, call, directory):
    """V audit of every Sketcher geometry, constraint and drawing variant through MCP only."""
    import re

    transcript = []
    documents = []
    state = {}

    def decode(response):
        if response.structuredContent and "contract_version" in response.structuredContent:
            return response.structuredContent
        return json.loads(response.content[0].text)

    async def invoke(tool, **arguments):
        result = decode(await call(tool, **arguments))
        transcript.append({"tool": tool, "arguments": arguments, "result": result})
        if isinstance(result, dict) and "contract_version" in result:
            assert result["status"] == "success", result
            return result["data"]
        return result

    def same(actual, expected, path="$"):
        if isinstance(expected, float) or isinstance(actual, float):
            assert abs(actual - expected) <= 1e-7, (path, actual, expected)
        elif isinstance(expected, dict):
            assert isinstance(actual, dict) and set(actual) == set(expected), (path, actual, expected)
            for key in expected:
                same(actual[key], expected[key], f"{path}.{key}")
        elif isinstance(expected, list):
            assert isinstance(actual, list) and len(actual) == len(expected), (path, actual, expected)
            for index, (left, right) in enumerate(zip(actual, expected)):
                same(left, right, f"{path}[{index}]")
        else:
            assert actual == expected, (path, actual, expected)

    def near(actual, expected, tolerance=1e-6):
        def flat(values):
            return [item for value in values for item in (flat(value) if isinstance(value, (list, tuple)) else [value])]
        actual, expected = flat(actual), flat(expected)
        assert len(actual) == len(expected) and all(abs(a - e) <= tolerance for a, e in zip(actual, expected)), (
            actual, expected)

    def xy(geometry, key):
        return geometry[key]["x"], geometry[key]["y"]

    def vector(geometry):
        (x1, y1), (x2, y2) = xy(geometry, "start"), xy(geometry, "end")
        return x2 - x1, y2 - y1

    def line_distance(point, geometry):
        (x1, y1), (dx, dy) = xy(geometry, "start"), vector(geometry)
        return abs(dx * (point[1] - y1) - dy * (point[0] - x1)) / math.hypot(dx, dy)

    async def info(sketch):
        return await invoke("sketch_info", doc_name=state["doc"], sketch_name=sketch)

    async def names():
        return sorted(item["name"] for item in await invoke("list_objects", doc_name=state["doc"]))

    async def reject(tool, sketch, expected, **arguments):
        objects = await names()
        before = await info(sketch) if sketch else None
        response = await session.call_tool(tool, {"doc_name": state["doc"], **arguments})
        text = " ".join(getattr(content, "text", "") for content in response.content)
        transcript.append({"tool": tool, "arguments": arguments, "is_error": response.isError, "result": text})
        assert response.isError, (tool, arguments, text)
        assert expected in text, (tool, expected, text)
        assert await names() == objects, (tool, arguments)
        if sketch:
            same(await info(sketch), before)
        return text

    async def mutate(tool, sketch, **arguments):
        before = await info(sketch)
        result = await invoke(tool, doc_name=state["doc"], sketch_name=sketch, **arguments)
        after = await info(sketch)
        await invoke("undo", doc_name=state["doc"])
        same(await info(sketch), before)
        await invoke("redo", doc_name=state["doc"])
        same(await info(sketch), after)
        return result, before, after

    async def sketch(name, *geometry, **options):
        await invoke("create_sketch", doc_name=state["doc"], name=name, **options)
        indices = []
        for tool, arguments in geometry:
            result = await invoke(tool, doc_name=state["doc"], sketch_name=name, **arguments)
            indices.append(result.get("geometry_index", result.get("geometry_indices")))
        return indices

    async def constrain(tool, name, dof_delta, **arguments):
        result, before, after = await mutate(tool, name, **arguments)
        assert before["degrees_of_freedom"] - after["degrees_of_freedom"] == dof_delta, (tool, before, after)
        assert not after["conflicting_constraint_indices"] and not after["redundant_constraint_indices"], after
        return result, after["geometries"]

    async def vertices(obj_name):
        items = (await invoke("list_subelements", doc_name=state["doc"], obj_name=obj_name, kind="vertex"))["items"]
        return sorted((tuple(item["position"]) for item in items), key=lambda point: tuple(round(v, 6) for v in point))

    async def select(obj_name, kind, **filters):
        return (await invoke("select_subelement", doc_name=state["doc"], obj_name=obj_name, kind=kind,
                             filters=filters))["selection"]

    line = "sketch_add_line"
    assert not json.loads((await call("get_status")).content[0].text)["documents"], "Stage 12b needs an empty instance"
    try:
        state["doc"] = doc = (await invoke("create_document", name="MCP_Stage12b_Sketcher"))["name"]
        documents.append(doc)

        # I05 planes, offsets, documented sketch-local orientation, rejection and undo/redo of creation.
        for plane, offset, expected in [("XY", 3, [(1, 2, 3), (11, 2, 3)]), ("XZ", 5, [(1, 5, -2), (11, 5, -2)]),
                                        ("YZ", 7, [(7, 2, -11), (7, 2, -1)])]:
            name = f"Plane{plane}"
            before = await names()
            assert (await invoke("create_sketch", doc_name=doc, name=name, plane=plane, offset=offset))["plane"] == plane
            after = await names()
            assert set(after) - set(before) == {name}
            await invoke("undo", doc_name=doc)
            assert await names() == before
            await invoke("redo", doc_name=doc)
            assert await names() == after
            await invoke(line, doc_name=doc, sketch_name=name, x1=1, y1=2, x2=11, y2=2)
            for actual, wanted in zip(await vertices(name), sorted(expected)):
                near(actual, wanted, 1e-6)
        await reject("create_sketch", None, "Unknown plane", name="BadPlane", plane="AB")
        await reject("create_sketch", None, "Missing", name="BadBody", body_name="Missing")

        # I06-I09 geometry creation: oracle, undo/redo and invalid boundaries.
        await invoke("create_sketch", doc_name=doc, name="Geometry")
        creations = [
            (line, dict(x1=0, y1=0, x2=10, y2=0)),
            (line, dict(x1=0, y1=5, x2=10, y2=5, construction=True)),
            ("sketch_add_rectangle", dict(x1=-5, y1=-3, x2=5, y2=3)),
            ("sketch_add_circle", dict(cx=20, cy=0, radius=3)),
            ("sketch_add_arc", dict(cx=0, cy=20, radius=2, start_angle=0.5, end_angle=2.0)),
            ("sketch_add_ellipse", dict(cx=40, cy=0, major_radius=5, minor_radius=2, angle=0.5)),
            ("sketch_add_bspline", dict(points=[[0, 30], [5, 35], [10, 30]])),
            ("sketch_add_point", dict(x=5, y=7)),
            ("sketch_add_polygon", dict(points=[[0, 40], [10, 40], [10, 50]], close=False)),
            ("sketch_add_polygon", dict(points=[[20, 40], [30, 40], [25, 48]], close=True)),
            ("sketch_add_slot", dict(x1=0, y1=60, x2=20, y2=60, radius=3)),
        ]
        created = {}
        for tool, arguments in creations:
            result, before, after = await mutate(tool, "Geometry", **arguments)
            added = after["geometries"][before["geometry_count"]:]
            created[(tool, arguments.get("close"), arguments.get("construction"))] = (result, added, before, after)
        geometry = {key: value[1] for key, value in created.items()}
        first, construction = geometry[(line, None, None)][0], geometry[(line, None, True)][0]
        assert first["type"] == "LineSegment" and not first["construction"] and construction["construction"]
        near(xy(first, "start") + xy(first, "end"), (0, 0, 10, 0))
        rectangle = created[("sketch_add_rectangle", None, None)]
        assert len(rectangle[1]) == 4 and rectangle[3]["constraint_count"] - rectangle[2]["constraint_count"] == 8
        assert rectangle[3]["degrees_of_freedom"] - rectangle[2]["degrees_of_freedom"] == 4
        near(sorted(xy(item, "start") for item in rectangle[1]), sorted([(-5, -3), (5, -3), (5, 3), (-5, 3)]))
        circle = geometry[("sketch_add_circle", None, None)][0]
        assert circle["type"] == "Circle" and abs(circle["radius"] - 3) < 1e-6
        near(xy(circle, "center"), (20, 0))
        arc = geometry[("sketch_add_arc", None, None)][0]
        near(arc["parameter_range"], (0.5, 2.0))
        near(xy(arc, "start"), (2 * math.cos(0.5), 20 + 2 * math.sin(0.5)))
        near(xy(arc, "end"), (2 * math.cos(2.0), 20 + 2 * math.sin(2.0)))
        ellipse = geometry[("sketch_add_ellipse", None, None)][0]
        near((ellipse["major_radius"], ellipse["minor_radius"]), (5, 2))
        near(ellipse["major_axis"], (math.cos(0.5), math.sin(0.5)))
        near(xy(ellipse, "center"), (40, 0))
        spline = geometry[("sketch_add_bspline", None, None)][0]
        assert spline["degree"] == 2 and len(spline["poles"]) == 3
        near(xy(spline, "start") + xy(spline, "end"), (0, 30, 10, 30))
        assert geometry[("sketch_add_point", None, None)][0]["point"] == {"x": 5, "y": 7}
        open_polygon = created[("sketch_add_polygon", False, None)]
        closed_polygon = created[("sketch_add_polygon", True, None)]
        assert len(open_polygon[1]) == 2 and open_polygon[3]["constraint_count"] - open_polygon[2]["constraint_count"] == 1
        assert len(closed_polygon[1]) == 3 and closed_polygon[3]["constraint_count"] - closed_polygon[2]["constraint_count"] == 3
        slot = geometry[("sketch_add_slot", None, None)]
        assert [item["type"] for item in slot] == ["LineSegment", "LineSegment", "ArcOfCircle", "ArcOfCircle"]
        assert all(abs(math.hypot(*vector(item)) - 20) < 1e-6 for item in slot[:2])
        assert all(abs(item["radius"] - 3) < 1e-6 for item in slot[2:])
        near(sorted(xy(item, "center") for item in slot[2:]), [(0, 60), (20, 60)])
        for tool, expected, arguments in [
            ("sketch_add_circle", "Circle radius must be positive", dict(cx=0, cy=0, radius=0)),
            ("sketch_add_circle", "Circle radius must be positive", dict(cx=0, cy=0, radius=-1)),
            ("sketch_add_arc", "Arc radius must be positive", dict(cx=0, cy=0, radius=0, start_angle=0, end_angle=1)),
            ("sketch_add_arc", "Arc sweep", dict(cx=0, cy=0, radius=2, start_angle=0, end_angle=7)),
            ("sketch_add_arc", "Arc sweep", dict(cx=0, cy=0, radius=2, start_angle=2, end_angle=1)),
            ("sketch_add_arc", "Arc sweep", dict(cx=0, cy=0, radius=2, start_angle=1, end_angle=1)),
            ("sketch_add_ellipse", "major_radius > minor_radius", dict(cx=0, cy=0, major_radius=2, minor_radius=2)),
            ("sketch_add_ellipse", "minor_radius must be positive", dict(cx=0, cy=0, major_radius=2, minor_radius=0)),
            ("sketch_add_bspline", "At least 2 points", dict(points=[[0, 0]])),
            ("sketch_add_bspline", "Consecutive points", dict(points=[[0, 0], [0, 0], [1, 1]])),
            (line, "Line endpoints must be different", dict(x1=1, y1=1, x2=1, y2=1)),
            ("sketch_add_rectangle", "differ in both x and y", dict(x1=0, y1=0, x2=0, y2=5)),
            ("sketch_add_polygon", "Consecutive points", dict(points=[[0, 0], [3, 0], [3, 0]], close=False)),
            ("sketch_add_polygon", "closed polygon needs at least three", dict(points=[[0, 0], [3, 0]], close=True)),
            ("sketch_add_polygon", "[x, y] pair", dict(points=[[0], [1, 2]], close=False)),
            ("sketch_add_slot", "Slot endpoints must be different", dict(x1=0, y1=0, x2=0, y2=0, radius=1)),
            ("sketch_add_slot", "Slot radius must be positive", dict(x1=0, y1=0, x2=5, y2=0, radius=0)),
        ]:
            await reject(tool, "Geometry", expected, sketch_name="Geometry", **arguments)

        # N08 geometry and constraint editing.
        await sketch("Edit", (line, dict(x1=0, y1=0, x2=10, y2=2)), ("sketch_add_circle", dict(cx=20, cy=0, radius=3)))
        _, _, after = await mutate("sketch_move_point", "Edit", geo_idx=0, point_idx=2, x=12, y=4)
        near(xy(after["geometries"][0], "end"), (12, 4))
        await reject("sketch_move_point", "Edit", "position 3 is invalid", sketch_name="Edit", geo_idx=0, point_idx=3, x=1, y=1)
        for flag in (True, False):
            result, _, after = await mutate("sketch_set_construction", "Edit", geo_idx=0, construction=flag)
            assert result["construction"] is flag and after["geometries"][0]["construction"] is flag
        await reject("sketch_set_construction", "Edit", "outside", sketch_name="Edit", geo_idx=99, construction=True)
        await invoke("sketch_constrain_radius", doc_name=doc, sketch_name="Edit", geo_idx=1, radius=3)
        result, _, after = await mutate("sketch_delete_geometry", "Edit", geo_idx=1)
        assert result["deleted_constraint_count"] == 1 and after["geometry_count"] == 1 and after["constraint_count"] == 0
        await reject("sketch_delete_geometry", "Edit", "outside", sketch_name="Edit", geo_idx=99)
        length = (await invoke("sketch_constrain_length", doc_name=doc, sketch_name="Edit", geo_idx=0, value=10))["constraint_index"]
        _, _, after = await mutate("sketch_set_constraint_value", "Edit", constraint_idx=length, value=15)
        assert abs(math.hypot(*vector(after["geometries"][0])) - 15) < 1e-6
        await reject("sketch_set_constraint_value", "Edit", "must be positive", sketch_name="Edit", constraint_idx=length, value=0)
        await reject("sketch_set_constraint_value", "Edit", "outside", sketch_name="Edit", constraint_idx=99, value=1)
        result, _, after = await mutate("sketch_set_constraint_mode", "Edit", constraint_idx=length, driving=False)
        assert result["driving"] is False and after["constraints"][length]["driving"] is False
        await reject("sketch_set_constraint_value", "Edit", "reference (non-driving)", sketch_name="Edit",
                     constraint_idx=length, value=12)
        await mutate("sketch_set_constraint_mode", "Edit", constraint_idx=length, driving=True)
        result, _, after = await mutate("sketch_set_constraint_mode", "Edit", constraint_idx=length, active=False)
        assert result["active"] is False and after["constraints"][length]["active"] is False
        await mutate("sketch_set_constraint_mode", "Edit", constraint_idx=length, active=True)
        await reject("sketch_set_constraint_mode", "Edit", "At least one", sketch_name="Edit", constraint_idx=length)
        horizontal = (await invoke("sketch_constrain_horizontal", doc_name=doc, sketch_name="Edit", geo_idx=0))["constraint_index"]
        await reject("sketch_set_constraint_mode", "Edit", "requires a dimensional constraint", sketch_name="Edit",
                     constraint_idx=horizontal, driving=False)
        await reject("sketch_set_constraint_value", "Edit", "requires a dimensional constraint", sketch_name="Edit",
                     constraint_idx=horizontal, value=1)
        result, before, after = await mutate("sketch_delete_constraint", "Edit", constraint_idx=horizontal)
        assert after["constraint_count"] == before["constraint_count"] - 1
        await reject("sketch_delete_constraint", "Edit", "outside", sketch_name="Edit", constraint_idx=99)

        # I11-I17/N08 every constraint variant on its own fixture: DoF delta, geometric oracle, rejection.
        await sketch("Coincident", (line, dict(x1=0, y1=0, x2=10, y2=0)), (line, dict(x1=11, y1=1, x2=20, y2=5)))
        _, geometries = await constrain("sketch_constrain_coincident", "Coincident", 2,
                                        geo_idx1=0, point_idx1=2, geo_idx2=1, point_idx2=1)
        near(xy(geometries[0], "end"), xy(geometries[1], "start"))
        await reject("sketch_constrain_coincident", "Coincident", "two different points", sketch_name="Coincident",
                     geo_idx1=0, point_idx1=2, geo_idx2=0, point_idx2=2)
        await reject("sketch_constrain_coincident", "Coincident", "position 7 is invalid", sketch_name="Coincident",
                     geo_idx1=0, point_idx1=7, geo_idx2=1, point_idx2=1)
        await reject("sketch_constrain_coincident", "Coincident", "outside", sketch_name="Coincident",
                     geo_idx1=0, point_idx1=1, geo_idx2=99, point_idx2=1)

        await sketch("TangentEdge", (line, dict(x1=0, y1=0, x2=10, y2=0)), ("sketch_add_circle", dict(cx=5, cy=4, radius=3)))
        _, geometries = await constrain("sketch_constrain_tangent", "TangentEdge", 1, geo_idx1=0, geo_idx2=1)
        assert abs(line_distance(xy(geometries[1], "center"), geometries[0]) - geometries[1]["radius"]) < 1e-6
        await reject("sketch_constrain_tangent", "TangentEdge", "both point_idx1 and point_idx2", sketch_name="TangentEdge",
                     geo_idx1=0, geo_idx2=1, point_idx1=2)
        await sketch("TangentEnd", (line, dict(x1=0, y1=0, x2=10, y2=0)),
                     ("sketch_add_arc", dict(cx=10.5, cy=3.2, radius=3, start_angle=-1.4, end_angle=0.2)))
        _, geometries = await constrain("sketch_constrain_tangent", "TangentEnd", 3,
                                        geo_idx1=0, geo_idx2=1, point_idx1=2, point_idx2=1)
        near(xy(geometries[0], "end"), xy(geometries[1], "start"))
        radial = [s - c for s, c in zip(xy(geometries[1], "start"), xy(geometries[1], "center"))]
        assert abs(sum(a * b for a, b in zip(vector(geometries[0]), radial))) < 1e-6
        await reject("sketch_constrain_tangent", "TangentEnd", "must be an endpoint", sketch_name="TangentEnd",
                     geo_idx1=0, geo_idx2=1, point_idx1=2, point_idx2=3)
        await sketch("TangentPoint", (line, dict(x1=0, y1=0, x2=10, y2=0)), ("sketch_add_point", dict(x=3, y=3)))
        await reject("sketch_constrain_tangent", "TangentPoint", "Tangent requires", sketch_name="TangentPoint",
                     geo_idx1=0, geo_idx2=1)

        await sketch("Perpendicular", (line, dict(x1=0, y1=0, x2=10, y2=1)), (line, dict(x1=0, y1=0, x2=1, y2=10)),
                     ("sketch_add_circle", dict(cx=5, cy=4, radius=2)), ("sketch_add_point", dict(x=30, y=30)))
        _, geometries = await constrain("sketch_constrain_perpendicular", "Perpendicular", 1, geo_idx1=0, geo_idx2=1)
        assert abs(sum(a * b for a, b in zip(vector(geometries[0]), vector(geometries[1])))) < 1e-6
        _, geometries = await constrain("sketch_constrain_perpendicular", "Perpendicular", 1, geo_idx1=0, geo_idx2=2)
        assert line_distance(xy(geometries[2], "center"), geometries[0]) < 1e-6
        await reject("sketch_constrain_perpendicular", "Perpendicular", "Perpendicular requires", sketch_name="Perpendicular",
                     geo_idx1=2, geo_idx2=3)
        await reject("sketch_constrain_perpendicular", "Perpendicular", "at least one of them a line",
                     sketch_name="Perpendicular", geo_idx1=2, geo_idx2=2)

        await sketch("Parallel", (line, dict(x1=0, y1=0, x2=10, y2=1)), (line, dict(x1=0, y1=5, x2=10, y2=7)),
                     ("sketch_add_circle", dict(cx=5, cy=20, radius=2)))
        _, geometries = await constrain("sketch_constrain_parallel", "Parallel", 1, geo_idx1=0, geo_idx2=1)
        (ax, ay), (bx, by) = vector(geometries[0]), vector(geometries[1])
        assert abs(ax * by - ay * bx) < 1e-6
        await reject("sketch_constrain_parallel", "Parallel", "Parallel requires", sketch_name="Parallel", geo_idx1=0, geo_idx2=2)

        await sketch("Equal", (line, dict(x1=0, y1=0, x2=10, y2=0)), (line, dict(x1=0, y1=5, x2=4, y2=8)),
                     ("sketch_add_circle", dict(cx=20, cy=0, radius=2)),
                     ("sketch_add_arc", dict(cx=30, cy=0, radius=5, start_angle=0, end_angle=1)))
        _, geometries = await constrain("sketch_constrain_equal", "Equal", 1, geo_idx1=0, geo_idx2=1)
        assert abs(math.hypot(*vector(geometries[0])) - math.hypot(*vector(geometries[1]))) < 1e-6
        _, geometries = await constrain("sketch_constrain_equal", "Equal", 1, geo_idx1=2, geo_idx2=3)
        assert abs(geometries[2]["radius"] - geometries[3]["radius"]) < 1e-6
        await reject("sketch_constrain_equal", "Equal", "Equal requires two different lines", sketch_name="Equal",
                     geo_idx1=0, geo_idx2=2)

        await sketch("Symmetric", ("sketch_add_point", dict(x=3, y=2)), ("sketch_add_point", dict(x=-4, y=2.5)),
                     ("sketch_add_point", dict(x=5, y=-1)), ("sketch_add_point", dict(x=-2, y=3)),
                     ("sketch_add_circle", dict(cx=20, cy=0, radius=2)))
        _, geometries = await constrain("sketch_constrain_symmetric", "Symmetric", 2, geo_idx1=0, point_idx1=1,
                                        geo_idx2=1, point_idx2=1, sym_geo=-2)
        near((geometries[1]["point"]["x"], geometries[1]["point"]["y"]), (-geometries[0]["point"]["x"], geometries[0]["point"]["y"]))
        _, geometries = await constrain("sketch_constrain_symmetric", "Symmetric", 2, geo_idx1=2, point_idx1=1,
                                        geo_idx2=3, point_idx2=1, sym_geo=-1, sym_point=1)
        near((geometries[3]["point"]["x"], geometries[3]["point"]["y"]), (-geometries[2]["point"]["x"], -geometries[2]["point"]["y"]))
        await reject("sketch_constrain_symmetric", "Symmetric", "Symmetry about a line requires", sketch_name="Symmetric",
                     geo_idx1=0, point_idx1=1, geo_idx2=1, point_idx2=1, sym_geo=4)

        await sketch("HorizontalVertical", (line, dict(x1=0, y1=0, x2=10, y2=1)), (line, dict(x1=0, y1=0, x2=1, y2=10)),
                     ("sketch_add_circle", dict(cx=20, cy=0, radius=2)), ("sketch_add_point", dict(x=30, y=30)))
        _, geometries = await constrain("sketch_constrain_horizontal", "HorizontalVertical", 1, geo_idx=0)
        assert abs(vector(geometries[0])[1]) < 1e-6
        _, geometries = await constrain("sketch_constrain_vertical", "HorizontalVertical", 1, geo_idx=1)
        assert abs(vector(geometries[1])[0]) < 1e-6
        await reject("sketch_constrain_horizontal", "HorizontalVertical", "Horizontal requires", sketch_name="HorizontalVertical", geo_idx=2)
        await reject("sketch_constrain_vertical", "HorizontalVertical", "Vertical requires", sketch_name="HorizontalVertical", geo_idx=3)
        await reject("sketch_constrain_horizontal", "HorizontalVertical", "local sketch geometry",
                     sketch_name="HorizontalVertical", geo_idx=-1)

        await sketch("Lock", (line, dict(x1=0, y1=0, x2=10, y2=3)), (line, dict(x1=5, y1=0, x2=8, y2=4)),
                     ("sketch_add_point", dict(x=3, y=4)))
        for geo_idx, point_idx, types, position in [(0, 1, ["PointOnObject", "PointOnObject"], (0, 0)),
                                                     (1, 1, ["DistanceX", "PointOnObject"], (5, 0)),
                                                     (2, 1, ["DistanceX", "DistanceY"], (3, 4))]:
            result, before, after = await mutate("sketch_constrain_lock", "Lock", geo_idx=geo_idx, point_idx=point_idx)
            assert before["degrees_of_freedom"] - after["degrees_of_freedom"] == 2
            assert [after["constraints"][index]["type"] for index in result["constraint_indices"]] == types
            locked = after["geometries"][geo_idx]
            near((locked["point"]["x"], locked["point"]["y"]) if "point" in locked else xy(locked, "start"), position)
        await reject("sketch_constrain_lock", "Lock", "position 9 is invalid", sketch_name="Lock", geo_idx=0, point_idx=9)

        await sketch("Block", (line, dict(x1=0, y1=0, x2=10, y2=3)))
        _, geometries = await constrain("sketch_constrain_block", "Block", 4, geo_idx=0)
        near(xy(geometries[0], "start") + xy(geometries[0], "end"), (0, 0, 10, 3))
        await reject("sketch_constrain_block", "Block", "local sketch geometry", sketch_name="Block", geo_idx=-1)

        await sketch("Dimensions", (line, dict(x1=0, y1=0, x2=10, y2=1)), ("sketch_add_point", dict(x=3, y=4)),
                     ("sketch_add_point", dict(x=1, y=1)), ("sketch_add_point", dict(x=5, y=6)),
                     ("sketch_add_circle", dict(cx=30, cy=0, radius=2)))
        _, geometries = await constrain("sketch_constrain_distance", "Dimensions", 1, geo_idx1=0, point_idx1=1,
                                        geo_idx2=1, point_idx2=1, value=7)
        assert abs(math.dist(xy(geometries[0], "start"), (geometries[1]["point"]["x"], geometries[1]["point"]["y"])) - 7) < 1e-6
        _, geometries = await constrain("sketch_constrain_length", "Dimensions", 1, geo_idx=0, value=12)
        assert abs(math.hypot(*vector(geometries[0])) - 12) < 1e-6
        _, geometries = await constrain("sketch_constrain_distance_x", "Dimensions", 1, geo_idx=2, point_idx=1, value=-3)
        assert abs(geometries[2]["point"]["x"] + 3) < 1e-6
        _, geometries = await constrain("sketch_constrain_distance_y", "Dimensions", 1, geo_idx=2, point_idx=1, value=-4)
        assert abs(geometries[2]["point"]["y"] + 4) < 1e-6
        _, geometries = await constrain("sketch_constrain_distance_x_between", "Dimensions", 1, geo_idx1=2, point_idx1=1,
                                        geo_idx2=3, point_idx2=1, value=2.5)
        assert abs(geometries[3]["point"]["x"] - geometries[2]["point"]["x"] - 2.5) < 1e-6
        _, geometries = await constrain("sketch_constrain_distance_y_between", "Dimensions", 1, geo_idx1=2, point_idx1=1,
                                        geo_idx2=3, point_idx2=1, value=-1.5)
        assert abs(geometries[3]["point"]["y"] - geometries[2]["point"]["y"] + 1.5) < 1e-6
        for tool, expected, arguments in [
            ("sketch_constrain_distance", "must be positive", dict(geo_idx1=0, point_idx1=1, geo_idx2=1, point_idx2=1, value=0)),
            ("sketch_constrain_distance", "two different points", dict(geo_idx1=1, point_idx1=1, geo_idx2=1, point_idx2=1, value=2)),
            ("sketch_constrain_length", "must be positive", dict(geo_idx=0, value=0)),
            ("sketch_constrain_length", "Length requires", dict(geo_idx=4, value=3)),
            ("sketch_constrain_distance_x", "position 3 is invalid", dict(geo_idx=1, point_idx=3, value=1)),
            ("sketch_constrain_distance_y_between", "two different points",
             dict(geo_idx1=1, point_idx1=1, geo_idx2=1, point_idx2=1, value=1)),
        ]:
            await reject(tool, "Dimensions", expected, sketch_name="Dimensions", **arguments)

        await sketch("Angles", (line, dict(x1=0, y1=0, x2=10, y2=0)), (line, dict(x1=0, y1=0, x2=10, y2=3)),
                     (line, dict(x1=20, y1=0, x2=25, y2=2)), ("sketch_add_circle", dict(cx=40, cy=0, radius=2)))
        result, geometries = await constrain("sketch_constrain_angle", "Angles", 1, geo_idx1=0, geo_idx2=1, angle=30)
        (ax, ay), (bx, by) = vector(geometries[0]), vector(geometries[1])
        measured = math.degrees(math.acos(abs(ax * bx + ay * by) / math.hypot(ax, ay) / math.hypot(bx, by)))
        assert abs(measured - 30) < 1e-6
        result, geometries = await constrain("sketch_constrain_angle_to_axis", "Angles", 1, geo_idx=2, angle=45)
        assert abs(math.degrees(math.atan2(vector(geometries[2])[1], vector(geometries[2])[0])) - 45) < 1e-6
        constraints = (await info("Angles"))["constraints"]
        assert abs(constraints[result["constraint_index"]]["value"] - math.radians(45)) < 1e-6
        _, _, after = await mutate("sketch_set_constraint_value", "Angles", constraint_idx=result["constraint_index"], value=60)
        assert abs(math.degrees(math.atan2(vector(after["geometries"][2])[1], vector(after["geometries"][2])[0])) - 60) < 1e-6
        await reject("sketch_constrain_angle", "Angles", "Angle requires", sketch_name="Angles", geo_idx1=0, geo_idx2=3, angle=30)
        await reject("sketch_constrain_angle_to_axis", "Angles", "Angle to axis requires", sketch_name="Angles", geo_idx=3, angle=30)

        await sketch("Radii", ("sketch_add_circle", dict(cx=0, cy=0, radius=2)),
                     ("sketch_add_arc", dict(cx=10, cy=0, radius=3, start_angle=0, end_angle=2)),
                     ("sketch_add_circle", dict(cx=20, cy=0, radius=2)), (line, dict(x1=0, y1=10, x2=5, y2=10)))
        _, geometries = await constrain("sketch_constrain_radius", "Radii", 1, geo_idx=0, radius=4)
        assert abs(geometries[0]["radius"] - 4) < 1e-6
        _, geometries = await constrain("sketch_constrain_radius", "Radii", 1, geo_idx=1, radius=2.5)
        assert abs(geometries[1]["radius"] - 2.5) < 1e-6
        _, geometries = await constrain("sketch_constrain_diameter", "Radii", 1, geo_idx=2, diameter=10)
        assert abs(geometries[2]["radius"] - 5) < 1e-6
        for tool, expected, arguments in [
            ("sketch_constrain_radius", "Radius requires", dict(geo_idx=3, radius=2)),
            ("sketch_constrain_radius", "must be positive", dict(geo_idx=0, radius=0)),
            ("sketch_constrain_diameter", "Diameter requires", dict(geo_idx=3, diameter=2)),
            ("sketch_constrain_diameter", "Diameter must be positive", dict(geo_idx=2, diameter=-1)),
        ]:
            await reject(tool, "Radii", expected, sketch_name="Radii", **arguments)

        await sketch("PointOnObject", ("sketch_add_circle", dict(cx=0, cy=0, radius=5)), ("sketch_add_point", dict(x=7, y=1)),
                     ("sketch_add_point", dict(x=3, y=2)), (line, dict(x1=10, y1=0, x2=20, y2=5)),
                     ("sketch_add_point", dict(x=15, y=8)))
        await invoke("sketch_constrain_lock", doc_name=doc, sketch_name="PointOnObject", geo_idx=0, point_idx=3)
        _, geometries = await constrain("sketch_constrain_point_on_object", "PointOnObject", 1, geo_idx=1, point_idx=1,
                                        target_geo_idx=0)
        assert abs(math.hypot(geometries[1]["point"]["x"], geometries[1]["point"]["y"]) - geometries[0]["radius"]) < 1e-6
        _, geometries = await constrain("sketch_constrain_point_on_object", "PointOnObject", 1, geo_idx=2, point_idx=1,
                                        target_geo_idx=-1)
        assert abs(geometries[2]["point"]["y"]) < 1e-6
        _, geometries = await constrain("sketch_constrain_point_on_object", "PointOnObject", 1, geo_idx=4, point_idx=1,
                                        target_geo_idx=3)
        assert line_distance((geometries[4]["point"]["x"], geometries[4]["point"]["y"]), geometries[3]) < 1e-6
        await reject("sketch_constrain_point_on_object", "PointOnObject", "Point on object requires", sketch_name="PointOnObject",
                     geo_idx=1, point_idx=1, target_geo_idx=2)
        await reject("sketch_constrain_point_on_object", "PointOnObject", "other than", sketch_name="PointOnObject",
                     geo_idx=3, point_idx=1, target_geo_idx=3)

        # N08 solver diagnostics: 0-based conflict/redundancy IDs with exact rollback; inactive constraints.
        await sketch("Diagnostics", (line, dict(x1=0, y1=0, x2=10, y2=0)))
        await invoke("sketch_constrain_length", doc_name=doc, sketch_name="Diagnostics", geo_idx=0, value=10)
        text = await reject("sketch_constrain_length", "Diagnostics", "conflicting=[0, 1]", sketch_name="Diagnostics",
                            geo_idx=0, value=20)
        text = await reject("sketch_constrain_length", "Diagnostics", "redundant=[1]", sketch_name="Diagnostics",
                            geo_idx=0, value=10)
        await invoke("sketch_constrain_horizontal", doc_name=doc, sketch_name="Diagnostics", geo_idx=0)
        await mutate("sketch_set_constraint_mode", "Diagnostics", constraint_idx=0, active=False)
        _, geometries = await constrain("sketch_constrain_length", "Diagnostics", 1, geo_idx=0, value=20)
        assert abs(math.hypot(*vector(geometries[0])) - 20) < 1e-6
        text = await reject("sketch_set_constraint_mode", "Diagnostics", "conflicting=", sketch_name="Diagnostics",
                            constraint_idx=0, active=True)
        assert {0, 2} <= {int(value) for value in re.search(r"conflicting=\[([^\]]*)\]", text).group(1).split(",")}

        # N09 external geometry, attachment and drawing operations.
        await invoke("part_box", doc_name=doc, name="RefBox", length=10, width=10, height=10)
        await invoke("create_sketch", doc_name=doc, name="External")
        await invoke(line, doc_name=doc, sketch_name="External", x1=1, y1=1, x2=4, y2=3)
        edge = await select("RefBox", "edge", geometry_type="line", position=[5, 0, 10])
        result, _, after = await mutate("sketch_add_external", "External", selection=edge)
        assert (result["external_index"], result["geometry_index"]) == (0, -3)
        projected = after["external_geometries"]
        assert [(item["index"], item["type"]) for item in projected] == [(-3, "LineSegment")]
        near(sorted(xy(projected[0], "start") + xy(projected[0], "end")), sorted((0, 0, 10, 0)))
        await reject("sketch_add_external", "External", "Document changed", sketch_name="External", selection=edge)
        _, geometries = await constrain("sketch_constrain_coincident", "External", 2, geo_idx1=0, point_idx1=1,
                                        geo_idx2=-3, point_idx2=1)
        near(xy(geometries[0], "start"), xy(projected[0], "start"))
        defining = await select("RefBox", "edge", geometry_type="line", position=[10, 5, 10])
        result, _, after = await mutate("sketch_add_external", "External", selection=defining, defining=True)
        assert result["external_index"] == 1 and after["external_geometries"][1]["type"] == "LineSegment"
        vertical = await select("RefBox", "edge", geometry_type="line", position=[0, 0, 5])
        result, _, after = await mutate("sketch_add_external", "External", selection=vertical, intersection=True)
        assert result["external_index"] == 2 and after["external_geometries"][2]["type"] == "Point"
        near((after["external_geometries"][2]["point"]["x"], after["external_geometries"][2]["point"]["y"]), (0, 0))
        face = await select("RefBox", "face", normal=[0, 0, 1])
        await reject("sketch_add_external", "External", "must be an edge", sketch_name="External", selection=face)
        await reject("sketch_delete_external", "External", "outside", sketch_name="External", external_idx=9)
        result, before, after = await mutate("sketch_delete_external", "External", external_idx=2)
        assert len(after["external_geometries"]) == len(before["external_geometries"]) - 1

        await invoke("create_sketch", doc_name=doc, name="OnFace")
        await invoke(line, doc_name=doc, sketch_name="OnFace", x1=1, y1=2, x2=3, y2=2)
        face = await select("RefBox", "face", normal=[0, 0, 1])
        result, _, after = await mutate("sketch_set_attachment", "OnFace", support_selection=face, offset_z=2, rotation_z=90)
        assert result["map_mode"] == "FlatFace" and after["attachment"]["support"][0]["object"] == "RefBox"
        for actual, wanted in zip(await vertices("OnFace"), sorted([(-2, 1, 12), (-2, 3, 12)])):
            near(actual, wanted, 1e-6)
        body = (await invoke("partdesign_body", doc_name=doc, name="DatumBody"))["name"]
        datum = (await invoke("partdesign_datum", doc_name=doc, body_name=body, kind="plane", name="SketchDatum",
                              z=4, rotation_x=90))["name"]
        await invoke("create_sketch", doc_name=doc, name="OnDatum", body_name=body)
        await invoke(line, doc_name=doc, sketch_name="OnDatum", x1=1, y1=2, x2=3, y2=2)
        result, _, after = await mutate("sketch_set_attachment", "OnDatum", support_name=datum, offset_x=1, rotation_z=90)
        assert result["map_mode"] == "ObjectXY" and after["attachment"]["support"] == [
            {"document": doc, "object": datum, "subelements": []}]
        for actual, wanted in zip(await vertices("OnDatum"), sorted([(-1, 0, 5), (-1, 0, 7)])):
            near(actual, wanted, 1e-6)
        await invoke("part_cylinder", doc_name=doc, name="RefCylinder", radius=2, height=5, x=30)
        curved = await select("RefCylinder", "face", geometry_type="cylinder")
        await reject("sketch_set_attachment", "OnDatum", "planar face", sketch_name="OnDatum", support_selection=curved)
        face = await select("RefBox", "face", normal=[0, 0, 1])
        await reject("sketch_set_attachment", "OnDatum", "not both", sketch_name="OnDatum", support_name=datum,
                     support_selection=face)
        await reject("sketch_set_attachment", "OnDatum", "datum plane", sketch_name="OnDatum", support_name="RefBox")
        await invoke("create_sketch", doc_name=doc, name="Detached", body_name=body)
        await invoke(line, doc_name=doc, sketch_name="Detached", x1=1, y1=2, x2=3, y2=2)
        await invoke("sketch_set_attachment", doc_name=doc, sketch_name="Detached", support_name=datum)
        result, _, after = await mutate("sketch_set_attachment", "Detached")
        assert result["support"] is None and after["attachment"]["map_mode"] == "Deactivated" and not after["attachment"]["support"]

        await sketch("Trim", (line, dict(x1=0, y1=0, x2=30, y2=0)), (line, dict(x1=10, y1=-5, x2=10, y2=5)),
                     (line, dict(x1=20, y1=-5, x2=20, y2=5)), ("sketch_add_circle", dict(cx=50, cy=0, radius=5)),
                     (line, dict(x1=40, y1=0, x2=60, y2=0)), ("sketch_add_point", dict(x=0, y=20)))
        result, before, after = await mutate("sketch_trim", "Trim", geo_idx=0, x=15, y=0)
        horizontal = sorted(xy(item, "start") + xy(item, "end") for item in after["geometries"]
                            if item["type"] == "LineSegment" and abs(vector(item)[1]) < 1e-6 and item["start"]["x"] < 35)
        near([value for item in horizontal for value in item], [0, 0, 10, 0, 20, 0, 30, 0])
        assert after["geometry_count"] == before["geometry_count"] + 1
        result, before, after = await mutate("sketch_trim", "Trim", geo_idx=3, x=50, y=5)
        trimmed = after["geometries"][3]
        assert trimmed["type"] == "ArcOfCircle" and abs(trimmed["radius"] - 5) < 1e-6
        assert abs(trimmed["parameter_range"][1] - trimmed["parameter_range"][0] - math.pi) < 1e-6
        near(sorted(xy(trimmed, "start") + xy(trimmed, "end")), sorted((45, 0, 55, 0)))
        await reject("sketch_trim", "Trim", "must lie on the curve", sketch_name="Trim", geo_idx=1, x=50, y=50)
        await reject("sketch_trim", "Trim", "does not support trimming against sketch axes", sketch_name="Trim",
                     geo_idx=1, x=10, y=1, include_axes=True)
        await reject("sketch_trim", "Trim", "Trim requires", sketch_name="Trim", geo_idx=5, x=0, y=20)

        await sketch("Extend", (line, dict(x1=0, y1=0, x2=5, y2=0)),
                     ("sketch_add_arc", dict(cx=0, cy=10, radius=2, start_angle=0, end_angle=math.pi / 2)),
                     ("sketch_add_circle", dict(cx=20, cy=10, radius=2)))
        _, _, after = await mutate("sketch_extend", "Extend", geo_idx=0, increment=2, point_idx=1)
        near(xy(after["geometries"][0], "start"), (-2, 0))
        _, _, after = await mutate("sketch_extend", "Extend", geo_idx=0, increment=-1, point_idx=2)
        near(xy(after["geometries"][0], "end"), (4, 0))
        _, _, after = await mutate("sketch_extend", "Extend", geo_idx=1, increment=1, point_idx=2)
        span = after["geometries"][1]["parameter_range"]
        assert abs(span[1] - span[0] - (math.pi / 2 + 0.5)) < 1e-6
        await reject("sketch_extend", "Extend", "must be nonzero", sketch_name="Extend", geo_idx=0, increment=0, point_idx=2)
        await reject("sketch_extend", "Extend", "point_idx must be 1", sketch_name="Extend", geo_idx=0, increment=1, point_idx=3)
        await reject("sketch_extend", "Extend", "Extend requires", sketch_name="Extend", geo_idx=2, increment=1, point_idx=2)

        for name, trim, corner, new_count, line_ends in [("FilletBoth", True, True, 2, ((8, 0), (10, 2))),
                                                         ("FilletNone", False, False, 1, ((10, 0), (10, 0))),
                                                         ("FilletTrim", True, False, 1, ((8, 0), (10, 2)))]:
            await sketch(name, (line, dict(x1=0, y1=0, x2=10, y2=0)), (line, dict(x1=10, y1=0, x2=10, y2=10)))
            await invoke("sketch_constrain_coincident", doc_name=doc, sketch_name=name,
                         geo_idx1=0, point_idx1=2, geo_idx2=1, point_idx2=1)
            result, before, after = await mutate("sketch_fillet", name, geo_idx1=0, geo_idx2=1, near1_x=9, near1_y=0,
                                                 near2_x=10, near2_y=1, radius=2, trim=trim, create_corner=corner)
            assert len(result["geometry_indices"]) == new_count, (name, result)
            fillet = after["geometries"][result["geometry_indices"][0]]
            assert fillet["type"] == "ArcOfCircle" and abs(fillet["radius"] - 2) < 1e-6
            near(xy(fillet, "center"), (8, 2))
            near(xy(after["geometries"][0], "end") + xy(after["geometries"][1], "start"), line_ends[0] + line_ends[1])
        await reject("sketch_fillet", "FilletNone", "must be positive", sketch_name="FilletNone", geo_idx1=0, geo_idx2=1,
                     near1_x=9, near1_y=0, near2_x=10, near2_y=1, radius=0)
        await sketch("FilletArc", (line, dict(x1=0, y1=0, x2=10, y2=0)),
                     ("sketch_add_arc", dict(cx=20, cy=0, radius=10, start_angle=math.pi / 2, end_angle=math.pi)))
        await invoke("sketch_constrain_coincident", doc_name=doc, sketch_name="FilletArc",
                     geo_idx1=0, point_idx1=2, geo_idx2=1, point_idx2=2)
        result, _, after = await mutate("sketch_fillet", "FilletArc", geo_idx1=0, geo_idx2=1, near1_x=9, near1_y=0,
                                        near2_x=20 - 10 * math.cos(0.1), near2_y=10 * math.sin(0.1), radius=2)
        fillet = after["geometries"][result["geometry_indices"][0]]
        assert fillet["type"] == "ArcOfCircle" and abs(fillet["radius"] - 2) < 1e-6
        assert abs(abs(fillet["center"]["y"]) - 2) < 1e-6, fillet
        assert min(abs(math.dist(xy(fillet, "center"), (20, 0)) - value) for value in (8, 12)) < 1e-6, fillet
        await reject("sketch_fillet", "FilletNone", "two different geometries", sketch_name="FilletNone", geo_idx1=0,
                     geo_idx2=0, near1_x=9, near1_y=0, near2_x=10, near2_y=1, radius=1)
        await reject("sketch_fillet", "FilletBoth", "Fillet requires", sketch_name="FilletBoth", geo_idx1=0,
                     geo_idx2=3, near1_x=9, near1_y=0, near2_x=10, near2_y=1, radius=1)

        await sketch("CopyMirror", ("sketch_add_circle", dict(cx=3, cy=4, radius=2)), ("sketch_add_point", dict(x=20, y=20)))
        await invoke("sketch_constrain_radius", doc_name=doc, sketch_name="CopyMirror", geo_idx=0, radius=2)
        for clone, offset, kind in [(False, (10, 0), "Radius"), (True, (0, 10), "Equal")]:
            result, before, after = await mutate("sketch_copy", "CopyMirror", geometry_indices=[0], offset_x=offset[0],
                                                 offset_y=offset[1], clone=clone)
            new = result["geometry_indices"][0]
            near(xy(after["geometries"][new], "center"), (3 + offset[0], 4 + offset[1]))
            added = after["constraints"][before["constraint_count"]:]
            assert [item["type"] for item in added] == [kind] and new in (added[0]["first"], added[0]["second"]), added
        result, _, after = await mutate("sketch_mirror", "CopyMirror", geometry_indices=[0], reference_geo_idx=-2)
        near(xy(after["geometries"][result["geometry_indices"][0]], "center"), (-3, 4))
        result, _, after = await mutate("sketch_mirror", "CopyMirror", geometry_indices=[0], reference_geo_idx=1,
                                        reference_point_idx=1)
        near(xy(after["geometries"][result["geometry_indices"][0]], "center"), (37, 36))
        await reject("sketch_copy", "CopyMirror", "without duplicates", sketch_name="CopyMirror", geometry_indices=[0, 0],
                     offset_x=1, offset_y=1)
        await reject("sketch_copy", "CopyMirror", "at least 1 item", sketch_name="CopyMirror", geometry_indices=[],
                     offset_x=1, offset_y=1)
        await reject("sketch_copy", "CopyMirror", "outside", sketch_name="CopyMirror", geometry_indices=[99],
                     offset_x=1, offset_y=1)
        await reject("sketch_mirror", "CopyMirror", "Reference geometry index 99", sketch_name="CopyMirror",
                     geometry_indices=[0], reference_geo_idx=99)
        await reject("sketch_mirror", "CopyMirror", "Mirror about a line requires", sketch_name="CopyMirror",
                     geometry_indices=[1], reference_geo_idx=0)

        # Fully constrained editable profile without Block, file cycle and second edit after reopen.
        await sketch("Profile", ("sketch_add_rectangle", dict(x1=0, y1=0, x2=40, y2=20)))
        await invoke("sketch_constrain_lock", doc_name=doc, sketch_name="Profile", geo_idx=0, point_idx=1)
        width = (await invoke("sketch_constrain_length", doc_name=doc, sketch_name="Profile", geo_idx=0, value=40))["constraint_index"]
        profile = await invoke("sketch_constrain_length", doc_name=doc, sketch_name="Profile", geo_idx=1, value=20)
        assert profile["fully_constrained"] and profile["degrees_of_freedom"] == 0
        audited = ["PlaneXY", "PlaneXZ", "PlaneYZ", "Geometry", "Edit", "Coincident", "TangentEnd", "Symmetric", "Lock",
                   "Dimensions", "Angles", "Radii", "PointOnObject", "Diagnostics", "External", "OnFace", "OnDatum",
                   "Trim", "Extend", "FilletBoth", "FilletArc", "CopyMirror", "Profile"]
        saved = {name: await info(name) for name in audited}
        path = str(directory / f"{doc}.FCStd")
        await invoke("save_document_safe", doc_name=doc, path=path)
        await invoke("close_document_safe", doc_name=doc)
        documents.remove(doc)
        state["doc"] = doc = (await invoke("open_document", path=path))["name"]
        documents.append(doc)
        for name in audited:
            same(await info(name), saved[name], name)
        for actual, wanted in zip(await vertices("OnDatum"), sorted([(-1, 0, 5), (-1, 0, 7)])):
            near(actual, wanted, 1e-6)
        _, _, after = await mutate("sketch_set_constraint_value", "Profile", constraint_idx=width, value=60)
        assert after["fully_constrained"] and abs(math.hypot(*vector(after["geometries"][0])) - 60) < 1e-6
        await invoke("save_document_safe", doc_name=doc, path=path, overwrite=True)
        failures = sum(1 for entry in transcript if entry.get("is_error"))
        return {"calls": len(transcript), "negative_checks": failures, "fcstd": path, "sketches": len(audited)}
    finally:
        for document in reversed(documents):
            await invoke("close_document_safe", doc_name=document, discard_changes=True)
        (directory / "mcp-transcript.json").write_text(json.dumps(transcript, indent=2), encoding="utf-8")
        assert not json.loads((await call("get_status")).content[0].text)["documents"]


async def check_stage12b_partdesign_a(session, call, directory):
    """V audit of PartDesign datums, extrusions, rotations, lofts and pipes through MCP only."""
    transcript = []
    documents = []
    state = {}
    pi = math.pi

    def decode(response):
        if response.structuredContent and "contract_version" in response.structuredContent:
            return response.structuredContent
        return json.loads(response.content[0].text)

    async def invoke(tool, **arguments):
        result = decode(await call(tool, **arguments))
        transcript.append({"tool": tool, "arguments": arguments, "result": result})
        if isinstance(result, dict) and "contract_version" in result:
            assert result["status"] == "success", result
            return result["data"]
        return result

    def same(actual, expected, path="$"):
        if isinstance(expected, float) or isinstance(actual, float):
            assert abs(actual - expected) <= 1e-7, (path, actual, expected)
        elif isinstance(expected, dict):
            assert isinstance(actual, dict) and set(actual) == set(expected), (path, actual, expected)
            for key in expected:
                same(actual[key], expected[key], f"{path}.{key}")
        elif isinstance(expected, list):
            assert isinstance(actual, list) and len(actual) == len(expected), (path, actual, expected)
            for index, (left, right) in enumerate(zip(actual, expected)):
                same(left, right, f"{path}[{index}]")
        else:
            assert actual == expected, (path, actual, expected)

    def near(actual, expected, tolerance=1e-6):
        assert len(actual) == len(expected) and all(abs(a - e) <= tolerance for a, e in zip(actual, expected)), (
            actual, expected)

    def volume_ok(actual, expected):
        assert abs(actual - expected) <= max(1e-6, 1e-6 * abs(expected)), (actual, expected)

    def parallel(actual, expected):
        length = math.sqrt(sum(value * value for value in expected))
        assert abs(abs(sum(a * e for a, e in zip(actual, expected))) / length - 1) <= 1e-9, (actual, expected)

    def on_line(point, origin, direction):
        delta = [p - o for p, o in zip(point, origin)]
        cross = [delta[1] * direction[2] - delta[2] * direction[1], delta[2] * direction[0] - delta[0] * direction[2],
                 delta[0] * direction[1] - delta[1] * direction[0]]
        assert math.sqrt(sum(value * value for value in cross)) <= 1e-6, (point, origin, direction)

    def sector(outer, inner, theta_deg, bisector_deg):
        theta = math.radians(theta_deg)
        distance = (2 / 3) * (outer ** 3 - inner ** 3) / (outer ** 2 - inner ** 2)
        distance *= math.sin(theta / 2) / (theta / 2) if theta < 2 * pi - 1e-12 else 0
        return distance * math.cos(math.radians(bisector_deg)), distance * math.sin(math.radians(bisector_deg))

    async def names():
        return sorted(item["name"] for item in await invoke("list_objects", doc_name=state["doc"]))

    async def tip(body):
        value = (await invoke("get_properties", doc_name=state["doc"], obj_name=body, properties=["Tip"]))["properties"][0]["value"]
        return value["object"] if value else None

    async def snap(body):
        objects = await names()
        snapshot = {"objects": objects, "tip": await tip(body) if body in objects else None}
        if snapshot["tip"]:
            measured = await invoke("measure", doc_name=state["doc"], obj_name=snapshot["tip"])
            snapshot["shape"] = {key: measured[key] for key in ("volume", "area", "bounding_box", "center_of_mass")}
            snapshot["tip_properties"] = (await invoke("get_properties", doc_name=state["doc"],
                                                       obj_name=snapshot["tip"]))["properties"]
        return snapshot

    async def measure(obj):
        return await invoke("measure", doc_name=state["doc"], obj_name=obj)

    async def reject(tool, body, expected, **arguments):
        before = await snap(body)
        response = await session.call_tool(tool, {"doc_name": state["doc"], **arguments})
        text = " ".join(getattr(content, "text", "") for content in response.content)
        transcript.append({"tool": tool, "arguments": arguments, "is_error": response.isError, "result": text})
        assert response.isError, (tool, arguments, text)
        assert expected in text, (tool, expected, text)
        same(await snap(body), before)
        return text

    async def mutate(tool, body, **arguments):
        before = await snap(body)
        result = await invoke(tool, doc_name=state["doc"], **arguments)
        after = await snap(body)
        await invoke("undo", doc_name=state["doc"])
        same(await snap(body), before)
        await invoke("redo", doc_name=state["doc"])
        same(await snap(body), after)
        return result, after

    async def feature(tool, body, expected_volume, **arguments):
        result, after = await mutate(tool, body, **arguments)
        assert after["tip"] == result["name"], (after, result)
        volume_ok(after["shape"]["volume"], expected_volume)
        volume_ok(result["volume"], expected_volume)
        return result, after["shape"]

    async def new_body(name):
        result, _ = await mutate("partdesign_body", name, name=name)
        return result["name"]

    async def rect(name, body, x1, y1, x2, y2, plane="XY", offset=0):
        await invoke("create_sketch", doc_name=state["doc"], name=name, body_name=body, plane=plane, offset=offset)
        await invoke("sketch_add_rectangle", doc_name=state["doc"], sketch_name=name, x1=x1, y1=y1, x2=x2, y2=y2)
        return name

    async def circle(name, body, cx, cy, radius, plane="XY", offset=0):
        await invoke("create_sketch", doc_name=state["doc"], name=name, body_name=body, plane=plane, offset=offset)
        await invoke("sketch_add_circle", doc_name=state["doc"], sketch_name=name, cx=cx, cy=cy, radius=radius)
        return name

    async def select(obj, kind, **filters):
        return (await invoke("select_subelement", doc_name=state["doc"], obj_name=obj, kind=kind, filters=filters))

    async def count(obj, kind, **filters):
        return (await invoke("list_subelements", doc_name=state["doc"], obj_name=obj, kind=kind, filters=filters))["total"]

    async def base_block(body, size=20, height=20):
        sketch = await rect(f"{body}Base", body, -size / 2, -size / 2, size / 2, size / 2)
        await feature("partdesign_pad", body, size * size * height, sketch_name=sketch, length=height, name=f"{body}Pad")

    def span(value):
        return {"min": float(value) - 1e-6, "max": float(value) + 1e-6}

    def bbox(shape):
        box = shape["bounding_box"]
        return [box["min"][axis] for axis in "xyz"] + [box["max"][axis] for axis in "xyz"]

    def com(shape):
        return [shape["center_of_mass"][axis] for axis in "xyz"]

    assert not json.loads((await call("get_status")).content[0].text)["documents"], "Stage 12b needs an empty instance"
    try:
        state["doc"] = doc = (await invoke("create_document", name="MCP_Stage12b_PartDesignA"))["name"]
        documents.append(doc)
        other = (await invoke("create_document", name="MCP_Stage12b_PartDesignA_Other"))["name"]
        documents.append(other)
        await invoke("part_box", doc_name=other, name="ForeignBox", length=5, width=5, height=5)
        foreign_face = (await invoke("select_subelement", doc_name=other, obj_name="ForeignBox", kind="face",
                                     filters={"normal": [0, 0, 1]}))["selection"]

        # N10 datums: explicit placements, supports on Body features, undo/redo and invalid supports.
        datum_body = await new_body("DatumBody")
        await rect("DatumBase", datum_body, 0, 0, 20, 20)
        await feature("partdesign_pad", datum_body, 4000, sketch_name="DatumBase", length=10, name="DatumPad")
        await circle("DatumHole", datum_body, 10, 10, 5, offset=10)
        await feature("partdesign_pocket", datum_body, 4000 - 250 * pi, sketch_name="DatumHole", length=1,
                      through_all=True, name="DatumBore")
        await mutate("partdesign_datum", datum_body, body_name=datum_body, kind="plane", name="ExplicitPlane",
                     x=1, y=2, z=3, rotation_x=90, rotation_z=30)
        face = (await select("ExplicitPlane", "face"))
        parallel(face["normal"], [0.5, -math.sqrt(3) / 2, 0])
        placement = (await invoke("get_properties", doc_name=doc, obj_name="ExplicitPlane",
                                  properties=["Placement"]))["properties"][0]["value"]
        near(placement["position"], [1, 2, 3])
        await mutate("partdesign_datum", datum_body, body_name=datum_body, kind="axis", name="ExplicitAxis",
                     x=2, rotation_y=90)
        edge = await select("ExplicitAxis", "edge")
        parallel(edge["axis"], [1, 0, 0])
        on_line(edge["position"], [2, 0, 0], [1, 0, 0])
        await mutate("partdesign_datum", datum_body, body_name=datum_body, kind="point", name="ExplicitPoint", x=4, y=5, z=6)
        near((await select("ExplicitPoint", "vertex"))["position"], [4, 5, 6])

        top = (await select("DatumBore", "face", geometry_type="plane", normal=[0, 0, 1]))["selection"]
        result, _ = await mutate("partdesign_datum", datum_body, body_name=datum_body, kind="plane", name="TopPlane",
                                 support_selection=top, z=2)
        assert result["attachment"]["map_mode"] == "FlatFace", result
        parallel((await select("TopPlane", "face"))["normal"], [0, 0, 1])
        placement = (await invoke("get_properties", doc_name=doc, obj_name="TopPlane",
                                  properties=["Placement"]))["properties"][0]["value"]
        assert abs(placement["position"][2] - 12) <= 1e-6, placement
        bore = (await select("DatumBore", "face", geometry_type="cylinder", radius=span(5)))["selection"]
        result, _ = await mutate("partdesign_datum", datum_body, body_name=datum_body, kind="axis", name="BoreAxis",
                                 support_selection=bore, z=3)
        assert result["attachment"]["map_mode"] == "AxisOfCurvature", result
        assert result["attachment"]["subelements"][0].startswith("Edge"), result
        edge = await select("BoreAxis", "edge")
        parallel(edge["axis"], [0, 0, 1])
        on_line(edge["position"], [10, 10, 0], [0, 0, 1])
        line_support = (await select("DatumBore", "edge", geometry_type="line", position=[10, 0, 0]))["selection"]
        result, _ = await mutate("partdesign_datum", datum_body, body_name=datum_body, kind="axis", name="EdgeAxis",
                                 support_selection=line_support)
        assert result["attachment"]["map_mode"] == "TwoPointLine", result
        edge = await select("EdgeAxis", "edge")
        parallel(edge["axis"], [1, 0, 0])
        on_line(edge["position"], [0, 0, 0], [1, 0, 0])
        corner = (await select("DatumBore", "vertex", position=[20, 20, 10]))["selection"]
        result, _ = await mutate("partdesign_datum", datum_body, body_name=datum_body, kind="point", name="CornerPoint",
                                 support_selection=corner, x=1)
        assert result["attachment"]["map_mode"] == "Vertex", result
        near((await select("CornerPoint", "vertex"))["position"], [21, 20, 10])
        await reject("partdesign_datum", datum_body, "Datum kind must be", body_name=datum_body, kind="circle")
        corner = (await select("DatumBore", "vertex", position=[20, 20, 10]))["selection"]
        await reject("partdesign_datum", datum_body, "does not support vertex", body_name=datum_body, kind="plane",
                     support_selection=corner)
        top = (await select("DatumBore", "face", geometry_type="plane", normal=[0, 0, 1]))["selection"]
        await reject("partdesign_datum", datum_body, "does not support plane face", body_name=datum_body, kind="axis",
                     support_selection=top)
        await reject("partdesign_datum", datum_body, "does not support line edge", body_name=datum_body, kind="point",
                     support_selection=(await select("DatumBore", "edge", geometry_type="line", position=[10, 0, 0]))["selection"])
        await reject("partdesign_datum", datum_body, "not a PartDesign Body", body_name="DatumPad", kind="point")
        await reject("partdesign_datum", datum_body, "must be in document", body_name=datum_body, kind="plane",
                     support_selection=foreign_face)
        top = (await select("DatumBore", "face", geometry_type="plane", normal=[0, 0, 1]))["selection"]
        await invoke("sketch_add_line", doc_name=doc, sketch_name="DatumHole", x1=0, y1=0, x2=1, y2=0)
        await invoke("undo", doc_name=doc)
        await reject("partdesign_datum", datum_body, "Document changed", body_name=datum_body, kind="plane",
                     support_selection=top)

        # N10 Pad: every end condition and side; area 50 mm^2 profile.
        pads = {"dimension": ({}, 500, [0, 0, 0, 10, 5, 10]),
                "reversed": ({"reversed": True}, 500, [0, 0, -10, 10, 5, 0]),
                "symmetric": ({"symmetric": True}, 500, [0, 0, -5, 10, 5, 5]),
                "symmetric_reversed": ({"symmetric": True, "reversed": True}, 500, [0, 0, -5, 10, 5, 5]),
                "two_lengths": ({"end_condition": "two_lengths", "second_length": 4}, 700, [0, 0, -4, 10, 5, 10]),
                "two_lengths_reversed": ({"end_condition": "two_lengths", "second_length": 4, "reversed": True}, 700,
                                         [0, 0, -10, 10, 5, 4])}
        for index, (variant, (options, expected, box)) in enumerate(pads.items()):
            body = await new_body(f"Pad{index}")
            await rect(f"PadProfile{index}", body, 0, 0, 10, 5)
            _, shape = await feature("partdesign_pad", body, expected, sketch_name=f"PadProfile{index}", length=10,
                                     name=f"Pad_{variant}", **options)
            near(bbox(shape), box)
        upto = await new_body("PadUpTo")
        await rect("UpToBase", upto, -10, -10, 10, 10, offset=20)
        await feature("partdesign_pad", upto, 4000, sketch_name="UpToBase", length=10, name="UpToBasePad")
        await rect("UpToProfile", upto, -5, -5, 5, 5)
        await reject("partdesign_pad", upto, "No faces found", sketch_name="UpToProfile", length=1,
                     end_condition="up_to_first", reversed=True)
        _, shape = await feature("partdesign_pad", upto, 6000, sketch_name="UpToProfile", length=1,
                                 end_condition="up_to_first", name="PadUpToFirst")
        near(bbox(shape), [-10, -10, 0, 10, 10, 30])
        await invoke("undo", doc_name=doc)
        bottom = (await select("UpToBasePad", "face", geometry_type="plane", normal=[0, 0, -1]))["selection"]
        _, shape = await feature("partdesign_pad", upto, 6000, sketch_name="UpToProfile", length=1,
                                 end_condition="up_to_face", target_selection=bottom, name="PadUpToFace")
        near(bbox(shape), [-10, -10, 0, 10, 10, 30])
        datum_pad = await new_body("PadUpToDatum")
        await rect("UpToDatumProfile", datum_pad, 0, 0, 10, 5)
        await mutate("partdesign_datum", datum_pad, body_name=datum_pad, kind="plane", name="LevelPlane", z=25)
        await mutate("partdesign_datum", datum_pad, body_name=datum_pad, kind="plane", name="TiltPlane", z=25, rotation_y=20)
        level = (await select("LevelPlane", "face"))["selection"]
        _, shape = await feature("partdesign_pad", datum_pad, 1250, sketch_name="UpToDatumProfile", length=1,
                                 end_condition="up_to_face", target_selection=level, name="PadToLevel")
        near(bbox(shape), [0, 0, 0, 10, 5, 25])
        await invoke("undo", doc_name=doc)
        tilt = (await select("TiltPlane", "face"))["selection"]
        await feature("partdesign_pad", datum_pad, 1250 - 250 * math.tan(math.radians(20)),
                      sketch_name="UpToDatumProfile", length=1, end_condition="up_to_face", target_selection=tilt,
                      name="PadToTilt")
        await invoke("create_sketch", doc_name=doc, name="LooseProfile")
        await invoke("sketch_add_rectangle", doc_name=doc, sketch_name="LooseProfile", x1=0, y1=0, x2=1, y2=1)
        level = (await select("LevelPlane", "face"))["selection"]
        for message, options in [("Extrusion length must be positive", {"length": 0}),
                                 ("Extrusion length must be positive", {"length": -1}),
                                 ("symmetric is not supported with up_to_first", {"end_condition": "up_to_first", "symmetric": True}),
                                 ("symmetric is not supported with two_lengths",
                                  {"end_condition": "two_lengths", "second_length": 2, "symmetric": True}),
                                 ("two_lengths requires a positive second_length", {"end_condition": "two_lengths"}),
                                 ("second_length is only valid for two_lengths", {"second_length": 3}),
                                 ("target_selection is only valid for up_to_face", {"target_selection": level}),
                                 ("up_to_face requires target_selection", {"end_condition": "up_to_face"}),
                                 ("Unknown end condition", {"end_condition": "through_all"}),
                                 ("Unknown end condition", {"end_condition": "sideways"})]:
            await reject("partdesign_pad", upto, message, **{"sketch_name": "UpToProfile", "length": 1, **options})
        edge_target = (await select("UpToBasePad", "edge", geometry_type="line", position=[0, -10, 20]))["selection"]
        await reject("partdesign_pad", upto, "must be a face", sketch_name="UpToProfile", length=1,
                     end_condition="up_to_face", target_selection=edge_target)
        await reject("partdesign_pad", upto, "must belong to a PartDesign Body", sketch_name="LooseProfile", length=1)
        await reject("partdesign_pad", upto, "must be a Sketcher sketch", sketch_name="UpToBasePad", length=1)
        await invoke("sketch_add_line", doc_name=doc, sketch_name="LooseProfile", x1=5, y1=5, x2=6, y2=5)
        await reject("partdesign_pad", datum_pad, "Document changed", sketch_name="UpToDatumProfile", length=1,
                     end_condition="up_to_face", target_selection=level)

        # N10 Pocket: base 20x20x20, 4x4 profile; floors/ceilings via planar subelements.
        pockets = [("dimension", 20, {"length": 5}, 7920, [(15, 1)]),
                   ("reversed", 0, {"length": 5, "reversed": True}, 7920, [(5, -1)]),
                   ("symmetric", 10, {"length": 6, "symmetric": True}, 7904, [(7, 1), (13, -1)]),
                   ("two_lengths", 10, {"length": 3, "end_condition": "two_lengths", "second_length": 2}, 7920,
                    [(7, 1), (12, -1)]),
                   ("through_all", 20, {"length": 1, "through_all": True}, 7680, []),
                   ("through_all_condition", 20, {"length": 1, "end_condition": "through_all"}, 7680, []),
                   ("through_all_symmetric", 10, {"length": 1, "end_condition": "through_all", "symmetric": True}, 7680, []),
                   ("through_all_reversed", 0, {"length": 1, "end_condition": "through_all", "reversed": True}, 7680, [])]
        for index, (variant, offset, options, expected, faces) in enumerate(pockets):
            body = await new_body(f"Pocket{index}")
            await base_block(body)
            await rect(f"PocketProfile{index}", body, -2, -2, 2, 2, offset=offset)
            result, _ = await feature("partdesign_pocket", body, expected, sketch_name=f"PocketProfile{index}",
                                      name=f"Pocket_{variant}", **options)
            for height, direction in faces:
                found = await select(result["name"], "face", geometry_type="plane", normal=[0, 0, direction],
                                     position=[0, 0, height])
                assert abs(found["area"] - 16) <= 1e-6, found
            if not faces:
                assert await count(result["name"], "face", geometry_type="plane", area=span(16)) == 0
        bridge = await new_body("PocketBridge")
        await base_block(bridge)
        await rect("BridgeCavity", bridge, -11, -11, 6, 11, offset=10)
        await feature("partdesign_pocket", bridge, 4800, sketch_name="BridgeCavity", length=10, symmetric=True,
                      name="BridgeCavityPocket")
        await rect("BridgeHole", bridge, -4, -2, 0, 2, offset=20)
        await feature("partdesign_pocket", bridge, 4720, sketch_name="BridgeHole", length=1,
                      end_condition="up_to_first", name="BridgeUpToFirst")
        await invoke("undo", doc_name=doc)
        await feature("partdesign_pocket", bridge, 4640, sketch_name="BridgeHole", length=1, through_all=True,
                      name="BridgeThroughAll")
        await invoke("undo", doc_name=doc)
        face_body = await new_body("PocketToDatum")
        await base_block(face_body)
        await mutate("partdesign_datum", face_body, body_name=face_body, kind="plane", name="PocketFloor", z=12)
        await rect("PocketToDatumProfile", face_body, -2, -2, 2, 2, offset=20)
        floor = (await select("PocketFloor", "face"))["selection"]
        result, _ = await feature("partdesign_pocket", face_body, 8000 - 16 * 8, sketch_name="PocketToDatumProfile",
                                  length=1, end_condition="up_to_face", target_selection=floor, name="PocketToFace")
        assert abs((await select(result["name"], "face", geometry_type="plane", normal=[0, 0, 1],
                                 position=[0, 0, 12]))["area"] - 16) <= 1e-6
        empty = await new_body("PocketEmpty")
        await rect("PocketEmptyProfile", empty, -2, -2, 2, 2)
        await reject("partdesign_pocket", empty, "requires an existing solid", sketch_name="PocketEmptyProfile", length=5)
        for message, options in [("conflicts with end_condition", {"through_all": True, "end_condition": "dimension"}),
                                 ("conflicts with end_condition", {"through_all": True, "end_condition": "up_to_first"}),
                                 ("second_length is only valid for two_lengths", {"second_length": 2}),
                                 ("symmetric is not supported with up_to_first",
                                  {"end_condition": "up_to_first", "symmetric": True}),
                                 ("Extrusion length must be positive", {"length": 0})]:
            await reject("partdesign_pocket", bridge, message, **{"sketch_name": "BridgeHole", "length": 1, **options})

        # N11 Revolution: XZ profile x 5..10, z -4..0 (A=20, centroid radius 7.5); sketch V axis is global -Z.
        revolutions = [("full", {}, 300 * pi, (0, 0)),
                       ("partial", {"angle": 90}, 75 * pi, sector(10, 5, 90, -45)),
                       ("reversed", {"angle": 90, "reversed": True}, 75 * pi, sector(10, 5, 90, 45)),
                       ("symmetric", {"angle": 90, "symmetric": True}, 75 * pi, sector(10, 5, 90, 0)),
                       ("second_angle", {"angle": 90, "second_angle": 45}, 112.5 * pi, sector(10, 5, 135, -22.5)),
                       ("two_halves", {"angle": 180, "second_angle": 180}, 300 * pi, (0, 0)),
                       ("symmetric_full", {"angle": 360, "symmetric": True}, 300 * pi, (0, 0))]
        for index, (variant, options, expected, center) in enumerate(revolutions):
            body = await new_body(f"Rev{index}")
            await rect(f"RevProfile{index}", body, 5, 0, 10, 4, plane="XZ")
            _, shape = await feature("partdesign_revolution", body, expected, sketch_name=f"RevProfile{index}",
                                     name=f"Rev_{variant}", **options)
            near(com(shape), [center[0], center[1], -2])
        horizontal = await new_body("RevH")
        await rect("RevHProfile", horizontal, 0, 5, 4, 10, plane="XZ")
        _, shape = await feature("partdesign_revolution", horizontal, 300 * pi, sketch_name="RevHProfile", axis="H",
                                 name="Rev_H")
        near(com(shape), [2, 0, 0])
        partial_body = "Rev1"
        outer = (await select("Rev_partial", "face", geometry_type="cylinder", radius=span(10)))["selection"]
        await mutate("partdesign_datum", partial_body, body_name=partial_body, kind="axis", name="PartialAxis",
                     support_selection=outer)
        edge = await select("PartialAxis", "edge")
        parallel(edge["axis"], [0, 0, 1])
        on_line(edge["position"], [0, 0, 0], [0, 0, 1])
        datum_rev = await new_body("RevDatum")
        await mutate("partdesign_datum", datum_rev, body_name=datum_rev, kind="axis", name="RevAxis", x=20)
        await mutate("partdesign_datum", datum_rev, body_name=datum_rev, kind="axis", name="RevAxisY", rotation_x=90)
        await rect("RevDatumProfile", datum_rev, 25, 0, 30, 4, plane="XZ")
        _, shape = await feature("partdesign_revolution", datum_rev, 150 * pi, sketch_name="RevDatumProfile",
                                 axis_name="RevAxis", angle=180, name="Rev_datum")
        offset = sector(10, 5, 180, 90)
        near(com(shape), [20 + offset[0], offset[1], -2])
        await invoke("undo", doc_name=doc)
        foreign = await new_body("RevForeign")
        await mutate("partdesign_datum", foreign, body_name=foreign, kind="axis", name="ForeignAxis", x=20)
        for message, options in [("degenerate tool shape", {"axis": "N"}),
                                 ("Rotation angle must be in (0, 360]", {"angle": 0}),
                                 ("Rotation angle must be in (0, 360]", {"angle": 361}),
                                 ("Second rotation angle must be in (0, 360]", {"angle": 90, "second_angle": 0}),
                                 ("mutually exclusive", {"angle": 90, "second_angle": 10, "symmetric": True}),
                                 ("must not exceed 360", {"angle": 270, "second_angle": 180}),
                                 ("Rotation axis must be V, H, or N", {"axis": "Q"}),
                                 ("not found", {"axis_name": "MissingAxis"}),
                                 ("is not a datum axis", {"axis_name": "RevDatumProfile"}),
                                 ("must belong to Body", {"axis_name": "ForeignAxis"}),
                                 ("must not be perpendicular", {"axis_name": "RevAxisY", "angle": 90})]:
            await reject("partdesign_revolution", datum_rev, message, **{"sketch_name": "RevDatumProfile", **options})
        await rect("RevCrossing", datum_rev, -3, 0, 5, 4, plane="XZ")
        await reject("partdesign_revolution", datum_rev, "intersects the sketch", sketch_name="RevCrossing")
        await reject("partdesign_revolution", datum_rev, "must belong to a PartDesign Body", sketch_name="LooseProfile")

        # N11 Groove: base cylinder r=12, h=10 (V0=1440*pi, centroid z=5); XZ profile x 8..12, z 4..6 (A=8, rc=10).
        def groove_center(removed, xy):
            remaining = 1440 * pi - removed
            return [-removed * xy[0] / remaining, -removed * xy[1] / remaining, 5]

        grooves = [("full", {}, 160 * pi, (0, 0)),
                   ("partial", {"angle": 90}, 40 * pi, sector(12, 8, 90, -45)),
                   ("reversed", {"angle": 90, "reversed": True}, 40 * pi, sector(12, 8, 90, 45)),
                   ("symmetric", {"angle": 90, "symmetric": True}, 40 * pi, sector(12, 8, 90, 0)),
                   ("second_angle", {"angle": 90, "second_angle": 45}, 60 * pi, sector(12, 8, 135, -22.5))]
        for index, (variant, options, removed, center) in enumerate(grooves):
            body = await new_body(f"Groove{index}")
            await circle(f"GrooveBase{index}", body, 0, 0, 12)
            await feature("partdesign_pad", body, 1440 * pi, sketch_name=f"GrooveBase{index}", length=10)
            await rect(f"GrooveProfile{index}", body, 8, -6, 12, -4, plane="XZ")
            _, shape = await feature("partdesign_groove", body, 1440 * pi - removed, sketch_name=f"GrooveProfile{index}",
                                     name=f"Groove_{variant}", **options)
            near(com(shape), groove_center(removed, center))
        groove_h = await new_body("GrooveH")
        await circle("GrooveHBase", groove_h, 0, 0, 12)
        await feature("partdesign_pad", groove_h, 1440 * pi, sketch_name="GrooveHBase", length=10)
        await rect("GrooveHProfile", groove_h, -2, -6, 2, -4, plane="XZ")
        _, shape = await feature("partdesign_groove", groove_h, 1400 * pi, sketch_name="GrooveHProfile", axis="H",
                                 name="Groove_H")
        half_ring = 4 * (6 ** 3 - 4 ** 3) / (3 * pi * (6 ** 2 - 4 ** 2))
        near(com(shape), [0, 0, (1440 * pi * 5 - 40 * pi * half_ring) / (1400 * pi)])
        await mutate("partdesign_datum", groove_h, body_name=groove_h, kind="axis", name="GrooveAxis")
        await rect("GrooveDatumProfile", groove_h, 8, -9, 12, -7, plane="XZ")
        _, shape = await feature("partdesign_groove", groove_h, 1400 * pi - 80 * pi, sketch_name="GrooveDatumProfile",
                                 axis_name="GrooveAxis", angle=180, name="Groove_datum")
        await invoke("undo", doc_name=doc)
        groove_empty = await new_body("GrooveEmpty")
        await rect("GrooveEmptyProfile", groove_empty, 8, -6, 12, -4, plane="XZ")
        await reject("partdesign_groove", groove_empty, "requires an existing solid", sketch_name="GrooveEmptyProfile")
        await reject("partdesign_groove", groove_h, "produced invalid BRep geometry", sketch_name="GrooveDatumProfile", axis="N")
        await reject("partdesign_groove", groove_h, "must not exceed 360", sketch_name="GrooveDatumProfile",
                     angle=200, second_angle=200)
        await reject("partdesign_groove", groove_h, "must belong to Body", sketch_name="GrooveDatumProfile",
                     axis_name="ForeignAxis")

        # N11 Loft: squares 10 (z=0), 6 (z=12), 10 (z=24); frustum V = h/3 (A1 + A2 + sqrt(A1 A2)).
        frustum = 12 / 3 * (100 + 36 + 60)
        loft = await new_body("Loft")
        await rect("LoftLow", loft, -5, -5, 5, 5)
        await rect("LoftMid", loft, -3, -3, 3, 3, offset=12)
        await rect("LoftHigh", loft, -5, -5, 5, 5, offset=24)
        _, shape = await feature("partdesign_loft", loft, frustum, sketch_names=["LoftLow", "LoftMid"], name="Loft_two")
        near(bbox(shape), [-5, -5, 0, 5, 5, 12])
        await invoke("undo", doc_name=doc)
        _, shape = await feature("partdesign_loft", loft, 2 * frustum, sketch_names=["LoftLow", "LoftMid", "LoftHigh"],
                                 ruled=True, name="Loft_ruled")
        near(bbox(shape), [-5, -5, 0, 5, 5, 24])
        await invoke("undo", doc_name=doc)
        result, after = await mutate("partdesign_loft", loft, sketch_names=["LoftLow", "LoftMid", "LoftHigh"],
                                     name="Loft_smooth")
        assert 24 * 36 < after["shape"]["volume"] < 2 * frustum - 1, after
        for height, direction in ((0, -1), (24, 1)):
            assert abs((await select(result["name"], "face", geometry_type="plane", normal=[0, 0, direction],
                                     position=[0, 0, height]))["area"] - 100) <= 1e-6
        await invoke("undo", doc_name=doc)
        ring = await new_body("LoftRing")
        ring_profiles = []
        for index, angle in enumerate((0, 90, 180, 270)):
            await mutate("partdesign_datum", ring, body_name=ring, kind="plane", name=f"RingPlane{index}",
                         rotation_x=90, rotation_z=angle)
            await invoke("create_sketch", doc_name=doc, name=f"RingProfile{index}", body_name=ring)
            await invoke("sketch_set_attachment", doc_name=doc, sketch_name=f"RingProfile{index}",
                         support_name=f"RingPlane{index}")
            await invoke("sketch_add_rectangle", doc_name=doc, sketch_name=f"RingProfile{index}", x1=5, y1=0, x2=10, y2=4)
            ring_profiles.append(f"RingProfile{index}")
        await feature("partdesign_loft", ring, 3 * 4 * 75 / 2, sketch_names=ring_profiles, ruled=True, name="Ring_open")
        await invoke("undo", doc_name=doc)
        result, after = await mutate("partdesign_loft", ring, sketch_names=ring_profiles, closed=True, name="Ring_closed")
        assert 600 < after["shape"]["volume"] < 1200, after
        for normal in ([0, 1, 0], [0, -1, 0], [1, 0, 0], [-1, 0, 0]):
            assert await count(result["name"], "face", geometry_type="plane", normal=normal) == 0, normal
        await invoke("undo", doc_name=doc)
        for message, options in [("must be solid", {"sketch_names": ["LoftLow", "LoftMid"], "solid": False}),
                                 ("at least two profiles", {"sketch_names": ["LoftLow"]}),
                                 ("distinct", {"sketch_names": ["LoftLow", "LoftLow"]}),
                                 ("at least three profiles", {"sketch_names": ["LoftLow", "LoftMid"], "closed": True}),
                                 ("closed ruled", {"sketch_names": ring_profiles, "closed": True, "ruled": True}),
                                 ("not found", {"sketch_names": ["LoftLow", "LoftMissing"]}),
                                 ("must belong to a PartDesign Body", {"sketch_names": ["LoftLow", "LooseProfile"]})]:
            await reject("partdesign_loft", loft, message, **options)
        sub_loft = await new_body("SubLoft")
        await base_block(sub_loft)
        await rect("SubLoftLow", sub_loft, -5, -5, 5, 5)
        await rect("SubLoftMid", sub_loft, -3, -3, 3, 3, offset=12)
        await rect("SubLoftHigh", sub_loft, -5, -5, 5, 5, offset=24)
        await feature("partdesign_subtractive_loft", sub_loft, 8000 - frustum, sketch_names=["SubLoftLow", "SubLoftMid"],
                      name="SubLoft_two")
        await invoke("undo", doc_name=doc)
        side = 6 + 4 * 8 / 12
        await feature("partdesign_subtractive_loft", sub_loft, 8000 - frustum - 8 / 3 * (36 + side ** 2 + 6 * side),
                      sketch_names=["SubLoftLow", "SubLoftMid", "SubLoftHigh"], ruled=True, name="SubLoft_ruled")
        await invoke("undo", doc_name=doc)
        await reject("partdesign_subtractive_loft", sub_loft, "must be solid", sketch_names=["SubLoftLow", "SubLoftMid"],
                     solid=False)
        await reject("partdesign_subtractive_loft", sub_loft, "distinct", sketch_names=["SubLoftLow", "SubLoftLow"])
        await reject("partdesign_subtractive_loft", loft, "requires an existing solid", sketch_names=["LoftLow", "LoftMid"])

        # N11 Sweep/Pipe: XZ spine (local y = -Z); circle r=3 or square 4x4 profile at the origin.
        async def pipe_body(name, profile, spine, base=False):
            body = await new_body(name)
            if base:
                await rect(f"{name}Base", body, -10, -10, 30, 10, offset=-5)
                await feature("partdesign_pad", body, 28000, sketch_name=f"{name}Base", length=35)
            if profile == "circle":
                await circle(f"{name}Profile", body, 0, 0, 3)
            else:
                await rect(f"{name}Profile", body, -2, -2, 2, 2)
            await invoke("create_sketch", doc_name=doc, name=f"{name}Spine", body_name=body, plane="XZ")
            if spine == "arc":
                await invoke("sketch_add_arc", doc_name=doc, sketch_name=f"{name}Spine", cx=20, cy=0, radius=20,
                             start_angle=pi, end_angle=1.5 * pi)
            else:
                await invoke("sketch_add_line", doc_name=doc, sketch_name=f"{name}Spine", x1=0, y1=0, x2=0, y2=-20)
            if spine == "corner":
                await invoke("sketch_add_line", doc_name=doc, sketch_name=f"{name}Spine", x1=0, y1=-20, x2=20, y2=-20)
                await invoke("sketch_constrain_coincident", doc_name=doc, sketch_name=f"{name}Spine",
                             geo_idx1=0, point_idx1=2, geo_idx2=1, point_idx2=1)
            return body, f"{name}Profile", f"{name}Spine"

        tube = 20 + 9 / 80
        arc_center = [20 - tube * math.sin(pi / 4) / (pi / 4) * math.sqrt(0.5), 0,
                      tube * math.sin(pi / 4) / (pi / 4) * math.sqrt(0.5)]
        for orientation in ("standard", "frenet"):
            body, profile, spine = await pipe_body(f"SweepLine{orientation}", "circle", "line")
            _, shape = await feature("partdesign_sweep", body, 180 * pi, sketch_name=profile, spine_name=spine,
                                     orientation=orientation, name=f"Sweep_line_{orientation}")
            near(com(shape), [0, 0, 10])
            body, profile, spine = await pipe_body(f"SweepArc{orientation}", "circle", "arc")
            _, shape = await feature("partdesign_sweep", body, 90 * pi * pi, sketch_name=profile, spine_name=spine,
                                     orientation=orientation, name=f"Sweep_arc_{orientation}")
            near(com(shape), arc_center)
        corner_volumes = {"right": 640, "round": 624 + 4 * pi}
        for transition, expected in corner_volumes.items():
            body, profile, spine = await pipe_body(f"SweepCorner{transition}", "square", "corner")
            _, shape = await feature("partdesign_sweep", body, expected, sketch_name=profile, spine_name=spine,
                                     transition=transition, name=f"Sweep_{transition}")
            near(bbox(shape), [-2, -2, 0, 20, 2, 22])
        body, profile, spine = await pipe_body("SweepPath", "square", "corner")
        await reject("partdesign_sweep", body, "tangent-continuous", sketch_name=profile, spine_name=spine)
        first_edge = (await select(spine, "edge", geometry_type="line", axis=[0, 0, 1]))["selection"]
        _, shape = await feature("partdesign_sweep", body, 320, sketch_name=profile, spine_name=spine,
                                 path_edges=[first_edge], name="Sweep_path_selection")
        near(bbox(shape), [-2, -2, 0, 2, 2, 20])
        await invoke("undo", doc_name=doc)
        edges = [item["selection"] for item in (await invoke("list_subelements", doc_name=doc, obj_name=spine,
                                                             kind="edge"))["items"]]
        await feature("partdesign_sweep", body, 640, sketch_name=profile, spine_name=spine, transition="right",
                      path_edges=[item["subelement"] for item in edges], name="Sweep_path_names")
        await invoke("undo", doc_name=doc)

        async def fresh_edges():
            items = (await invoke("list_subelements", doc_name=doc, obj_name=spine, kind="edge"))["items"]
            first = [item["selection"] for item in items if abs(abs(item["axis"][2]) - 1) <= 1e-9][0]
            second = [item["selection"] for item in items if item["selection"]["subelement"] != first["subelement"]][0]
            return first, second

        selection_cases = [("must not contain duplicates", lambda first, second, foreign: [first, first]),
                           ("different object", lambda first, second, foreign: [foreign]),
                           ("produced invalid BRep geometry", lambda first, second, foreign: [second])]
        for message, build in selection_cases:
            first, second = await fresh_edges()
            foreign = (await select(profile, "edge", geometry_type="line", position=[0, -2, 0]))["selection"]
            await reject("partdesign_sweep", body, message, sketch_name=profile, spine_name=spine, transition="right",
                         path_edges=build(first, second, foreign))
        for message, options in [("is not an edge of", {"path_edges": ["Edge9"], "transition": "right"}),
                                 ("is not an edge of", {"path_edges": ["Face1"], "transition": "right"}),
                                 ("Unsupported Mode", {"orientation": "fixed", "transition": "right"}),
                                 ("Unsupported Transition", {"transition": "miter"}),
                                 ("must be solid", {"solid": False, "transition": "right"})]:
            await reject("partdesign_sweep", body, message, **{"sketch_name": profile, "spine_name": spine, **options})
        await reject("partdesign_sweep", body, "must differ", sketch_name=profile, spine_name=profile)
        await reject("partdesign_sweep", body, "must belong to a PartDesign Body", sketch_name="LooseProfile",
                     spine_name=spine, transition="right")
        first, _ = await fresh_edges()
        await invoke("sketch_add_line", doc_name=doc, sketch_name="LooseProfile", x1=7, y1=7, x2=8, y2=7)
        await reject("partdesign_sweep", body, "Document changed", sketch_name=profile, spine_name=spine,
                     path_edges=[first], transition="right")

        body, profile, spine = await pipe_body("CutLine", "circle", "line", base=True)
        await feature("partdesign_subtractive_pipe", body, 28000 - 180 * pi, sketch_name=profile, spine_name=spine,
                      name="Cut_line")
        await invoke("undo", doc_name=doc)
        await feature("partdesign_subtractive_pipe", body, 28000 - 180 * pi, sketch_name=profile, spine_name=spine,
                      orientation="frenet", name="Cut_line_frenet")
        await invoke("undo", doc_name=doc)
        body, profile, spine = await pipe_body("CutArc", "circle", "arc", base=True)
        await feature("partdesign_subtractive_pipe", body, 28000 - 90 * pi * pi, sketch_name=profile, spine_name=spine,
                      orientation="frenet", name="Cut_arc")
        body, profile, spine = await pipe_body("CutCorner", "square", "corner", base=True)
        for transition, expected in corner_volumes.items():
            await feature("partdesign_subtractive_pipe", body, 28000 - expected, sketch_name=profile, spine_name=spine,
                          transition=transition, name=f"Cut_{transition}")
            await invoke("undo", doc_name=doc)
        await reject("partdesign_subtractive_pipe", body, "tangent-continuous", sketch_name=profile, spine_name=spine)
        await reject("partdesign_subtractive_pipe", body, "must not contain duplicates", sketch_name=profile,
                     spine_name=spine, path_edges=["Edge1", "Edge1"], transition="right")
        empty_body, empty_profile, empty_spine = await pipe_body("CutEmpty", "circle", "line")
        await reject("partdesign_subtractive_pipe", empty_body, "requires an existing solid", sketch_name=empty_profile,
                     spine_name=empty_spine)

        # File cycle: every audited body survives save/close/reopen; datums stay attached; second edit + resave.
        bodies = sorted(item["name"] for item in await invoke("list_objects", doc_name=doc)
                        if item["type"] == "PartDesign::Body")
        saved = {body: await snap(body) for body in bodies}
        datums = {name: await select(name, kind)
                  for name, kind in (("BoreAxis", "edge"), ("EdgeAxis", "edge"), ("CornerPoint", "vertex"),
                                     ("TopPlane", "face"), ("PartialAxis", "edge"))}
        path = str(directory / f"{doc}.FCStd")
        await invoke("save_document_safe", doc_name=doc, path=path)
        await invoke("close_document_safe", doc_name=doc)
        documents.remove(doc)
        state["doc"] = doc = (await invoke("open_document", path=path))["name"]
        documents.append(doc)
        for body in bodies:
            same(await snap(body), saved[body], body)
        for name, kind in (("BoreAxis", "edge"), ("EdgeAxis", "edge"), ("CornerPoint", "vertex"), ("TopPlane", "face"),
                           ("PartialAxis", "edge")):
            reopened = await select(name, kind)
            for key in (("normal",) if kind == "face" else ("position", "axis")):
                if datums[name][key] is not None:
                    near(reopened[key], datums[name][key])
        await rect("ReopenCut", "Pad0", 1, 1, 3, 3, offset=10)
        _, shape = await feature("partdesign_pocket", "Pad0", 500 - 40, sketch_name="ReopenCut", through_all=True,
                                 length=1, name="ReopenThrough")
        near(bbox(shape), [0, 0, 0, 10, 5, 10])
        for normal in ([1, 0, 0], [-1, 0, 0], [0, 1, 0], [0, -1, 0]):
            assert await count("ReopenThrough", "face", geometry_type="plane", normal=normal, area=span(20)) == 1, normal
        await invoke("save_document_safe", doc_name=doc, path=path, overwrite=True)
        failures = sum(1 for entry in transcript if entry.get("is_error"))
        return {"calls": len(transcript), "negative_checks": failures, "fcstd": path, "bodies": len(bodies)}
    finally:
        for document in reversed(documents):
            await invoke("close_document_safe", doc_name=document, discard_changes=True)
        (directory / "mcp-transcript.json").write_text(json.dumps(transcript, indent=2), encoding="utf-8")
        assert not json.loads((await call("get_status")).content[0].text)["documents"]


async def check_stage12b_partdesign_b(session, call, directory):
    """V audit of PartDesign holes, dress-ups, patterns, MultiTransform and edit_feature through MCP only."""
    transcript = []
    documents = []
    state = {}
    pi = math.pi
    tan59 = math.tan(math.radians(59))

    def decode(response):
        if response.structuredContent and "contract_version" in response.structuredContent:
            return response.structuredContent
        return json.loads(response.content[0].text)

    async def invoke(tool, **arguments):
        result = decode(await call(tool, **arguments))
        transcript.append({"tool": tool, "arguments": arguments, "result": result})
        if isinstance(result, dict) and "contract_version" in result:
            assert result["status"] == "success", result
            return result["data"]
        return result

    def same(actual, expected, path="$"):
        if isinstance(expected, float) or isinstance(actual, float):
            assert abs(actual - expected) <= 1e-7, (path, actual, expected)
        elif isinstance(expected, dict):
            assert isinstance(actual, dict) and set(actual) == set(expected), (path, actual, expected)
            for key in expected:
                same(actual[key], expected[key], f"{path}.{key}")
        elif isinstance(expected, list):
            assert isinstance(actual, list) and len(actual) == len(expected), (path, actual, expected)
            for index, (left, right) in enumerate(zip(actual, expected)):
                same(left, right, f"{path}[{index}]")
        else:
            assert actual == expected, (path, actual, expected)

    def near(actual, expected, tolerance=1e-6):
        assert len(actual) == len(expected) and all(abs(a - e) <= tolerance for a, e in zip(actual, expected)), (
            actual, expected)

    def volume_ok(actual, expected):
        assert abs(actual - expected) <= max(1e-6, 1e-6 * abs(expected)), (actual, expected)

    def parallel(actual, expected):
        length = math.sqrt(sum(value * value for value in expected))
        assert abs(abs(sum(a * e for a, e in zip(actual, expected))) / length - 1) <= 1e-9, (actual, expected)

    async def names():
        return sorted(item["name"] for item in await invoke("list_objects", doc_name=state["doc"]))

    async def tip(body):
        value = (await invoke("get_properties", doc_name=state["doc"], obj_name=body, properties=["Tip"]))["properties"][0]["value"]
        return value["object"] if value else None

    async def snap(body):
        objects = await names()
        snapshot = {"objects": objects, "tip": await tip(body) if body in objects else None}
        if snapshot["tip"]:
            measured = await invoke("measure", doc_name=state["doc"], obj_name=snapshot["tip"])
            snapshot["shape"] = {key: measured[key] for key in ("volume", "area", "bounding_box", "center_of_mass")}
            snapshot["tip_properties"] = (await invoke("get_properties", doc_name=state["doc"],
                                                       obj_name=snapshot["tip"]))["properties"]
        return snapshot

    async def measure(obj):
        return await invoke("measure", doc_name=state["doc"], obj_name=obj)

    async def reject(tool, body, expected, **arguments):
        before = await snap(body)
        response = await session.call_tool(tool, {"doc_name": state["doc"], **arguments})
        text = " ".join(getattr(content, "text", "") for content in response.content)
        transcript.append({"tool": tool, "arguments": arguments, "is_error": response.isError, "result": text})
        assert response.isError, (tool, arguments, text)
        assert expected in text, (tool, expected, text)
        same(await snap(body), before)
        return text

    async def mutate(tool, body, **arguments):
        before = await snap(body)
        result = await invoke(tool, doc_name=state["doc"], **arguments)
        after = await snap(body)
        await invoke("undo", doc_name=state["doc"])
        same(await snap(body), before)
        await invoke("redo", doc_name=state["doc"])
        same(await snap(body), after)
        return result, after

    async def feature(tool, body, expected_volume, **arguments):
        result, after = await mutate(tool, body, **arguments)
        assert after["tip"] == result["name"], (after, result)
        volume_ok(after["shape"]["volume"], expected_volume)
        volume_ok(result["volume"], expected_volume)
        return result, after["shape"]

    async def edit(body, feature_name, expected_volume, **arguments):
        before_tip = await tip(body)
        result, after = await mutate("partdesign_edit_feature", body, feature_name=feature_name, **arguments)
        assert result["tip"] == before_tip == after["tip"], (result, before_tip, after)
        volume_ok(after["shape"]["volume"], expected_volume)
        return result, after["shape"]

    async def undo():
        await invoke("undo", doc_name=state["doc"])

    async def new_body(name):
        result, _ = await mutate("partdesign_body", name, name=name)
        return result["name"]

    async def rect(name, body, x1, y1, x2, y2, plane="XY", offset=0):
        await invoke("create_sketch", doc_name=state["doc"], name=name, body_name=body, plane=plane, offset=offset)
        await invoke("sketch_add_rectangle", doc_name=state["doc"], sketch_name=name, x1=x1, y1=y1, x2=x2, y2=y2)
        return name

    async def circle(name, body, cx, cy, radius, plane="XY", offset=0):
        await invoke("create_sketch", doc_name=state["doc"], name=name, body_name=body, plane=plane, offset=offset)
        await invoke("sketch_add_circle", doc_name=state["doc"], sketch_name=name, cx=cx, cy=cy, radius=radius)
        return name

    async def circles(name, body, centers, radius, offset=0):
        await invoke("create_sketch", doc_name=state["doc"], name=name, body_name=body, plane="XY", offset=offset)
        for cx, cy in centers:
            await invoke("sketch_add_circle", doc_name=state["doc"], sketch_name=name, cx=cx, cy=cy, radius=radius)
        return name

    async def select(obj, kind, **filters):
        return await invoke("select_subelement", doc_name=state["doc"], obj_name=obj, kind=kind, filters=filters)

    async def listing(obj, kind, **filters):
        return (await invoke("list_subelements", doc_name=state["doc"], obj_name=obj, kind=kind, filters=filters))["items"]

    async def count(obj, kind, **filters):
        return (await invoke("list_subelements", doc_name=state["doc"], obj_name=obj, kind=kind, filters=filters))["total"]

    async def block(body, name, x1, y1, x2, y2, height, offset=0, symmetric=False):
        sketch = await rect(f"{name}Sketch", body, x1, y1, x2, y2, offset=offset)
        volume = (x2 - x1) * (y2 - y1) * height
        await feature("partdesign_pad", body, volume, sketch_name=sketch, length=height, symmetric=symmetric,
                      name=name)
        return name

    def span(value):
        return {"min": float(value) - 1e-6, "max": float(value) + 1e-6}

    def bbox(shape):
        box = shape["bounding_box"]
        return [box["min"][axis] for axis in "xyz"] + [box["max"][axis] for axis in "xyz"]

    def com(shape):
        return [shape["center_of_mass"][axis] for axis in "xyz"]

    def mass_com(base_volume, base_com, parts):
        """Center of mass after removing parts [(volume, (x, y, z))] from a body of known volume and center."""
        volume = base_volume - sum(part[0] for part in parts)
        return [(base_volume * base_com[axis] - sum(part[0] * part[1][axis] for part in parts)) / volume
                for axis in range(3)]

    def frustum(big, small, depth):
        volume = pi * depth / 3 * (big ** 2 + big * small + small ** 2)
        centroid = depth * (big ** 2 + 2 * big * small + 3 * small ** 2) / (4 * (big ** 2 + big * small + small ** 2))
        return volume, centroid

    def drill_parts(top, x, y, radius, length, cut=None, through=False):
        """Removed volumes of a hole at (x, y) from height `top`: cylinder, optional cut and the 118 degree tip."""
        parts = []
        if cut and cut["type"] == "counterbore":
            volume = pi * cut["radius"] ** 2 * cut["depth"]
            parts.append((volume, (x, y, top - cut["depth"] / 2)))
            top_depth = cut["depth"]
        elif cut:
            volume, centroid = frustum(cut["radius"], radius, cut["depth"])
            parts.append((volume, (x, y, top - centroid)))
            top_depth = cut["depth"]
        else:
            top_depth = 0.0
        shaft = length - top_depth
        parts.append((pi * radius ** 2 * shaft, (x, y, top - top_depth - shaft / 2)))
        if not through:
            tip_height = radius / tan59
            parts.append((pi * radius ** 2 * tip_height / 3, (x, y, top - length - tip_height / 4)))
        return parts

    assert not json.loads((await call("get_status")).content[0].text)["documents"], "Stage 12b needs an empty instance"
    try:
        state["doc"] = doc = (await invoke("create_document", name="MCP_Stage12b_PartDesignB"))["name"]
        documents.append(doc)
        other = (await invoke("create_document", name="MCP_Stage12b_PartDesignB_Other"))["name"]
        documents.append(other)
        await invoke("part_box", doc_name=other, name="ForeignBox", length=5, width=5, height=5)
        state["doc"] = doc

        # N12 Hole: simple, counterbore, countersink, blind and through-all, threads, several centers.
        body = await new_body("HoleBody")
        await block(body, "HolePad", -20, -20, 20, 20, 20)
        base_volume, base_com = 32000.0, (0.0, 0.0, 10.0)
        await circle("HoleOne", body, 0, 0, 2, offset=20)

        async def hole_case(label, parts, **arguments):
            removed = sum(part[0] for part in parts)
            result, shape = await feature("partdesign_hole", body, base_volume - removed,
                                          sketch_name="HoleOne", name=f"Hole_{label}", **arguments)
            near(bbox(shape), [-20, -20, 0, 20, 20, 20])
            near(com(shape), mass_com(base_volume, base_com, parts))
            await undo()
            return result

        result = await hole_case("simple", drill_parts(20, 0, 0, 2, 10), diameter=4, depth=10)
        assert (result["diameter"], result["depth"], result["depth_type"], result["cut_type"]) == (
            4.0, 10.0, "Dimension", "simple"), result
        result = await hole_case("through", drill_parts(20, 0, 0, 2, 20, through=True), diameter=4, depth=10,
                                 through_all=True)
        assert result["depth_type"] == "ThroughAll", result
        cut = {"type": "counterbore", "radius": 4, "depth": 3}
        await hole_case("cbore", drill_parts(20, 0, 0, 2, 10, cut), diameter=4, depth=10, cut_type="counterbore",
                        cut_diameter=8, cut_depth=3)
        await hole_case("cbore_through", drill_parts(20, 0, 0, 2, 20, cut, through=True), diameter=4, depth=10,
                        through_all=True, cut_type="counterbore", cut_diameter=8, cut_depth=3)
        for angle in (60, 90, 120):
            depth = (4 - 2) / math.tan(math.radians(angle / 2))
            cut = {"type": "countersink", "radius": 4, "depth": depth}
            await hole_case(f"csink{angle}", drill_parts(20, 0, 0, 2, 10, cut), diameter=4, depth=10,
                            cut_type="countersink", cut_diameter=8, countersink_angle=angle)
        cut = {"type": "countersink", "radius": 4, "depth": 2.0}
        await hole_case("csink_through", drill_parts(20, 0, 0, 2, 20, cut, through=True), diameter=4, depth=10,
                        through_all=True, cut_type="countersink", cut_diameter=8, countersink_angle=90)

        # Threads: the requested drill diameter is honoured, size/pitch/diameter reported.
        threads = [("iso_m6", dict(thread_size="M6"), 5.0, ("ISOMetricProfile", "M6x1.0", 1.0, 6.0)),
                   ("iso_m6_explicit", dict(thread_size="M6x1.0"), 5.0, ("ISOMetricProfile", "M6x1.0", 1.0, 6.0)),
                   ("iso_m6_fine", dict(thread_size="M6", thread_pitch=0.75), 5.25,
                    ("ISOMetricFineProfile", "M6x0.75", 0.75, 6.0)),
                   ("iso_m8_fine_explicit", dict(thread_size="M8x1.0"), 7.0,
                    ("ISOMetricFineProfile", "M8x1.0", 1.0, 8.0)),
                   ("iso_m8_coarse_pitch", dict(thread_size="M8", thread_pitch=1.25), 6.8,
                    ("ISOMetricProfile", "M8x1.25", 1.25, 8.0)),
                   ("uts_quarter", dict(thread_type="UTS", thread_size="1/4"), 5.1,
                    ("UNC", "1/4", None, 6.35))]
        for label, options, diameter, (freecad_type, size, pitch, thread_diameter) in threads:
            result = await hole_case(label, drill_parts(20, 0, 0, diameter / 2, 10), diameter=diameter, depth=10,
                                     threaded=True, **options)
            thread = result["thread"]
            assert (thread["freecad_type"], thread["size"], thread["pitch"], thread["type"]) == (
                freecad_type, size, pitch, options.get("thread_type", "ISO")), result
            assert abs(thread["thread_diameter"] - thread_diameter) <= 1e-9 and result["diameter"] == diameter, result
        result = await hole_case("thread_through", drill_parts(20, 0, 0, 2.5, 20, through=True), diameter=5,
                                 depth=10, through_all=True, threaded=True, thread_size="M6")
        assert result["thread"]["size"] == "M6x1.0", result

        # Several hole centers in one sketch: circles or points.
        centers = [(-10, -10), (10, 0), (0, 12)]
        await circles("HoleThree", body, centers, 2, offset=20)
        parts = [part for x, y in centers for part in drill_parts(20, x, y, 2, 10)]
        result, shape = await feature("partdesign_hole", body, 32000 - sum(part[0] for part in parts),
                                      sketch_name="HoleThree", diameter=4, depth=10, name="Hole_three")
        near(com(shape), mass_com(32000.0, base_com, parts))
        await undo()
        await invoke("create_sketch", doc_name=doc, name="HolePoints", body_name=body, plane="XY", offset=20)
        for x, y in centers:
            await invoke("sketch_add_point", doc_name=doc, sketch_name="HolePoints", x=x, y=y)
        result, shape = await feature("partdesign_hole", body, 32000 - sum(part[0] for part in parts),
                                      sketch_name="HolePoints", diameter=4, depth=10, name="Hole_points")
        near(com(shape), mass_com(32000.0, base_com, parts))
        await undo()

        # Negative and boundary cases: every rejection leaves objects, Tip and shape unchanged.
        for expected, options in [
                ("greater than 0", dict(diameter=0, depth=10)),
                ("greater than 0", dict(diameter=-1, depth=10)),
                ("greater than 0", dict(diameter=4, depth=0)),
                ("greater than 0", dict(diameter=4, depth=-3)),
                ("requires cut_diameter greater than diameter",
                 dict(diameter=4, depth=10, cut_type="counterbore", cut_diameter=4, cut_depth=2)),
                ("requires cut_diameter greater than diameter",
                 dict(diameter=4, depth=10, cut_type="countersink", cut_diameter=3)),
                ("requires cut_diameter greater than diameter",
                 dict(diameter=4, depth=10, cut_type="counterbore", cut_depth=2)),
                ("Counterbore requires positive cut_depth",
                 dict(diameter=4, depth=10, cut_type="counterbore", cut_diameter=8)),
                ("greater than 0", dict(diameter=4, depth=10, cut_type="counterbore", cut_diameter=8, cut_depth=0)),
                ("greater than 0", dict(diameter=4, depth=10, cut_type="countersink", cut_diameter=8,
                                        countersink_angle=0)),
                ("less than 180", dict(diameter=4, depth=10, cut_type="countersink", cut_diameter=8,
                                       countersink_angle=180)),
                ("cut_type must be simple, counterbore, or countersink",
                 dict(diameter=4, depth=10, cut_type="slotted")),
                ("Unknown thread size 'M99'", dict(diameter=5, depth=10, threaded=True, thread_size="M99")),
                ("Unknown thread size 'M6' with pitch 0.5",
                 dict(diameter=5, depth=10, threaded=True, thread_size="M6", thread_pitch=0.5)),
                ("disagree", dict(diameter=5, depth=10, threaded=True, thread_size="M6x1.0", thread_pitch=0.75)),
                ("not supported for UTS", dict(diameter=5, depth=10, threaded=True, thread_type="UTS",
                                               thread_size="1/4", thread_pitch=1.0)),
                ("Unknown thread size", dict(diameter=5, depth=10, threaded=True, thread_type="UTS",
                                             thread_size="M6")),
                ("greater than 0", dict(diameter=5, depth=10, threaded=True, thread_size="M6", thread_pitch=0)),
                ("Input should be 'ISO' or 'UTS'", dict(diameter=5, depth=10, threaded=True, thread_type="BSP",
                                                        thread_size="1/4")),
                ("thread_size must be a nonempty string", dict(diameter=5, depth=10, threaded=True,
                                                               thread_size=" "))]:
            await reject("partdesign_hole", body, expected, sketch_name="HoleOne", **options)
        await reject("partdesign_hole", body, "must be a Sketcher sketch", sketch_name="HolePad", diameter=4,
                     depth=10)
        await reject("partdesign_hole", body, "is not in", sketch_name="NoSuchSketch", diameter=4, depth=10)
        await circle("HoleOutside", body, 60, 60, 2, offset=20)
        await reject("partdesign_hole", body, "had no effect", sketch_name="HoleOutside", diameter=4, depth=10)
        empty = await new_body("HoleEmpty")
        await circle("HoleNoBase", empty, 0, 0, 2)
        await reject("partdesign_hole", empty, "requires an existing solid", sketch_name="HoleNoBase",
                     diameter=4, depth=10)
        await reject("partdesign_hole", body, "must be a Sketcher sketch", sketch_name="HoleBody", diameter=4,
                     depth=10)

        body = await new_body("DressBody")
        base = await block(body, "DressPad", -10, -10, 10, 10, 20)
        V0, C0 = 8000.0, (0.0, 0.0, 10.0)
        await rect("DressScratch", body, 30, 30, 31, 31)
        foreign_edge = (await invoke("select_subelement", doc_name=other, obj_name="ForeignBox", kind="edge",
                                     filters={"position": [2.5, 0, 0]}))["selection"]

        async def vedge(x, y):
            return (await select(base, "edge", geometry_type="line", axis=[0, 0, 1], position=[x, y, 10]))["selection"]

        async def tedge(x, y):
            return (await select(base, "edge", geometry_type="line", position=[x, y, 20]))["selection"]

        async def dressup(tool, name, parts, **arguments):
            result, shape = await feature(tool, body, V0 - sum(part[0] for part in parts), base_name=base,
                                          name=name, **arguments)
            near(com(shape), mass_com(V0, C0, parts))
            return result, shape

        def fillet_removed(radius, length):
            inset = radius * (5 / 6 - pi / 4) / (1 - pi / 4)
            return (1 - pi / 4) * radius ** 2 * length, inset

        # Fillet: constant radius on one and several edges, Tip-only base, analytic volume and centroid.
        volume, inset = fillet_removed(2, 20)
        edge = await vedge(10, 10)
        result, shape = await dressup("partdesign_fillet", "Fillet_one", [(volume, (10 - inset, 10 - inset, 10))],
                                      edges=[edge], radius=2)
        near(bbox(shape), [-10, -10, 0, 10, 10, 20])
        assert await count(result["name"], "face", geometry_type="cylinder", radius=span(2),
                           area=span(pi * 2 * 20 / 2)) == 1
        await undo()
        edges = [await vedge(10, 10), await vedge(-10, -10)]
        await dressup("partdesign_fillet", "Fillet_opposite",
                      [(volume, (10 - inset, 10 - inset, 10)), (volume, (-10 + inset, -10 + inset, 10))],
                      edges=edges, radius=2)
        await undo()
        edges = [await vedge(10, 10), await vedge(-10, 10)]
        await dressup("partdesign_fillet", "Fillet_adjacent",
                      [(volume, (10 - inset, 10 - inset, 10)), (volume, (-10 + inset, 10 - inset, 10))],
                      edges=edges, radius=2)
        await undo()
        corners = [(10, 10), (-10, 10), (-10, -10), (10, -10)]
        edges = [await vedge(x, y) for x, y in corners]
        result, shape = await dressup("partdesign_fillet", "Fillet_vertical",
                                      [(volume, (x * (10 - inset) / 10, y * (10 - inset) / 10, 10)) for x, y in corners],
                                      edges=edges, radius=2)
        assert await count(result["name"], "face", geometry_type="cylinder", radius=span(2)) == 4
        await undo()
        edge = (await select(base, "edge", geometry_type="line", axis=[0, 1, 0], position=[10, 0, 20]))["selection"]
        await dressup("partdesign_fillet", "Fillet_top_edge", [(volume, (10 - inset, 0, 20 - inset))],
                      edges=[edge], radius=2)
        await undo()
        edges = [await tedge(10, 0), await tedge(-10, 0), await tedge(0, 10), await tedge(0, -10)]
        overlap = (5 / 3 - pi / 2) * 2 ** 3
        result, shape = await feature("partdesign_fillet", body, V0 - (4 * volume - 4 * overlap), base_name=base,
                                      edges=edges, radius=2, name="Fillet_top_loop")
        near(com(shape)[:2], [0, 0])
        near(bbox(shape), [-10, -10, 0, 10, 10, 20])
        await undo()
        big, big_inset = fillet_removed(10, 20)
        edge = await vedge(10, 10)
        await dressup("partdesign_fillet", "Fillet_half_width", [(big, (10 - big_inset, 10 - big_inset, 10))],
                      edges=[edge], radius=10)
        await undo()
        edge = await vedge(10, 10)
        await reject("partdesign_fillet", body, "may be too large", base_name=base, edges=[edge], radius=25)
        edge = await vedge(10, 10)
        await reject("partdesign_fillet", body, "greater than 0", base_name=base, edges=[edge], radius=0)
        edge = await vedge(10, 10)
        await reject("partdesign_fillet", body, "greater than 0", base_name=base, edges=[edge], radius=-1)
        await reject("partdesign_fillet", body, "valid dictionary", base_name=base, edges=["Edge5"], radius=2)
        await reject("partdesign_fillet", body, "valid dictionary", base_name=base, edges=["Face1"], radius=2)
        await reject("partdesign_fillet", body, "at least 1 item", base_name=base, edges=[], radius=2)
        face = (await select(base, "face", normal=[0, 0, 1]))["selection"]
        await reject("partdesign_fillet", body, "different object or subelement kind", base_name=base,
                     edges=[face], radius=2)
        await reject("partdesign_fillet", body, "different object", base_name=base, edges=[foreign_edge], radius=2)
        sketch_edge = (await select("DressPadSketch", "edge", geometry_type="line", position=[10, 0, 0]))["selection"]
        await reject("partdesign_fillet", body, "different object", base_name=base, edges=[sketch_edge], radius=2)
        edge = await vedge(10, 10)
        await reject("partdesign_fillet", body, "must not contain duplicates", base_name=base, edges=[edge, edge],
                     radius=2)
        await reject("partdesign_fillet", body, "is not in", base_name="NoSuchBase", edges=[edge], radius=2)
        edge = await vedge(10, 10)
        await invoke("sketch_add_line", doc_name=doc, sketch_name="DressScratch", x1=0, y1=0, x2=1, y2=0)
        await undo()
        await reject("partdesign_fillet", body, "Document changed", base_name=base, edges=[edge], radius=2)

        # Chamfer: equal and two distances, face areas, order of the distances, limits.
        def chamfer_removed(first, second, length):
            return first * second / 2 * length, (first / 3, second / 3)

        volume, (leg, _) = chamfer_removed(2, 2, 20)
        edge = await vedge(10, 10)
        result, shape = await dressup("partdesign_chamfer", "Chamfer_equal",
                                      [(volume, (10 - leg, 10 - leg, 10))], edges=[edge], size=2)
        slanted = await listing(result["name"], "face", geometry_type="plane", normal=[math.sqrt(0.5), math.sqrt(0.5), 0])
        assert len(slanted) == 1 and abs(slanted[0]["area"] - 2 * math.sqrt(2) * 20) <= 1e-9, slanted
        await undo()
        edge = await vedge(10, 10)
        await dressup("partdesign_chamfer", "Chamfer_equal_pair", [(volume, (10 - leg, 10 - leg, 10))],
                      edges=[edge], size=2, second_size=2)
        await undo()
        normals = {}
        for first, second in ((2, 3), (3, 2)):
            volume2, _ = chamfer_removed(first, second, 20)
            edge = await vedge(10, 10)
            result, shape = await feature("partdesign_chamfer", body, V0 - volume2, base_name=base, edges=[edge],
                                          size=first, second_size=second, name=f"Chamfer_{first}_{second}")
            faces = [item for item in await listing(result["name"], "face", geometry_type="plane")
                     if item["normal"][0] > 0.1 and item["normal"][1] > 0.1]
            assert len(faces) == 1 and abs(faces[0]["area"] - math.sqrt(13) * 20) <= 1e-9, faces
            normals[(first, second)] = faces[0]["normal"]
            await undo()
        parallel(normals[(2, 3)], [2, 3, 0] if normals[(2, 3)][1] > normals[(2, 3)][0] else [3, 2, 0])
        assert abs(normals[(2, 3)][0] - normals[(3, 2)][1]) <= 1e-9 and abs(normals[(2, 3)][1] - normals[(3, 2)][0]) <= 1e-9, normals
        edges = [await vedge(x, y) for x, y in corners]
        volume, (leg, _) = chamfer_removed(2, 2, 20)
        await dressup("partdesign_chamfer", "Chamfer_vertical",
                      [(volume, (x * (10 - leg) / 10, y * (10 - leg) / 10, 10)) for x, y in corners],
                      edges=edges, size=2)
        await undo()
        edge = (await select(base, "edge", geometry_type="line", axis=[0, 1, 0], position=[10, 0, 20]))["selection"]
        volume, (leg, _) = chamfer_removed(3, 3, 20)
        await dressup("partdesign_chamfer", "Chamfer_top_edge", [(volume, (10 - leg, 0, 20 - leg))],
                      edges=[edge], size=3)
        await undo()
        edge = await vedge(10, 10)
        await reject("partdesign_chamfer", body, "failed", base_name=base, edges=[edge], size=30)
        edge = await vedge(10, 10)
        await reject("partdesign_chamfer", body, "failed", base_name=base, edges=[edge], size=2, second_size=30)
        edge = await vedge(10, 10)
        await reject("partdesign_chamfer", body, "greater than 0", base_name=base, edges=[edge], size=0)
        await reject("partdesign_chamfer", body, "greater than 0", base_name=base, edges=[edge], size=-2)
        await reject("partdesign_chamfer", body, "greater than 0", base_name=base, edges=[edge], size=2,
                     second_size=0)
        await reject("partdesign_chamfer", body, "valid dictionary", base_name=base, edges=["Edge5"], size=2)
        await reject("partdesign_chamfer", body, "different object or subelement kind", base_name=base,
                     edges=[(await select(base, "face", normal=[0, 0, 1]))["selection"]], size=2)
        edge = await vedge(10, 10)
        await reject("partdesign_chamfer", body, "must not contain duplicates", base_name=base, edges=[edge, edge],
                     size=2)
        await reject("partdesign_chamfer", body, "different object", base_name=base, edges=[foreign_edge], size=2)
        edge = await vedge(10, 10)
        await invoke("sketch_add_line", doc_name=doc, sketch_name="DressScratch", x1=0, y1=0, x2=1, y2=0)
        await undo()
        await reject("partdesign_chamfer", body, "Document changed", base_name=base, edges=[edge], size=2)

        body = await new_body("ThickBody")
        base = await block(body, "ThickPad", -10, -10, 10, 10, 20)
        await rect("ThickScratch", body, 30, 30, 31, 31)
        V0, C0 = 8000.0, (0.0, 0.0, 10.0)
        foreign_face = (await invoke("select_subelement", doc_name=other, obj_name="ForeignBox", kind="face",
                                     filters={"normal": [0, 0, 1]}))["selection"]

        async def face(normal):
            return (await select(base, "face", normal=normal))["selection"]

        async def shell(label, expected, faces_normals, **arguments):
            faces = [await face(normal) for normal in faces_normals]
            return await feature("partdesign_thickness", body, expected, base_name=base, faces=faces,
                                 name=f"Thick_{label}", **arguments)

        cavity = 16 * 16 * 18
        for join in ("arc", "intersection"):
            result, shape = await shell(f"in_{join}", V0 - cavity, [[0, 0, 1]], value=2, join=join)
            near(bbox(shape), [-10, -10, 0, 10, 10, 20])
            near(com(shape), mass_com(V0, C0, [(cavity, (0, 0, 11))]))
            assert await count(result["name"], "face", geometry_type="plane", normal=[0, 0, 1], area=span(144)) == 1
            await undo()
        outer_arc = (20 * 20 * 2 + 4 * (20 * 20 * 2) + 4 * (pi * 4 / 4 * 20) + 4 * (pi * 4 / 4 * 20)
                     + 4 * (4 / 3 * pi * 8 / 8))
        result, shape = await shell("out_arc", outer_arc, [[0, 0, 1]], value=2, direction="outside", join="arc")
        near(bbox(shape), [-12, -12, -2, 12, 12, 20])
        near(com(shape)[:2], [0, 0])
        await undo()
        result, shape = await shell("out_intersection", 24 * 24 * 22 - 8000, [[0, 0, 1]], value=2,
                                    direction="outside", join="intersection")
        near(bbox(shape), [-12, -12, -2, 12, 12, 20])
        near(com(shape)[:2], [0, 0])
        await undo()
        result, shape = await shell("in_two_faces", V0 - 18 * 16 * 18, [[0, 0, 1], [1, 0, 0]], value=2)
        near(bbox(shape), [-10, -10, 0, 10, 10, 20])
        near(com(shape), mass_com(V0, C0, [(18 * 16 * 18, (1, 0, 11))]))
        await undo()
        result, shape = await shell("out_two_faces", 22 * 24 * 22 - 8000, [[0, 0, 1], [1, 0, 0]], value=2,
                                    direction="outside", join="intersection")
        near(bbox(shape), [-12, -12, -2, 10, 12, 20])
        await undo()
        result, shape = await shell("in_thin", V0 - 1 * 1 * 10.5, [[0, 0, 1]], value=9.5)
        near(com(shape), mass_com(V0, C0, [(10.5, (0, 0, (9.5 + 20) / 2))]))
        await undo()
        top = await face([0, 0, 1])
        await reject("partdesign_thickness", body, "invalid BRep geometry", base_name=base, faces=[top], value=10)
        top = await face([0, 0, 1])
        await reject("partdesign_thickness", body, "greater than 0", base_name=base, faces=[top], value=0)
        await reject("partdesign_thickness", body, "greater than 0", base_name=base, faces=[top], value=-1)
        await reject("partdesign_thickness", body, "Input should be 'inside' or 'outside'", base_name=base,
                     faces=[top], value=2, direction="both")
        await reject("partdesign_thickness", body, "Input should be 'arc' or 'intersection'", base_name=base,
                     faces=[top], value=2, join="round")
        await reject("partdesign_thickness", body, "valid dictionary", base_name=base, faces=["Face6"], value=2)
        await reject("partdesign_thickness", body, "at least 1 item", base_name=base, faces=[], value=2)
        await reject("partdesign_thickness", body, "must not contain duplicates", base_name=base,
                     faces=[top, top], value=2)
        await reject("partdesign_thickness", body, "different object", base_name=base, faces=[foreign_face], value=2)
        edge = (await select(base, "edge", geometry_type="line", axis=[0, 0, 1], position=[10, 10, 10]))["selection"]
        await reject("partdesign_thickness", body, "different object or subelement kind", base_name=base,
                     faces=[edge], value=2)
        every = [await face(normal) for normal in ([0, 0, 1], [0, 0, -1], [1, 0, 0], [-1, 0, 0], [0, 1, 0], [0, -1, 0])]
        await reject("partdesign_thickness", body, "had no effect", base_name=base, faces=every, value=2)
        top = await face([0, 0, 1])
        await invoke("sketch_add_line", doc_name=doc, sketch_name="ThickScratch", x1=0, y1=0, x2=1, y2=0)
        await undo()
        await reject("partdesign_thickness", body, "Document changed", base_name=base, faces=[top], value=2)

        body = await new_body("DraftBody")
        base = await block(body, "DraftPad", -10, -10, 10, 10, 20)
        await rect("DraftScratch", body, 30, 30, 31, 31)
        t5 = math.tan(math.radians(5))
        foreign_face = (await invoke("select_subelement", doc_name=other, obj_name="ForeignBox", kind="face",
                                     filters={"normal": [0, 0, 1]}))["selection"]

        def prismatoid(wide, narrow, height=20):
            return height / 3 * (wide * wide + wide * narrow + narrow * narrow)

        def prismatoid_com_z(base_width, top_width, height=20):
            return height * (base_width ** 2 + 2 * base_width * top_width + 3 * top_width ** 2) / (
                4 * (base_width ** 2 + base_width * top_width + top_width ** 2))

        async def sides(obj=base):
            return [item["selection"] for item in await listing(obj, "face", geometry_type="plane")
                    if abs(item["normal"][2]) < 1e-9]

        async def plane_face(normal, obj=base):
            return (await select(obj, "face", normal=normal))["selection"]

        async def drafted(label, bottom_width, top_width, **arguments):
            faces = await sides()
            result, shape = await feature("partdesign_draft", body, prismatoid(bottom_width, top_width),
                                          base_name=base, faces=faces, name=f"Draft_{label}", **arguments)
            half = max(bottom_width, top_width) / 2
            near(bbox(shape), [-half, -half, 0, half, half, 20])
            near(com(shape)[:2], [0, 0])
            assert abs(com(shape)[2] - prismatoid_com_z(bottom_width, top_width)) <= 1e-6, (label, com(shape))
            await undo()
            return result

        # Positive angles narrow the section toward +Z, negative angles widen it; the neutral plane keeps its size.
        bottom = await plane_face([0, 0, -1])
        await drafted("bottom_name", 20, 20 - 40 * t5, angle=5, plane_name=f"{base}.{bottom['subelement']}")
        await drafted("bottom_selection", 20, 20 - 40 * t5, angle=5, plane_selection=await plane_face([0, 0, -1]))
        await drafted("bottom_negative", 20, 20 + 40 * t5, angle=-5, plane_selection=await plane_face([0, 0, -1]))
        await drafted("top_neutral", 20 + 40 * t5, 20, angle=5, plane_selection=await plane_face([0, 0, 1]))
        await drafted("bottom_pull_edge", 20, 20 - 40 * t5, angle=5, plane_selection=await plane_face([0, 0, -1]),
                      pull_selection=(await select(base, "edge", geometry_type="line", axis=[0, 0, 1],
                                                   position=[10, 10, 10]))["selection"])
        await drafted("boundary_26", 20, 20 - 40 * math.tan(math.radians(26)), angle=26,
                      plane_selection=await plane_face([0, 0, -1]))
        await mutate("partdesign_datum", body, body_name=body, kind="plane", name="DraftBottomPlane")
        await mutate("partdesign_datum", body, body_name=body, kind="plane", name="DraftMidPlane", z=10)
        await drafted("datum_bottom", 20, 20 - 40 * t5, angle=5, plane_name="DraftBottomPlane")
        await drafted("datum_mid", 20 + 20 * t5, 20 - 20 * t5, angle=5, plane_name="DraftMidPlane")
        one = (await sides())[0]
        result, shape = await feature("partdesign_draft", body, 8000 - 4000 * t5, base_name=base, faces=[one],
                                      angle=5, plane_selection=await plane_face([0, 0, -1]), name="Draft_one_face")
        near(bbox(shape), [-10, -10, 0, 10, 10, 20])
        await undo()

        bottom_name = f"{base}.{(await plane_face([0, 0, -1]))['subelement']}"
        for expected, options in [("may be too large", dict(angle=27)),
                                  ("nonzero with |angle| < 90", dict(angle=0)),
                                  ("nonzero with |angle| < 90", dict(angle=90)),
                                  ("nonzero with |angle| < 90", dict(angle=-90)),
                                  ("nonzero with |angle| < 90", dict(angle=95))]:
            await reject("partdesign_draft", body, expected, base_name=base, faces=await sides(),
                         plane_selection=await plane_face([0, 0, -1]), **options)
        await reject("partdesign_draft", body, "A neutral plane is required", base_name=base, faces=await sides(),
                     angle=5)
        await reject("partdesign_draft", body, "either plane_name or plane_selection", base_name=base,
                     faces=await sides(), angle=5, plane_name=bottom_name,
                     plane_selection=await plane_face([0, 0, -1]))
        for expected, plane_name in [("must name a face", f"{base}.Edge1"),
                                     ("must name a face", f"{bottom_name}.Face2"),
                                     ("is not a face of", f"{base}.Face99"),
                                     ("Object 'Nope' not found", "Nope.Face1"),
                                     ("must be a datum plane or a face", "DraftPadSketch")]:
            await reject("partdesign_draft", body, expected, base_name=base, faces=await sides(), angle=5,
                         plane_name=plane_name)
        async def vedge():
            return (await select(base, "edge", geometry_type="line", axis=[0, 0, 1], position=[10, 10, 10]))["selection"]

        faces = await sides()
        await reject("partdesign_draft", body, "must not be one of the drafted faces", base_name=base, faces=faces,
                     angle=5, plane_selection=faces[0])
        faces = await sides()
        await reject("partdesign_draft", body, "must not be one of the drafted faces", base_name=base, faces=faces,
                     angle=5, plane_name=f"{base}.{faces[0]['subelement']}")
        await reject("partdesign_draft", body, "must be a same-document face selection", base_name=base,
                     faces=await sides(), angle=5, plane_selection=await vedge())
        await reject("partdesign_draft", body, "requires a same-document edge selection", base_name=base,
                     faces=await sides(), angle=5, plane_selection=await plane_face([0, 0, -1]),
                     pull_selection=await plane_face([0, 0, 1]))
        await reject("partdesign_draft", body, "requires a same-document edge selection", base_name=base,
                     faces=await sides(), angle=5, plane_selection=await plane_face([0, 0, -1]),
                     pull_selection=foreign_face)
        await reject("partdesign_draft", body, "different object or subelement kind", base_name=base,
                     faces=[await vedge()], angle=5, plane_name=bottom_name)
        await reject("partdesign_draft", body, "different object", base_name=base, faces=[foreign_face], angle=5,
                     plane_name=bottom_name)
        faces = await sides()
        await reject("partdesign_draft", body, "must not contain duplicates", base_name=base,
                     faces=[faces[0], faces[0]], angle=5, plane_name=bottom_name)
        await reject("partdesign_draft", body, "valid dictionary", base_name=base, faces=["Face1"], angle=5,
                     plane_name=bottom_name)
        await reject("partdesign_draft", body, "at least 1 item", base_name=base, faces=[], angle=5,
                     plane_name=bottom_name)
        faces = await sides()
        await invoke("sketch_add_line", doc_name=doc, sketch_name="DraftScratch", x1=0, y1=0, x2=1, y2=0)
        await undo()
        await reject("partdesign_draft", body, "Document changed", base_name=base, faces=faces, angle=5,
                     plane_name=bottom_name)

        # A non-planar neutral plane is rejected before mutation.
        round_body = await new_body("DraftRound")
        round_base = await block(round_body, "RoundPad", -10, -10, 10, 10, 20)
        edge = (await select(round_base, "edge", geometry_type="line", axis=[0, 0, 1], position=[10, 10, 10]))["selection"]
        await feature("partdesign_fillet", round_body, 8000 - (1 - pi / 4) * 4 * 20, base_name=round_base,
                      edges=[edge], radius=2, name="RoundFillet")
        faces = await sides("RoundFillet")
        cylinder = (await select("RoundFillet", "face", geometry_type="cylinder"))["selection"]
        await reject("partdesign_draft", round_body, "must be planar", base_name="RoundFillet", faces=faces,
                     angle=5, plane_selection=cylinder)

        # Dress-ups only accept the Body Tip as base.
        tip_body = await new_body("TipBody")
        tip_base = await block(tip_body, "TipPad", -10, -10, 10, 10, 20)
        await circle("TipCut", tip_body, 0, 0, 2, offset=20)
        await feature("partdesign_pocket", tip_body, 8000 - pi * 4 * 5, sketch_name="TipCut", length=5,
                      name="TipPocket")
        expected = "must be the Tip of Body 'TipBody'"

        async def tip_edge():
            return (await select(tip_base, "edge", geometry_type="line", axis=[0, 0, 1], position=[10, 10, 10]))["selection"]

        async def tip_face(normal):
            return (await select(tip_base, "face", normal=normal))["selection"]

        await reject("partdesign_fillet", tip_body, expected, base_name=tip_base, edges=[await tip_edge()], radius=2)
        await reject("partdesign_chamfer", tip_body, expected, base_name=tip_base, edges=[await tip_edge()], size=2)
        await reject("partdesign_thickness", tip_body, expected, base_name=tip_base,
                     faces=[await tip_face([0, 0, 1])], value=2)
        await reject("partdesign_draft", tip_body, expected, base_name=tip_base, faces=[await tip_face([1, 0, 0])],
                     angle=5, plane_selection=await tip_face([0, 0, -1]))

        plate_volume = 200000.0
        hole_volume = pi * 4 * 5

        async def plate(body, name):
            return await block(body, name, -50, -50, 50, 50, 20, symmetric=True)

        async def pocket_hole(body, name, x, y, radius, depth, before):
            sketch = await circle(f"{name}Sketch", body, x, y, radius, offset=10)
            volume = before - pi * radius ** 2 * depth
            await feature("partdesign_pocket", body, volume, sketch_name=sketch, length=depth, name=name)
            return volume

        def hole_part(x, y, radius=2.0, depth=5.0, z=None):
            return (pi * radius ** 2 * depth, (x, y, 10 - depth / 2 if z is None else z))

        async def pattern(tool, body, label, parts, **arguments):
            result, shape = await feature(tool, body, plate_volume - sum(part[0] for part in parts),
                                          name=f"Pattern_{label}", **arguments)
            near(bbox(shape), [-50, -50, -10, 50, 50, 10])
            near(com(shape), mass_com(plate_volume, (0, 0, 0), parts))
            await undo()
            return result

        body = await new_body("PatBody")
        await plate(body, "PatPlate")
        await pocket_hole(body, "PatHole", -40, -40, 2, 5, plate_volume)
        original = hole_part(-40, -40)
        await rect("PatScratch", body, 80, 80, 81, 81)
        await mutate("partdesign_datum", body, body_name=body, kind="axis", name="PatAxisX", rotation_y=90)
        await mutate("partdesign_datum", body, body_name=body, kind="axis", name="PatAxisY", rotation_x=-90)
        await mutate("partdesign_datum", body, body_name=body, kind="plane", name="PatPlaneX", x=-20, rotation_y=90)

        # Linear: body axes and datum axis, minimum and typical counts; the last copy lies `length` from the first.
        for axis, step in (("X", (20, 0)), ("Y", (0, 20))):
            parts = [hole_part(-40 + step[0] * k, -40 + step[1] * k) for k in range(4)]
            result = await pattern("partdesign_linear_pattern", body, f"linear_{axis}", parts,
                                   feature_name="PatHole", direction=axis, length=60, occurrences=4)
            assert result["occurrences"] == 4 and result["originals"] == ["PatHole"], result
        parts = [hole_part(-40 + 20 * k, -40) for k in range(4)]
        await pattern("partdesign_linear_pattern", body, "linear_datum_x", parts, feature_name="PatHole",
                      direction_name="PatAxisX", length=60, occurrences=4)
        parts = [hole_part(-40, -40 + 20 * k) for k in range(4)]
        await pattern("partdesign_linear_pattern", body, "linear_datum_y", parts, feature_name="PatHole",
                      direction_name="PatAxisY", length=60, occurrences=4)
        await pattern("partdesign_linear_pattern", body, "linear_two", [original, hole_part(20, -40)],
                      feature_name="PatHole", direction="X", length=60, occurrences=2)

        # Polar: full circle, datum-free about Z, evenly spread copies.
        parts = [hole_part(x, y) for x, y in ((-40, -40), (40, -40), (40, 40), (-40, 40))]
        await pattern("partdesign_polar_pattern", body, "polar_z_360", parts, feature_name="PatHole", axis="Z",
                      angle=360, occurrences=4)
        await pattern("partdesign_polar_pattern", body, "polar_z_180", [original, hole_part(40, 40)],
                      feature_name="PatHole", axis="Z", angle=180, occurrences=2)
        await pattern("partdesign_polar_pattern", body, "polar_z_360_two", [original, hole_part(40, 40)],
                      feature_name="PatHole", axis="Z", angle=360, occurrences=2)

        # Mirrored: three origin planes and a datum plane.
        for plane, mirrored_at in (("XY", (-40, -40, -7.5)), ("XZ", (-40, 40, 7.5)), ("YZ", (40, -40, 7.5))):
            result = await pattern("partdesign_mirrored", body, f"mirror_{plane}",
                                   [original, (hole_volume, mirrored_at)], feature_name="PatHole", plane=plane)
            assert result["originals"] == ["PatHole"], result
        await pattern("partdesign_mirrored", body, "mirror_datum", [original, hole_part(0, -40)],
                      feature_name="PatHole", plane_name="PatPlaneX")

        # Occurrence and length limits.
        for expected, tool, options in [
                ("greater than or equal to 2", "partdesign_linear_pattern", dict(direction="X", length=60, occurrences=1)),
                ("less than or equal to 100", "partdesign_linear_pattern", dict(direction="X", length=60, occurrences=101)),
                ("valid integer", "partdesign_linear_pattern", dict(direction="X", length=60, occurrences=2.5)),
                ("greater than 0", "partdesign_linear_pattern", dict(direction="X", length=0, occurrences=3)),
                ("greater than 0", "partdesign_linear_pattern", dict(direction="X", length=-5, occurrences=3)),
                ("Unknown axis 'W'", "partdesign_linear_pattern", dict(direction="W", length=60, occurrences=3)),
                ("must be a PartDesign::Line in the same Body", "partdesign_linear_pattern",
                 dict(direction_name="PatPlaneX", length=60, occurrences=3)),
                ("Object 'NoAxis' not found", "partdesign_linear_pattern", dict(direction_name="NoAxis", length=60, occurrences=3)),
                ("greater than 0", "partdesign_polar_pattern", dict(axis="Z", angle=0, occurrences=3)),
                ("less than or equal to 360", "partdesign_polar_pattern", dict(axis="Z", angle=361, occurrences=3)),
                ("greater than or equal to 2", "partdesign_polar_pattern", dict(axis="Z", angle=90, occurrences=1)),
                ("less than or equal to 100", "partdesign_polar_pattern", dict(axis="Z", angle=90, occurrences=101)),
                ("Unknown axis 'Q'", "partdesign_polar_pattern", dict(axis="Q", angle=90, occurrences=3)),
                ("must be a PartDesign::Line in the same Body", "partdesign_polar_pattern",
                 dict(axis_name="PatPlaneX", angle=90, occurrences=3)),
                ("Unknown plane 'AB'", "partdesign_mirrored", dict(plane="AB")),
                ("must be a PartDesign::Plane in the same Body", "partdesign_mirrored", dict(plane_name="PatAxisX"))]:
            await reject(tool, body, expected, feature_name="PatHole", **options)
        await reject("partdesign_linear_pattern", body, "Only additive and subtractive features",
                     feature_name="PatScratch", direction="X", length=60, occurrences=3)
        await reject("partdesign_linear_pattern", body, "is not in", feature_name="NoFeature", direction="X",
                     length=60, occurrences=3)
        await reject("partdesign_linear_pattern", body, "must belong to a PartDesign Body", feature_name=body,
                     direction="X", length=60, occurrences=3)

        # Foreign Body: originals and datums must come from the pattern's own Body.
        foreign_body = await new_body("PatForeign")
        await block(foreign_body, "ForeignPlate", -10, -10, 10, 10, 10)
        await mutate("partdesign_datum", foreign_body, body_name=foreign_body, kind="axis", name="ForeignAxis")
        await mutate("partdesign_datum", foreign_body, body_name=foreign_body, kind="plane", name="ForeignPlane")
        await reject("partdesign_linear_pattern", body, "same PartDesign Body", feature_name="PatHole",
                     feature_names=["ForeignPlate"], direction="X", length=60, occurrences=3)
        await reject("partdesign_linear_pattern", body, "must be a PartDesign::Line in the same Body",
                     feature_name="PatHole", direction_name="ForeignAxis", length=60, occurrences=3)
        await reject("partdesign_polar_pattern", body, "must be a PartDesign::Line in the same Body",
                     feature_name="PatHole", axis_name="ForeignAxis", angle=90, occurrences=3)
        await reject("partdesign_mirrored", body, "must be a PartDesign::Plane in the same Body",
                     feature_name="PatHole", plane_name="ForeignPlane")

        # Maximum occurrence count with non-overlapping small holes.
        tiny = await new_body("PatTiny")
        await plate(tiny, "TinyPlate")
        await pocket_hole(tiny, "TinyHole", -45, -45, 0.3, 5, plate_volume)
        tiny_part = hole_part(-45, -45, radius=0.3)
        parts = [hole_part(-45 + 90 * k / 99, -45, radius=0.3) for k in range(100)]
        await pattern("partdesign_linear_pattern", tiny, "linear_100", parts, feature_name="TinyHole",
                      direction="X", length=90, occurrences=100)
        assert tiny_part == parts[0]

        # Stacked pad copies along Z merge into one column.
        column = await new_body("PatColumn")
        await plate(column, "ColumnPlate")
        await rect("ColumnBump", column, -42, -42, -38, -38, offset=10)
        await feature("partdesign_pad", column, plate_volume + 64, sketch_name="ColumnBump", length=4, name="Bump")
        result, shape = await feature("partdesign_linear_pattern", column, plate_volume + 192, feature_name="Bump",
                                      direction="Z", length=8, occurrences=3, name="BumpColumn")
        near(bbox(shape), [-50, -50, -10, 50, 50, 22])
        near(com(shape), [192 * -40 / (plate_volume + 192), 192 * -40 / (plate_volume + 192),
                          192 * 16 / (plate_volume + 192)])
        await undo()

        # Polar about X, Y, a datum axis and a partial angle (the last copy lies `angle` from the first).
        for axis, original_at, copy_at in (("X", (-40, 0), (-40, -7.5, 0)), ("Y", (0, -40), (7.5, -40, 0))):
            axis_body = await new_body(f"PatPolar{axis}")
            await plate(axis_body, f"Polar{axis}Plate")
            await pocket_hole(axis_body, f"Polar{axis}Hole", *original_at, 2, 5, plate_volume)
            await pattern("partdesign_polar_pattern", axis_body, f"polar_{axis}",
                          [hole_part(*original_at), (hole_volume, copy_at)],
                          feature_name=f"Polar{axis}Hole", axis=axis, angle=90, occurrences=2)
        datum_body = await new_body("PatPolarDatum")
        await plate(datum_body, "DatumPlate")
        await pocket_hole(datum_body, "DatumHole", -20, -20, 2, 5, plate_volume)
        await mutate("partdesign_datum", datum_body, body_name=datum_body, kind="axis", name="VerticalAxis", x=10, y=10)
        await pattern("partdesign_polar_pattern", datum_body, "polar_datum", [hole_part(-20, -20), hole_part(40, 40)],
                      feature_name="DatumHole", axis_name="VerticalAxis", angle=180, occurrences=2)
        partial = await new_body("PatPartial")
        await plate(partial, "PartialPlate")
        await pocket_hole(partial, "PartialHole", -30, -30, 2, 5, plate_volume)
        radius_at, start = math.hypot(30, 30), math.radians(225)
        parts = [hole_part(radius_at * math.cos(start + math.radians(30 * k)),
                           radius_at * math.sin(start + math.radians(30 * k))) for k in range(4)]
        await pattern("partdesign_polar_pattern", partial, "polar_partial", parts, feature_name="PartialHole",
                      axis="Z", angle=90, occurrences=4)

        # Several originals in one pattern.
        multi = await new_body("PatMulti")
        await plate(multi, "MultiPlate")
        volume = await pocket_hole(multi, "HoleA", -40, -40, 2, 5, plate_volume)
        await pocket_hole(multi, "HoleB", -30, 20, 1, 3, volume)
        part_a, part_b = hole_part(-40, -40), hole_part(-30, 20, radius=1, depth=3)
        result = await pattern("partdesign_mirrored", multi, "mirror_two", [
            part_a, part_b, (part_a[0], (-40, 40, 7.5)), (part_b[0], (-30, -20, 8.5))],
            feature_name="HoleA", feature_names=["HoleB"], plane="XZ")
        assert result["originals"] == ["HoleA", "HoleB"], result
        await pattern("partdesign_linear_pattern", multi, "linear_two_originals", [
            part_a, part_b, (part_a[0], (-10, -40, 7.5)), (part_b[0], (0, 20, 8.5))],
            feature_name="HoleA", feature_names=["HoleB"], direction="X", length=30, occurrences=2)
        await pattern("partdesign_polar_pattern", multi, "polar_two_originals", [
            part_a, part_b, (part_a[0], (40, 40, 7.5)), (part_b[0], (30, -20, 8.5))],
            feature_name="HoleA", feature_names=["HoleB"], axis="Z", angle=180, occurrences=2)

        plate_volume = 200000.0
        hole_volume = pi * 4 * 5

        def hole_part(x, y, radius=2.0, depth=5.0):
            return (pi * radius ** 2 * depth, (x, y, 10 - depth / 2))

        async def plate_hole(body, name, x, y, radius=2, depth=5, before=None):
            await block(body, f"{name}Plate", -50, -50, 50, 50, 20, symmetric=True)
            sketch = await circle(f"{name}Sketch", body, x, y, radius, offset=10)
            volume = plate_volume - pi * radius ** 2 * depth
            await feature("partdesign_pocket", body, volume, sketch_name=sketch, length=depth, name=name)
            return volume

        async def chain(label, parts, steps, names=None, **options):
            feature_names = names or ["MultiHole"]
            result, shape = await feature("partdesign_multi_transform", multi_body,
                                          plate_volume - sum(part[0] for part in parts),
                                          feature_names=feature_names, transformations=steps,
                                          name=f"Multi_{label}", **options)
            near(bbox(shape), [-50, -50, -10, 50, 50, 10])
            near(com(shape), mass_com(plate_volume, (0, 0, 0), parts))
            assert result["originals"] == feature_names, result
            assert result["transformations"] == [f"Multi_{label}_{step['type'].title()}{index}"
                                                 for index, step in enumerate(steps, 1)], result
            await undo()
            return result

        multi_body = await new_body("MultiBody")
        await plate_hole(multi_body, "MultiHole", -30, -10)
        await rect("MultiScratch", multi_body, 80, 80, 81, 81)
        await mutate("partdesign_datum", multi_body, body_name=multi_body, kind="plane", name="MirrorPlane",
                     x=-20, rotation_y=90)
        await mutate("partdesign_datum", multi_body, body_name=multi_body, kind="axis", name="MultiAxis")
        linear = {"type": "linear", "direction": "X", "length": 10, "occurrences": 2}
        polar180 = {"type": "polar", "axis": "Z", "angle": 360, "occurrences": 2}
        mirror_xz, mirror_yz = {"type": "mirrored", "plane": "XZ"}, {"type": "mirrored", "plane": "YZ"}

        # Ordered chains: the order of the steps changes the result.
        await chain("polar_linear", [hole_part(-30, -10), hole_part(30, 10), hole_part(-20, -10), hole_part(40, 10)],
                    [polar180, linear])
        await chain("linear_polar", [hole_part(-30, -10), hole_part(-20, -10), hole_part(30, 10), hole_part(20, 10)],
                    [linear, polar180])
        await chain("mirror_linear", [hole_part(x, y) for x in (-30, -20, -10, 0) for y in (-10, 10)],
                    [mirror_xz, {"type": "linear", "direction": "X", "length": 30, "occurrences": 4}])
        await chain("mirror_mirror", [hole_part(x, y) for x in (-30, 30) for y in (-10, 10)], [mirror_yz, mirror_xz])
        await chain("three_steps", [hole_part(x, y) for x in (-30, -20, 20, 30) for y in (-10, 10)],
                    [mirror_xz, linear, polar180])
        await chain("datum_plane", [hole_part(-30, -10), hole_part(-10, -10)],
                    [{"type": "mirrored", "plane_name": "MirrorPlane"}])
        await chain("single_linear", [hole_part(-30, -10), hole_part(-20, -10)], [linear])
        datum_body = await new_body("MultiDatum")
        await plate_hole(datum_body, "DatumHoleM", -20, -10)
        await mutate("partdesign_datum", datum_body, body_name=datum_body, kind="axis", name="MultiVertical", x=10, y=10)
        multi_body, result = datum_body, None
        await chain("datum_axis", [hole_part(-20, -10), hole_part(40, 30), hole_part(-15, -10), hole_part(45, 30)],
                    [{"type": "polar", "axis_name": "MultiVertical", "angle": 360, "occurrences": 2},
                     {"type": "linear", "direction": "X", "length": 5, "occurrences": 2}], names=["DatumHoleM"])
        two_body = await new_body("MultiTwo")
        await block(two_body, "TwoPlate", -50, -50, 50, 50, 20, symmetric=True)
        await rect("TwoSketchA", two_body, -42, -42, -38, -38, offset=10)
        await feature("partdesign_pocket", two_body, plate_volume - 16 * 5, sketch_name="TwoSketchA", length=5,
                      name="TwoA")
        await rect("TwoSketchB", two_body, -33, 17, -27, 23, offset=10)
        await feature("partdesign_pocket", two_body, plate_volume - 16 * 5 - 36 * 3, sketch_name="TwoSketchB",
                      length=3, name="TwoB")
        multi_body = two_body
        await chain("two_originals", [(80, (-40, -40, 7.5)), (108, (-30, 20, 8.5)), (80, (-40, 40, 7.5)),
                                      (108, (-30, -20, 8.5))], [mirror_xz], names=["TwoA", "TwoB"])
        multi_body = "MultiBody"

        # Invalid steps are rejected before any document change.
        foreign_body = await new_body("MultiForeign")
        await block(foreign_body, "MultiForeignPad", -10, -10, 10, 10, 10)
        await mutate("partdesign_datum", foreign_body, body_name=foreign_body, kind="axis", name="MultiForeignAxis")
        names_ = ["MultiHole"]
        for expected, step in [
                ("linear transformation requires length", {"type": "linear", "direction": "X", "occurrences": 2}),
                ("linear transformation requires occurrences", {"type": "linear", "direction": "X", "length": 10}),
                ("polar transformation requires angle", {"type": "polar", "axis": "Z", "occurrences": 2}),
                ("polar transformation requires occurrences", {"type": "polar", "axis": "Z", "angle": 90}),
                ("linear transformation does not accept angle", {**linear, "angle": 90}),
                ("polar transformation does not accept length", {**polar180, "length": 10}),
                ("mirrored transformation does not accept occurrences", {**mirror_xz, "occurrences": 2}),
                ("mirrored transformation does not accept axis", {**mirror_xz, "axis": "Z"}),
                ("takes either direction or direction_name", {**linear, "direction_name": "MultiAxis"}),
                ("takes either axis or axis_name", {**polar180, "axis_name": "MultiAxis"}),
                ("takes either plane or plane_name", {**mirror_xz, "plane_name": "MirrorPlane"}),
                ("Input should be 'linear', 'polar' or 'mirrored'", {"type": "scale"}),
                ("less than or equal to 360", {**polar180, "angle": 400}),
                ("greater than 0", {**polar180, "angle": 0}),
                ("greater than 0", {**linear, "length": 0}),
                ("greater than or equal to 2", {**linear, "occurrences": 1}),
                ("less than or equal to 100", {**linear, "occurrences": 101}),
                ("Input should be 'X', 'Y' or 'Z'", {**linear, "direction": "W"}),
                ("Extra inputs are not permitted", {**mirror_xz, "foo": 1})]:
            await reject("partdesign_multi_transform", multi_body, expected, feature_names=names_,
                         transformations=[step])
        await reject("partdesign_multi_transform", multi_body, "at most 16 items", feature_names=names_,
                     transformations=[mirror_xz] * 17)
        await reject("partdesign_multi_transform", multi_body, "at least 1 item", feature_names=names_,
                     transformations=[])
        await reject("partdesign_multi_transform", multi_body, "at least 1 item", feature_names=[],
                     transformations=[mirror_xz])
        await reject("partdesign_multi_transform", multi_body, "limit is 100", feature_names=names_,
                     transformations=[{**polar180, "occurrences": 10}, {**linear, "occurrences": 11}])
        await reject("partdesign_multi_transform", multi_body, "limit is 100", feature_names=names_,
                     transformations=[mirror_xz, {**linear, "occurrences": 51}])
        await reject("partdesign_multi_transform", multi_body, "Object 'NoAxis' not found", feature_names=names_,
                     transformations=[{**polar180, "axis": None, "axis_name": "NoAxis"}])
        await reject("partdesign_multi_transform", multi_body, "must be a PartDesign::Line in the same Body",
                     feature_names=names_, transformations=[{"type": "polar", "axis_name": "MirrorPlane",
                                                             "angle": 90, "occurrences": 2}])
        await reject("partdesign_multi_transform", multi_body, "must be a PartDesign::Plane in the same Body",
                     feature_names=names_, transformations=[{"type": "mirrored", "plane_name": "MultiAxis"}])
        await reject("partdesign_multi_transform", multi_body, "must be a PartDesign::Line in the same Body",
                     feature_names=names_, transformations=[{"type": "linear", "direction_name": "MultiForeignAxis",
                                                             "length": 10, "occurrences": 2}])
        await reject("partdesign_multi_transform", multi_body, "same PartDesign Body",
                     feature_names=["MultiHole", "MultiForeignPad"], transformations=[mirror_xz])
        await reject("partdesign_multi_transform", multi_body, "Only additive and subtractive features",
                     feature_names=["MultiScratch"], transformations=[mirror_xz])
        await reject("partdesign_multi_transform", multi_body, "Object 'NoFeature' not found", feature_names=["NoFeature"],
                     transformations=[mirror_xz])

        plate_volume = 200000.0

        def hole_part(x, y, radius=2.0, depth=5.0):
            return (pi * radius ** 2 * depth, (x, y, 10 - depth / 2))

        async def edit_reject(body, expected, feature_name, **arguments):
            return await reject("partdesign_edit_feature", body, expected, feature_name=feature_name, **arguments)

        def prismatoid(wide, narrow, height=20):
            return height / 3 * (wide * wide + wide * narrow + narrow * narrow)

        foreign_body = await new_body("EditForeign")
        await rect("EditForeignSketch", foreign_body, -3, -3, 3, 3)

        # Pad: length, reversed, profile; modes ignoring a parameter reject it.
        pad_body = await new_body("EditPadBody")
        await rect("EPadA", pad_body, -10, -10, 10, 10)
        await feature("partdesign_pad", pad_body, 4000, sketch_name="EPadA", length=10, name="EPad")
        await rect("EPadB", pad_body, -5, -5, 5, 5)
        result, shape = await edit(pad_body, "EPad", 6000, parameters={"length": 15})
        near(bbox(shape), [-10, -10, 0, 10, 10, 15])
        assert result["body"] == pad_body and result["name"] == "EPad", result
        await undo()
        result, shape = await edit(pad_body, "EPad", 4000, parameters={"reversed": True})
        near(bbox(shape), [-10, -10, -10, 10, 10, 0])
        await undo()
        result, shape = await edit(pad_body, "EPad", 2000, parameters={"length": 5, "reversed": True})
        near(bbox(shape), [-10, -10, -5, 10, 10, 0])
        await undo()
        result, shape = await edit(pad_body, "EPad", 1000, profile_names=["EPadB"])
        near(bbox(shape), [-5, -5, 0, 5, 5, 10])
        await undo()
        result, shape = await edit(pad_body, "EPad", 2000, profile_names=["EPadB"], parameters={"length": 20})
        near(bbox(shape), [-5, -5, 0, 5, 5, 20])
        await undo()
        for expected, arguments in [
                ("requires an end condition with two lengths", dict(parameters={"second_length": 3})),
                ("must be positive", dict(parameters={"length": 0})),
                ("must be positive", dict(parameters={"length": -3})),
                ("must be positive", dict(parameters={"length": True})),
                ("must be positive", dict(parameters={"length": "5"})),
                ("must be positive", dict(parameters={"length": 1e999})),
                ("not editable for PartDesign::Pad", dict(parameters={"depth": 5})),
                ("not editable for PartDesign::Pad", dict(parameters={"angle": 5})),
                ("not editable for PartDesign::Pad", dict(parameters={"radius": 5})),
                ("not editable for PartDesign::Pad", dict(parameters={"foo": 5})),
                ("reversed must be boolean", dict(parameters={"reversed": 1})),
                ("profile_names or parameters is required", dict()),
                ("profile_names or parameters is required", dict(parameters={})),
                ("must be a nonempty list", dict(profile_names=[])),
                ("exactly one replacement profile", dict(profile_names=["EPadA", "EPadB"])),
                ("must be distinct", dict(profile_names=["EPadB", "EPadB"])),
                ("must be a Sketcher sketch", dict(profile_names=["EPad"])),
                ("must belong to the same Body", dict(profile_names=["EditForeignSketch"])),
                ("Object 'NoSketch' not found", dict(profile_names=["NoSketch"])),
                ("must be positive", dict(profile_names=["EPadB"], parameters={"length": 0}))]:
            await edit_reject(pad_body, expected, "EPad", **arguments)
        await edit_reject(pad_body, "not editable for Sketcher::SketchObject", "EPadA", parameters={"length": 5})
        await edit_reject(pad_body, "must belong to a PartDesign Body", pad_body, parameters={"length": 5})
        await edit_reject(pad_body, "Object 'NoFeature' is not in", "NoFeature", parameters={"length": 5})

        two_body = await new_body("EditTwoBody")
        await rect("ETwoSketch", two_body, -10, -10, 10, 10)
        await feature("partdesign_pad", two_body, 5600, sketch_name="ETwoSketch", end_condition="two_lengths",
                      length=10, second_length=4, name="ETwo")
        for parameters, volume, z_span in [({"second_length": 6}, 6400, (-6, 10)), ({"length": 12}, 6400, (-4, 12)),
                                           ({"length": 12, "second_length": 6}, 7200, (-6, 12)),
                                           ({"reversed": True}, 5600, (-10, 4))]:
            result, shape = await edit(two_body, "ETwo", volume, parameters=parameters)
            near(bbox(shape), [-10, -10, z_span[0], 10, 10, z_span[1]])
            await undo()
        await edit_reject(two_body, "must be positive", "ETwo", parameters={"second_length": 0})

        # Pocket: length, reversed, two lengths, through-all, profile.
        pocket_body = await new_body("EditPocketBody")
        await block(pocket_body, "EPocketBase", -10, -10, 10, 10, 10)
        await rect("EPocketSketch", pocket_body, -5, -5, 5, 5, offset=10)
        await feature("partdesign_pocket", pocket_body, 3600, sketch_name="EPocketSketch", length=4, name="EPocket")
        await rect("EPocketB", pocket_body, -2, -2, 2, 2, offset=10)
        await edit(pocket_body, "EPocket", 3200, parameters={"length": 8})
        await undo()
        result, shape = await edit(pocket_body, "EPocket", 4000, parameters={"reversed": True})
        near(bbox(shape), [-10, -10, 0, 10, 10, 10])
        await undo()
        await edit(pocket_body, "EPocket", 4000 - 16 * 4, profile_names=["EPocketB"])
        await undo()
        await edit(pocket_body, "EPocketBase", 8000 - 400 - 0, parameters={"length": 20})
        await undo()
        await edit_reject(pocket_body, "not editable for PartDesign::Pocket", "EPocket", parameters={"depth": 3})
        await edit_reject(pocket_body, "requires an end condition with two lengths", "EPocket",
                          parameters={"second_length": 3})
        through_body = await new_body("EditThroughBody")
        await block(through_body, "EThroughBase", -10, -10, 10, 10, 10)
        await rect("EThroughSketch", through_body, -5, -5, 5, 5, offset=10)
        await feature("partdesign_pocket", through_body, 3000, sketch_name="EThroughSketch", through_all=True,
                      length=1, name="EThrough")
        await edit_reject(through_body, "is not used by the end condition ThroughAll", "EThrough",
                          parameters={"length": 5})
        two_pocket = await new_body("EditPocketTwo")
        await block(two_pocket, "ETwoPocketBase", -10, -10, 10, 10, 10)
        await rect("ETwoPocketSketch", two_pocket, -5, -5, 5, 5, offset=5)
        await feature("partdesign_pocket", two_pocket, 3500, sketch_name="ETwoPocketSketch",
                      end_condition="two_lengths", length=2, second_length=3, name="ETwoPocket")
        for parameters, volume in [({"second_length": 5}, 3300), ({"length": 4}, 3300),
                                   ({"length": 4, "second_length": 5}, 3100)]:
            await edit(two_pocket, "ETwoPocket", volume, parameters=parameters)
            await undo()

        # Revolution and Groove: angles, second angle, reversed, profile.
        rev_body = await new_body("EditRevBody")
        await rect("ERevA", rev_body, 2, 0, 4, 5)
        await rect("ERevB", rev_body, 3, 0, 5, 5)
        await feature("partdesign_revolution", rev_body, 60 * pi, sketch_name="ERevA", angle=360, axis="V",
                      name="ERev")
        await edit(rev_body, "ERev", 30 * pi, parameters={"angle": 180})
        half_z = (await measure("ERev"))["center_of_mass"]["z"]
        await undo()
        await edit(rev_body, "ERev", 15 * pi, parameters={"angle": 90})
        await undo()
        await edit(rev_body, "ERev", 30 * pi, parameters={"angle": 180, "reversed": True})
        reversed_z = (await measure("ERev"))["center_of_mass"]["z"]
        assert abs(half_z) > 0.1 and abs(half_z + reversed_z) <= 1e-6, (half_z, reversed_z)
        await undo()
        await edit(rev_body, "ERev", 80 * pi, profile_names=["ERevB"])
        await undo()
        for expected, parameters in [("requires a two-angle rotation", {"second_angle": 90}),
                                     ("must be positive and at most 360", {"angle": 0}),
                                     ("must be positive and at most 360", {"angle": 361}),
                                     ("must be positive and at most 360", {"angle": True}),
                                     ("not editable for PartDesign::Revolution", {"length": 5})]:
            await edit_reject(rev_body, expected, "ERev", parameters=parameters)
        two_rev = await new_body("EditTwoRevBody")
        await rect("ETwoRevA", two_rev, 2, 0, 4, 5)
        await feature("partdesign_revolution", two_rev, 30 * pi, sketch_name="ETwoRevA", angle=90, second_angle=90,
                      axis="V", name="ETwoRev")
        await edit(two_rev, "ETwoRev", 45 * pi, parameters={"second_angle": 180})
        await undo()
        await edit(two_rev, "ETwoRev", 60 * pi * 290 / 360, parameters={"angle": 200})
        await undo()
        await edit_reject(two_rev, "must not exceed 360", "ETwoRev", parameters={"angle": 200, "second_angle": 180})
        await edit_reject(two_rev, "must not exceed 360", "ETwoRev", parameters={"angle": 300})
        groove_body = await new_body("EditGrooveBody")
        await rect("EGrooveBase", groove_body, 2, 0, 4, 5)
        await feature("partdesign_revolution", groove_body, 60 * pi, sketch_name="EGrooveBase", angle=360, axis="V",
                      name="EGrooveRing")
        await rect("EGrooveA", groove_body, 2.5, 1, 3.5, 2)
        await rect("EGrooveB", groove_body, 2.5, 3, 3.5, 4)
        await feature("partdesign_groove", groove_body, 54 * pi, sketch_name="EGrooveA", angle=360, axis="V",
                      name="EGroove")
        await edit(groove_body, "EGroove", 57 * pi, parameters={"angle": 180})
        await undo()
        before_y = (await measure("EGroove"))["center_of_mass"]["y"]
        await edit(groove_body, "EGroove", 54 * pi, profile_names=["EGrooveB"])
        assert abs((await measure("EGroove"))["center_of_mass"]["y"] - before_y) > 1e-4
        await undo()
        await edit_reject(groove_body, "requires a two-angle rotation", "EGroove", parameters={"second_angle": 90})
        two_groove = await new_body("EditTwoGrooveBody")
        await rect("ETwoGrooveBase", two_groove, 2, 0, 4, 5)
        await feature("partdesign_revolution", two_groove, 60 * pi, sketch_name="ETwoGrooveBase", angle=360,
                      axis="V", name="ETwoGrooveRing")
        await rect("ETwoGrooveSketch", two_groove, 2.5, 1, 3.5, 2)
        await feature("partdesign_groove", two_groove, 57 * pi, sketch_name="ETwoGrooveSketch", angle=90,
                      second_angle=90, axis="V", name="ETwoGroove")
        await edit(two_groove, "ETwoGroove", 60 * pi - 4.5 * pi, parameters={"second_angle": 180})
        await undo()

        # Hole: diameter, depth, profile; through-all rejects depth.
        hole_body = await new_body("EditHoleBody")
        await block(hole_body, "EHolePad", -20, -20, 20, 20, 20)
        await circle("EHoleSketch", hole_body, 0, 0, 2, offset=20)
        await circle("EHoleMoved", hole_body, 10, 0, 2, offset=20)
        removed = drill_parts(20, 0, 0, 2, 10)
        await feature("partdesign_hole", hole_body, 32000 - sum(part[0] for part in removed),
                      sketch_name="EHoleSketch", diameter=4, depth=10, name="EHole")
        for parameters, radius, depth in [({"diameter": 6}, 3, 10), ({"depth": 15}, 2, 15),
                                          ({"diameter": 6, "depth": 15}, 3, 15)]:
            parts = drill_parts(20, 0, 0, radius, depth)
            result, shape = await edit(hole_body, "EHole", 32000 - sum(part[0] for part in parts), parameters=parameters)
            near(com(shape), mass_com(32000.0, (0, 0, 10), parts))
            await undo()
        parts = drill_parts(20, 10, 0, 2, 10)
        result, shape = await edit(hole_body, "EHole", 32000 - sum(part[0] for part in parts),
                                   profile_names=["EHoleMoved"])
        near(com(shape), mass_com(32000.0, (0, 0, 10), parts))
        await undo()
        for expected, parameters in [("must be positive", {"diameter": 0}), ("must be positive", {"depth": -1}),
                                     ("not editable for PartDesign::Hole", {"length": 4}),
                                     ("not editable for PartDesign::Hole", {"radius": 4})]:
            await edit_reject(hole_body, expected, "EHole", parameters=parameters)
        through_hole = await new_body("EditHoleThrough")
        await block(through_hole, "EThroughPad", -20, -20, 20, 20, 20)
        await circle("EThroughSketch2", through_hole, 0, 0, 2, offset=20)
        await feature("partdesign_hole", through_hole, 32000 - pi * 4 * 20, sketch_name="EThroughSketch2", diameter=4,
                      depth=10, through_all=True, name="EThroughHole")
        await edit(through_hole, "EThroughHole", 32000 - pi * 9 * 20, parameters={"diameter": 6})
        await undo()
        await edit_reject(through_hole, "not used by a through-all hole", "EThroughHole", parameters={"depth": 5})

        # Dress-ups: radius, size, second size, wall thickness, draft angle, reversed.
        dress = await new_body("EditDressBody")
        await block(dress, "EDPad", -10, -10, 10, 10, 20)
        await circle("EDCircle", dress, 0, 0, 5)
        fillet_removed = lambda radius, length: (1 - pi / 4) * radius ** 2 * length
        edge = (await select("EDPad", "edge", geometry_type="line", axis=[0, 0, 1], position=[10, 10, 10]))["selection"]
        await feature("partdesign_fillet", dress, 8000 - fillet_removed(2, 20), base_name="EDPad", edges=[edge],
                      radius=2, name="EFillet")
        await edit(dress, "EFillet", 8000 - fillet_removed(3, 20), parameters={"radius": 3})
        await undo()
        await edit(dress, "EDPad", 12000 - fillet_removed(2, 30), parameters={"length": 30})
        await undo()
        await edit_reject(dress, "failed", "EFillet", parameters={"radius": 25})
        await edit_reject(dress, "must be positive", "EFillet", parameters={"radius": 0})
        await edit_reject(dress, "not editable for PartDesign::Fillet", "EFillet", parameters={"size": 2})
        await edit_reject(dress, "invalidated", "EDPad", profile_names=["EDCircle"])
        chamfer_body = await new_body("EditChamferBody")
        await block(chamfer_body, "ECPad", -10, -10, 10, 10, 20)
        edge = (await select("ECPad", "edge", geometry_type="line", axis=[0, 0, 1], position=[10, 10, 10]))["selection"]
        await feature("partdesign_chamfer", chamfer_body, 8000 - 60, base_name="ECPad", edges=[edge], size=2,
                      second_size=3, name="EChamfer")
        await edit(chamfer_body, "EChamfer", 8000 - 90, parameters={"size": 3})
        await undo()
        await edit(chamfer_body, "EChamfer", 8000 - 80, parameters={"second_size": 4})
        await undo()
        await edit_reject(chamfer_body, "not editable for PartDesign::Chamfer", "EChamfer", parameters={"reversed": True})
        await edit_reject(chamfer_body, "must be positive", "EChamfer", parameters={"second_size": 0})
        equal_body = await new_body("EditEqualBody")
        await block(equal_body, "EEPad", -10, -10, 10, 10, 20)
        edge = (await select("EEPad", "edge", geometry_type="line", axis=[0, 0, 1], position=[10, 10, 10]))["selection"]
        await feature("partdesign_chamfer", equal_body, 8000 - 40, base_name="EEPad", edges=[edge], size=2,
                      name="EEqual")
        await edit(equal_body, "EEqual", 8000 - 90, parameters={"size": 3})
        await undo()
        await edit_reject(equal_body, "requires a two-distances chamfer", "EEqual", parameters={"second_size": 3})
        thick_body = await new_body("EditThickBody")
        await block(thick_body, "ETPad", -10, -10, 10, 10, 20)
        top = (await select("ETPad", "face", normal=[0, 0, 1]))["selection"]
        await feature("partdesign_thickness", thick_body, 8000 - 16 * 16 * 18, base_name="ETPad", faces=[top],
                      value=2, name="EThickness")
        await edit(thick_body, "EThickness", 8000 - 14 * 14 * 17, parameters={"value": 3})
        await undo()
        outer_arc = (20 * 20 * 2 + 4 * (20 * 20 * 2) + 4 * (pi * 4 / 4 * 20) + 4 * (pi * 4 / 4 * 20)
                     + 4 * (4 / 3 * pi * 8 / 8))
        result, shape = await edit(thick_body, "EThickness", outer_arc, parameters={"reversed": False})
        near(bbox(shape), [-12, -12, -2, 12, 12, 20])
        await undo()
        await edit_reject(thick_body, "must be positive", "EThickness", parameters={"value": 0})
        await edit_reject(thick_body, "not editable for PartDesign::Thickness", "EThickness", parameters={"radius": 1})
        draft_body = await new_body("EditDraftBody")
        await block(draft_body, "EDrPad", -10, -10, 10, 10, 20)
        bottom = (await select("EDrPad", "face", normal=[0, 0, -1]))["selection"]
        sides = [item["selection"] for item in await listing("EDrPad", "face", geometry_type="plane")
                 if abs(item["normal"][2]) < 1e-9]
        t5, t8 = math.tan(math.radians(5)), math.tan(math.radians(8))
        await feature("partdesign_draft", draft_body, prismatoid(20, 20 - 40 * t5), base_name="EDrPad", faces=sides,
                      angle=5, plane_selection=bottom, name="EDraft")
        await edit(draft_body, "EDraft", prismatoid(20, 20 - 40 * t8), parameters={"angle": 8})
        await undo()
        await edit(draft_body, "EDraft", prismatoid(20, 20 + 40 * t5), parameters={"angle": -5})
        await undo()
        await edit(draft_body, "EDraft", prismatoid(20, 20 + 40 * t5), parameters={"reversed": True})
        await undo()
        for expected, angle in [("nonzero with |angle| < 90", 0), ("nonzero with |angle| < 90", 90),
                                ("nonzero with |angle| < 90", -90), ("nonzero with |angle| < 90", 100),
                                ("failed", 27)]:
            await edit_reject(draft_body, expected, "EDraft", parameters={"angle": angle})
        await edit_reject(draft_body, "not editable for PartDesign::Draft", "EDraft", parameters={"length": 3})

        plate_volume = 200000.0

        def hole_part(x, y, radius=2.0, depth=5.0):
            return (pi * radius ** 2 * depth, (x, y, 10 - depth / 2))

        async def edit_reject(body, expected, feature_name, **arguments):
            return await reject("partdesign_edit_feature", body, expected, feature_name=feature_name, **arguments)

        async def pattern_edit(body, name, parts, **arguments):
            result, shape = await edit(body, name, plate_volume - sum(part[0] for part in parts), **arguments)
            near(bbox(shape), [-50, -50, -10, 50, 50, 10])
            near(com(shape), mass_com(plate_volume, (0, 0, 0), parts))
            await undo()

        lin = await new_body("EditLinBody")
        await block(lin, "ELinPlate", -50, -50, 50, 50, 20, symmetric=True)
        await circle("ELinSketch", lin, -40, -40, 2, offset=10)
        await feature("partdesign_pocket", lin, plate_volume - pi * 20, sketch_name="ELinSketch", length=5,
                      name="ELinHole")
        await feature("partdesign_linear_pattern", lin, plate_volume - 4 * pi * 20, feature_name="ELinHole",
                      direction="X", length=60, occurrences=4, name="ELin")
        await pattern_edit(lin, "ELin", [hole_part(-40 + 10 * k, -40) for k in range(4)], parameters={"length": 30})
        await pattern_edit(lin, "ELin", [hole_part(-40 + 30 * k, -40) for k in range(3)], parameters={"occurrences": 3})
        await pattern_edit(lin, "ELin", [hole_part(-40, -40), hole_part(20, -40)], parameters={"occurrences": 2})
        await pattern_edit(lin, "ELin", [hole_part(-40, -40)], parameters={"reversed": True})
        await pattern_edit(lin, "ELin", [hole_part(-40 + 15 * k, -40) for k in range(3)],
                           parameters={"length": 30, "occurrences": 3})
        for expected, parameters in [("occurrences must be an integer >= 2", {"occurrences": 1}),
                                     ("occurrences must be an integer >= 2", {"occurrences": 2.5}),
                                     ("occurrences must be an integer >= 2", {"occurrences": "3"}),
                                     ("occurrences must be an integer >= 2", {"occurrences": True}),
                                     ("occurrences must not exceed 100", {"occurrences": 101}),
                                     ("must be positive", {"length": 0}),
                                     ("not editable for PartDesign::LinearPattern", {"angle": 90}),
                                     ("not editable for PartDesign::LinearPattern", {"second_length": 3})]:
            await edit_reject(lin, expected, "ELin", parameters=parameters)
        await undo()
        await feature("partdesign_mirrored", lin, plate_volume - 2 * pi * 20, feature_name="ELinHole", plane="XZ",
                      name="EMirror")
        await edit_reject(lin, "not editable for PartDesign::Mirrored", "EMirror", parameters={"reversed": True})
        await edit_reject(lin, "not editable for PartDesign::Mirrored", "EMirror", parameters={"occurrences": 3})
        await undo()
        await feature("partdesign_multi_transform", lin, plate_volume - 2 * pi * 20, feature_names=["ELinHole"],
                      transformations=[{"type": "mirrored", "plane": "XZ"}], name="EMulti")
        await edit_reject(lin, "not editable for PartDesign::MultiTransform", "EMulti", parameters={"occurrences": 3})
        await undo()

        polar = await new_body("EditPolarBody")
        await block(polar, "EPolarPlate", -50, -50, 50, 50, 20, symmetric=True)
        await circle("EPolarSketch", polar, -30, -30, 2, offset=10)
        await feature("partdesign_pocket", polar, plate_volume - pi * 20, sketch_name="EPolarSketch", length=5,
                      name="EPolarHole")
        radius_at = math.hypot(30, 30)

        def ring(step, count, sign=1):
            return [hole_part(radius_at * math.cos(math.radians(225 + sign * step * k)),
                              radius_at * math.sin(math.radians(225 + sign * step * k))) for k in range(count)]

        await feature("partdesign_polar_pattern", polar, plate_volume - 4 * pi * 20, feature_name="EPolarHole",
                      axis="Z", angle=90, occurrences=4, name="EPolar")
        await pattern_edit(polar, "EPolar", ring(20, 4), parameters={"angle": 60})
        await pattern_edit(polar, "EPolar", ring(90, 2), parameters={"occurrences": 2})
        await pattern_edit(polar, "EPolar", ring(30, 4, -1), parameters={"reversed": True})
        await edit_reject(polar, "must be positive and at most 360", "EPolar", parameters={"angle": 0})
        await edit_reject(polar, "must be positive and at most 360", "EPolar", parameters={"angle": 361})
        await edit_reject(polar, "occurrences must not exceed 100", "EPolar", parameters={"occurrences": 101})
        await edit_reject(polar, "not editable for PartDesign::PolarPattern", "EPolar", parameters={"length": 5})

        # Loft: two or more replacement profiles of the same Body.
        loft_foreign = await new_body("EditLoftForeign")
        await rect("EditLoftForeignSketch", loft_foreign, -3, -3, 3, 3)
        loft = await new_body("EditLoftBody")
        for index, offset in enumerate((0, 10, 20), 1):
            await rect(f"EL{index}", loft, -5, -5, 5, 5, offset=offset)
        await feature("partdesign_loft", loft, 1000, sketch_names=["EL1", "EL2"], ruled=True, name="ELoft")
        result, shape = await edit(loft, "ELoft", 2000, profile_names=["EL1", "EL2", "EL3"])
        near(bbox(shape), [-5, -5, 0, 5, 5, 20])
        await undo()
        result, shape = await edit(loft, "ELoft", 2000, profile_names=["EL1", "EL3"])
        near(bbox(shape), [-5, -5, 0, 5, 5, 20])
        await undo()
        for expected, arguments in [("at least two profiles", dict(profile_names=["EL1"])),
                                    ("must be distinct", dict(profile_names=["EL1", "EL1"])),
                                    ("must belong to the same Body", dict(profile_names=["EL1", "EditLoftForeignSketch"])),
                                    ("must be a Sketcher sketch", dict(profile_names=["EL1", "ELoft"])),
                                    ("not editable for PartDesign::AdditiveLoft", dict(parameters={"length": 3}))]:
            await edit_reject(loft, expected, "ELoft", **arguments)
        # File cycle: every audited body survives save/close/reopen; a second change works on the reopened document.
        bodies = sorted(item["name"] for item in await invoke("list_objects", doc_name=doc)
                        if item["type"] == "PartDesign::Body")
        def values(snapshot):  # Hole ReadOnly flags and enum choices depend on thread mode and are rebuilt on open
            copy = dict(snapshot)
            if "tip_properties" in copy:
                copy["tip_properties"] = [{key: value for key, value in item.items() if key not in ("writable", "status", "choices")}
                                          for item in copy["tip_properties"]
                                          if item["name"] not in ("ThreadFit", "ThreadClass")]
            return copy

        saved = {name: values(await snap(name)) for name in bodies}
        path = str(directory / f"{doc}.FCStd")
        await invoke("save_document_safe", doc_name=doc, path=path)
        await invoke("close_document_safe", doc_name=doc)
        documents.remove(doc)
        state["doc"] = doc = (await invoke("open_document", path=path))["name"]
        documents.append(doc)
        for name in bodies:
            same(values(await snap(name)), saved[name], name)
        await edit(dress, "EFillet", 8000 - fillet_removed(3, 20), parameters={"radius": 3})
        await undo()
        await pattern_edit(polar, "EPolar", ring(20, 4), parameters={"angle": 60})
        parts = drill_parts(20, 0, 0, 2, 10)
        await feature("partdesign_hole", "HoleBody", 32000 - sum(part[0] for part in parts), sketch_name="HoleOne",
                      diameter=4, depth=10, name="HoleReopened")
        top = (await select("ThickPad", "face", normal=[0, 0, 1]))["selection"]
        await feature("partdesign_thickness", "ThickBody", 8000 - 16 * 16 * 18, base_name="ThickPad", faces=[top],
                      value=2, name="ThickReopened")
        await invoke("save_document_safe", doc_name=doc, path=path, overwrite=True)
        failures = sum(1 for entry in transcript if entry.get("is_error"))
        return {"calls": len(transcript), "negative_checks": failures, "fcstd": path, "bodies": len(bodies)}
    finally:
        for document in reversed(documents):
            await invoke("close_document_safe", doc_name=document, discard_changes=True)
        (directory / "mcp-transcript.json").write_text(json.dumps(transcript, indent=2), encoding="utf-8")
        assert not json.loads((await call("get_status")).content[0].text)["documents"]


async def check_stage12b_part(session, call, directory):
    """V audit of Part primitives, booleans, dress-ups, transforms, N14 construction and N15 analysis through MCP only."""
    transcript = []
    documents = []
    state = {}
    pi = math.pi

    def decode(response):
        if response.structuredContent and "contract_version" in response.structuredContent:
            return response.structuredContent
        return json.loads(response.content[0].text)

    async def invoke(tool, **arguments):
        result = decode(await call(tool, **arguments))
        transcript.append({"tool": tool, "arguments": arguments, "result": result})
        if isinstance(result, dict) and "contract_version" in result:
            assert result["status"] == "success", result
            return result["data"]
        return result

    def same(actual, expected, path="$"):
        # Curved-shape bounding boxes come from a cached tessellation and drift slightly across recomputes.
        if isinstance(expected, float) or isinstance(actual, float):
            assert abs(actual - expected) <= (0.05 if "bounding_box" in path else 1e-7), (path, actual, expected)
        elif isinstance(expected, dict):
            assert isinstance(actual, dict) and set(actual) == set(expected), (path, actual, expected)
            for key in expected:
                same(actual[key], expected[key], f"{path}.{key}")
        elif isinstance(expected, list):
            assert isinstance(actual, list) and len(actual) == len(expected), (path, actual, expected)
            for index, (left, right) in enumerate(zip(actual, expected)):
                same(left, right, f"{path}[{index}]")
        else:
            assert actual == expected, (path, actual, expected)

    def near(actual, expected, tolerance=1e-6, label=""):
        assert len(actual) == len(expected) and all(abs(a - e) <= tolerance for a, e in zip(actual, expected)), (
            label, actual, expected)

    def close(actual, expected, tolerance=1e-6, label=""):
        assert abs(actual - expected) <= max(tolerance, tolerance * abs(expected)), (label, actual, expected)

    def bbox(measured):
        box = measured["bounding_box"]
        return [box["min"][axis] for axis in "xyz"] + [box["max"][axis] for axis in "xyz"]

    def com(measured):
        return [measured["center_of_mass"][axis] for axis in "xyz"]

    async def objects():
        return await invoke("list_objects", doc_name=state["doc"])

    async def names():
        return sorted(item["name"] for item in await objects())

    async def measure(obj):
        return await invoke("measure", doc_name=state["doc"], obj_name=obj)

    async def snap(*watch):
        snapshot = {"objects": await objects()}
        for obj in watch:
            measured = await measure(obj)
            snapshot[obj] = {key: measured[key] for key in ("volume", "area", "bounding_box", "center_of_mass")
                             if key in measured}
        return snapshot

    async def reject(tool, expected, *watch, **arguments):
        """The call must fail with `expected` in the message and leave objects, visibility and masses untouched."""
        before = await snap(*watch)
        response = await session.call_tool(tool, {"doc_name": state["doc"], **arguments})
        text = " ".join(getattr(content, "text", "") for content in response.content)
        transcript.append({"tool": tool, "arguments": arguments, "is_error": response.isError, "result": text})
        assert response.isError, (tool, arguments, text)
        assert expected in text, (tool, expected, text)
        same(await snap(*watch), before)
        return text

    async def mutate(tool, *watch, **arguments):
        """Run a mutation and prove Undo restores and Redo reapplies the exact object list and masses."""
        before = await snap(*watch)
        result = await invoke(tool, doc_name=state["doc"], **arguments)
        after = await snap(*watch)
        await invoke("undo", doc_name=state["doc"])
        same(await snap(*watch), before)
        await invoke("redo", doc_name=state["doc"])
        same(await snap(*watch), after)
        return result

    async def undo():
        await invoke("undo", doc_name=state["doc"])

    async def make(tool, *watch, volume=None, area=None, box=None, centroid=None, box_tol=1e-6, tol=1e-6, com_tol=None,
                   **arguments):
        """Create through `tool` (with Undo/Redo) and compare the result with the analytic oracle."""
        result = await mutate(tool, *watch, **arguments)
        measured = await measure(result["name"])
        if volume is not None:
            close(measured["volume"], volume, tol, f"{tool} volume")
            close(result["volume"], volume, tol, f"{tool} result volume")
        if area is not None:
            close(measured["area"], area, tol, f"{tool} area")
        if box is not None:
            near(bbox(measured), box, box_tol, f"{tool} bbox")
        if centroid is not None:
            near(com(measured), centroid, com_tol or max(tol, 1e-6), f"{tool} center of mass")
        return result, measured

    async def select(obj, kind, **filters):
        return await invoke("select_subelement", doc_name=state["doc"], obj_name=obj, kind=kind, filters=filters)

    async def listing(obj, kind, **filters):
        return (await invoke("list_subelements", doc_name=state["doc"], obj_name=obj, kind=kind, filters=filters))["items"]

    async def sketch(name, kind, plane="XY", offset=0, **parameters):
        await invoke("create_sketch", doc_name=state["doc"], name=name, plane=plane, offset=offset)
        tool = {"rect": "sketch_add_rectangle", "circle": "sketch_add_circle", "polygon": "sketch_add_polygon",
                "line": "sketch_add_line", "arc": "sketch_add_arc", "slot": "sketch_add_slot"}[kind]
        await invoke(tool, doc_name=state["doc"], sketch_name=name, **parameters)
        return name

    async def wire(source, closed=True, name=None, edge_filter=None):
        """Wire from all (or filtered) edges of a sketch/shape object, selections freshly queried."""
        items = await listing(source, "edge", **(edge_filter or {}))
        result = await invoke("part_wire", doc_name=state["doc"], obj_name=source,
                              edges=[item["selection"] for item in items], closed=closed, name=name or f"{source}W")
        return result["name"]

    async def profile(name, kind, closed=True, plane="XY", offset=0, **parameters):
        await sketch(name, kind, plane, offset, **parameters)
        return await wire(name, closed)

    async def face(wire_name, holes=None, name=None):
        arguments = dict(outer_wire_name=wire_name, name=name or f"{wire_name}F")
        if holes:
            arguments["hole_wire_names"] = holes
        return (await invoke("part_face", doc_name=state["doc"], **arguments))["name"]

    def rotation(rx, ry, rz):
        """Rows of Rz*Ry*Rx (X applied first), degrees."""
        a, b, c = (math.radians(value) for value in (rx, ry, rz))
        rx_m = [[1, 0, 0], [0, math.cos(a), -math.sin(a)], [0, math.sin(a), math.cos(a)]]
        ry_m = [[math.cos(b), 0, math.sin(b)], [0, 1, 0], [-math.sin(b), 0, math.cos(b)]]
        rz_m = [[math.cos(c), -math.sin(c), 0], [math.sin(c), math.cos(c), 0], [0, 0, 1]]

        def product(left, right):
            return [[sum(left[i][k] * right[k][j] for k in range(3)) for j in range(3)] for i in range(3)]

        return product(rz_m, product(ry_m, rx_m))

    def axis_rotation(axis, angle):
        length = math.sqrt(sum(value * value for value in axis))
        x, y, z = (value / length for value in axis)
        c, s = math.cos(math.radians(angle)), math.sin(math.radians(angle))
        return [[c + x * x * (1 - c), x * y * (1 - c) - z * s, x * z * (1 - c) + y * s],
                [y * x * (1 - c) + z * s, c + y * y * (1 - c), y * z * (1 - c) - x * s],
                [z * x * (1 - c) - y * s, z * y * (1 - c) + x * s, c + z * z * (1 - c)]]

    def apply(matrix, point):
        return [sum(matrix[i][j] * point[j] for j in range(3)) for i in range(3)]

    def box_corners(size, offset=(0, 0, 0)):
        return [[offset[0] + dx * size[0], offset[1] + dy * size[1], offset[2] + dz * size[2]]
                for dx in (0, 1) for dy in (0, 1) for dz in (0, 1)]

    def extent(points):
        return [min(point[axis] for point in points) for axis in range(3)] + [
            max(point[axis] for point in points) for axis in range(3)]

    def frustum(big, small, height):
        """Volume and centroid height (from the big end) of a round or square-area frustum given end widths."""
        return (height / 3 * (big ** 2 + big * small + small ** 2),
                height * (big ** 2 + 2 * big * small + 3 * small ** 2) / (4 * (big ** 2 + big * small + small ** 2)))

    assert not json.loads((await call("get_status")).content[0].text)["documents"], "Stage 12b needs an empty instance"
    try:
        state["doc"] = doc = (await invoke("create_document", name="MCP_Stage12b_Part"))["name"]
        documents.append(doc)
        other = (await invoke("create_document", name="MCP_Stage12b_Part_Other"))["name"]
        documents.append(other)
        await invoke("part_box", doc_name=other, name="ForeignBox", length=5, width=5, height=5)
        state["doc"] = doc

        # I27 primitives: analytic volume, bounding box and center of mass for every variant.
        def sector(radius, degrees):
            """Bounding box (x0, y0, x1, y1) and centroid distance factor of a circular sector from +X."""
            alpha = math.radians(degrees)
            angles = [0.0, alpha] + [k * pi / 2 for k in range(1, 5) if k * pi / 2 < alpha]
            xs = [0.0] + [radius * math.cos(angle) for angle in angles]
            ys = [0.0] + [radius * math.sin(angle) for angle in angles]
            return [min(xs), min(ys), max(xs), max(ys)]

        box, _ = await make("part_box", volume=24, box=[1, 2, 3, 3, 5, 7], centroid=[2, 3.5, 5], length=2, width=3,
                            height=4, x=1, y=2, z=3, name="PrimBox")
        assert box["num_faces"] == 6 and box["num_solids"] == 1 and box["shape_type"] == "Solid", box
        twin, _ = await make("part_box", volume=1, length=1, width=1, height=1, name="PrimBox")
        assert twin["name"] != "PrimBox", twin
        cylinder, _ = await make("part_cylinder", volume=12 * pi, box=[-1, -3, 2, 3, 1, 5], box_tol=0.02,
                                 centroid=[1, -1, 3.5], radius=2, height=3, x=1, y=-1, z=2, name="PrimCylinder")
        assert cylinder["num_faces"] == 3, cylinder
        for degrees in (1, 45, 90, 180, 270, 360):
            alpha = math.radians(degrees)
            volume = alpha / 2 * 4 * 3
            radial = 4 * 2 * math.sin(alpha / 2) / (3 * alpha) if degrees < 360 else 0.0
            x0, y0, x1, y1 = sector(2, degrees)
            await make("part_cylinder", volume=volume, box=[x0, y0, 0, x1, y1, 3], box_tol=0.02,
                       centroid=[radial * math.cos(alpha / 2), radial * math.sin(alpha / 2), 1.5],
                       radius=2, height=3, angle=degrees, name=f"PrimSector{degrees}")
        await make("part_sphere", volume=36 * pi, box=[-2, -1, 0, 4, 5, 6], box_tol=0.05, centroid=[1, 2, 3],
                   radius=3, x=1, y=2, z=3, name="PrimSphere")
        await make("part_cone", volume=12 * pi, box=[-3, -3, 0, 3, 3, 4], box_tol=0.02, centroid=[0, 0, 1],
                   radius1=3, radius2=0, height=4, name="PrimConePoint")
        await make("part_cone", volume=12 * pi, box=[-3, -3, 0, 3, 3, 4], box_tol=0.02, centroid=[0, 0, 3],
                   radius1=0, radius2=3, height=4, name="PrimConeInverted")
        volume, centroid = frustum(4, 2, 5)
        await make("part_cone", volume=pi * volume, box=[1, 2, 3, 9, 10, 8], box_tol=0.02,
                   centroid=[5, 6, 3 + centroid], radius1=4, radius2=2, height=5, x=5, y=6, z=3, name="PrimConeFrustum")
        await make("part_cone", volume=pi * 4 * 3, box=[-2, -2, 0, 2, 2, 3], box_tol=0.02, centroid=[0, 0, 1.5],
                   radius1=2, radius2=2, height=3, name="PrimConeCylinder")
        await make("part_torus", volume=2 * pi ** 2 * 10 * 4, box=[-12, -12, -2, 12, 12, 2], box_tol=0.08,
                   centroid=[0, 0, 0], radius1=10, radius2=2, name="PrimTorus")
        await make("part_torus", volume=2 * pi ** 2 * 2 * 4, box=[1, 2, 3, 9, 10, 7], box_tol=0.08,
                   centroid=[5, 6, 5], radius1=2, radius2=2, x=5, y=6, z=5, name="PrimTorusHorn")

        # Parametric edit with Undo/Redo: the primitive is a native object, not a static copy.
        result = await mutate("set_properties", cylinder["name"], obj_name=cylinder["name"],
                              values={"Radius": {"value": 3, "unit": "mm"}})
        close((await measure(cylinder["name"]))["volume"], 27 * pi, 1e-6, "edited cylinder")

        before = await names()
        for tool, expected, arguments in [
                ("part_box", "greater than 0", dict(length=0, width=1, height=1)),
                ("part_box", "greater than 0", dict(length=1, width=-1, height=1)),
                ("part_box", "greater than 0", dict(length=1, width=1, height=0)),
                ("part_cylinder", "greater than 0", dict(radius=0, height=1)),
                ("part_cylinder", "greater than 0", dict(radius=1, height=0)),
                ("part_cylinder", "greater than 0", dict(radius=1, height=-1)),
                ("part_cylinder", "greater than 0", dict(radius=1, height=1, angle=0)),
                ("part_cylinder", "greater than 0", dict(radius=1, height=1, angle=-10)),
                ("part_cylinder", "less than or equal to 360", dict(radius=1, height=1, angle=361)),
                ("part_sphere", "greater than 0", dict(radius=0)),
                ("part_sphere", "greater than 0", dict(radius=-2)),
                ("part_cone", "must not both be 0", dict(radius1=0, radius2=0, height=1)),
                ("part_cone", "greater than or equal to 0", dict(radius1=-1, radius2=1, height=1)),
                ("part_cone", "greater than 0", dict(radius1=2, radius2=1, height=0)),
                ("part_torus", "greater than 0", dict(radius1=0, radius2=1)),
                ("part_torus", "greater than 0", dict(radius1=5, radius2=0)),
                ("part_torus", "must not exceed radius1", dict(radius1=2, radius2=3))]:
            await reject(tool, expected, **arguments)
        assert await names() == before

        # I28 booleans: fuse/cut/common with overlap, nesting, contact and disjoint operands.
        async def cube(name, size, x=0, y=0, z=0):
            return (await invoke("part_box", doc_name=doc, name=name, length=size, width=size, height=size,
                                 x=x, y=y, z=z))["name"]

        a = await cube("BoolA", 10)
        b = await cube("BoolB", 10, 5, 5, 5)
        inner = await cube("BoolC", 4, 7, 7, 7)
        far = await cube("BoolFar", 2, 100)
        touch = await cube("BoolTouch", 10, 10)
        big = await cube("BoolBig", 20, -5, -5, -5)
        watch = (a, b, inner, far, touch, big)
        result, measured = await make("boolean_fuse", *watch, volume=1875, box=[0, 0, 0, 15, 15, 15],
                                      centroid=[7.5, 7.5, 7.5], obj_names=[a, b], name="BoolFuse2")
        assert result["quality"]["output"]["valid"] and result["num_solids"] == 1, result
        fuse2 = result["name"]
        visible = {item["name"]: item["visibility"] for item in await objects()}
        assert not visible[a] and not visible[b] and visible[fuse2], visible
        await make("boolean_fuse", *watch, volume=1875, box=[0, 0, 0, 15, 15, 15], centroid=[7.5, 7.5, 7.5],
                   obj_names=[a, b, inner], name="BoolFuse3")
        result, measured = await make("boolean_fuse", *watch, volume=1008, box=[0, 0, 0, 102, 10, 10],
                                      centroid=[(1000 * 5 + 8 * 101) / 1008, (1000 * 5 + 8 * 1) / 1008,
                                                (1000 * 5 + 8 * 1) / 1008], obj_names=[a, far], name="BoolFuseFar")
        assert result["num_solids"] == 2, result
        result, _ = await make("boolean_fuse", *watch, volume=2000, box=[0, 0, 0, 20, 10, 10],
                               centroid=[10, 5, 5], obj_names=[a, touch], name="BoolFuseTouch")
        assert result["num_solids"] == 1, result
        await make("boolean_cut", *watch, volume=875, box=[0, 0, 0, 10, 10, 10],
                   centroid=[(1000 * 5 - 125 * 7.5) / 875] * 3, base_name=a, tool_name=b, name="BoolCutOverlap")
        await make("boolean_cut", *watch, volume=1000, box=[0, 0, 0, 10, 10, 10], centroid=[5, 5, 5],
                   base_name=a, tool_name=far, name="BoolCutDisjoint")
        await make("boolean_cut", *watch, volume=64 - 27, box=[7, 7, 7, 11, 11, 11],
                   centroid=[(64 * 9 - 27 * 8.5) / 37] * 3, base_name=inner, tool_name=a, name="BoolCutClip")
        await make("boolean_common", *watch, volume=125, box=[5, 5, 5, 10, 10, 10], centroid=[7.5] * 3,
                   obj_names=[a, b], name="BoolCommon2")
        await make("boolean_common", *watch, volume=27, box=[7, 7, 7, 10, 10, 10], centroid=[8.5] * 3,
                   obj_names=[a, b, inner], name="BoolCommon3")
        await make("boolean_common", *watch, volume=1000, box=[0, 0, 0, 10, 10, 10], centroid=[5] * 3,
                   obj_names=[a, big], name="BoolCommonNested")

        # Round trip with a cylindrical tool: a through-hole with an analytic center of mass.
        tool = (await invoke("part_cylinder", doc_name=doc, name="BoolDrill", radius=2, height=20, x=3, y=4, z=-5))["name"]
        hole = pi * 4 * 10
        result, _ = await make("boolean_cut", *watch, tool, volume=1000 - hole, box=[0, 0, 0, 10, 10, 10],
                               box_tol=1e-6, centroid=[(5000 - hole * 3) / (1000 - hole),
                                                       (5000 - hole * 4) / (1000 - hole), 5],
                               base_name=a, tool_name=tool, name="BoolDrilled")
        drilled = result["name"]

        # Parametric: editing an operand recomputes the fuse; Undo/Redo covers the edit.
        await mutate("set_properties", a, fuse2, obj_name=a, values={"Length": {"value": 20, "unit": "mm"}})
        close((await measure(fuse2))["volume"], 2750, 1e-6, "fuse after operand edit")
        await mutate("set_properties", a, fuse2, obj_name=a, values={"Length": {"value": 10, "unit": "mm"}})
        close((await measure(fuse2))["volume"], 1875, 1e-6, "fuse after restoring operand")

        # Rejections: empty results, degenerate operand sets, wrong operand kinds; all roll back.
        await invoke("create_sketch", doc_name=doc, name="BoolSketch")
        await reject("boolean_cut", "must be different objects", *watch, base_name=a, tool_name=a, name="BadCut")
        await reject("boolean_cut", "tool covers the whole base", *watch, base_name=a, tool_name=big, name="BadCut")
        await reject("boolean_common", "share no volume", *watch, obj_names=[a, far], name="BadCommon")
        await reject("boolean_common", "share no volume", *watch, obj_names=[a, touch], name="BadCommon")
        await reject("boolean_common", "must be distinct", *watch, obj_names=[a, a], name="BadCommon")
        await reject("boolean_fuse", "must be distinct", *watch, obj_names=[a, a], name="BadFuse")
        await reject("boolean_fuse", "at least 2 items", *watch, obj_names=[a], name="BadFuse")
        await reject("boolean_common", "at least 2 items", *watch, obj_names=[a], name="BadCommon")
        await reject("boolean_fuse", "has no valid shape", *watch, obj_names=[a, "BoolSketch"], name="BadFuse")
        await reject("boolean_cut", "has no valid shape", *watch, base_name=a, tool_name="BoolSketch", name="BadCut")
        await reject("boolean_fuse", "not found", *watch, obj_names=[a, "NoSuchObject"], name="BadFuse")
        await reject("boolean_cut", "is not in", *watch, base_name=a, tool_name="ForeignBox", name="BadCut")

        # I29 part_fillet/part_chamfer: revision-checked edges only, analytic removed volume, parametric result.
        async def dressed_box(name, length=20, width=10, height=10):
            return (await invoke("part_box", doc_name=doc, name=name, length=length, width=width, height=height))["name"]

        async def edge(obj, **filters):
            return (await select(obj, "edge", **filters))["selection"]

        base = await dressed_box("DressBox")
        removed_fillet = lambda radius, length: (1 - pi / 4) * radius ** 2 * length
        # Single top-front edge along X (length 20), radius 2 and half the face width 5.
        for radius in (2, 5):
            volume = 2000 - removed_fillet(radius, 20)
            selection = await edge(base, position=[10, 0, 10])
            result, measured = await make("part_fillet", base, volume=volume, box=[0, 0, 0, 20, 10, 10],
                                          obj_name=base, edges=[selection], radius=radius, name=f"DressFillet{radius}")
            assert result["type"] == "Part::Fillet" and result["shape_valid"], result
            # Removed corner = square minus quarter disc; its centroid is u from both legs.
            corner = radius * (5 / 6 - pi / 4) / (1 - pi / 4)
            near(com(measured), [10, (5 * 2000 - removed_fillet(radius, 20) * corner) / volume,
                                 (5 * 2000 - removed_fillet(radius, 20) * (10 - corner)) / volume], 1e-6, "fillet center")
        selection = await edge(base, position=[10, 0, 10])
        size_volume = 2000 - 0.5 * 2 ** 2 * 20
        result, measured = await make("part_chamfer", base, volume=size_volume, box=[0, 0, 0, 20, 10, 10],
                                      obj_name=base, edges=[selection], size=2, name="DressChamfer")
        assert result["type"] == "Part::Chamfer", result
        # Chamfer center of mass: wedge centroid sits a third of the legs from the removed corner.
        wedge = 0.5 * 2 ** 2 * 20
        near(com(measured), [10, (5 * 2000 - wedge * (2 / 3)) / size_volume, (5 * 2000 - wedge * (10 - 2 / 3)) / size_volume],
             1e-6, "chamfer center")
        # Four parallel edges (no corner interaction): analytic for fillet and chamfer.
        parallel = [item["selection"] for item in await listing(base, "edge", axis=[1, 0, 0])]
        assert len(parallel) == 4
        result, _ = await make("part_fillet", base, volume=2000 - 4 * removed_fillet(1.5, 20), box=[0, 0, 0, 20, 10, 10],
                               obj_name=base, edges=parallel, radius=1.5, name="DressFillet4")
        parallel = [item["selection"] for item in await listing(base, "edge", axis=[1, 0, 0])]
        result, _ = await make("part_chamfer", base, volume=2000 - 4 * 0.5 * 1.5 ** 2 * 20, box=[0, 0, 0, 20, 10, 10],
                               obj_name=base, edges=parallel, size=1.5, name="DressChamfer4")
        # All twelve edges: rounded box (Minkowski) volume; chamfer bounded by the wedge union estimate.
        radius = 2
        inner = (16, 6, 6)
        rounded = (inner[0] * inner[1] * inner[2]
                   + 2 * radius * (inner[0] * inner[1] + inner[0] * inner[2] + inner[1] * inner[2])
                   + pi * radius ** 2 * sum(inner) + 4 / 3 * pi * radius ** 3)
        every = [item["selection"] for item in await listing(base, "edge")]
        assert len(every) == 12
        result, measured = await make("part_fillet", base, volume=rounded, box=[0, 0, 0, 20, 10, 10], centroid=[10, 5, 5],
                                      obj_name=base, edges=every, radius=2, name="DressFilletAll")
        assert result["num_faces"] == 26, result
        every = [item["selection"] for item in await listing(base, "edge")]
        result, measured = await make("part_chamfer", base, box=[0, 0, 0, 20, 10, 10], centroid=[10, 5, 5],
                                      obj_name=base, edges=every, size=2, name="DressChamferAll")
        assert 2000 - 0.5 * 4 * 160 <= measured["volume"] <= 2000 - 0.5 * 4 * 160 + 6 * 8 and result["num_faces"] == 26, result

        # Circular edge: Pappus volume of the removed fillet corner.
        can = (await invoke("part_cylinder", doc_name=doc, name="DressCan", radius=5, height=10))["name"]
        top = [item["selection"] for item in await listing(can, "edge", geometry_type="circle", position=[0, 0, 10])]
        assert len(top) == 1
        radius, fillet_radius = 5.0, 1.0
        ring = 2 * pi * (fillet_radius ** 2 * (radius - fillet_radius / 2) - pi * fillet_radius ** 2 / 4 * (radius - fillet_radius)
                         - fillet_radius ** 3 / 3)
        await make("part_fillet", can, volume=pi * 25 * 10 - ring, box=[-5, -5, 0, 5, 5, 10], box_tol=0.02,
                   obj_name=can, edges=top, radius=1, name="DressCanFillet")

        # Chained: a fillet result is itself a valid base for a further dress-up.
        filleted = (await invoke("part_fillet", doc_name=doc, obj_name=base, name="DressChainBase", radius=1,
                                 edges=[await edge(base, position=[10, 0, 10])]))["name"]
        second = await listing(filleted, "edge", position=[10, 10, 10])
        assert len(second) == 1
        result, measured = await make("part_chamfer", filleted, obj_name=filleted, edges=[second[0]["selection"]],
                                      size=1, name="DressChain")
        close(measured["volume"], 2000 - removed_fillet(1, 20) - 0.5 * 20, 1e-6, "chained chamfer")

        # Parametric: raising the base height lengthens the filleted body; Undo/Redo covers the edit.
        parametric = (await invoke("part_fillet", doc_name=doc, obj_name=base, name="DressParam", radius=2,
                                   edges=[await edge(base, position=[10, 0, 10])]))["name"]
        await mutate("set_properties", base, parametric, obj_name=base, values={"Height": {"value": 30, "unit": "mm"}})
        close((await measure(parametric))["volume"], 6000 - removed_fillet(2, 20), 1e-6, "parametric fillet")
        await mutate("set_properties", base, parametric, obj_name=base, values={"Height": {"value": 10, "unit": "mm"}})

        # Rejections: every one leaves objects, visibility and masses unchanged.
        watch = (base, can)
        good = await edge(base, position=[10, 0, 10])
        await reject("part_fillet", "may be too large", *watch, obj_name=base, edges=[good], radius=10, name="BadFillet")
        good = await edge(base, position=[10, 0, 10])
        await reject("part_fillet", "may be too large", *watch, obj_name=base, edges=[good], radius=11, name="BadFillet")
        good = await edge(base, position=[10, 0, 10])
        await reject("part_chamfer", "may be too large", *watch, obj_name=base, edges=[good], size=10, name="BadChamfer")
        good = await edge(base, position=[10, 0, 10])
        await reject("part_chamfer", "may be too large", *watch, obj_name=base, edges=[good], size=11, name="BadChamfer")
        for tool, key in (("part_fillet", "radius"), ("part_chamfer", "size")):
            for value in (0, -1):
                good = await edge(base, position=[10, 0, 10])
                await reject(tool, "greater than 0", *watch, obj_name=base, edges=[good], name="BadDress", **{key: value})
        good = await edge(base, position=[10, 0, 10])
        await reject("part_fillet", "must not contain duplicates", *watch, obj_name=base, edges=[good, good], radius=1, name="BadFillet")
        await reject("part_fillet", "at least 1 item", *watch, obj_name=base, edges=[], radius=1, name="BadFillet")
        for naked in ("Edge1", 1):
            await reject("part_fillet", "valid dictionary", *watch, obj_name=base, edges=[naked], radius=1, name="BadFillet")
            await reject("part_chamfer", "valid dictionary", *watch, obj_name=base, edges=[naked], size=1, name="BadChamfer")
        face_selection = (await select(base, "face", normal=[0, 0, 1]))["selection"]
        await reject("part_fillet", "different object or subelement kind", *watch, obj_name=base, edges=[face_selection],
                     radius=1, name="BadFillet")
        foreign = await edge(can, geometry_type="circle", position=[0, 0, 10])
        await reject("part_fillet", "different object or subelement kind", *watch, obj_name=base, edges=[foreign],
                     radius=1, name="BadFillet")
        stale = await edge(base, position=[10, 0, 10])
        await invoke("move_object", doc_name=doc, obj_name=can, dx=1)
        await reject("part_fillet", "Document changed", *watch, obj_name=base, edges=[stale], radius=1, name="BadFillet")
        await invoke("move_object", doc_name=doc, obj_name=can, dx=-1)
        good = await edge(base, position=[10, 0, 10])
        await reject("part_fillet", "is not in", *watch, obj_name="NoSuchObject", edges=[good], radius=1, name="BadFillet")

        # I30/I31 transforms: placements, relative moves, axis rotations, uniform scale and plane mirrors.
        size = (2, 3, 4)

        async def placed(name, offset=(0, 0, 0), angles=(0, 0, 0)):
            made = (await invoke("part_box", doc_name=doc, name=name, length=size[0], width=size[1], height=size[2]))["name"]
            if offset != (0, 0, 0) or angles != (0, 0, 0):
                await invoke("set_placement", doc_name=doc, obj_name=made, x=offset[0], y=offset[1], z=offset[2],
                             rx=angles[0], ry=angles[1], rz=angles[2])
            return made

        def expect_state(matrix, offset, points=None):
            corners = [[offset[i] + apply(matrix, corner)[i] for i in range(3)] for corner in box_corners(size)]
            center = [offset[i] + apply(matrix, [size[0] / 2, size[1] / 2, size[2] / 2])[i] for i in range(3)]
            return extent(corners), center

        async def check_pose(name, matrix, offset):
            measured = await measure(name)
            box, center = expect_state(matrix, offset)
            close(measured["volume"], 24, 1e-6, f"{name} volume")
            near(bbox(measured), box, 1e-6, f"{name} bbox")
            near(com(measured), center, 1e-6, f"{name} center")

        subject = await placed("XformBox")
        cases = [("translate", (1, 2, 3), (0, 0, 0)), ("rx90", (0, 0, 0), (90, 0, 0)), ("ry90", (0, 0, 0), (0, 90, 0)),
                 ("rz90", (0, 0, 0), (0, 0, 90)), ("rx90ry90", (0, 0, 0), (90, 90, 0)),
                 ("rx90rz90", (0, 0, 0), (90, 0, 90)), ("ry45rz45", (0, 0, 0), (0, 45, 45)),
                 ("combined", (1, 2, 3), (30, 40, 50)), ("negative", (-5, 6, -7), (-30, 200, -50)),
                 ("reset", (0, 0, 0), (0, 0, 0))]
        for label, offset, angles in cases:
            arguments = dict(obj_name=subject, x=offset[0], y=offset[1], z=offset[2],
                             rx=angles[0], ry=angles[1], rz=angles[2])
            result = await mutate("set_placement", subject, **arguments)
            await check_pose(subject, rotation(*angles), offset)
            quaternion = result["quaternion"]
            assert len(quaternion) == 4 and abs(sum(value * value for value in quaternion) - 1) < 1e-9, result
            near(result["position"], list(offset), 1e-9, f"{label} position")
            reread = (await invoke("get_properties", doc_name=doc, obj_name=subject, properties=["Placement"]))["properties"][0]["value"]
            near(reread["position"], list(offset), 1e-9, f"{label} reread position")
            near(reread["quaternion"], quaternion, 1e-9, f"{label} reread rotation")
        await invoke("set_placement", doc_name=doc, obj_name=subject, x=1, y=2, z=3, rx=30, ry=40, rz=50)

        # Relative moves compose; a zero move changes nothing.
        mover = await placed("XformMove")
        for delta in [(10, -5, 2), (0, 0, 0), (-3, 4, -5)]:
            await mutate("move_object", mover, obj_name=mover, dx=delta[0], dy=delta[1], dz=delta[2])
        await check_pose(mover, rotation(0, 0, 0), (7, -1, -3))

        # Rotations act about the object's own origin with a parent-frame axis and accumulate.
        turner = await placed("XformTurn", (10, -5, 2))
        matrix = rotation(0, 0, 0)
        for axis, angle in [((0, 0, 1), 90), ((1, 0, 0), 90), ((0, 1, 0), 90), ((1, 1, 0), 45), ((0, 0, 1), 0),
                            ((1, 2, 3), 33), ((0, 0, -1), 720), ((0, 0, 5), -45)]:
            await mutate("rotate_object", turner, obj_name=turner, axis_x=axis[0], axis_y=axis[1], axis_z=axis[2],
                         angle=angle)
            step = axis_rotation(axis, angle)
            matrix = [[sum(step[i][k] * matrix[k][j] for k in range(3)) for j in range(3)] for i in range(3)]
            await check_pose(turner, matrix, (10, -5, 2))

        # Scale: independent static copy about the global origin; the source is unchanged.
        origin_box = await placed("XformScaleSource", (10, 0, 0))
        for factor in (2, 0.5, 1, 3.25):
            result, measured = await make("scale_object", origin_box, volume=24 * factor ** 3,
                                          box=[10 * factor, 0, 0, 10 * factor + 2 * factor, 3 * factor, 4 * factor],
                                          centroid=[(10 + 1) * factor, 1.5 * factor, 2 * factor],
                                          obj_name=origin_box, factor=factor, name=f"XformScaled{str(factor).replace('.', '_')}")
            assert result["type"] == "Part::Feature" and result["num_solids"] == 1, result
            await check_pose(origin_box, rotation(0, 0, 0), (10, 0, 0))
        await invoke("scale_object", doc_name=doc, obj_name=origin_box, factor=2, name="XformScaleOfScale")
        result = await invoke("scale_object", doc_name=doc, obj_name=origin_box, factor=2)
        assert result["name"].startswith(f"{origin_box}_Scaled"), result

        # Mirror: parametric Part::Mirroring across XY, XZ and YZ (case-insensitive).
        mirrored_source = await placed("XformMirrorSource", (1, 2, 3))
        flips = {"XY": (1, 1, -1), "XZ": (1, -1, 1), "YZ": (-1, 1, 1), "xy": (1, 1, -1), "yz": (-1, 1, 1)}
        for plane, flip in flips.items():
            corners = [[corner[i] * flip[i] for i in range(3)] for corner in box_corners(size, (1, 2, 3))]
            result, measured = await make("mirror_object", mirrored_source, volume=24, box=extent(corners),
                                          centroid=[(offset + size[i] / 2) * flip[i] for i, offset in enumerate((1, 2, 3))],
                                          obj_name=mirrored_source, plane=plane, name=f"XformMirror{plane}")
            assert result["type"] == "Part::Mirroring", result
        mirror = (await invoke("mirror_object", doc_name=doc, obj_name=mirrored_source, plane="XY", name="XformMirrorLive"))["name"]
        await mutate("set_properties", mirrored_source, mirror, obj_name=mirrored_source,
                     values={"Length": {"value": 5, "unit": "mm"}})
        near(bbox(await measure(mirror)), [1, 2, -7, 6, 5, -3], 1e-6, "mirror follows source edit")
        await mutate("set_properties", mirrored_source, mirror, obj_name=mirrored_source,
                     values={"Length": {"value": 2, "unit": "mm"}})

        # Rejections: no object or placement may change.
        watch = (subject, mover, turner, origin_box, mirrored_source)
        await reject("rotate_object", "must be non-zero", *watch, obj_name=turner, axis_x=0, axis_y=0, axis_z=0, angle=30)
        for factor, expected in [(0, "greater than 0"), (-1, "greater than 0"), (1e6 + 1, "less than or equal to")]:
            await reject("scale_object", expected, *watch, obj_name=origin_box, factor=factor, name="BadScale")
        for plane in ("AB", "", "XYZ", "X", "ZZ"):
            await reject("mirror_object", "plane must be XY, XZ, or YZ", *watch, obj_name=mirrored_source,
                         plane=plane, name="BadMirror")
        await reject("set_placement", "is not in", *watch, obj_name="NoSuchObject", x=1)
        await reject("move_object", "is not in", *watch, obj_name="NoSuchObject", dx=1)
        await reject("rotate_object", "is not in", *watch, obj_name="NoSuchObject", axis_z=1, angle=10)
        await reject("scale_object", "is not in", *watch, obj_name="NoSuchObject", factor=2)
        await reject("mirror_object", "is not in", *watch, obj_name="NoSuchObject", plane="XY")
        await invoke("create_sketch", doc_name=doc, name="XformSketch")
        await reject("scale_object", "has no valid shape", *watch, obj_name="XformSketch", factor=2, name="BadScale")
        await reject("mirror_object", "has no valid shape", *watch, obj_name="XformSketch", plane="XY", name="BadMirror")

        # N14: wire, face with holes, extrusion, revolution, loft, sweep, shell and solid.
        outer = await profile("N14Outer", "rect", x1=0, y1=0, x2=10, y2=10)
        measured = await measure(outer)
        near(bbox(measured), [0, 0, 0, 10, 10, 0], 1e-9, "wire bbox")
        validation = await invoke("part_validate", doc_name=doc, obj_name=outer)
        assert validation["quality"]["closed"] and validation["quality"]["num_edges"] == 4, validation
        open_wire = await profile("N14Open", "line", closed=False, x1=0, y1=0, x2=10, y2=0)
        assert not (await invoke("part_validate", doc_name=doc, obj_name=open_wire))["quality"]["closed"]
        # Ordered edges of a solid: a connected open chain and a closed loop from the top face.
        block = (await invoke("part_box", doc_name=doc, name="N14Block", length=10, width=10, height=10))["name"]
        top_ring = [[0, 5, 10], [5, 10, 10], [10, 5, 10], [5, 0, 10]]

        async def ring_edges():
            return [(await select(block, "edge", position=position))["selection"] for position in top_ring]

        await invoke("part_wire", doc_name=doc, obj_name=block, edges=await ring_edges(), closed=True, name="N14Loop")
        near(bbox(await measure("N14Loop")), [0, 0, 10, 10, 10, 10], 1e-9, "loop bbox")
        chain = await mutate("part_wire", block, obj_name=block, edges=(await ring_edges())[:2], closed=False, name="N14Chain")
        assert chain["shape_type"] == "Wire" and not chain["closed"] and chain["num_edges"] == 2, chain

        # Face with holes: area oracle and containment rules.
        hole = await profile("N14Hole", "circle", cx=5, cy=5, radius=2)
        small = await profile("N14HoleSmall", "circle", cx=2, cy=2, radius=1)
        square_hole = await profile("N14HoleSquare", "rect", x1=7, y1=1, x2=9, y2=3)
        far = await profile("N14HoleFar", "circle", cx=50, cy=50, radius=2)
        cross = await profile("N14HoleCross", "circle", cx=10, cy=5, radius=2)
        huge = await profile("N14HoleHuge", "circle", cx=5, cy=5, radius=8)
        lifted = await profile("N14HoleLifted", "circle", offset=3, cx=5, cy=5, radius=2)
        vertical = await profile("N14HoleVertical", "circle", plane="XZ", cx=5, cy=5, radius=2)
        overlap = await profile("N14HoleOverlap", "circle", cx=3, cy=3, radius=1.5)
        watch = (outer,)
        plain, measured = await make("part_face", outer, area=100, box=[0, 0, 0, 10, 10, 0], centroid=[5, 5, 0],
                                     outer_wire_name=outer, name="N14Plain")
        assert plain["shape_type"] == "Face" and plain["num_wires"] == 1, plain
        await make("part_face", outer, area=100 - 4 * pi, centroid=[5, 5, 0], outer_wire_name=outer,
                   hole_wire_names=[hole], name="N14OneHole")
        await make("part_face", outer, area=100 - 4 * pi - pi, outer_wire_name=outer,
                   hole_wire_names=[hole, small], name="N14TwoHoles")
        two_squares, _ = await make("part_face", outer, area=100 - 4 * pi - 4, outer_wire_name=outer,
                                    hole_wire_names=[square_hole, hole], name="N14HoleMix")
        assert two_squares["num_wires"] == 3, two_squares
        hole_face = (await invoke("part_face", doc_name=doc, outer_wire_name=outer, hole_wire_names=[hole], name="N14HoleFace"))["name"]
        for label, arguments in [("far", dict(hole_wire_names=[far])), ("crossing", dict(hole_wire_names=[cross])),
                                 ("larger than outer", dict(hole_wire_names=[huge])),
                                 ("lifted plane", dict(hole_wire_names=[lifted])),
                                 ("vertical plane", dict(hole_wire_names=[vertical])),
                                 ("equal to outer", dict(hole_wire_names=[outer])),
                                 ("duplicate", dict(hole_wire_names=[hole, hole])),
                                 ("overlapping holes", dict(hole_wire_names=[hole, overlap]))]:
            await reject("part_face", "Hole wire must be coplanar and strictly inside the outer wire", outer,
                         outer_wire_name=outer, name="N14Bad", **arguments)
        await reject("part_face", "is not closed", outer, outer_wire_name=open_wire, name="N14Bad")
        await reject("part_face", "must be one of: Wire", outer, outer_wire_name=hole_face, name="N14Bad")
        await reject("part_face", "must be one of: Wire", outer, outer_wire_name=block, name="N14Bad")
        await reject("part_wire", "must not contain duplicates", block, obj_name=block, edges=["Edge1", "Edge1"], name="N14Bad")
        await reject("part_wire", "do not form a closed wire", open_wire, obj_name="N14Open", edges=[1], closed=True, name="N14Bad")
        await reject("part_wire", "Edge index out of range", block, obj_name=block, edges=["Edge99"], name="N14Bad")
        await reject("part_wire", "do not form a connected wire", block, obj_name=block, edges=["Edge1", "Edge8"], name="N14Bad")

        # Extrusion: prisms, shear, direction, surfaces; volume is meaningful for solids only.
        solid_face = plain["name"]
        await make("part_extrude", solid_face, volume=500, box=[0, 0, 0, 10, 10, 5], centroid=[5, 5, 2.5],
                   obj_name=solid_face, vector_x=0, vector_y=0, vector_z=5, name="N14Prism")
        await make("part_extrude", solid_face, volume=500, box=[0, 0, 0, 13, 10, 5], centroid=[6.5, 5, 2.5],
                   obj_name=solid_face, vector_x=3, vector_y=0, vector_z=5, name="N14Sheared")
        await make("part_extrude", solid_face, volume=500, box=[0, 0, -5, 10, 10, 0], centroid=[5, 5, -2.5],
                   obj_name=solid_face, vector_x=0, vector_y=0, vector_z=-5, name="N14Down")
        await make("part_extrude", outer, volume=500, box=[0, 0, 0, 10, 10, 5], centroid=[5, 5, 2.5],
                   obj_name=outer, vector_x=0, vector_y=0, vector_z=5, name="N14WirePrism")
        await make("part_extrude", hole_face, volume=(100 - 4 * pi) * 5, box=[0, 0, 0, 10, 10, 5], centroid=[5, 5, 2.5],
                   obj_name=hole_face, vector_x=0, vector_y=0, vector_z=5, name="N14HolePrism")
        surface, _ = await make("part_extrude", outer, area=200, box=[0, 0, 0, 10, 10, 5], obj_name=outer,
                                vector_x=0, vector_y=0, vector_z=5, solid=False, name="N14Walls")
        assert surface["num_solids"] == 0 and not surface["closed"] and surface["num_faces"] == 4, surface
        capped, _ = await make("part_extrude", solid_face, area=400, box=[0, 0, 0, 10, 10, 5], obj_name=solid_face,
                               vector_x=0, vector_y=0, vector_z=5, solid=False, name="N14Capped")
        assert capped["num_solids"] == 0 and capped["closed"], capped
        await make("part_extrude", open_wire, area=50, box=[0, 0, 0, 10, 0, 5], obj_name=open_wire,
                   vector_x=0, vector_y=0, vector_z=5, solid=False, name="N14Sheet")
        for tool, expected, arguments in [
                ("part_extrude", "must be non-zero", dict(obj_name=solid_face, vector_x=0, vector_y=0, vector_z=0)),
                ("part_extrude", "must not lie in the profile plane", dict(obj_name=solid_face, vector_x=5, vector_y=0, vector_z=0)),
                ("part_extrude", "requires a closed wire or face", dict(obj_name=open_wire, vector_x=0, vector_y=0, vector_z=5)),
                ("part_extrude", "has no area", dict(obj_name=open_wire, vector_x=5, vector_y=0, vector_z=0, solid=False)),
                ("part_extrude", "must be one of: Face, Wire", dict(obj_name=block, vector_x=0, vector_y=0, vector_z=5))]:
            await reject(tool, expected, outer, name="N14Bad", **arguments)

        # Revolution: Pappus volumes, sectors, off-origin axes and surfaces. XZ sketch y maps to global -Z.
        section_wire = await profile("N14Section", "rect", plane="XZ", x1=5, y1=-5, x2=10, y2=0)
        section_face = await face(section_wire, name="N14SectionFace")
        near(bbox(await measure(section_wire)), [5, 0, 0, 10, 0, 5], 1e-9, "revolve profile bbox")
        full = 375 * pi
        for source in (section_wire, section_face):
            await make("part_revolve", source, volume=full, box=[-10, -10, 0, 10, 10, 5], box_tol=0.02,
                       centroid=[0, 0, 2.5], obj_name=source, name=f"N14Full{source}")
        for degrees in (1, 90, 180, 270):
            alpha = math.radians(degrees)
            radial = 4 * math.sin(alpha / 2) / (3 * alpha) * (10 ** 3 - 5 ** 3) / (10 ** 2 - 5 ** 2)
            await make("part_revolve", section_wire, volume=full * degrees / 360, box_tol=0.02,
                       centroid=[radial * math.cos(alpha / 2), radial * math.sin(alpha / 2), 2.5],
                       obj_name=section_wire, angle=degrees, name=f"N14Sector{degrees}")
        await make("part_revolve", section_wire, volume=25 * 2 * pi * 12.5, centroid=[20, 0, 2.5], box_tol=0.02,
                   obj_name=section_wire, center_x=20, name="N14OffAxis")
        await make("part_revolve", section_wire, volume=pi * 25 * 5, centroid=[7.5, 0, 0], box_tol=0.02,
                   obj_name=section_wire, axis_x=1, axis_y=0, axis_z=0, name="N14XAxis")
        await make("part_revolve", section_wire, volume=pi * 25 * 5, centroid=[5, 0, 2.5], box_tol=0.02,
                   obj_name=section_wire, center_x=5, name="N14EdgeAxis")
        await make("part_revolve", section_wire, volume=full, centroid=[0, 0, 2.5], box_tol=0.02,
                   obj_name=section_wire, axis_z=7, name="N14LongAxis")
        await make("part_revolve", section_wire, area=300 * pi, box_tol=0.02, obj_name=section_wire,
                   solid=False, name="N14ShellRev")
        side_wire = await profile("N14SideLine", "line", closed=False, plane="XZ", x1=5, y1=-5, x2=5, y2=0)
        await make("part_revolve", side_wire, area=50 * pi, box_tol=0.02, obj_name=side_wire, solid=False, name="N14Tube")
        for tool, expected, arguments in [
                ("part_revolve", "must be in (0, 360]", dict(obj_name=section_wire, angle=0)),
                ("part_revolve", "must be in (0, 360]", dict(obj_name=section_wire, angle=361)),
                ("part_revolve", "must be in (0, 360]", dict(obj_name=section_wire, angle=-10)),
                ("part_revolve", "axis must be non-zero", dict(obj_name=section_wire, axis_x=0, axis_y=0, axis_z=0)),
                ("part_revolve", "Revolution failed", dict(obj_name=section_wire, center_x=7.5)),
                ("part_revolve", "has no volume", dict(obj_name=section_wire, axis_x=0, axis_y=1, axis_z=0)),
                ("part_revolve", "requires a closed wire or face", dict(obj_name=side_wire)),
                ("part_revolve", "must be one of: Face, Wire", dict(obj_name=block))]:
            await reject(tool, expected, section_wire, name="N14Bad", **arguments)

        # N14 loft: analytic frusta, quadratic smooth interpolation, surfaces, closed and invalid inputs.
        async def stack(prefix, kind, levels, **sizes):
            wires = []
            for index, (level, extent_value) in enumerate(levels):
                name = f"{prefix}{index}"
                if kind == "circle":
                    wires.append(await profile(name, "circle", offset=level, cx=0, cy=0, radius=extent_value))
                else:
                    wires.append(await profile(name, "rect", offset=level, x1=-extent_value, y1=-extent_value,
                                               x2=extent_value, y2=extent_value))
            return wires

        circles = await stack("LoftCircle", "circle", [(0, 2), (10, 1)])
        volume, centroid = frustum(2, 1, 10)
        for ruled in (False, True):
            await make("part_loft", *circles, volume=pi * volume, box=[-2, -2, 0, 2, 2, 10], box_tol=0.02,
                       centroid=[0, 0, centroid], section_names=circles, ruled=ruled, name=f"LoftCone{ruled}")
        shell_loft, _ = await make("part_loft", *circles, area=pi * 3 * math.sqrt(101), box_tol=0.02,
                                   section_names=circles, solid=False, name="LoftSurface")
        assert shell_loft["num_solids"] == 0 and not shell_loft["closed"], shell_loft
        await make("part_loft", *circles, volume=pi * volume, centroid=[0, 0, centroid], box_tol=0.02,
                   section_names=circles[::-1], name="LoftReversed")
        squares = await stack("LoftSquare", "rect", [(0, 5), (10, 3)])
        volume, centroid = frustum(10, 6, 10)
        await make("part_loft", *squares, volume=volume, box=[-5, -5, 0, 5, 5, 10], centroid=[0, 0, centroid],
                   section_names=squares, ruled=True, name="LoftFrustum")
        three = await stack("LoftThree", "rect", [(0, 5), (5, 3), (10, 5)])
        # Ruled: two frusta; smooth: quadratic half-width w(z) through (0,5),(5,3),(10,5) gives 4*integral(w^2).
        volume, centroid = frustum(10, 6, 5)
        await make("part_loft", *three, volume=2 * volume, box=[-5, -5, 0, 5, 5, 10], centroid=[0, 0, 5],
                   section_names=three, ruled=True, name="LoftRuled3")
        smooth_w = lambda z: 0.08 * z * z - 0.8 * z + 5
        steps = 2000
        smooth_volume = sum(4 * smooth_w((i + 0.5) * 10 / steps) ** 2 for i in range(steps)) * 10 / steps
        await make("part_loft", *three, volume=smooth_volume, box=[-5, -5, 0, 5, 5, 10], centroid=[0, 0, 5],
                   tol=1e-6, section_names=three, name="LoftSmooth3")
        bulge = await stack("LoftBulge", "circle", [(0, 2), (5, 4), (10, 2)])
        radius_at = lambda z: -0.08 * z * z + 0.8 * z + 2
        bulge_volume = pi * sum(radius_at((i + 0.5) * 10 / steps) ** 2 for i in range(steps)) * 10 / steps
        await make("part_loft", *bulge, volume=bulge_volume, box=[-4, -4, 0, 4, 4, 10], box_tol=0.02, centroid=[0, 0, 5],
                   tol=1e-6, com_tol=1e-4, section_names=bulge, name="LoftBulge3")
        round_to_square = [circles[0], squares[1]]
        result, measured = await make("part_loft", *round_to_square, section_names=round_to_square, name="LoftMixed")
        assert 10 * pi * 4 < measured["volume"] < 10 * 36 and result["num_solids"] == 1, measured
        ring = await stack("LoftRing", "rect", [(0, 5), (5, 3), (10, 5)])
        closed_loft, measured = await make("part_loft", *ring, section_names=ring, closed=True, name="LoftClosed")
        assert closed_loft["num_solids"] == 1 and closed_loft["closed"] and measured["volume"] > 0, closed_loft
        # Sections keep their Placement: lifting a wire with set_placement moves the loft.
        flat = await profile("LoftFlat", "rect", x1=-5, y1=-5, x2=5, y2=5)
        lifted = await profile("LoftLifted", "rect", x1=-5, y1=-5, x2=5, y2=5)
        await invoke("set_placement", doc_name=doc, obj_name=lifted, z=10)
        await make("part_loft", flat, lifted, volume=1000, box=[-5, -5, 0, 5, 5, 10], centroid=[0, 0, 5],
                   section_names=[flat, lifted], name="LoftPlacement")
        watch = tuple(circles)
        face_object = await face(squares[0], name="LoftFace")
        loft_open = await profile("LoftOpenLine", "line", closed=False, offset=10, x1=0, y1=0, x2=5, y2=0)
        for tool, expected, arguments in [
                ("part_loft", "Segments of a Loft/Pad do not have sufficient separation", dict(section_names=[circles[0], circles[0]])),
                ("part_loft", "Solid loft section", dict(section_names=[circles[0], loft_open])),
                ("part_loft", "closed loft requires at least three", dict(section_names=circles, closed=True)),
                ("part_loft", "at least 2 items", dict(section_names=[circles[0]])),
                ("part_loft", "must be one of: Wire", dict(section_names=[circles[0], face_object]))]:
            await reject(tool, expected, *watch, name="LoftBad", **arguments)

        # N14 sweep: Pappus volumes, mitre and round corners, frames and surfaces.
        straight = await profile("SweepStraight", "line", closed=False, plane="XZ", x1=0, y1=0, x2=0, y2=-10)
        corner = await profile("SweepCorner", "polygon", closed=False, plane="XZ", points=[[0, 0], [0, -10], [10, -10]], close=False)
        arc = await profile("SweepArc", "arc", closed=False, plane="XZ", cx=10, cy=0, radius=10,
                            start_angle=pi / 2, end_angle=pi)
        disc = await profile("SweepDisc", "circle", cx=0, cy=0, radius=1)
        rod = 10 * pi
        for frenet in (False, True):
            await make("part_sweep", disc, straight, volume=rod, box=[-1, -1, 0, 1, 1, 10], box_tol=0.02,
                       centroid=[0, 0, 5], profile_name=disc, path_name=straight, frenet=frenet, name=f"SweepRod{frenet}")
            await make("part_sweep", disc, arc, volume=pi * 10 * pi / 2, box_tol=0.02,
                       profile_name=disc, path_name=arc, frenet=frenet, name=f"SweepArc{frenet}")
            await make("part_sweep", disc, corner, volume=20 * pi, box=[-1, -1, 0, 10, 1, 11], box_tol=0.02,
                       profile_name=disc, path_name=corner, frenet=frenet, transition="right_corner",
                       name=f"SweepMitre{frenet}")
            await make("part_sweep", disc, corner, volume=20 * pi - (4 - pi) / 3, box=[-1, -1, 0, 10, 1, 11], box_tol=0.02,
                       profile_name=disc, path_name=corner, frenet=frenet, transition="round", name=f"SweepRound{frenet}")
        await make("part_sweep", disc, straight, area=20 * pi, box_tol=0.02, profile_name=disc, path_name=straight,
                   solid=False, name="SweepTube")
        await make("part_sweep", disc, arc, volume=pi * 10 * pi / 2, box_tol=0.02, profile_name=disc, path_name=arc,
                   transition="transformed", name="SweepArcTransformed")
        blade = await profile("SweepBlade", "rect", x1=-2, y1=-0.5, x2=2, y2=0.5)
        for transition in ("right_corner",):
            await make("part_sweep", blade, corner, volume=80, box_tol=0.02, profile_name=blade, path_name=corner,
                       transition=transition, name="SweepBlade")
        offset_disc = await profile("SweepMid", "circle", offset=4, cx=0, cy=0, radius=1)
        await make("part_sweep", offset_disc, straight, volume=rod, box=[-1, -1, 0, 1, 1, 10], box_tol=0.02,
                   profile_name=offset_disc, path_name=straight, name="SweepMidPath")
        band = await profile("SweepBand", "line", closed=False, x1=0, y1=0, x2=2, y2=0)
        await make("part_sweep", band, straight, area=20, box=[0, 0, 0, 2, 0, 10], profile_name=band, path_name=straight,
                   solid=False, name="SweepSheet")
        for tool, expected, arguments in [
                ("part_sweep", "requires a tangent-continuous path", dict(profile_name=disc, path_name=corner)),
                ("part_sweep", "requires a closed profile", dict(profile_name=band, path_name=straight)),
                ("part_sweep", "Sweep is degenerate", dict(profile_name=disc, path_name=disc)),
                ("part_sweep", "Input should be", dict(profile_name=disc, path_name=straight, transition="mitre")),
                ("part_sweep", "must be one of: Wire", dict(profile_name=disc, path_name=face_object))]:
            await reject(tool, expected, disc, name="SweepBad", **arguments)

        # N14 shell/solid: six cube faces, open shells, disconnected faces.
        def cube_faces():
            return [("ShellBottom", "XY", 0, 0, 0, 10, 10), ("ShellTop", "XY", 10, 0, 0, 10, 10),
                    ("ShellFront", "XZ", 0, 0, -10, 10, 0), ("ShellBack", "XZ", 10, 0, -10, 10, 0),
                    ("ShellLeft", "YZ", 0, -10, 0, 0, 10), ("ShellRight", "YZ", 10, -10, 0, 0, 10)]

        faces = []
        for name, plane, offset_value, x1, y1, x2, y2 in cube_faces():
            wire_name = await profile(name, "rect", plane=plane, offset=offset_value, x1=x1, y1=y1, x2=x2, y2=y2)
            faces.append(await face(wire_name, name=f"{name}Face"))
        shell, measured = await make("part_shell", *faces, area=600, box=[0, 0, 0, 10, 10, 10], face_names=faces, name="ShellCube")
        assert shell["shape_type"] == "Shell" and shell["closed"] and shell["num_shells"] == 1 and shell["num_faces"] == 6, shell
        solid_cube, measured = await make("part_solid", shell["name"], volume=1000, area=600, box=[0, 0, 0, 10, 10, 10],
                                          centroid=[5, 5, 5], shell_name=shell["name"], name="ShellSolid")
        assert solid_cube["num_solids"] == 1 and solid_cube["shape_type"] == "Solid", solid_cube
        open_shell, measured = await make("part_shell", *faces, area=500, face_names=faces[:5], name="ShellOpen")
        assert not open_shell["closed"] and open_shell["num_solids"] == 0, open_shell
        await make("part_shell", *faces, area=100, face_names=faces[:1], name="ShellSingle")
        duplicated, _ = await make("part_shell", *faces, area=600, face_names=faces + [faces[0]], name="ShellDuplicate")
        assert duplicated["closed"] and duplicated["num_faces"] == 6, duplicated
        for tool, expected, arguments in [
                ("part_shell", "do not form one connected shell", dict(face_names=[faces[0], faces[1]])),
                ("part_shell", "do not form one connected shell", dict(face_names=[faces[2], faces[3]])),
                ("part_shell", "must be one of: Face", dict(face_names=[faces[0], "ShellBottom"])),
                ("part_shell", "at least 1 item", dict(face_names=[])),
                ("part_solid", "is not closed", dict(shell_name=open_shell["name"])),
                ("part_solid", "must be one of: Shell", dict(shell_name=faces[0])),
                ("part_solid", "not found", dict(shell_name="NoSuchShell"))]:
            await reject(tool, expected, *faces[:2], name="ShellBad", **arguments)

        # N15 section, split, 2D/3D offsets, validation, refine, repair and sewing.
        async def cube(name, size, x=0, y=0, z=0):
            return (await invoke("part_box", doc_name=doc, name=name, length=size, width=size, height=size,
                                 x=x, y=y, z=z))["name"]

        a = await cube("N15A", 10)
        b = await cube("N15B", 10, 5, 5, 5)
        touch = await cube("N15Touch", 10, 10)
        far = await cube("N15Far", 2, 100)
        inner = (await invoke("part_sphere", doc_name=doc, name="N15Ball", radius=3, x=5, y=5, z=5))["name"]
        pin = (await invoke("part_cylinder", doc_name=doc, name="N15Pin", radius=3, height=20, x=5, y=5, z=-5))["name"]
        watch = (a, b, touch, far, inner, pin)

        # Section: boundary intersection curves only.
        result, _ = await make("part_section", *watch, box=[5, 5, 5, 10, 10, 10], first_name=a, second_name=b, name="N15Section")
        assert result["num_edges"] == 6 and result["num_solids"] == 0, result
        result, _ = await make("part_section", *watch, box=[10, 0, 0, 10, 10, 10], first_name=a, second_name=touch,
                               name="N15SectionTouch")
        assert result["num_edges"] == 4, result
        result, _ = await make("part_section", *watch, box=[2, 2, 0, 8, 8, 10], box_tol=0.02, first_name=a,
                               second_name=pin, name="N15SectionPin")
        assert result["num_edges"] == 2, result
        for second, expected in ((far, "do not produce section curves"), (inner, "do not produce section curves"),
                                 (a, "do not produce section curves")):
            await reject("part_section", expected, *watch, first_name=a, second_name=second, name="N15BadSection")

        # Split: part volumes are exact; planes are centered at plane_origin for any normal.
        for label, arguments, volumes in [
                ("plane_x2", dict(plane_origin=[2, 5, 5], plane_normal=[1, 0, 0]), [200, 800]),
                ("plane_center", dict(plane_origin=[5, 5, 5], plane_normal=[1, 0, 0]), [500, 500]),
                ("plane_diag_corner", dict(plane_origin=[3, 3, 5], plane_normal=[1, 1, 0]), [180, 820]),
                ("plane_diag_center", dict(plane_origin=[5, 5, 5], plane_normal=[1, 1, 1]), [500, 500]),
                ("plane_skew_center", dict(plane_origin=[5, 5, 5], plane_normal=[1, 2, 3]), [500, 500]),
                ("plane_scaled_normal", dict(plane_origin=[4, 5, 5], plane_normal=[0, 0, 100]), None),
                ("tool_box", dict(tool_name=b), [125, 875]),
                ("tool_ball", dict(tool_name=inner), [36 * pi, 1000 - 36 * pi])]:
            result, measured = await make("part_split", *watch, obj_name=a, name=f"N15Split{label}", **arguments)
            assert result["num_parts"] == 2 and result["shape_type"] == "Compound", result
            close(result["parts_volume"], 1000, 1e-9, label)
            close(measured["volume"], 1000, 1e-6, label)
            if volumes is not None:
                near(result["part_volumes"], sorted(volumes), 1e-6, f"{label} part volumes")
        # The hexagonal cut cap is one face shared by both parts: 6 cube faces split in two plus the shared cap.
        diag_split = await invoke("part_split", doc_name=doc, obj_name=a, name="N15SplitDiagFaces",
                                  plane_origin=[5, 5, 5], plane_normal=[1, 1, 1])
        assert diag_split["num_faces"] == 13 and diag_split["num_solids"] == 2, diag_split
        await undo()
        plane = dict(plane_origin=[5, 5, 5], plane_normal=[1, 0, 0])
        for expected, arguments in [
                ("Specify exactly one of tool_name or plane_normal", dict(tool_name=b, **plane)),
                ("Specify exactly one of tool_name or plane_normal", dict()),
                ("plane_normal must be non-zero", dict(plane_origin=[5, 5, 5], plane_normal=[0, 0, 0])),
                ("plane_origin must contain three coordinates", dict(plane_normal=[1, 0, 0])),
                ("plane_origin must contain three coordinates", dict(plane_origin=[1, 2], plane_normal=[1, 0, 0])),
                ("must cut through the solid", dict(plane_origin=[50, 5, 5], plane_normal=[1, 0, 0])),
                ("must cut through the solid", dict(plane_origin=[0, 0, 0], plane_normal=[1, 0, 0])),
                ("must cut through the solid", dict(tool_name=far))]:
            await reject("part_split", expected, *watch, obj_name=a, name="N15BadSplit", **arguments)
        sheet = await profile("N15Sheet", "rect", x1=0, y1=0, x2=10, y2=10)
        sheet_face = await face(sheet, name="N15SheetFace")
        await reject("part_split", "requires a source with at least one solid", *watch, obj_name=sheet_face,
                     plane_origin=[5, 5, 0], plane_normal=[1, 0, 0], name="N15BadSplit")

        # 2D offsets: perimeter bands have exact areas; collapse and unsupported joins are rejected.
        square = await profile("N15Square", "rect", x1=0, y1=0, x2=10, y2=10)
        circle_wire = await profile("N15Circle", "circle", cx=0, cy=0, radius=3)
        polyline = await profile("N15Polyline", "polygon", closed=False, points=[[0, 0], [10, 0], [10, 10]], close=False)
        for join, edges in (("arc", 8), ("tangent", 4), ("intersection", 4)):
            result, _ = await make("part_offset_2d", square, box=[-1, -1, 0, 11, 11, 0], box_tol=0.02,
                                   obj_name=square, distance=1, join=join, name=f"N15Offset{join}")
            assert result["shape_type"] == "Wire" and result["closed"] and result["num_edges"] == edges, result
            result, _ = await make("part_offset_2d", square, area=40 + pi if join == "arc" else 44,
                                   obj_name=square, distance=1, join=join, fill=True, name=f"N15Band{join}")
            assert result["shape_type"] == "Face", result
        for join in ("arc", "intersection"):
            result, _ = await make("part_offset_2d", square, box=[1, 1, 0, 9, 9, 0], area=None, obj_name=square,
                                   distance=-1, join=join, name=f"N15Inner{join}")
            assert result["closed"] and result["num_edges"] == 4, result
            await make("part_offset_2d", square, area=36, obj_name=square, distance=-1, join=join, fill=True,
                       name=f"N15InnerBand{join}")
        for join in ("arc", "tangent", "intersection"):
            await make("part_offset_2d", circle_wire, area=7 * pi, obj_name=circle_wire, distance=1, join=join,
                       fill=True, name=f"N15CircleOut{join}")
            await make("part_offset_2d", circle_wire, area=5 * pi, obj_name=circle_wire, distance=-1, join=join,
                       fill=True, name=f"N15CircleIn{join}")
        result, _ = await make("part_offset_2d", polyline, box=[-1, -1, 0, 11, 11, 0], box_tol=0.02, obj_name=polyline,
                               distance=1, name="N15OpenOffset")
        assert result["closed"], result
        triangle = await profile("N15Triangle", "polygon", points=[[0, 0], [10, 0], [1, 1]], close=True)
        for tool, expected, arguments in [
                ("part_offset_2d", "must be non-zero", dict(obj_name=square, distance=0)),
                ("part_offset_2d", "failed or collapsed the wire", dict(obj_name=square, distance=-5)),
                ("part_offset_2d", "failed or collapsed the wire", dict(obj_name=square, distance=-6)),
                ("part_offset_2d", "failed or collapsed the wire", dict(obj_name=circle_wire, distance=-3)),
                ("part_offset_2d", "failed or collapsed the wire", dict(obj_name=triangle, distance=1, join="tangent")),
                ("part_offset_2d", "Input should be", dict(obj_name=square, distance=1, join="miter")),
                ("part_offset_2d", "must be one of: Wire", dict(obj_name=a, distance=1))]:
            await reject(tool, expected, square, name="N15BadOffset", **arguments)

        # 3D offsets: Minkowski volumes; tangent joins are a documented kernel limitation.
        ball = (await invoke("part_sphere", doc_name=doc, name="N15OffsetBall", radius=5))["name"]
        can = (await invoke("part_cylinder", doc_name=doc, name="N15OffsetCan", radius=3, height=10))["name"]
        rounded = 1000 + 600 + 12 * 10 * pi / 4 + 4 / 3 * pi
        await make("part_offset_shape", a, volume=rounded, area=600 + 64 * pi, box=[-1, -1, -1, 11, 11, 11], centroid=[5, 5, 5],
                   obj_name=a, distance=1, join="arc", name="N15GrowArc")
        await make("part_offset_shape", a, volume=1728, area=864, box=[-1, -1, -1, 11, 11, 11], centroid=[5, 5, 5],
                   obj_name=a, distance=1, join="intersection", name="N15GrowIntersection")
        for join in ("arc", "intersection"):
            await make("part_offset_shape", a, volume=512, area=384, box=[1, 1, 1, 9, 9, 9], centroid=[5, 5, 5],
                       obj_name=a, distance=-1, join=join, name=f"N15Shrink{join}")
        for join in ("arc", "intersection"):
            await make("part_offset_shape", ball, volume=4 / 3 * pi * 343, box_tol=0.02, centroid=[0, 0, 0],
                       obj_name=ball, distance=2, join=join, name=f"N15BallOut{join}")
            await make("part_offset_shape", ball, volume=4 / 3 * pi * 27, box_tol=0.02, centroid=[0, 0, 0],
                       obj_name=ball, distance=-2, join=join, name=f"N15BallIn{join}")
        radius_value, grow, height = 3.0, 1.0, 10.0
        can_volume = (pi * (radius_value + grow) ** 2 * height + 2 * pi * radius_value ** 2 * grow
                      + 2 * (2 * pi * (radius_value + 4 * grow / (3 * pi)) * (pi * grow ** 2 / 4)))
        await make("part_offset_shape", can, volume=can_volume, box=[-4, -4, -1, 4, 4, 11], box_tol=0.02,
                   centroid=[0, 0, 5], obj_name=can, distance=1, name="N15CanOut")
        top_face = await invoke("part_face", doc_name=doc, outer_wire_name=square, name="N15OffsetFace")
        result, _ = await make("part_offset_shape", top_face["name"], area=100, box=[0, 0, 2, 10, 10, 2],
                               obj_name=top_face["name"], distance=2, name="N15FaceUp")
        assert result["shape_type"] == "Shell" and result["num_solids"] == 0, result
        await make("part_offset_shape", top_face["name"], volume=200, box=[0, 0, 0, 10, 10, 2], centroid=[5, 5, 1],
                   obj_name=top_face["name"], distance=2, fill=True, name="N15FaceSolid")
        for tool, expected, arguments in [
                ("part_offset_shape", "join='tangent' is not supported", dict(obj_name=a, distance=1, join="tangent")),
                ("part_offset_shape", "join='tangent' is not supported", dict(obj_name=top_face["name"], distance=1, join="tangent")),
                ("part_offset_shape", "failed or collapsed the shape", dict(obj_name=a, distance=-5)),
                ("part_offset_shape", "failed or collapsed the shape", dict(obj_name=a, distance=-6)),
                ("part_offset_shape", "failed or collapsed the shape", dict(obj_name=ball, distance=-6)),
                ("part_offset_shape", "fill=true is not supported", dict(obj_name=a, distance=1, fill=True)),
                ("part_offset_shape", "must be non-zero and tolerance positive", dict(obj_name=a, distance=0)),
                ("part_offset_shape", "must be non-zero and tolerance positive", dict(obj_name=a, distance=1, tolerance=0)),
                ("part_offset_shape", "Input should be", dict(obj_name=a, distance=1, join="miter")),
                ("part_offset_shape", "must be one of: Face, Shell, Solid", dict(obj_name=square, distance=1))]:
            await reject(tool, expected, a, ball, name="N15BadOffset", **arguments)

        # N15 validation, refine, repair and sewing.
        async def cube(name, size, x=0, y=0, z=0):
            return (await invoke("part_box", doc_name=doc, name=name, length=size, width=size, height=size,
                                 x=x, y=y, z=z))["name"]

        solid_box = await cube("N15VBox", 10)
        second = await cube("N15VSecond", 10, 30)
        two = (await invoke("boolean_fuse", doc_name=doc, obj_names=[solid_box, second], name="N15VTwo"))["name"]
        walls_wire = await profile("N15VWalls", "rect", x1=0, y1=0, x2=10, y2=10)
        walls = (await invoke("part_extrude", doc_name=doc, obj_name=walls_wire, vector_x=0, vector_y=0, vector_z=5,
                              solid=False, name="N15VOpenShell"))["name"]
        sheet = (await invoke("create_spreadsheet", doc_name=doc, name="N15VSheet"))["name"]
        line_sketch = await sketch("N15VLine", "line", x1=0, y1=0, x2=1, y2=0)
        before = await snap(solid_box, two, walls)
        report = await invoke("part_validate", doc_name=doc, obj_name=solid_box)
        quality = report["quality"]
        assert report["diagnostics"] == [] and quality["valid"] and quality["closed"], report
        assert (quality["num_faces"], quality["num_edges"], quality["num_vertices"], quality["num_solids"]) == (6, 12, 8, 1)
        close(quality["volume"], 1000, 1e-9, "validate volume")
        close(quality["area"], 600, 1e-9, "validate area")
        assert (await invoke("part_validate", doc_name=doc, obj_name=two))["diagnostics"] == ["multiple_solids"]
        report = await invoke("part_validate", doc_name=doc, obj_name=walls)
        assert report["diagnostics"] == ["open_shell"] and report["quality"]["valid"], report
        report = await invoke("part_validate", doc_name=doc, obj_name=sheet)
        assert report["diagnostics"] == ["object_has_no_shape"] and report["quality"]["null"], report
        report = await invoke("part_validate", doc_name=doc, obj_name=line_sketch)
        assert report["quality"]["valid"] and report["diagnostics"] == [], report
        await reject("part_validate", "is not in", solid_box, obj_name="NoSuchObject")
        await reject("part_validate", "is not in", solid_box, obj_name="ForeignBox")
        # validate is read-only: nothing changed.
        same(await snap(solid_box, two, walls), before)

        # Refine merges coplanar split faces; refining twice or refining a clean solid changes nothing.
        half = (await invoke("part_box", doc_name=doc, name="N15RHalf", length=5, width=10, height=10))["name"]
        other_half = (await invoke("part_box", doc_name=doc, name="N15ROther", length=5, width=10, height=10, x=5))["name"]
        fused = (await invoke("boolean_fuse", doc_name=doc, obj_names=[half, other_half], name="N15RFuse"))["name"]
        # Native fuses refine by default; disabling Refine exposes the splitter faces that part_refine merges.
        await invoke("set_properties", doc_name=doc, obj_name=fused, values={"Refine": False})
        faces_before = (await invoke("part_validate", doc_name=doc, obj_name=fused))["quality"]["num_faces"]
        assert faces_before == 10, faces_before  # two end faces plus four split side faces per half
        refined, measured = await make("part_refine", fused, volume=1000, area=600, box=[0, 0, 0, 10, 10, 10],
                                       centroid=[5, 5, 5], obj_name=fused, name="N15Refined")
        assert refined["before"]["num_faces"] == 10 and refined["after"]["num_faces"] == 6, refined
        assert refined["after"]["num_edges"] == 12 and refined["after"]["num_solids"] == 1, refined
        again = await invoke("part_refine", doc_name=doc, obj_name=refined["name"], name="N15RefinedAgain")
        assert again["before"]["num_faces"] == again["after"]["num_faces"] == 6, again
        clean, _ = await make("part_refine", solid_box, volume=1000, area=600, obj_name=solid_box, name="N15RefinedBox")
        assert clean["before"]["num_faces"] == clean["after"]["num_faces"] == 6, clean
        await reject("part_refine", "is not in", solid_box, obj_name="NoSuchObject", name="N15BadRefine")

        # Repair: a valid shape reports changed=false; tolerances are bounded; empty inputs are rejected.
        repaired, _ = await make("part_repair", solid_box, volume=1000, area=600, obj_name=solid_box, name="N15Repaired")
        assert repaired["changed"] is False and isinstance(repaired["native_fix_reported"], bool), repaired
        assert repaired["before"]["num_faces"] == repaired["after"]["num_faces"] == 6, repaired
        await make("part_repair", solid_box, volume=1000, obj_name=solid_box, tolerance=0.001, max_tolerance=1,
                   name="N15RepairedWide")
        for expected, arguments in [("0 < tolerance <= max_tolerance <= 1", dict(tolerance=0)),
                                    ("0 < tolerance <= max_tolerance <= 1", dict(tolerance=0.2, max_tolerance=0.1)),
                                    ("0 < tolerance <= max_tolerance <= 1", dict(max_tolerance=2)),
                                    ("0 < tolerance <= max_tolerance <= 1", dict(tolerance=-0.01)),
                                    ("has no valid shape", dict(obj_name=sheet)),
                                    ("is not in", dict(obj_name="NoSuchObject"))]:
            await reject("part_repair", expected, solid_box, **{"obj_name": solid_box, "name": "N15BadRepair", **arguments})

        # Sewing: coincident faces become a solid; gaps need a tolerance and stay open otherwise.
        async def cube_faces(prefix, top_inset=0.0, angle=0):
            parts = [("Bottom", "XY", 0, 0, 0, 10, 10), ("Top", "XY", 10, top_inset, top_inset, 10 - top_inset, 10 - top_inset),
                     ("Front", "XZ", 0, 0, -10, 10, 0), ("Back", "XZ", 10, 0, -10, 10, 0),
                     ("Left", "YZ", 0, -10, 0, 0, 10), ("Right", "YZ", 10, -10, 0, 0, 10)]
            faces = []
            for label, plane, offset_value, x1, y1, x2, y2 in parts:
                wire_name = await profile(f"{prefix}{label}", "rect", plane=plane, offset=offset_value,
                                          x1=x1, y1=y1, x2=x2, y2=y2)
                faces.append(await face(wire_name, name=f"{prefix}{label}Face"))
                if angle:
                    await invoke("set_placement", doc_name=doc, obj_name=faces[-1], rz=angle)
            return faces

        exact = await cube_faces("SewExact")
        sewed, _ = await make("part_sew", *exact, volume=1000, area=600, box=[0, 0, 0, 10, 10, 10], centroid=[5, 5, 5],
                              face_names=exact, name="SewExactSolid")
        assert sewed["num_solids"] == 1 and sewed["healing_mode"] == "native_sewing" and sewed["closed"], sewed
        open_sewed, _ = await make("part_sew", *exact, area=500, face_names=exact[:5], name="SewOpen")
        assert open_sewed["num_solids"] == 0 and not open_sewed["closed"] and open_sewed["num_shells"] == 1, open_sewed
        await make("part_sew", *exact, volume=1000, face_names=exact + [exact[0]], name="SewDuplicate")
        single, _ = await make("part_sew", *exact, area=100, face_names=exact[:1], name="SewSingle")
        assert single["shape_type"] == "Face", single
        apart, _ = await make("part_sew", *exact, area=200, face_names=exact[:2], name="SewDisjoint")
        assert apart["num_shells"] == 0 and apart["num_solids"] == 0, apart
        gapped = await cube_faces("SewGap", top_inset=0.005)
        open_gap, _ = await make("part_sew", *gapped, face_names=gapped, tolerance=0.001, name="SewGapOpen")
        assert open_gap["num_solids"] == 0 and not open_gap["closed"] and open_gap["healing_mode"] == "native_sewing", open_gap
        healed, _ = await make("part_sew", *gapped, volume=1000, area=600, box=[0, 0, 0, 10, 10, 10], centroid=[5, 5, 5],
                               face_names=gapped, tolerance=0.01, name="SewGapHealed")
        assert healed["num_solids"] == 1 and healed["healing_mode"] == "axis_aligned_planar_hexahedron", healed
        turned = await cube_faces("SewTurned", top_inset=0.005, angle=30)
        stays_open, _ = await make("part_sew", *turned, face_names=turned, tolerance=0.01, name="SewTurnedOpen")
        assert stays_open["num_solids"] == 0 and stays_open["healing_mode"] == "native_sewing", stays_open
        for expected, arguments in [("tolerance in (0, 1] mm", dict(face_names=exact, tolerance=0)),
                                    ("tolerance in (0, 1] mm", dict(face_names=exact, tolerance=-0.01)),
                                    ("tolerance in (0, 1] mm", dict(face_names=exact, tolerance=1.5)),
                                    ("must be one of: Face", dict(face_names=[exact[0], solid_box])),
                                    ("at least 1 item", dict(face_names=[])),
                                    ("not found", dict(face_names=[exact[0], "NoSuchFace"]))]:
            await reject("part_sew", expected, *exact[:2], name="SewBad", **arguments)

        # File cycle: every object survives save/close/reopen; parametric features still recompute afterwards.
        async def inventory():
            result = {}
            for item in await objects():
                entry = {"listing": item}
                if "shape_type" in item:
                    measured = await measure(item["name"])
                    entry["mass"] = {key: measured[key] for key in ("volume", "area", "bounding_box", "center_of_mass")
                                     if key in measured}
                result[item["name"]] = entry
            return result

        saved = await inventory()
        assert len(saved) > 300, len(saved)
        path = str(directory / f"{doc}.FCStd")
        await invoke("save_document_safe", doc_name=doc, path=path)
        await invoke("close_document_safe", doc_name=doc)
        documents.remove(doc)
        state["doc"] = doc = (await invoke("open_document", path=path))["name"]
        documents.append(doc)
        reopened = await inventory()
        assert sorted(reopened) == sorted(saved), sorted(set(reopened) ^ set(saved))
        for name in saved:
            same(reopened[name], saved[name], name)

        # Second change after reopening: native primitives, booleans, dress-ups and mirrors recompute.
        await mutate("set_properties", "BoolA", "BoolFuse2", obj_name="BoolA", values={"Length": {"value": 20, "unit": "mm"}})
        close((await measure("BoolFuse2"))["volume"], 2750, 1e-6, "fuse after reopen")
        await mutate("set_properties", "DressBox", "DressParam", obj_name="DressBox",
                     values={"Height": {"value": 30, "unit": "mm"}})
        close((await measure("DressParam"))["volume"], 6000 - (1 - pi / 4) * 4 * 20, 1e-6, "fillet after reopen")
        await mutate("set_properties", "XformMirrorSource", "XformMirrorLive", obj_name="XformMirrorSource",
                     values={"Length": {"value": 5, "unit": "mm"}})
        near(bbox(await measure("XformMirrorLive")), [1, 2, -7, 6, 5, -3], 1e-6, "mirror after reopen")
        await mutate("set_properties", "PrimCylinder", obj_name="PrimCylinder", values={"Height": {"value": 5, "unit": "mm"}})
        close((await measure("PrimCylinder"))["volume"], 45 * pi, 1e-6, "cylinder after reopen")
        await invoke("set_placement", doc_name=doc, obj_name="XformBox", x=4, y=5, z=6, rz=90)
        near(bbox(await measure("XformBox")), [4 - 3, 5, 6, 4, 5 + 2, 10], 1e-6, "placement after reopen")
        fresh = (await select("DressBox", "edge", position=[10, 0, 30]))["selection"]
        reopened_fillet, _ = await make("part_fillet", "DressBox", volume=6000 - (1 - pi / 4) * 4 * 20, obj_name="DressBox",
                                        edges=[fresh], radius=2, name="DressAfterReopen")
        await make("boolean_common", "BoolA", "BoolB", obj_names=["BoolA", "BoolB"], name="BoolAfterReopen")
        await invoke("save_document_safe", doc_name=doc, path=path, overwrite=True)
        failures = sum(1 for entry in transcript if entry.get("is_error"))
        return {"calls": len(transcript), "negative_checks": failures, "fcstd": path, "objects": len(saved)}

    finally:
        for document in reversed(documents):
            await invoke("close_document_safe", doc_name=document, discard_changes=True)
        (directory / "mcp-transcript.json").write_text(json.dumps(transcript, indent=2), encoding="utf-8")
        assert not json.loads((await call("get_status")).content[0].text)["documents"]


async def main():
    server_path = Path(os.environ.get("FREECAD_TEST_SERVER_PATH", str(ROOT / "src"))).resolve()
    environment = dict(os.environ, PYTHONPATH=str(server_path), PYTHONDONTWRITEBYTECODE="1")
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
            if "--stage12-only" in sys.argv or "--stage12-security-only" in sys.argv:
                directory = Path(tempfile.mkdtemp(prefix="freecad-stage12-mcp-"))
                report = {"success": False, "registered_tools": len(tools.tools), "gates": [],
                          "host_python": sys.executable, "python_version": sys.version, "os": platform.platform(),
                          "port": int(os.environ.get("FREECAD_TEST_PORT", "9876")), "server_path": str(server_path),
                          "server_sha256": hashlib.sha256((server_path / "freecad_mcp" / "server.py").read_bytes()).hexdigest(),
                          "capabilities": (await call("get_capabilities")).structuredContent["data"]}
                checks = [("normal_mode", check_stage12_security)]
                if "--stage12-only" in sys.argv:
                    checks += [("contracts", None), ("document_parameters", check_stage3),
                               ("geometry", check_stage4), ("sketcher", check_stage5),
                               ("partdesign", check_stage6), ("part", check_stage7),
                               ("A1", check_stage8_a1), ("A2", check_stage8_a2), ("A3", check_stage8_a3),
                               ("A4", check_stage9), ("techdraw_pages", check_stage10a),
                               ("A5", check_stage10b), ("draft", check_stage11a), ("mesh_exchange", check_stage11bc)]
                try:
                    for index in range(2):
                        for name, check in checks:
                            run_directory = directory / str(index + 1) / name
                            run_directory.mkdir(parents=True)
                            gate = {"run": index + 1, "id": name, "success": False, "directory": str(run_directory)}
                            report["gates"].append(gate)
                            if check is None:
                                gate["result"] = await check_contracts(session, call)
                            else:
                                gate["result"] = await check(session, call, run_directory)
                            if name == "techdraw_pages":
                                gate["render"] = check_stage10a_exports(run_directory, gate["result"]["final"]["views"])
                            gate["success"] = True
                            (directory / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
                            print(f"PASS run={index + 1} gate={name}", flush=True)
                    report["success"] = True
                except BaseException as error:
                    report["error"] = {"type": type(error).__name__, "message": str(error)}
                    raise
                finally:
                    (directory / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
                    print(f"Stage12 report: {directory / 'report.json'}", flush=True)
                return
            gates12b = {"--stage12b-sketcher-only": ("stage12b_sketcher", check_stage12b_sketcher),
                        "--stage12b-partdesign-a-only": ("stage12b_partdesign_a", check_stage12b_partdesign_a),
                        "--stage12b-partdesign-b-only": ("stage12b_partdesign_b", check_stage12b_partdesign_b),
                        "--stage12b-part-only": ("stage12b_part", check_stage12b_part)}
            selected12b = [option for option in gates12b if option in sys.argv]
            if selected12b:
                gate_id, gate = gates12b[selected12b[0]]
                prefix = "freecad-" + gate_id.replace("_", "-") + "-mcp-"
                directory = Path(tempfile.mkdtemp(prefix=prefix))
                capabilities = (await call("get_capabilities")).structuredContent["data"]
                assert not capabilities["features"]["raw_python_enabled"], capabilities
                report = {"success": False, "registered_tools": len(tools.tools), "runs": [], "capabilities": capabilities,
                          "directory": str(directory), "host_python": sys.executable, "python_version": sys.version,
                          "os": platform.platform(), "port": int(os.environ.get("FREECAD_TEST_PORT", "9876")),
                          "server_sha256": hashlib.sha256((server_path / "freecad_mcp" / "server.py").read_bytes()).hexdigest()}
                try:
                    for index in range(2):
                        run_directory = directory / str(index + 1)
                        run_directory.mkdir()
                        report["runs"].append(await gate(session, call, run_directory))
                        print(f"PASS run={index + 1} gate={gate_id}", flush=True)
                    report["success"] = True
                except BaseException as error:
                    report["error"] = {"type": type(error).__name__, "message": str(error)}
                    raise
                finally:
                    (directory / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
                    print(f"Stage12b {gate_id} report: {directory / 'report.json'}", flush=True)
                return
            if "--stage11bc-only" in sys.argv:
                directory = Path(tempfile.mkdtemp(prefix="freecad-stage11bc-mcp-"))
                runs = []
                capabilities = (await call("get_capabilities")).structuredContent["data"]
                assert not capabilities["features"]["raw_python_enabled"], capabilities
                assert capabilities["features"]["mesh_editing"] and capabilities["features"]["structured_exchange"], capabilities
                assert capabilities["options"]["step"]["schemas"] == ["AP214", "AP242"], capabilities
                for index in range(2):
                    run_directory = directory / str(index + 1)
                    run_directory.mkdir()
                    runs.append(await check_stage11bc(session, call, run_directory))
                report = {"success": True, "registered_tools": len(tools.tools), "runs": runs,
                          "capabilities": capabilities, "directory": str(directory), "host_python": sys.executable,
                          "python_version": sys.version, "os": platform.platform(),
                          "port": int(os.environ.get("FREECAD_TEST_PORT", "9876"))}
                (directory / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
                print(json.dumps({"success": True, "registered_tools": len(tools.tools), "runs": runs,
                                  "report": str(directory / "report.json"),
                                  "features": capabilities["features"], "step": capabilities["options"]["step"]}, indent=2))
                return
            if "--stage11a-only" in sys.argv:
                directory = Path(tempfile.mkdtemp(prefix="freecad-stage11a-mcp-"))
                runs = []
                capabilities = (await call("get_capabilities")).structuredContent["data"]
                assert not capabilities["features"]["raw_python_enabled"], capabilities
                assert capabilities["features"]["draft_modeling"], capabilities
                assert ".".join(capabilities["freecad_version"][:3]) in capabilities["options"]["draft"]["tested_versions"], capabilities
                for index in range(2):
                    run_directory = directory / str(index + 1)
                    run_directory.mkdir()
                    runs.append(await check_stage11a(session, call, run_directory))
                report = {"success": True, "registered_tools": len(tools.tools), "runs": runs,
                          "capabilities": capabilities, "directory": str(directory), "host_python": sys.executable,
                          "python_version": sys.version, "os": platform.platform(),
                          "port": int(os.environ.get("FREECAD_TEST_PORT", "9876"))}
                (directory / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
                print(json.dumps(report, indent=2))
                return
            if "--stage10b-only" in sys.argv:
                directory = Path(tempfile.mkdtemp(prefix="freecad-stage10b-mcp-"))
                runs = []
                capabilities = (await call("get_capabilities")).structuredContent["data"]
                assert not capabilities["features"]["raw_python_enabled"], capabilities
                assert capabilities["features"]["techdraw_drawings"], capabilities
                assert ".".join(capabilities["freecad_version"][:3]) in capabilities["options"]["techdraw_pages"]["tested_versions"], capabilities
                for index in range(2):
                    run_directory = directory / str(index + 1)
                    run_directory.mkdir()
                    runs.append(await check_stage10b(session, call, run_directory))
                report = {"success": True, "registered_tools": len(tools.tools), "runs": runs,
                          "capabilities": capabilities, "directory": str(directory), "host_python": sys.executable,
                          "python_version": sys.version, "os": platform.platform(),
                          "port": int(os.environ.get("FREECAD_TEST_PORT", "9876"))}
                (directory / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
                print(json.dumps(report, indent=2))
                return
            if "--stage10a-only" in sys.argv or "--stage10a-basic-only" in sys.argv:
                directory = Path(tempfile.mkdtemp(prefix="freecad-stage10a-mcp-"))
                runs = []
                for index in range(2):
                    run_directory = directory / str(index + 1)
                    run_directory.mkdir()
                    run = await check_stage10a(session, call, run_directory,
                                              verify_undo="--stage10a-basic-only" not in sys.argv)
                    if "--stage10a-render" in sys.argv:
                        run["export_verification"] = check_stage10a_exports(run_directory, run["final"]["views"])
                    runs.append(run)
                report = {"success": True, "registered_tools": len(tools.tools), "runs": runs,
                          "partial_only": "--stage10a-basic-only" in sys.argv,
                          "directory": str(directory), "host_python": sys.executable, "python_version": sys.version,
                          "os": platform.platform(), "port": int(os.environ.get("FREECAD_TEST_PORT", "9876")),
                          "capabilities": (await call("get_capabilities")).structuredContent["data"]}
                (directory / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
                print(json.dumps(report, indent=2))
                return
            if "--audit-only" in sys.argv:
                directory = Path(tempfile.mkdtemp(prefix="freecad-audit-mcp-"))
                result = await check_audit(session, call, directory)
                report = {"success": True, "registered_tools": len(tools.tools), "result": result,
                          "directory": str(directory), "host_python": sys.executable,
                          "python_version": sys.version, "port": int(os.environ.get("FREECAD_TEST_PORT", "9876"))}
                (directory / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
                print(json.dumps(report, indent=2))
                return
            if "--stage9-only" in sys.argv:
                directory = Path(tempfile.mkdtemp(prefix="freecad-stage9-mcp-"))
                runs = []
                for index in range(2):
                    run_directory = directory / str(index + 1)
                    run_directory.mkdir()
                    runs.append(await check_stage9(session, call, run_directory))
                report = {"success": True, "registered_tools": len(tools.tools), "runs": runs,
                          "host_python": sys.executable, "python_version": sys.version,
                          "os": platform.platform(), "port": int(os.environ.get("FREECAD_TEST_PORT", "9876")),
                          "capabilities": (await call("get_capabilities")).structuredContent["data"]}
                (directory / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
                print(json.dumps(report, indent=2))
                return
            if "--stage8-only" in sys.argv:
                directory = Path(tempfile.mkdtemp(prefix="freecad-stage8-mcp-"))
                runs = []
                for index in range(2):
                    run_directory = directory / str(index + 1)
                    run_directory.mkdir()
                    for name in ["a1", "a2", "a3"]:
                        (run_directory / name).mkdir()
                    runs.append({
                        "a1": await check_stage8_a1(session, call, run_directory / "a1"),
                        "a2": await check_stage8_a2(session, call, run_directory / "a2"),
                        "a3": await check_stage8_a3(session, call, run_directory / "a3"),
                    })
                report = {"success": True, "registered_tools": len(tools.tools), "runs": runs,
                          "host_python": sys.executable, "python_version": sys.version,
                          "os": platform.platform(), "port": int(os.environ.get("FREECAD_TEST_PORT", "9876"))}
                (directory / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
                print(json.dumps(report, indent=2))
                return
            if "--stage8-a1-only" in sys.argv:
                directory = Path(tempfile.mkdtemp(prefix="freecad-stage8-a1-mcp-"))
                result = await check_stage8_a1(session, call, directory)
                report = {"success": True, "registered_tools": len(tools.tools), "result": result,
                          "host_python": sys.executable, "python_version": sys.version,
                          "os": platform.platform(), "port": int(os.environ.get("FREECAD_TEST_PORT", "9876"))}
                (directory / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
                print(json.dumps(report, indent=2))
                return
            if "--stage8-a2-only" in sys.argv:
                directory = Path(tempfile.mkdtemp(prefix="freecad-stage8-a2-mcp-"))
                result = await check_stage8_a2(session, call, directory)
                report = {"success": True, "registered_tools": len(tools.tools), "result": result,
                          "host_python": sys.executable, "python_version": sys.version,
                          "os": platform.platform(), "port": int(os.environ.get("FREECAD_TEST_PORT", "9876"))}
                (directory / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
                print(json.dumps(report, indent=2))
                return
            if "--stage8-a3-only" in sys.argv:
                directory = Path(tempfile.mkdtemp(prefix="freecad-stage8-a3-mcp-"))
                result = await check_stage8_a3(session, call, directory)
                report = {"success": True, "registered_tools": len(tools.tools), "result": result,
                          "host_python": sys.executable, "python_version": sys.version,
                          "os": platform.platform(), "port": int(os.environ.get("FREECAD_TEST_PORT", "9876"))}
                (directory / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
                print(json.dumps(report, indent=2))
                return
            if "--stage7-only" in sys.argv:
                directory = Path(tempfile.mkdtemp(prefix="freecad-stage7-mcp-"))
                results = []
                for index in range(2):
                    run_directory = directory / str(index + 1)
                    run_directory.mkdir()
                    results.append(await check_stage7(session, call, run_directory))
                report = {"success": True, "registered_tools": len(tools.tools), "runs": results,
                          "host_python": sys.executable, "python_version": sys.version, "os": platform.platform(),
                          "port": int(os.environ.get("FREECAD_TEST_PORT", "9876")),
                          "capabilities": (await call("get_capabilities")).structuredContent["data"]}
                (directory / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
                print(json.dumps(report, indent=2))
                return
            if "--stage6-only" in sys.argv:
                directory = Path(tempfile.mkdtemp(prefix="freecad-stage6-mcp-"))
                results = []
                for index in range(2):
                    run_directory = directory / str(index + 1)
                    run_directory.mkdir()
                    results.append(await check_stage6(session, call, run_directory))
                report = {"success": True, "registered_tools": len(tools.tools), "runs": results,
                          "host_python": sys.executable, "python_version": sys.version, "os": platform.platform(),
                          "port": int(os.environ.get("FREECAD_TEST_PORT", "9876")),
                          "capabilities": (await call("get_capabilities")).structuredContent["data"]}
                (directory / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
                print(json.dumps(report, indent=2))
                return
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
                                              "dependency rejection and deletion rollback", "job reconnect/idempotency/failure/unknown",
                                              "paginated object overview", "cleanup"]}, indent=2))
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
                capabilities = (await call("get_capabilities")).structuredContent["data"]
                if capabilities["features"]["raw_python_enabled"]:
                    scripted = await call("execute_python", code="import math\nradius = 3\ndef area():\n    return math.pi * radius ** 2\nresult = area()")
                    assert abs(json.loads(scripted.content[0].text)["result"] - 28.2743338823) < 1e-8
                    python_check = "developer Python namespace"
                else:
                    scripted = await session.call_tool("execute_python", {"code": "result = 42"})
                    assert scripted.isError, scripted
                    assert "Raw Python is disabled" in str(scripted.content), scripted
                    python_check = "normal-mode raw Python rejection"
                print(json.dumps({"success": True, "registered_tools": len(tools.tools),
                                  "checked": ["stdio", "RPC", "Part fillet", "measure", "undo", "redo",
                                              "STEP", "STL", "OBJ", "MCP image", python_check]}, indent=2))
            finally:
                await call("close_document", name=document)


if __name__ == "__main__":
    asyncio.run(main())