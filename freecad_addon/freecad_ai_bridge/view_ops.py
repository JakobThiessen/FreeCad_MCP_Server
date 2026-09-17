"""View and export operations running inside FreeCAD."""

import base64
import math
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

    if width <= 0 or height <= 0:
        raise ValueError("Screenshot dimensions must be positive")
    doc = _get_doc(doc_name)
    active_view = FreeCADGui.getDocument(doc.Name).activeView()

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
        if not cmd:
            raise ValueError(f"Unknown view direction '{view}'")
        getattr(active_view, cmd.replace("View", "view"))()

    # Fit all objects in view
    doc.recompute()
    FreeCADGui.updateGui()
    active_view.fitAll()
    FreeCADGui.updateGui()

    # Save screenshot to temp file
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as image_file:
        tmp_file = image_file.name
    try:
        active_view.saveImage(tmp_file, width, height, "Current")
        with open(tmp_file, "rb") as image_file:
            img_data = base64.b64encode(image_file.read()).decode("utf-8")
    finally:
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
    if any(isinstance(channel, bool) or not isinstance(channel, (float, int)) or not math.isfinite(channel)
           or not 0 <= channel <= 1 for channel in (r, g, b)):
        raise ValueError("RGB channels must be finite numbers in 0..1")
    obj = _get_object(obj_name, doc_name)
    if obj.ViewObject:
        obj.ViewObject.ShapeColor = (r, g, b)
    FreeCADGui.updateGui()
    return {"name": obj_name, "color": [r, g, b]}


def set_transparency(obj_name: str, transparency: int, doc_name: str = None) -> dict:
    """Set transparency of an object (0=opaque, 100=fully transparent)."""
    if type(transparency) is not int:
        raise ValueError("Transparency must be an integer percentage")
    transparency = max(0, min(100, transparency))
    obj = _get_object(obj_name, doc_name)
    if obj.ViewObject:
        obj.ViewObject.Transparency = transparency
    FreeCADGui.updateGui()
    return {"name": obj_name, "transparency": transparency}


# =============================================================================
# Export Operations
# =============================================================================


def _export_objects(doc_name, obj_names):
    doc = _get_doc(doc_name)
    if obj_names is not None:
        objects = [_get_object(name, doc.Name) for name in dict.fromkeys(obj_names)]
    else:
        objects = []
        for obj in doc.Objects:
            if not obj.ViewObject or not obj.ViewObject.Visibility:
                continue
            parent = obj.getParentGeoFeatureGroup()
            skip = False
            while parent:
                if not parent.ViewObject.Visibility or hasattr(parent, "Shape"):
                    skip = True
                    break
                parent = parent.getParentGeoFeatureGroup()
            if not skip and (
                (hasattr(obj, "Shape") and not obj.Shape.isNull())
                or (hasattr(obj, "Mesh") and obj.Mesh.CountFacets > 0)
            ):
                objects.append(obj)
    if not objects:
        raise ValueError("No exportable objects selected")
    return objects


def _export_mesh(path, objects):
    import Mesh
    import MeshPart

    combined = Mesh.Mesh()
    for obj in objects:
        if hasattr(obj, "Mesh"):
            mesh = obj.Mesh.copy()
        elif hasattr(obj, "Shape") and not obj.Shape.isNull():
            mesh = MeshPart.meshFromShape(
                Shape=obj.Shape, LinearDeflection=0.1, AngularDeflection=0.5, Relative=False
            )
        else:
            raise ValueError(f"Object '{obj.Name}' has no exportable shape or mesh")
        combined.addMesh(mesh)
    if combined.CountFacets == 0:
        raise ValueError("Selected objects contain no mesh faces")
    combined.write(path)
    return {"path": path, "objects_exported": len(objects), "facets": combined.CountFacets}


def export_step(path: str, obj_names: list = None, doc_name: str = None) -> dict:
    """Export objects to STEP format.

    Args:
        path: Output file path
        obj_names: List of object names to export (None = all visible)
    """
    import Import
    objects = _export_objects(doc_name, obj_names)
    for obj in objects:
        if not hasattr(obj, "Shape") or obj.Shape.isNull():
            raise ValueError(f"Object '{obj.Name}' has no STEP-exportable shape")

    Import.export(objects, path)
    return {"path": path, "objects_exported": len(objects)}


def export_stl(path: str, obj_names: list = None, doc_name: str = None) -> dict:
    """Export objects to STL format."""
    return _export_mesh(path, _export_objects(doc_name, obj_names))


def export_obj(path: str, obj_names: list = None, doc_name: str = None) -> dict:
    """Export objects to OBJ format."""
    return _export_mesh(path, _export_objects(doc_name, obj_names))


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
