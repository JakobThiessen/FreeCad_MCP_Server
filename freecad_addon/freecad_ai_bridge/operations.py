"""Core FreeCAD operations callable from the RPC server.

These functions run on the GUI thread and have full access to FreeCAD/FreeCADGui.
"""

import json
from typing import Any

import FreeCAD
import FreeCADGui

from freecad_ai_bridge.contracts import BRIDGE_API_VERSION, CONTRACT_VERSION, BridgeError


def execute_batch(steps: list, atomic: bool = True, preview: bool = False) -> dict:
    """Validate/preview/execute a bounded allowlisted batch on the GUI thread."""
    from freecad_ai_bridge.batch import run_batch

    return run_batch(steps, atomic, preview)


def get_capabilities() -> dict:
    """Report loaded bridge contracts and runtime availability without recompute."""
    from freecad_ai_bridge.batch import BATCH_OPERATIONS
    from freecad_ai_bridge.document_ops import _SUPPORTED

    return {
        "contract_version": CONTRACT_VERSION,
        "bridge_api_version": BRIDGE_API_VERSION,
        "freecad_version": list(FreeCAD.Version()),
        "gui_available": bool(FreeCAD.GuiUp),
        "available_workbenches": sorted(FreeCADGui.listWorkbenches()) if FreeCAD.GuiUp else [],
        "features": {
            "explicit_reference_resolution": True,
            "structured_errors": True,
            "atomic_batch": True,
            "multi_document_batch": True,
            "mutation_preview": True,
            "consistent_transactions": True,
            "document_editing": True,
            "typed_properties": True,
            "spreadsheet_expressions": True,
            "dependency_deletion_preview": True,
            "geometry_selection": True,
            "revision_checked_subelements": True,
            "geometric_measurement": True,
            "static_interference": True,
            "document_targeted_capture": True,
            "sketch_editing": True,
            "sketch_diagnostics": True,
            "sketch_external_geometry": True,
            "sketch_attachment": True,
            "raw_python_enabled": True,
        },
        "batch": {"operations": sorted(BATCH_OPERATIONS), "max_steps": 100, "max_bytes": 65536,
                  "references": "{'$ref': 'earlier_id'} resolves name; same document only",
                  "excluded": ["file_io", "document_lifecycle", "undo_redo", "nested_batch", "scripts"],
                  "preview": "validation and planned effects, not geometric simulation"},
        "options": {
            "source": "implemented bridge variants; native geometry/property compatibility checked during execution",
            "partdesign_pad": {"supported": ["length", "symmetric", "reversed"], "unavailable": ["up_to_face", "two_lengths"]},
            "partdesign_pocket": {"supported": ["length", "through_all", "reversed"], "unavailable": ["up_to_face", "two_lengths"]},
            "revolution_groove": {"axes": ["V", "H", "N"], "angle_unit": "deg"},
            "partdesign_loft_pipe": {"solid": [True], "shell": False},
            "linear_polar_pattern": {"axes": ["X", "Y", "Z"]},
            "planes": ["XY", "XZ", "YZ"],
            "sketch_angle_units": {"arc": "rad", "ellipse": "rad", "constraint": "deg"},
            "step": {"schema_selection": False, "native_default_only": True},
            "normal_mode": {"raw_python_disabled": False},
            "geometry_selection": {"kinds": ["face", "edge", "vertex"], "max_page": 256, "max_subelements": 10000,
                                   "filters": ["geometry_type", "position", "bbox", "normal", "axis", "radius", "area", "length"],
                                   "coordinates": "document_global; position is center of mass or vertex point",
                                   "revision": "conservative session/document token; object changes, recompute, Undo/Redo and reopen invalidate; requery, never remap",
                                   "consumers": ["part_fillet", "part_chamfer", "partdesign_fillet", "partdesign_chamfer",
                                                 "partdesign_thickness", "partdesign_draft", "measure_distance", "measure_angle",
                                                 "highlight_subelements", "capture_view"],
                                   "legacy_selectors": "EdgeN/FaceN and Part integer indices remain unprotected; batch unchanged"},
            "measurement": {"distance": "finite BRep minimum distance, <=32 closest point pairs",
                            "angle": "selected line/line, plane/plane, line/plane; smallest unoriented 0..90 deg",
                            "interference": "whole closed-solid objects in one document; static discrete only",
                            "contact_tolerance_mm": 0.001, "volume_tolerance_mm3": 0.000001},
            "capture_view": {"views": ["isometric", "front", "back", "top", "bottom", "left", "right"],
                             "min_dimension_px": 64, "max_dimension_px": 2048, "max_highlights": 100,
                             "recompute": False, "response": "ContractResponse JSON text plus native MCP PNG"},
            "document_editing": {"property_types": sorted(_SUPPORTED), "max_properties": 100,
                                 "max_property_list": 256, "containers": ["group", "body"],
                                 "copy": "recursive native copy; retained source dependencies rejected",
                                 "external_links": "both documents must be saved; explicitly recompute dependent documents",
                                 "safe_files": "save_document_safe/close_document_safe; legacy Save/Close retain old behavior",
                                 "deletion": "exact confirmed dependency/ownership set, single document only"},
            "spreadsheet": {"cells": "A1..ZZ99999", "max_cells": 256, "max_content_length": 4096,
                            "formulas": "native arithmetic and same-document object/cell references; no function calls",
                            "aliases": "native identifiers; reserved unit names such as W are rejected"},
            "sketcher": {"geometry_crud": ["move_point", "construction", "delete"],
                         "constraint_crud": ["value", "driving_reference", "active_inactive", "delete"],
                         "diagnostics": ["dof", "conflicting_ids", "redundant_ids", "partially_redundant_ids"],
                         "external_geometry": "revision-checked same-document edge selection",
                         "attachment": ["PartDesign::Plane", "revision-checked planar face", "offset_xyz", "rotation_xyz"],
                         "drawing": ["trim_line_arc", "extend_line_arc", "fillet_line_arc", "copy", "clone", "mirror"],
                         "limits": ["FreeCAD 1.1 trim cannot use axes", "no arbitrary spline edit suite"]},
        },
        "units": {"length": "mm", "area": "mm^2", "volume": "mm^3", "angle": "deg"},
        "coordinates": {
            "model": "document_global for top-level primitives; placements/transforms parent_local",
            "sketch_geometry": "sketch_local_xy",
            "legacy_exceptions": "See docs/CONTRACTS.md; existing angle parameters retain their units.",
        },
        "references": {
            "document": "internal Name, never Label or file path",
            "object": "internal Name within the explicit document, never Label",
            "lifetime": "name lookup in currently open documents; not a persistent identity token",
        },
    }


def resolve_reference(doc_name: str, obj_name: str = None) -> dict:
    """Resolve exact internal names without active-document or label fallback."""
    if not isinstance(doc_name, str) or not doc_name.strip():
        raise BridgeError("invalid_arguments", "doc_name must be a nonempty internal document name")
    if obj_name is not None and (not isinstance(obj_name, str) or not obj_name.strip()):
        raise BridgeError("invalid_arguments", "obj_name must be a nonempty internal object name")
    reference = {"document": doc_name}
    if obj_name is not None:
        reference["object"] = obj_name
    doc = FreeCAD.listDocuments().get(doc_name)
    if doc is None:
        raise BridgeError("document_not_found", f"Document '{doc_name}' is not open", [reference])
    if obj_name is None:
        return {"reference": reference, "label": doc.Label, "type": "App::Document"}
    obj = doc.getObject(obj_name)
    if obj is None:
        raise BridgeError("object_not_found", f"Object '{obj_name}' is not in '{doc_name}'", [reference])
    return {"reference": reference, "label": obj.Label, "type": obj.TypeId}


# =============================================================================
# Document Operations
# =============================================================================


def get_document_state() -> dict:
    """Get state of all open documents and their objects."""
    docs = {}
    for name, doc in FreeCAD.listDocuments().items():
        objects = []
        for obj in doc.Objects:
            obj_info = {
                "name": obj.Name,
                "label": obj.Label,
                "type": obj.TypeId,
            }
            if hasattr(obj, "Shape") and obj.Shape:
                obj_info["shape_type"] = obj.Shape.ShapeType
                obj_info["is_valid"] = obj.Shape.isValid()
            objects.append(obj_info)
        docs[name] = {"objects": objects, "file_name": doc.FileName}

    return {
        "documents": docs,
        "active_document": FreeCAD.ActiveDocument.Name if FreeCAD.ActiveDocument else None,
    }


def create_document(name: str) -> dict:
    """Create a new document."""
    doc = FreeCAD.newDocument(name)
    return {"name": doc.Name, "label": doc.Label}


def open_document(path: str) -> dict:
    """Open a document from file."""
    doc = FreeCAD.openDocument(path)
    return {"name": doc.Name, "label": doc.Label, "file_name": doc.FileName}


def save_document(name: str = None, path: str = None) -> dict:
    """Save a document. If path is given, save as."""
    doc = FreeCAD.getDocument(name) if name else FreeCAD.ActiveDocument
    if not doc:
        raise ValueError("No document to save")

    if path:
        doc.saveAs(path)
    else:
        doc.save()
    return {"name": doc.Name, "file_name": doc.FileName}


def close_document(name: str) -> dict:
    """Close a document."""
    FreeCAD.closeDocument(name)
    return {"closed": name}


def list_objects(doc_name: str = None) -> list:
    """List all objects in a document."""
    doc = FreeCAD.getDocument(doc_name) if doc_name else FreeCAD.ActiveDocument
    if not doc:
        raise ValueError("No active document")

    objects = []
    for obj in doc.Objects:
        info = {
            "name": obj.Name,
            "label": obj.Label,
            "type": obj.TypeId,
            "visibility": obj.ViewObject.Visibility if hasattr(obj, "ViewObject") and obj.ViewObject else None,
        }
        if hasattr(obj, "Shape") and obj.Shape and not obj.Shape.isNull():
            info["shape_type"] = obj.Shape.ShapeType
            bb = obj.Shape.BoundBox
            info["bounding_box"] = {
                "x_min": bb.XMin, "y_min": bb.YMin, "z_min": bb.ZMin,
                "x_max": bb.XMax, "y_max": bb.YMax, "z_max": bb.ZMax,
            }
        objects.append(info)
    return objects


def inspect_object(obj_name: str, doc_name: str = None) -> dict:
    """Get detailed information about an object."""
    doc = FreeCAD.getDocument(doc_name) if doc_name else FreeCAD.ActiveDocument
    if not doc:
        raise ValueError("No active document")

    obj = doc.getObject(obj_name)
    if not obj:
        raise ValueError(f"Object '{obj_name}' not found")

    info = {
        "name": obj.Name,
        "label": obj.Label,
        "type": obj.TypeId,
        "properties": {},
    }

    for prop in obj.PropertiesList:
        try:
            val = getattr(obj, prop)
            # Convert FreeCAD types to serializable values
            if hasattr(val, "x") and hasattr(val, "y") and hasattr(val, "z"):
                info["properties"][prop] = {"x": val.x, "y": val.y, "z": val.z}
            elif isinstance(val, (int, float, str, bool)):
                info["properties"][prop] = val
            else:
                info["properties"][prop] = str(val)
        except Exception:
            pass

    if hasattr(obj, "Shape") and obj.Shape and not obj.Shape.isNull():
        shape = obj.Shape
        info["shape"] = {
            "type": shape.ShapeType,
            "is_valid": shape.isValid(),
            "volume": shape.Volume if hasattr(shape, "Volume") else None,
            "area": shape.Area if hasattr(shape, "Area") else None,
            "num_faces": len(shape.Faces),
            "num_edges": len(shape.Edges),
            "num_vertices": len(shape.Vertexes),
        }

    return info


def delete_object(obj_name: str, doc_name: str = None) -> dict:
    """Delete an object from a document."""
    doc = FreeCAD.getDocument(doc_name) if doc_name else FreeCAD.ActiveDocument
    if not doc:
        raise ValueError("No active document")

    from freecad_ai_bridge.document_ops import _deletion_set

    targets = _deletion_set(doc.Name, [obj_name])
    if len(targets) != 1 or targets[0].Name != obj_name:
        raise BridgeError("dependency_conflict", "Use preview_delete/delete_objects to confirm dependent or owned objects",
                          [{"document": target.Document.Name, "object": target.Name} for target in targets])
    doc.removeObject(obj_name)
    return {"deleted": obj_name}
