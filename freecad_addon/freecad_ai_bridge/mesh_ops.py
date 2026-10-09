"""Bounded native mesh diagnostics, repair and conversion on the GUI executor."""

import math

import FreeCAD
import Mesh
import MeshPart
import Part

from freecad_ai_bridge.contracts import BridgeError
from freecad_ai_bridge.document_ops import _document, _object, _reference
from freecad_ai_bridge.geometry_ops import _shape


def _number(value, name, positive=True):
    if type(value) not in (int, float) or not math.isfinite(value) or (value <= 0 if positive else value < 0):
        raise BridgeError("invalid_arguments", f"{name} must be finite and {'positive' if positive else 'nonnegative'}")
    return float(value)


def _mesh(doc_name, obj_name):
    obj = _object(doc_name, obj_name)
    if not hasattr(obj, "Mesh") or not obj.Mesh.CountFacets:
        raise BridgeError("invalid_mesh", "A nonempty native Mesh object is required", [_reference(obj)])
    if obj.Mesh.CountFacets > 100000:
        raise BridgeError("mesh_limit", "At most 100000 facets are supported", [_reference(obj)])
    return obj


def _global_mesh(obj, mesh=None):
    result = (mesh if mesh is not None else obj.Mesh).copy()
    result.Placement = obj.getGlobalPlacement()
    return result


def _defects(mesh, area_tolerance):
    seen, duplicates, degenerate, edges = set(), [], [], {}
    for index, facet in enumerate(mesh.Facets):
        points = [tuple(point) for point in facet.Points]
        key = tuple(sorted(points))
        if key in seen:
            duplicates.append(index)
        seen.add(key)
        vectors = [FreeCAD.Vector(*point) for point in points]
        if (vectors[1] - vectors[0]).cross(vectors[2] - vectors[0]).Length / 2 <= area_tolerance:
            degenerate.append(index)
        for start, end in ((0, 1), (1, 2), (2, 0)):
            edge = tuple(sorted((points[start], points[end])))
            edges[edge] = edges.get(edge, 0) + 1
    return duplicates, degenerate, sum(count == 1 for count in edges.values()), sum(count > 2 for count in edges.values())


def _signed_volume(mesh):
    origin = mesh.BoundBox.Center
    return sum((FreeCAD.Vector(*facet.Points[0]) - origin).dot(
        (FreeCAD.Vector(*facet.Points[1]) - origin).cross(FreeCAD.Vector(*facet.Points[2]) - origin))
        for facet in mesh.Facets) / 6


def _stats(mesh, area_tolerance=1e-12):
    duplicates, degenerate, boundary, nonmanifold = _defects(mesh, area_tolerance)
    closed = mesh.isSolid()
    inconsistent = mesh.hasNonUniformOrientedFacets()
    box = mesh.BoundBox
    components = mesh.getSeparateComponents()
    orientations = ["outward" if _signed_volume(component) > 0 else "inward" for component in components if component.isSolid()]
    orientation = ("inconsistent" if inconsistent else "open" if not closed else
                   orientations[0] if len(set(orientations)) == 1 else "mixed")
    return {"facets": mesh.CountFacets, "points": mesh.CountPoints, "components": len(components),
            "closed": closed, "orientation": orientation, "area_mm2": mesh.Area,
            "volume_mm3": mesh.Volume if closed else None,
            "bbox_mm": {"min": [box.XMin, box.YMin, box.ZMin], "max": [box.XMax, box.YMax, box.ZMax]},
            "defects": {"duplicate_facets": len(duplicates), "degenerate_facets": len(degenerate),
                        "boundary_edges": boundary, "nonmanifold_edges": nonmanifold,
                        "nonmanifold": mesh.hasNonManifolds(), "inconsistent_normals": inconsistent,
                        "self_intersections": mesh.hasSelfIntersections(), "invalid_points": mesh.hasInvalidPoints()},
            "area_tolerance_mm2": area_tolerance}


def _store(document, mesh, name, warnings):
    if not mesh.CountFacets or mesh.CountFacets > 100000 or mesh.hasInvalidPoints():
        raise BridgeError("invalid_mesh", "Result must have 1..100000 facets with finite coordinates")
    obj = document.addObject("Mesh::Feature", name)
    obj.Mesh = mesh
    document.recompute()
    result = inspect_mesh(document.Name, obj.Name)
    result["warnings"] = warnings
    return result


def create_mesh(doc_name, facets, name="Mesh"):
    document = _document(doc_name)
    if not isinstance(facets, list) or not 1 <= len(facets) <= 100000:
        raise BridgeError("invalid_arguments", "facets requires 1..100000 triangles")
    for facet in facets:
        if not isinstance(facet, list) or len(facet) != 3:
            raise BridgeError("invalid_arguments", "Each facet requires three XYZ points")
        for point in facet:
            if not isinstance(point, list) or len(point) != 3 or any(type(value) not in (int, float) or not math.isfinite(value) for value in point):
                raise BridgeError("invalid_arguments", "XYZ coordinates must be finite numbers in mm")
    return _store(document, Mesh.Mesh(facets), name, ["Input facets may be defective; inspect or repair before solid conversion."])


def inspect_mesh(doc_name, obj_name, area_tolerance=1e-12):
    area_tolerance = _number(area_tolerance, "area_tolerance", False)
    obj = _mesh(doc_name, obj_name)
    return dict(_stats(_global_mesh(obj), area_tolerance), reference=_reference(obj), name=obj.Name,
                label=obj.Label, warnings=[], units="mm")


def from_shape(doc_name, obj_name, linear_deflection=0.1, angular_deflection=0.5, name="Mesh"):
    linear = _number(linear_deflection, "linear_deflection")
    angular = _number(angular_deflection, "angular_deflection")
    if angular > math.pi:
        raise BridgeError("invalid_arguments", "angular_deflection must not exceed pi radians")
    document = _document(doc_name)
    _, obj, shape = _shape(document.Name, obj_name)
    mesh = MeshPart.meshFromShape(Shape=shape, LinearDeflection=linear,
                                  AngularDeflection=angular, Relative=False)
    result = _store(document, mesh, name, ["Static triangulation; feature history and source dependencies are not retained."])
    result.update(source=_reference(obj), linear_deflection_mm=linear, angular_deflection_rad=angular, relative=False)
    return result


def repair_mesh(doc_name, obj_name, remove_duplicates=True, remove_degenerate=True,
                orient_normals=True, max_hole_edges=0, area_tolerance=1e-12, require_closed=False):
    area = _number(area_tolerance, "area_tolerance", False)
    if any(type(value) is not bool for value in (remove_duplicates, remove_degenerate, orient_normals, require_closed)):
        raise BridgeError("invalid_arguments", "Repair flags must be boolean")
    if type(max_hole_edges) is not int or not 0 <= max_hole_edges <= 10000:
        raise BridgeError("invalid_arguments", "max_hole_edges must be an integer in 0..10000; zero disables hole filling")
    obj = _mesh(doc_name, obj_name)
    mesh = obj.Mesh.copy()
    placement = mesh.Placement
    before = _stats(_global_mesh(obj, mesh), area)
    duplicate_indices, degenerate_indices, _, _ = _defects(mesh, area)
    indices = set(duplicate_indices if remove_duplicates else []) | set(degenerate_indices if remove_degenerate else [])
    if indices:
        mesh = Mesh.Mesh([facet.Points for index, facet in enumerate(mesh.Facets) if index not in indices])
    if not mesh.CountFacets or mesh.hasNonManifolds() or mesh.hasInvalidPoints() or mesh.hasSelfIntersections():
        raise BridgeError("mesh_not_repairable", "Empty, nonmanifold, invalid or self-intersecting mesh is outside bounded repair", [_reference(obj)], {"before": before})
    if orient_normals:
        mesh.harmonizeNormals()
        combined = Mesh.Mesh()
        for component in mesh.getSeparateComponents():
            if component.isSolid() and _signed_volume(component) < 0:
                component.flipNormals()
            combined.addMesh(component)
        mesh = combined
    if max_hole_edges:
        mesh.fillupHoles(max_hole_edges)
        if orient_normals:
            mesh.harmonizeNormals()
            if mesh.isSolid() and _signed_volume(mesh) < 0:
                mesh.flipNormals()
    mesh.Placement = placement
    after = _stats(_global_mesh(obj, mesh), area)
    if after["defects"]["nonmanifold"] or after["defects"]["self_intersections"] or (require_closed and not after["closed"]):
        raise BridgeError("mesh_not_repairable", "Requested bounded repair did not meet the target", [_reference(obj)], {"before": before, "after": after})
    obj.Mesh = mesh
    obj.Document.recompute()
    return {"reference": _reference(obj), "before": before, "after": after,
            "removed_facets": len(indices), "max_hole_edges": max_hole_edges,
            "area_tolerance_mm2": area, "warnings": ["No general healing, remeshing or self-intersection repair is promised."]}


def to_shape(doc_name, obj_name, target="solid", tolerance=0.01, name="MeshShape"):
    tolerance = _number(tolerance, "tolerance")
    if target not in {"shape", "solid"}:
        raise BridgeError("invalid_arguments", "target must be shape or solid")
    obj = _mesh(doc_name, obj_name)
    diagnostics = _stats(_global_mesh(obj))
    defects = diagnostics["defects"]
    if any(defects[key] for key in ("duplicate_facets", "degenerate_facets", "nonmanifold", "self_intersections", "invalid_points", "inconsistent_normals")):
        raise BridgeError("invalid_mesh", "Repair mesh defects before conversion", [_reference(obj)], diagnostics)
    if target == "solid" and (not diagnostics["closed"] or diagnostics["components"] != 1 or diagnostics["orientation"] != "outward"):
        raise BridgeError("mesh_not_solid", "Solid requires one closed outward-oriented component", [_reference(obj)], diagnostics)
    shape = Part.Shape()
    shape.makeShapeFromMesh(obj.Mesh.Topology, tolerance)
    if target == "solid":
        if len(shape.Shells) != 1 or not shape.Shells[0].isClosed():
            raise BridgeError("mesh_not_solid", "Native conversion did not produce one closed shell")
        shape = Part.makeSolid(shape.Shells[0])
    shape.Placement = obj.getGlobalPlacement().multiply(obj.Placement.inverse()).multiply(shape.Placement)
    if shape.isNull() or not shape.isValid() or (target == "solid" and (not shape.Solids or shape.Volume <= 0)):
        raise BridgeError("conversion_failed", "Native mesh conversion produced invalid geometry")
    result = obj.Document.addObject("Part::Feature", name)
    result.Shape = shape
    obj.Document.recompute()
    return {"reference": _reference(result), "name": result.Name, "source": _reference(obj),
            "shape_valid": True, "solids": len(shape.Solids), "volume_mm3": shape.Volume,
            "tolerance_mm": tolerance, "diagnostics": diagnostics,
            "warnings": ["Static faceted BRep; original curved surfaces and feature history cannot be reconstructed."]}