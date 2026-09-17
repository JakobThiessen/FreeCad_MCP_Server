"""Bounded structured modeling batches executed entirely on the GUI thread."""

import inspect
import json
import math
import re

import FreeCAD

from freecad_ai_bridge.contracts import BridgeError, error_response
from freecad_ai_bridge.security import resolve_function
from freecad_ai_bridge.transactions import document_transaction


BATCH_OPERATIONS = {
    "part_box": ("part_ops", "make_box"),
    "part_cylinder": ("part_ops", "make_cylinder"),
    "part_sphere": ("part_ops", "make_sphere"),
    "part_cone": ("part_ops", "make_cone"),
    "part_torus": ("part_ops", "make_torus"),
    "move_object": ("part_ops", "move_object"),
    "set_placement": ("part_ops", "set_placement"),
    "boolean_cut": ("part_ops", "boolean_cut"),
    "part_fillet": ("part_ops", "part_fillet"),
    "part_chamfer": ("part_ops", "part_chamfer"),
    "delete_object": ("operations", "delete_object"),
}
REFERENCE_PARAMETERS = {"obj_name", "base_name", "tool_name"}


def _invalid(message):
    raise BridgeError("invalid_batch", message)


def _validate(steps, atomic):
    if type(atomic) is not bool or not isinstance(steps, list) or not 1 <= len(steps) <= 100:
        _invalid("Batch requires 1..100 steps and a boolean atomic flag")
    if len(json.dumps(steps, allow_nan=False).encode("utf-8")) > 65536:
        _invalid("Batch payload exceeds 65536 UTF-8 bytes")
    seen = {}
    planned = []
    for step in steps:
        if not isinstance(step, dict) or set(step) != {"id", "operation", "doc_name", "arguments"}:
            _invalid("Each step requires exactly id, operation, doc_name and arguments")
        step_id = step["id"]
        if not isinstance(step_id, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,63}", step_id) or step_id in seen:
            _invalid("Step IDs must be unique identifiers of 1..64 characters")
        operation = step["operation"]
        if not isinstance(operation, str) or operation not in BATCH_OPERATIONS:
            _invalid("Operation is not batch-allowlisted; lifecycle, file I/O, undo/redo and scripts are excluded")
        document = step["doc_name"]
        if not isinstance(document, str) or not document.strip():
            _invalid("Every step requires an explicit internal document name")
        arguments = step["arguments"]
        if not isinstance(arguments, dict) or "doc_name" in arguments:
            _invalid("arguments must be an object without doc_name; use the step's doc_name")
        module, function = BATCH_OPERATIONS[operation]
        module = "freecad_ai_bridge." + module
        target = resolve_function(module, function)
        signature = inspect.signature(target)
        try:
            bound = signature.bind(**arguments, doc_name=document)
        except TypeError as error:
            _invalid(str(error))
        for name, value in arguments.items():
            if isinstance(value, dict):
                if name not in REFERENCE_PARAMETERS or set(value) != {"$ref"} or not isinstance(value["$ref"], str):
                    _invalid("Only object-name arguments accept {'$ref': 'earlier_step_id'}")
                source = seen.get(value["$ref"])
                if source is None or source["doc_name"] != document or source["operation"] == "delete_object":
                    _invalid("Result references require an earlier same-document step returning name")
                continue
            expected = signature.parameters[name].annotation
            valid = ((expected is float and type(value) in {int, float} and math.isfinite(value))
                     or (expected is str and isinstance(value, str) and bool(value.strip()))
                     or (expected is list and isinstance(value, list)))
            if not valid:
                _invalid(f"Invalid type/value for {operation}.{name}")
            if name in {"length", "width", "height", "radius", "size"} and value <= 0:
                _invalid(f"{name} must be positive in mm")
            if name in {"radius1", "radius2"} and value < 0:
                _invalid(f"{name} must be nonnegative in mm")
            if name == "angle" and not 0 < value <= 360:
                _invalid("Cylinder angle must be in (0,360] deg")
            if name == "edges" and (not value or any(
                    not ((type(edge) is int and edge > 0) or (isinstance(edge, str) and re.fullmatch(r"Edge[1-9][0-9]*", edge)))
                    for edge in value)):
                _invalid("edges requires nonempty EdgeN or positive integer selections")
        bound.apply_defaults()
        planned.append((step, module, function, dict(bound.arguments)))
        seen[step_id] = step
    documents = {step["doc_name"] for step in steps}
    if atomic and len(documents) != 1:
        _invalid("Atomic batch requires exactly one existing document")
    for name in documents:
        doc = FreeCAD.listDocuments().get(name)
        if doc is None:
            raise BridgeError("document_not_found", f"Document '{name}' is not open", [{"document": name}])
        if doc.HasPendingTransaction:
            raise BridgeError("transaction_conflict", f"Document '{name}' has a foreign open transaction",
                              [{"document": name}])
    return planned


def run_batch(steps, atomic=True, preview=False):
    if type(preview) is not bool:
        _invalid("preview must be boolean")
    planned = _validate(steps, atomic)
    if preview:
        effects = []
        for step, module, function, arguments in planned:
            references = [{"document": step["doc_name"], "object": value}
                          for name, value in arguments.items() if name in REFERENCE_PARAMETERS and isinstance(value, str)]
            effects.append({"id": step["id"], "status": "planned", "operation": step["operation"],
                            "document": step["doc_name"], "references": references,
                            "effect": "delete leaf object" if function == "delete_object" else
                            "replace placement" if function == "set_placement" else
                            "move object" if function == "move_object" else
                            "create feature; source objects may be hidden"})
        return {"status": "preview", "atomic": atomic, "steps": effects,
                "warnings": ["No geometry executed; object existence, dependency and kernel failures may occur at execution."]}

    from freecad_ai_bridge.gui_executor import GuiExecutor

    executor = GuiExecutor()
    results = [{"id": step["id"], "status": "not_executed", "data": None, "error": None, "references": []} for step in steps]
    outputs = {}
    current = 0

    def execute_steps():
        nonlocal current
        for current, (step, module, function, arguments) in enumerate(planned):
            resolved = {name: outputs[value["$ref"]]["name"] if isinstance(value, dict) else value
                        for name, value in arguments.items()}
            doc = FreeCAD.listDocuments()[step["doc_name"]]
            if function == "delete_object":
                obj = doc.getObject(resolved["obj_name"])
                if obj is not None and obj.InList:
                    raise BridgeError("dependency_conflict", "Batch deletion is limited to unreferenced leaf objects",
                                      [{"document": doc.Name, "object": obj.Name}])
            data = executor._execute_function(module, function, json.dumps(resolved, allow_nan=False))
            outputs[step["id"]] = data
            name = data.get("name", data.get("deleted"))
            references = [{"document": step["doc_name"], "object": name}] if name else []
            results[current].update(status="succeeded", data=data, references=references)

    try:
        if atomic:
            doc = FreeCAD.listDocuments()[steps[0]["doc_name"]]
            with document_transaction(doc, "MCP: atomic batch"):
                executor._transaction_owner = doc
                execute_steps()
        else:
            execute_steps()
    except Exception as error:
        failure = error_response(error)["error_details"]
        results[current].update(status="failed", error=failure, data=None, references=failure["references"])
        if atomic:
            for result in results:
                if result["status"] == "succeeded":
                    result.update(status="rolled_back" if failure["state"] == "rolled_back" else "unknown", data=None, references=[])
        return {"status": "rolled_back" if atomic and failure["state"] == "rolled_back" else
                "partial" if not atomic and outputs else "error", "atomic": atomic, "steps": results,
                "error": failure, "warnings": []}
    finally:
        executor._transaction_owner = None
    return {"status": "succeeded", "atomic": atomic, "steps": results, "warnings": []}
