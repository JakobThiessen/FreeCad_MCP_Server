"""FreeCAD MCP Server - Main entry point.

Exposes FreeCAD functionality as MCP tools for Claude and other AI assistants.
Uses FastMCP with stdio transport.
"""

import json
from typing import Any

from mcp.server.fastmcp import FastMCP

from freecad_mcp.connection import FreeCADConnection

# Initialize MCP server
mcp = FastMCP("FreeCAD AI Server")

# Global connection instance
_conn = FreeCADConnection()


def _call(module: str, function: str, **kwargs) -> Any:
    """Helper to call a function in FreeCAD via RPC."""
    # Remove None values to use defaults on the FreeCAD side
    kwargs = {k: v for k, v in kwargs.items() if v is not None}
    return _conn.call_function(module, function, **kwargs)


# =============================================================================
# Connection & Document Tools
# =============================================================================


@mcp.tool()
def connect(host: str = "127.0.0.1", port: int = 9875) -> str:
    """Connect to a running FreeCAD instance with the AI Bridge addon.

    Must be called before using any other tools. FreeCAD must be running
    with the FreecadAIBridge addon loaded.
    """
    global _conn
    _conn = FreeCADConnection(host=host, port=port)
    if _conn.connect():
        version = _conn.get_version()
        return f"Connected to FreeCAD {version} at {host}:{port}"
    else:
        return f"Failed to connect to FreeCAD at {host}:{port}. Is FreeCAD running with the AI Bridge addon?"


@mcp.tool()
def get_status() -> str:
    """Check connection status and get document state."""
    if not _conn.is_connected:
        return "Not connected to FreeCAD. Use 'connect' tool first."
    state = _conn.get_document_state()
    return json.dumps(state, indent=2)


@mcp.tool()
def create_document(name: str = "Unnamed") -> str:
    """Create a new FreeCAD document."""
    result = _call("freecad_ai_bridge.operations", "create_document", name=name)
    return json.dumps(result)


@mcp.tool()
def open_document(path: str) -> str:
    """Open a FreeCAD document from file."""
    result = _call("freecad_ai_bridge.operations", "open_document", path=path)
    return json.dumps(result)


@mcp.tool()
def save_document(name: str = None, path: str = None) -> str:
    """Save the current document. Optionally specify path for 'Save As'."""
    result = _call("freecad_ai_bridge.operations", "save_document", name=name, path=path)
    return json.dumps(result)


@mcp.tool()
def close_document(name: str) -> str:
    """Close a document by name."""
    result = _call("freecad_ai_bridge.operations", "close_document", name=name)
    return json.dumps(result)


@mcp.tool()
def list_objects(doc_name: str = None) -> str:
    """List all objects in the active (or specified) document with their types and properties."""
    result = _call("freecad_ai_bridge.operations", "list_objects", doc_name=doc_name)
    return json.dumps(result, indent=2)


@mcp.tool()
def inspect_object(obj_name: str, doc_name: str = None) -> str:
    """Get detailed information about a specific object (properties, shape info, etc.)."""
    result = _call("freecad_ai_bridge.operations", "inspect_object", obj_name=obj_name, doc_name=doc_name)
    return json.dumps(result, indent=2)


@mcp.tool()
def delete_object(obj_name: str, doc_name: str = None) -> str:
    """Delete an object from the document."""
    result = _call("freecad_ai_bridge.operations", "delete_object", obj_name=obj_name, doc_name=doc_name)
    return json.dumps(result)


# =============================================================================
# Sketcher - Geometry Tools
# =============================================================================


@mcp.tool()
def create_sketch(name: str = "Sketch", plane: str = "XY", offset: float = 0.0,
                  body_name: str = None, doc_name: str = None) -> str:
    """Create a new sketch on a plane (XY, XZ, or YZ).

    If body_name is specified, attaches the sketch to that PartDesign Body.
    Returns the sketch name and constraint status.
    """
    result = _call("freecad_ai_bridge.sketcher_ops", "create_sketch",
                   name=name, plane=plane, offset=offset, body_name=body_name, doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def sketch_add_line(sketch_name: str, x1: float, y1: float, x2: float, y2: float,
                    construction: bool = False, doc_name: str = None) -> str:
    """Add a line segment to a sketch. Returns geometry index."""
    result = _call("freecad_ai_bridge.sketcher_ops", "add_line",
                   sketch_name=sketch_name, x1=x1, y1=y1, x2=x2, y2=y2,
                   construction=construction, doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def sketch_add_rectangle(sketch_name: str, x1: float, y1: float, x2: float, y2: float,
                         construction: bool = False, doc_name: str = None) -> str:
    """Add a rectangle to a sketch (4 lines with coincident + H/V constraints).

    (x1,y1) is bottom-left, (x2,y2) is top-right corner.
    Returns geometry indices of the 4 lines.
    """
    result = _call("freecad_ai_bridge.sketcher_ops", "add_rectangle",
                   sketch_name=sketch_name, x1=x1, y1=y1, x2=x2, y2=y2,
                   construction=construction, doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def sketch_add_circle(sketch_name: str, cx: float, cy: float, radius: float,
                      construction: bool = False, doc_name: str = None) -> str:
    """Add a circle to a sketch. Returns geometry index."""
    result = _call("freecad_ai_bridge.sketcher_ops", "add_circle",
                   sketch_name=sketch_name, cx=cx, cy=cy, radius=radius,
                   construction=construction, doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def sketch_add_arc(sketch_name: str, cx: float, cy: float, radius: float,
                   start_angle: float, end_angle: float,
                   construction: bool = False, doc_name: str = None) -> str:
    """Add an arc (portion of circle) to a sketch. Angles in radians."""
    result = _call("freecad_ai_bridge.sketcher_ops", "add_arc",
                   sketch_name=sketch_name, cx=cx, cy=cy, radius=radius,
                   start_angle=start_angle, end_angle=end_angle,
                   construction=construction, doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def sketch_add_ellipse(sketch_name: str, cx: float, cy: float,
                       major_radius: float, minor_radius: float,
                       angle: float = 0.0, construction: bool = False,
                       doc_name: str = None) -> str:
    """Add an ellipse to a sketch."""
    result = _call("freecad_ai_bridge.sketcher_ops", "add_ellipse",
                   sketch_name=sketch_name, cx=cx, cy=cy,
                   major_radius=major_radius, minor_radius=minor_radius,
                   angle=angle, construction=construction, doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def sketch_add_bspline(sketch_name: str, points: list,
                       construction: bool = False, doc_name: str = None) -> str:
    """Add a B-spline curve through control points.

    Args:
        points: List of [x, y] coordinate pairs, e.g. [[0,0], [5,10], [10,0]]
    """
    result = _call("freecad_ai_bridge.sketcher_ops", "add_bspline",
                   sketch_name=sketch_name, points=points,
                   construction=construction, doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def sketch_add_point(sketch_name: str, x: float, y: float,
                     construction: bool = False, doc_name: str = None) -> str:
    """Add a point to a sketch."""
    result = _call("freecad_ai_bridge.sketcher_ops", "add_point",
                   sketch_name=sketch_name, x=x, y=y,
                   construction=construction, doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def sketch_add_polygon(sketch_name: str, points: list, close: bool = True,
                       construction: bool = False, doc_name: str = None) -> str:
    """Add a polygon (connected lines) to a sketch.

    Args:
        points: List of [x, y] coordinate pairs
        close: If True, connect last point back to first
    """
    result = _call("freecad_ai_bridge.sketcher_ops", "add_polygon",
                   sketch_name=sketch_name, points=points, close=close,
                   construction=construction, doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def sketch_add_slot(sketch_name: str, x1: float, y1: float, x2: float, y2: float,
                    radius: float, construction: bool = False, doc_name: str = None) -> str:
    """Add a slot (two parallel lines connected by semicircles) to a sketch."""
    result = _call("freecad_ai_bridge.sketcher_ops", "add_slot",
                   sketch_name=sketch_name, x1=x1, y1=y1, x2=x2, y2=y2,
                   radius=radius, construction=construction, doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def sketch_info(sketch_name: str, doc_name: str = None) -> str:
    """Get detailed sketch info: all geometries, constraints, and constraint status."""
    result = _call("freecad_ai_bridge.sketcher_ops", "get_sketch_info",
                   sketch_name=sketch_name, doc_name=doc_name)
    return json.dumps(result, indent=2)


# =============================================================================
# Sketcher - Constraint Tools
# =============================================================================


@mcp.tool()
def sketch_constrain_coincident(sketch_name: str, geo_idx1: int, point_idx1: int,
                                geo_idx2: int, point_idx2: int,
                                doc_name: str = None) -> str:
    """Make two points coincident (same location).

    Point indices: 1=start, 2=end, 3=center (circles/arcs).
    Use -1 for external geometry, -2 for origin.
    """
    result = _call("freecad_ai_bridge.sketcher_ops", "add_constraint_coincident",
                   sketch_name=sketch_name, geo_idx1=geo_idx1, point_idx1=point_idx1,
                   geo_idx2=geo_idx2, point_idx2=point_idx2, doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def sketch_constrain_tangent(sketch_name: str, geo_idx1: int, geo_idx2: int,
                             point_idx1: int = None, point_idx2: int = None,
                             doc_name: str = None) -> str:
    """Make two geometries tangent to each other."""
    result = _call("freecad_ai_bridge.sketcher_ops", "add_constraint_tangent",
                   sketch_name=sketch_name, geo_idx1=geo_idx1, geo_idx2=geo_idx2,
                   point_idx1=point_idx1, point_idx2=point_idx2, doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def sketch_constrain_perpendicular(sketch_name: str, geo_idx1: int, geo_idx2: int,
                                   doc_name: str = None) -> str:
    """Make two lines perpendicular."""
    result = _call("freecad_ai_bridge.sketcher_ops", "add_constraint_perpendicular",
                   sketch_name=sketch_name, geo_idx1=geo_idx1, geo_idx2=geo_idx2, doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def sketch_constrain_parallel(sketch_name: str, geo_idx1: int, geo_idx2: int,
                              doc_name: str = None) -> str:
    """Make two lines parallel."""
    result = _call("freecad_ai_bridge.sketcher_ops", "add_constraint_parallel",
                   sketch_name=sketch_name, geo_idx1=geo_idx1, geo_idx2=geo_idx2, doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def sketch_constrain_equal(sketch_name: str, geo_idx1: int, geo_idx2: int,
                           doc_name: str = None) -> str:
    """Make two elements equal (same length for lines, same radius for circles)."""
    result = _call("freecad_ai_bridge.sketcher_ops", "add_constraint_equal",
                   sketch_name=sketch_name, geo_idx1=geo_idx1, geo_idx2=geo_idx2, doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def sketch_constrain_symmetric(sketch_name: str,
                               geo_idx1: int, point_idx1: int,
                               geo_idx2: int, point_idx2: int,
                               sym_geo: int, sym_point: int,
                               doc_name: str = None) -> str:
    """Make two points symmetric about a line or point."""
    result = _call("freecad_ai_bridge.sketcher_ops", "add_constraint_symmetric",
                   sketch_name=sketch_name,
                   geo_idx1=geo_idx1, point_idx1=point_idx1,
                   geo_idx2=geo_idx2, point_idx2=point_idx2,
                   sym_geo=sym_geo, sym_point=sym_point, doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def sketch_constrain_horizontal(sketch_name: str, geo_idx: int,
                                doc_name: str = None) -> str:
    """Constrain a line to be horizontal."""
    result = _call("freecad_ai_bridge.sketcher_ops", "add_constraint_horizontal",
                   sketch_name=sketch_name, geo_idx=geo_idx, doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def sketch_constrain_vertical(sketch_name: str, geo_idx: int,
                              doc_name: str = None) -> str:
    """Constrain a line to be vertical."""
    result = _call("freecad_ai_bridge.sketcher_ops", "add_constraint_vertical",
                   sketch_name=sketch_name, geo_idx=geo_idx, doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def sketch_constrain_lock(sketch_name: str, geo_idx: int, point_idx: int,
                          doc_name: str = None) -> str:
    """Lock a point at its current position."""
    result = _call("freecad_ai_bridge.sketcher_ops", "add_constraint_lock",
                   sketch_name=sketch_name, geo_idx=geo_idx, point_idx=point_idx, doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def sketch_constrain_block(sketch_name: str, geo_idx: int,
                           doc_name: str = None) -> str:
    """Block a geometry element (prevent any movement)."""
    result = _call("freecad_ai_bridge.sketcher_ops", "add_constraint_block",
                   sketch_name=sketch_name, geo_idx=geo_idx, doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def sketch_constrain_distance(sketch_name: str, geo_idx1: int, point_idx1: int,
                              geo_idx2: int, point_idx2: int, value: float,
                              doc_name: str = None) -> str:
    """Set distance between two points."""
    result = _call("freecad_ai_bridge.sketcher_ops", "add_constraint_distance",
                   sketch_name=sketch_name, geo_idx1=geo_idx1, point_idx1=point_idx1,
                   geo_idx2=geo_idx2, point_idx2=point_idx2, value=value, doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def sketch_constrain_distance_x(sketch_name: str, geo_idx: int, point_idx: int,
                                value: float, doc_name: str = None) -> str:
    """Set horizontal distance from origin to a point."""
    result = _call("freecad_ai_bridge.sketcher_ops", "add_constraint_distance_x",
                   sketch_name=sketch_name, geo_idx=geo_idx, point_idx=point_idx,
                   value=value, doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def sketch_constrain_distance_y(sketch_name: str, geo_idx: int, point_idx: int,
                                value: float, doc_name: str = None) -> str:
    """Set vertical distance from origin to a point."""
    result = _call("freecad_ai_bridge.sketcher_ops", "add_constraint_distance_y",
                   sketch_name=sketch_name, geo_idx=geo_idx, point_idx=point_idx,
                   value=value, doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def sketch_constrain_angle(sketch_name: str, geo_idx1: int, geo_idx2: int,
                           angle: float, doc_name: str = None) -> str:
    """Set angle between two lines (in degrees)."""
    result = _call("freecad_ai_bridge.sketcher_ops", "add_constraint_angle",
                   sketch_name=sketch_name, geo_idx1=geo_idx1, geo_idx2=geo_idx2,
                   angle=angle, doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def sketch_constrain_radius(sketch_name: str, geo_idx: int, radius: float,
                            doc_name: str = None) -> str:
    """Set radius of a circle or arc."""
    result = _call("freecad_ai_bridge.sketcher_ops", "add_constraint_radius",
                   sketch_name=sketch_name, geo_idx=geo_idx, radius=radius, doc_name=doc_name)
    return json.dumps(result)


# =============================================================================
# PartDesign Tools
# =============================================================================


@mcp.tool()
def partdesign_body(name: str = "Body", doc_name: str = None) -> str:
    """Create a new PartDesign Body (container for features)."""
    result = _call("freecad_ai_bridge.partdesign_ops", "create_body", name=name, doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def partdesign_pad(sketch_name: str, length: float, name: str = "Pad",
                   symmetric: bool = False, reversed: bool = False,
                   doc_name: str = None) -> str:
    """Pad (extrude) a sketch to create a solid.

    Args:
        sketch_name: Name of the sketch to pad
        length: Extrusion length in mm
        symmetric: Pad equally in both directions
        reversed: Pad in reverse direction
    """
    result = _call("freecad_ai_bridge.partdesign_ops", "pad",
                   sketch_name=sketch_name, length=length, name=name,
                   symmetric=symmetric, reversed=reversed, doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def partdesign_pocket(sketch_name: str, length: float = 10.0, name: str = "Pocket",
                      through_all: bool = False, reversed: bool = False,
                      doc_name: str = None) -> str:
    """Create a pocket (subtractive extrusion) from a sketch.

    Args:
        length: Pocket depth (ignored if through_all=True)
        through_all: Cut through entire part
    """
    result = _call("freecad_ai_bridge.partdesign_ops", "pocket",
                   sketch_name=sketch_name, length=length, name=name,
                   through_all=through_all, reversed=reversed, doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def partdesign_revolution(sketch_name: str, angle: float = 360.0,
                          name: str = "Revolution", axis: str = "V",
                          reversed: bool = False, doc_name: str = None) -> str:
    """Revolve a sketch around an axis to create a solid of revolution.

    Args:
        angle: Revolution angle in degrees (360 = full)
        axis: 'V' (vertical/Y-axis), 'H' (horizontal/X-axis), 'N' (normal/Z-axis)
    """
    result = _call("freecad_ai_bridge.partdesign_ops", "revolution",
                   sketch_name=sketch_name, angle=angle, name=name,
                   axis=axis, reversed=reversed, doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def partdesign_groove(sketch_name: str, angle: float = 360.0,
                      name: str = "Groove", axis: str = "V",
                      reversed: bool = False, doc_name: str = None) -> str:
    """Create a groove (subtractive revolution) - cuts material by revolving a sketch."""
    result = _call("freecad_ai_bridge.partdesign_ops", "groove",
                   sketch_name=sketch_name, angle=angle, name=name,
                   axis=axis, reversed=reversed, doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def partdesign_loft(sketch_names: list, name: str = "Loft",
                    solid: bool = True, ruled: bool = False,
                    closed: bool = False, doc_name: str = None) -> str:
    """Create a loft (blend) between multiple sketch profiles.

    Args:
        sketch_names: List of sketch names in order (at least 2)
        ruled: Use ruled surfaces (straight edges between profiles)
        closed: Connect last profile back to first
    """
    result = _call("freecad_ai_bridge.partdesign_ops", "loft",
                   sketch_names=sketch_names, name=name, solid=solid,
                   ruled=ruled, closed=closed, doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def partdesign_sweep(sketch_name: str, spine_name: str, name: str = "Sweep",
                     solid: bool = True, doc_name: str = None) -> str:
    """Sweep a profile sketch along a spine/path.

    Args:
        sketch_name: Profile sketch
        spine_name: Path sketch or edge to sweep along
    """
    result = _call("freecad_ai_bridge.partdesign_ops", "sweep",
                   sketch_name=sketch_name, spine_name=spine_name,
                   name=name, solid=solid, doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def partdesign_hole(sketch_name: str, diameter: float, depth: float,
                    name: str = "Hole", threaded: bool = False,
                    thread_type: str = "ISO", thread_size: str = "M6",
                    doc_name: str = None) -> str:
    """Create a hole feature (positioned by sketch points).

    Args:
        sketch_name: Sketch with center point(s) for hole positions
        diameter: Hole diameter in mm
        depth: Hole depth in mm
        threaded: Create threaded hole
        thread_size: Thread size (e.g., 'M6', 'M8', 'M10')
    """
    result = _call("freecad_ai_bridge.partdesign_ops", "hole",
                   sketch_name=sketch_name, diameter=diameter, depth=depth,
                   name=name, threaded=threaded, thread_type=thread_type,
                   thread_size=thread_size, doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def partdesign_fillet(base_name: str, edges: list, radius: float,
                     name: str = "Fillet", doc_name: str = None) -> str:
    """Add fillet (rounded edges) to a feature.

    Args:
        base_name: Name of the feature to fillet
        edges: List of edge names, e.g. ["Edge1", "Edge2", "Edge5"]
        radius: Fillet radius in mm
    """
    result = _call("freecad_ai_bridge.partdesign_ops", "fillet",
                   base_name=base_name, edges=edges, radius=radius,
                   name=name, doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def partdesign_chamfer(base_name: str, edges: list, size: float,
                       name: str = "Chamfer", doc_name: str = None) -> str:
    """Add chamfer (beveled edges) to a feature.

    Args:
        base_name: Name of the feature to chamfer
        edges: List of edge names, e.g. ["Edge1", "Edge3"]
        size: Chamfer size in mm
    """
    result = _call("freecad_ai_bridge.partdesign_ops", "chamfer",
                   base_name=base_name, edges=edges, size=size,
                   name=name, doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def partdesign_thickness(base_name: str, faces: list, value: float,
                         name: str = "Thickness", doc_name: str = None) -> str:
    """Shell a solid - removes faces and offsets remaining walls.

    Args:
        base_name: Feature name
        faces: List of face names to remove, e.g. ["Face1"]
        value: Wall thickness in mm
    """
    result = _call("freecad_ai_bridge.partdesign_ops", "thickness",
                   base_name=base_name, faces=faces, value=value,
                   name=name, doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def partdesign_draft(base_name: str, faces: list, angle: float,
                     name: str = "Draft", doc_name: str = None) -> str:
    """Add draft angle to faces (for mold release).

    Args:
        faces: List of face names to draft
        angle: Draft angle in degrees
    """
    result = _call("freecad_ai_bridge.partdesign_ops", "draft",
                   base_name=base_name, faces=faces, angle=angle,
                   name=name, doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def partdesign_linear_pattern(feature_name: str, direction: str = "X",
                              length: float = 100.0, occurrences: int = 3,
                              name: str = "LinearPattern", doc_name: str = None) -> str:
    """Create a linear pattern (array) of a feature.

    Args:
        feature_name: Feature to pattern
        direction: 'X', 'Y', or 'Z'
        length: Total span of the pattern in mm
        occurrences: Number of copies including original
    """
    result = _call("freecad_ai_bridge.partdesign_ops", "linear_pattern",
                   feature_name=feature_name, direction=direction,
                   length=length, occurrences=occurrences,
                   name=name, doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def partdesign_polar_pattern(feature_name: str, axis: str = "Z",
                             angle: float = 360.0, occurrences: int = 6,
                             name: str = "PolarPattern", doc_name: str = None) -> str:
    """Create a polar (circular) pattern of a feature.

    Args:
        axis: Rotation axis - 'X', 'Y', or 'Z'
        angle: Total angle span in degrees
        occurrences: Number of copies including original
    """
    result = _call("freecad_ai_bridge.partdesign_ops", "polar_pattern",
                   feature_name=feature_name, axis=axis,
                   angle=angle, occurrences=occurrences,
                   name=name, doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def partdesign_mirrored(feature_name: str, plane: str = "XY",
                        name: str = "Mirrored", doc_name: str = None) -> str:
    """Mirror a feature about a plane (XY, XZ, or YZ)."""
    result = _call("freecad_ai_bridge.partdesign_ops", "mirrored",
                   feature_name=feature_name, plane=plane,
                   name=name, doc_name=doc_name)
    return json.dumps(result)


# =============================================================================
# Part Primitives
# =============================================================================


@mcp.tool()
def part_box(length: float, width: float, height: float,
             x: float = 0, y: float = 0, z: float = 0,
             name: str = "Box", doc_name: str = None) -> str:
    """Create a box (Part primitive). Position at (x, y, z)."""
    result = _call("freecad_ai_bridge.part_ops", "make_box",
                   length=length, width=width, height=height,
                   x=x, y=y, z=z, name=name, doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def part_cylinder(radius: float, height: float,
                  x: float = 0, y: float = 0, z: float = 0,
                  angle: float = 360.0, name: str = "Cylinder",
                  doc_name: str = None) -> str:
    """Create a cylinder (Part primitive). Angle < 360 for partial cylinder."""
    result = _call("freecad_ai_bridge.part_ops", "make_cylinder",
                   radius=radius, height=height, x=x, y=y, z=z,
                   angle=angle, name=name, doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def part_sphere(radius: float, x: float = 0, y: float = 0, z: float = 0,
                name: str = "Sphere", doc_name: str = None) -> str:
    """Create a sphere (Part primitive)."""
    result = _call("freecad_ai_bridge.part_ops", "make_sphere",
                   radius=radius, x=x, y=y, z=z, name=name, doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def part_cone(radius1: float, radius2: float, height: float,
              x: float = 0, y: float = 0, z: float = 0,
              name: str = "Cone", doc_name: str = None) -> str:
    """Create a cone (Part primitive). radius2=0 for pointed cone."""
    result = _call("freecad_ai_bridge.part_ops", "make_cone",
                   radius1=radius1, radius2=radius2, height=height,
                   x=x, y=y, z=z, name=name, doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def part_torus(radius1: float, radius2: float,
               x: float = 0, y: float = 0, z: float = 0,
               name: str = "Torus", doc_name: str = None) -> str:
    """Create a torus (donut shape). radius1=major, radius2=minor."""
    result = _call("freecad_ai_bridge.part_ops", "make_torus",
                   radius1=radius1, radius2=radius2,
                   x=x, y=y, z=z, name=name, doc_name=doc_name)
    return json.dumps(result)


# =============================================================================
# Boolean Operations
# =============================================================================


@mcp.tool()
def boolean_fuse(obj_names: list, name: str = "Fuse", doc_name: str = None) -> str:
    """Fuse (union/add) multiple objects together."""
    result = _call("freecad_ai_bridge.part_ops", "boolean_fuse",
                   obj_names=obj_names, name=name, doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def boolean_cut(base_name: str, tool_name: str, name: str = "Cut",
                doc_name: str = None) -> str:
    """Cut (subtract) tool from base."""
    result = _call("freecad_ai_bridge.part_ops", "boolean_cut",
                   base_name=base_name, tool_name=tool_name,
                   name=name, doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def boolean_common(obj_names: list, name: str = "Common",
                   doc_name: str = None) -> str:
    """Common (intersection) of multiple objects."""
    result = _call("freecad_ai_bridge.part_ops", "boolean_common",
                   obj_names=obj_names, name=name, doc_name=doc_name)
    return json.dumps(result)


# =============================================================================
# Transform
# =============================================================================


@mcp.tool()
def set_placement(obj_name: str, x: float = 0, y: float = 0, z: float = 0,
                  rx: float = 0, ry: float = 0, rz: float = 0,
                  doc_name: str = None) -> str:
    """Set position and rotation of an object. Rotation in degrees (Euler angles)."""
    result = _call("freecad_ai_bridge.part_ops", "set_placement",
                   obj_name=obj_name, x=x, y=y, z=z, rx=rx, ry=ry, rz=rz, doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def move_object(obj_name: str, dx: float = 0, dy: float = 0, dz: float = 0,
                doc_name: str = None) -> str:
    """Move an object by a relative offset."""
    result = _call("freecad_ai_bridge.part_ops", "move_object",
                   obj_name=obj_name, dx=dx, dy=dy, dz=dz, doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def rotate_object(obj_name: str, axis_x: float = 0, axis_y: float = 0,
                  axis_z: float = 1, angle: float = 0,
                  doc_name: str = None) -> str:
    """Rotate an object around an axis (angle in degrees)."""
    result = _call("freecad_ai_bridge.part_ops", "rotate_object",
                   obj_name=obj_name, axis_x=axis_x, axis_y=axis_y,
                   axis_z=axis_z, angle=angle, doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def scale_object(obj_name: str, factor: float, name: str = None,
                 doc_name: str = None) -> str:
    """Scale an object uniformly (creates a scaled copy)."""
    result = _call("freecad_ai_bridge.part_ops", "scale_object",
                   obj_name=obj_name, factor=factor, name=name, doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def mirror_object(obj_name: str, plane: str = "XY", name: str = None,
                  doc_name: str = None) -> str:
    """Mirror an object across a plane (XY, XZ, or YZ)."""
    result = _call("freecad_ai_bridge.part_ops", "mirror_object",
                   obj_name=obj_name, plane=plane, name=name, doc_name=doc_name)
    return json.dumps(result)


# =============================================================================
# View & Visualization
# =============================================================================


@mcp.tool()
def screenshot(width: int = 800, height: int = 600, view: str = None,
               doc_name: str = None) -> str:
    """Capture a screenshot of the FreeCAD 3D view.

    Args:
        view: Optional camera preset - 'isometric', 'front', 'back', 'top', 'bottom', 'left', 'right'
    Returns:
        Base64-encoded PNG image data
    """
    result = _call("freecad_ai_bridge.view_ops", "get_screenshot",
                   width=width, height=height, view=view, doc_name=doc_name)
    return json.dumps({"image": result.get("image_base64", ""), "format": "png"})


@mcp.tool()
def set_view(direction: str) -> str:
    """Set the 3D view direction: 'isometric', 'front', 'back', 'top', 'bottom', 'left', 'right'."""
    result = _call("freecad_ai_bridge.view_ops", "set_view", direction=direction)
    return json.dumps(result)


@mcp.tool()
def fit_view() -> str:
    """Zoom to fit all objects in view."""
    result = _call("freecad_ai_bridge.view_ops", "fit_all")
    return json.dumps(result)


@mcp.tool()
def set_visibility(obj_name: str, visible: bool, doc_name: str = None) -> str:
    """Show or hide an object."""
    result = _call("freecad_ai_bridge.view_ops", "set_visibility",
                   obj_name=obj_name, visible=visible, doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def set_color(obj_name: str, r: float, g: float, b: float,
              doc_name: str = None) -> str:
    """Set object color (RGB values 0.0-1.0)."""
    result = _call("freecad_ai_bridge.view_ops", "set_color",
                   obj_name=obj_name, r=r, g=g, b=b, doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def set_transparency(obj_name: str, transparency: int, doc_name: str = None) -> str:
    """Set object transparency (0=opaque, 100=fully transparent)."""
    result = _call("freecad_ai_bridge.view_ops", "set_transparency",
                   obj_name=obj_name, transparency=transparency, doc_name=doc_name)
    return json.dumps(result)


# =============================================================================
# Export / Import
# =============================================================================


@mcp.tool()
def export_step(path: str, obj_names: list = None, doc_name: str = None) -> str:
    """Export to STEP format (industry standard)."""
    result = _call("freecad_ai_bridge.view_ops", "export_step",
                   path=path, obj_names=obj_names, doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def export_stl(path: str, obj_names: list = None, doc_name: str = None) -> str:
    """Export to STL format (for 3D printing)."""
    result = _call("freecad_ai_bridge.view_ops", "export_stl",
                   path=path, obj_names=obj_names, doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def import_step(path: str, doc_name: str = None) -> str:
    """Import a STEP file."""
    result = _call("freecad_ai_bridge.view_ops", "import_step",
                   path=path, doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def import_stl(path: str, doc_name: str = None) -> str:
    """Import an STL file."""
    result = _call("freecad_ai_bridge.view_ops", "import_stl",
                   path=path, doc_name=doc_name)
    return json.dumps(result)


# =============================================================================
# Measurement & Utilities
# =============================================================================


@mcp.tool()
def measure(obj_name: str, doc_name: str = None) -> str:
    """Measure an object: volume, area, bounding box, center of mass."""
    result = _call("freecad_ai_bridge.view_ops", "measure_object",
                   obj_name=obj_name, doc_name=doc_name)
    return json.dumps(result, indent=2)


@mcp.tool()
def undo(doc_name: str = None) -> str:
    """Undo the last operation."""
    result = _call("freecad_ai_bridge.view_ops", "undo", doc_name=doc_name)
    return json.dumps(result)


@mcp.tool()
def redo(doc_name: str = None) -> str:
    """Redo the last undone operation."""
    result = _call("freecad_ai_bridge.view_ops", "redo", doc_name=doc_name)
    return json.dumps(result)


# =============================================================================
# Fallback: Execute Python
# =============================================================================


@mcp.tool()
def execute_python(code: str) -> str:
    """Execute arbitrary Python code in FreeCAD (for operations not covered by other tools).

    The code runs in FreeCAD's Python environment with access to all modules.
    Set a variable named 'result' to return data.

    Example: "import Part; result = Part.makeBox(10,10,10).Volume"
    """
    result = _conn.execute(code)
    return json.dumps({"result": result})


# =============================================================================
# Entry point
# =============================================================================


def main():
    """Run the MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
