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


def _get_constraint_status(sketch) -> dict:
    """Get the constraint status of a sketch."""
    dof = sketch.solve()
    return {
        "degrees_of_freedom": dof,
        "fully_constrained": dof == 0,
        "geometry_count": sketch.GeometryCount,
        "constraint_count": sketch.ConstraintCount,
    }


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

    sketch = doc.addObject("Sketcher::SketchObject", name)

    # Set plane
    plane_map = {
        "XY": FreeCAD.Placement(
            Vector(0, 0, offset),
            FreeCAD.Rotation(Vector(0, 0, 1), 0)
        ),
        "XZ": FreeCAD.Placement(
            Vector(0, 0, 0),
            FreeCAD.Rotation(Vector(1, 0, 0), -90)
        ),
        "YZ": FreeCAD.Placement(
            Vector(0, 0, 0),
            FreeCAD.Rotation(Vector(0, 1, 0), 90)
        ),
    }

    if plane.upper() in plane_map:
        sketch.Placement = plane_map[plane.upper()]
    else:
        raise ValueError(f"Unknown plane '{plane}'. Use 'XY', 'XZ', or 'YZ'.")

    # Attach to body if specified
    if body_name:
        body = doc.getObject(body_name)
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

    return {"geometry_indices": [idx0, idx1, idx2, idx3], **_get_constraint_status(sketch)}


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
                             sym_geo: int, sym_point: int,
                             doc_name: str = None) -> dict:
    """Add a symmetric constraint (two points symmetric about a line/point)."""
    sketch = _get_sketch(sketch_name, doc_name)
    c_idx = sketch.addConstraint(Sketcher.Constraint(
        "Symmetric", geo_idx1, point_idx1, geo_idx2, point_idx2, sym_geo, sym_point
    ))
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
    c_idx = sketch.addConstraint(Sketcher.Constraint("Lock", geo_idx, point_idx))
    return {"constraint_index": c_idx, **_get_constraint_status(sketch)}


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


def add_constraint_angle(sketch_name: str, geo_idx1: int, geo_idx2: int,
                         angle: float, doc_name: str = None) -> dict:
    """Set angle between two lines (in degrees)."""
    import math
    sketch = _get_sketch(sketch_name, doc_name)
    c_idx = sketch.addConstraint(Sketcher.Constraint(
        "Angle", geo_idx1, geo_idx2, math.radians(angle)
    ))
    return {"constraint_index": c_idx, **_get_constraint_status(sketch)}


def add_constraint_radius(sketch_name: str, geo_idx: int, radius: float,
                          doc_name: str = None) -> dict:
    """Set radius of a circle or arc."""
    sketch = _get_sketch(sketch_name, doc_name)
    c_idx = sketch.addConstraint(Sketcher.Constraint("Radius", geo_idx, radius))
    return {"constraint_index": c_idx, **_get_constraint_status(sketch)}


def get_sketch_info(sketch_name: str, doc_name: str = None) -> dict:
    """Get detailed information about a sketch."""
    sketch = _get_sketch(sketch_name, doc_name)

    geometries = []
    for i in range(sketch.GeometryCount):
        geo = sketch.Geometry[i]
        geo_info = {"index": i, "type": type(geo).__name__}

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
            "value": c.Value if c.Value != 0 else None,
        })

    return {
        "name": sketch.Name,
        "geometries": geometries,
        "constraints": constraints,
        **_get_constraint_status(sketch),
    }
