"""Core FreeCAD operations callable from the RPC server.

These functions run on the GUI thread and have full access to FreeCAD/FreeCADGui.
"""

import json
from typing import Any

import FreeCAD
import FreeCADGui


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

    doc.removeObject(obj_name)
    return {"deleted": obj_name}
