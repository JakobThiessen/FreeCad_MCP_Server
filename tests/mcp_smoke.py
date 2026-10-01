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
    assert capabilities["data"]["bridge_api_version"] == "0.10.0"
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
        assert await invoke("assembly_inspect", doc_name=assembly_doc, assembly_name=assembly) == before_ground

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
        return {"calls": len(transcript), "fcstd": {key: str(path) for key, path in paths.items()},
                "step": str(step_path), "states": [(0, 0), (45, 10), (90, 20), (90, 15)],
                "joint_fixtures": ["fixed", "revolute", "slider", "cylindrical", "ball"],
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
                scripted = await call("execute_python", code="import math\nradius = 3\ndef area():\n    return math.pi * radius ** 2\nresult = area()")
                assert abs(json.loads(scripted.content[0].text)["result"] - 28.2743338823) < 1e-8
                print(json.dumps({"success": True, "registered_tools": len(tools.tools),
                                  "checked": ["stdio", "RPC", "Part fillet", "measure", "undo", "redo",
                                              "STEP", "STL", "OBJ", "MCP image", "Python namespace"]}, indent=2))
            finally:
                await call("close_document", name=document)


if __name__ == "__main__":
    asyncio.run(main())