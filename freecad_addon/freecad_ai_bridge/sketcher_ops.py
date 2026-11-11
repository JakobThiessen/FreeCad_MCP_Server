"""Sketcher operations running inside FreeCAD.

Provides geometry creation and constraint management for Sketcher objects.
"""

import math

import FreeCAD
import FreeCADGui
import Part
import Sketcher
from FreeCAD import Vector

# Native Sketcher point positions: 1 start, 2 end, 3 center.
_POINT_POSITIONS = {
    "Point": {1}, "LineSegment": {1, 2}, "Circle": {3}, "ArcOfCircle": {1, 2, 3},
    "Ellipse": {3}, "ArcOfEllipse": {1, 2, 3}, "BSplineCurve": {1, 2},
}
_LINE = {"LineSegment"}
_CIRCULAR = {"Circle", "ArcOfCircle"}
_CURVES = {"LineSegment", "Circle", "ArcOfCircle", "Ellipse", "ArcOfEllipse", "BSplineCurve"}
_DIMENSIONAL = {"Distance", "DistanceX", "DistanceY", "Radius", "Diameter", "Angle"}
_TRIM_PICK_TOLERANCE = 1e-3


def _get_sketch(sketch_name: str, doc_name: str = None):
    """Get a sketch object by name."""
    doc = FreeCAD.getDocument(doc_name) if doc_name else FreeCAD.ActiveDocument
    if not doc:
        raise ValueError("No active document")
    obj = doc.getObject(sketch_name)
    if not obj:
        raise ValueError(f"Sketch '{sketch_name}' not found")
    if obj.TypeId != "Sketcher::SketchObject":
        raise ValueError(f"Object '{sketch_name}' is not a Sketch (is {obj.TypeId})")
    return obj


def _get_constraint_status(sketch, raise_on_failure: bool = True) -> dict:
    """Get the constraint status of a sketch."""
    solver_status = sketch.solve()
    # FreeCAD reports solver diagnostics 1-based; the MCP contract uses 0-based constraint indices.
    conflicting = [index - 1 for index in sketch.ConflictingConstraints]
    redundant = [index - 1 for index in sketch.RedundantConstraints]
    partially_redundant = [index - 1 for index in sketch.PartiallyRedundantConstraints]
    if raise_on_failure and (solver_status != 0 or conflicting or redundant or partially_redundant):
        raise ValueError(
            f"Sketch solver failed with status {solver_status}; conflicting={conflicting}; "
            f"redundant={redundant}; partially_redundant={partially_redundant}"
        )
    dof = sketch.DoF
    return {
        "degrees_of_freedom": dof,
        "fully_constrained": sketch.FullyConstrained,
        "solver_status": solver_status,
        "geometry_count": sketch.GeometryCount,
        "constraint_count": sketch.ConstraintCount,
        "conflicting_constraint_indices": conflicting,
        "redundant_constraint_indices": redundant,
        "partially_redundant_constraint_indices": partially_redundant,
    }


def _require_index(index: int, count: int, kind: str) -> None:
    if not isinstance(index, int) or isinstance(index, bool) or index < 0 or index >= count:
        raise ValueError(f"{kind} index {index!r} is outside 0..{count - 1}")


def _finite(value, label: str, positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{label} must be a finite number")
    if positive and value <= 0:
        raise ValueError(f"{label} must be positive")
    return float(value)


def _xy(point, label: str):
    if (not isinstance(point, (list, tuple)) or len(point) != 2):
        raise ValueError(f"{label} must be an [x, y] pair")
    return _finite(point[0], f"{label} x"), _finite(point[1], f"{label} y")


def _xy_points(points, minimum: int, closed: bool = False) -> list:
    if not isinstance(points, (list, tuple)) or len(points) < minimum:
        raise ValueError(f"At least {minimum} points are required")
    result = [_xy(point, f"Point {index}") for index, point in enumerate(points)]
    pairs = list(zip(result, result[1:])) + ([(result[-1], result[0])] if closed else [])
    if any(first == second for first, second in pairs):
        raise ValueError("Consecutive points must be different")
    return result


def _geometry_type(sketch, geo_idx, label: str = "Geometry") -> str:
    """Native type name for local (>=0), axis (-1 X, -2 Y) or external (<=-3) geometry indices."""
    if isinstance(geo_idx, bool) or not isinstance(geo_idx, int):
        raise ValueError(f"{label} index {geo_idx!r} must be an integer")
    if geo_idx >= 0:
        _require_index(geo_idx, sketch.GeometryCount, label)
        return type(sketch.Geometry[geo_idx]).__name__
    if geo_idx in (-1, -2):
        return "LineSegment"
    external = list(sketch.ExternalGeo)
    if -geo_idx - 1 >= len(external):
        raise ValueError(f"{label} index {geo_idx} is not a sketch axis or projected external geometry")
    return type(external[-geo_idx - 1]).__name__


def _require_type(sketch, geo_idx, allowed: set, purpose: str, label: str = "Geometry",
                  local: bool = False) -> str:
    if local and isinstance(geo_idx, int) and not isinstance(geo_idx, bool) and geo_idx < 0:
        raise ValueError(f"{purpose} requires local sketch geometry, not axis/external index {geo_idx}")
    kind = _geometry_type(sketch, geo_idx, label)
    if kind not in allowed:
        raise ValueError(f"{purpose} requires {'/'.join(sorted(allowed))}; {label.lower()} {geo_idx} is {kind}")
    return kind


def _require_point(sketch, geo_idx, point_idx, label: str = "Point", local: bool = False) -> None:
    if local and isinstance(geo_idx, int) and geo_idx < 0:
        raise ValueError(f"{label} must belong to local sketch geometry, not index {geo_idx}")
    if geo_idx == -1 and point_idx == 1 and not local:
        return
    kind = _geometry_type(sketch, geo_idx, label)
    allowed = set() if geo_idx in (-1, -2) else _POINT_POSITIONS.get(kind, set())
    if isinstance(point_idx, bool) or point_idx not in allowed:
        raise ValueError(f"{label} position {point_idx!r} is invalid for {kind} {geo_idx}; "
                         f"allowed {sorted(allowed) or 'none (use geometry -1 position 1 for the origin)'}")


def _constraint_mode(sketch, index: int, getter: str):
    try:
        return bool(getattr(sketch, getter)(index))
    except (ValueError, RuntimeError):
        return None


# =============================================================================
# Sketch Creation
# =============================================================================


def create_sketch(name: str = "Sketch", plane: str = "XY", offset: float = 0.0,
                  body_name: str = None, doc_name: str = None) -> dict:
    """Create a new sketch on a specified plane.

    Args:
        name: Name for the sketch object
        plane: One of 'XY', 'XZ', 'YZ'
        offset: Offset from the plane
        body_name: If given, attach sketch to this PartDesign Body
        doc_name: Document name (uses active if None)
    """
    doc = FreeCAD.getDocument(doc_name) if doc_name else FreeCAD.ActiveDocument
    if not doc:
        doc = FreeCAD.newDocument("Unnamed")

    # Set plane
    plane_map = {
        "XY": FreeCAD.Placement(
            Vector(0, 0, offset),
            FreeCAD.Rotation(Vector(0, 0, 1), 0)
        ),
        "XZ": FreeCAD.Placement(
            Vector(0, offset, 0),
            FreeCAD.Rotation(Vector(1, 0, 0), -90)
        ),
        "YZ": FreeCAD.Placement(
            Vector(offset, 0, 0),
            FreeCAD.Rotation(Vector(0, 1, 0), 90)
        ),
    }

    if plane.upper() not in plane_map:
        raise ValueError(f"Unknown plane '{plane}'. Use 'XY', 'XZ', or 'YZ'.")

    body = doc.getObject(body_name) if body_name else None
    if body_name and (body is None or body.TypeId != "PartDesign::Body"):
        raise ValueError(f"Body '{body_name}' not found or not a PartDesign Body")
    sketch = doc.addObject("Sketcher::SketchObject", name)
    sketch.Placement = plane_map[plane.upper()]

    # Attach to body if specified
    if body:
        body.addObject(sketch)

    doc.recompute()
    return {"name": sketch.Name, "label": sketch.Label, "plane": plane}


# =============================================================================
# Geometry Operations
# =============================================================================


def add_line(sketch_name: str, x1: float, y1: float, x2: float, y2: float,
             construction: bool = False, doc_name: str = None) -> dict:
    """Add a line segment to a sketch."""
    x1, y1, x2, y2 = (_finite(value, name) for value, name in ((x1, "x1"), (y1, "y1"), (x2, "x2"), (y2, "y2")))
    if (x1, y1) == (x2, y2):
        raise ValueError("Line endpoints must be different")
    sketch = _get_sketch(sketch_name, doc_name)
    idx = sketch.addGeometry(
        Part.LineSegment(Vector(x1, y1, 0), Vector(x2, y2, 0)),
        construction
    )
    return {"geometry_index": idx, **_get_constraint_status(sketch)}


def add_rectangle(sketch_name: str, x1: float, y1: float, x2: float, y2: float,
                  construction: bool = False, doc_name: str = None) -> dict:
    """Add a rectangle (4 lines + constraints) to a sketch."""
    x1, y1, x2, y2 = (_finite(value, name) for value, name in ((x1, "x1"), (y1, "y1"), (x2, "x2"), (y2, "y2")))
    if x1 == x2 or y1 == y2:
        raise ValueError("Rectangle corners must differ in both x and y")
    sketch = _get_sketch(sketch_name, doc_name)

    # Add 4 lines
    idx0 = sketch.addGeometry(Part.LineSegment(Vector(x1, y1, 0), Vector(x2, y1, 0)), construction)
    idx1 = sketch.addGeometry(Part.LineSegment(Vector(x2, y1, 0), Vector(x2, y2, 0)), construction)
    idx2 = sketch.addGeometry(Part.LineSegment(Vector(x2, y2, 0), Vector(x1, y2, 0)), construction)
    idx3 = sketch.addGeometry(Part.LineSegment(Vector(x1, y2, 0), Vector(x1, y1, 0)), construction)

    # Add coincident constraints to close the rectangle
    sketch.addConstraint(Sketcher.Constraint("Coincident", idx0, 2, idx1, 1))
    sketch.addConstraint(Sketcher.Constraint("Coincident", idx1, 2, idx2, 1))
    sketch.addConstraint(Sketcher.Constraint("Coincident", idx2, 2, idx3, 1))
    sketch.addConstraint(Sketcher.Constraint("Coincident", idx3, 2, idx0, 1))

    # Add horizontal/vertical constraints
    sketch.addConstraint(Sketcher.Constraint("Horizontal", idx0))
    sketch.addConstraint(Sketcher.Constraint("Horizontal", idx2))
    sketch.addConstraint(Sketcher.Constraint("Vertical", idx1))
    sketch.addConstraint(Sketcher.Constraint("Vertical", idx3))

    return {"geometry_indices": [idx0, idx1, idx2, idx3], **_get_constraint_status(sketch)}


def add_circle(sketch_name: str, cx: float, cy: float, radius: float,
               construction: bool = False, doc_name: str = None) -> dict:
    """Add a circle to a sketch."""
    cx, cy = _finite(cx, "cx"), _finite(cy, "cy")
    radius = _finite(radius, "Circle radius", positive=True)
    sketch = _get_sketch(sketch_name, doc_name)
    idx = sketch.addGeometry(
        Part.Circle(Vector(cx, cy, 0), Vector(0, 0, 1), radius),
        construction
    )
    return {"geometry_index": idx, **_get_constraint_status(sketch)}


def add_arc(sketch_name: str, cx: float, cy: float, radius: float,
            start_angle: float, end_angle: float,
            construction: bool = False, doc_name: str = None) -> dict:
    """Add a counterclockwise arc (portion of circle) to a sketch.

    Angles in radians; requires 0 < end_angle - start_angle < 2*pi.
    """
    cx, cy = _finite(cx, "cx"), _finite(cy, "cy")
    radius = _finite(radius, "Arc radius", positive=True)
    start_angle, end_angle = _finite(start_angle, "start_angle"), _finite(end_angle, "end_angle")
    if not 0 < end_angle - start_angle < 2 * math.pi:
        raise ValueError("Arc sweep end_angle - start_angle must be in (0, 2*pi) radians")
    sketch = _get_sketch(sketch_name, doc_name)
    circle = Part.Circle(Vector(cx, cy, 0), Vector(0, 0, 1), radius)
    idx = sketch.addGeometry(
        Part.ArcOfCircle(circle, start_angle, end_angle),
        construction
    )
    return {"geometry_index": idx, **_get_constraint_status(sketch)}


def add_ellipse(sketch_name: str, cx: float, cy: float,
                major_radius: float, minor_radius: float, angle: float = 0.0,
                construction: bool = False, doc_name: str = None) -> dict:
    """Add an ellipse to a sketch; requires major_radius > minor_radius > 0, angle in radians."""
    cx, cy, angle = _finite(cx, "cx"), _finite(cy, "cy"), _finite(angle, "angle")
    major_radius = _finite(major_radius, "major_radius", positive=True)
    minor_radius = _finite(minor_radius, "minor_radius", positive=True)
    if minor_radius >= major_radius:
        raise ValueError("Ellipse requires major_radius > minor_radius > 0")
    sketch = _get_sketch(sketch_name, doc_name)

    # Major axis endpoint
    major_x = cx + major_radius * math.cos(angle)
    major_y = cy + major_radius * math.sin(angle)

    # Minor axis endpoint
    minor_x = cx - minor_radius * math.sin(angle)
    minor_y = cy + minor_radius * math.cos(angle)

    idx = sketch.addGeometry(
        Part.Ellipse(Vector(major_x, major_y, 0), Vector(minor_x, minor_y, 0), Vector(cx, cy, 0)),
        construction
    )
    return {"geometry_index": idx, **_get_constraint_status(sketch)}


def add_bspline(sketch_name: str, points: list,
                construction: bool = False, doc_name: str = None) -> dict:
    """Add an interpolating B-spline through at least two distinct consecutive points.

    Args:
        points: List of [x, y] coordinate pairs
    """
    points = _xy_points(points, 2)
    sketch = _get_sketch(sketch_name, doc_name)
    vectors = [Vector(x, y, 0) for x, y in points]
    bspline = Part.BSplineCurve()
    bspline.interpolate(vectors)
    idx = sketch.addGeometry(bspline, construction)
    return {"geometry_index": idx, **_get_constraint_status(sketch)}


def add_point(sketch_name: str, x: float, y: float,
              construction: bool = False, doc_name: str = None) -> dict:
    """Add a point to a sketch."""
    x, y = _finite(x, "x"), _finite(y, "y")
    sketch = _get_sketch(sketch_name, doc_name)
    idx = sketch.addGeometry(Part.Point(Vector(x, y, 0)), construction)
    return {"geometry_index": idx, **_get_constraint_status(sketch)}


def add_polygon(sketch_name: str, points: list,
                close: bool = True, construction: bool = False,
                doc_name: str = None) -> dict:
    """Add a polygon (multiple connected lines) to a sketch.

    Args:
        points: List of [x, y] coordinate pairs
        close: If True, connect last point back to first
    """
    if len(points) < (3 if close else 2):
        raise ValueError("A closed polygon needs at least three points; an open one needs two")
    points = _xy_points(points, 3 if close else 2, closed=close)
    sketch = _get_sketch(sketch_name, doc_name)
    indices = []

    for i in range(len(points) - 1):
        p1, p2 = points[i], points[i + 1]
        idx = sketch.addGeometry(
            Part.LineSegment(Vector(p1[0], p1[1], 0), Vector(p2[0], p2[1], 0)),
            construction
        )
        indices.append(idx)

    if close and len(points) > 2:
        p1, p2 = points[-1], points[0]
        idx = sketch.addGeometry(
            Part.LineSegment(Vector(p1[0], p1[1], 0), Vector(p2[0], p2[1], 0)),
            construction
        )
        indices.append(idx)

    # Add coincident constraints between consecutive lines
    for i in range(len(indices) - 1):
        sketch.addConstraint(Sketcher.Constraint("Coincident", indices[i], 2, indices[i + 1], 1))

    if close and len(indices) > 1:
        sketch.addConstraint(Sketcher.Constraint("Coincident", indices[-1], 2, indices[0], 1))

    return {"geometry_indices": indices, **_get_constraint_status(sketch)}


def add_slot(sketch_name: str, x1: float, y1: float, x2: float, y2: float,
             radius: float, construction: bool = False, doc_name: str = None) -> dict:
    """Add a slot (two parallel lines connected by semicircles) to a sketch."""
    x1, y1, x2, y2 = (_finite(value, name) for value, name in ((x1, "x1"), (y1, "y1"), (x2, "x2"), (y2, "y2")))
    radius = _finite(radius, "Slot radius")
    if radius <= 0:
        raise ValueError("Slot radius must be positive")
    sketch = _get_sketch(sketch_name, doc_name)

    # Calculate perpendicular direction
    dx = x2 - x1
    dy = y2 - y1
    length = math.sqrt(dx * dx + dy * dy)
    if length == 0:
        raise ValueError("Slot endpoints must be different")

    nx = -dy / length * radius
    ny = dx / length * radius

    # Calculate angle for arcs
    angle = math.atan2(dy, dx)

    # Two parallel lines
    idx0 = sketch.addGeometry(Part.LineSegment(
        Vector(x1 + nx, y1 + ny, 0), Vector(x2 + nx, y2 + ny, 0)), construction)
    idx1 = sketch.addGeometry(Part.LineSegment(
        Vector(x2 - nx, y2 - ny, 0), Vector(x1 - nx, y1 - ny, 0)), construction)

    # Two semicircular arcs
    c1 = Part.Circle(Vector(x2, y2, 0), Vector(0, 0, 1), radius)
    idx2 = sketch.addGeometry(Part.ArcOfCircle(c1, angle - math.pi / 2, angle + math.pi / 2), construction)

    c2 = Part.Circle(Vector(x1, y1, 0), Vector(0, 0, 1), radius)
    idx3 = sketch.addGeometry(Part.ArcOfCircle(c2, angle + math.pi / 2, angle + 3 * math.pi / 2), construction)

    sketch.addConstraint([
        Sketcher.Constraint("Tangent", idx0, 2, idx2, 2),
        Sketcher.Constraint("Tangent", idx2, 1, idx1, 1),
        Sketcher.Constraint("Tangent", idx1, 2, idx3, 2),
        Sketcher.Constraint("Tangent", idx3, 1, idx0, 1),
        Sketcher.Constraint("Equal", idx2, idx3),
    ])

    return {"geometry_indices": [idx0, idx1, idx2, idx3], **_get_constraint_status(sketch)}


def move_geometry_point(sketch_name: str, geo_idx: int, point_idx: int,
                        x: float, y: float, doc_name: str = None) -> dict:
    """Move a geometry point to an absolute sketch-local XY position."""
    sketch = _get_sketch(sketch_name, doc_name)
    _require_point(sketch, geo_idx, point_idx, local=True)
    x, y = _finite(x, "x"), _finite(y, "y")
    sketch.moveGeometry(geo_idx, point_idx, Vector(x, y, 0), False)
    return {"geometry_index": geo_idx, "point_index": point_idx, **_get_constraint_status(sketch)}


def set_geometry_construction(sketch_name: str, geo_idx: int, construction: bool,
                              doc_name: str = None) -> dict:
    """Set whether a geometry element is construction geometry."""
    sketch = _get_sketch(sketch_name, doc_name)
    _require_index(geo_idx, sketch.GeometryCount, "Geometry")
    current = bool(sketch.getConstruction(geo_idx))
    if current != construction:
        sketch.toggleConstruction(geo_idx)
    return {"geometry_index": geo_idx, "construction": bool(sketch.getConstruction(geo_idx)),
            **_get_constraint_status(sketch)}


def delete_geometry(sketch_name: str, geo_idx: int, doc_name: str = None) -> dict:
    """Delete one geometry element and native constraints that depend on it."""
    sketch = _get_sketch(sketch_name, doc_name)
    _require_index(geo_idx, sketch.GeometryCount, "Geometry")
    before_constraints = sketch.ConstraintCount
    sketch.delGeometry(geo_idx)
    return {"deleted_geometry_index": geo_idx,
            "deleted_constraint_count": before_constraints - sketch.ConstraintCount,
            **_get_constraint_status(sketch)}


def _external_count(sketch) -> int:
    # ExternalGeometry groups subelements per source object; count every projected link.
    return sum(len(names) for _obj, names in sketch.ExternalGeometry)


def add_external_geometry(sketch_name: str, selection: dict,
                          defining: bool = False, intersection: bool = False,
                          doc_name: str = None) -> dict:
    """Project one revision-checked external edge into a sketch."""
    from freecad_ai_bridge.geometry_ops import _resolve

    sketch = _get_sketch(sketch_name, doc_name)
    doc, obj, _element, kind = _resolve(selection)
    if doc is not sketch.Document or kind != "edge" or obj is sketch:
        raise ValueError("External geometry must be an edge from another object in the sketch document")
    external_index = _external_count(sketch)
    sketch.addExternal(obj.Name, selection["subelement"], defining, intersection)
    return {"external_index": external_index, "geometry_index": -3 - external_index,
            "source": selection, **_get_constraint_status(sketch)}


def delete_external_geometry(sketch_name: str, external_idx: int,
                             doc_name: str = None) -> dict:
    """Remove an external geometry link by its zero-based external-list index."""
    sketch = _get_sketch(sketch_name, doc_name)
    _require_index(external_idx, _external_count(sketch), "External geometry")
    sketch.delExternal(external_idx)
    return {"deleted_external_index": external_idx, **_get_constraint_status(sketch)}


def set_sketch_attachment(sketch_name: str, support_name: str = None,
                          support_selection: dict = None,
                          offset_x: float = 0.0, offset_y: float = 0.0, offset_z: float = 0.0,
                          rotation_x: float = 0.0, rotation_y: float = 0.0, rotation_z: float = 0.0,
                          doc_name: str = None) -> dict:
    """Attach to a datum plane or revision-checked planar face, or detach when no support is given."""
    from freecad_ai_bridge.geometry_ops import _resolve

    if support_name is not None and support_selection is not None:
        raise ValueError("Provide support_name or support_selection, not both")
    sketch = _get_sketch(sketch_name, doc_name)
    support = None
    subelements = []
    map_mode = "Deactivated"
    if support_selection is not None:
        doc, support, element, kind = _resolve(support_selection)
        if doc is not sketch.Document or kind != "face" or "Plane" not in type(element.Surface).__name__:
            raise ValueError("Sketch face support must be a planar face in the sketch document")
        subelements = [support_selection["subelement"]]
        map_mode = "FlatFace"
    elif support_name is not None:
        support = sketch.Document.getObject(support_name)
        if support is None or support.TypeId != "PartDesign::Plane":
            raise ValueError("Sketch datum support must be a PartDesign datum plane")
        # FreeCAD 1.1 silently drops an object-only support given as an empty subelement list.
        subelements = [""]
        map_mode = "ObjectXY"
    if support is None:
        sketch.AttachmentSupport = []
    else:
        sketch.AttachmentSupport = [(support, subelements)]
        if not sketch.AttachmentSupport:
            raise ValueError(f"FreeCAD rejected attachment support '{support.Name}'")
    sketch.MapMode = map_mode
    sketch.AttachmentOffset = FreeCAD.Placement(
        Vector(offset_x, offset_y, offset_z),
        FreeCAD.Rotation(rotation_z, rotation_y, rotation_x),
    )
    return {"support": None if support is None else {"document": sketch.Document.Name,
                                                       "object": support.Name,
                                                       "subelements": [name for name in subelements if name]},
            "map_mode": sketch.MapMode, **_get_constraint_status(sketch)}


def _record_geometry(sketch) -> None:
    # Native extend/trim/fillet may modify curves in place; re-assigning first lets the open transaction keep the old value.
    sketch.Geometry = list(sketch.Geometry)


def trim_geometry(sketch_name: str, geo_idx: int, x: float, y: float,
                  include_axes: bool = False, doc_name: str = None) -> dict:
    """Trim a line, circle or circular arc at a sketch-local pick point on that curve.

    Without intersections FreeCAD deletes the whole picked element.
    """
    if include_axes:
        raise ValueError("FreeCAD 1.1 does not support trimming against sketch axes")
    sketch = _get_sketch(sketch_name, doc_name)
    _require_type(sketch, geo_idx, _LINE | _CIRCULAR, "Trim", local=True)
    pick = Vector(_finite(x, "x"), _finite(y, "y"), 0)
    distance = sketch.Geometry[geo_idx].toShape().distToShape(Part.Vertex(pick))[0]
    if distance > _TRIM_PICK_TOLERANCE:
        raise ValueError(f"Trim pick point is {distance:.6g} mm from geometry {geo_idx}; "
                         f"it must lie on the curve within {_TRIM_PICK_TOLERANCE} mm")
    before = sketch.GeometryCount
    _record_geometry(sketch)
    sketch.trim(geo_idx, pick)
    return {"source_geometry_index": geo_idx, "geometry_count_before": before,
            **_get_constraint_status(sketch)}


def extend_geometry(sketch_name: str, geo_idx: int, increment: float, point_idx: int,
                    doc_name: str = None) -> dict:
    """Extend a line or circular arc endpoint by a signed increment in mm."""
    if _finite(increment, "Extension increment") == 0:
        raise ValueError("Extension increment must be nonzero")
    sketch = _get_sketch(sketch_name, doc_name)
    _require_type(sketch, geo_idx, _LINE | {"ArcOfCircle"}, "Extend", local=True)
    if point_idx not in {1, 2}:
        raise ValueError("Extension point_idx must be 1 (start) or 2 (end)")
    native_increment = increment
    if isinstance(sketch.Geometry[geo_idx], Part.ArcOfCircle):
        # FreeCAD extends arcs by a parameter angle in rad; the MCP contract is arc length in mm.
        native_increment = increment / sketch.Geometry[geo_idx].Radius
    _record_geometry(sketch)
    sketch.extend(geo_idx, native_increment, point_idx)
    return {"geometry_index": geo_idx, "point_index": point_idx,
            "increment": increment, **_get_constraint_status(sketch)}


def fillet_geometry(sketch_name: str, geo_idx1: int, geo_idx2: int,
                    near1_x: float, near1_y: float, near2_x: float, near2_y: float,
                    radius: float, trim: bool = True, create_corner: bool = True,
                    doc_name: str = None) -> dict:
    """Create a tangent fillet between two lines or circular arcs."""
    if radius <= 0:
        raise ValueError("Fillet radius must be positive")
    sketch = _get_sketch(sketch_name, doc_name)
    _require_type(sketch, geo_idx1, _LINE | {"ArcOfCircle"}, "Fillet", "First geometry", local=True)
    _require_type(sketch, geo_idx2, _LINE | {"ArcOfCircle"}, "Fillet", "Second geometry", local=True)
    if geo_idx1 == geo_idx2:
        raise ValueError("Fillet requires two different geometries")
    before = sketch.GeometryCount
    _record_geometry(sketch)
    sketch.fillet(geo_idx1, geo_idx2, Vector(near1_x, near1_y, 0),
                  Vector(near2_x, near2_y, 0), radius, trim, create_corner, False)
    return {"geometry_indices": list(range(before, sketch.GeometryCount)),
            **_get_constraint_status(sketch)}


def copy_geometry(sketch_name: str, geometry_indices: list, offset_x: float, offset_y: float,
                  clone: bool = False, doc_name: str = None) -> dict:
    """Copy selected local geometry by a sketch-local XY offset."""
    sketch = _get_sketch(sketch_name, doc_name)
    if not geometry_indices or len(set(geometry_indices)) != len(geometry_indices):
        raise ValueError("geometry_indices must be a nonempty list without duplicates")
    for index in geometry_indices:
        _require_index(index, sketch.GeometryCount, "Geometry")
    indices = list(sketch.addCopy(geometry_indices, Vector(offset_x, offset_y, 0), clone))
    return {"geometry_indices": indices, "clone": clone, **_get_constraint_status(sketch)}


def mirror_geometry(sketch_name: str, geometry_indices: list,
                    reference_geo_idx: int, reference_point_idx: int = 0,
                    doc_name: str = None) -> dict:
    """Mirror selected local geometry about a local/external line or point."""
    sketch = _get_sketch(sketch_name, doc_name)
    if not geometry_indices or len(set(geometry_indices)) != len(geometry_indices):
        raise ValueError("geometry_indices must be a nonempty list without duplicates")
    for index in geometry_indices:
        _require_index(index, sketch.GeometryCount, "Geometry")
    if reference_point_idx == 0:
        _require_type(sketch, reference_geo_idx, _LINE, "Mirror about a line", "Reference geometry")
    else:
        _require_point(sketch, reference_geo_idx, reference_point_idx, "Reference point")
    indices = list(sketch.addSymmetric(geometry_indices, reference_geo_idx, reference_point_idx))
    return {"geometry_indices": indices, **_get_constraint_status(sketch)}


# =============================================================================
# Constraint Operations
# =============================================================================


def add_constraint_coincident(sketch_name: str, geo_idx1: int, point_idx1: int,
                              geo_idx2: int, point_idx2: int, doc_name: str = None) -> dict:
    """Add a coincident constraint between two points.

    Point indices: 1 = start point, 2 = end point, 3 = center (for circles/arcs).
    """
    sketch = _get_sketch(sketch_name, doc_name)
    _require_point(sketch, geo_idx1, point_idx1, "First point")
    _require_point(sketch, geo_idx2, point_idx2, "Second point")
    if (geo_idx1, point_idx1) == (geo_idx2, point_idx2):
        raise ValueError("Coincident requires two different points")
    c_idx = sketch.addConstraint(Sketcher.Constraint("Coincident", geo_idx1, point_idx1, geo_idx2, point_idx2))
    return {"constraint_index": c_idx, **_get_constraint_status(sketch)}


def add_constraint_tangent(sketch_name: str, geo_idx1: int, geo_idx2: int,
                           point_idx1: int = None, point_idx2: int = None,
                           doc_name: str = None) -> dict:
    """Add an edge-edge tangent, or an endpoint-to-endpoint tangent when both point indices are given."""
    if (point_idx1 is None) != (point_idx2 is None):
        raise ValueError("Tangent requires both point_idx1 and point_idx2, or neither")
    sketch = _get_sketch(sketch_name, doc_name)
    _require_type(sketch, geo_idx1, _CURVES, "Tangent", "First geometry")
    _require_type(sketch, geo_idx2, _CURVES, "Tangent", "Second geometry")
    if geo_idx1 == geo_idx2:
        raise ValueError("Tangent requires two different geometries")
    if point_idx1 is not None:
        for geo_idx, point_idx, label in ((geo_idx1, point_idx1, "First point"), (geo_idx2, point_idx2, "Second point")):
            if point_idx not in {1, 2}:
                raise ValueError(f"{label} must be an endpoint (1 or 2) for endpoint tangency")
            _require_point(sketch, geo_idx, point_idx, label)
        c_idx = sketch.addConstraint(Sketcher.Constraint("Tangent", geo_idx1, point_idx1, geo_idx2, point_idx2))
    else:
        c_idx = sketch.addConstraint(Sketcher.Constraint("Tangent", geo_idx1, geo_idx2))
    return {"constraint_index": c_idx, **_get_constraint_status(sketch)}


def add_constraint_perpendicular(sketch_name: str, geo_idx1: int, geo_idx2: int,
                                 doc_name: str = None) -> dict:
    """Add a perpendicular constraint between two lines, or a line normal to a circle/arc."""
    sketch = _get_sketch(sketch_name, doc_name)
    kinds = (_require_type(sketch, geo_idx1, _LINE | _CIRCULAR, "Perpendicular", "First geometry"),
             _require_type(sketch, geo_idx2, _LINE | _CIRCULAR, "Perpendicular", "Second geometry"))
    if "LineSegment" not in kinds or geo_idx1 == geo_idx2:
        raise ValueError("Perpendicular requires two different geometries, at least one of them a line")
    c_idx = sketch.addConstraint(Sketcher.Constraint("Perpendicular", geo_idx1, geo_idx2))
    return {"constraint_index": c_idx, **_get_constraint_status(sketch)}


def add_constraint_parallel(sketch_name: str, geo_idx1: int, geo_idx2: int,
                            doc_name: str = None) -> dict:
    """Add a parallel constraint between two lines."""
    sketch = _get_sketch(sketch_name, doc_name)
    _require_type(sketch, geo_idx1, _LINE, "Parallel", "First geometry")
    _require_type(sketch, geo_idx2, _LINE, "Parallel", "Second geometry")
    if geo_idx1 == geo_idx2:
        raise ValueError("Parallel requires two different lines")
    c_idx = sketch.addConstraint(Sketcher.Constraint("Parallel", geo_idx1, geo_idx2))
    return {"constraint_index": c_idx, **_get_constraint_status(sketch)}


def add_constraint_equal(sketch_name: str, geo_idx1: int, geo_idx2: int,
                         doc_name: str = None) -> dict:
    """Add an equal constraint: two lines (length) or two circles/arcs (radius)."""
    sketch = _get_sketch(sketch_name, doc_name)
    first = _require_type(sketch, geo_idx1, _LINE | _CIRCULAR, "Equal", "First geometry")
    second = _require_type(sketch, geo_idx2, _LINE | _CIRCULAR, "Equal", "Second geometry")
    if (first in _LINE) != (second in _LINE) or geo_idx1 == geo_idx2:
        raise ValueError("Equal requires two different lines or two different circles/arcs")
    c_idx = sketch.addConstraint(Sketcher.Constraint("Equal", geo_idx1, geo_idx2))
    return {"constraint_index": c_idx, **_get_constraint_status(sketch)}


def add_constraint_symmetric(sketch_name: str, geo_idx1: int, point_idx1: int,
                             geo_idx2: int, point_idx2: int,
                             sym_geo: int, sym_point: int = None,
                             doc_name: str = None) -> dict:
    """Add a symmetric constraint (two points symmetric about a line, or about a point if sym_point is given)."""
    sketch = _get_sketch(sketch_name, doc_name)
    _require_point(sketch, geo_idx1, point_idx1, "First point")
    _require_point(sketch, geo_idx2, point_idx2, "Second point")
    if (geo_idx1, point_idx1) == (geo_idx2, point_idx2):
        raise ValueError("Symmetric requires two different points")
    args = ["Symmetric", geo_idx1, point_idx1, geo_idx2, point_idx2, sym_geo]
    if sym_point is None:
        _require_type(sketch, sym_geo, _LINE, "Symmetry about a line", "Symmetry geometry")
    else:
        _require_point(sketch, sym_geo, sym_point, "Symmetry point")
        args.append(sym_point)
    c_idx = sketch.addConstraint(Sketcher.Constraint(*args))
    return {"constraint_index": c_idx, **_get_constraint_status(sketch)}


def add_constraint_horizontal(sketch_name: str, geo_idx: int, doc_name: str = None) -> dict:
    """Add a horizontal constraint to a local line."""
    sketch = _get_sketch(sketch_name, doc_name)
    _require_type(sketch, geo_idx, _LINE, "Horizontal", local=True)
    c_idx = sketch.addConstraint(Sketcher.Constraint("Horizontal", geo_idx))
    return {"constraint_index": c_idx, **_get_constraint_status(sketch)}


def add_constraint_vertical(sketch_name: str, geo_idx: int, doc_name: str = None) -> dict:
    """Add a vertical constraint to a local line."""
    sketch = _get_sketch(sketch_name, doc_name)
    _require_type(sketch, geo_idx, _LINE, "Vertical", local=True)
    c_idx = sketch.addConstraint(Sketcher.Constraint("Vertical", geo_idx))
    return {"constraint_index": c_idx, **_get_constraint_status(sketch)}


def add_constraint_lock(sketch_name: str, geo_idx: int, point_idx: int,
                        doc_name: str = None) -> dict:
    """Lock a point at its current position (adds DistanceX + DistanceY from origin)."""
    sketch = _get_sketch(sketch_name, doc_name)
    _require_point(sketch, geo_idx, point_idx, local=True)
    point = sketch.getPoint(geo_idx, point_idx)
    constraints = []
    for kind, value, axis in [("DistanceX", point.x, -2), ("DistanceY", point.y, -1)]:
        if abs(value) < 1e-9:
            constraints.append(Sketcher.Constraint("PointOnObject", geo_idx, point_idx, axis))
        else:
            constraints.append(Sketcher.Constraint(kind, geo_idx, point_idx, value))
    indices = list(sketch.addConstraint(constraints))
    return {"constraint_index": indices[0], "constraint_indices": indices, **_get_constraint_status(sketch)}


def add_constraint_block(sketch_name: str, geo_idx: int, doc_name: str = None) -> dict:
    """Block a local geometry element (prevent any movement)."""
    sketch = _get_sketch(sketch_name, doc_name)
    _require_type(sketch, geo_idx, set(_POINT_POSITIONS), "Block", local=True)
    c_idx = sketch.addConstraint(Sketcher.Constraint("Block", geo_idx))
    return {"constraint_index": c_idx, **_get_constraint_status(sketch)}


def add_constraint_distance(sketch_name: str, geo_idx1: int, point_idx1: int,
                            geo_idx2: int, point_idx2: int, value: float,
                            doc_name: str = None) -> dict:
    """Set a positive distance between two different points; use Coincident for zero distance."""
    value = _finite(value, "Point distance", positive=True)
    sketch = _get_sketch(sketch_name, doc_name)
    _require_point(sketch, geo_idx1, point_idx1, "First point")
    _require_point(sketch, geo_idx2, point_idx2, "Second point")
    if (geo_idx1, point_idx1) == (geo_idx2, point_idx2):
        raise ValueError("Distance requires two different points")
    c_idx = sketch.addConstraint(Sketcher.Constraint(
        "Distance", geo_idx1, point_idx1, geo_idx2, point_idx2, value
    ))
    return {"constraint_index": c_idx, **_get_constraint_status(sketch)}


def add_constraint_length(sketch_name: str, geo_idx: int, value: float,
                          doc_name: str = None) -> dict:
    """Set the length of a line segment."""
    if _finite(value, "Line length") <= 0:
        raise ValueError("Line length must be positive")
    sketch = _get_sketch(sketch_name, doc_name)
    _require_type(sketch, geo_idx, _LINE, "Length", local=True)
    c_idx = sketch.addConstraint(Sketcher.Constraint("Distance", geo_idx, value))
    return {"constraint_index": c_idx, **_get_constraint_status(sketch)}


def add_constraint_distance_x(sketch_name: str, geo_idx: int, point_idx: int,
                              value: float, doc_name: str = None) -> dict:
    """Set signed horizontal distance from origin to a point."""
    value = _finite(value, "DistanceX value")
    sketch = _get_sketch(sketch_name, doc_name)
    _require_point(sketch, geo_idx, point_idx, local=True)
    c_idx = sketch.addConstraint(Sketcher.Constraint("DistanceX", geo_idx, point_idx, value))
    return {"constraint_index": c_idx, **_get_constraint_status(sketch)}


def add_constraint_distance_y(sketch_name: str, geo_idx: int, point_idx: int,
                              value: float, doc_name: str = None) -> dict:
    """Set signed vertical distance from origin to a point."""
    value = _finite(value, "DistanceY value")
    sketch = _get_sketch(sketch_name, doc_name)
    _require_point(sketch, geo_idx, point_idx, local=True)
    c_idx = sketch.addConstraint(Sketcher.Constraint("DistanceY", geo_idx, point_idx, value))
    return {"constraint_index": c_idx, **_get_constraint_status(sketch)}


def add_constraint_distance_x_between(sketch_name: str, geo_idx1: int, point_idx1: int,
                                      geo_idx2: int, point_idx2: int, value: float,
                                      doc_name: str = None) -> dict:
    """Set signed horizontal distance x2 - x1 between two geometry points."""
    value = _finite(value, "DistanceX value")
    sketch = _get_sketch(sketch_name, doc_name)
    _require_point(sketch, geo_idx1, point_idx1, "First point")
    _require_point(sketch, geo_idx2, point_idx2, "Second point")
    if (geo_idx1, point_idx1) == (geo_idx2, point_idx2):
        raise ValueError("DistanceX requires two different points")
    c_idx = sketch.addConstraint(Sketcher.Constraint(
        "DistanceX", geo_idx1, point_idx1, geo_idx2, point_idx2, value
    ))
    return {"constraint_index": c_idx, **_get_constraint_status(sketch)}


def add_constraint_distance_y_between(sketch_name: str, geo_idx1: int, point_idx1: int,
                                      geo_idx2: int, point_idx2: int, value: float,
                                      doc_name: str = None) -> dict:
    """Set signed vertical distance y2 - y1 between two geometry points."""
    value = _finite(value, "DistanceY value")
    sketch = _get_sketch(sketch_name, doc_name)
    _require_point(sketch, geo_idx1, point_idx1, "First point")
    _require_point(sketch, geo_idx2, point_idx2, "Second point")
    if (geo_idx1, point_idx1) == (geo_idx2, point_idx2):
        raise ValueError("DistanceY requires two different points")
    c_idx = sketch.addConstraint(Sketcher.Constraint(
        "DistanceY", geo_idx1, point_idx1, geo_idx2, point_idx2, value
    ))
    return {"constraint_index": c_idx, **_get_constraint_status(sketch)}


def add_constraint_angle(sketch_name: str, geo_idx1: int, geo_idx2: int,
                         angle: float, doc_name: str = None) -> dict:
    """Set angle between two lines (in degrees)."""
    angle = _finite(angle, "Angle")
    sketch = _get_sketch(sketch_name, doc_name)
    _require_type(sketch, geo_idx1, _LINE, "Angle", "First geometry")
    _require_type(sketch, geo_idx2, _LINE, "Angle", "Second geometry")
    if geo_idx1 == geo_idx2:
        raise ValueError("Angle requires two different lines")
    c_idx = sketch.addConstraint(Sketcher.Constraint(
        "Angle", geo_idx1, geo_idx2, math.radians(angle)
    ))
    return {"constraint_index": c_idx, **_get_constraint_status(sketch)}


def add_constraint_angle_to_axis(sketch_name: str, geo_idx: int, angle: float,
                                 doc_name: str = None) -> dict:
    """Set a line angle relative to the sketch-local positive X axis, in degrees."""
    angle = _finite(angle, "Angle")
    sketch = _get_sketch(sketch_name, doc_name)
    _require_type(sketch, geo_idx, _LINE, "Angle to axis", local=True)
    c_idx = sketch.addConstraint(Sketcher.Constraint("Angle", geo_idx, math.radians(angle)))
    return {"constraint_index": c_idx, **_get_constraint_status(sketch)}


def add_constraint_radius(sketch_name: str, geo_idx: int, radius: float,
                          doc_name: str = None) -> dict:
    """Set radius of a circle or arc."""
    radius = _finite(radius, "Radius", positive=True)
    sketch = _get_sketch(sketch_name, doc_name)
    _require_type(sketch, geo_idx, _CIRCULAR, "Radius", local=True)
    c_idx = sketch.addConstraint(Sketcher.Constraint("Radius", geo_idx, radius))
    return {"constraint_index": c_idx, **_get_constraint_status(sketch)}


def add_constraint_diameter(sketch_name: str, geo_idx: int, diameter: float,
                            doc_name: str = None) -> dict:
    """Set the diameter of a circle or arc."""
    if _finite(diameter, "Diameter") <= 0:
        raise ValueError("Diameter must be positive")
    sketch = _get_sketch(sketch_name, doc_name)
    _require_type(sketch, geo_idx, _CIRCULAR, "Diameter", local=True)
    c_idx = sketch.addConstraint(Sketcher.Constraint("Diameter", geo_idx, diameter))
    return {"constraint_index": c_idx, **_get_constraint_status(sketch)}


def add_constraint_point_on_object(sketch_name: str, geo_idx: int, point_idx: int,
                                   target_geo_idx: int, doc_name: str = None) -> dict:
    """Constrain a geometry point onto another curve or a sketch axis."""
    sketch = _get_sketch(sketch_name, doc_name)
    _require_point(sketch, geo_idx, point_idx)
    _require_type(sketch, target_geo_idx, _CURVES, "Point on object", "Target geometry")
    if geo_idx == target_geo_idx:
        raise ValueError("Point on object requires a target other than the point's own geometry")
    c_idx = sketch.addConstraint(Sketcher.Constraint(
        "PointOnObject", geo_idx, point_idx, target_geo_idx
    ))
    return {"constraint_index": c_idx, **_get_constraint_status(sketch)}


def _dimensional_constraint(sketch, constraint_idx: int, purpose: str):
    _require_index(constraint_idx, sketch.ConstraintCount, "Constraint")
    constraint = sketch.Constraints[constraint_idx]
    if constraint.Type not in _DIMENSIONAL:
        raise ValueError(f"{purpose} requires a dimensional constraint "
                         f"({', '.join(sorted(_DIMENSIONAL))}); constraint {constraint_idx} is {constraint.Type}")
    return constraint


def set_constraint_value(sketch_name: str, constraint_idx: int, value: float,
                         doc_name: str = None) -> dict:
    """Change a driving dimensional constraint value; angles are supplied in degrees."""
    sketch = _get_sketch(sketch_name, doc_name)
    constraint = _dimensional_constraint(sketch, constraint_idx, "Setting a value")
    if not sketch.getDriving(constraint_idx):
        raise ValueError(f"Constraint {constraint_idx} is a reference (non-driving) dimension; "
                         "make it driving before setting its value")
    value = _finite(value, f"{constraint.Type} value",
                    positive=constraint.Type in {"Distance", "Radius", "Diameter"})
    unit = "deg" if constraint.Type.startswith("Angle") else "mm"
    sketch.setDatum(constraint_idx, FreeCAD.Units.Quantity(f"{value} {unit}"))
    return {"constraint_index": constraint_idx, "value": value, "unit": unit,
            **_get_constraint_status(sketch)}


def set_constraint_mode(sketch_name: str, constraint_idx: int,
                        driving: bool = None, active: bool = None,
                        doc_name: str = None) -> dict:
    """Set driving/reference (dimensional constraints only) and active/inactive state for a constraint."""
    if driving is None and active is None:
        raise ValueError("At least one of driving or active must be provided")
    sketch = _get_sketch(sketch_name, doc_name)
    _require_index(constraint_idx, sketch.ConstraintCount, "Constraint")
    if driving is not None:
        _dimensional_constraint(sketch, constraint_idx, "Driving/reference mode")
        sketch.setDriving(constraint_idx, driving)
    if active is not None:
        sketch.setActive(constraint_idx, active)
    return {"constraint_index": constraint_idx,
            "driving": bool(sketch.getDriving(constraint_idx)),
            "active": bool(sketch.getActive(constraint_idx)),
            **_get_constraint_status(sketch)}


def delete_constraint(sketch_name: str, constraint_idx: int, doc_name: str = None) -> dict:
    """Delete one constraint from a sketch."""
    sketch = _get_sketch(sketch_name, doc_name)
    _require_index(constraint_idx, sketch.ConstraintCount, "Constraint")
    sketch.delConstraint(constraint_idx)
    return {"deleted_constraint_index": constraint_idx, **_get_constraint_status(sketch)}


def _geometry_info(geo) -> dict:
    info = {"type": type(geo).__name__}
    if hasattr(geo, "StartPoint"):
        info["start"] = {"x": geo.StartPoint.x, "y": geo.StartPoint.y}
    if hasattr(geo, "EndPoint"):
        info["end"] = {"x": geo.EndPoint.x, "y": geo.EndPoint.y}
    if hasattr(geo, "Center"):
        info["center"] = {"x": geo.Center.x, "y": geo.Center.y}
    if hasattr(geo, "Radius"):
        info["radius"] = geo.Radius
    if isinstance(geo, Part.Point):
        info["point"] = {"x": geo.X, "y": geo.Y}
    if isinstance(geo, (Part.ArcOfCircle, Part.ArcOfEllipse)):
        info["parameter_range"] = [geo.FirstParameter, geo.LastParameter]
    if isinstance(geo, (Part.Ellipse, Part.ArcOfEllipse)):
        ellipse = geo if isinstance(geo, Part.Ellipse) else geo.Ellipse
        info["major_radius"], info["minor_radius"] = ellipse.MajorRadius, ellipse.MinorRadius
        info["major_axis"] = [ellipse.XAxis.x, ellipse.XAxis.y]
    if isinstance(geo, Part.BSplineCurve):
        info["degree"] = geo.Degree
        info["poles"] = [[pole.x, pole.y] for pole in geo.getPoles()]
        info["periodic"] = bool(geo.isPeriodic())
    return info


def get_sketch_info(sketch_name: str, doc_name: str = None) -> dict:
    """Get detailed information about a sketch."""
    sketch = _get_sketch(sketch_name, doc_name)
    status = _get_constraint_status(sketch, raise_on_failure=False)

    geometries = []
    for i in range(sketch.GeometryCount):
        geo_info = {"index": i, **_geometry_info(sketch.Geometry[i]),
                    "construction": bool(sketch.getConstruction(i)), "external": i < 0}
        geometries.append(geo_info)

    external = [{"index": -3 - i, "external_index": i, **_geometry_info(geo)}
                for i, geo in enumerate(list(sketch.ExternalGeo)[2:])]

    constraints = []
    for i in range(sketch.ConstraintCount):
        c = sketch.Constraints[i]
        constraints.append({
            "index": i,
            "type": c.Type,
            "first": c.First,
            "first_pos": c.FirstPos,
            "second": c.Second,
            "second_pos": c.SecondPos,
            "value": c.Value,
            "driving": _constraint_mode(sketch, i, "getDriving"),
            "active": _constraint_mode(sketch, i, "getActive"),
            "virtual": bool(c.InVirtualSpace),
        })

    support = [{"document": obj.Document.Name, "object": obj.Name,
                "subelements": [name for name in subelements if name]}
               for obj, subelements in sketch.AttachmentSupport]
    offset = sketch.AttachmentOffset

    return {
        "name": sketch.Name,
        "geometries": geometries,
        "external_geometries": external,
        "constraints": constraints,
        "attachment": {
            "support": support,
            "map_mode": sketch.MapMode,
            "offset": {"position": [offset.Base.x, offset.Base.y, offset.Base.z],
                       "rotation_xyzw": list(offset.Rotation.Q)},
            "placement": {"position": list(sketch.Placement.Base),
                          "rotation_xyzw": list(sketch.Placement.Rotation.Q)},
        },
        **status,
    }
