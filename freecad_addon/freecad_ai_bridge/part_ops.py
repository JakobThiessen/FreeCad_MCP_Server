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
    return result


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
# Boolean Operations
# =============================================================================


def boolean_fuse(obj_names: list, name: str = "Fuse", doc_name: str = None) -> dict:
    """Fuse (union) multiple objects."""
    doc = _get_doc(doc_name)
    objects = [_get_object(n, doc_name) for n in obj_names]

    fuse = doc.addObject("Part::MultiFuse", name)
    fuse.Shapes = objects
    doc.recompute()

    for obj in objects:
        obj.Visibility = False
    return _shape_result(fuse)


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

    base.Visibility = False
    tool.Visibility = False
    return _shape_result(cut)


def boolean_common(obj_names: list, name: str = "Common",
                   doc_name: str = None) -> dict:
    """Common (intersection) of multiple objects."""
    doc = _get_doc(doc_name)
    objects = [_get_object(n, doc_name) for n in obj_names]

    common = doc.addObject("Part::MultiCommon", name)
    common.Shapes = objects
    doc.recompute()

    for obj in objects:
        obj.Visibility = False
    return _shape_result(common)


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

    fillet.Shape = obj.Shape.makeFillet(radius, [obj.Shape.Edges[i - 1] for i, _, _ in edge_list])
    doc.recompute()

    obj.Visibility = False
    return _shape_result(fillet)


def part_chamfer(obj_name: str, edges: list, size: float,
                 name: str = "Chamfer", doc_name: str = None) -> dict:
    """Add chamfer to edges (Part-level)."""
    doc = _get_doc(doc_name)
    obj = _get_object(obj_name, doc_name)

    chamfer = doc.addObject("Part::Chamfer", name)
    chamfer.Base = obj

    edge_indices = []
    for e in edges:
        if isinstance(e, int):
            edge_indices.append(e)
        else:
            edge_indices.append(int("".join(filter(str.isdigit, str(e)))))

    chamfer.Shape = obj.Shape.makeChamfer(size, [obj.Shape.Edges[i - 1] for i in edge_indices])
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
        rx, ry, rz: Rotation angles in degrees (Euler angles)
    """
    doc = _get_doc(doc_name)
    obj = _get_object(obj_name, doc_name)

    obj.Placement = Placement(
        Vector(x, y, z),
        Rotation(rx, ry, rz)
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
