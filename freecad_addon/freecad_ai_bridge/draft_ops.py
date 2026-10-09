"""Bounded native Draft operations for the GUI executor."""

from contextlib import contextmanager
import math

import FreeCAD
import FreeCADGui
import Draft

from freecad_ai_bridge.contracts import BridgeError
from freecad_ai_bridge.document_ops import _document, _object, _reference


def _number(value, label, positive=False):
    if type(value) not in (int, float) or not math.isfinite(value) or (positive and value <= 0):
        raise BridgeError("invalid_arguments", f"{label} requires a finite {'positive ' if positive else ''}number")
    return float(value)


def _vector(value, label):
    if not isinstance(value, list) or len(value) != 3:
        raise BridgeError("invalid_arguments", f"{label} requires three components")
    return FreeCAD.Vector(*[_number(component, label) for component in value])


def _placement(spec):
    position = _vector(spec.get("position", [0, 0, 0]), "position")
    quaternion = spec.get("quaternion", [0, 0, 0, 1])
    if not isinstance(quaternion, list) or len(quaternion) != 4:
        raise BridgeError("invalid_arguments", "quaternion requires four components")
    quaternion = [_number(component, "quaternion") for component in quaternion]
    if abs(sum(component * component for component in quaternion) - 1) > 1e-6:
        raise BridgeError("invalid_arguments", "quaternion must be normalized")
    return FreeCAD.Placement(position, FreeCAD.Rotation(*quaternion))


@contextmanager
def _active(document):
    previous = FreeCAD.ActiveDocument
    selection = [(item.DocumentName, item.ObjectName, list(item.SubElementNames))
                 for item in FreeCADGui.Selection.getSelectionEx("", 0)]
    FreeCAD.setActiveDocument(document.Name)
    FreeCADGui.setActiveDocument(document.Name)
    try:
        yield
    finally:
        FreeCAD.setActiveDocument(previous.Name if previous else "")
        FreeCADGui.setActiveDocument(previous.Name if previous else "")
        FreeCADGui.Selection.clearSelection()
        for doc_name, obj_name, subelements in selection:
            for subelement in subelements or [""]:
                FreeCADGui.Selection.addSelection(doc_name, obj_name, subelement)


def _element_spec(spec):
    if not isinstance(spec, dict):
        raise BridgeError("invalid_arguments", "spec must be an object")
    kind = spec.get("kind")
    fields = {"line": {"points"}, "wire": {"points", "closed"},
              "rectangle": {"length", "width"}, "circle": {"radius"},
              "arc": {"radius", "start_angle", "end_angle"},
              "text": {"text", "size"}, "label": {"text", "size", "target_point"}}
    if kind not in fields or set(spec) - fields[kind] - {"kind", "position", "quaternion"}:
        raise BridgeError("invalid_arguments", "Unsupported Draft kind or fields")
    placement = _placement(spec)
    values = {}
    if kind in {"line", "wire"}:
        points = spec.get("points")
        minimum, maximum = (2, 2) if kind == "line" else (2, 256)
        if not isinstance(points, list) or not minimum <= len(points) <= maximum:
            raise BridgeError("invalid_arguments", f"points requires {minimum}..{maximum} local XYZ points")
        values["points"] = [_vector(point, "points") for point in points]
        closed = spec.get("closed", False)
        if type(closed) is not bool or (closed and len(points) < 3):
            raise BridgeError("invalid_arguments", "Closed wires require at least three points")
        if any((right - left).Length <= 1e-7 for left, right in zip(values["points"], values["points"][1:])):
            raise BridgeError("invalid_arguments", "Consecutive points must be distinct")
        if (values["points"][0] - values["points"][-1]).Length <= 1e-7:
            raise BridgeError("invalid_arguments", "Do not repeat the first point; use closed=true")
        values["closed"] = closed
    elif kind == "rectangle":
        values = {key: _number(spec.get(key), key, True) for key in ("length", "width")}
    elif kind in {"circle", "arc"}:
        values["radius"] = _number(spec.get("radius"), "radius", True)
        if kind == "arc":
            values.update({key: _number(spec.get(key), key) for key in ("start_angle", "end_angle")})
            if not 0 <= values["start_angle"] < values["end_angle"] <= 360 or values["end_angle"] - values["start_angle"] >= 360:
                raise BridgeError("invalid_arguments", "Arc requires 0 <= start_angle < end_angle <= 360 and sweep < 360 degrees")
    else:
        text = spec.get("text")
        if not isinstance(text, list) or not 1 <= len(text) <= 32 or any(
                not isinstance(line, str) or not line.strip() or len(line) > 4096 for line in text):
            raise BridgeError("invalid_arguments", "text requires 1..32 nonempty lines of up to 4096 characters")
        values = {"text": text, "size": _number(spec.get("size", 3.5), "size", True)}
        if kind == "label":
            values["target_point"] = _vector(spec.get("target_point"), "target_point")
    return kind, placement, values


def _mark(obj, kind):
    obj.addProperty("App::PropertyString", "MCPDraftKind", "MCP")
    obj.MCPDraftKind = kind
    obj.setEditorMode("MCPDraftKind", 1)


def _typed(doc_name, obj_name):
    obj = _object(doc_name, obj_name)
    if "MCPDraftKind" not in obj.PropertiesList:
        raise BridgeError("unsupported_feature", "Object was not created by the structured Draft workflow", [_reference(obj)])
    return obj


def _check(obj):
    if obj.MCPDraftKind in {"ortho_array", "polar_array"}:
        if obj.Base is None or obj.Base.Name != obj.MCPDraftSource or obj.Base.Document is not obj.Document:
            raise BridgeError("draft_reference_lost", "Array source was removed or replaced", [_reference(obj)])
        if not hasattr(obj.Base, "Shape") or obj.Base.Shape.isNull() or not obj.Base.Shape.isValid():
            raise BridgeError("invalid_geometry", "Array source must have valid nonempty geometry", [_reference(obj.Base)])
    if "Invalid" in obj.State:
        raise BridgeError("invalid_geometry", "Native Draft recompute failed", [_reference(obj)])
    if obj.MCPDraftKind not in {"text", "label"} and (obj.Shape.isNull() or not obj.Shape.isValid()):
        raise BridgeError("invalid_geometry", "Native Draft produced invalid or empty geometry", [_reference(obj)])


def create_element(doc_name: str, spec: dict, name: str = "DraftElement") -> dict:
    document = _document(doc_name)
    kind, placement, values = _element_spec(spec)
    if not isinstance(name, str) or not name.strip() or len(name) > 128:
        raise BridgeError("invalid_arguments", "name requires 1..128 characters")
    with _active(document):
        if kind == "line":
            obj = Draft.make_line(*values["points"])
            obj.Placement = placement
        elif kind == "wire":
            obj = Draft.make_wire(values["points"], closed=values["closed"], placement=placement, face=False)
        elif kind == "rectangle":
            obj = Draft.make_rectangle(values["length"], values["width"], placement=placement, face=False)
        elif kind in {"circle", "arc"}:
            obj = Draft.make_circle(values["radius"], placement=placement, face=False,
                startangle=values.get("start_angle"), endangle=values.get("end_angle"))
        elif kind == "text":
            obj = Draft.make_text(values["text"], placement=placement, height=values["size"])
        else:
            obj = Draft.make_label(target_point=values["target_point"], placement=placement,
                                   label_type="Custom", custom_text=values["text"])
            obj.ViewObject.FontSize = values["size"]
    if obj is None or obj.Document is not document:
        raise BridgeError("operation_failed", "Native Draft did not create an object in the requested document")
    obj.Label = name
    _mark(obj, kind)
    document.recompute()
    _check(obj)
    return inspect_element(doc_name, obj.Name)


def edit_element(doc_name: str, obj_name: str, spec: dict) -> dict:
    obj = _typed(doc_name, obj_name)
    kind, placement, values = _element_spec(spec)
    if kind != obj.MCPDraftKind:
        raise BridgeError("invalid_arguments", "An edit must retain the native element kind", [_reference(obj)])
    if kind in {"line", "wire"}:
        obj.Points = values["points"]
        obj.Closed = values["closed"]
    elif kind == "rectangle":
        obj.Length, obj.Height = values["length"], values["width"]
    elif kind in {"circle", "arc"}:
        obj.Radius = values["radius"]
        if kind == "arc":
            obj.FirstAngle, obj.LastAngle = values["start_angle"], values["end_angle"]
    elif kind == "text":
        obj.Text = values["text"]
        obj.ViewObject.FontSize = values["size"]
    else:
        obj.CustomText = values["text"]
        obj.TargetPoint = values["target_point"]
        obj.ViewObject.FontSize = values["size"]
    obj.Placement = placement
    obj.Document.recompute()
    for candidate in obj.Document.Objects:
        if "MCPDraftKind" in candidate.PropertiesList:
            _check(candidate)
    return inspect_element(doc_name, obj_name)


def _array_spec(spec):
    if not isinstance(spec, dict) or spec.get("kind") not in {"ortho_array", "polar_array"}:
        raise BridgeError("invalid_arguments", "An ortho_array or polar_array spec is required")
    kind = spec["kind"]
    allowed = {"kind", "counts", "spacing"} if kind == "ortho_array" else {"kind", "count", "angle", "center", "axis"}
    if set(spec) - allowed:
        raise BridgeError("invalid_arguments", "Unsupported array fields")
    counts = spec.get("counts") if kind == "ortho_array" else [spec.get("count")]
    if not isinstance(counts, list) or len(counts) != (3 if kind == "ortho_array" else 1) or any(
            type(count) is not int or not 1 <= count <= 1000 for count in counts) or math.prod(counts) > 1000:
        raise BridgeError("invalid_arguments", "Array requires positive integer counts and at most 1000 instances")
    if kind == "ortho_array":
        spacing = _vector(spec.get("spacing"), "spacing")
        if any(count > 1 and abs(component) < 1e-7 for count, component in zip(counts, (spacing.x, spacing.y, spacing.z))):
            raise BridgeError("invalid_arguments", "Repeated array directions require nonzero spacing in mm")
        return kind, {"counts": counts, "spacing": spacing}
    axis = _vector(spec.get("axis"), "axis")
    if axis.Length < 1e-12:
        raise BridgeError("invalid_arguments", "Polar axis must be nonzero")
    angle = _number(spec.get("angle", 360), "angle", True)
    if angle > 360:
        raise BridgeError("invalid_arguments", "Polar angle must not exceed 360 degrees")
    return kind, {"count": counts[0], "angle": angle, "center": _vector(spec.get("center"), "center"), "axis": axis}


def _set_array(obj, kind, values):
    obj.Fuse = False
    if kind == "ortho_array":
        obj.NumberX, obj.NumberY, obj.NumberZ = values["counts"]
        spacing = values["spacing"]
        obj.IntervalX, obj.IntervalY, obj.IntervalZ = (FreeCAD.Vector(spacing.x, 0, 0),
            FreeCAD.Vector(0, spacing.y, 0), FreeCAD.Vector(0, 0, spacing.z))
    else:
        obj.NumberPolar, obj.Angle = values["count"], values["angle"]
        obj.Center, obj.Axis = values["center"], values["axis"]


def create_array(doc_name: str, base_name: str, spec: dict, name: str = "DraftArray") -> dict:
    base = _object(doc_name, base_name)
    kind, values = _array_spec(spec)
    if not isinstance(name, str) or not name.strip() or len(name) > 128:
        raise BridgeError("invalid_arguments", "name requires 1..128 characters")
    if not hasattr(base, "Shape") or base.Shape.isNull() or not base.Shape.isValid() or "Invalid" in base.State:
        raise BridgeError("invalid_geometry", "Array source requires valid nonempty shape", [_reference(base)])
    if "Touched" in base.State:
        raise BridgeError("geometry_not_ready", "Recompute source before creating an array", [_reference(base)])
    source_visibility = base.ViewObject.Visibility
    with _active(base.Document):
        if kind == "ortho_array":
            obj = Draft.make_ortho_array(base, use_link=False)
        else:
            obj = Draft.make_polar_array(base, use_link=False)
        base.ViewObject.Visibility = source_visibility
    _set_array(obj, kind, values)
    obj.Label = name
    _mark(obj, kind)
    obj.addProperty("App::PropertyString", "MCPDraftSource", "MCP")
    obj.MCPDraftSource = base.Name
    obj.setEditorMode("MCPDraftSource", 1)
    obj.Document.recompute()
    _check(obj)
    return inspect_element(doc_name, obj.Name)


def edit_array(doc_name: str, obj_name: str, spec: dict) -> dict:
    obj = _typed(doc_name, obj_name)
    _check(obj)
    kind, values = _array_spec(spec)
    if kind != obj.MCPDraftKind:
        raise BridgeError("invalid_arguments", "Array kind cannot change", [_reference(obj)])
    _set_array(obj, kind, values)
    obj.Document.recompute()
    _check(obj)
    return inspect_element(doc_name, obj_name)


def inspect_element(doc_name: str, obj_name: str) -> dict:
    obj = _typed(doc_name, obj_name)
    _check(obj)
    if "Touched" in obj.State:
        raise BridgeError("geometry_not_ready", "Recompute Draft element before inspection", [_reference(obj)])
    kind = obj.MCPDraftKind
    result = {"reference": _reference(obj), "name": obj.Name, "label": obj.Label,
              "kind": kind, "native_type": Draft.get_type(obj), "parametric": True,
              "placement": {"position": list(obj.Placement.Base), "quaternion": list(obj.Placement.Rotation.Q)},
              "warnings": []}
    if kind in {"text", "label"}:
        result["text"] = list(obj.Text if kind == "text" else obj.CustomText)
        result["size_mm"] = float(obj.ViewObject.FontSize)
        if kind == "label":
            result["target_point_mm"] = list(obj.TargetPoint)
    else:
        shape = obj.Shape
        bounds = shape.optimalBoundingBox(False, False)
        result.update({"length_mm": shape.Length, "edges": len(shape.Edges), "wires": len(shape.Wires),
                       "closed": all(wire.isClosed() for wire in shape.Wires) if shape.Wires else shape.isClosed(),
                       "bbox_mm": {"min": [bounds.XMin, bounds.YMin, bounds.ZMin],
                                   "max": [bounds.XMax, bounds.YMax, bounds.ZMax]}})
        if kind in {"circle", "arc"}:
            result["radius_mm"] = float(obj.Radius)
        if kind == "arc":
            result["angles_deg"] = [float(obj.FirstAngle), float(obj.LastAngle)]
        if kind in {"ortho_array", "polar_array"}:
            result["source"] = _reference(obj.Base)
            result["instances"] = obj.NumberX * obj.NumberY * obj.NumberZ if kind == "ortho_array" else obj.NumberPolar
            result["fused"] = bool(obj.Fuse)
    return result