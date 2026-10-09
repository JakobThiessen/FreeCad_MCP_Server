"""Explicit, bounded exchange with atomic file publication and native parsers."""

from contextlib import contextmanager
import os
from pathlib import Path
import re
import tempfile
import xml.etree.ElementTree as ET

import FreeCAD
import Mesh
import MeshPart
import Part

from freecad_ai_bridge.contracts import BridgeError
from freecad_ai_bridge.document_ops import _document, _object, _reference
from freecad_ai_bridge.geometry_ops import _shape
from freecad_ai_bridge.mesh_ops import _global_mesh, _number, _stats


_SUFFIXES = {"step": {".step", ".stp"}, "stl": {".stl"}, "obj": {".obj"},
             "dxf": {".dxf"}, "svg": {".svg"}}


@contextmanager
def _settings(entries):
    previous = []
    try:
        for path, key, kind, value in entries:
            group = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/" + path)
            exists = any(entry[1] == key for entry in (group.GetContents() or []))
            old = getattr(group, "Get" + kind)(key)
            previous.append((group, key, kind, exists, old))
            getattr(group, "Set" + kind)(key, value)
        yield
    finally:
        for group, key, kind, exists, old in reversed(previous):
            if exists:
                getattr(group, "Set" + kind)(key, old)
            else:
                getattr(group, "Rem" + kind)(key)


def _path(path, format, writing=False):
    if format not in _SUFFIXES or not isinstance(path, str):
        raise BridgeError("invalid_arguments", "Explicit supported format and absolute path required")
    target = Path(path)
    if not target.is_absolute() or target.suffix.lower() not in _SUFFIXES[format]:
        raise BridgeError("invalid_arguments", "Absolute path must match explicit format")
    if writing:
        if not target.parent.is_dir() or (target.exists() and not target.is_file()):
            raise BridgeError("invalid_arguments", "Existing parent and regular output file required")
    elif not target.is_file() or not 0 < target.stat().st_size <= 64 * 1024 * 1024:
        raise BridgeError("invalid_arguments", "Input must be a nonempty regular file of at most 64 MiB")
    return target.resolve()


def _options(options):
    if not isinstance(options, dict):
        raise BridgeError("invalid_arguments", "Structured format options required")
    format = options.get("format")
    allowed = {"step": {"format", "step_schema"}, "stl": {"format", "encoding", "linear_deflection", "angular_deflection"},
               "obj": {"format", "linear_deflection", "angular_deflection"}, "dxf": {"format"}, "svg": {"format"}}
    if format not in allowed or set(options) - allowed[format]:
        raise BridgeError("invalid_arguments", "Unsupported format option")
    result = dict(options)
    if format == "step" and result.get("step_schema") not in {"AP214", "AP242"}:
        raise BridgeError("invalid_arguments", "STEP requires explicit AP214 or AP242")
    if format == "stl" and result.get("encoding") not in {"ascii", "binary"}:
        raise BridgeError("invalid_arguments", "STL requires explicit ascii or binary encoding")
    if format in {"stl", "obj"}:
        result["linear_deflection"] = _number(result.get("linear_deflection", 0.1), "linear_deflection")
        result["angular_deflection"] = _number(result.get("angular_deflection", 0.5), "angular_deflection")
        if result["angular_deflection"] > 3.141592653589793:
            raise BridgeError("invalid_arguments", "Angular deflection must be at most pi radians")
    return result


def _circular_radius(edge):
    curve = edge.Curve
    if isinstance(curve, Part.Circle):
        return curve.Radius
    if isinstance(curve, Part.Ellipse) and abs(curve.MajorRadius - curve.MinorRadius) <= 1e-7:
        return curve.MajorRadius
    return None


def _planar(shape):
    if shape.Solids or shape.Faces or abs(shape.BoundBox.ZMin) > 1e-7 or abs(shape.BoundBox.ZMax) > 1e-7:
        raise BridgeError("unsupported_geometry", "DXF/SVG require wire geometry in document XY at Z=0")
    if not shape.Edges or any(not isinstance(edge.Curve, Part.Line) and _circular_radius(edge) is None for edge in shape.Edges):
        raise BridgeError("unsupported_geometry", "Only planar lines, polylines, circles and circular arcs are supported",
                          diagnostics={"edges": len(shape.Edges), "curves": [type(edge.Curve).__name__ for edge in shape.Edges]})


def _objects(document, objects):
    result = []
    for obj in objects:
        if obj.TypeId == "App::Part":
            result.append({"reference": _reference(obj), "label": obj.Label, "type": obj.TypeId,
                           "children": [_reference(child) for child in obj.Group if child.TypeId == "App::Part" or child.isDerivedFrom("Part::Feature")]})
        elif obj.isDerivedFrom("Part::Feature"):
            shape = _shape(document.Name, obj.Name)[2]
            box = shape.optimalBoundingBox(False, False)
            result.append({"reference": _reference(obj), "label": obj.Label, "type": obj.TypeId,
                           "volume_mm3": shape.Volume, "solids": len(shape.Solids), "length_mm": shape.Length,
                           "bbox_mm": {"min": [box.XMin, box.YMin, box.ZMin], "max": [box.XMax, box.YMax, box.ZMax]},
                           "color": list(obj.ViewObject.ShapeColor),
                           "closed_wires": sum(wire.isClosed() for wire in shape.Wires) +
                           sum(edge.isClosed() and not any(edge.isSame(member) for wire in shape.Wires for member in wire.Edges) for edge in shape.Edges),
                           "curves": [{"type": "circle" if _circular_radius(edge) is not None else "line" if isinstance(edge.Curve, Part.Line) else type(edge.Curve).__name__,
                                       "radius_mm": _circular_radius(edge),
                                       "closed": edge.isClosed(), "length_mm": edge.Length} for edge in shape.Edges]})
        elif hasattr(obj, "Mesh"):
            if obj.Mesh.CountFacets > 100000:
                raise BridgeError("mesh_limit", "At most 100000 facets are supported")
            result.append(dict(_stats(obj.Mesh), reference=_reference(obj), label=obj.Label, type=obj.TypeId))
    return result


@contextmanager
def _proxies(document, objects, format):
    proxy = FreeCAD.newDocument("MCP_Exchange", hidden=True, temp=True)
    try:
        def copy(source, parent=None):
            if source.TypeId in {"App::Part", "App::DocumentObjectGroup"}:
                target = proxy.addObject("App::Part", source.Name)
                target.Label = source.Label
                if parent:
                    parent.addObject(target)
                for child in source.Group:
                    if child.TypeId != "App::Origin":
                        copy(child, target)
            else:
                shape = _shape(document.Name, source.Name)[2]
                if format in {"dxf", "svg"}:
                    _planar(shape)
                target = proxy.addObject("Part::Feature", source.Name)
                target.Label = source.Label
                target.Shape = shape
                color_source = source.getLinkedObject(True) if source.TypeId == "App::Link" else source
                if hasattr(color_source.ViewObject, "ShapeColor"):
                    target.ViewObject.ShapeColor = color_source.ViewObject.ShapeColor
                if parent:
                    parent.addObject(target)
            return target

        roots = [copy(obj) for obj in objects]
        proxy.recompute()
        yield roots
    finally:
        FreeCAD.closeDocument(proxy.Name)


def export_model(doc_name, obj_names, path, options, overwrite=False):
    import Import
    import ImportGui
    import importSVG

    document = _document(doc_name)
    options = _options(options)
    format = options["format"]
    target = _path(path, format, True)
    if type(overwrite) is not bool or not isinstance(obj_names, list) or not 1 <= len(obj_names) <= 100:
        raise BridgeError("invalid_arguments", "Explicit 1..100 object Names and boolean overwrite required")
    if len(set(obj_names)) != len(obj_names):
        raise BridgeError("invalid_arguments", "Duplicate selections are not supported")
    objects = [_object(doc_name, name) for name in obj_names]
    for obj in objects:
        if any(parent.Name in obj_names for parent in obj.InList if hasattr(parent, "Group") and obj in parent.Group):
            raise BridgeError("invalid_arguments", "Do not select both a container and its children")
    if target.exists() and not overwrite:
        raise BridgeError("file_exists", "Existing output requires overwrite=true")
    warnings = ["Static exchange; feature history, expressions, constraints and joints are not retained."]
    with tempfile.TemporaryDirectory(prefix="freecad-exchange-", dir=target.parent) as directory:
        staged = Path(directory) / ("model" + target.suffix)
        if format in {"stl", "obj"}:
            mesh = Mesh.Mesh()
            for obj in objects:
                if hasattr(obj, "Mesh"):
                    part_mesh = _global_mesh(obj)
                else:
                    shape = _shape(doc_name, obj.Name)[2]
                    part_mesh = MeshPart.meshFromShape(Shape=shape, LinearDeflection=options["linear_deflection"],
                        AngularDeflection=options["angular_deflection"], Relative=False)
                points, triangles = part_mesh.Topology
                mesh.addMesh(Mesh.Mesh([tuple(tuple(points[index]) for index in triangle) for triangle in triangles]))
            if not 1 <= mesh.CountFacets <= 100000:
                raise BridgeError("mesh_limit", "Export requires 1..100000 facets")
            mesh.write(str(staged), "OBJ" if format == "obj" else "AST" if options["encoding"] == "ascii" else "STL")
            warnings.append("mm convention only: mesh format has no reliable units; colors, hierarchy and materials are not retained.")
        else:
            with _proxies(document, objects, format) as roots:
                if format == "step":
                    with _settings([("Part/STEP", "Scheme", "String", options["step_schema"] + ("IS" if options["step_schema"] == "AP214" else "DIS")),
                                    ("Part/STEP", "Unit", "Int", 0)]):
                        ImportGui.export(roots, str(staged), exportHidden=False, legacy=False, keepPlacement=True)
                    header = staged.read_text(errors="strict").split("ENDSEC;", 1)[0]
                    expected = "AUTOMOTIVE_DESIGN" if options["step_schema"] == "AP214" else "AP242_MANAGED_MODEL_BASED_3D_ENGINEERING"
                    if not re.search(r"FILE_SCHEMA\s*\(.*" + expected, header, re.DOTALL):
                        raise BridgeError("unsupported_feature", "Native exporter did not honor requested STEP schema")
                    warnings.append("Linked components become static labeled colored components; external link identity is not retained.")
                elif format == "dxf":
                    Import.writeDXFObject(roots, str(staged), 14, True)
                else:
                    importSVG.export(roots, str(staged))
                    tree = ET.parse(staged)
                    root = tree.getroot()
                    boxes = [obj.Shape.BoundBox for obj in roots[0].Document.Objects if obj.isDerivedFrom("Part::Feature")]
                    minimum_x = min(box.XMin for box in boxes)
                    minimum_y = min(box.YMin for box in boxes)
                    maximum_x = max(box.XMax for box in boxes)
                    maximum_y = max(box.YMax for box in boxes)
                    width = max(maximum_x - minimum_x, 1.0)
                    height = max(maximum_y - minimum_y, 1.0)
                    root.set("width", str(width) + "mm")
                    root.set("height", str(height) + "mm")
                    root.set("viewBox", f"{minimum_x} {-maximum_y} {width} {height}")
                    for group in root:
                        if group.tag == "{http://www.w3.org/2000/svg}g":
                            group.set("transform", "scale(1,-1)")
                    ET.register_namespace("", "http://www.w3.org/2000/svg")
                    tree.write(staged, encoding="utf-8", xml_declaration=True)
        if not staged.is_file() or not staged.stat().st_size:
            raise BridgeError("file_write_failed", "Native exporter produced no file")
        try:
            if overwrite:
                os.replace(staged, target)
            else:
                os.link(staged, target)
        except FileExistsError as error:
            raise BridgeError("file_exists", "Output appeared during export; not overwritten") from error
    return {"references": [_reference(obj) for obj in objects], "file_name": str(target), "format": format,
            "options": options, "units": "mm", "bytes": target.stat().st_size, "warnings": warnings}


def import_model(doc_name, path, format, units="mm"):
    import Import
    import ImportGui
    import importSVG

    document = _document(doc_name)
    path = _path(path, format)
    if units != "mm":
        raise BridgeError("invalid_arguments", "Only explicit mm imports are supported")
    original = {obj.Name for obj in document.Objects}
    if format == "step":
        ImportGui.insert(str(path), document.Name, importHidden=False, merge=False, useLinkGroup=False)
    elif format in {"stl", "obj"}:
        mesh = Mesh.Mesh(str(path))
        if not mesh.CountFacets or mesh.CountFacets > 100000 or mesh.hasInvalidPoints():
            raise BridgeError("invalid_mesh", "Imported mesh requires 1..100000 finite facets")
        obj = document.addObject("Mesh::Feature", path.stem)
        obj.Mesh = mesh
    elif format == "dxf":
        Import.readDXF(str(path), document.Name, False)
        imported_shapes = [obj for obj in document.Objects if obj.Name not in original and hasattr(obj, "Shape")]
        edges = []
        for obj in imported_shapes:
            shape = _shape(document.Name, obj.Name)[2]
            _planar(shape)
            edges.extend(shape.Edges)
        for edge_group in Part.sortEdges(edges):
            wire = Part.Wire(edge_group)
            if not wire.isValid():
                raise BridgeError("invalid_geometry", "DXF edges cannot form valid unbranched planar wires.")
            obj = document.addObject("Part::Feature", "DXFWire")
            obj.Shape = wire
        for obj in imported_shapes:
            document.removeObject(obj.Name)
    else:
        ET.parse(path)
        importSVG.insert(str(path), document.Name)
    document.recompute()
    created = [obj for obj in document.Objects if obj.Name not in original]
    if len(created) > 1000:
        raise BridgeError("exchange_limit", "Import exceeds 1000 objects")
    geometries = [obj for obj in created if obj.isDerivedFrom("Part::Feature") or hasattr(obj, "Mesh")]
    if not geometries:
        raise BridgeError("empty_import", "No supported geometry imported")
    if format in {"dxf", "svg"}:
        for obj in geometries:
            _planar(_shape(doc_name, obj.Name)[2])
    result = _objects(document, created)
    return {"references": [_reference(obj) for obj in geometries], "objects": result, "format": format,
            "file_name": str(path), "units": "mm", "warnings": ["Static imported geometry; feature history and source dependencies are not reconstructed."] +
            (["mm is an explicit assumption; mesh format does not carry reliable units or structure."] if format in {"stl", "obj"} else []) +
            (["Connected DXF edges are rebuilt as static wires; original entity segmentation and labels are not preserved."] if format == "dxf" else [])}