"""Explicit document editing operations; executed on the GUI thread."""

import math
import re
from pathlib import Path

import FreeCAD
import FreeCADGui

from freecad_ai_bridge.contracts import BridgeError


def _document(doc_name):
    if not isinstance(doc_name, str) or not doc_name.strip():
        raise BridgeError("invalid_arguments", "An explicit document Name is required")
    document = FreeCAD.listDocuments().get(doc_name)
    if document is None:
        raise BridgeError("document_not_found", f"Document '{doc_name}' is not open", [{"document": doc_name}])
    return document


def _object(doc_name, obj_name):
    document = _document(doc_name)
    if not isinstance(obj_name, str) or not obj_name.strip():
        raise BridgeError("invalid_arguments", "An explicit object Name is required")
    obj = document.getObject(obj_name)
    if obj is None:
        raise BridgeError("object_not_found", f"Object '{obj_name}' is not in '{doc_name}'",
                          [{"document": doc_name, "object": obj_name}])
    return obj


def _reference(obj):
    return {"document": obj.Document.Name, "object": obj.Name}


def _validate_document(document):
    invalid = [obj for obj in document.Objects if "Invalid" in obj.State]
    if invalid:
        raise BridgeError("recompute_failed", "Invalid objects after recompute: " +
                          "; ".join(f"{obj.Name}: {obj.getStatusString()}" for obj in invalid),
                          [_reference(obj) for obj in invalid])


def inspect_document(doc_name: str) -> dict:
    document = _document(doc_name)
    return {"reference": {"document": doc_name}, "label": document.Label,
            "file_name": document.FileName,
            "modified": bool(FreeCADGui.getDocument(doc_name).Modified),
            "active": FreeCAD.ActiveDocument is document,
            "pending_transaction": bool(document.HasPendingTransaction),
            "objects": [{"reference": _reference(obj), "type": obj.TypeId, "label": obj.Label,
                         "state": list(obj.State),
                         "members": [_reference(member) for member in obj.Group] if "Group" in obj.PropertiesList else None,
                         "tip": _reference(obj.Tip) if "Tip" in obj.PropertiesList and obj.Tip else None}
                        for obj in document.Objects]}


def activate_document(doc_name: str) -> dict:
    _document(doc_name)
    FreeCAD.setActiveDocument(doc_name)
    return {"reference": {"document": doc_name}, "active": True}


def recompute_document(doc_name: str) -> dict:
    document = _document(doc_name)
    document.recompute()
    _validate_document(document)
    return {"reference": {"document": doc_name}, "recomputed": True}


def save_document_safe(doc_name: str, path: str = None, overwrite: bool = False) -> dict:
    document = _document(doc_name)
    if type(overwrite) is not bool:
        raise BridgeError("invalid_arguments", "overwrite must be boolean")
    target = Path(path or document.FileName)
    if not (path or document.FileName) or not target.is_absolute() or target.suffix.lower() != ".fcstd":
        raise BridgeError("invalid_arguments", "An absolute .FCStd path is required")
    target = target.resolve()
    if target.exists() and not target.is_file():
        raise BridgeError("invalid_arguments", "Destination must be a regular file, not a directory")
    if target.exists() and not overwrite:
        raise BridgeError("file_exists", "Existing destination requires overwrite=true")
    if not target.parent.is_dir():
        raise BridgeError("invalid_arguments", "Destination directory does not exist")
    for other in FreeCAD.listDocuments().values():
        if other is not document and other.FileName and Path(other.FileName).resolve() == target:
            raise BridgeError("dependency_conflict", "Destination belongs to another open document")
    try:
        document.saveAs(str(target)) if path else document.save()
        if not target.is_file() or target.stat().st_size == 0:
            raise OSError("No complete output file was produced")
    except Exception as error:
        failure = BridgeError("file_write_failed", f"Save failed; inspect possible partial artifact at {target}: {error}",
                              [{"document": doc_name}])
        failure.bridge_state = "unknown"
        raise failure from error
    FreeCADGui.getDocument(doc_name).Modified = False
    return {"reference": {"document": doc_name}, "file_name": str(target), "bytes": target.stat().st_size}


def close_document_safe(doc_name: str, discard_changes: bool = False) -> dict:
    _document(doc_name)
    if type(discard_changes) is not bool:
        raise BridgeError("invalid_arguments", "discard_changes must be boolean")
    if FreeCADGui.getDocument(doc_name).Modified and not discard_changes:
        raise BridgeError("unsaved_changes", "Document has unsaved changes; save or explicitly discard")
    external = [source for obj in _document(doc_name).Objects for source in obj.InList
                if source.Document.Name != doc_name]
    if external:
        raise BridgeError("dependency_conflict", "Close dependent documents first", [_reference(obj) for obj in external])
    FreeCAD.closeDocument(doc_name)
    return {"closed": doc_name}


def create_container(doc_name: str, name: str, kind: str = "group") -> dict:
    types = {"group": "App::DocumentObjectGroup", "body": "PartDesign::Body"}
    if kind not in types or not isinstance(name, str) or not name.strip():
        raise BridgeError("invalid_arguments", "Expected a name and kind group or body")
    obj = _document(doc_name).addObject(types[kind], name)
    return {"reference": _reference(obj), "name": obj.Name, "type": obj.TypeId}


def set_container_members(doc_name: str, obj_name: str, members: list) -> dict:
    container = _object(doc_name, obj_name)
    if container.TypeId not in {"App::DocumentObjectGroup", "PartDesign::Body"}:
        raise BridgeError("invalid_arguments", "Expected a group or Body")
    if not isinstance(members, list) or len(members) > 100 or any(not isinstance(name, str) for name in members) or len(set(members)) != len(members):
        raise BridgeError("invalid_arguments", "members must contain at most 100 unique object Names")
    objects = [_object(doc_name, name) for name in members]
    for obj in objects:
        if obj is container or container in obj.OutListRecursive:
            raise BridgeError("dependency_cycle", "Container membership would create a cycle", [_reference(obj)])
        if container.TypeId == "PartDesign::Body":
            if not (obj.isDerivedFrom("PartDesign::Feature") or obj.isDerivedFrom("Sketcher::SketchObject")):
                raise BridgeError("invalid_arguments", "Body members must be PartDesign features or sketches")
            if any(parent.TypeId == "PartDesign::Body" and parent is not container for parent in obj.InList):
                raise BridgeError("dependency_conflict", "Remove member from its current Body first")
    if container.TypeId == "PartDesign::Body" and container.Tip and container.Tip not in objects:
        raise BridgeError("dependency_conflict", "Clear or change Tip before removing it")
    container.Group = objects
    return {"reference": _reference(container), "members": [_reference(obj) for obj in container.Group]}


def set_body_tip(doc_name: str, obj_name: str, tip_name: str = None) -> dict:
    body = _object(doc_name, obj_name)
    if body.TypeId != "PartDesign::Body":
        raise BridgeError("invalid_arguments", "Expected a PartDesign Body")
    tip = _object(doc_name, tip_name) if tip_name is not None else None
    if tip is not None and (tip not in body.Group or not tip.isDerivedFrom("PartDesign::Feature")):
        raise BridgeError("invalid_arguments", "Tip must be a PartDesign feature in this Body")
    body.Tip = tip
    return {"reference": _reference(body), "tip": _reference(tip) if tip else None}


_SCALARS = {"App::PropertyBool": bool, "App::PropertyInteger": int,
            "App::PropertyIntegerConstraint": int, "App::PropertyFloat": float,
            "App::PropertyFloatConstraint": float, "App::PropertyString": str,
            "App::PropertyEnumeration": str}
_QUANTITIES = {"App::PropertyQuantity", "App::PropertyLength", "App::PropertyDistance",
               "App::PropertyAngle", "App::PropertyArea", "App::PropertyVolume", "App::PropertySpeed",
               "App::PropertyAcceleration", "App::PropertyPressure", "App::PropertyForce"}
_LISTS = {"App::PropertyBoolList": "App::PropertyBool", "App::PropertyIntegerList": "App::PropertyInteger",
          "App::PropertyFloatList": "App::PropertyFloat", "App::PropertyStringList": "App::PropertyString",
          "App::PropertyVectorList": "App::PropertyVector", "App::PropertyPlacementList": "App::PropertyPlacement",
          "App::PropertyLinkList": "App::PropertyLink", "App::PropertyLinkSubList": "App::PropertyLinkSub"}
_SUPPORTED = set(_SCALARS) | _QUANTITIES | set(_LISTS) | {"App::PropertyVector", "App::PropertyPlacement",
                                                       "App::PropertyLink", "App::PropertyLinkSub"}
_MANAGED = {"Group", "Tip", "Origin", "ExpressionEngine", "Label", "LinkedObject"}


def _property(obj, name):
    if name not in obj.PropertiesList:
        raise BridgeError("property_not_found", f"Property '{name}' does not exist", [_reference(obj)])
    return obj.getTypeIdOfProperty(name)


def _writable(obj, name):
    kind = _property(obj, name)
    status = obj.getPropertyStatus(name)
    writable = not ("ReadOnly" in status or "Immutable" in status or "ReadOnly" in obj.getEditorMode(name))
    return kind in _SUPPORTED and writable and name not in _MANAGED


def _unit(value):
    return "*".join(base if exponent == 1 else f"{base}^{exponent}"
                    for base, exponent in zip(("mm", "kg", "s", "A", "K", "mol", "cd", "deg"), value.Unit.Signature)
                    if exponent)


def _encode(kind, value):
    if kind in _LISTS:
        return [_encode(_LISTS[kind], item) for item in value]
    if kind in _QUANTITIES:
        return {"value": value.Value, "unit": _unit(value)}
    if kind == "App::PropertyVector":
        return [value.x, value.y, value.z]
    if kind == "App::PropertyPlacement":
        return {"position": _encode("App::PropertyVector", value.Base), "quaternion": list(value.Rotation.Q)}
    if kind == "App::PropertyLink":
        return _reference(value) if value else None
    if kind == "App::PropertyLinkSub":
        return {"reference": _reference(value[0]), "subelements": list(value[1])} if value and value[0] else None
    return value


def get_properties(doc_name: str, obj_name: str, properties: list = None) -> dict:
    obj = _object(doc_name, obj_name)
    names = properties if properties is not None else obj.PropertiesList
    if not isinstance(names, list) or len(names) > 256:
        raise BridgeError("invalid_arguments", "Select at most 256 property Names")
    result = []
    for name in names:
        kind = _property(obj, name)
        supported = kind in _SUPPORTED
        value = getattr(obj, name) if supported else None
        result.append({"name": name, "type": kind, "supported": supported,
                       "writable": _writable(obj, name), "status": list(obj.getPropertyStatus(name)),
                       "unit": _unit(value) if kind in _QUANTITIES else None,
                       "choices": list(obj.getEnumerationsOfProperty(name)) if kind == "App::PropertyEnumeration" else [],
                       "value": _encode(kind, value) if supported else None})
    return {"reference": _reference(obj), "properties": result}


def _number(value):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise BridgeError("invalid_arguments", "Expected a finite JSON number, not a string or boolean")
    return value


def _vector(value, size=3):
    if not isinstance(value, list) or len(value) != size:
        raise BridgeError("invalid_arguments", f"Expected {size} coordinates")
    return [_number(component) for component in value]


def _link(owner, value):
    if not isinstance(value, dict) or set(value) != {"document", "object"}:
        raise BridgeError("invalid_arguments", "Link requires document and object Names")
    target = _object(value["document"], value["object"])
    if target.Document is not owner.Document:
        raise BridgeError("invalid_reference", "Property links must be in the same document; use create_link for external links")
    if target is owner or owner in target.OutListRecursive:
        raise BridgeError("dependency_cycle", "Link would create a dependency cycle", [_reference(target)])
    return target


def _decode(obj, name, kind, value):
    if kind in _LISTS:
        if not isinstance(value, list) or len(value) > 256:
            raise BridgeError("invalid_arguments", "Property list is limited to 256 entries")
        return [_decode(obj, name, _LISTS[kind], item) for item in value]
    if kind in _SCALARS:
        expected = _SCALARS[kind]
        if expected is float:
            return _number(value)
        if type(value) is not expected:
            raise BridgeError("invalid_arguments", f"Wrong value type for {kind}")
        if kind == "App::PropertyEnumeration" and value not in obj.getEnumerationsOfProperty(name):
            raise BridgeError("invalid_enum", "Value is not an available enumeration choice")
        return value
    if kind in _QUANTITIES:
        if not isinstance(value, dict) or set(value) != {"value", "unit"} or not isinstance(value["unit"], str):
            raise BridgeError("invalid_arguments", "Quantity requires numeric value and unit string")
        try:
            quantity = FreeCAD.Units.Quantity(f"{_number(value['value'])} {value['unit']}")
        except Exception as error:
            raise BridgeError("invalid_unit", "Invalid native quantity/unit") from error
        if quantity.Unit != getattr(obj, name).Unit:
            raise BridgeError("invalid_unit", "Quantity dimension does not match property")
        return quantity
    if kind == "App::PropertyVector":
        return FreeCAD.Vector(*_vector(value))
    if kind == "App::PropertyPlacement":
        if not isinstance(value, dict) or set(value) != {"position", "quaternion"}:
            raise BridgeError("invalid_arguments", "Placement requires position (mm) and quaternion [x,y,z,w] in parent coordinates")
        quaternion = _vector(value["quaternion"], 4)
        if abs(sum(component ** 2 for component in quaternion) - 1) > 1e-6:
            raise BridgeError("invalid_arguments", "Quaternion must have unit norm")
        return FreeCAD.Placement(FreeCAD.Vector(*_vector(value["position"])), FreeCAD.Rotation(*quaternion))
    if kind == "App::PropertyLink":
        return _link(obj, value) if value is not None else None
    if kind == "App::PropertyLinkSub":
        if value is None:
            return None
        if not isinstance(value, dict) or set(value) != {"reference", "subelements"}:
            raise BridgeError("invalid_arguments", "LinkSub requires reference and subelements")
        target = _link(obj, value["reference"])
        elements = value["subelements"]
        if not isinstance(elements, list) or not elements or len(elements) > 256:
            raise BridgeError("invalid_reference", "Select 1..256 subelements")
        for element in elements:
            if not isinstance(element, str) or not hasattr(target, "Shape"):
                raise BridgeError("invalid_reference", "Expected a shape subelement Name")
            try:
                shape = target.Shape.getElement(element)
                if shape.isNull():
                    raise ValueError("Null subelement")
            except Exception as error:
                raise BridgeError("invalid_reference", f"Invalid subelement '{element}'") from error
        return (target, elements)
    raise BridgeError("unsupported_property", f"Unsupported property type {kind}")


def set_properties(doc_name: str, obj_name: str, values: dict) -> dict:
    obj = _object(doc_name, obj_name)
    if not isinstance(values, dict) or not 1 <= len(values) <= 100:
        raise BridgeError("invalid_arguments", "values must contain 1..100 property/value pairs")
    decoded = {}
    for name, value in values.items():
        kind = _property(obj, name)
        if not _writable(obj, name):
            raise BridgeError("property_read_only", f"Property '{name}' is read-only, managed or unsupported", [_reference(obj)])
        if any(path == name or path.startswith(name + ".") for path, expression in obj.ExpressionEngine):
            raise BridgeError("expression_driven", f"Remove expression on '{name}' before assigning a value")
        decoded[name] = _decode(obj, name, kind, value)
    for name, value in decoded.items():
        setattr(obj, name, value)
        if _property(obj, name) in _SCALARS and getattr(obj, name) != value:
            raise BridgeError("invalid_arguments", f"Native property constraints rejected the requested value for '{name}'")
    obj.Document.recompute()
    _validate_document(obj.Document)
    return get_properties(doc_name, obj_name, list(values))


def _expression(expression):
    if not isinstance(expression, str) or not expression.strip() or len(expression) > 4096:
        raise BridgeError("invalid_expression", "Expected 1..4096 characters of arithmetic expression")
    if not re.fullmatch(r"[A-Za-z0-9_.$+*/^()\s-]+", expression) or re.search(r"[A-Za-z_]\w*\s*\(", expression):
        raise BridgeError("invalid_expression", "Only arithmetic, units and same-document cell/object references; no function calls")
    return expression


def get_expressions(doc_name: str, obj_name: str) -> dict:
    obj = _object(doc_name, obj_name)
    return {"reference": _reference(obj), "expressions": [{"property": path, "expression": expression}
                                                         for path, expression in obj.ExpressionEngine]}


def set_expression(doc_name: str, obj_name: str, property_name: str, expression: str = None) -> dict:
    obj = _object(doc_name, obj_name)
    if not isinstance(property_name, str) or not re.fullmatch(r"[A-Za-z_]\w*(?:\.[A-Za-z_]\w*|\[\d+\])*", property_name):
        raise BridgeError("invalid_arguments", "Invalid property path")
    root = re.split(r"[.\[]", property_name)[0]
    _property(obj, root)
    if root in _MANAGED or any(status in obj.getPropertyStatus(root) for status in ("ReadOnly", "Immutable")) or "ReadOnly" in obj.getEditorMode(root):
        raise BridgeError("property_read_only", "Expression target is read-only or managed", [_reference(obj)])
    if expression is not None:
        _expression(expression)
    try:
        obj.setExpression(property_name, expression)
        obj.Document.recompute()
        _validate_document(obj.Document)
    except Exception as error:
        raise BridgeError("invalid_expression", f"Expression failed: {error}", [_reference(obj)]) from error
    return get_expressions(doc_name, obj_name)


def create_spreadsheet(doc_name: str, name: str = "Parameters") -> dict:
    if not isinstance(name, str) or not name.strip():
        raise BridgeError("invalid_arguments", "Expected nonempty sheet Name")
    sheet = _document(doc_name).addObject("Spreadsheet::Sheet", name)
    return {"reference": _reference(sheet), "name": sheet.Name}


def _sheet(doc_name, obj_name):
    sheet = _object(doc_name, obj_name)
    if sheet.TypeId != "Spreadsheet::Sheet":
        raise BridgeError("invalid_arguments", "Expected a Spreadsheet::Sheet")
    return sheet


def _cell(address):
    if not isinstance(address, str) or not re.fullmatch(r"[A-Z]{1,2}[1-9][0-9]{0,4}", address):
        raise BridgeError("invalid_arguments", "Cell must be A1..ZZ99999 (uppercase)")
    return address


def _range(cell_range):
    if not isinstance(cell_range, str):
        raise BridgeError("invalid_arguments", "Expected A1 or A1:B2 range")
    bounds = cell_range.split(":")
    if len(bounds) not in (1, 2):
        raise BridgeError("invalid_arguments", "Expected A1 or A1:B2 range")
    coords = []
    for address in bounds:
        _cell(address)
        letters, row = re.fullmatch(r"([A-Z]+)(\d+)", address).groups()
        column = 0
        for letter in letters:
            column = column * 26 + ord(letter) - 64
        coords.append((column, int(row)))
    left, top = coords[0]
    right, bottom = coords[-1]
    if right < left or bottom < top or (right - left + 1) * (bottom - top + 1) > 256:
        raise BridgeError("invalid_arguments", "Range must be ordered and contain at most 256 cells")
    cells = []
    for row in range(top, bottom + 1):
        for column in range(left, right + 1):
            prefix, suffix = divmod(column - 1, 26)
            letters = (chr(64 + prefix) if prefix else "") + chr(65 + suffix)
            cells.append(f"{letters}{row}")
    return cells


def read_spreadsheet(doc_name: str, obj_name: str, cell_range: str) -> dict:
    sheet = _sheet(doc_name, obj_name)
    nonempty = set(sheet.getNonEmptyCells())
    cells = []
    for address in _range(cell_range):
        value = sheet.get(address) if address in nonempty else None
        if hasattr(value, "Unit"):
            value = {"value": value.Value, "unit": _unit(value)}
        if value is not None and not isinstance(value, (str, int, float, bool, dict)):
            raise BridgeError("unsupported_property", "Cell value cannot be represented as a typed scalar")
        cells.append({"address": address, "content": sheet.getContents(address) if address in nonempty else "",
                      "alias": sheet.getAlias(address) or None, "value": value})
    return {"reference": _reference(sheet), "cells": cells}


def set_spreadsheet_cells(doc_name: str, obj_name: str, cells: dict) -> dict:
    sheet = _sheet(doc_name, obj_name)
    if not isinstance(cells, dict) or not 1 <= len(cells) <= 256:
        raise BridgeError("invalid_arguments", "Expected 1..256 cell/content pairs; null clears a cell")
    for address, content in cells.items():
        _cell(address)
        if content is not None:
            if not isinstance(content, str) or len(content) > 4096:
                raise BridgeError("invalid_arguments", "Cell content must be a string up to 4096 characters or null")
            stripped = content.lstrip()
            if stripped.startswith("="):
                _expression(stripped[1:])
    try:
        for address, content in cells.items():
            sheet.clear(address) if content is None else sheet.set(address, content)
        sheet.Document.recompute()
        _validate_document(sheet.Document)
    except Exception as error:
        raise BridgeError("invalid_expression", f"Spreadsheet edit failed: {error}", [_reference(sheet)]) from error
    return {"reference": _reference(sheet), "cells": [read_spreadsheet(doc_name, obj_name, address)["cells"][0]
                                                     for address in cells]}


def set_spreadsheet_alias(doc_name: str, obj_name: str, cell: str, alias: str = None) -> dict:
    sheet = _sheet(doc_name, obj_name)
    _cell(cell)
    if alias is not None:
        if not isinstance(alias, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", alias) or re.fullmatch(r"[A-Za-z]{1,2}\d+", alias):
            raise BridgeError("invalid_alias", "Alias must be an identifier, not a cell address")
        existing = sheet.getCellFromAlias(alias)
        if existing and existing != cell:
            raise BridgeError("invalid_alias", "Alias already belongs to another cell")
    try:
        sheet.setAlias(cell, alias or "")
        sheet.Document.recompute()
        _validate_document(sheet.Document)
    except Exception as error:
        raise BridgeError("invalid_alias", f"Alias edit failed: {error}", [_reference(sheet)]) from error
    return read_spreadsheet(doc_name, obj_name, cell)


def rename_object(doc_name: str, obj_name: str, label: str) -> dict:
    obj = _object(doc_name, obj_name)
    if not isinstance(label, str) or not label.strip() or len(label) > 256:
        raise BridgeError("invalid_arguments", "Label must contain 1..256 characters")
    obj.Label = label
    return {"reference": _reference(obj), "name": obj.Name, "label": obj.Label}


def get_dependencies(doc_name: str, obj_name: str) -> dict:
    obj = _object(doc_name, obj_name)
    return {"reference": _reference(obj), "dependencies": [_reference(target) for target in obj.OutList],
            "dependents": [_reference(target) for target in obj.InList],
            "affected": [_reference(target) for target in obj.InListRecursive],
            "warnings": ["Dependency graph only; geometric success of a proposed change is not predicted."]}


def copy_object(doc_name: str, obj_name: str) -> dict:
    obj = _object(doc_name, obj_name)
    document = obj.Document
    before = {item.Name for item in document.Objects}
    if obj.TypeId == "App::Link":
        raise BridgeError("invalid_arguments", "Copy the source object, not an App::Link")
    copied = document.copyObject(obj, True)
    created = [item for item in document.Objects if item.Name not in before]
    if any(target.Document is not document or target.Name in before
           for item in created for target in item.OutList):
        raise BridgeError("dependency_conflict", "Native copy retained source dependencies; independent copy rejected")
    document.recompute()
    _validate_document(document)
    return {"reference": _reference(copied), "name": copied.Name,
            "references": [_reference(item) for item in created], "independent": True}


def create_link(doc_name: str, name: str, source_document: str, source_object: str) -> dict:
    document = _document(doc_name)
    source = _object(source_document, source_object)
    if not isinstance(name, str) or not name.strip():
        raise BridgeError("invalid_arguments", "Expected a nonempty link Name")
    if source.Document is not document:
        if not source.Document.FileName or not document.FileName:
            raise BridgeError("invalid_reference", "Save both source and owner documents before creating an external link")
        if source.Document.HasPendingTransaction:
            raise BridgeError("transaction_conflict", "Source document has a foreign pending transaction")
        if any(target.Document is document for target in source.OutListRecursive):
            raise BridgeError("dependency_cycle", "External link would introduce a document dependency cycle")
    link = document.addObject("App::Link", name)
    link.setLink(source)
    return {"reference": _reference(link), "name": link.Name, "source": _reference(source),
            "warnings": ["External source file must remain available and be saved separately."] if source.Document is not document else []}


def _deletion_set(doc_name, obj_names):
    if not isinstance(obj_names, list) or not 1 <= len(obj_names) <= 100 or any(not isinstance(name, str) for name in obj_names) or len(set(obj_names)) != len(obj_names):
        raise BridgeError("invalid_arguments", "Select 1..100 unique object Names")
    pending = [_object(doc_name, name) for name in obj_names]
    objects = {}
    while pending:
        obj = pending.pop()
        key = (obj.Document.Name, obj.Name)
        if key in objects:
            continue
        objects[key] = obj
        pending.extend(obj.InList)
        if "Group" in obj.PropertiesList:
            pending.extend(obj.Group)
        if "Origin" in obj.PropertiesList and obj.Origin:
            pending.append(obj.Origin)
        if "OriginFeatures" in obj.PropertiesList:
            pending.extend(obj.OriginFeatures)
    return [objects[key] for key in sorted(objects)]


def preview_delete(doc_name: str, obj_names: list) -> dict:
    objects = _deletion_set(doc_name, obj_names)
    references = [_reference(obj) for obj in objects]
    external = any(obj.Document.Name != doc_name for obj in objects)
    return {"reference": {"document": doc_name}, "requested": obj_names, "references": references,
            "can_delete": not external,
            "confirmation": [obj.Name for obj in objects] if not external else None,
            "warnings": ["External dependents prevent deletion; remove those links explicitly first."] if external else
                        ["Execution recalculates this set; pass every Name in confirmation explicitly."]}


def delete_objects(doc_name: str, obj_names: list, confirmed_objects: list) -> dict:
    document = _document(doc_name)
    objects = _deletion_set(doc_name, obj_names)
    if any(obj.Document is not document for obj in objects):
        raise BridgeError("dependency_conflict", "External dependents prevent single-document deletion",
                          [_reference(obj) for obj in objects])
    expected = {obj.Name for obj in objects}
    if not isinstance(confirmed_objects, list) or any(not isinstance(name, str) for name in confirmed_objects) or len(set(confirmed_objects)) != len(confirmed_objects) or set(confirmed_objects) != expected:
        raise BridgeError("confirmation_required", "Confirm the exact current preview deletion set", [_reference(obj) for obj in objects])
    before = {obj.Name for obj in document.Objects}
    remaining = set(expected)
    while remaining:
        candidates = [name for name in remaining if document.getObject(name) is None or
                      not any(parent.Name in remaining for parent in document.getObject(name).InList)]
        if not candidates:
            raise BridgeError("dependency_cycle", "Cannot order deletion of cyclic dependencies")
        for name in candidates:
            if document.getObject(name) is not None:
                document.removeObject(name)
            remaining.remove(name)
    removed = before - {obj.Name for obj in document.Objects}
    if removed != expected:
        raise BridgeError("dependency_conflict", "Native deletion affected a different object set; rolled back")
    return {"reference": {"document": doc_name}, "deleted": sorted(removed)}