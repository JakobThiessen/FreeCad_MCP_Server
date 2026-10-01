"""Part module operations running inside FreeCAD.

Provides primitive creation, boolean operations, and transforms.
"""

import FreeCAD
import FreeCADGui
import Part
from FreeCAD import Vector, Rotation, Placement


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


def _shape_result(obj) -> dict:
    if not hasattr(obj, "Shape") or obj.Shape.isNull() or not obj.Shape.isValid():
        raise RuntimeError(f"Feature '{obj.Name}' produced an empty or invalid shape")
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


# =============================================================================
# Primitives
# =============================================================================


def make_box(length: float, width: float, height: float,
             x: float = 0, y: float = 0, z: float = 0,
             name: str = "Box", doc_name: str = None) -> dict:
    """Create a box primitive."""
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
    """Create a cylinder primitive."""
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
    doc = _get_doc(doc_name)
    obj = doc.addObject("Part::Sphere", name)
    obj.Radius = radius
    obj.Placement.Base = Vector(x, y, z)
    doc.recompute()
    return _shape_result(obj)


def make_cone(radius1: float, radius2: float, height: float,
              x: float = 0, y: float = 0, z: float = 0,
              name: str = "Cone", doc_name: str = None) -> dict:
    """Create a cone primitive."""
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
    """Create a torus primitive."""
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


def make_wire(obj_name: str, edges: list, closed: bool = False,
              name: str = "Wire", doc_name: str = None) -> dict:
    """Build a wire from ordered, revision-checked edges of one object."""
    doc = _get_doc(doc_name)
    obj = _get_object(obj_name, doc.Name)
    _require_shape(obj)

    from freecad_ai_bridge.geometry_ops import _selection_names

    edge_names = _selection_names(doc.Name, obj.Name, edges, "edge")
    selected = []
    for edge_name in edge_names:
        index = int("".join(filter(str.isdigit, str(edge_name))))
        if index < 1 or index > len(obj.Shape.Edges):
            raise ValueError(f"Edge index out of range: {edge_name}")
        selected.append(obj.Shape.Edges[index - 1])
    wire = Part.Wire(selected)
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
    vector = Vector(vector_x, vector_y, vector_z)
    if vector.Length <= 0:
        raise ValueError("Extrusion vector must be non-zero")
    if solid and shape.ShapeType == "Wire" and not shape.isClosed():
        raise ValueError("A solid extrusion requires a closed wire or face")
    if solid and shape.ShapeType == "Wire":
        shape = Part.Face(shape)
    extruded = shape.extrude(vector)
    if not solid and extruded.ShapeType == "Solid":
        extruded = Part.makeShell(extruded.Faces)
    if solid and (len(extruded.Solids) != 1 or extruded.Volume <= 0):
        raise RuntimeError("Extrusion did not produce exactly one solid")
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
    axis = Vector(axis_x, axis_y, axis_z)
    if axis.Length <= 0:
        raise ValueError("Revolution axis must be non-zero")
    if angle <= 0 or angle > 360:
        raise ValueError("Revolution angle must be in (0, 360]")
    if solid and shape.ShapeType == "Wire" and not shape.isClosed():
        raise ValueError("A solid revolution requires a closed wire or face")
    if solid and shape.ShapeType == "Wire":
        shape = Part.Face(shape)
    revolved = shape.revolve(Vector(center_x, center_y, center_z), axis, angle)
    if not solid and revolved.ShapeType == "Solid":
        revolved = Part.makeShell(revolved.Faces)
    if solid and (len(revolved.Solids) != 1 or revolved.Volume <= 0):
        raise RuntimeError("Revolution did not produce exactly one solid")
    result = _feature_from_shape(doc, name, revolved, [obj_name])
    source.Visibility = False
    return _shape_result(result)


def loft(section_names: list, solid: bool = True, ruled: bool = False,
         closed: bool = False, name: str = "Loft",
         doc_name: str = None) -> dict:
    """Loft through ordered wire sections."""
    doc = _get_doc(doc_name)
    if len(section_names) < 2:
        raise ValueError("Loft requires at least two sections")
    sections = []
    for section_name in section_names:
        section = _get_object(section_name, doc.Name)
        shape = _require_shape(section, {"Wire"})
        if solid and not shape.isClosed():
            raise ValueError(f"Solid loft section '{section_name}' is not closed")
        sections.append(shape)
    lofted = Part.makeLoft(sections, solid, ruled, closed)
    if solid and (len(lofted.Solids) != 1 or lofted.Volume <= 0):
        raise RuntimeError("Loft did not produce exactly one solid")
    result = _feature_from_shape(doc, name, lofted, section_names)
    for section_name in section_names:
        _get_object(section_name, doc.Name).Visibility = False
    return _shape_result(result)


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
    transition_modes = {"transformed": 0, "round": 1, "right_corner": 2}
    if transition not in transition_modes:
        raise ValueError("Transition must be transformed, round, or right_corner")
    swept = path.makePipeShell([profile], solid, frenet, transition_modes[transition])
    if solid and (len(swept.Solids) != 1 or swept.Volume <= 0):
        raise RuntimeError("Sweep did not produce exactly one solid")
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
        normal = Vector(*plane_normal)
        if normal.Length <= 0:
            raise ValueError("plane_normal must be non-zero")
        diagonal = max(source_shape.BoundBox.DiagonalLength * 4, 1.0)
        unit_normal = normal.normalize()
        reference = Vector(1, 0, 0) if abs(unit_normal.x) < 0.9 else Vector(0, 1, 0)
        first_axis = unit_normal.cross(reference).normalize()
        second_axis = unit_normal.cross(first_axis).normalize()
        origin = Vector(*plane_origin) - (first_axis + second_axis) * (diagonal / 2)
        tools = [Part.makePlane(diagonal, diagonal, origin, unit_normal)]
        source_names = [obj_name]
    split = SplitAPI.slice(source_shape, tools, "Split")
    solids = list(split.Solids)
    if len(solids) < 2:
        raise ValueError("Splitter did not divide the source into at least two solids")
    result_shape = Part.makeCompound(solids)
    result = _feature_from_shape(doc, name, result_shape, source_names)
    source.Visibility = False
    if tool_name is not None:
        _get_object(tool_name, doc.Name).Visibility = False
    response = _shape_result(result)
    response["num_parts"] = len(solids)
    response["parts_volume"] = sum(solid.Volume for solid in solids)
    return response


def offset_2d(obj_name: str, distance: float, join: str = "arc",
              fill: bool = False, name: str = "Offset2D",
              doc_name: str = None) -> dict:
    """Offset a planar wire in its plane."""
    doc = _get_doc(doc_name)
    source = _get_object(obj_name, doc.Name)
    wire = _require_shape(source, {"Wire"})
    if distance == 0:
        raise ValueError("Offset distance must be non-zero")
    joins = {"arc": 0, "tangent": 1, "intersection": 2}
    if join not in joins:
        raise ValueError("Join must be arc, tangent, or intersection")
    offset = wire.makeOffset2D(distance, joins[join], fill)
    result = _feature_from_shape(doc, name, offset, [obj_name])
    source.Visibility = False
    return _shape_result(result)


def offset_shape(obj_name: str, distance: float, tolerance: float = 0.01,
                 join: str = "arc", fill: bool = False,
                 name: str = "OffsetShape", doc_name: str = None) -> dict:
    """Create a 3D offset of a face, shell, or solid."""
    doc = _get_doc(doc_name)
    source = _get_object(obj_name, doc.Name)
    shape = _require_shape(source, {"Face", "Shell", "Solid"})
    if distance == 0 or tolerance <= 0:
        raise ValueError("Offset distance must be non-zero and tolerance positive")
    if shape.ShapeType == "Solid" and fill:
        raise ValueError("fill=true is not supported for an already closed solid")
    joins = {"arc": 0, "tangent": 1, "intersection": 2}
    if join not in joins:
        raise ValueError("Join must be arc, tangent, or intersection")
    offset = shape.makeOffsetShape(distance, tolerance, False, False, 0, joins[join], fill)
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
    if not face_names or tolerance <= 0 or tolerance > 1:
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


def repair_shape(obj_name: str, tolerance: float = 0.01,
                 max_tolerance: float = 0.1, name: str = "Repaired",
                 doc_name: str = None) -> dict:
    """Run bounded OpenCascade shape fixing on a copy of one shape."""
    doc = _get_doc(doc_name)
    source = _get_object(obj_name, doc.Name)
    if tolerance <= 0 or max_tolerance < tolerance or max_tolerance > 1:
        raise ValueError("Require 0 < tolerance <= max_tolerance <= 1 mm")
    shape = _require_shape(source).copy()
    before = _shape_quality(shape)
    changed = bool(shape.fix(tolerance, tolerance, max_tolerance))
    if shape.isNull() or not shape.isValid():
        raise ValueError("Shape is not repairable within max_tolerance")
    result = _feature_from_shape(doc, name, shape, [obj_name])
    source.Visibility = False
    response = _shape_result(result)
    response.update(changed=changed, tolerance=tolerance, max_tolerance=max_tolerance,
                    before=before, after=_shape_quality(shape))
    return response


# =============================================================================
# Boolean Operations
# =============================================================================


def boolean_fuse(obj_names: list, name: str = "Fuse", doc_name: str = None) -> dict:
    """Fuse (union) multiple objects."""
    doc = _get_doc(doc_name)
    objects = [_get_object(n, doc_name) for n in obj_names]

    fuse = doc.addObject("Part::MultiFuse", name)
    fuse.Shapes = objects
    doc.recompute()

    quality_before = {obj.Name: _shape_quality(_require_shape(obj)) for obj in objects}
    for obj in objects:
        obj.Visibility = False
    result = _shape_result(fuse)
    result["quality"] = {"inputs": quality_before, "output": _shape_quality(fuse.Shape)}
    return result


def boolean_cut(base_name: str, tool_name: str, name: str = "Cut",
                doc_name: str = None) -> dict:
    """Cut tool from base (subtraction)."""
    doc = _get_doc(doc_name)
    base = _get_object(base_name, doc_name)
    tool = _get_object(tool_name, doc_name)

    cut = doc.addObject("Part::Cut", name)
    cut.Base = base
    cut.Tool = tool
    doc.recompute()

    quality_before = {base.Name: _shape_quality(_require_shape(base)),
                      tool.Name: _shape_quality(_require_shape(tool))}
    base.Visibility = False
    tool.Visibility = False
    result = _shape_result(cut)
    result["quality"] = {"inputs": quality_before, "output": _shape_quality(cut.Shape)}
    return result


def boolean_common(obj_names: list, name: str = "Common",
                   doc_name: str = None) -> dict:
    """Common (intersection) of multiple objects."""
    doc = _get_doc(doc_name)
    objects = [_get_object(n, doc_name) for n in obj_names]

    common = doc.addObject("Part::MultiCommon", name)
    common.Shapes = objects
    doc.recompute()

    quality_before = {obj.Name: _shape_quality(_require_shape(obj)) for obj in objects}
    for obj in objects:
        obj.Visibility = False
    result = _shape_result(common)
    result["quality"] = {"inputs": quality_before, "output": _shape_quality(common.Shape)}
    return result


# =============================================================================
# Part-level Fillet & Chamfer
# =============================================================================


def part_fillet(obj_name: str, edges: list, radius: float,
               name: str = "Fillet", doc_name: str = None) -> dict:
    """Add fillet to edges (Part-level, not PartDesign).

    Args:
        obj_name: Object name
        edges: List of edge indices (1-based) or edge names
        radius: Fillet radius
    """
    doc = _get_doc(doc_name)
    obj = _get_object(obj_name, doc_name)

    from freecad_ai_bridge.geometry_ops import _selection_names

    edges = _selection_names(doc.Name, obj.Name, edges, "edge")

    fillet = doc.addObject("Part::Fillet", name)
    fillet.Base = obj

    # Build edge list: [(edge_index, radius, radius), ...]
    edge_list = []
    for e in edges:
        if isinstance(e, int):
            edge_list.append((e, radius, radius))
        else:
            # Extract number from "Edge1" etc.
            idx = int("".join(filter(str.isdigit, str(e))))
            edge_list.append((idx, radius, radius))

    fillet.Edges = edge_list
    doc.recompute()

    obj.Visibility = False
    return _shape_result(fillet)


def part_chamfer(obj_name: str, edges: list, size: float,
                 name: str = "Chamfer", doc_name: str = None) -> dict:
    """Add chamfer to edges (Part-level)."""
    doc = _get_doc(doc_name)
    obj = _get_object(obj_name, doc_name)

    from freecad_ai_bridge.geometry_ops import _selection_names

    edges = _selection_names(doc.Name, obj.Name, edges, "edge")

    chamfer = doc.addObject("Part::Chamfer", name)
    chamfer.Base = obj

    edge_indices = []
    for e in edges:
        if isinstance(e, int):
            edge_indices.append(e)
        else:
            edge_indices.append(int("".join(filter(str.isdigit, str(e)))))

    chamfer.Edges = [(index, size, size) for index in edge_indices]
    doc.recompute()

    obj.Visibility = False
    return _shape_result(chamfer)


# =============================================================================
# Transform Operations
# =============================================================================


def set_placement(obj_name: str, x: float = 0, y: float = 0, z: float = 0,
                  rx: float = 0, ry: float = 0, rz: float = 0,
                  doc_name: str = None) -> dict:
    """Set position and rotation of an object.

    Args:
        rx, ry, rz: X/Y/Z rotation angles in degrees, applied X then Y then Z
    """
    doc = _get_doc(doc_name)
    obj = _get_object(obj_name, doc_name)

    obj.Placement = Placement(
        Vector(x, y, z),
        Rotation(rz, ry, rx)
    )
    doc.recompute()
    return {"name": obj.Name, "placement": str(obj.Placement)}


def move_object(obj_name: str, dx: float = 0, dy: float = 0, dz: float = 0,
                doc_name: str = None) -> dict:
    """Move an object by a relative offset."""
    doc = _get_doc(doc_name)
    obj = _get_object(obj_name, doc_name)

    obj.Placement.Base = obj.Placement.Base + Vector(dx, dy, dz)
    doc.recompute()
    return {"name": obj.Name, "position": {"x": obj.Placement.Base.x, "y": obj.Placement.Base.y, "z": obj.Placement.Base.z}}


def rotate_object(obj_name: str, axis_x: float = 0, axis_y: float = 0,
                  axis_z: float = 1, angle: float = 0,
                  doc_name: str = None) -> dict:
    """Rotate an object around an axis.

    Args:
        axis_x, axis_y, axis_z: Rotation axis vector
        angle: Rotation angle in degrees
    """
    doc = _get_doc(doc_name)
    obj = _get_object(obj_name, doc_name)

    rot = Rotation(Vector(axis_x, axis_y, axis_z), angle)
    obj.Placement.Rotation = rot.multiply(obj.Placement.Rotation)
    doc.recompute()
    return {"name": obj.Name, "rotation": str(obj.Placement.Rotation)}


def scale_object(obj_name: str, factor: float, name: str = None,
                 doc_name: str = None) -> dict:
    """Scale an object uniformly (creates a copy)."""
    doc = _get_doc(doc_name)
    obj = _get_object(obj_name, doc_name)

    if not name:
        name = f"{obj.Name}_Scaled"

    scaled_shape = obj.Shape.copy()
    scaled_shape.scale(factor)

    new_obj = doc.addObject("Part::Feature", name)
    new_obj.Shape = scaled_shape
    doc.recompute()

    return _shape_result(new_obj)


def mirror_object(obj_name: str, plane: str = "XY", name: str = None,
                  doc_name: str = None) -> dict:
    """Mirror an object across a plane.

    Args:
        plane: 'XY', 'XZ', or 'YZ'
    """
    doc = _get_doc(doc_name)
    obj = _get_object(obj_name, doc_name)

    if not name:
        name = f"{obj.Name}_Mirrored"

    mirror_obj = doc.addObject("Part::Mirroring", name)
    mirror_obj.Source = obj

    plane_map = {
        "XY": Vector(0, 0, 1),
        "XZ": Vector(0, 1, 0),
        "YZ": Vector(1, 0, 0),
    }
    mirror_obj.Normal = plane_map.get(plane.upper(), Vector(0, 0, 1))
    doc.recompute()

    return _shape_result(mirror_obj)
