"""View and export operations running inside FreeCAD."""

import base64
import os
import tempfile

import FreeCAD
import FreeCADGui


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


# =============================================================================
# View Operations
# =============================================================================


def get_screenshot(width: int = 800, height: int = 600,
                   view: str = None, doc_name: str = None) -> dict:
    """Capture a screenshot of the current 3D view.

    Args:
        width: Image width in pixels
        height: Image height in pixels
        view: Optional view preset - 'isometric', 'front', 'back', 'top', 'bottom', 'left', 'right'
    """
    if not FreeCAD.GuiUp:
        raise RuntimeError("GUI not available for screenshots")

    active_view = FreeCADGui.ActiveDocument.ActiveView

    # Set view angle if specified
    if view:
        view_map = {
            "isometric": "ViewIsometric",
            "front": "ViewFront",
            "back": "ViewRear",
            "top": "ViewTop",
            "bottom": "ViewBottom",
            "left": "ViewLeft",
            "right": "ViewRight",
        }
        cmd = view_map.get(view.lower())
        if cmd:
            getattr(active_view, cmd.replace("View", "view"))()

    # Fit all objects in view
    active_view.fitAll()
    FreeCADGui.updateGui()

    # Save screenshot to temp file
    tmp_file = os.path.join(tempfile.gettempdir(), "freecad_mcp_screenshot.png")
    active_view.saveImage(tmp_file, width, height, "Current")

    # Read and encode as base64
    with open(tmp_file, "rb") as f:
        img_data = base64.b64encode(f.read()).decode("utf-8")

    os.remove(tmp_file)

    return {
        "image_base64": img_data,
        "width": width,
        "height": height,
        "format": "png",
    }


def set_view(direction: str) -> dict:
    """Set the 3D view direction.

    Args:
        direction: 'isometric', 'front', 'back', 'top', 'bottom', 'left', 'right'
    """
    if not FreeCAD.GuiUp:
        raise RuntimeError("GUI not available")

    active_view = FreeCADGui.ActiveDocument.ActiveView
    view_methods = {
        "isometric": active_view.viewIsometric,
        "front": active_view.viewFront,
        "back": active_view.viewRear,
        "top": active_view.viewTop,
        "bottom": active_view.viewBottom,
        "left": active_view.viewLeft,
        "right": active_view.viewRight,
    }

    method = view_methods.get(direction.lower())
    if method:
        method()
        FreeCADGui.updateGui()
        return {"view": direction}
    else:
        raise ValueError(f"Unknown view direction '{direction}'")


def fit_all() -> dict:
    """Fit all objects in the view."""
    if not FreeCAD.GuiUp:
        raise RuntimeError("GUI not available")

    FreeCADGui.ActiveDocument.ActiveView.fitAll()
    FreeCADGui.updateGui()
    return {"status": "ok"}


def set_visibility(obj_name: str, visible: bool, doc_name: str = None) -> dict:
    """Set visibility of an object."""
    obj = _get_object(obj_name, doc_name)
    if obj.ViewObject:
        obj.ViewObject.Visibility = visible
    FreeCADGui.updateGui()
    return {"name": obj_name, "visible": visible}


def set_color(obj_name: str, r: float, g: float, b: float,
              doc_name: str = None) -> dict:
    """Set color of an object (RGB values 0.0-1.0)."""
    obj = _get_object(obj_name, doc_name)
    if obj.ViewObject:
        obj.ViewObject.ShapeColor = (r, g, b)
    FreeCADGui.updateGui()
    return {"name": obj_name, "color": [r, g, b]}


def set_transparency(obj_name: str, transparency: int, doc_name: str = None) -> dict:
    """Set transparency of an object (0=opaque, 100=fully transparent)."""
    obj = _get_object(obj_name, doc_name)
    if obj.ViewObject:
        obj.ViewObject.Transparency = max(0, min(100, transparency))
    FreeCADGui.updateGui()
    return {"name": obj_name, "transparency": transparency}


# =============================================================================
# Export Operations
# =============================================================================


def export_step(path: str, obj_names: list = None, doc_name: str = None) -> dict:
    """Export objects to STEP format.

    Args:
        path: Output file path
        obj_names: List of object names to export (None = all visible)
    """
    import Import
    doc = _get_doc(doc_name)

    if obj_names:
        objects = [_get_object(n, doc_name) for n in obj_names]
    else:
        objects = [obj for obj in doc.Objects if hasattr(obj, "Shape") and obj.Shape and not obj.Shape.isNull()]

    Import.export(objects, path)
    return {"path": path, "objects_exported": len(objects)}


def export_stl(path: str, obj_names: list = None, doc_name: str = None) -> dict:
    """Export objects to STL format."""
    import Mesh
    doc = _get_doc(doc_name)

    if obj_names:
        objects = [_get_object(n, doc_name) for n in obj_names]
    else:
        objects = [obj for obj in doc.Objects if hasattr(obj, "Shape") and obj.Shape and not obj.Shape.isNull()]

    meshes = []
    for obj in objects:
        mesh = Mesh.Mesh(obj.Shape.tessellate(0.1)[0])
        meshes.append(mesh)

    if meshes:
        combined = meshes[0]
        for m in meshes[1:]:
            combined.addMesh(m)
        combined.write(path)

    return {"path": path, "objects_exported": len(objects)}


def export_obj(path: str, obj_names: list = None, doc_name: str = None) -> dict:
    """Export objects to OBJ format."""
    import Mesh
    doc = _get_doc(doc_name)

    if obj_names:
        objects = [_get_object(n, doc_name) for n in obj_names]
    else:
        objects = [obj for obj in doc.Objects if hasattr(obj, "Shape") and obj.Shape and not obj.Shape.isNull()]

    Mesh.export(objects, path)
    return {"path": path, "objects_exported": len(objects)}


def import_step(path: str, doc_name: str = None) -> dict:
    """Import a STEP file."""
    import Import
    doc = _get_doc(doc_name)
    Import.insert(path, doc.Name)
    doc.recompute()
    return {"path": path, "document": doc.Name}


def import_stl(path: str, doc_name: str = None) -> dict:
    """Import an STL file."""
    import Mesh
    doc = _get_doc(doc_name)
    Mesh.insert(path, doc.Name)
    doc.recompute()
    return {"path": path, "document": doc.Name}


# =============================================================================
# Measurement
# =============================================================================


def measure_object(obj_name: str, doc_name: str = None) -> dict:
    """Get measurements of an object (volume, area, bounding box, center of mass)."""
    obj = _get_object(obj_name, doc_name)
    if not hasattr(obj, "Shape") or obj.Shape.isNull():
        raise ValueError(f"Object '{obj_name}' has no shape")

    shape = obj.Shape
    bb = shape.BoundBox
    result = {
        "name": obj_name,
        "volume": shape.Volume,
        "area": shape.Area,
        "bounding_box": {
            "x_length": bb.XLength,
            "y_length": bb.YLength,
            "z_length": bb.ZLength,
            "min": {"x": bb.XMin, "y": bb.YMin, "z": bb.ZMin},
            "max": {"x": bb.XMax, "y": bb.YMax, "z": bb.ZMax},
        },
    }
    if hasattr(shape, "CenterOfMass"):
        com = shape.CenterOfMass
        result["center_of_mass"] = {"x": com.x, "y": com.y, "z": com.z}
    return result


def undo(doc_name: str = None) -> dict:
    """Undo last operation."""
    doc = _get_doc(doc_name)
    doc.undo()
    doc.recompute()
    if FreeCAD.GuiUp:
        FreeCADGui.updateGui()
    return {"status": "ok"}


def redo(doc_name: str = None) -> dict:
    """Redo last undone operation."""
    doc = _get_doc(doc_name)
    doc.redo()
    doc.recompute()
    if FreeCAD.GuiUp:
        FreeCADGui.updateGui()
    return {"status": "ok"}
