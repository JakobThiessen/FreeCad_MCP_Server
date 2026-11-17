"""View and export operations running inside FreeCAD."""

import base64
import math
import os
import tempfile

import FreeCAD
import FreeCADGui

from freecad_ai_bridge.transactions import draft_wire_snapshot, repair_draft_wire_endpoints

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


MAX_IMAGE_SIZE = 4096
VIEW_METHODS = {"isometric": "viewIsometric", "front": "viewFront", "back": "viewRear", "top": "viewTop",
                "bottom": "viewBottom", "left": "viewLeft", "right": "viewRight"}


def _view(doc_name=None):
    """Active 3D view of an explicit or the active document."""
    if not FreeCAD.GuiUp:
        raise RuntimeError("GUI not available")
    doc = _get_doc(doc_name)
    gui_document = FreeCADGui.getDocument(doc.Name)
    active_view = gui_document.activeView() if gui_document else None
    if active_view is None or not hasattr(active_view, "viewIsometric"):
        raise ValueError(f"Document '{doc.Name}' has no 3D view")
    return doc, active_view


def _direction(direction):
    key = direction.lower() if isinstance(direction, str) else None
    if key not in VIEW_METHODS:
        raise ValueError(f"Unknown view direction '{direction}'; use one of {', '.join(VIEW_METHODS)}")
    return VIEW_METHODS[key]


def _apply_direction(active_view, method):
    """Switch the camera without navigation animation so the new orientation is final when this returns."""
    animated = hasattr(active_view, "isAnimationEnabled") and active_view.isAnimationEnabled()
    if animated:
        active_view.setAnimationEnabled(False)
    try:
        getattr(active_view, method)()
    finally:
        if animated:
            active_view.setAnimationEnabled(True)


def get_screenshot(width: int = 800, height: int = 600,
                   view: str = None, doc_name: str = None) -> dict:
    """Capture a screenshot of the current 3D view.

    Args:
        width, height: Image size in pixels, 1..4096 each (larger offscreen buffers crash FreeCAD)
        view: Optional view preset - 'isometric', 'front', 'back', 'top', 'bottom', 'left', 'right'
    """
    for value in (width, height):
        if type(value) is not int or not 1 <= value <= MAX_IMAGE_SIZE:
            raise ValueError(f"Screenshot dimensions must be integers in 1..{MAX_IMAGE_SIZE}")
    method = _direction(view) if view else None
    doc, active_view = _view(doc_name)
    if method:
        _apply_direction(active_view, method)

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


def set_view(direction: str, doc_name: str = None) -> dict:
    """Set the 3D view direction of an explicit or the active document.

    Args:
        direction: 'isometric', 'front', 'back', 'top', 'bottom', 'left', 'right'
    """
    method = _direction(direction)
    doc, active_view = _view(doc_name)
    _apply_direction(active_view, method)
    FreeCADGui.updateGui()
    return {"view": direction.lower(), "document": doc.Name}


def fit_all(doc_name: str = None) -> dict:
    """Fit all objects in the view of an explicit or the active document."""
    doc, active_view = _view(doc_name)
    active_view.fitAll()
    FreeCADGui.updateGui()
    return {"status": "ok", "document": doc.Name}


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
    losses = ["FreeCAD feature history, constraints, and Assembly joints are not preserved in STEP."]
    return {"path": path, "objects_exported": len(objects), "format": "STEP",
            "losses": losses, "warnings": losses}


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
    elif shape.Solids and abs(sum(solid.Volume for solid in shape.Solids)) > 1e-12:
        # Generic TopoShapes (e.g. PartDesign Pocket results) expose no CenterOfMass; use their solids.
        total = sum(solid.Volume for solid in shape.Solids)
        com = sum((solid.CenterOfMass * solid.Volume for solid in shape.Solids), FreeCAD.Vector()) * (1 / total)
        result["center_of_mass"] = {"x": com.x, "y": com.y, "z": com.z}
    return result


def undo(doc_name: str = None) -> dict:
    """Undo last operation."""
    doc = _get_doc(doc_name)
    placements = draft_wire_snapshot(doc)
    doc.undo()
    repaired = repair_draft_wire_endpoints(doc, placements)
    doc.recompute()
    if FreeCAD.GuiUp:
        FreeCADGui.updateGui()
    return {"status": "ok", **({"draft_wire_endpoint_repairs": repaired} if repaired else {})}


def redo(doc_name: str = None) -> dict:
    """Redo last undone operation."""
    doc = _get_doc(doc_name)
    placements = draft_wire_snapshot(doc)
    doc.redo()
    repaired = repair_draft_wire_endpoints(doc, placements)
    doc.recompute()
    if FreeCAD.GuiUp:
        FreeCADGui.updateGui()
    return {"status": "ok", **({"draft_wire_endpoint_repairs": repaired} if repaired else {})}
