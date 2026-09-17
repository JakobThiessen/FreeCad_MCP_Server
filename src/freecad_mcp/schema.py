"""Parameter metadata shared by legacy MCP registrations."""

import inspect
from typing import Annotated, get_origin

from mcp.server.fastmcp import FastMCP
from pydantic import Field


DESCRIPTIONS = {
    "doc_name": "Internal document Name, never Label/path. Omitted/null uses active document (legacy); pass explicitly.",
    "name": "Requested internal name for a new object/document; FreeCAD may uniquify it. Use the returned name.",
    "path": "File path on the FreeCAD host; FCStd/STEP/STL/OBJ as selected by this tool. File I/O is not undoable.",
    "host": "Trusted local bridge host; default IPv4 loopback. No remote security or authentication promised.",
    "port": "XML-RPC TCP port; default 9875, isolated tests may use another port.",
    "plane": "Plane XY, XZ or YZ; sketch plane is relative to its container, PartDesign mirror uses Body origin.",
    "plane_name": "Required neutral plane for draft: internal datum name or Object.FaceN in the same document.",
    "axis": "V/H/N sketch-local axes for revolution/groove; X/Y/Z Body-origin axes for polar pattern.",
    "direction": "X/Y/Z Body-origin axis for linear pattern; isometric/front/back/top/bottom/left/right for set_view.",
    "view": "Optional camera preset: isometric, front, back, top, bottom, left, right; null keeps current camera.",
    "edges": "Nonempty edge list: issued {document,object,revision,subelement} selections are validated before mutation; legacy EdgeN strings (Part also 1-based integers) have no revision protection. Batch retains legacy selectors only.",
    "faces": "Nonempty face list: issued {document,object,revision,subelement} selections are validated before mutation; legacy FaceN strings have no revision protection.",
    "points": "Ordered [x,y] coordinate pairs in mm in sketch-local XY; control points for B-spline.",
    "obj_names": "Internal object Names in the explicit document; export null selects visible final objects, empty selects none.",
    "sketch_names": "Ordered internal profile sketch Names in the same document/Body; at least two for loft.",
    "construction": "True creates sketch construction geometry; false creates profile geometry.",
    "defining": "True imports external geometry as defining geometry; false uses construction geometry.",
    "intersection": "True imports the support intersection; false projects the selected edge.",
    "external_idx": "External geometry list index, zero-based; the corresponding sketch geometry index starts at -3.",
    "support_selection": "Revision-checked planar face selection in the same document; mutually exclusive with support_name.",
    "selection": "Complete revision-checked subelement selection issued by a Stage 4 geometry query.",
    "include_axes": "Whether trim may use sketch axes as cutters; unsupported and rejected by FreeCAD 1.1.",
    "clone": "True adds clone relationships for copies; false creates independent copied geometry.",
    "trim": "True trims source curves when creating the sketch fillet.",
    "create_corner": "True creates coincident/tangent corner constraints for the sketch fillet.",
    "reference_geo_idx": "Local or external sketch geometry index used as mirror line or point reference.",
    "reference_point_idx": "Mirror reference point position; 0 uses the reference geometry as a line.",
    "constraint_idx": "Sketch constraint index, zero-based in the current sketch state.",
    "driving": "True makes the dimensional constraint driving; false makes it a reference. Null leaves the mode unchanged.",
    "active": "True activates the constraint; false deactivates it. Null leaves the mode unchanged.",
    "close": "True adds a closing polygon segment; false leaves the polyline open.",
    "closed": "True connects the last loft section to the first; false leaves section sequence open.",
    "solid": "PartDesign supports only true (solid); false is rejected. Shells belong to Part.",
    "ruled": "True uses straight generators between loft sections; false uses smooth interpolation.",
    "reversed": "Reverse the feature direction relative to the profile/axis.",
    "symmetric": "Extrude symmetrically about the profile plane; length is the total span.",
    "through_all": "True cuts through all and ignores length; false uses the specified pocket length.",
    "threaded": "Enable simplified threaded-hole metadata; not a manufacturing or strength guarantee.",
    "thread_type": "ISO or UTS alias, or native FreeCAD ThreadType enumeration; unsupported values fail.",
    "thread_size": "Native thread size (e.g. M6x1.0); legacy M6 selects first matching diameter in runtime enum.",
    "visible": "True shows the object; false hides it.",
    "transparency": "Percent: 0 opaque, 100 transparent; legacy implementation clamps outside this interval.",
    "factor": "Dimensionless uniform scaling factor; creates a new independent shape copy.",
    "occurrences": "Integer count including original feature, at least two for a pattern.",
    "code": "Legacy developer Python executed in FreeCAD, not a sandbox. Excluded from structured CAD workflows.",
    "steps": "Ordered allowlisted batch steps, 1..100; only backward same-document result-name references.",
    "atomic": "True: one existing document, all-or-nothing. False: stop on first error, preserve prior successes.",
    "preview": "True validates and reports effects without executing CAD operations; geometry success is not predicted.",
}


def parameter_metadata(tool, parameter):
    name = parameter.name
    metadata = {}
    if name in {"x", "y", "z", "x1", "y1", "x2", "y2", "cx", "cy", "dx", "dy", "dz", "offset",
                "length", "width", "height", "depth", "diameter", "radius", "radius1", "radius2",
                "major_radius", "minor_radius", "size", "value", "offset_x", "offset_y", "offset_z",
                "near1_x", "near1_y", "near2_x", "near2_y", "increment"}:
        unit = "px" if tool == "screenshot" and name in {"width", "height"} else "mm"
        frame = "sketch_local_xy" if tool.startswith("sketch_") else "feature_local"
        if tool.startswith("part_"):
            frame = "document_global"
        if tool in {"set_placement", "move_object"}:
            frame = "parent_local (document_global for top-level objects)"
        if tool == "create_sketch":
            frame = "container_local; offset along positive global X/Y/Z for YZ/XZ/XY"
        if tool == "sketch_set_constraint_value" and name == "value":
            unit = "mm_or_deg_by_constraint_type"
            frame = "sketch_local"
        metadata = {"x-unit": unit, "x-coordinate-system": frame}
        description = f"{name}: {unit}, {frame}."
    elif name in {"angle", "start_angle", "end_angle", "rx", "ry", "rz",
                 "rotation_x", "rotation_y", "rotation_z"}:
        unit = "rad" if tool in {"sketch_add_arc", "sketch_add_ellipse"} else "deg"
        frame = "sketch_local" if tool.startswith("sketch_") else "feature_axis"
        if tool in {"set_placement", "rotate_object"}:
            frame = "parent_local; XYZ applied X then Y then Z for set_placement"
        metadata = {"x-unit": unit, "x-coordinate-system": frame}
        description = f"{name}: {unit}, {frame}."
    elif name in {"axis_x", "axis_y", "axis_z"}:
        description = "Dimensionless rotation-axis vector component in parent coordinates; vector must be nonzero."
    elif name in {"r", "g", "b"}:
        description = "Dimensionless RGB color channel in [0,1]."
    elif name.startswith("geo_idx") or name in {"sym_geo", "target_geo_idx"}:
        description = "Sketch geometry index, zero-based; FreeCAD external axis indices may be negative."
    elif name.startswith("point_idx") or name == "sym_point":
        description = "Sketch point position: 1=start, 2=end, 3=center where supported; symmetry 0 selects line."
    elif name.endswith("_name") and name not in DESCRIPTIONS:
        description = "Internal object Name in the selected document, never Label; must have the type required by this tool."
    else:
        description = DESCRIPTIONS[name]
    if name == "name" and tool in {"save_document", "close_document"}:
        description = "Existing internal document Name; save null uses active document, close requires a name."
    return description, metadata


class SchemaMCP(FastMCP):
    """Add field-level legacy metadata before FastMCP builds its input models."""

    def tool(self, *args, **kwargs):
        register = super().tool(*args, **kwargs)

        def decorate(function):
            for parameter in inspect.signature(function).parameters.values():
                if get_origin(parameter.annotation) is Annotated:
                    continue
                description, metadata = parameter_metadata(function.__name__, parameter)
                annotation = parameter.annotation
                if parameter.default is None:
                    annotation = annotation | None
                function.__annotations__[parameter.name] = Annotated[
                    annotation, Field(description=description, json_schema_extra=metadata)
                ]
            function.__doc__ = (function.__doc__ or "") + (
                "\n\nContract: explicit internal names recommended. Length mm, area mm^2, volume mm^3; "
                "field units override defaults. Errors: invalid_arguments, document_not_found, object_not_found, "
                "transaction_conflict, operation_failed, execution_timeout; transport failures are possible. "
                "Timeout is not cancellation: never blindly retry mutations. Legacy return shape preserved."
            )
            return register(function)

        return decorate
