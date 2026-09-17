"""Sketcher operations running inside FreeCAD.

Provides geometry creation and constraint management for Sketcher objects.
"""

import FreeCAD
import FreeCADGui
import Part
import Sketcher
from FreeCAD import Vector


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
    conflicting = list(sketch.ConflictingConstraints)
    redundant = list(sketch.RedundantConstraints)
    partially_redundant = list(sketch.PartiallyRedundantConstraints)
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
    sketch = _get_sketch(sketch_name, doc_name)
    idx = sketch.addGeometry(
        Part.LineSegment(Vector(x1, y1, 0), Vector(x2, y2, 0)),
        construction
    )
    return {"geometry_index": idx, **_get_constraint_status(sketch)}


def add_rectangle(sketch_name: str, x1: float, y1: float, x2: float, y2: float,
                  construction: bool = False, doc_name: str = None) -> dict:
    """Add a rectangle (4 lines + constraints) to a sketch."""
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
    sketch = _get_sketch(sketch_name, doc_name)
    idx = sketch.addGeometry(
        Part.Circle(Vector(cx, cy, 0), Vector(0, 0, 1), radius),
        construction
    )
    return {"geometry_index": idx, **_get_constraint_status(sketch)}


def add_arc(sketch_name: str, cx: float, cy: float, radius: float,
            start_angle: float, end_angle: float,
            construction: bool = False, doc_name: str = None) -> dict:
    """Add an arc (portion of circle) to a sketch.

    Angles in radians.
    """
    import math
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
    """Add an ellipse to a sketch."""
    import math
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
    """Add a B-spline through control points.

    Args:
        points: List of [x, y] coordinate pairs
    """
    sketch = _get_sketch(sketch_name, doc_name)
    vectors = [Vector(p[0], p[1], 0) for p in points]
    bspline = Part.BSplineCurve()
    bspline.interpolate(vectors)
    idx = sketch.addGeometry(bspline, construction)
    return {"geometry_index": idx, **_get_constraint_status(sketch)}


def add_point(sketch_name: str, x: float, y: float,
              construction: bool = False, doc_name: str = None) -> dict:
    """Add a point to a sketch."""
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
    import math
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
    _require_index(geo_idx, sketch.GeometryCount, "Geometry")
    sketch.getPoint(geo_idx, point_idx)
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


def add_external_geometry(sketch_name: str, selection: dict,
                          defining: bool = False, intersection: bool = False,
                          doc_name: str = None) -> dict:
    """Project one revision-checked external edge into a sketch."""
    from freecad_ai_bridge.geometry_ops import _resolve

    sketch = _get_sketch(sketch_name, doc_name)
    doc, obj, _element, kind = _resolve(selection)
    if doc is not sketch.Document or kind != "edge" or obj is sketch:
        raise ValueError("External geometry must be an edge from another object in the sketch document")
    external_index = len(sketch.ExternalGeometry)
    sketch.addExternal(obj.Name, selection["subelement"], defining, intersection)
    return {"external_index": external_index, "geometry_index": -3 - external_index,
            "source": selection, **_get_constraint_status(sketch)}


def delete_external_geometry(sketch_name: str, external_idx: int,
                             doc_name: str = None) -> dict:
    """Remove an external geometry link by its zero-based external-list index."""
    sketch = _get_sketch(sketch_name, doc_name)
    _require_index(external_idx, len(sketch.ExternalGeometry), "External geometry")
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
        map_mode = "ObjectXY"
    if support is None:
        sketch.AttachmentSupport = []
    else:
        sketch.AttachmentSupport = [(support, subelements)]
    sketch.MapMode = map_mode
    sketch.AttachmentOffset = FreeCAD.Placement(
        Vector(offset_x, offset_y, offset_z),
        FreeCAD.Rotation(rotation_z, rotation_y, rotation_x),
    )
    return {"support": None if support is None else {"document": sketch.Document.Name,
                                                       "object": support.Name,
                                                       "subelements": subelements},
            "map_mode": sketch.MapMode, **_get_constraint_status(sketch)}


def trim_geometry(sketch_name: str, geo_idx: int, x: float, y: float,
                  include_axes: bool = False, doc_name: str = None) -> dict:
    """Trim a line or circular arc at a sketch-local reference point."""
    if include_axes:
        raise ValueError("FreeCAD 1.1 does not support trimming against sketch axes")
    sketch = _get_sketch(sketch_name, doc_name)
    _require_index(geo_idx, sketch.GeometryCount, "Geometry")
    before = sketch.GeometryCount
    sketch.trim(geo_idx, Vector(x, y, 0))
    return {"source_geometry_index": geo_idx, "geometry_count_before": before,
            **_get_constraint_status(sketch)}


def extend_geometry(sketch_name: str, geo_idx: int, increment: float, point_idx: int,
                    doc_name: str = None) -> dict:
    """Extend a line or circular arc endpoint by a signed increment in mm."""
    if increment == 0:
        raise ValueError("Extension increment must be nonzero")
    sketch = _get_sketch(sketch_name, doc_name)
    _require_index(geo_idx, sketch.GeometryCount, "Geometry")
    if point_idx not in {1, 2}:
        raise ValueError("Extension point_idx must be 1 (start) or 2 (end)")
    sketch.extend(geo_idx, increment, point_idx)
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
    _require_index(geo_idx1, sketch.GeometryCount, "Geometry")
    _require_index(geo_idx2, sketch.GeometryCount, "Geometry")
    before = sketch.GeometryCount
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
    if reference_geo_idx >= 0:
        _require_index(reference_geo_idx, sketch.GeometryCount, "Reference geometry")
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
    c_idx = sketch.addConstraint(Sketcher.Constraint("Coincident", geo_idx1, point_idx1, geo_idx2, point_idx2))
    return {"constraint_index": c_idx, **_get_constraint_status(sketch)}


def add_constraint_tangent(sketch_name: str, geo_idx1: int, geo_idx2: int,
                           point_idx1: int = None, point_idx2: int = None,
                           doc_name: str = None) -> dict:
    """Add a tangent constraint between two geometries."""
    sketch = _get_sketch(sketch_name, doc_name)
    if point_idx1 is not None and point_idx2 is not None:
        c_idx = sketch.addConstraint(Sketcher.Constraint("Tangent", geo_idx1, point_idx1, geo_idx2, point_idx2))
    else:
        c_idx = sketch.addConstraint(Sketcher.Constraint("Tangent", geo_idx1, geo_idx2))
    return {"constraint_index": c_idx, **_get_constraint_status(sketch)}


def add_constraint_perpendicular(sketch_name: str, geo_idx1: int, geo_idx2: int,
                                 doc_name: str = None) -> dict:
    """Add a perpendicular constraint between two lines."""
    sketch = _get_sketch(sketch_name, doc_name)
    c_idx = sketch.addConstraint(Sketcher.Constraint("Perpendicular", geo_idx1, geo_idx2))
    return {"constraint_index": c_idx, **_get_constraint_status(sketch)}


def add_constraint_parallel(sketch_name: str, geo_idx1: int, geo_idx2: int,
                            doc_name: str = None) -> dict:
    """Add a parallel constraint between two lines."""
    sketch = _get_sketch(sketch_name, doc_name)
    c_idx = sketch.addConstraint(Sketcher.Constraint("Parallel", geo_idx1, geo_idx2))
    return {"constraint_index": c_idx, **_get_constraint_status(sketch)}


def add_constraint_equal(sketch_name: str, geo_idx1: int, geo_idx2: int,
                         doc_name: str = None) -> dict:
    """Add an equal constraint (same length for lines, same radius for circles)."""
    sketch = _get_sketch(sketch_name, doc_name)
    c_idx = sketch.addConstraint(Sketcher.Constraint("Equal", geo_idx1, geo_idx2))
    return {"constraint_index": c_idx, **_get_constraint_status(sketch)}


def add_constraint_symmetric(sketch_name: str, geo_idx1: int, point_idx1: int,
                             geo_idx2: int, point_idx2: int,
                             sym_geo: int, sym_point: int = None,
                             doc_name: str = None) -> dict:
    """Add a symmetric constraint (two points symmetric about a line/point)."""
    sketch = _get_sketch(sketch_name, doc_name)
    args = ["Symmetric", geo_idx1, point_idx1, geo_idx2, point_idx2, sym_geo]
    if sym_point is not None:
        args.append(sym_point)
    c_idx = sketch.addConstraint(Sketcher.Constraint(*args))
    return {"constraint_index": c_idx, **_get_constraint_status(sketch)}


def add_constraint_horizontal(sketch_name: str, geo_idx: int, doc_name: str = None) -> dict:
    """Add a horizontal constraint to a line."""
    sketch = _get_sketch(sketch_name, doc_name)
    c_idx = sketch.addConstraint(Sketcher.Constraint("Horizontal", geo_idx))
    return {"constraint_index": c_idx, **_get_constraint_status(sketch)}


def add_constraint_vertical(sketch_name: str, geo_idx: int, doc_name: str = None) -> dict:
    """Add a vertical constraint to a line."""
    sketch = _get_sketch(sketch_name, doc_name)
    c_idx = sketch.addConstraint(Sketcher.Constraint("Vertical", geo_idx))
    return {"constraint_index": c_idx, **_get_constraint_status(sketch)}


def add_constraint_lock(sketch_name: str, geo_idx: int, point_idx: int,
                        doc_name: str = None) -> dict:
    """Lock a point at its current position (adds DistanceX + DistanceY from origin)."""
    sketch = _get_sketch(sketch_name, doc_name)
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
    """Block a geometry element (prevent any movement)."""
    sketch = _get_sketch(sketch_name, doc_name)
    c_idx = sketch.addConstraint(Sketcher.Constraint("Block", geo_idx))
    return {"constraint_index": c_idx, **_get_constraint_status(sketch)}


def add_constraint_distance(sketch_name: str, geo_idx1: int, point_idx1: int,
                            geo_idx2: int, point_idx2: int, value: float,
                            doc_name: str = None) -> dict:
    """Set distance between two points."""
    sketch = _get_sketch(sketch_name, doc_name)
    c_idx = sketch.addConstraint(Sketcher.Constraint(
        "Distance", geo_idx1, point_idx1, geo_idx2, point_idx2, value
    ))
    return {"constraint_index": c_idx, **_get_constraint_status(sketch)}


def add_constraint_length(sketch_name: str, geo_idx: int, value: float,
                          doc_name: str = None) -> dict:
    """Set the length of a line segment."""
    if value <= 0:
        raise ValueError("Line length must be positive")
    sketch = _get_sketch(sketch_name, doc_name)
    c_idx = sketch.addConstraint(Sketcher.Constraint("Distance", geo_idx, value))
    return {"constraint_index": c_idx, **_get_constraint_status(sketch)}


def add_constraint_distance_x(sketch_name: str, geo_idx: int, point_idx: int,
                              value: float, doc_name: str = None) -> dict:
    """Set horizontal distance from origin to a point."""
    sketch = _get_sketch(sketch_name, doc_name)
    c_idx = sketch.addConstraint(Sketcher.Constraint("DistanceX", geo_idx, point_idx, value))
    return {"constraint_index": c_idx, **_get_constraint_status(sketch)}


def add_constraint_distance_y(sketch_name: str, geo_idx: int, point_idx: int,
                              value: float, doc_name: str = None) -> dict:
    """Set vertical distance from origin to a point."""
    sketch = _get_sketch(sketch_name, doc_name)
    c_idx = sketch.addConstraint(Sketcher.Constraint("DistanceY", geo_idx, point_idx, value))
    return {"constraint_index": c_idx, **_get_constraint_status(sketch)}


def add_constraint_distance_x_between(sketch_name: str, geo_idx1: int, point_idx1: int,
                                      geo_idx2: int, point_idx2: int, value: float,
                                      doc_name: str = None) -> dict:
    """Set signed horizontal distance between two geometry points."""
    sketch = _get_sketch(sketch_name, doc_name)
    c_idx = sketch.addConstraint(Sketcher.Constraint(
        "DistanceX", geo_idx1, point_idx1, geo_idx2, point_idx2, value
    ))
    return {"constraint_index": c_idx, **_get_constraint_status(sketch)}


def add_constraint_distance_y_between(sketch_name: str, geo_idx1: int, point_idx1: int,
                                      geo_idx2: int, point_idx2: int, value: float,
                                      doc_name: str = None) -> dict:
    """Set signed vertical distance between two geometry points."""
    sketch = _get_sketch(sketch_name, doc_name)
    c_idx = sketch.addConstraint(Sketcher.Constraint(
        "DistanceY", geo_idx1, point_idx1, geo_idx2, point_idx2, value
    ))
    return {"constraint_index": c_idx, **_get_constraint_status(sketch)}


def add_constraint_angle(sketch_name: str, geo_idx1: int, geo_idx2: int,
                         angle: float, doc_name: str = None) -> dict:
    """Set angle between two lines (in degrees)."""
    import math
    sketch = _get_sketch(sketch_name, doc_name)
    c_idx = sketch.addConstraint(Sketcher.Constraint(
        "Angle", geo_idx1, geo_idx2, math.radians(angle)
    ))
    return {"constraint_index": c_idx, **_get_constraint_status(sketch)}


def add_constraint_angle_to_axis(sketch_name: str, geo_idx: int, angle: float,
                                 doc_name: str = None) -> dict:
    """Set a line angle relative to the sketch-local positive X axis, in degrees."""
    import math
    sketch = _get_sketch(sketch_name, doc_name)
    c_idx = sketch.addConstraint(Sketcher.Constraint("Angle", geo_idx, math.radians(angle)))
    return {"constraint_index": c_idx, **_get_constraint_status(sketch)}


def add_constraint_radius(sketch_name: str, geo_idx: int, radius: float,
                          doc_name: str = None) -> dict:
    """Set radius of a circle or arc."""
    sketch = _get_sketch(sketch_name, doc_name)
    c_idx = sketch.addConstraint(Sketcher.Constraint("Radius", geo_idx, radius))
    return {"constraint_index": c_idx, **_get_constraint_status(sketch)}


def add_constraint_diameter(sketch_name: str, geo_idx: int, diameter: float,
                            doc_name: str = None) -> dict:
    """Set the diameter of a circle or arc."""
    if diameter <= 0:
        raise ValueError("Diameter must be positive")
    sketch = _get_sketch(sketch_name, doc_name)
    c_idx = sketch.addConstraint(Sketcher.Constraint("Diameter", geo_idx, diameter))
    return {"constraint_index": c_idx, **_get_constraint_status(sketch)}


def add_constraint_point_on_object(sketch_name: str, geo_idx: int, point_idx: int,
                                   target_geo_idx: int, doc_name: str = None) -> dict:
    """Constrain a geometry point onto another curve or a sketch axis."""
    sketch = _get_sketch(sketch_name, doc_name)
    c_idx = sketch.addConstraint(Sketcher.Constraint(
        "PointOnObject", geo_idx, point_idx, target_geo_idx
    ))
    return {"constraint_index": c_idx, **_get_constraint_status(sketch)}


def set_constraint_value(sketch_name: str, constraint_idx: int, value: float,
                         doc_name: str = None) -> dict:
    """Change a dimensional constraint value; angles are supplied in degrees."""
    sketch = _get_sketch(sketch_name, doc_name)
    _require_index(constraint_idx, sketch.ConstraintCount, "Constraint")
    constraint = sketch.Constraints[constraint_idx]
    unit = "deg" if constraint.Type.startswith("Angle") else "mm"
    sketch.setDatum(constraint_idx, FreeCAD.Units.Quantity(f"{value} {unit}"))
    return {"constraint_index": constraint_idx, "value": value, "unit": unit,
            **_get_constraint_status(sketch)}


def set_constraint_mode(sketch_name: str, constraint_idx: int,
                        driving: bool = None, active: bool = None,
                        doc_name: str = None) -> dict:
    """Set driving/reference and active/inactive state for a constraint."""
    if driving is None and active is None:
        raise ValueError("At least one of driving or active must be provided")
    sketch = _get_sketch(sketch_name, doc_name)
    _require_index(constraint_idx, sketch.ConstraintCount, "Constraint")
    if driving is not None:
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


def get_sketch_info(sketch_name: str, doc_name: str = None) -> dict:
    """Get detailed information about a sketch."""
    sketch = _get_sketch(sketch_name, doc_name)

    geometries = []
    for i in range(sketch.GeometryCount):
        geo = sketch.Geometry[i]
        geo_info = {"index": i, "type": type(geo).__name__,
                    "construction": bool(sketch.getConstruction(i)), "external": i < 0}

        if hasattr(geo, "StartPoint"):
            geo_info["start"] = {"x": geo.StartPoint.x, "y": geo.StartPoint.y}
        if hasattr(geo, "EndPoint"):
            geo_info["end"] = {"x": geo.EndPoint.x, "y": geo.EndPoint.y}
        if hasattr(geo, "Center"):
            geo_info["center"] = {"x": geo.Center.x, "y": geo.Center.y}
        if hasattr(geo, "Radius"):
            geo_info["radius"] = geo.Radius

        geometries.append(geo_info)

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

    support = [{"document": obj.Document.Name, "object": obj.Name, "subelements": list(subelements)}
               for obj, subelements in sketch.AttachmentSupport]
    offset = sketch.AttachmentOffset

    return {
        "name": sketch.Name,
        "geometries": geometries,
        "constraints": constraints,
        "attachment": {
            "support": support,
            "map_mode": sketch.MapMode,
            "offset": {"position": [offset.Base.x, offset.Base.y, offset.Base.z],
                       "rotation_xyzw": list(offset.Rotation.Q)},
        },
        **_get_constraint_status(sketch, raise_on_failure=False),
    }
