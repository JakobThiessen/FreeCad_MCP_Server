"""Part module operations running inside FreeCAD.

Provides primitive creation, boolean operations, and transforms.
"""

import math
import re

import FreeCAD
import FreeCADGui
import Part
from FreeCAD import Vector, Rotation, Placement

# A solid or surface smaller than this fraction of its bounding-box measure is a degenerate artifact.
_DEGENERATE_RELATIVE = 1e-9
_MAX_SCALE = 1e6


def _finite(label, value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{label} must be a finite number")
    return float(value)


def _positive(label, value):
    if _finite(label, value) <= 0:
        raise ValueError(f"{label} must be greater than 0")
    return float(value)


def _get_doc(doc_name=None):
    doc = FreeCAD.getDocument(doc_name) if doc_name else FreeCAD.ActiveDocument
    if not doc:
        raise ValueError("No active document")
    return doc


def _get_object(name, doc_name=None):
    doc = _get_doc(doc_name)
    obj = doc.getObject(name)
    if not obj:
        raise ValueError(f"Object '{name}' not found")
    return obj


def _shape_result(obj, hint=None) -> dict:
    state = getattr(obj, "State", ())
    # A failed native recompute keeps the previous (default) shape, so the state must be checked too.
    recompute_failed = isinstance(state, (list, tuple)) and "Invalid" in state
    if recompute_failed or not hasattr(obj, "Shape") or obj.Shape.isNull() or not obj.Shape.isValid():
        reason = " (native recompute failed)" if recompute_failed else ""
        raise RuntimeError(f"Feature '{obj.Name}' produced an empty or invalid shape{reason}"
                           + (f"; {hint}" if hint else ""))
    result = {
        "name": obj.Name,
        "label": obj.Label,
        "type": obj.TypeId,
    }
    if hasattr(obj, "Shape") and obj.Shape and not obj.Shape.isNull():
        result["shape_valid"] = obj.Shape.isValid()
        result["volume"] = obj.Shape.Volume
        result["num_faces"] = len(obj.Shape.Faces)
        result["num_edges"] = len(obj.Shape.Edges)
        result["num_vertices"] = len(obj.Shape.Vertexes)
        result["num_wires"] = len(obj.Shape.Wires)
        result["num_shells"] = len(obj.Shape.Shells)
        result["num_solids"] = len(obj.Shape.Solids)
        result["shape_type"] = obj.Shape.ShapeType
        result["closed"] = bool(obj.Shape.isClosed())
    return result


def _feature_from_shape(doc, name, shape, source_names=None):
    if shape is None or shape.isNull() or not shape.isValid():
        raise RuntimeError(f"Feature '{name}' produced an empty or invalid shape")
    obj = doc.addObject("Part::Feature", name)
    obj.Shape = shape
    if source_names:
        obj.addProperty("App::PropertyStringList", "SourceNames", "Stage7")
        obj.SourceNames = list(source_names)
    doc.recompute()
    return obj


def _require_shape(obj, allowed_types=None):
    if not hasattr(obj, "Shape") or obj.Shape.isNull() or not obj.Shape.isValid():
        raise ValueError(f"Object '{obj.Name}' has no valid shape")
    if allowed_types and obj.Shape.ShapeType not in allowed_types:
        expected = ", ".join(sorted(allowed_types))
        raise ValueError(f"Object '{obj.Name}' must be one of: {expected}")
    return obj.Shape


def _shape_quality(shape):
    if shape is None or shape.isNull():
        return {"valid": False, "null": True, "shape_type": None}
    return {
        "valid": bool(shape.isValid()),
        "null": False,
        "shape_type": shape.ShapeType,
        "closed": bool(shape.isClosed()),
        "num_vertices": len(shape.Vertexes),
        "num_edges": len(shape.Edges),
        "num_wires": len(shape.Wires),
        "num_faces": len(shape.Faces),
        "num_shells": len(shape.Shells),
        "num_solids": len(shape.Solids),
        "area": float(shape.Area),
        "volume": float(shape.Volume),
    }


def _require_extent(shape, label, solid=True, hint=None):
    """Reject valid kernel results without volume (solids) or area (surfaces)."""
    diagonal = shape.BoundBox.DiagonalLength
    measure, scale, unit = ((abs(shape.Volume), diagonal ** 3, "volume") if solid
                            else (shape.Area, diagonal ** 2, "area"))
    if measure <= _DEGENERATE_RELATIVE * max(scale, 1e-12):
        raise ValueError(f"{label} is degenerate: the result has no {unit}" + (f"; {hint}" if hint else ""))


# =============================================================================
# Primitives
# =============================================================================


def make_box(length: float, width: float, height: float,
             x: float = 0, y: float = 0, z: float = 0,
             name: str = "Box", doc_name: str = None) -> dict:
    """Create a box primitive."""
    _positive("length", length)
    _positive("width", width)
    _positive("height", height)
    for label, value in (("x", x), ("y", y), ("z", z)):
        _finite(label, value)
    doc = _get_doc(doc_name)
    obj = doc.addObject("Part::Box", name)
    obj.Length = length
    obj.Width = width
    obj.Height = height
    obj.Placement.Base = Vector(x, y, z)
    doc.recompute()
    return _shape_result(obj)


def make_cylinder(radius: float, height: float,
                  x: float = 0, y: float = 0, z: float = 0,
                  angle: float = 360.0, name: str = "Cylinder",
                  doc_name: str = None) -> dict:
    """Create a cylinder primitive; 0 < angle <= 360 degrees."""
    _positive("radius", radius)
    _positive("height", height)
    if not 0 < _finite("angle", angle) <= 360:
        raise ValueError("angle must be in (0, 360] degrees")
    for label, value in (("x", x), ("y", y), ("z", z)):
        _finite(label, value)
    doc = _get_doc(doc_name)
    obj = doc.addObject("Part::Cylinder", name)
    obj.Radius = radius
    obj.Height = height
    obj.Angle = angle
    obj.Placement.Base = Vector(x, y, z)
    doc.recompute()
    return _shape_result(obj)


def make_sphere(radius: float, x: float = 0, y: float = 0, z: float = 0,
                name: str = "Sphere", doc_name: str = None) -> dict:
    """Create a sphere primitive."""
    _positive("radius", radius)
    for label, value in (("x", x), ("y", y), ("z", z)):
        _finite(label, value)
    doc = _get_doc(doc_name)
    obj = doc.addObject("Part::Sphere", name)
    obj.Radius = radius
    obj.Placement.Base = Vector(x, y, z)
    doc.recompute()
    return _shape_result(obj)


def make_cone(radius1: float, radius2: float, height: float,
              x: float = 0, y: float = 0, z: float = 0,
              name: str = "Cone", doc_name: str = None) -> dict:
    """Create a cone primitive; one radius may be 0 (pointed), not both."""
    for label, value in (("radius1", radius1), ("radius2", radius2)):
        if _finite(label, value) < 0:
            raise ValueError(f"{label} must be greater than or equal to 0")
    if radius1 == 0 and radius2 == 0:
        raise ValueError("radius1 and radius2 must not both be 0")
    _positive("height", height)
    for label, value in (("x", x), ("y", y), ("z", z)):
        _finite(label, value)
    doc = _get_doc(doc_name)
    obj = doc.addObject("Part::Cone", name)
    obj.Radius1 = radius1
    obj.Radius2 = radius2
    obj.Height = height
    obj.Placement.Base = Vector(x, y, z)
    doc.recompute()
    return _shape_result(obj)


def make_torus(radius1: float, radius2: float,
               x: float = 0, y: float = 0, z: float = 0,
               name: str = "Torus", doc_name: str = None) -> dict:
    """Create a torus; radius1 = major, radius2 = minor with 0 < radius2 <= radius1."""
    _positive("radius1", radius1)
    _positive("radius2", radius2)
    if radius2 > radius1:
        raise ValueError("radius2 (minor) must not exceed radius1 (major); a larger tube self-intersects")
    for label, value in (("x", x), ("y", y), ("z", z)):
        _finite(label, value)
    doc = _get_doc(doc_name)
    obj = doc.addObject("Part::Torus", name)
    obj.Radius1 = radius1
    obj.Radius2 = radius2
    obj.Placement.Base = Vector(x, y, z)
    doc.recompute()
    return _shape_result(obj)


# =============================================================================
# Part and surface construction
# =============================================================================


def scrub_edges(doc_name: str, edges: list, name: str = "ScrubbedEdges") -> dict:
    """Create a static compound using native TechDraw face-boundary cleanup."""
    from freecad_ai_bridge.contracts import BridgeError
    from freecad_ai_bridge.geometry_ops import _resolve

    if not isinstance(doc_name, str) or not doc_name.strip():
        raise BridgeError("invalid_arguments", "An explicit document Name is required")
    if not isinstance(edges, list) or not 1 <= len(edges) <= 256:
        raise BridgeError("invalid_arguments", "Expected 1..256 revision-checked edge selections")
    if not isinstance(name, str) or not name.strip():
        raise BridgeError("invalid_arguments", "A nonempty result name is required")
    doc = _get_doc(doc_name)
    selected = []
    sources = []
    for selection in edges:
        source_doc, obj, edge, kind = _resolve(selection)
        if source_doc.Name != doc.Name or kind != "edge":
            raise BridgeError("invalid_reference", "All selections must be edges in the target document",
                              [{"document": doc.Name}])
        selected.append(edge.copy())
        if obj.Name not in sources:
            sources.append(obj.Name)
    try:
        import TechDraw
    except ImportError as error:
        raise BridgeError("unsupported_feature", "TechDraw.scrubEdges is unavailable in this runtime") from error
    if not callable(getattr(TechDraw, "scrubEdges", None)):
        raise BridgeError("unsupported_feature", "TechDraw.scrubEdges is unavailable; use FreeCAD 1.1.4")
    cleaned = TechDraw.scrubEdges(selected)
    if not cleaned:
        raise BridgeError("operation_failed", "TechDraw.scrubEdges returned no edges")
    result = _shape_result(_feature_from_shape(doc, name, Part.makeCompound(cleaned), sources))
    result.update(reference={"document": doc.Name, "object": result["name"]},
                  input_edges=len(selected), output_edges=len(cleaned),
                  parametric=False, source_names=sources)
    return result


def make_wire(obj_name: str, edges: list, closed: bool = False,
              name: str = "Wire", doc_name: str = None) -> dict:
    """Build a wire from ordered, revision-checked edges of one object."""
    doc = _get_doc(doc_name)
    obj = _get_object(obj_name, doc.Name)
    _require_shape(obj)

    from freecad_ai_bridge.geometry_ops import _selection_names

    edge_names = _selection_names(doc.Name, obj.Name, edges, "edge")
    if len(set(map(str, edge_names))) != len(edge_names):
        raise ValueError("edges must not contain duplicates")
    selected = []
    for edge_name in edge_names:
        index = int("".join(filter(str.isdigit, str(edge_name))))
        if index < 1 or index > len(obj.Shape.Edges):
            raise ValueError(f"Edge index out of range: {edge_name}")
        selected.append(obj.Shape.Edges[index - 1])
    try:
        wire = Part.Wire(selected)
    except Exception as error:
        raise ValueError("Edges do not form a connected wire; list them in connected order "
                         f"({error})") from error
    if wire.isNull() or not wire.isValid():
        raise ValueError("Ordered edges do not form a valid wire")
    if closed and not wire.isClosed():
        raise ValueError("Ordered edges do not form a closed wire")
    result = _feature_from_shape(doc, name, wire, [obj.Name])
    obj.Visibility = False
    return _shape_result(result)


def make_face(outer_wire_name: str, hole_wire_names: list = None,
              name: str = "Face", doc_name: str = None) -> dict:
    """Build a planar face from a closed outer wire and optional hole wires."""
    doc = _get_doc(doc_name)
    names = [outer_wire_name] + list(hole_wire_names or [])
    wires = []
    for wire_name in names:
        obj = _get_object(wire_name, doc.Name)
        shape = _require_shape(obj, {"Wire"})
        if not shape.isClosed():
            raise ValueError(f"Wire '{wire_name}' is not closed")
        wires.append(shape)
    oriented_wires = [wires[0]]
    face = Part.Face(oriented_wires)
    for hole_wire in wires[1:]:
        candidates = [hole_wire.copy(), hole_wire.copy()]
        candidates[1].reverse()
        previous_area = face.Area
        accepted = None
        for candidate in candidates:
            attempted = Part.Face(oriented_wires + [candidate])
            if attempted.isValid() and attempted.Area < previous_area:
                accepted = (candidate, attempted)
                break
        if accepted is None:
            raise ValueError("Hole wire must be coplanar and strictly inside the outer wire")
        oriented_wires.append(accepted[0])
        face = accepted[1]
    result = _feature_from_shape(doc, name, face, names)
    for wire_name in names:
        _get_object(wire_name, doc.Name).Visibility = False
    return _shape_result(result)


def make_shell(face_names: list, name: str = "Shell",
               doc_name: str = None) -> dict:
    """Build a shell from individual face objects."""
    doc = _get_doc(doc_name)
    if not face_names:
        raise ValueError("At least one face is required")
    faces = []
    for face_name in face_names:
        obj = _get_object(face_name, doc.Name)
        shape = _require_shape(obj, {"Face"})
        faces.append(shape)
    shell = Part.makeShell(faces)
    if shell.ShapeType != "Shell" or len(shell.Faces) != len(set(face.hashCode() for face in faces)):
        raise ValueError("Faces do not form one connected shell; every face must share edges with the others")
    result = _feature_from_shape(doc, name, shell, face_names)
    for face_name in face_names:
        _get_object(face_name, doc.Name).Visibility = False
    return _shape_result(result)


def make_solid(shell_name: str, name: str = "Solid",
               doc_name: str = None) -> dict:
    """Convert one closed shell to a solid; open shells are rejected."""
    doc = _get_doc(doc_name)
    shell_obj = _get_object(shell_name, doc.Name)
    shell = _require_shape(shell_obj, {"Shell"})
    if not shell.isClosed():
        raise ValueError(f"Shell '{shell_name}' is not closed")
    solid = Part.makeSolid(shell)
    if solid.ShapeType != "Solid" or len(solid.Solids) != 1 or solid.Volume <= 0:
        raise RuntimeError("Closed shell did not produce exactly one solid")
    result = _feature_from_shape(doc, name, solid, [shell_name])
    shell_obj.Visibility = False
    return _shape_result(result)


def extrude(obj_name: str, vector_x: float, vector_y: float, vector_z: float,
            solid: bool = True, name: str = "Extrusion",
            doc_name: str = None) -> dict:
    """Extrude a wire or face along a non-zero vector."""
    doc = _get_doc(doc_name)
    source = _get_object(obj_name, doc.Name)
    shape = _require_shape(source, {"Wire", "Face"})
    vector = Vector(_finite("vector_x", vector_x), _finite("vector_y", vector_y), _finite("vector_z", vector_z))
    if vector.Length <= 0:
        raise ValueError("Extrusion vector must be non-zero")
    if solid and shape.ShapeType == "Wire" and not shape.isClosed():
        raise ValueError("A solid extrusion requires a closed wire or face")
    if solid and shape.ShapeType == "Wire":
        shape = Part.Face(shape)
    extruded = shape.extrude(vector)
    if not solid and extruded.ShapeType == "Solid":
        extruded = Part.makeShell(extruded.Faces)
    if solid and len(extruded.Solids) != 1:
        raise ValueError("Extrusion did not produce a solid; the vector must not lie in the profile plane")
    _require_extent(extruded, "Extrusion", solid, "the vector must not lie in the profile plane")
    result = _feature_from_shape(doc, name, extruded, [obj_name])
    source.Visibility = False
    return _shape_result(result)


def revolve(obj_name: str, axis_x: float = 0, axis_y: float = 0,
            axis_z: float = 1, angle: float = 360,
            center_x: float = 0, center_y: float = 0, center_z: float = 0,
            solid: bool = True, name: str = "Revolution",
            doc_name: str = None) -> dict:
    """Revolve a wire or face about an axis."""
    doc = _get_doc(doc_name)
    source = _get_object(obj_name, doc.Name)
    shape = _require_shape(source, {"Wire", "Face"})
    axis = Vector(_finite("axis_x", axis_x), _finite("axis_y", axis_y), _finite("axis_z", axis_z))
    center = Vector(_finite("center_x", center_x), _finite("center_y", center_y), _finite("center_z", center_z))
    if axis.Length <= 0:
        raise ValueError("Revolution axis must be non-zero")
    if not 0 < _finite("angle", angle) <= 360:
        raise ValueError("Revolution angle must be in (0, 360]")
    if solid and shape.ShapeType == "Wire" and not shape.isClosed():
        raise ValueError("A solid revolution requires a closed wire or face")
    if solid and shape.ShapeType == "Wire":
        shape = Part.Face(shape)
    try:
        revolved = shape.revolve(center, axis, angle)
    except Exception as error:
        raise ValueError("Revolution failed; the profile must not cross or touch the axis from both sides "
                         f"({error})") from error
    if not solid and revolved.ShapeType == "Solid":
        revolved = Part.makeShell(revolved.Faces)
    if solid and len(revolved.Solids) != 1:
        raise ValueError("Revolution did not produce a solid")
    _require_extent(revolved, "Revolution", solid, "the axis must lie in the plane of the profile")
    result = _feature_from_shape(doc, name, revolved, [obj_name])
    source.Visibility = False
    return _shape_result(result)


def loft(section_names: list, solid: bool = True, ruled: bool = False,
         closed: bool = False, name: str = "Loft",
         doc_name: str = None) -> dict:
    """Loft through ordered wire sections; closed=True needs at least three sections."""
    doc = _get_doc(doc_name)
    if len(section_names) < 2:
        raise ValueError("Loft requires at least two sections")
    if closed and len(section_names) < 3:
        raise ValueError("A closed loft requires at least three sections")
    sections = []
    for section_name in section_names:
        section = _get_object(section_name, doc.Name)
        shape = _require_shape(section, {"Wire"})
        if solid and not shape.isClosed():
            raise ValueError(f"Solid loft section '{section_name}' is not closed")
        sections.append(shape)
    lofted = Part.makeLoft(sections, solid, ruled, closed)
    if solid and len(lofted.Solids) != 1:
        raise ValueError("Loft did not produce exactly one solid")
    _require_extent(lofted, "Loft", solid, "the sections must enclose a volume")
    result = _feature_from_shape(doc, name, lofted, section_names)
    for section_name in section_names:
        _get_object(section_name, doc.Name).Visibility = False
    return _shape_result(result)


# OCC BRepBuilderAPI_TransitionMode values accepted by Shape.makePipeShell.
_SWEEP_TRANSITIONS = {"transformed": 0, "right_corner": 1, "round": 2}


def _tangent_continuous(path, tolerance=1e-7):
    """True when every joint between the path edges is G1 (no corner)."""
    ends = [(edge.valueAt(parameter), edge.tangentAt(parameter), index)
            for index, edge in enumerate(path.Edges) for parameter in (edge.FirstParameter, edge.LastParameter)]
    for first in range(len(ends)):
        for second in range(first + 1, len(ends)):
            point, tangent, owner = ends[first]
            other, other_tangent, other_owner = ends[second]
            if owner != other_owner and point.distanceToPoint(other) <= tolerance:
                if 1e-6 < tangent.getAngle(other_tangent) < math.pi - 1e-6:
                    return False
    return True


def sweep(profile_name: str, path_name: str, solid: bool = True,
          frenet: bool = False, transition: str = "transformed",
          name: str = "Sweep", doc_name: str = None) -> dict:
    """Sweep one constant wire profile along a wire path."""
    doc = _get_doc(doc_name)
    profile_obj = _get_object(profile_name, doc.Name)
    path_obj = _get_object(path_name, doc.Name)
    profile = _require_shape(profile_obj, {"Wire"})
    path = _require_shape(path_obj, {"Wire"})
    if solid and not profile.isClosed():
        raise ValueError("A solid sweep requires a closed profile")
    if transition not in _SWEEP_TRANSITIONS:
        raise ValueError("Transition must be transformed, right_corner, or round")
    if transition == "transformed" and not _tangent_continuous(path):
        # FreeCAD 1.1 silently sweeps only the first segment of a path with a non-tangent joint.
        raise ValueError("transition 'transformed' requires a tangent-continuous path; "
                         "use 'right_corner' or 'round' for paths with corners")
    try:
        swept = path.makePipeShell([profile], solid, bool(frenet), _SWEEP_TRANSITIONS[transition])
    except Exception as error:
        raise ValueError("Sweep failed; the profile must be roughly perpendicular to the path start "
                         f"({error})") from error
    if solid and len(swept.Solids) != 1:
        raise ValueError("Sweep did not produce one solid; the profile must be roughly perpendicular to the "
                         "path start and must not coincide with the path")
    _require_extent(swept, "Sweep", solid, "the profile must not lie along the path")
    result = _feature_from_shape(doc, name, swept, [profile_name, path_name])
    profile_obj.Visibility = False
    path_obj.Visibility = False
    return _shape_result(result)


# =============================================================================
# Part analysis, intersection, offsets, and repair
# =============================================================================


def validate_shape(obj_name: str, doc_name: str = None) -> dict:
    """Return bounded BRep validity and topology diagnostics without mutation."""
    doc = _get_doc(doc_name)
    obj = _get_object(obj_name, doc.Name)
    if not hasattr(obj, "Shape"):
        return {"name": obj.Name, "quality": _shape_quality(None),
                "diagnostics": ["object_has_no_shape"]}
    shape = obj.Shape
    quality = _shape_quality(shape)
    diagnostics = []
    if quality["null"]:
        diagnostics.append("null_shape")
    elif not quality["valid"]:
        diagnostics.append("brep_invalid")
    if not quality.get("closed", False) and quality.get("num_shells", 0):
        diagnostics.append("open_shell")
    if quality.get("num_solids", 0) > 1:
        diagnostics.append("multiple_solids")
    return {"name": obj.Name, "quality": quality, "diagnostics": diagnostics}


def section(first_name: str, second_name: str, name: str = "Section",
            doc_name: str = None) -> dict:
    """Create intersection curves between two shapes."""
    doc = _get_doc(doc_name)
    first = _get_object(first_name, doc.Name)
    second = _get_object(second_name, doc.Name)
    first_shape = _require_shape(first)
    second_shape = _require_shape(second)
    result_shape = first_shape.section(second_shape)
    if result_shape.isNull() or not result_shape.isValid() or not result_shape.Edges:
        raise ValueError("Shapes do not produce section curves")
    result = _feature_from_shape(doc, name, result_shape, [first_name, second_name])
    return _shape_result(result)


def split_shape(obj_name: str, tool_name: str = None,
                plane_origin: list = None, plane_normal: list = None,
                name: str = "Split", doc_name: str = None) -> dict:
    """Split a shape with another shape or a sufficiently large planar face."""
    from BOPTools import SplitAPI

    doc = _get_doc(doc_name)
    source = _get_object(obj_name, doc.Name)
    source_shape = _require_shape(source)
    if not source_shape.Solids:
        raise ValueError("part_split requires a source with at least one solid")
    if (tool_name is None) == (plane_normal is None):
        raise ValueError("Specify exactly one of tool_name or plane_normal")
    if tool_name is not None:
        tool = _get_object(tool_name, doc.Name)
        tools = [_require_shape(tool)]
        source_names = [obj_name, tool_name]
    else:
        if not isinstance(plane_origin, list) or len(plane_origin) != 3:
            raise ValueError("plane_origin must contain three coordinates")
        if not isinstance(plane_normal, list) or len(plane_normal) != 3:
            raise ValueError("plane_normal must contain three components")
        origin = Vector(*(_finite("plane_origin", value) for value in plane_origin))
        normal = Vector(*(_finite("plane_normal", value) for value in plane_normal))
        if normal.Length <= 0:
            raise ValueError("plane_normal must be non-zero")
        # Part.makePlane chooses its own in-plane axes, so the sheet is re-centered on plane_origin afterwards.
        size = max(source_shape.BoundBox.DiagonalLength * 4, 1.0)
        sheet = Part.makePlane(size, size, Vector(), normal.normalize())
        sheet.translate(origin - sheet.CenterOfMass)
        tools = [sheet]
        source_names = [obj_name]
    split = SplitAPI.slice(source_shape, tools, "Split")
    solids = list(split.Solids)
    if len(solids) < 2:
        raise ValueError("Splitter did not divide the source into at least two solids; "
                         "the plane or tool must cut through the solid")
    result_shape = Part.makeCompound(solids)
    result = _feature_from_shape(doc, name, result_shape, source_names)
    source.Visibility = False
    if tool_name is not None:
        _get_object(tool_name, doc.Name).Visibility = False
    response = _shape_result(result)
    response["num_parts"] = len(solids)
    response["parts_volume"] = sum(solid.Volume for solid in solids)
    response["part_volumes"] = sorted(solid.Volume for solid in solids)
    return response


def offset_2d(obj_name: str, distance: float, join: str = "arc",
              fill: bool = False, name: str = "Offset2D",
              doc_name: str = None) -> dict:
    """Offset a planar wire in its plane."""
    doc = _get_doc(doc_name)
    source = _get_object(obj_name, doc.Name)
    wire = _require_shape(source, {"Wire"})
    if _finite("distance", distance) == 0:
        raise ValueError("Offset distance must be non-zero")
    joins = {"arc": 0, "tangent": 1, "intersection": 2}
    if join not in joins:
        raise ValueError("Join must be arc, tangent, or intersection")
    try:
        offset = wire.makeOffset2D(distance, joins[join], bool(fill))
    except Exception as error:
        raise ValueError(f"2D offset of {distance:g} mm failed or collapsed the wire with join '{join}' "
                         f"({error})") from error
    result = _feature_from_shape(doc, name, offset, [obj_name])
    source.Visibility = False
    return _shape_result(result)


def offset_shape(obj_name: str, distance: float, tolerance: float = 0.01,
                 join: str = "arc", fill: bool = False,
                 name: str = "OffsetShape", doc_name: str = None) -> dict:
    """Create a 3D offset of a face, shell, or solid (join arc or intersection)."""
    from freecad_ai_bridge.contracts import BridgeError

    doc = _get_doc(doc_name)
    source = _get_object(obj_name, doc.Name)
    shape = _require_shape(source, {"Face", "Shell", "Solid"})
    if _finite("distance", distance) == 0 or _finite("tolerance", tolerance) <= 0:
        raise ValueError("Offset distance must be non-zero and tolerance positive")
    if shape.ShapeType == "Solid" and fill:
        raise ValueError("fill=true is not supported for an already closed solid")
    joins = {"arc": 0, "tangent": 1, "intersection": 2}
    if join not in joins:
        raise ValueError("Join must be arc, tangent, or intersection")
    if join == "tangent":
        raise BridgeError("unsupported_feature",
                          "join='tangent' is not supported by the OpenCASCADE 3D offset kernel "
                          "(verified to fail for planar, spherical, cylindrical, conical, toroidal faces, "
                          "shells and solids on FreeCAD 1.1.4); use 'arc' or 'intersection'",
                          [{"document": doc.Name, "object": source.Name}])
    try:
        offset = shape.makeOffsetShape(distance, tolerance, False, False, 0, joins[join], bool(fill))
    except Exception as error:
        raise ValueError(f"3D offset of {distance:g} mm failed or collapsed the shape with join '{join}' "
                         f"({error})") from error
    result = _feature_from_shape(doc, name, offset, [obj_name])
    source.Visibility = False
    return _shape_result(result)


def refine_shape(obj_name: str, name: str = "Refined",
                 doc_name: str = None) -> dict:
    """Remove redundant splitter edges without changing intended volume."""
    doc = _get_doc(doc_name)
    source = _get_object(obj_name, doc.Name)
    shape = _require_shape(source)
    before = _shape_quality(shape)
    refined = shape.removeSplitter()
    result = _feature_from_shape(doc, name, refined, [obj_name])
    source.Visibility = False
    response = _shape_result(result)
    response.update(before=before, after=_shape_quality(refined))
    return response


def _heal_axis_aligned_hexahedron(faces, tolerance):
    """Rebuild six near-rectangular axis-aligned faces when all gaps are bounded."""
    if len(faces) != 6:
        return None
    planes = {0: [], 1: [], 2: []}
    for face in faces:
        if type(face.Surface).__name__ != "Plane":
            return None
        normal = face.normalAt(0, 0)
        components = [abs(normal.x), abs(normal.y), abs(normal.z)]
        axis = components.index(max(components))
        if components[axis] < 1 - 1e-7 or any(components[index] > 1e-7 for index in range(3) if index != axis):
            return None
        coordinates = [vertex.Point[axis] for vertex in face.Vertexes]
        plane = sum(coordinates) / len(coordinates)
        if any(abs(coordinate - plane) > tolerance for coordinate in coordinates):
            return None
        planes[axis].append((plane, face))
    if any(len(entries) != 2 for entries in planes.values()):
        return None
    bounds = [[min(entry[0] for entry in planes[axis]), max(entry[0] for entry in planes[axis])]
              for axis in range(3)]
    if any(high - low <= tolerance for low, high in bounds):
        return None
    for axis, entries in planes.items():
        for _plane, face in entries:
            for vertex in face.Vertexes:
                for coordinate_axis in range(3):
                    if coordinate_axis == axis:
                        continue
                    coordinate = vertex.Point[coordinate_axis]
                    if min(abs(coordinate - bound) for bound in bounds[coordinate_axis]) > tolerance:
                        return None
    origin = Vector(bounds[0][0], bounds[1][0], bounds[2][0])
    return Part.makeBox(bounds[0][1] - bounds[0][0], bounds[1][1] - bounds[1][0],
                        bounds[2][1] - bounds[2][0], origin)


def sew_faces(face_names: list, tolerance: float = 0.01,
              name: str = "Sewing", doc_name: str = None) -> dict:
    """Sew faces within an explicit positive tolerance into a shell or solid."""
    doc = _get_doc(doc_name)
    if not face_names or _finite("tolerance", tolerance) <= 0 or tolerance > 1:
        raise ValueError("face_names must be nonempty and tolerance in (0, 1] mm")
    before = []
    faces = []
    for face_name in face_names:
        face = _require_shape(_get_object(face_name, doc.Name), {"Face"})
        before.append(_shape_quality(face))
        faces.append(face)
    sewed = Part.makeCompound(faces)
    sewed.sewShape(tolerance)
    if sewed.isNull() or not sewed.isValid():
        raise ValueError("Faces could not be sewn into a valid shape within tolerance")
    healing_mode = "native_sewing"
    if sewed.ShapeType == "Shell" and sewed.isClosed():
        sewed = Part.makeSolid(sewed)
    if not sewed.Solids:
        healed = _heal_axis_aligned_hexahedron(faces, tolerance)
        if healed is not None:
            sewed = healed
            healing_mode = "axis_aligned_planar_hexahedron"
    result = _feature_from_shape(doc, name, sewed, face_names)
    for face_name in face_names:
        _get_object(face_name, doc.Name).Visibility = False
    response = _shape_result(result)
    response.update(tolerance=tolerance, healing_mode=healing_mode,
                    before=before, after=_shape_quality(sewed))
    return response


def _quality_changed(before, after):
    for key in ("valid", "closed", "num_vertices", "num_edges", "num_wires", "num_faces", "num_shells", "num_solids"):
        if before.get(key) != after.get(key):
            return True
    return any(abs(before[key] - after[key]) > 1e-9 * max(1.0, abs(before[key])) for key in ("area", "volume"))


def repair_shape(obj_name: str, tolerance: float = 0.01,
                 max_tolerance: float = 0.1, name: str = "Repaired",
                 doc_name: str = None) -> dict:
    """Run bounded OpenCascade shape fixing on a copy of one shape.

    `changed` compares validity, topology counts, area and volume before and after; the raw kernel flag is
    reported as `native_fix_reported` because it is true even for shapes that were already valid.
    """
    doc = _get_doc(doc_name)
    source = _get_object(obj_name, doc.Name)
    if (_finite("tolerance", tolerance) <= 0 or _finite("max_tolerance", max_tolerance) < tolerance
            or max_tolerance > 1):
        raise ValueError("Require 0 < tolerance <= max_tolerance <= 1 mm")
    shape = _require_shape(source).copy()
    before = _shape_quality(shape)
    native_changed = bool(shape.fix(tolerance, tolerance, max_tolerance))
    if shape.isNull() or not shape.isValid():
        raise ValueError("Shape is not repairable within max_tolerance")
    result = _feature_from_shape(doc, name, shape, [obj_name])
    source.Visibility = False
    response = _shape_result(result)
    after = _shape_quality(shape)
    response.update(changed=_quality_changed(before, after), native_fix_reported=native_changed,
                    tolerance=tolerance, max_tolerance=max_tolerance, before=before, after=after)
    return response


# =============================================================================
# Boolean Operations
# =============================================================================


def _boolean_operands(doc_name, names, label):
    doc = _get_doc(doc_name)
    if not isinstance(names, list) or len(names) < 2:
        raise ValueError(f"{label} requires at least two objects")
    if len(set(names)) != len(names):
        raise ValueError(f"{label} operands must be distinct objects")
    objects = [_get_object(n, doc.Name) for n in names]
    for obj in objects:
        _require_shape(obj)
    return doc, objects


def _boolean_result(feature, objects, empty_message):
    """Validate a recomputed Part boolean; a result without volume or elements is not a success."""
    quality_before = {obj.Name: _shape_quality(_require_shape(obj)) for obj in objects}
    result = _shape_result(feature)
    shape = feature.Shape
    if all(obj.Shape.Solids for obj in objects):
        reference = max(abs(obj.Shape.Volume) for obj in objects)
        if not shape.Solids or abs(shape.Volume) <= 1e-9 * max(reference, 1e-12):
            raise ValueError(empty_message)
    elif not shape.Vertexes:
        raise ValueError(empty_message)
    for obj in objects:
        obj.Visibility = False
    result["quality"] = {"inputs": quality_before, "output": _shape_quality(shape)}
    return result


def boolean_fuse(obj_names: list, name: str = "Fuse", doc_name: str = None) -> dict:
    """Fuse (union) two or more distinct objects."""
    doc, objects = _boolean_operands(doc_name, obj_names, "Fuse")
    fuse = doc.addObject("Part::MultiFuse", name)
    fuse.Shapes = objects
    doc.recompute()
    return _boolean_result(fuse, objects, "Fuse produced an empty result")


def boolean_cut(base_name: str, tool_name: str, name: str = "Cut",
                doc_name: str = None) -> dict:
    """Cut tool from base (subtraction); the base must not be consumed entirely."""
    if base_name == tool_name:
        raise ValueError("Cut base and tool must be different objects")
    doc = _get_doc(doc_name)
    base = _get_object(base_name, doc.Name)
    tool = _get_object(tool_name, doc.Name)
    _require_shape(base)
    _require_shape(tool)

    cut = doc.addObject("Part::Cut", name)
    cut.Base = base
    cut.Tool = tool
    doc.recompute()
    return _boolean_result(cut, [base, tool], "Cut removed the entire base; the tool covers the whole base solid")


def boolean_common(obj_names: list, name: str = "Common",
                   doc_name: str = None) -> dict:
    """Common (intersection) of two or more distinct objects; the operands must share volume."""
    doc, objects = _boolean_operands(doc_name, obj_names, "Common")
    common = doc.addObject("Part::MultiCommon", name)
    common.Shapes = objects
    doc.recompute()
    return _boolean_result(common, objects, "Common is empty; the operands share no volume")


# =============================================================================
# Part-level Fillet & Chamfer
# =============================================================================


def _dressup_edges(doc, obj, edges):
    """Resolve edge references to unique 1-based indices; legacy EdgeN/int stay valid for batch steps."""
    from freecad_ai_bridge.geometry_ops import _selection_names

    names = _selection_names(doc.Name, obj.Name, edges, "edge")
    indices = []
    for edge in names:
        if type(edge) is int and edge >= 1:
            indices.append(edge)
        elif isinstance(edge, str) and re.fullmatch(r"Edge[1-9][0-9]*", edge):
            indices.append(int(edge[4:]))
        else:
            raise ValueError(f"Invalid edge reference {edge!r}; use revision-checked selections")
    if len(set(indices)) != len(indices):
        raise ValueError("edges must not contain duplicates")
    count = len(obj.Shape.Edges)
    for index in indices:
        if index > count:
            raise ValueError(f"Edge{index} does not exist on '{obj.Name}' ({count} edges)")
    return indices


def _dressup_effect(feature, base, hint):
    result = _shape_result(feature, hint)
    if base.Shape.Solids and abs(feature.Shape.Volume - base.Shape.Volume) <= max(
            1e-9, 1e-9 * abs(base.Shape.Volume)):
        raise ValueError(f"'{feature.Name}' had no effect on the solid; {hint}")
    return result


def part_fillet(obj_name: str, edges: list, radius: float,
                name: str = "Fillet", doc_name: str = None) -> dict:
    """Add a constant-radius fillet to edges of a Part object (parametric Part::Fillet).

    Args:
        obj_name: Object name
        edges: Revision-checked edge selections (batch steps may use legacy EdgeN names or 1-based integers)
        radius: Fillet radius in mm, greater than 0
    """
    radius = _positive("radius", radius)
    doc = _get_doc(doc_name)
    obj = _get_object(obj_name, doc.Name)
    _require_shape(obj)
    indices = _dressup_edges(doc, obj, edges)

    fillet = doc.addObject("Part::Fillet", name)
    fillet.Base = obj
    fillet.Edges = [(index, radius, radius) for index in indices]
    doc.recompute()

    result = _dressup_effect(fillet, obj, f"radius {radius:g} mm may be too large for the selected edges")
    obj.Visibility = False
    return result


def part_chamfer(obj_name: str, edges: list, size: float,
                 name: str = "Chamfer", doc_name: str = None) -> dict:
    """Add an equal-distance chamfer to edges of a Part object (parametric Part::Chamfer)."""
    size = _positive("size", size)
    doc = _get_doc(doc_name)
    obj = _get_object(obj_name, doc.Name)
    _require_shape(obj)
    indices = _dressup_edges(doc, obj, edges)

    chamfer = doc.addObject("Part::Chamfer", name)
    chamfer.Base = obj
    chamfer.Edges = [(index, size, size) for index in indices]
    doc.recompute()

    result = _dressup_effect(chamfer, obj, f"chamfer size {size:g} mm may be too large for the selected edges")
    obj.Visibility = False
    return result


# =============================================================================
# Transform Operations
# =============================================================================


def _placement_state(obj):
    placement = obj.Placement
    return {"position": [placement.Base.x, placement.Base.y, placement.Base.z],
            "quaternion": [float(value) for value in placement.Rotation.Q]}


def set_placement(obj_name: str, x: float = 0, y: float = 0, z: float = 0,
                  rx: float = 0, ry: float = 0, rz: float = 0,
                  doc_name: str = None) -> dict:
    """Set position and rotation of an object.

    Args:
        rx, ry, rz: X/Y/Z rotation angles in degrees, applied X then Y then Z
    """
    values = [_finite(label, value) for label, value in
              (("x", x), ("y", y), ("z", z), ("rx", rx), ("ry", ry), ("rz", rz))]
    doc = _get_doc(doc_name)
    obj = _get_object(obj_name, doc_name)

    obj.Placement = Placement(
        Vector(*values[:3]),
        Rotation(values[5], values[4], values[3])
    )
    doc.recompute()
    return {"name": obj.Name, "placement": str(obj.Placement), **_placement_state(obj)}


def move_object(obj_name: str, dx: float = 0, dy: float = 0, dz: float = 0,
                doc_name: str = None) -> dict:
    """Move an object by a relative offset."""
    offset = Vector(*(_finite(label, value) for label, value in (("dx", dx), ("dy", dy), ("dz", dz))))
    doc = _get_doc(doc_name)
    obj = _get_object(obj_name, doc_name)

    obj.Placement.Base = obj.Placement.Base + offset
    doc.recompute()
    return {"name": obj.Name, "position": {"x": obj.Placement.Base.x, "y": obj.Placement.Base.y, "z": obj.Placement.Base.z}}


def rotate_object(obj_name: str, axis_x: float = 0, axis_y: float = 0,
                  axis_z: float = 1, angle: float = 0,
                  doc_name: str = None) -> dict:
    """Rotate an object about its own placement origin around a parent-frame axis.

    Args:
        axis_x, axis_y, axis_z: Nonzero rotation axis vector
        angle: Rotation angle in degrees, applied after the existing rotation
    """
    axis = Vector(_finite("axis_x", axis_x), _finite("axis_y", axis_y), _finite("axis_z", axis_z))
    if axis.Length <= 0:
        raise ValueError("Rotation axis must be non-zero")
    _finite("angle", angle)
    doc = _get_doc(doc_name)
    obj = _get_object(obj_name, doc_name)

    rot = Rotation(axis, angle)
    obj.Placement.Rotation = rot.multiply(obj.Placement.Rotation)
    doc.recompute()
    return {"name": obj.Name, "rotation": str(obj.Placement.Rotation), **_placement_state(obj)}


def scale_object(obj_name: str, factor: float, name: str = None,
                 doc_name: str = None) -> dict:
    """Scale an object uniformly about the global origin (creates an independent copy); 0 < factor <= 1e6."""
    if not 0 < _finite("factor", factor) <= _MAX_SCALE:
        raise ValueError(f"factor must be greater than 0 and at most {_MAX_SCALE:g}")
    doc = _get_doc(doc_name)
    obj = _get_object(obj_name, doc_name)
    shape = _require_shape(obj)

    if not name:
        name = f"{obj.Name}_Scaled"

    scaled_shape = shape.copy()
    scaled_shape.scale(factor)

    new_obj = doc.addObject("Part::Feature", name)
    new_obj.Shape = scaled_shape
    doc.recompute()

    return _shape_result(new_obj)


def mirror_object(obj_name: str, plane: str = "XY", name: str = None,
                  doc_name: str = None) -> dict:
    """Mirror an object across a global coordinate plane through the origin (parametric Part::Mirroring).

    Args:
        plane: 'XY', 'XZ', or 'YZ' (case-insensitive)
    """
    plane_map = {
        "XY": Vector(0, 0, 1),
        "XZ": Vector(0, 1, 0),
        "YZ": Vector(1, 0, 0),
    }
    if not isinstance(plane, str) or plane.upper() not in plane_map:
        raise ValueError("plane must be XY, XZ, or YZ")
    doc = _get_doc(doc_name)
    obj = _get_object(obj_name, doc_name)
    _require_shape(obj)

    if not name:
        name = f"{obj.Name}_Mirrored"

    mirror_obj = doc.addObject("Part::Mirroring", name)
    mirror_obj.Source = obj
    mirror_obj.Normal = plane_map[plane.upper()]
    doc.recompute()

    return _shape_result(mirror_obj)
