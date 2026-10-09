"""Structured native drawing operations, executed only by the GUI executor."""

from pathlib import Path
import json
import math
import os
import tempfile
import xml.etree.ElementTree as ET

import FreeCAD
import Part

from freecad_ai_bridge.contracts import BridgeError
from freecad_ai_bridge.document_ops import _document, _object, _reference


def _number(value, label, positive=False):
    if type(value) not in (int, float) or not math.isfinite(value) or (positive and value <= 0):
        raise BridgeError("invalid_arguments", f"{label} must be a finite {'positive ' if positive else ''}number")
    return float(value)


def _vector(value):
    if not isinstance(value, list) or len(value) != 3:
        raise BridgeError("invalid_arguments", "direction must have three finite components")
    vector = FreeCAD.Vector(*[_number(component, "direction") for component in value])
    if vector.Length < 1e-12:
        raise BridgeError("invalid_arguments", "direction must be nonzero")
    return vector


def _typed(doc_name, name, kind):
    obj = _object(doc_name, name)
    if obj.TypeId != kind:
        raise BridgeError("invalid_arguments", f"Expected {kind}", [_reference(obj)])
    return obj


def _paper(page):
    if page.Template is None:
        raise BridgeError("invalid_template", "Page has no template", [_reference(page)])
    return [float(page.Template.Width), float(page.Template.Height)]


def _position(page, x, y):
    width, height = _paper(page)
    x, y = _number(x, "x"), _number(y, "y")
    if not 0 <= x <= width or not 0 <= y <= height:
        raise BridgeError("invalid_arguments", "View center must lie inside the paper in mm")
    return x, y


def _finish_projection():
    try:
        from PySide6.QtCore import QCoreApplication, QEventLoop, QThreadPool
    except ImportError:
        from PySide2.QtCore import QCoreApplication, QEventLoop, QThreadPool
    for phase in range(2):
        if not QThreadPool.globalInstance().waitForDone(10000):
            raise BridgeError("drawing_not_ready", "Native projection jobs did not finish within the 10a wait budget")
        QCoreApplication.processEvents(QEventLoop.ExcludeUserInputEvents)


def list_templates() -> dict:
    directory = Path(FreeCAD.getResourceDir()) / "Mod" / "TechDraw" / "Templates"
    return {"templates": [path.relative_to(directory).as_posix() for path in sorted(directory.rglob("*.svg"))],
            "directory": str(directory), "custom_templates": "absolute SVG paths only; trusted files"}


def _template_path(template):
    if not isinstance(template, str) or not template.strip():
        raise BridgeError("invalid_arguments", "A named SVG template or absolute SVG path is required")
    path = Path(template)
    if not path.is_absolute():
        directory = (Path(FreeCAD.getResourceDir()) / "Mod" / "TechDraw" / "Templates").resolve()
        path = (directory / path).resolve()
        if not path.is_relative_to(directory):
            raise BridgeError("invalid_arguments", "Named template must stay inside the built-in template directory")
    if path.suffix.lower() != ".svg" or not path.is_file():
        raise BridgeError("template_not_found", f"SVG template not found: {path}")
    try:
        root = ET.parse(path).getroot()
        if root.tag != "{http://www.w3.org/2000/svg}svg":
            raise ValueError("Expected an SVG root")
        dimensions = [float(root.attrib[key][:-2]) for key in ("width", "height")
                      if root.attrib[key].endswith("mm")]
        if len(dimensions) != 2:
            raise ValueError("SVG width and height must use explicit mm units")
        if any(not 0 < dimension <= 2000 for dimension in dimensions):
            raise ValueError("Invalid paper dimensions")
    except (ET.ParseError, ValueError, KeyError) as error:
        raise BridgeError("invalid_template", f"Invalid SVG template: {error}") from error
    return path.resolve(), dimensions


def create_page(doc_name: str, template: str, name: str = "Page") -> dict:
    document = _document(doc_name)
    path, dimensions = _template_path(template)
    if not isinstance(name, str) or not name.strip() or len(name) > 128:
        raise BridgeError("invalid_arguments", "A page Name of 1..128 characters is required")
    page = document.addObject("TechDraw::DrawPage", name)
    svg = document.addObject("TechDraw::DrawSVGTemplate", name + "Template")
    svg.Template = str(path)
    page.Template = svg
    page.Scale = 1.0
    document.recompute()
    return {"reference": _reference(page), "name": page.Name, "template": _reference(svg),
            "template_path": str(path), "paper_mm": dimensions, "scale": float(page.Scale),
            "editable_texts": dict(svg.EditableTexts)}


def create_view(doc_name: str, page_name: str, source_names: list, direction: list,
                x: float, y: float, scale: float = 1.0, name: str = "View") -> dict:
    page = _typed(doc_name, page_name, "TechDraw::DrawPage")
    if not isinstance(source_names, list) or not 1 <= len(source_names) <= 32 or any(
            not isinstance(source, str) or not source.strip() for source in source_names) or len(set(source_names)) != len(source_names):
        raise BridgeError("invalid_arguments", "source_names must contain 1..32 unique object Names")
    sources = [_object(doc_name, source) for source in source_names]
    for source in sources:
        if not hasattr(source, "Shape") or source.Shape.isNull() or not source.Shape.isValid():
            raise BridgeError("invalid_geometry", "Drawing source needs a valid nonempty Shape", [_reference(source)])
        if any(state in source.State for state in ("Touched", "Invalid")):
            raise BridgeError("geometry_not_ready", "Recompute the source first", [_reference(source)])
    direction = _vector(direction)
    x, y = _position(page, x, y)
    scale = _number(scale, "scale", positive=True)
    if not isinstance(name, str) or not name.strip() or len(name) > 128:
        raise BridgeError("invalid_arguments", "A view Name of 1..128 characters is required")
    view = page.Document.addObject("TechDraw::DrawViewPart", name)
    view.Source = sources
    view.Direction = direction
    view.ScaleType = "Custom"
    view.Scale = scale
    view.addProperty("App::PropertyStringList", "MCPSourceNames", "MCP")
    view.MCPSourceNames = source_names
    view.setEditorMode("MCPSourceNames", 1)
    page.addView(view)
    view.X, view.Y = x, y
    page.Document.recompute()
    _finish_projection()
    _validate_page(page)
    return _view_data(view)


def _validate_page(page):
    _paper(page)
    for view in _model_views(page):
        if "MCPSourceNames" not in view.PropertiesList:
            raise BridgeError("unsupported_feature", "View has no structured source provenance", [_reference(view)])
        expected = list(view.MCPSourceNames)
        if not expected or [source.Name for source in view.Source] != expected:
            raise BridgeError("drawing_reference_lost", "Drawing source reference was removed or changed", [_reference(view)])
        for source in view.Source:
            if source.Shape.isNull() or not source.Shape.isValid() or "Invalid" in source.State:
                raise BridgeError("drawing_reference_lost", "Drawing source is invalid", [_reference(source)])
            if "Touched" in source.State:
                raise BridgeError("geometry_not_ready", "Drawing source needs recompute", [_reference(source)])
        if "Invalid" in view.State or "Touched" in view.State:
            raise BridgeError("drawing_not_ready", "Drawing view needs a successful update", [_reference(view)])
        if not view.getVisibleEdges():
            raise BridgeError("drawing_not_ready", "Drawing view contains no visible projected edges", [_reference(view)])
    for item in page.Views:
        if item.TypeId == "TechDraw::DrawViewDimension":
            _validate_dimension(item)
        if item.TypeId in {"TechDraw::DrawViewSection", "TechDraw::DrawViewDetail"}:
            if item.BaseView is None or item.BaseView.Name != item.MCPBaseViewName:
                raise BridgeError("drawing_reference_lost", "Base view was removed or replaced", [_reference(item)])
        if item.TypeId == "TechDraw::DrawLeaderLine":
            if ("MCPParentViewName" not in item.PropertiesList or item.LeaderParent is None or
                    item.LeaderParent not in _model_views(page) or item.LeaderParent.Name != item.MCPParentViewName):
                raise BridgeError("drawing_reference_lost", "Leader parent was removed or changed", [_reference(item)])


def _model_views(page):
    views = []
    for item in page.Views:
        if item.TypeId == "TechDraw::DrawProjGroup":
            views.extend(item.Views)
        elif item.isDerivedFrom("TechDraw::DrawViewPart"):
            views.append(item)
        elif item.TypeId in {"TechDraw::DrawViewDimension", "TechDraw::DrawViewAnnotation", "TechDraw::DrawLeaderLine"}:
            continue
        else:
            raise BridgeError("unsupported_feature", "Unsupported drawing object", [_reference(item)])
    return views


def _provenance(view, sources):
    view.addProperty("App::PropertyStringList", "MCPSourceNames", "MCP")
    view.MCPSourceNames = [source.Name for source in sources]
    view.setEditorMode("MCPSourceNames", 1)


def _page_view(page, name):
    view = _object(page.Document.Name, name)
    if view not in _model_views(page):
        raise BridgeError("invalid_reference", "Model view does not belong to the page", [_reference(view)])
    return view


def _paper_position(view):
    x, y = float(view.X), float(view.Y)
    if view.TypeId == "TechDraw::DrawProjGroupItem":
        group = next(parent for parent in view.InList if parent.TypeId == "TechDraw::DrawProjGroup")
        x, y = x + float(group.X), y + float(group.Y)
    elif view.TypeId == "TechDraw::DrawViewDimension" and view.References2D:
        parent_x, parent_y = _paper_position(view.References2D[0][0])
        x, y = x + parent_x, y + parent_y
    return x, y


def _set_paper_position(view, x, y):
    old_x, old_y = _paper_position(view)
    view.X = float(view.X) + x - old_x
    view.Y = float(view.Y) + y - old_y


def create_projection_group(doc_name: str, page_name: str, source_names: list, direction: list,
                            x: float, y: float, scale: float = 1.0, name: str = "ProjectionGroup") -> dict:
    page = _typed(doc_name, page_name, "TechDraw::DrawPage")
    seed = create_view(doc_name, page_name, source_names, direction, x, y, scale, name + "Seed")
    sources = list(page.Document.getObject(seed["name"]).Source)
    page.Document.removeObject(seed["name"])
    group = page.Document.addObject("TechDraw::DrawProjGroup", name)
    group.Source = sources
    group.ScaleType, group.Scale = "Custom", scale
    page.addView(group)
    group.X, group.Y = x, y
    front = group.addProjection("Front")
    front.Direction = _vector(direction)
    _provenance(front, sources)
    for projection in ("Top", "Right"):
        item = group.addProjection(projection)
        _provenance(item, sources)
    page.Document.recompute()
    _finish_projection()
    _validate_page(page)
    return {"reference": _reference(group), "name": group.Name,
            "views": [_view_data(item) for item in group.Views]}


def create_section(doc_name: str, page_name: str, base_view: str, origin: list, normal: list,
                   x: float, y: float, scale: float = 1.0, name: str = "Section") -> dict:
    page = _typed(doc_name, page_name, "TechDraw::DrawPage")
    _validate_page(page)
    base = _page_view(page, base_view)
    normal = _vector(normal)
    if abs(normal.normalize().dot(base.Direction.normalize())) > 1e-7:
        raise BridgeError("invalid_arguments", "Orthogonal section normal must be perpendicular to the base viewing direction")
    if not isinstance(origin, list) or len(origin) != 3:
        raise BridgeError("invalid_arguments", "origin requires three document-global mm coordinates")
    origin = FreeCAD.Vector(*[_number(component, "origin") for component in origin])
    x, y = _position(page, x, y)
    scale = _number(scale, "scale", positive=True)
    section = page.Document.addObject("TechDraw::DrawViewSection", name)
    section.BaseView, section.Source = base, base.Source
    section.SectionOrigin, section.SectionNormal = origin, normal
    section.Direction = normal
    section.SectionSymbol = "A"
    section.ScaleType, section.Scale = "Custom", scale
    _provenance(section, base.Source)
    section.addProperty("App::PropertyString", "MCPBaseViewName", "MCP")
    section.MCPBaseViewName = base.Name
    section.setEditorMode("MCPBaseViewName", 1)
    page.addView(section)
    section.X, section.Y = x, y
    page.Document.recompute()
    _finish_projection()
    _validate_page(page)
    return _view_data(section)


def create_detail(doc_name: str, page_name: str, base_view: str, anchor: list, radius: float,
                  x: float, y: float, scale: float = 2.0, name: str = "Detail") -> dict:
    page = _typed(doc_name, page_name, "TechDraw::DrawPage")
    _validate_page(page)
    base = _page_view(page, base_view)
    if not isinstance(anchor, list) or len(anchor) != 2:
        raise BridgeError("invalid_arguments", "anchor requires two unscaled base-view coordinates in mm")
    anchor = FreeCAD.Vector(*[_number(component, "anchor") for component in anchor], 0)
    radius = _number(radius, "radius", positive=True)
    scale = _number(scale, "scale", positive=True)
    x, y = _position(page, x, y)
    detail = page.Document.addObject("TechDraw::DrawViewDetail", name)
    detail.BaseView, detail.Source = base, base.Source
    detail.AnchorPoint, detail.Radius = anchor, radius
    detail.ScaleType, detail.Scale = "Custom", scale
    _provenance(detail, base.Source)
    detail.addProperty("App::PropertyString", "MCPBaseViewName", "MCP")
    detail.MCPBaseViewName = base.Name
    detail.setEditorMode("MCPBaseViewName", 1)
    page.addView(detail)
    detail.X, detail.Y = x, y
    page.Document.recompute()
    _finish_projection()
    _validate_page(page)
    return _view_data(detail)


def _topology(view):
    edges = [view.getEdgeByIndex(index) for index in range(len(view.getVisibleEdges()) + len(view.getHiddenEdges()))]
    vertices = [view.getVertexByIndex(index).Point for index in
                range(len(view.getVisibleVertexes()) + len(view.getHiddenVertexes()))]
    points = vertices + [vertex.Point for edge in edges for vertex in edge.Vertexes]
    points.extend(edge.Curve.Center for edge in edges if hasattr(edge.Curve, "Radius"))
    axes = [sorted({round(point[axis], 6) for point in points}) for axis in (0, 1)]
    radii = sorted({round(edge.Curve.Radius, 6) for edge in edges if hasattr(edge.Curve, "Radius")})

    def ranked(point):
        return [axes[axis].index(round(point[axis], 6)) for axis in (0, 1)]

    signatures = []
    for edge in edges:
        signature = [type(edge.Curve).__name__, bool(edge.isClosed()), sorted(ranked(vertex.Point) for vertex in edge.Vertexes)]
        if hasattr(edge.Curve, "Radius"):
            signature.extend([ranked(edge.Curve.Center), radii.index(round(edge.Curve.Radius, 6))])
        signatures.append(signature)
    return json.dumps({"edges": signatures, "vertices": [ranked(point) for point in vertices]})


def list_geometry(doc_name: str, page_name: str, view_name: str) -> dict:
    from freecad_ai_bridge.geometry_ops import _revisions

    page = _typed(doc_name, page_name, "TechDraw::DrawPage")
    _validate_page(page)
    view = _page_view(page, view_name)
    revision = _revisions.token(page.Document)
    edges = []
    count = len(view.getVisibleEdges()) + len(view.getHiddenEdges())
    if count > 4096:
        raise BridgeError("unsupported_feature", "Projected geometry query is limited to 4096 edges")
    for index in range(count):
        edge = view.getEdgeByIndex(index)
        curve = edge.Curve
        item = {"selection": dict(document=doc_name, object=view.Name, revision=revision,
                                  subelement="Edge" + str(index)),
                "curve": type(curve).__name__, "length_mm": edge.Length,
                "points_mm": [list(vertex.Point) for vertex in edge.Vertexes]}
        if hasattr(curve, "Radius"):
            item.update(radius_mm=curve.Radius, center_mm=list(curve.Center))
        edges.append(item)
    vertices = [{"selection": dict(document=doc_name, object=view.Name, revision=revision,
                                   subelement="Vertex" + str(index)),
                 "point_mm": list(view.getVertexByIndex(index).Point)}
                for index in range(len(view.getVisibleVertexes()) + len(view.getHiddenVertexes()))]
    return {"reference": _reference(view), "revision": revision, "edges": edges, "vertices": vertices,
            "coordinates": "unscaled view XY in mm; origin at projection center"}


def _drawing_selection(page, selection):
    from freecad_ai_bridge.geometry_ops import _revisions

    if not isinstance(selection, dict) or set(selection) != {"document", "object", "revision", "subelement"}:
        raise BridgeError("invalid_arguments", "Expected a complete projected geometry selection")
    if selection["document"] != page.Document.Name:
        raise BridgeError("invalid_reference", "Selection belongs to another document")
    if selection["revision"] != _revisions.token(page.Document):
        raise BridgeError("stale_selection", "Projected selection is stale; query geometry again")
    view = _page_view(page, selection["object"])
    subelement = selection["subelement"]
    try:
        if subelement.startswith("Edge"):
            geometry = view.getEdgeBySelection(subelement)
            if geometry.isNull():
                raise ValueError("Null edge")
        elif subelement.startswith("Vertex"):
            geometry = view.getVertexBySelection(subelement)
        else:
            raise ValueError("Expected Edge or Vertex")
    except Exception as error:
        raise BridgeError("invalid_reference", "Projected subelement does not exist") from error
    return view, subelement, geometry


def _validate_dimension(dimension):
    if "MCPDimensionReferences" not in dimension.PropertiesList:
        raise BridgeError("unsupported_feature", "Dimension has no structured reference provenance")
    expected = json.loads(dimension.MCPDimensionReferences)
    actual = [[view.Name, list(names)] for view, names in dimension.References2D]
    if (actual != expected or dimension.Arbitrary or "MCPDimensionType" not in dimension.PropertiesList or
            dimension.Type != dimension.MCPDimensionType or dimension.MeasureType != "Projected"):
        raise BridgeError("drawing_reference_lost", "Dimension references or measurement mode were changed", [_reference(dimension)])
    for view, names in dimension.References2D:
        if _topology(view) != dimension.MCPTopology:
            raise BridgeError("drawing_reference_stale", "Projected topology changed; recreate the dimension explicitly", [_reference(dimension)])
        for name in names:
            if name.startswith("Edge") and view.getEdgeBySelection(name).isNull():
                raise BridgeError("drawing_reference_lost", "Dimension edge no longer exists", [_reference(dimension)])
            if name.startswith("Vertex"):
                view.getVertexBySelection(name)
    if "Invalid" in dimension.State or not math.isfinite(float(dimension.getRawValue())):
        raise BridgeError("drawing_not_ready", "Native dimension is invalid", [_reference(dimension)])


def _dimension_data(dimension):
    return {"reference": _reference(dimension), "name": dimension.Name, "type": dimension.Type,
            "value": float(dimension.getRawValue()), "unit": "deg" if dimension.Type == "Angle" else "mm",
            "model_bound": not dimension.Arbitrary,
            "references_2d": [[_reference(view), list(names)] for view, names in dimension.References2D],
            "position_mm": list(_paper_position(dimension))}


def create_dimension(doc_name: str, page_name: str, kind: str, selections: list,
                     x: float, y: float, name: str = "Dimension") -> dict:
    page = _typed(doc_name, page_name, "TechDraw::DrawPage")
    _validate_page(page)
    kinds = {"length": "Distance", "distance": "Distance", "distance_x": "DistanceX",
             "distance_y": "DistanceY", "diameter": "Diameter", "radius": "Radius", "angle": "Angle"}
    if kind not in kinds or not isinstance(selections, list) or not 1 <= len(selections) <= 2:
        raise BridgeError("invalid_arguments", "Unsupported dimension kind or selection count")
    resolved = [_drawing_selection(page, selection) for selection in selections]
    base = resolved[0][0]
    if any(view is not base for view, subelement, geometry in resolved):
        raise BridgeError("invalid_arguments", "Dimension selections must belong to one view")
    if kind in {"diameter", "radius"}:
        if len(resolved) != 1 or not hasattr(getattr(resolved[0][2], "Curve", None), "Radius"):
            raise BridgeError("invalid_arguments", "Diameter/radius requires one circular edge")
    if kind == "angle" and (len(resolved) != 2 or any(
            len(geometry.Vertexes) != 2 or abs(geometry.Length -
                (geometry.Vertexes[1].Point - geometry.Vertexes[0].Point).Length) > 1e-7
            for view, subelement, geometry in resolved)):
        raise BridgeError("invalid_arguments", "Angle requires two straight edges")
    x, y = _position(page, x, y)
    dimension = page.Document.addObject("TechDraw::DrawViewDimension", name)
    dimension.Type = kinds[kind]
    dimension.MeasureType = "Projected"
    dimension.References2D = [(base, [subelement for view, subelement, geometry in resolved])]
    dimension.Arbitrary = False
    dimension.FormatSpec = {"diameter": "\u2300%.2f", "radius": "R%.2f", "angle": "%.2f\u00b0"}.get(kind, "%.2f")
    dimension.ViewObject.Fontsize = 3.0
    for property_name, value in (("MCPDimensionReferences", json.dumps([[base.Name, [item[1] for item in resolved]]])),
                                 ("MCPDimensionType", kinds[kind]),
                                 ("MCPTopology", _topology(base))):
        dimension.addProperty("App::PropertyString", property_name, "MCP")
        setattr(dimension, property_name, value)
        dimension.setEditorMode(property_name, 1)
    page.addView(dimension)
    _set_paper_position(dimension, x, y)
    page.Document.recompute()
    _finish_projection()
    _validate_page(page)
    return _dimension_data(dimension)


def create_annotation(doc_name: str, page_name: str, text: list, x: float, y: float,
                      size: float = 3.5, name: str = "Annotation") -> dict:
    page = _typed(doc_name, page_name, "TechDraw::DrawPage")
    _validate_page(page)
    if not isinstance(text, list) or not 1 <= len(text) <= 32 or any(
            not isinstance(line, str) or not line.strip() or len(line) > 4096 for line in text):
        raise BridgeError("invalid_arguments", "text needs 1..32 nonempty lines of at most 4096 characters")
    x, y = _position(page, x, y)
    size = _number(size, "size", positive=True)
    annotation = page.Document.addObject("TechDraw::DrawViewAnnotation", name)
    annotation.Text, annotation.TextSize = text, size
    page.addView(annotation)
    annotation.X, annotation.Y = x, y
    page.Document.recompute()
    return {"reference": _reference(annotation), "name": annotation.Name, "text": list(annotation.Text)}


def create_leader(doc_name: str, page_name: str, view_name: str, points: list, name: str = "Leader") -> dict:
    page = _typed(doc_name, page_name, "TechDraw::DrawPage")
    _validate_page(page)
    view = _page_view(page, view_name)
    if not isinstance(points, list) or not 2 <= len(points) <= 32:
        raise BridgeError("invalid_arguments", "Leader requires 2..32 view-local paper-mm waypoints")
    vectors = []
    for point in points:
        if not isinstance(point, list) or len(point) != 2:
            raise BridgeError("invalid_arguments", "Leader waypoint needs x/y in mm")
        vectors.append(FreeCAD.Vector(*[_number(value, "waypoint") for value in point], 0))
    leader = page.Document.addObject("TechDraw::DrawLeaderLine", name)
    leader.LeaderParent, leader.WayPoints = view, vectors
    leader.addProperty("App::PropertyString", "MCPParentViewName", "MCP")
    leader.MCPParentViewName = view.Name
    leader.setEditorMode("MCPParentViewName", 1)
    page.addView(leader)
    page.Document.recompute()
    return {"reference": _reference(leader), "name": leader.Name, "parent": _reference(view), "points_mm": points}


def _view_data(view):
    projected = Part.makeCompound(view.getVisibleEdges()).BoundBox
    return {"reference": _reference(view), "name": view.Name, "type": view.TypeId,
            "sources": [_reference(source) for source in view.Source],
            "direction": list(view.Direction), "position_mm": list(_paper_position(view)),
            "scale": float(view.Scale), "rotation_deg": float(view.Rotation),
            "visible_edges": len(view.getVisibleEdges()),
            "projected_bbox_mm": [projected.XLength / float(view.Scale), projected.YLength / float(view.Scale)],
            "source_bbox_mm": [[source.Shape.BoundBox.XLength, source.Shape.BoundBox.YLength,
                                source.Shape.BoundBox.ZLength] for source in view.Source]}


def inspect_page(doc_name: str, page_name: str) -> dict:
    page = _typed(doc_name, page_name, "TechDraw::DrawPage")
    _validate_page(page)
    return {"reference": _reference(page), "name": page.Name, "paper_mm": _paper(page),
            "scale": float(page.Scale), "template": _reference(page.Template),
            "editable_texts": dict(page.Template.EditableTexts), "current": True,
            "views": [_view_data(view) for view in _model_views(page)],
            "dimensions": [_dimension_data(item) for item in page.Views if item.TypeId == "TechDraw::DrawViewDimension"],
            "annotations": [{"reference": _reference(item), "text": list(item.Text),
                             "position_mm": [float(item.X), float(item.Y)]}
                            for item in page.Views if item.TypeId == "TechDraw::DrawViewAnnotation"],
            "warnings": ["No automatic whole-sheet overlap validation or manufacturing assurance."]}


def update_page(doc_name: str, page_name: str) -> dict:
    page = _typed(doc_name, page_name, "TechDraw::DrawPage")
    page.Document.recompute()
    _finish_projection()
    return inspect_page(doc_name, page_name)


def set_layout(doc_name: str, page_name: str, view_name: str = None, x: float = None,
               y: float = None, scale: float = None, rotation: float = None,
               texts: dict = None) -> dict:
    page = _typed(doc_name, page_name, "TechDraw::DrawPage")
    _validate_page(page)
    view = _object(doc_name, view_name) if view_name is not None else None
    manual_position = x is not None or y is not None
    if view is not None and view not in page.Views and view not in _model_views(page):
        raise BridgeError("invalid_reference", "Drawing item does not belong to the page", [_reference(view)])
    if view is None and any(value is not None for value in (x, y, rotation)):
        raise BridgeError("invalid_arguments", "Position/rotation require view_name")
    if all(value is None for value in (x, y, scale, rotation, texts)):
        raise BridgeError("invalid_arguments", "At least one layout field is required")
    if view is not None:
        current_x, current_y = _paper_position(view)
        x, y = _position(page, current_x if x is None else x, current_y if y is None else y)
    if scale is not None:
        if view is not None and not view.isDerivedFrom("TechDraw::DrawViewPart") and view.TypeId != "TechDraw::DrawProjGroup":
            raise BridgeError("invalid_arguments", "Custom scale is only supported for model views")
        scale = _number(scale, "scale", positive=True)
    if rotation is not None:
        rotation = _number(rotation, "rotation")
    editable = dict(page.Template.EditableTexts)
    if texts is not None:
        if not isinstance(texts, dict) or not 1 <= len(texts) <= 100 or any(
                key not in editable or not isinstance(value, str) or len(value) > 4096 for key, value in texts.items()):
            raise BridgeError("invalid_arguments", "texts requires existing template keys and strings of at most 4096 characters")
        editable.update(texts)
    if view is not None:
        if manual_position and view.TypeId == "TechDraw::DrawProjGroupItem":
            for parent in view.InList:
                if parent.TypeId == "TechDraw::DrawProjGroup":
                    parent.AutoDistribute = False
        _set_paper_position(view, x, y)
        if rotation is not None:
            view.Rotation = rotation
    if scale is not None:
        target = view if view is not None else page
        if view is not None:
            view.ScaleType = "Custom"
        target.Scale = scale
    if texts is not None:
        page.Template.EditableTexts = editable
    page.Document.recompute()
    _finish_projection()
    return inspect_page(doc_name, page_name)


def export_page(doc_name: str, page_name: str, path: str, format: str, overwrite: bool = False) -> dict:
    import TechDrawGui

    page = _typed(doc_name, page_name, "TechDraw::DrawPage")
    _validate_page(page)
    if not page.Views:
        raise BridgeError("drawing_not_ready", "Cannot export a page without model views", [_reference(page)])
    if format not in {"pdf", "svg"} or type(overwrite) is not bool or not isinstance(path, str):
        raise BridgeError("invalid_arguments", "Expected pdf/svg format, absolute path and boolean overwrite")
    target = Path(path)
    if not target.is_absolute() or target.suffix.lower() != "." + format or not target.parent.is_dir():
        raise BridgeError("invalid_arguments", "Expected an absolute format-matching output path with an existing parent")
    target = target.resolve()
    if target.exists() and not target.is_file():
        raise BridgeError("invalid_arguments", "Output must be a regular file")
    if target.exists() and not overwrite:
        raise BridgeError("file_exists", "Existing output requires overwrite=true")
    exporter = getattr(TechDrawGui, "exportPageAsPdf" if format == "pdf" else "exportPageAsSvg", None)
    if not callable(exporter):
        raise BridgeError("unsupported_feature", "Native TechDraw GUI exporter is unavailable")
    try:
        with tempfile.TemporaryDirectory(prefix="freecad-drawing-", dir=target.parent) as directory:
            staged = Path(directory) / ("page." + format)
            exporter(page, str(staged))
            content = staged.read_bytes()
            if not content:
                raise ValueError("Empty drawing export")
            if format == "svg":
                if ET.fromstring(content).tag != "{http://www.w3.org/2000/svg}svg":
                    raise ValueError("Invalid SVG output")
            elif not content.startswith(b"%PDF-") or b"%%EOF" not in content[-1024:]:
                raise ValueError("Incomplete PDF output")
            if overwrite:
                os.replace(staged, target)
            else:
                os.link(staged, target)
    except FileExistsError as error:
        raise BridgeError("file_exists", "Output appeared during export; not overwritten") from error
    except Exception as error:
        failure = BridgeError("file_write_failed", f"Drawing export failed at {target}: {error}", [_reference(page)])
        failure.bridge_state = "unknown"
        raise failure from error
    return {"reference": _reference(page), "file_name": str(target), "format": format,
            "bytes": target.stat().st_size, "paper_mm": _paper(page), "scale": float(page.Scale)}