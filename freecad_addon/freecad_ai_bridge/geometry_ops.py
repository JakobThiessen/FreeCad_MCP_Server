"""Revision-checked geometric queries on the GUI thread, in document-global mm."""

import math
import base64
import os
import tempfile
import uuid

import FreeCAD
import FreeCADGui

from freecad_ai_bridge.contracts import BridgeError


class _Revisions:
    def __init__(self):
        self.documents = {}

    def token(self, doc):
        if doc.Name not in self.documents:
            self.documents[doc.Name] = [uuid.uuid4().hex, 0]
        identity, counter = self.documents[doc.Name]
        return f"{identity}:{counter}"

    def changed(self, doc):
        self.token(doc)
        self.documents[doc.Name][1] += 1

    def slotCreatedDocument(self, doc):
        self.documents.pop(doc.Name, None)
        self.token(doc)

    def slotDeletedDocument(self, doc):
        self.documents.pop(doc.Name, None)

    def slotCreatedObject(self, obj):
        self.changed(obj.Document)

    def slotDeletedObject(self, obj):
        self.changed(obj.Document)

    def slotChangedObject(self, obj, property_name):
        self.changed(obj.Document)

    def slotRecomputedDocument(self, doc):
        self.changed(doc)

    def slotUndoDocument(self, doc):
        self.changed(doc)

    def slotRedoDocument(self, doc):
        self.changed(doc)


_revisions = _Revisions()
FreeCAD.addDocumentObserver(_revisions)
_KINDS = {"face": "Faces", "edge": "Edges", "vertex": "Vertexes"}
_PREFIXES = {"face": "Face", "edge": "Edge", "vertex": "Vertex"}
_TYPES = {"Plane": "plane", "Cylinder": "cylinder", "Cone": "cone", "Sphere": "sphere",
          "Toroid": "torus", "ToroidalSurface": "torus", "BSplineSurface": "bspline_surface",
          "Line": "line", "LineSegment": "line", "Circle": "circle", "Ellipse": "ellipse",
          "BSplineCurve": "bspline_curve", "BezierCurve": "bezier_curve"}


def _fail(code, message, doc_name=None, obj_name=None):
    references = [{"document": doc_name, "object": obj_name}] if doc_name else []
    raise BridgeError(code, message, references)


def _number(value, name, minimum=None):
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value):
        _fail("invalid_arguments", f"{name} must be a finite number")
    if minimum is not None and value < minimum:
        _fail("invalid_arguments", f"{name} must be >= {minimum}")
    return float(value)


def _vector(value, name):
    if not isinstance(value, list) or len(value) != 3:
        _fail("invalid_arguments", f"{name} must be three document-global coordinates")
    return [_number(component, name) for component in value]


def _xyz(vector):
    return [float(vector.x), float(vector.y), float(vector.z)]


def _shape(doc_name, obj_name):
    if not isinstance(doc_name, str) or not doc_name.strip() or not isinstance(obj_name, str) or not obj_name.strip():
        _fail("invalid_arguments", "Explicit document and object Names are required")
    doc = FreeCAD.listDocuments().get(doc_name)
    if doc is None:
        _fail("document_not_found", "Document is not open", doc_name, obj_name)
    obj = doc.getObject(obj_name)
    if obj is None:
        _fail("object_not_found", "Object does not exist", doc_name, obj_name)
    if "Touched" in obj.State or "Invalid" in obj.State:
        _fail("geometry_not_ready", "Recompute the document before querying geometry", doc_name, obj_name)
    if not hasattr(obj, "Shape") or obj.Shape.isNull() or not obj.Shape.isValid():
        _fail("invalid_geometry", "Object must have a nonempty valid BRep shape", doc_name, obj_name)
    shape = obj.Shape.copy()
    if hasattr(obj, "getGlobalPlacement"):
        shape.Placement = obj.getGlobalPlacement().multiply(obj.Placement.inverse()).multiply(shape.Placement)
    else:
        parents = [parent for parent in obj.InList if hasattr(parent, "getGlobalPlacement")
                   and hasattr(parent, "Group") and obj in parent.Group]
        if len(parents) > 1:
            _fail("coordinate_system_mismatch", "Object has multiple geometric owners", doc_name, obj_name)
        if parents:
            shape.Placement = parents[0].getGlobalPlacement().multiply(shape.Placement)
    return doc, obj, shape


def _descriptor(element, kind):
    bounds = element.BoundBox
    result = {"kind": kind, "geometry_type": "vertex", "position": _xyz(element.Point if kind == "vertex" else element.CenterOfMass),
              "bbox": {"min": [bounds.XMin, bounds.YMin, bounds.ZMin], "max": [bounds.XMax, bounds.YMax, bounds.ZMax]},
              "normal": None, "axis": None, "radius": None, "area": None, "length": None}
    if kind == "vertex":
        return result
    geometry = element.Surface if kind == "face" else element.Curve
    result["geometry_type"] = _TYPES.get(type(geometry).__name__, "other")
    result["area" if kind == "face" else "length"] = element.Area if kind == "face" else element.Length
    if hasattr(geometry, "Radius"):
        result["radius"] = float(geometry.Radius)
    if hasattr(geometry, "Axis"):
        result["axis"] = _xyz(geometry.Axis)
    if kind == "face" and result["geometry_type"] == "plane":
        lower_u, upper_u, lower_v, upper_v = element.ParameterRange
        result["normal"] = _xyz(element.normalAt((lower_u + upper_u) / 2, (lower_v + upper_v) / 2))
    if kind == "edge" and result["geometry_type"] == "line":
        result["axis"] = _xyz(element.tangentAt(element.FirstParameter))
    return result


def _filters(filters, tolerance, angular_tolerance):
    _number(tolerance, "tolerance", 0)
    _number(angular_tolerance, "angular_tolerance", 0)
    if angular_tolerance > 180:
        _fail("invalid_arguments", "angular_tolerance must be <= 180 deg")
    filters = {} if filters is None else filters
    allowed = {"geometry_type", "position", "bbox", "normal", "axis", "radius", "area", "length"}
    if not isinstance(filters, dict) or set(filters) - allowed:
        _fail("invalid_arguments", "Unknown geometric filter")
    for name, value in filters.items():
        if name == "geometry_type":
            if value not in set(_TYPES.values()) | {"vertex", "other"}:
                _fail("invalid_arguments", "Unknown geometry_type")
        elif name in {"position", "normal", "axis"}:
            coordinates = _vector(value, name)
            if name != "position" and sum(component * component for component in coordinates) == 0:
                _fail("invalid_arguments", f"{name} must not be zero")
        elif name == "bbox":
            if not isinstance(value, dict) or set(value) != {"min", "max"}:
                _fail("invalid_arguments", "bbox requires min and max vectors")
            minimum = _vector(value["min"], "bbox.min")
            maximum = _vector(value["max"], "bbox.max")
            if any(low > high for low, high in zip(minimum, maximum)):
                _fail("invalid_arguments", "bbox min must not exceed max")
        else:
            if not isinstance(value, dict) or not value or set(value) - {"min", "max"}:
                _fail("invalid_arguments", f"{name} requires min and/or max")
            for bound in value.values():
                _number(bound, name, 0)
            if value.get("min", 0) > value.get("max", math.inf):
                _fail("invalid_arguments", f"{name} min must not exceed max")
    return filters


def _angle(first, second, unoriented=False):
    first = FreeCAD.Vector(*first)
    second = FreeCAD.Vector(*second)
    angle = math.degrees(first.getAngle(second))
    return min(angle, 180 - angle) if unoriented else angle


def _matches(item, filters, tolerance, angular_tolerance):
    for name, value in filters.items():
        actual = item[name]
        if actual is None:
            return False
        if name == "geometry_type":
            if actual != value:
                return False
        elif name == "position":
            if math.sqrt(sum((left - right) ** 2 for left, right in zip(actual, value))) > tolerance:
                return False
        elif name in {"normal", "axis"}:
            if _angle(actual, value, unoriented=name == "axis") > angular_tolerance:
                return False
        elif name == "bbox":
            if any(actual["min"][index] < value["min"][index] - tolerance or
                   actual["max"][index] > value["max"][index] + tolerance for index in range(3)):
                return False
        elif actual < value.get("min", -math.inf) - tolerance or actual > value.get("max", math.inf) + tolerance:
            return False
    return True


def list_subelements(doc_name: str, obj_name: str, kind: str, filters: dict = None,
                     tolerance: float = 0.001, angular_tolerance: float = 0.001,
                     offset: int = 0, limit: int = 100) -> dict:
    """List a bounded page of matching subelements; no recompute or document mutation."""
    filters = _filters(filters, tolerance, angular_tolerance)
    if kind not in _KINDS:
        _fail("invalid_arguments", "kind must be face, edge or vertex")
    if type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 256:
        _fail("invalid_arguments", "offset >= 0 and limit 1..256 must be integers")
    doc, obj, shape = _shape(doc_name, obj_name)
    revision = _revisions.token(doc)
    elements = getattr(shape, _KINDS[kind])
    if len(elements) > 10000:
        _fail("query_limit", "At most 10000 subelements per query", doc_name, obj_name)
    matches = []
    count = 0
    for index, element in enumerate(elements, 1):
        item = _descriptor(element, kind)
        if _matches(item, filters, tolerance, angular_tolerance):
            if offset <= count < offset + limit:
                item["selection"] = {"document": doc.Name, "object": obj.Name, "revision": revision,
                                     "subelement": f"{_PREFIXES[kind]}{index}"}
                matches.append(item)
            count += 1
    return {"reference": {"document": doc.Name, "object": obj.Name}, "revision": revision,
            "coordinate_system": "document_global", "units": {"length": "mm", "area": "mm^2", "angle": "deg"},
            "total": count, "items": matches, "next_offset": offset + limit if offset + limit < count else None}


def select_subelement(doc_name: str, obj_name: str, kind: str, filters: dict = None,
                      tolerance: float = 0.001, angular_tolerance: float = 0.001) -> dict:
    """Require exactly one geometric match; never guess among multiple matches."""
    result = list_subelements(doc_name, obj_name, kind, filters, tolerance, angular_tolerance, limit=1)
    if result["total"] != 1:
        _fail("selection_empty" if result["total"] == 0 else "selection_ambiguous",
              f"Expected exactly one match, found {result['total']}", doc_name, obj_name)
    return dict(result["items"][0], reference=result["reference"])


def _resolve(selection):
    if not isinstance(selection, dict) or set(selection) != {"document", "object", "revision", "subelement"}:
        _fail("invalid_arguments", "selection requires document, object, revision and subelement")
    doc_name, obj_name = selection["document"], selection["object"]
    if not isinstance(doc_name, str) or not doc_name.strip() or not isinstance(obj_name, str) or not obj_name.strip():
        _fail("invalid_arguments", "Selection requires explicit document and object Names")
    doc = FreeCAD.listDocuments().get(doc_name)
    if doc is None:
        _fail("document_not_found", "Document is not open", doc_name, obj_name)
    if selection["revision"] != _revisions.token(doc):
        _fail("stale_selection", "Document changed; query geometry again", doc_name, obj_name)
    doc, obj, shape = _shape(doc_name, obj_name)
    name = selection["subelement"]
    for kind, prefix in _PREFIXES.items():
        suffix = name[len(prefix):] if isinstance(name, str) and name.startswith(prefix) else ""
        if suffix.isascii() and suffix.isdigit() and not suffix.startswith("0"):
            index = int(suffix)
            elements = getattr(shape, _KINDS[kind])
            if 1 <= index <= len(elements):
                return doc, obj, elements[index - 1], kind
    _fail("invalid_reference", "Subelement does not exist", doc_name, obj_name)


def resolve_subelement(selection: dict) -> dict:
    """Validate revision before resolving the exact issued subelement name."""
    doc, obj, element, kind = _resolve(selection)
    return dict(_descriptor(element, kind), selection=selection,
                reference={"document": doc.Name, "object": obj.Name})


def _selection_names(doc_name, obj_name, selections, kind):
    if not isinstance(selections, list) or not selections:
        _fail("invalid_arguments", "A nonempty subelement list is required", doc_name, obj_name)
    names = []
    for selection in selections:
        if isinstance(selection, dict):
            doc, obj, element, actual_kind = _resolve(selection)
            if (doc.Name, obj.Name, actual_kind) != (doc_name, obj_name, kind):
                _fail("invalid_reference", "Selection belongs to a different object or subelement kind", doc_name, obj_name)
            names.append(selection["subelement"])
        else:
            names.append(selection)
    return names


def _target(reference):
    if isinstance(reference, dict) and "revision" in reference:
        return _resolve(reference)
    if not isinstance(reference, dict) or set(reference) != {"document", "object"}:
        _fail("invalid_arguments", "Target must be an object reference or complete revision-checked selection")
    doc, obj, shape = _shape(reference["document"], reference["object"])
    return doc, obj, shape, "shape"


def _pair(first, second):
    left, right = _target(first), _target(second)
    if left[0].Name != right[0].Name:
        _fail("coordinate_system_mismatch", "Targets must belong to the same document", left[0].Name, left[1].Name)
    references = [{"document": target[0].Name, "object": target[1].Name} for target in (left, right)]
    return left, right, references


def measure_distance(first: dict, second: dict) -> dict:
    """Kernel minimum distance between finite BRep objects or selected subelements."""
    left, right, references = _pair(first, second)
    distance, pairs, details = left[2].distToShape(right[2])
    return {"distance": distance, "unit": "mm", "coordinate_system": "document_global",
            "closest_points": [{"first": _xyz(pair[0]), "second": _xyz(pair[1])} for pair in pairs[:32]],
            "solution_count": len(pairs), "truncated": len(pairs) > 32,
            "revision": _revisions.token(left[0]), "references": references}


def measure_angle(first: dict, second: dict) -> dict:
    """Smallest unoriented line/line, plane/plane or line/plane angle (0..90 deg)."""
    left, right, references = _pair(first, second)
    descriptors = []
    for target in (left, right):
        if target[3] not in {"face", "edge"}:
            _fail("unsupported_geometry", "Angle needs selected straight edges or planar faces", target[0].Name, target[1].Name)
        item = _descriptor(target[2], target[3])
        if item["geometry_type"] not in {"line", "plane"}:
            _fail("unsupported_geometry", "Angle supports only lines and planes", target[0].Name, target[1].Name)
        descriptors.append(item)
    first_item, second_item = descriptors
    first_vector = first_item["normal"] if first_item["geometry_type"] == "plane" else first_item["axis"]
    second_vector = second_item["normal"] if second_item["geometry_type"] == "plane" else second_item["axis"]
    angle = _angle(first_vector, second_vector, unoriented=True)
    if first_item["geometry_type"] != second_item["geometry_type"]:
        angle = 90 - angle
    return {"angle": angle, "unit": "deg", "convention": "smallest_unoriented_0_to_90",
            "types": [item["geometry_type"] for item in descriptors], "references": references,
            "revision": _revisions.token(left[0])}


def check_interference(first: dict, second: dict, contact_tolerance: float = 0.001,
                       volume_tolerance: float = 0.000001) -> dict:
    """Static solid intersection volume and minimum distance; never continuous collision assurance."""
    _number(contact_tolerance, "contact_tolerance", 0)
    _number(volume_tolerance, "volume_tolerance", 0)
    left, right, references = _pair(first, second)
    for target in (left, right):
        shape = target[2]
        if target[3] != "shape" or not shape.Solids or any(not solid.isClosed() for solid in shape.Solids):
            _fail("unsupported_geometry", "Interference requires whole objects containing closed solids", target[0].Name, target[1].Name)
        if len(shape.Faces) != sum(len(solid.Faces) for solid in shape.Solids):
            _fail("unsupported_geometry", "Mixed solid/surface shapes are unsupported", target[0].Name, target[1].Name)
    common = left[2].common(right[2])
    if not common.isNull() and not common.isValid():
        _fail("invalid_geometry", "Kernel intersection is invalid", left[0].Name, left[1].Name)
    volume = 0.0 if common.isNull() else common.Volume
    distance = left[2].distToShape(right[2])[0]
    interference = volume > volume_tolerance
    within_contact = distance <= contact_tolerance
    return {"distance": distance, "intersection_volume": volume, "interference": interference,
            "within_contact_tolerance": within_contact,
            "classification": "interference" if interference else "contact" if within_contact else "separated",
            "contact_tolerance": contact_tolerance, "volume_tolerance": volume_tolerance,
            "units": {"distance": "mm", "volume": "mm^3"}, "references": references,
            "revision": _revisions.token(left[0]), "warnings": ["Static discrete state only; no continuous collision or manufacturing safety assurance."]}


def _gui_document(doc_name):
    if not isinstance(doc_name, str) or not doc_name.strip():
        _fail("invalid_arguments", "An explicit document Name is required")
    doc = FreeCAD.listDocuments().get(doc_name)
    if doc is None:
        _fail("document_not_found", "Document is not open", doc_name)
    if not FreeCAD.GuiUp:
        _fail("gui_unavailable", "A GUI view is required", doc_name)
    return doc, FreeCADGui.getDocument(doc.Name).activeView()


def highlight_subelements(doc_name: str, selections: list) -> dict:
    """Replace only this document's GUI selection after validating every token; empty clears."""
    doc, active_view = _gui_document(doc_name)
    if not isinstance(selections, list) or len(selections) > 100:
        _fail("invalid_arguments", "At most 100 selections are allowed", doc_name)
    for selection in selections:
        target_doc, obj, element, kind = _resolve(selection)
        if target_doc.Name != doc.Name:
            _fail("coordinate_system_mismatch", "Highlight selections must belong to the target document", doc_name)
    requested = {(selection["object"], selection["subelement"]) for selection in selections}
    if len(requested) != len(selections):
        _fail("invalid_arguments", "Duplicate highlight selections are not allowed", doc_name)
    previous = [(entry.DocumentName, entry.ObjectName, list(entry.SubElementNames))
                for entry in FreeCADGui.Selection.getSelectionEx(doc.Name)]
    try:
        FreeCADGui.Selection.clearSelection(doc.Name)
        for selection in selections:
            FreeCADGui.Selection.addSelection(doc.Name, selection["object"], selection["subelement"])
        FreeCADGui.updateGui()
        actual = {(entry.ObjectName, name) for entry in FreeCADGui.Selection.getSelectionEx(doc.Name) for name in entry.SubElementNames}
        if actual != requested:
            _fail("selection_failed", "GUI rejected one or more selections", doc_name)
    except Exception:
        FreeCADGui.Selection.clearSelection(doc.Name)
        for document, name, subelements in previous:
            for subelement in subelements or [""]:
                FreeCADGui.Selection.addSelection(document, name, subelement)
        raise
    return {"reference": {"document": doc.Name}, "selections": selections, "count": len(selections),
            "warnings": ["GUI selection only; hidden objects are not made visible. Not a document Undo operation."]}


def get_view_state(doc_name: str, obj_names: list) -> dict:
    """Read camera orientation and bounded appearance values for restoration via view tools."""
    doc, active_view = _gui_document(doc_name)
    if not isinstance(obj_names, list) or len(obj_names) > 256 or any(not isinstance(name, str) for name in obj_names):
        _fail("invalid_arguments", "obj_names must contain at most 256 internal Names", doc_name)
    objects = []
    for name in obj_names:
        obj = doc.getObject(name)
        if obj is None:
            _fail("object_not_found", "Object does not exist", doc_name, name)
        provider = obj.ViewObject
        objects.append({"name": name, "visible": bool(provider.Visibility),
                        "color": list(provider.ShapeColor) if hasattr(provider, "ShapeColor") else None,
                        "transparency": provider.Transparency if hasattr(provider, "Transparency") else None})
    selection = [{"object": entry.ObjectName, "subelements": list(entry.SubElementNames)}
                 for entry in FreeCADGui.Selection.getSelectionEx(doc.Name)]
    return {"reference": {"document": doc.Name}, "objects": objects, "selection": selection,
            "camera_quaternion": list(active_view.getCameraOrientation().Q)}


def capture_view(doc_name: str, width: int = 800, height: int = 600, view: str = "isometric",
                 selections: list = None) -> dict:
    """Capture an explicit document without recompute, preserving geometry revision; replace highlight only when supplied."""
    previous_document = FreeCAD.ActiveDocument
    doc, active_view = _gui_document(doc_name)
    if type(width) is not int or type(height) is not int or not 64 <= width <= 2048 or not 64 <= height <= 2048:
        _fail("invalid_arguments", "Image dimensions must be integer pixels in 64..2048", doc_name)
    methods = {"isometric": "viewIsometric", "front": "viewFront", "back": "viewRear", "top": "viewTop",
               "bottom": "viewBottom", "left": "viewLeft", "right": "viewRight"}
    if view not in methods:
        _fail("invalid_arguments", "Unknown view preset", doc_name)
    if any("Touched" in obj.State or "Invalid" in obj.State for obj in doc.Objects):
        _fail("geometry_not_ready", "Explicitly recompute before capturing a current image", doc_name)
    if selections is not None:
        highlight_subelements(doc.Name, selections)
    selected = [(entry.DocumentName, entry.ObjectName, list(entry.SubElementNames))
                for document in FreeCAD.listDocuments()
                for entry in FreeCADGui.Selection.getSelectionEx(document)]
    animation_enabled = active_view.isAnimationEnabled()
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as image_file:
        path = image_file.name
    try:
        FreeCAD.setActiveDocument(doc.Name)
        FreeCADGui.setActiveDocument(doc.Name)
        FreeCADGui.updateGui()
        active_view.setAnimationEnabled(False)
        getattr(active_view, methods[view])()
        active_view.redraw()
        FreeCADGui.updateGui()
        active_view.fitAll()
        FreeCADGui.updateGui()
        for document, name, subelements in selected:
            for subelement in subelements or [""]:
                FreeCADGui.Selection.addSelection(document, name, subelement)
        active_view.redraw()
        FreeCADGui.updateGui()
        active_view.saveImage(path, width, height, "Current")
        with open(path, "rb") as image_file:
            image = base64.b64encode(image_file.read()).decode("ascii")
    finally:
        os.remove(path)
        active_view.setAnimationEnabled(animation_enabled)
        if previous_document is not None:
            FreeCAD.setActiveDocument(previous_document.Name)
            FreeCADGui.setActiveDocument(previous_document.Name)
            FreeCADGui.updateGui()
        for document, name, subelements in selected:
            for subelement in subelements or [""]:
                FreeCADGui.Selection.addSelection(document, name, subelement)
        FreeCADGui.updateGui()
    return {"reference": {"document": doc.Name}, "revision": _revisions.token(doc), "view": view,
            "image_base64": image, "format": "png", "width": width, "height": height,
            "camera_quaternion": list(active_view.getCameraOrientation().Q),
            "warnings": ["Camera and optional GUI selection changed; no document recompute or Undo entry."]}