"""PartDesign operations running inside FreeCAD.

Provides Body creation, feature operations (Pad, Pocket, Revolution, etc.),
and pattern operations.
"""

import math

import FreeCAD
import FreeCADGui
from FreeCAD import Vector


MAX_PATTERN_OCCURRENCES = 100
MAX_TRANSFORM_INSTANCES = 100

_EXTRUSION_TYPES = {
    "dimension": "Length",
    "through_all": "ThroughAll",
    "up_to_first": "UpToFirst",
    "up_to_face": "UpToFace",
    "two_lengths": "Length",
}


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
# Body
# =============================================================================


def create_body(name: str = "Body", doc_name: str = None) -> dict:
    """Create a new PartDesign Body."""
    doc = _get_doc(doc_name)
    body = doc.addObject("PartDesign::Body", name)
    doc.recompute()
    return {"name": body.Name, "label": body.Label}


def create_datum(body_name: str, kind: str, name: str = None,
                 support_selection: dict = None,
                 x: float = 0, y: float = 0, z: float = 0,
                 rotation_x: float = 0, rotation_y: float = 0,
                 rotation_z: float = 0, doc_name: str = None) -> dict:
    """Create a datum plane, line, or point in a PartDesign Body."""
    doc = _get_doc(doc_name)
    body = _get_object(body_name, doc_name)
    kinds = {
        "plane": ("PartDesign::Plane", "DatumPlane"),
        "axis": ("PartDesign::Line", "DatumLine"),
        "point": ("PartDesign::Point", "DatumPoint"),
    }
    normalized = kind.lower()
    if normalized not in kinds:
        raise ValueError("Datum kind must be plane, axis, or point")
    if body.TypeId != "PartDesign::Body":
        raise ValueError(f"Object '{body.Name}' is not a PartDesign Body")
    placement = FreeCAD.Placement(
        Vector(x, y, z), FreeCAD.Rotation(rotation_z, rotation_y, rotation_x))
    resolved_support = None
    if support_selection is not None:
        from freecad_ai_bridge.geometry_ops import _descriptor, _resolve

        support_doc, owner, shape, support_kind = _resolve(support_selection)
        geometry_type = _descriptor(shape, support_kind)["geometry_type"]
        allowed_supports = {"plane": {("face", "plane")},
                            "axis": {("face", "cylinder"), ("edge", "line")},
                            "point": {("vertex", "vertex")}}
        if support_doc.Name != doc.Name:
            raise ValueError(f"Datum support must be in document '{doc.Name}'")
        if (support_kind, geometry_type) not in allowed_supports[normalized]:
            raise ValueError(f"Datum {normalized} does not support {geometry_type} {support_kind}")
        subelement = support_selection["subelement"]
        if geometry_type == "cylinder":
            # FreeCAD 1.1 has no line mode for a cylindrical face itself (only inertia axes, which are
            # proportion dependent and wrong for partial cylinders); a circular boundary edge yields the exact axis.
            subelement, map_mode = _circular_boundary_edge(owner, subelement), "AxisOfCurvature"
        else:
            map_mode = {"plane": "FlatFace", "axis": "TwoPointLine", "point": "Vertex"}[normalized]
        resolved_support = owner, subelement, map_mode
    type_id, default_name = kinds[normalized]
    datum = body.newObject(type_id, name or default_name)
    if resolved_support is not None:
        owner, subelement, map_mode = resolved_support
        datum.AttachmentSupport = (owner, [subelement])
        datum.MapMode = map_mode
    else:
        datum.Placement = placement
    datum.AttachmentOffset = placement
    doc.recompute()
    if "Invalid" in datum.State or datum.Shape.isNull():
        raise ValueError(f"Datum {normalized} attachment failed: {datum.getStatusString()}")
    return {
        "name": datum.Name,
        "label": datum.Label,
        "type": datum.TypeId,
        "kind": normalized,
        "support": support_selection,
        "attachment": {
            "map_mode": datum.MapMode,
            "subelements": [resolved_support[1]] if resolved_support else [],
        },
        "attachment_offset": {
            "position": [x, y, z],
            "rotation_xyz_deg": [rotation_x, rotation_y, rotation_z],
        },
    }


def _circular_boundary_edge(owner, face_name):
    shape = owner.Shape
    face = shape.getElement(face_name)
    for index, edge in enumerate(shape.Edges, 1):
        if type(edge.Curve).__name__ == "Circle" and any(edge.isSame(boundary) for boundary in face.Edges):
            return f"Edge{index}"
    raise ValueError(f"Cylindrical support {owner.Name}.{face_name} needs a circular boundary edge")


# =============================================================================
# Additive Features
# =============================================================================


def pad(sketch_name: str, length: float, name: str = "Pad",
    symmetric: bool = False, reversed: bool = False,
    end_condition: str = "dimension", second_length: float = None,
    target_selection: dict = None, doc_name: str = None) -> dict:
    """Pad (extrude) a sketch.

    Args:
        sketch_name: Name of the sketch to pad
        length: Extrusion length
        symmetric: If True, pad symmetrically in both directions
        reversed: If True, pad in reverse direction
    """
    doc = _get_doc(doc_name)
    sketch, _body = _profile_sketch(sketch_name, doc_name)

    condition = _validate_extrusion(end_condition, length, symmetric,
                                    second_length, target_selection, False)
    target = _resolve_extrusion_target(target_selection, doc) if condition == "up_to_face" else None
    pad_obj = doc.addObject("PartDesign::Pad", name)
    pad_obj.Profile = sketch
    _configure_extrusion(pad_obj, condition, length, symmetric, reversed,
                         second_length, target, doc)

    # Add to body if sketch is in a body
    _add_to_body(sketch, pad_obj, doc)

    sketch.Visibility = False
    doc.recompute()
    return _feature_result(pad_obj)


def pocket(sketch_name: str, length: float, name: str = "Pocket",
           through_all: bool = False, reversed: bool = False,
           symmetric: bool = False, end_condition: str = None,
           second_length: float = None, target_selection: dict = None,
           doc_name: str = None) -> dict:
    """Create a pocket (subtractive extrusion) from a sketch.

    Args:
        sketch_name: Name of the sketch
        length: Depth of pocket (ignored if through_all=True)
        through_all: If True, cut through entire part
        reversed: If True, cut in reverse direction
    """
    doc = _get_doc(doc_name)
    sketch, body = _profile_sketch(sketch_name, doc_name)

    if through_all and end_condition is not None and str(end_condition).lower() != "through_all":
        raise ValueError(f"through_all=True conflicts with end_condition '{end_condition}'")
    condition = end_condition or ("through_all" if through_all else "dimension")
    condition = _validate_extrusion(condition, length, symmetric,
                                    second_length, target_selection, True)
    _require_base_solid(body, "Pocket")
    target = _resolve_extrusion_target(target_selection, doc) if condition == "up_to_face" else None
    pocket_obj = doc.addObject("PartDesign::Pocket", name)
    pocket_obj.Profile = sketch
    _configure_extrusion(pocket_obj, condition, length, symmetric, reversed,
                         second_length, target, doc)

    _add_to_body(sketch, pocket_obj, doc)

    sketch.Visibility = False
    doc.recompute()
    return _feature_result(pocket_obj)


def revolution(sketch_name: str, angle: float = 360.0, name: str = "Revolution",
               axis: str = "V", reversed: bool = False, symmetric: bool = False,
               second_angle: float = None, axis_name: str = None,
               doc_name: str = None) -> dict:
    """Revolve a sketch around an axis.

    Args:
        sketch_name: Name of the sketch
        angle: Revolution angle in degrees (default 360 = full revolution)
        axis: Sketch axis 'V' (sketch Y), 'H' (sketch X) or 'N' (sketch normal; degenerate for sketch
            profiles and rejected by the zero-volume check), or axis_name of a datum axis in the same Body
        reversed: If True, revolve in reverse direction
    """
    doc = _get_doc(doc_name)
    sketch, body = _profile_sketch(sketch_name, doc_name)

    _validate_rotation(angle, symmetric, second_angle)
    axis_reference = _rotation_axis_reference(sketch, body, axis, axis_name, doc)
    rev = doc.addObject("PartDesign::Revolution", name)
    rev.Profile = sketch
    rev.Angle = angle
    rev.Reversed = reversed
    rev.ReferenceAxis = axis_reference
    _configure_rotation_sides(rev, symmetric, second_angle)

    _add_to_body(sketch, rev, doc)

    sketch.Visibility = False
    doc.recompute()
    return _feature_result(rev)


def groove(sketch_name: str, angle: float = 360.0, name: str = "Groove",
           axis: str = "V", reversed: bool = False, symmetric: bool = False,
           second_angle: float = None, axis_name: str = None,
           doc_name: str = None) -> dict:
    """Create a groove (subtractive revolution) from a sketch."""
    doc = _get_doc(doc_name)
    sketch, body = _profile_sketch(sketch_name, doc_name)

    _validate_rotation(angle, symmetric, second_angle)
    axis_reference = _rotation_axis_reference(sketch, body, axis, axis_name, doc)
    _require_base_solid(body, "Groove")
    grv = doc.addObject("PartDesign::Groove", name)
    grv.Profile = sketch
    grv.Angle = angle
    grv.Reversed = reversed
    grv.ReferenceAxis = axis_reference
    _configure_rotation_sides(grv, symmetric, second_angle)

    _add_to_body(sketch, grv, doc)

    sketch.Visibility = False
    doc.recompute()
    return _feature_result(grv)


def loft(sketch_names: list, name: str = "Loft", solid: bool = True,
         ruled: bool = False, closed: bool = False, doc_name: str = None) -> dict:
    """Create a loft between multiple sketches/profiles.

    Args:
        sketch_names: List of sketch names to loft between (in order)
        solid: If True, create a solid (vs. shell)
        ruled: If True, use ruled surfaces
        closed: If True, close the loft (connect last to first)
    """
    sketches, _body = _loft_profiles(sketch_names, solid, closed, ruled, doc_name)
    doc = _get_doc(doc_name)

    loft_obj = doc.addObject("PartDesign::AdditiveLoft", name)
    loft_obj.Profile = sketches[0]
    loft_obj.Sections = sketches[1:]
    loft_obj.Ruled = ruled
    loft_obj.Closed = closed

    _add_to_body(sketches[0], loft_obj, doc)

    for s in sketches:
        s.Visibility = False
    doc.recompute()
    return _feature_result(loft_obj)


def sweep(sketch_name: str, spine_name: str, name: str = "Sweep",
          solid: bool = True, path_edges: list = None,
          orientation: str = "standard", transition: str = "transformed",
          doc_name: str = None) -> dict:
    """Sweep a profile along a spine (path).

    Args:
        sketch_name: Profile sketch name
        spine_name: Path/spine sketch or edge name
    """
    if not solid:
        raise ValueError("PartDesign sweeps must be solid; use Part for shells")
    doc = _get_doc(doc_name)
    sketch, _body = _profile_sketch(sketch_name, doc_name)
    spine, edges = _pipe_path(sketch, spine_name, path_edges, orientation, transition, doc)

    sweep_obj = doc.addObject("PartDesign::AdditivePipe", name)
    sweep_obj.Profile = sketch
    _configure_pipe(sweep_obj, spine, edges, orientation, transition)

    _add_to_body(sketch, sweep_obj, doc)

    sketch.Visibility = False
    doc.recompute()
    return _feature_result(sweep_obj)


def hole(sketch_name: str, diameter: float, depth: float,
         name: str = "Hole", threaded: bool = False,
         thread_type: str = "ISO", thread_size: str = "M6",
         thread_pitch: float = None, through_all: bool = False,
         cut_type: str = "simple", cut_diameter: float = None,
         cut_depth: float = None, countersink_angle: float = 90,
         doc_name: str = None) -> dict:
    """Create a hole feature (one hole per circle or point of the profile sketch).

    Args:
        sketch_name: Sketch with center point(s) or circles for hole positions
        diameter: Drilled hole diameter in mm (also honoured for threaded holes)
        depth: Hole depth in mm (replaced by the through-all length when through_all)
        threaded: If True, create threaded hole metadata (no modelled helix)
        thread_type: Thread standard 'ISO' (metric; coarse, or fine when thread_pitch
            selects a fine pitch) or 'UTS' (UNC; the size defines the pitch)
        thread_size: Thread size (e.g., 'M6', 'M8', '1/4')
        thread_pitch: ISO pitch in mm, for example 0.75 for M6 fine
    """
    doc = _get_doc(doc_name)
    sketch, body = _profile_sketch(sketch_name, doc_name)
    cut_types = {"simple": "None", "counterbore": "Counterbore", "countersink": "Countersink"}
    normalized_cut = str(cut_type).lower()
    if _positive_or_none(diameter) is None or _positive_or_none(depth) is None:
        raise ValueError("Hole diameter and depth must be positive")
    if normalized_cut not in cut_types:
        raise ValueError("cut_type must be simple, counterbore, or countersink")
    if normalized_cut != "simple" and (_positive_or_none(cut_diameter) is None or cut_diameter <= diameter):
        raise ValueError("Counterbore/countersink requires cut_diameter greater than diameter")
    if normalized_cut == "counterbore" and _positive_or_none(cut_depth) is None:
        raise ValueError("Counterbore requires positive cut_depth")
    if normalized_cut == "countersink" and not (_finite(countersink_angle) and 0 < countersink_angle < 180):
        raise ValueError("countersink_angle must be in (0, 180)")
    standard = str(thread_type).upper()
    if threaded:
        if standard not in {"ISO", "UTS"}:
            raise ValueError("thread_type must be ISO or UTS")
        if not isinstance(thread_size, str) or not thread_size.strip():
            raise ValueError("thread_size must be a nonempty string such as M6 or 1/4")
        if thread_pitch is not None:
            if standard == "UTS":
                raise ValueError("thread_pitch is not supported for UTS; the UNC size defines the pitch")
            if _positive_or_none(thread_pitch) is None:
                raise ValueError("thread_pitch must be positive")
    _require_base_solid(body, "Hole")
    base_volume = _dressup_base_volume(body.Tip)

    hole_obj = doc.addObject("PartDesign::Hole", name)
    hole_obj.Profile = sketch
    _add_to_body(sketch, hole_obj, doc)
    doc.recompute()
    hole_obj.Diameter = diameter
    hole_obj.Depth = depth
    hole_obj.DepthType = "ThroughAll" if through_all else "Dimension"
    hole_obj.HoleCutType = cut_types[normalized_cut]
    if normalized_cut != "simple":
        hole_obj.HoleCutCustomValues = True
        hole_obj.HoleCutDiameter = cut_diameter

    if normalized_cut == "counterbore":
        hole_obj.HoleCutDepth = cut_depth
    elif normalized_cut == "countersink":
        hole_obj.HoleCutCountersinkAngle = countersink_angle
    hole_obj.Threaded = threaded

    if threaded:
        pitch = float(thread_pitch) if thread_pitch is not None else None
        sizes_by_type = {}
        candidates = ["UNC"] if standard == "UTS" else (
            ["ISOMetricProfile", "ISOMetricFineProfile"] if pitch is not None or "x" in thread_size
            else ["ISOMetricProfile"])
        match = None
        for freecad_type in candidates:
            hole_obj.ThreadType = freecad_type
            sizes_by_type[freecad_type] = list(hole_obj.getEnumerationsOfProperty("ThreadSize"))
            match = _thread_size_match(sizes_by_type[freecad_type], thread_size.strip(), pitch)
            if match:
                break
        if not match:
            raise ValueError(f"Unknown thread size '{thread_size}'"
                             + (f" with pitch {pitch:g}" if pitch is not None else "")
                             + f" for {standard}; available: {sizes_by_type}")
        hole_obj.ThreadSize = match
        # FreeCAD replaces Diameter by the tap drill when the size is assigned; the requested value wins.
        hole_obj.Diameter = diameter

    sketch.Visibility = False
    doc.recompute()
    result = _feature_result(hole_obj)
    result = _dressup_effect(result, hole_obj, base_volume, "Hole")
    result["diameter"] = hole_obj.Diameter.Value
    result["depth_type"] = hole_obj.DepthType
    result["depth"] = hole_obj.Depth.Value
    result["cut_type"] = normalized_cut
    if threaded:
        result["thread"] = {"type": standard, "freecad_type": hole_obj.ThreadType,
                            "size": hole_obj.ThreadSize, "pitch": _thread_pitch(hole_obj.ThreadSize),
                            "thread_diameter": hole_obj.ThreadDiameter.Value}
    return result


# =============================================================================
# Subtractive Features
# =============================================================================


def subtractive_loft(sketch_names: list, name: str = "SubtractiveLoft",
                     solid: bool = True, ruled: bool = False,
                     doc_name: str = None) -> dict:
    """Create a subtractive loft (cut) between multiple sketches."""
    sketches, body = _loft_profiles(sketch_names, solid, False, ruled, doc_name)
    _require_base_solid(body, "Subtractive loft")
    doc = _get_doc(doc_name)

    loft_obj = doc.addObject("PartDesign::SubtractiveLoft", name)
    loft_obj.Profile = sketches[0]
    loft_obj.Sections = sketches[1:]
    loft_obj.Ruled = ruled

    _add_to_body(sketches[0], loft_obj, doc)

    for s in sketches:
        s.Visibility = False
    doc.recompute()
    return _feature_result(loft_obj)


def subtractive_pipe(sketch_name: str, spine_name: str,
                     name: str = "SubtractivePipe", path_edges: list = None,
                     orientation: str = "standard", transition: str = "transformed",
                     doc_name: str = None) -> dict:
    """Create a subtractive pipe/sweep (cut along path)."""
    doc = _get_doc(doc_name)
    sketch, body = _profile_sketch(sketch_name, doc_name)
    spine, edges = _pipe_path(sketch, spine_name, path_edges, orientation, transition, doc)
    _require_base_solid(body, "Subtractive pipe")

    pipe_obj = doc.addObject("PartDesign::SubtractivePipe", name)
    pipe_obj.Profile = sketch
    _configure_pipe(pipe_obj, spine, edges, orientation, transition)

    _add_to_body(sketch, pipe_obj, doc)

    sketch.Visibility = False
    doc.recompute()
    return _feature_result(pipe_obj)


# =============================================================================
# Dress-up Features
# =============================================================================


def fillet(base_name: str, edges: list, radius: float,
           name: str = "Fillet", doc_name: str = None) -> dict:
    """Add a constant-radius fillet to edges of the Body Tip.

    Args:
        base_name: Name of the base feature; must be the Tip of its Body
        edges: Revision-checked edge selections of the base feature
        radius: Fillet radius in mm
    """
    doc = _get_doc(doc_name)
    base = _get_object(base_name, doc_name)
    edges = _dressup_selection(doc, base, edges, "edge")
    radius = _positive("Fillet radius", radius)
    base_volume = _dressup_base_volume(base)

    fillet_obj = doc.addObject("PartDesign::Fillet", name)
    fillet_obj.Base = (base, edges)
    fillet_obj.Radius = radius

    _add_to_body(base, fillet_obj, doc)
    doc.recompute()
    result = _feature_result(fillet_obj, f"radius {radius:g} mm may be too large for the selected edges")
    return _dressup_effect(result, fillet_obj, base_volume, "Fillet")


def chamfer(base_name: str, edges: list, size: float,
            name: str = "Chamfer", second_size: float = None,
            doc_name: str = None) -> dict:
    """Add a chamfer to edges of the Body Tip.

    Args:
        base_name: Name of the base feature; must be the Tip of its Body
        edges: Revision-checked edge selections of the base feature
        size: Chamfer distance in mm (with second_size: distance on the first adjacent face)
        second_size: Optional second distance in mm (two-distances chamfer)
    """
    doc = _get_doc(doc_name)
    base = _get_object(base_name, doc_name)
    edges = _dressup_selection(doc, base, edges, "edge")
    size = _positive("Chamfer size", size)
    if second_size is not None:
        second_size = _positive("second_size", second_size)
    base_volume = _dressup_base_volume(base)

    chamfer_obj = doc.addObject("PartDesign::Chamfer", name)
    chamfer_obj.Base = (base, edges)
    chamfer_obj.Size = size
    if second_size is not None:
        chamfer_obj.ChamferType = "Two distances"
        chamfer_obj.Size2 = second_size

    _add_to_body(base, chamfer_obj, doc)
    doc.recompute()
    result = _feature_result(chamfer_obj, "chamfer distances may be too large for the selected edges")
    return _dressup_effect(result, chamfer_obj, base_volume, "Chamfer")


def thickness(base_name: str, faces: list, value: float,
              name: str = "Thickness", direction: str = "inside",
              join: str = "arc", doc_name: str = None) -> dict:
    """Shell a solid by removing faces and offsetting the remaining faces.

    Args:
        base_name: Name of the base feature; must be the Tip of its Body
        faces: Revision-checked face selections of the base feature to remove
        value: Wall thickness in mm
        direction: 'inside' grows the wall into the solid, 'outside' away from it
        join: Corner join 'arc' or 'intersection'
    """
    doc = _get_doc(doc_name)
    base = _get_object(base_name, doc_name)
    faces = _dressup_selection(doc, base, faces, "face")
    value = _positive("Thickness value", value)
    if direction not in {"inside", "outside"}:
        raise ValueError("direction must be inside or outside")
    if str(join).lower() not in {"arc", "intersection"}:
        raise ValueError(f"Unsupported Join '{join}'; expected arc, intersection")
    base_volume = _dressup_base_volume(base)

    thick_obj = doc.addObject("PartDesign::Thickness", name)
    thick_obj.Base = (base, faces)
    thick_obj.Value = value
    # FreeCAD's Reversed=False grows the wall away from the solid; 'inside' needs Reversed=True.
    thick_obj.Reversed = direction == "inside"
    _set_enum(thick_obj, "Join", join, {"arc": ["Arc"], "intersection": ["Intersection"]})

    _add_to_body(base, thick_obj, doc)
    doc.recompute()
    result = _feature_result(thick_obj, f"thickness {value:g} mm may be too large for this geometry")
    return _dressup_effect(result, thick_obj, base_volume, "Thickness")


def draft(base_name: str, faces: list, angle: float,
          plane_name: str = None, name: str = "Draft",
          pull_selection: dict = None, doc_name: str = None,
          plane_selection: dict = None) -> dict:
    """Add a draft angle to faces of the Body Tip.

    Args:
        base_name: Name of the base feature; must be the Tip of its Body
        faces: Revision-checked face selections of the base feature to draft
        angle: Draft angle in degrees, 0 < |angle| < 90 (the sign flips the taper)
        plane_name: Neutral plane as datum plane Name or 'Object.FaceN' of a planar face
        plane_selection: Alternative: revision-checked planar face selection as neutral plane
        pull_selection: Optional revision-checked straight-edge selection giving the pull direction
    """
    doc = _get_doc(doc_name)
    base = _get_object(base_name, doc_name)
    faces = _dressup_selection(doc, base, faces, "face")
    if not _finite(angle) or angle == 0 or abs(angle) >= 90:
        raise ValueError("Draft angle must be nonzero with |angle| < 90 degrees")
    plane_object, plane_elements = _draft_plane(doc, base, plane_name, plane_selection, faces)
    pull = None
    if pull_selection is not None:
        from freecad_ai_bridge.geometry_ops import _resolve

        pull_doc, pull_owner, _shape, pull_kind = _resolve(pull_selection)
        if pull_doc.Name != doc.Name or pull_kind != "edge":
            raise ValueError("Pull direction requires a same-document edge selection")
        pull = (pull_owner, [pull_selection["subelement"]])
    base_volume = _dressup_base_volume(base)

    draft_obj = doc.addObject("PartDesign::Draft", name)
    draft_obj.Base = (base, faces)
    draft_obj.Angle = angle
    draft_obj.NeutralPlane = (plane_object, plane_elements)
    if pull is not None:
        draft_obj.PullDirection = pull

    _add_to_body(base, draft_obj, doc)
    doc.recompute()
    result = _feature_result(draft_obj, f"angle {angle:g} degrees may be too large for this geometry")
    return _dressup_effect(result, draft_obj, base_volume, "Draft")



# =============================================================================
# Patterns
# =============================================================================


def linear_pattern(feature_name: str, direction: str = "X",
                   length: float = 100.0, occurrences: int = 3,
                   name: str = "LinearPattern", feature_names: list = None,
                   direction_name: str = None, doc_name: str = None) -> dict:
    """Create a linear pattern of a feature.

    Args:
        feature_name: Feature to pattern
        direction: 'X', 'Y', or 'Z'; axis_name (datum axis in the Body) takes precedence
        length: Distance between the first and the last copy in mm
        occurrences: Number of copies including the original, 2..100
    """
    doc = _get_doc(doc_name)
    feature = _get_object(feature_name, doc_name)
    originals, body = _pattern_originals(feature, feature_names, doc)
    reference = _pattern_reference(feature, direction, direction_name, ("X", "Y", "Z"), "Axis", doc)
    if not _finite(length) or length <= 0 or not _valid_count(occurrences):
        raise ValueError("Pattern requires at least two occurrences and positive length")
    _check_occurrence_limit(occurrences)

    pattern = doc.addObject("PartDesign::LinearPattern", name)
    pattern.Originals = originals
    pattern.Length = length
    pattern.Occurrences = occurrences

    # Set direction
    pattern.Direction = (reference, [""])

    _add_to_body(feature, pattern, doc)
    doc.recompute()
    return _pattern_result(pattern, originals)


def polar_pattern(feature_name: str, axis: str = "Z",
                  angle: float = 360.0, occurrences: int = 6,
                  name: str = "PolarPattern", feature_names: list = None,
                  axis_name: str = None, doc_name: str = None) -> dict:
    """Create a polar (circular) pattern of a feature.

    Args:
        feature_name: Feature to pattern
        axis: Rotation axis - 'X', 'Y', or 'Z'; axis_name (datum axis in the Body) takes precedence
        angle: Total angle span in degrees; 360 spreads the copies evenly around the
            circle, less than 360 puts the last copy exactly angle degrees from the first
        occurrences: Number of copies including the original, 2..100
    """
    doc = _get_doc(doc_name)
    feature = _get_object(feature_name, doc_name)
    originals, body = _pattern_originals(feature, feature_names, doc)
    reference = _pattern_reference(feature, axis, axis_name, ("X", "Y", "Z"), "Axis", doc)
    if not _valid_count(occurrences) or not (_finite(angle) and 0 < angle <= 360):
        raise ValueError("Pattern requires at least two occurrences and an angle in (0, 360]")
    _check_occurrence_limit(occurrences)

    pattern = doc.addObject("PartDesign::PolarPattern", name)
    pattern.Originals = originals
    pattern.Angle = angle
    pattern.Occurrences = occurrences
    pattern.Axis = (reference, [""])

    _add_to_body(feature, pattern, doc)
    doc.recompute()
    return _pattern_result(pattern, originals)


def mirrored(feature_name: str, plane: str = "XY",
             name: str = "Mirrored", feature_names: list = None,
             plane_name: str = None, doc_name: str = None) -> dict:
    """Mirror a feature about a plane.

    Args:
        feature_name: Feature to mirror
        plane: Mirror plane - 'XY', 'XZ', or 'YZ'; plane_name (datum plane in the Body) takes precedence
    """
    doc = _get_doc(doc_name)
    feature = _get_object(feature_name, doc_name)
    originals, body = _pattern_originals(feature, feature_names, doc)
    reference = _pattern_reference(feature, plane, plane_name, ("XY", "XZ", "YZ"), "Plane", doc)

    mirror = doc.addObject("PartDesign::Mirrored", name)
    mirror.Originals = originals
    mirror.MirrorPlane = (reference, [""])

    _add_to_body(feature, mirror, doc)
    doc.recompute()
    return _pattern_result(mirror, originals)



def multi_transform(feature_names: list, transformations: list,
                    name: str = "MultiTransform", doc_name: str = None) -> dict:
    """Apply an ordered chain of linear, polar, and mirrored transforms."""
    doc = _get_doc(doc_name)
    if not isinstance(feature_names, list) or not feature_names:
        raise ValueError("feature_names must be a nonempty list")
    if not isinstance(transformations, list) or not transformations:
        raise ValueError("transformations must be a nonempty ordered list")
    first = _get_object(feature_names[0], doc_name)
    originals, body = _pattern_originals(first, feature_names[1:], doc)
    steps = _prepare_transform_steps(first, transformations, doc)
    multi = doc.addObject("PartDesign::MultiTransform", name)
    multi.Originals = originals
    multi.Shape = body.Tip.Shape
    body.addObject(multi)
    helpers = []
    for index, step in enumerate(steps, 1):
        kind = step["type"]
        helper_name = f"{multi.Name}_{kind.title()}{index}"
        if kind == "linear":
            helper = doc.addObject("PartDesign::LinearPattern", helper_name)
            helper.Direction = (step["reference"], [""])
            helper.Length = step["length"]
            helper.Occurrences = step["occurrences"]
        elif kind == "polar":
            helper = doc.addObject("PartDesign::PolarPattern", helper_name)
            helper.Axis = (step["reference"], [""])
            helper.Angle = step["angle"]
            helper.Occurrences = step["occurrences"]
        else:
            helper = doc.addObject("PartDesign::Mirrored", helper_name)
            helper.MirrorPlane = (step["reference"], [""])
        body.addObject(helper)
        helpers.append(helper)
    multi.Transformations = helpers
    body.Tip = multi
    for helper in helpers:
        helper.Visibility = False
    doc.recompute()
    result = _pattern_result(multi, originals)
    result["transformations"] = [helper.Name for helper in helpers]
    return result


_EDIT_PARAMETERS = {
    "length": "Length", "second_length": "Length2",
    "angle": "Angle", "second_angle": "Angle2",
    "diameter": "Diameter", "depth": "Depth",
    "occurrences": "Occurrences", "radius": "Radius",
    "size": "Size", "second_size": "Size2", "value": "Value",
    "reversed": "Reversed",
}

# Secondary dimensions belong to one feature family even when other types expose a same-named property.
_EDIT_SECOND_OWNERS = {
    "second_length": {"PartDesign::Pad", "PartDesign::Pocket"},
    "second_angle": {"PartDesign::Revolution", "PartDesign::Groove"},
    "second_size": {"PartDesign::Chamfer"},
}


def edit_feature(feature_name: str, profile_names: list = None,
                 parameters: dict = None, doc_name: str = None) -> dict:
    """Replace feature profiles and edit a bounded set of native parameters.

    Parameters that the feature's current mode ignores (for example second_length without
    two lengths) are rejected, and the edit is rolled back when it invalidates the edited
    feature, any later feature, or the Body Tip.
    """
    doc = _get_doc(doc_name)
    feature = _get_object(feature_name, doc_name)
    body = feature.getParentGeoFeatureGroup()
    if body is None or body.TypeId != "PartDesign::Body":
        raise ValueError(f"Feature '{feature.Name}' must belong to a PartDesign Body")
    if profile_names is None and not parameters:
        raise ValueError("profile_names or parameters is required")
    if parameters is not None and not isinstance(parameters, dict):
        raise ValueError("parameters must be an object")
    edits = _validate_edit_parameters(feature, parameters or {})
    profiles = None
    if profile_names is not None:
        if not isinstance(profile_names, list) or not profile_names:
            raise ValueError("profile_names must be a nonempty list")
        if len(set(profile_names)) != len(profile_names):
            raise ValueError("Replacement profiles must be distinct")
        profiles = [_profile_sketch(profile_name, doc.Name, "Replacement profile")[0] for profile_name in profile_names]
        if any(profile.getParentGeoFeatureGroup() != body for profile in profiles):
            raise ValueError("Replacement profiles must belong to the same Body")
        if "Sections" in feature.PropertiesList:
            if len(profiles) < 2:
                raise ValueError("Loft profile replacement requires at least two profiles")
        elif "Profile" in feature.PropertiesList:
            if len(profiles) != 1:
                raise ValueError("This feature accepts exactly one replacement profile")
        else:
            raise ValueError(f"Feature '{feature.Name}' does not expose editable profiles")
    if profiles is not None:
        if "Sections" in feature.PropertiesList:
            feature.Profile = profiles[0]
            feature.Sections = profiles[1:]
        else:
            old_profile = feature.Profile[0] if isinstance(feature.Profile, tuple) else feature.Profile
            axis = getattr(feature, "ReferenceAxis", None)
            feature.Profile = profiles[0]
            # A sketch axis (V/H/N) of a Revolution/Groove belongs to the old profile and moves with it.
            if axis and axis[0] == old_profile:
                feature.ReferenceAxis = (profiles[0], list(axis[1]))
    for property_name, value in edits.items():
        setattr(feature, property_name, value)
    old_tip = body.Tip
    doc.recompute()
    if body.Tip != old_tip:
        raise ValueError("Editing changed the Body Tip unexpectedly")
    for member in body.Group:
        if member.isDerivedFrom("PartDesign::Feature") and "Invalid" in member.State:
            status = member.getStatusString() or "no valid result"
            if member == feature:
                raise ValueError(f"Feature '{feature.Name}' failed: {status}")
            raise ValueError(f"Editing '{feature.Name}' invalidated '{member.Name}': {status}")
    result = _feature_result(feature)
    if body.Tip != feature:
        try:
            _feature_result(body.Tip)
        except ValueError as error:
            raise ValueError(f"Editing '{feature.Name}' invalidated the Body Tip '{body.Tip.Name}': {error}")
    result["body"] = body.Name
    result["tip"] = body.Tip.Name if body.Tip else None
    return result



# =============================================================================
# Helpers
# =============================================================================


def _validate_extrusion(end_condition, length, symmetric, second_length,
                        target_selection, allow_through_all):
    condition = str(end_condition).lower()
    allowed = set(_EXTRUSION_TYPES)
    if not allow_through_all:
        allowed.remove("through_all")
    if condition not in allowed:
        raise ValueError(f"Unknown end condition '{end_condition}'; expected {', '.join(sorted(allowed))}")
    if length <= 0:
        raise ValueError("Extrusion length must be positive")
    if condition == "two_lengths" and (second_length is None or second_length <= 0):
        raise ValueError("two_lengths requires a positive second_length")
    if condition != "two_lengths" and second_length is not None:
        raise ValueError("second_length is only valid for two_lengths")
    if condition == "up_to_face" and target_selection is None:
        raise ValueError("up_to_face requires target_selection")
    if condition != "up_to_face" and target_selection is not None:
        raise ValueError("target_selection is only valid for up_to_face")
    if symmetric and condition in {"up_to_first", "up_to_face", "two_lengths"}:
        raise ValueError(f"symmetric is not supported with {condition}")
    return condition


def _validate_rotation(angle, symmetric, second_angle):
    if not 0 < angle <= 360:
        raise ValueError("Rotation angle must be in (0, 360]")
    if second_angle is not None and not 0 < second_angle <= 360:
        raise ValueError("Second rotation angle must be in (0, 360]")
    if symmetric and second_angle is not None:
        raise ValueError("symmetric and second_angle are mutually exclusive")
    if second_angle is not None and angle + second_angle > 360:
        raise ValueError("angle + second_angle must not exceed 360")


def _finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _positive_or_none(value):
    return float(value) if _finite(value) and value > 0 else None


def _positive(label, value):
    if _positive_or_none(value) is None:
        raise ValueError(f"{label} must be a positive finite number")
    return float(value)


def _valid_count(value):
    return isinstance(value, int) and not isinstance(value, bool) and value >= 2


def _check_occurrence_limit(occurrences):
    if occurrences > MAX_PATTERN_OCCURRENCES:
        raise ValueError(f"occurrences must not exceed {MAX_PATTERN_OCCURRENCES} (got {occurrences})")


def _pattern_result(pattern, originals):
    result = _feature_result(pattern)
    result["originals"] = [original.Name for original in originals]
    if "Occurrences" in pattern.PropertiesList:
        result["occurrences"] = int(pattern.Occurrences)
    return result


def _prepare_transform_steps(first, steps, doc):
    """Validate and resolve every MultiTransform step before any document mutation."""
    allowed = {"linear": {"direction", "direction_name", "length", "occurrences"},
               "polar": {"axis", "axis_name", "angle", "occurrences"},
               "mirrored": {"plane", "plane_name"}}
    if len(steps) > 16:
        raise ValueError("A MultiTransform chain accepts at most 16 transformations")
    prepared = []
    instances = 1
    for raw in steps:
        step = {key: value for key, value in raw.items() if value is not None} if isinstance(raw, dict) else None
        if step is None or step.get("type") not in allowed:
            raise ValueError("Each transformation requires type linear, polar, or mirrored")
        kind = step["type"]
        extra = sorted(set(step) - allowed[kind] - {"type"})
        if extra:
            raise ValueError(f"A {kind} transformation does not accept {', '.join(extra)}")
        prepared_step = {"type": kind}
        if kind == "linear":
            if not _positive_or_none(step.get("length")) or not _valid_count(step.get("occurrences")):
                raise ValueError("Linear transformation requires positive length and occurrences >= 2")
            if "direction" in step and "direction_name" in step:
                raise ValueError("Linear transformation takes either direction or direction_name")
            prepared_step.update(length=float(step["length"]), occurrences=step["occurrences"],
                                 reference=_pattern_reference(first, step.get("direction", "X"), step.get("direction_name"),
                                                              ("X", "Y", "Z"), "Axis", doc))
        elif kind == "polar":
            if not (_finite(step.get("angle")) and 0 < step["angle"] <= 360) or not _valid_count(step.get("occurrences")):
                raise ValueError("Polar transformation requires angle in (0, 360] and occurrences >= 2")
            if "axis" in step and "axis_name" in step:
                raise ValueError("Polar transformation takes either axis or axis_name")
            prepared_step.update(angle=float(step["angle"]), occurrences=step["occurrences"],
                                 reference=_pattern_reference(first, step.get("axis", "Z"), step.get("axis_name"),
                                                              ("X", "Y", "Z"), "Axis", doc))
        else:
            if "plane" in step and "plane_name" in step:
                raise ValueError("Mirrored transformation takes either plane or plane_name")
            prepared_step.update(reference=_pattern_reference(first, step.get("plane", "XY"), step.get("plane_name"),
                                                              ("XY", "XZ", "YZ"), "Plane", doc))
        if "occurrences" in prepared_step:
            _check_occurrence_limit(prepared_step["occurrences"])
            instances *= prepared_step["occurrences"]
        else:
            instances *= 2
        prepared.append(prepared_step)
    if instances > MAX_TRANSFORM_INSTANCES:
        raise ValueError(f"MultiTransform would create {instances} instances; the limit is {MAX_TRANSFORM_INSTANCES}")
    return prepared


def _two_sided(feature):
    if "SideType" in feature.PropertiesList:
        return feature.SideType == "Two sides"
    return str(getattr(feature, "Type", "")) in {"TwoLengths", "TwoAngles"}


def _validate_edit_parameters(feature, parameters):
    """Check edit_feature parameters against the feature's type and current mode; returns property values."""
    type_id = feature.TypeId
    values = {}
    for key, value in parameters.items():
        property_name = _EDIT_PARAMETERS.get(key)
        owners = _EDIT_SECOND_OWNERS.get(key)
        if (property_name is None or property_name not in feature.PropertiesList
                or (owners is not None and type_id not in owners)):
            raise ValueError(f"Parameter '{key}' is not editable for {type_id}")
        if key == "reversed":
            if not isinstance(value, bool):
                raise ValueError("reversed must be boolean")
        elif key == "occurrences":
            if not _valid_count(value):
                raise ValueError("occurrences must be an integer >= 2")
            _check_occurrence_limit(value)
        elif key == "angle" and type_id == "PartDesign::Draft":
            if not _finite(value) or value == 0 or abs(value) >= 90:
                raise ValueError("Draft angle must be nonzero with |angle| < 90 degrees")
        elif key in {"angle", "second_angle"}:
            if not (_finite(value) and 0 < value <= 360):
                raise ValueError(f"Parameter '{key}' must be positive and at most 360 degrees")
        elif _positive_or_none(value) is None:
            raise ValueError(f"Parameter '{key}' must be positive")
        values[key] = value
    two_sided = _two_sided(feature)
    if "second_length" in values and not two_sided:
        raise ValueError("second_length requires an end condition with two lengths")
    if "second_angle" in values and not two_sided:
        raise ValueError("second_angle requires a two-angle rotation")
    if "second_size" in values and feature.ChamferType != "Two distances":
        raise ValueError("second_size requires a two-distances chamfer")
    if "length" in values and type_id in {"PartDesign::Pad", "PartDesign::Pocket"} and feature.Type != "Length":
        raise ValueError(f"length is not used by the end condition {feature.Type}")
    if "depth" in values and feature.DepthType != "Dimension":
        raise ValueError("depth is not used by a through-all hole")
    if type_id in {"PartDesign::Revolution", "PartDesign::Groove"} and two_sided and ("angle" in values or "second_angle" in values):
        total = values.get("angle", feature.Angle.Value) + values.get("second_angle", feature.Angle2.Value)
        if total > 360 + 1e-9:
            raise ValueError("angle + second_angle must not exceed 360")
    return {_EDIT_PARAMETERS[key]: value for key, value in values.items()}


def _dressup_selection(doc, base, selections, kind):
    """Resolve revision-checked edge/face selections and require the base to be the Body Tip."""
    from freecad_ai_bridge.geometry_ops import _selection_names

    if isinstance(selections, list) and any(not isinstance(item, dict) for item in selections):
        raise ValueError(f"{kind} entries must be revision-checked selections from select_subelement or "
                         "list_subelements; bare names are not accepted")
    names = _selection_names(doc.Name, base.Name, selections, kind)
    if len(set(names)) != len(names):
        raise ValueError(f"{kind} selections must not contain duplicates")
    body = base.getParentGeoFeatureGroup()
    if body is None or body.TypeId != "PartDesign::Body":
        raise ValueError(f"Feature '{base.Name}' must belong to a PartDesign Body")
    if body.Tip != base:
        raise ValueError(f"Base '{base.Name}' must be the Tip of Body '{body.Name}' "
                         f"(current Tip: {body.Tip.Name if body.Tip else None})")
    return names


def _dressup_base_volume(base):
    shape = getattr(base, "Shape", None)
    return 0.0 if shape is None or shape.isNull() else shape.Volume


def _dressup_effect(result, obj, base_volume, label):
    if abs(obj.Shape.Volume - base_volume) <= max(1e-9, 1e-9 * abs(base_volume)):
        raise ValueError(f"{label} '{obj.Name}' had no effect on the solid")
    return result


def _draft_plane(doc, base, plane_name, plane_selection, faces):
    import re

    if plane_name and plane_selection is not None:
        raise ValueError("Provide either plane_name or plane_selection, not both")
    if plane_selection is not None:
        from freecad_ai_bridge.geometry_ops import _resolve

        plane_doc, owner, _shape, kind = _resolve(plane_selection)
        if plane_doc.Name != doc.Name or kind != "face":
            raise ValueError("plane_selection must be a same-document face selection")
        element = plane_selection["subelement"]
    elif plane_name:
        object_name, separator, element = str(plane_name).partition(".")
        owner = _get_object(object_name, doc.Name)
        element = element if separator else ""
    else:
        raise ValueError("A neutral plane is required: plane_name ('Object.FaceN' or a datum plane name) "
                         "or plane_selection")
    if element:
        if not re.fullmatch(r"Face[1-9][0-9]*", element):
            raise ValueError(f"Neutral plane '{plane_name}' must name a face as Object.FaceN")
        shape_faces = owner.Shape.Faces
        if int(element[4:]) > len(shape_faces):
            raise ValueError(f"'{element}' is not a face of '{owner.Name}'")
        if getattr(shape_faces[int(element[4:]) - 1].Surface, "TypeId", "") != "Part::GeomPlane":
            raise ValueError("The neutral plane face must be planar")
        if owner == base and element in faces:
            raise ValueError("The neutral plane face must not be one of the drafted faces")
        return owner, [element]
    if owner.TypeId not in {"PartDesign::Plane", "App::Plane"}:
        raise ValueError(f"Neutral plane '{owner.Name}' must be a datum plane or a face (Object.FaceN)")
    return owner, []


def _float_or_none(text):
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def _thread_pitch(size):
    return _float_or_none(size.partition("x")[2]) if "x" in size else None


def _thread_size_match(sizes, requested, pitch):
    base, _separator, explicit = requested.partition("x")
    explicit_pitch = _float_or_none(explicit) if explicit else None
    if explicit and explicit_pitch is None:
        return None
    if explicit_pitch is not None and pitch is not None and abs(explicit_pitch - pitch) > 1e-9:
        raise ValueError(f"thread_size '{requested}' and thread_pitch {pitch:g} disagree")
    wanted = explicit_pitch if explicit_pitch is not None else pitch
    for size in sizes:
        size_base, _separator, size_pitch = size.partition("x")
        if size_base != base:
            continue
        if wanted is None:
            return size
        actual = _float_or_none(size_pitch)
        if actual is not None and abs(actual - wanted) <= 1e-9:
            return size
    return None


def _profile_sketch(name, doc_name, role="Profile"):
    sketch = _get_object(name, doc_name)
    if sketch.TypeId != "Sketcher::SketchObject":
        raise ValueError(f"{role} '{sketch.Name}' must be a Sketcher sketch")
    body = sketch.getParentGeoFeatureGroup()
    if body is None or body.TypeId != "PartDesign::Body":
        raise ValueError(f"{role} sketch '{sketch.Name}' must belong to a PartDesign Body")
    return sketch, body


def _require_base_solid(body, feature_kind):
    # FreeCAD 1.1 turns Pocket/Groove/SubtractiveLoft without a base into added material.
    base = body.Tip or getattr(body, "BaseFeature", None)
    shape = getattr(base, "Shape", None)
    if shape is None or shape.isNull() or not shape.Solids:
        raise ValueError(f"{feature_kind} requires an existing solid in Body '{body.Name}'")


def _rotation_axis_reference(sketch, body, axis, axis_name, doc):
    if axis_name:
        reference = _get_object(axis_name, doc.Name)
        if reference.TypeId != "PartDesign::Line":
            raise ValueError(f"Axis '{axis_name}' is not a datum axis")
        if reference.getParentGeoFeatureGroup() != body:
            raise ValueError(f"Datum axis '{axis_name}' must belong to Body '{body.Name}'")
        return reference, [""]
    axis_map = {"V": "V_Axis", "H": "H_Axis", "N": "N_Axis"}
    normalized = str(axis).upper()
    if normalized not in axis_map:
        raise ValueError("Rotation axis must be V, H, or N, or axis_name must name a datum axis")
    return sketch, [axis_map[normalized]]


def _loft_profiles(sketch_names, solid, closed, ruled, doc_name):
    if not solid:
        raise ValueError("PartDesign lofts must be solid; use Part for shells")
    if not isinstance(sketch_names, list) or len(sketch_names) < 2:
        raise ValueError("A loft requires at least two profiles")
    if len(set(sketch_names)) != len(sketch_names):
        raise ValueError("Loft profiles must be distinct sketches")
    if closed and len(sketch_names) < 3:
        raise ValueError("A closed loft requires at least three profiles")
    if closed and ruled:
        raise ValueError("FreeCAD 1.1 produces invalid geometry for closed ruled lofts; use ruled=False")
    profiles = [_profile_sketch(sketch_name, doc_name) for sketch_name in sketch_names]
    return [sketch for sketch, _body in profiles], profiles[0][1]


_PIPE_MODES = {"standard": ["Standard"], "frenet": ["Frenet"]}
_PIPE_TRANSITIONS = {"transformed": ["Transformed"], "right": ["Right corner", "RightCorner"],
                     "round": ["Round corner", "RoundCorner"]}


def _pipe_path(profile, spine_name, path_edges, orientation, transition, doc):
    """Resolve and validate the swept path before any document mutation."""
    import math

    spine = _get_object(spine_name, doc.Name)
    if spine == profile:
        raise ValueError("The spine must differ from the profile sketch")
    if "Touched" in spine.State:
        spine.recompute()
    shape = getattr(spine, "Shape", None)
    if shape is None or shape.isNull() or not shape.Edges:
        raise ValueError(f"Spine '{spine.Name}' has no edges")
    if path_edges is None:
        names = []
    else:
        if not isinstance(path_edges, list):
            raise ValueError("path_edges must be a list of EdgeN names or edge selections")
        from freecad_ai_bridge.geometry_ops import _selection_names

        names = _selection_names(doc.Name, spine.Name, path_edges, "edge") if path_edges else []
    for edge_name in names:
        suffix = edge_name[4:] if isinstance(edge_name, str) and edge_name.startswith("Edge") else ""
        if not (suffix.isdigit() and not suffix.startswith("0") and 1 <= int(suffix) <= len(shape.Edges)):
            raise ValueError(f"path_edges entry '{edge_name}' is not an edge of '{spine.Name}'")
    if len(set(names)) != len(names):
        raise ValueError("path_edges must not contain duplicates")
    if str(orientation).lower() not in _PIPE_MODES:
        raise ValueError(f"Unsupported Mode '{orientation}'; expected {', '.join(sorted(_PIPE_MODES))}")
    if str(transition).lower() not in _PIPE_TRANSITIONS:
        raise ValueError(f"Unsupported Transition '{transition}'; expected {', '.join(sorted(_PIPE_TRANSITIONS))}")
    edges = [shape.Edges[int(edge_name[4:]) - 1] for edge_name in names] if names else list(shape.Edges)
    if str(transition).lower() == "transformed":
        # FreeCAD 1.1 silently sweeps only the first segment of a path with a non-tangent joint.
        ends = [(edge.valueAt(parameter), edge.tangentAt(parameter), index)
                for index, edge in enumerate(edges) for parameter in (edge.FirstParameter, edge.LastParameter)]
        for first in range(len(ends)):
            for second in range(first + 1, len(ends)):
                (point, tangent, owner), (other, other_tangent, other_owner) = ends[first], ends[second]
                if owner != other_owner and point.distanceToPoint(other) <= 1e-7:
                    angle = tangent.getAngle(other_tangent)
                    if 1e-6 < angle < math.pi - 1e-6:
                        raise ValueError("transition 'transformed' requires a tangent-continuous path; "
                                         "use 'right' or 'round' for paths with corners")
    return spine, names


def _configure_pipe(feature, spine, edges, orientation, transition):
    feature.Spine = (spine, edges)
    _set_enum(feature, "Mode", orientation, _PIPE_MODES)
    _set_enum(feature, "Transition", transition, _PIPE_TRANSITIONS)


def _configure_rotation_sides(feature, symmetric, second_angle):
    if "Type" in feature.PropertiesList:
        feature.Type = "TwoAngles" if second_angle is not None else "Angle"
    if "Midplane" in feature.PropertiesList:
        feature.Midplane = symmetric
    if "Angle2" in feature.PropertiesList and second_angle is not None:
        feature.Angle2 = second_angle
    if "SideType" in feature.PropertiesList:
        feature.SideType = "Symmetric" if symmetric else ("Two sides" if second_angle is not None else "One side")


def _set_enum(obj, property_name, requested, aliases):
    normalized = str(requested).lower()
    if normalized not in aliases:
        raise ValueError(f"Unsupported {property_name} '{requested}'; expected {', '.join(sorted(aliases))}")
    if property_name not in obj.PropertiesList:
        if normalized != next(iter(aliases)):
            raise ValueError(f"FreeCAD runtime does not expose {property_name}")
        return
    available = obj.getEnumerationsOfProperty(property_name)
    for candidate in aliases[normalized]:
        if candidate in available:
            setattr(obj, property_name, candidate)
            return
    raise ValueError(f"FreeCAD runtime does not support {property_name} '{requested}'; available: {available}")


def _configure_extrusion(feature, condition, length, symmetric, reversed,
                         second_length, target, doc):
    feature.Length = length
    if "SideType" in feature.PropertiesList:
        feature.SideType = "Symmetric" if symmetric else ("Two sides" if condition == "two_lengths" else "One side")
    elif "Midplane" in feature.PropertiesList:
        feature.Midplane = symmetric
    if "Reversed" in feature.PropertiesList:
        feature.Reversed = reversed
    feature.Type = _EXTRUSION_TYPES[condition]
    if condition == "two_lengths":
        feature.Length2 = second_length
        if "Type2" in feature.PropertiesList:
            feature.Type2 = "Length"
    elif condition == "up_to_face":
        owner, subelement = target
        feature.UpToFace = (owner, [subelement])


def _resolve_extrusion_target(selection, doc):
    from freecad_ai_bridge.geometry_ops import _resolve

    target_doc, owner, _shape, kind = _resolve(selection)
    if target_doc.Name != doc.Name:
        raise ValueError("Target face must be in the feature document")
    if kind != "face":
        raise ValueError(f"up_to_face target must be a face, not a {kind}")
    return owner, selection["subelement"]


def _origin_reference(feature, selection, allowed, kind):
    selection = selection.upper()
    if selection not in allowed:
        raise ValueError(f"Unknown {kind.lower()} '{selection}'; expected {', '.join(allowed)}")
    body = feature.getParentGeoFeatureGroup()
    if body is None or body.TypeId != "PartDesign::Body":
        raise ValueError(f"Feature '{feature.Name}' must belong to a PartDesign Body")
    role = f"{selection}_{kind}"
    for origin_feature in body.Origin.OriginFeatures:
        if origin_feature.Role == role:
            return origin_feature
    raise ValueError(f"Body origin has no {role}")


def _pattern_originals(first, additional_names, doc):
    body = first.getParentGeoFeatureGroup()
    if body is None or body.TypeId != "PartDesign::Body":
        raise ValueError(f"Feature '{first.Name}' must belong to a PartDesign Body")
    originals = [first]
    for name in additional_names or []:
        obj = _get_object(name, doc.Name)
        if obj.getParentGeoFeatureGroup() != body:
            raise ValueError("All pattern originals must belong to the same PartDesign Body")
        if obj not in originals:
            originals.append(obj)
    return originals, body


def _pattern_reference(feature, selection, datum_name, allowed, kind, doc):
    if datum_name:
        reference = _get_object(datum_name, doc.Name)
        expected = "PartDesign::Line" if kind == "Axis" else "PartDesign::Plane"
        if reference.TypeId != expected or reference.getParentGeoFeatureGroup() != feature.getParentGeoFeatureGroup():
            raise ValueError(f"{datum_name} must be a {expected} in the same Body")
        return reference
    return _origin_reference(feature, selection, allowed, kind)


def _add_to_body(reference_obj, new_obj, doc):
    """Add new_obj to the same body as reference_obj."""
    for obj in doc.Objects:
        if obj.TypeId == "PartDesign::Body":
            if hasattr(obj, "Group") and reference_obj in obj.Group:
                previous_tip = obj.Tip
                obj.addObject(new_obj)
                if previous_tip:
                    previous_tip.Visibility = False
                return
    # If reference is itself in the model tree, try to find body through InList
    if hasattr(reference_obj, "InList"):
        for parent in reference_obj.InList:
            if parent.TypeId == "PartDesign::Body":
                previous_tip = parent.Tip
                parent.addObject(new_obj)
                if previous_tip:
                    previous_tip.Visibility = False
                return


_ADDSUB_TYPES = {"PartDesign::Pad", "PartDesign::Pocket", "PartDesign::Revolution", "PartDesign::Groove",
                 "PartDesign::AdditiveLoft", "PartDesign::SubtractiveLoft", "PartDesign::AdditivePipe",
                 "PartDesign::SubtractivePipe", "PartDesign::Hole"}


def _feature_result(obj, hint=None) -> dict:
    """Build a standard result dict for a feature."""
    if "Invalid" in obj.State:
        status = obj.getStatusString()
        if hint and (status in {"", "Invalid", "Valid"} or "BRep_API" in status):
            status = f"{status or 'no valid result'}; {hint}"
        raise ValueError(f"Feature '{obj.Name}' failed: {status}")
    if obj.Shape.isNull():
        raise ValueError(f"Feature '{obj.Name}' produced no shape")
    if not obj.Shape.isValid():
        raise ValueError(f"Feature '{obj.Name}' produced invalid BRep geometry")
    if len(obj.Shape.Solids) != 1:
        raise ValueError(f"Feature '{obj.Name}' must produce one connected solid")
    if obj.TypeId in _ADDSUB_TYPES and abs(obj.AddSubShape.Volume) <= 1e-6:
        raise ValueError(f"Feature '{obj.Name}' has a degenerate tool shape without volume")
    result = {
        "name": obj.Name,
        "label": obj.Label,
        "type": obj.TypeId,
    }
    if hasattr(obj, "Shape") and obj.Shape and not obj.Shape.isNull():
        result["shape_valid"] = obj.Shape.isValid()
        result["volume"] = obj.Shape.Volume
    return result
